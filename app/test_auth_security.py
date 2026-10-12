from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app import main
from app.database import Base
from app import rag_service, retrieval_service
from app.main import app as fastapi_app
from app.models import Document, InterviewSession, Question, UserProfile
from app.ownership import get_owned_document, get_owned_question, get_owned_session
from app.rag_qa_service import answer_from_documents


PROJECT_URL = "https://agenthire-test.supabase.co"
ISSUER = f"{PROJECT_URL}/auth/v1"
TEST_USER_ID = UUID("b652a8da-0984-4efc-8e5a-e9d2e334ac1e")


class LocalJwksClient:
    def __init__(self, jwk):
        self.jwk = jwk

    def get_signing_key_from_jwt(self, token):
        header = jwt.get_unverified_header(token)
        if header.get("kid") != "current-key":
            raise jwt.PyJWKClientError("Unknown signing key.")
        return self.jwk


@pytest.fixture
def token_factory(monkeypatch):
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_jwk = json.loads(
        jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key())
    )
    public_jwk.update({"kid": "current-key", "alg": "ES256"})
    signing_key = jwt.PyJWK.from_dict(public_jwk)
    monkeypatch.setattr(
        auth,
        "_jwks_client",
        lambda _url: LocalJwksClient(signing_key),
    )

    def create_token(**overrides):
        claims = {
            "sub": str(TEST_USER_ID),
            "iss": ISSUER,
            "aud": "authenticated",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        claims.update(overrides)
        return jwt.encode(
            claims,
            private_key,
            algorithm="ES256",
            headers={"kid": "current-key"},
        )

    return create_token


def test_es256_access_token_validates_signature_and_claims(token_factory):
    claims = auth.decode_access_token(token_factory(), PROJECT_URL)
    assert claims["sub"] == str(TEST_USER_ID)
    assert claims["aud"] == "authenticated"


@pytest.mark.parametrize(
    "claim,value",
    [
        ("iss", "https://another-project.supabase.co/auth/v1"),
        ("aud", "anon"),
        ("sub", "not-a-uuid"),
        ("exp", datetime.now(timezone.utc) - timedelta(minutes=1)),
        ("nbf", datetime.now(timezone.utc) + timedelta(minutes=5)),
    ],
)
def test_invalid_claims_are_rejected(token_factory, claim, value):
    with pytest.raises(HTTPException) as error:
        auth.decode_access_token(token_factory(**{claim: value}), PROJECT_URL)
    assert error.value.status_code == 401


def test_unknown_kid_is_rejected(token_factory):
    token = token_factory()
    claims = jwt.decode(
        token,
        options={
            "verify_signature": False,
            "verify_exp": False,
            "verify_aud": False,
            "verify_iss": False,
        },
    )
    private_key = ec.generate_private_key(ec.SECP256R1())
    unknown_key_token = jwt.encode(
        claims,
        private_key,
        algorithm="ES256",
        headers={"kid": "revoked-or-unknown"},
    )
    with pytest.raises(HTTPException) as error:
        auth.decode_access_token(unknown_key_token, PROJECT_URL)
    assert error.value.status_code == 401


def test_hs256_is_rejected_even_if_a_legacy_key_exists():
    token = jwt.encode(
        {
            "sub": str(TEST_USER_ID),
            "iss": ISSUER,
            "aud": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "legacy-key-not-used-for-token-verification",
        algorithm="HS256",
        headers={"kid": "current-key"},
    )
    with pytest.raises(HTTPException) as error:
        auth.decode_access_token(token, PROJECT_URL)
    assert error.value.status_code == 401


def test_missing_bearer_token_is_unauthorized():
    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials=None, db=None)
    assert error.value.status_code == 401


def test_local_frontend_origin_is_allowed_by_cors():
    with TestClient(fastapi_app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )


def test_auth_me_returns_verified_profile_and_unauthenticated_calls_get_401():
    profile = UserProfile(id=TEST_USER_ID, role="user", is_active=False)
    fastapi_app.dependency_overrides[auth.get_current_user] = lambda: profile
    try:
        with TestClient(fastapi_app) as client:
            response = client.get("/api/v1/auth/me")
            assert response.status_code == 200
            assert response.json() == {
                "id": str(TEST_USER_ID),
                "role": "user",
                "is_active": False,
            }
            assert response.headers["cache-control"] == "no-store"
            fastapi_app.dependency_overrides.clear()
            unauthenticated = client.get("/api/v1/auth/me")
            assert unauthenticated.status_code == 401
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/v1/interview/question", "POST"),
        ("/api/v1/interview/evaluate", "POST"),
        ("/api/v1/interview/run", "POST"),
        ("/api/v1/interview/session", "POST"),
        (
            "/api/v1/interview/sessions/{session_id}/questions/{question_id}/answer",
            "POST",
        ),
        ("/api/v1/interview/sessions/{session_id}/report", "GET"),
        ("/api/v1/documents/upload", "POST"),
        ("/api/v1/search", "POST"),
        ("/api/v1/ask", "POST"),
        ("/api/v1/auth/me", "GET"),
    ],
)
def test_sensitive_api_routes_require_verified_user(path, method):
    route = next(
        route
        for route in fastapi_app.routes
        if getattr(route, "path", None) == path
        and method in getattr(route, "methods", set())
    )
    required_dependency = (
        auth.get_current_user
        if path == "/api/v1/auth/me"
        else auth.get_active_user
    )
    assert any(
        dependency.call is required_dependency
        for dependency in route.dependant.dependencies
    )


def test_authenticated_profile_is_loaded_only_by_verified_subject(monkeypatch):
    profile = UserProfile(id=TEST_USER_ID, role="user")

    class ProfileDatabase:
        def get(self, model, user_id):
            assert model is UserProfile
            assert user_id == TEST_USER_ID
            return profile

    monkeypatch.setattr(auth.auth_settings, "supabase_url", PROJECT_URL)
    monkeypatch.setattr(
        auth,
        "decode_access_token",
        lambda _token, _url: {"sub": str(TEST_USER_ID)},
    )
    result = auth.get_current_user(
        credentials=SimpleNamespace(scheme="Bearer", credentials="verified"),
        db=ProfileDatabase(),
    )
    assert result is profile
    assert result.role == "user"


@pytest.mark.parametrize("sqlstate", ["42P01", "42703"])
def test_missing_profile_schema_returns_safe_migration_error(
    monkeypatch,
    caplog,
    sqlstate,
):
    class MissingProfileTable:
        pass

    MissingProfileTable.sqlstate = sqlstate

    class MissingProfileDatabase:
        def get(self, _model, _user_id):
            raise ProgrammingError(
                "SELECT user_profiles",
                {},
                MissingProfileTable(),
            )

    monkeypatch.setattr(auth.auth_settings, "supabase_url", PROJECT_URL)
    monkeypatch.setattr(
        auth,
        "decode_access_token",
        lambda _token, _url: {"sub": str(TEST_USER_ID)},
    )

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(
            credentials=SimpleNamespace(
                scheme="Bearer",
                credentials="verified",
            ),
            db=MissingProfileDatabase(),
        )

    assert error.value.status_code == 503
    assert error.value.detail == (
        "Authentication database schema is not initialized."
    )
    assert "apply the latest user profile migration" in caplog.text


def test_valid_es256_token_creates_owned_interview_session(
    token_factory,
    monkeypatch,
):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        Base.metadata.tables[table_name]
        for table_name in ("user_profiles", "interview_sessions", "questions")
    ]
    Base.metadata.create_all(engine, tables=tables)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as db:
        db.add(UserProfile(id=TEST_USER_ID, is_active=True))
        db.commit()

    def get_test_db():
        with session_factory() as db:
            yield db

    generated_questions = {
        "questions": [
            {
                "question": f"Question {index}",
                "topic": "Testing",
                "difficulty": "Easy",
            }
            for index in range(1, 6)
        ]
    }
    monkeypatch.setattr(auth.auth_settings, "supabase_url", PROJECT_URL)
    monkeypatch.setattr(main, "SessionLocal", session_factory)
    monkeypatch.setattr(
        main,
        "generate_interview_questions",
        lambda **_kwargs: generated_questions,
    )
    fastapi_app.dependency_overrides[auth.get_db] = get_test_db
    try:
        with TestClient(fastapi_app) as client:
            response = client.post(
                "/api/v1/interview/session",
                json={
                    "job_description": "Test role",
                    "number_of_questions": 5,
                },
                headers={"Authorization": f"Bearer {token_factory()}"},
            )

        assert response.status_code == 200
        payload = response.json()
        session_id = UUID(payload["session_id"])
        question_ids = [UUID(item["question_id"]) for item in payload["questions"]]
        assert payload["total_questions"] == 5
        with session_factory() as db:
            stored_session = db.get(InterviewSession, session_id)
            stored_questions = (
                db.query(Question)
                .filter(Question.session_id == session_id)
                .order_by(Question.question_order)
                .all()
            )
        assert stored_session is not None
        assert stored_session.owner_id == TEST_USER_ID
        assert [question.id for question in stored_questions] == question_ids
    finally:
        fastapi_app.dependency_overrides.clear()
        engine.dispose()


def test_revoked_valid_token_is_denied_then_reenabled_without_data_loss(
    token_factory,
    monkeypatch,
):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        UserProfile.__table__,
        InterviewSession.__table__,
        Question.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    original_session_id = uuid4()
    with session_factory() as db:
        db.add(UserProfile(id=TEST_USER_ID, is_active=False))
        db.add(
            InterviewSession(
                id=original_session_id,
                job_title="Saved interview",
                job_description="Keep this data.",
                owner_id=TEST_USER_ID,
            )
        )
        db.commit()

    def get_test_db():
        with session_factory() as db:
            yield db

    monkeypatch.setattr(auth.auth_settings, "supabase_url", PROJECT_URL)
    monkeypatch.setattr(main, "SessionLocal", session_factory)
    monkeypatch.setattr(
        main,
        "generate_interview_questions",
        lambda **_kwargs: {
            "questions": [
                {
                    "question": f"Question {index}",
                    "topic": "Testing",
                    "difficulty": "Easy",
                }
                for index in range(1, 6)
            ]
        },
    )
    fastapi_app.dependency_overrides[auth.get_db] = get_test_db
    headers = {"Authorization": f"Bearer {token_factory()}"}
    request_body = {
        "job_description": "Test role",
        "number_of_questions": 5,
    }
    try:
        with TestClient(fastapi_app) as client:
            denied = client.post(
                "/api/v1/interview/session",
                json=request_body,
                headers=headers,
            )
            assert denied.status_code == 403

            with session_factory() as db:
                profile = db.get(UserProfile, TEST_USER_ID)
                profile.is_active = True
                db.commit()

            allowed = client.post(
                "/api/v1/interview/session",
                json=request_body,
                headers=headers,
            )
            assert allowed.status_code == 200
            assert client.get(
                f"/api/v1/interview/sessions/{original_session_id}/report",
                headers=headers,
            ).status_code == 200

            with session_factory() as db:
                profile = db.get(UserProfile, TEST_USER_ID)
                profile.is_active = False
                db.commit()
                assert db.get(InterviewSession, original_session_id) is not None
                assert (
                    db.query(InterviewSession)
                    .filter(InterviewSession.owner_id == TEST_USER_ID)
                    .count()
                    == 2
                )

            revoked_report = client.get(
                f"/api/v1/interview/sessions/{original_session_id}/report",
                headers=headers,
            )
            assert revoked_report.status_code == 403
    finally:
        fastapi_app.dependency_overrides.clear()
        engine.dispose()


def test_user_profile_role_defaults_to_user_on_insert():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    UserProfile.__table__.create(engine)
    try:
        with Session(engine) as db:
            profile = UserProfile(id=uuid4())
            db.add(profile)
            db.flush()
            assert profile.role == "user"
    finally:
        engine.dispose()


def test_owned_resources_exclude_other_users_and_legacy_rows():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        UserProfile.__table__,
        InterviewSession.__table__,
        Question.__table__,
        Document.__table__,
    ]
    UserProfile.__table__.create(engine)
    for table in tables[1:]:
        table.create(engine)

    owner_id = uuid4()
    other_id = uuid4()
    session_id = uuid4()
    question_id = uuid4()
    document_id = uuid4()
    legacy_session_id = uuid4()
    legacy_document_id = uuid4()
    try:
        with Session(engine) as db:
            db.add_all(
                [
                    UserProfile(id=owner_id),
                    UserProfile(id=other_id),
                    InterviewSession(
                        id=session_id,
                        job_title="Engineer",
                        job_description="A test role.",
                        owner_id=owner_id,
                    ),
                    InterviewSession(
                        id=legacy_session_id,
                        job_title="Legacy",
                        job_description="Unowned record.",
                    ),
                    Question(
                        id=question_id,
                        session_id=session_id,
                        question_text="Question?",
                        skill="Testing",
                        difficulty="Easy",
                        question_order=1,
                    ),
                    Document(
                        id=document_id,
                        filename="owned.txt",
                        owner_id=owner_id,
                    ),
                    Document(
                        id=legacy_document_id,
                        filename="legacy.txt",
                    ),
                ]
            )
            db.commit()

            assert get_owned_session(db, session_id, owner_id) is not None
            assert get_owned_session(db, session_id, other_id) is None
            assert get_owned_session(db, legacy_session_id, owner_id) is None
            assert (
                get_owned_question(db, question_id, session_id, owner_id)
                is not None
            )
            assert (
                get_owned_question(db, question_id, session_id, other_id)
                is None
            )
            assert get_owned_document(db, document_id, owner_id) is not None
            assert get_owned_document(db, document_id, other_id) is None
            assert get_owned_document(db, legacy_document_id, owner_id) is None
    finally:
        engine.dispose()


def test_semantic_search_query_is_scoped_to_authenticated_owner(monkeypatch):
    owner_id = uuid4()

    class QueryDatabase:
        statement = None

        def execute(self, statement):
            self.statement = statement
            return SimpleNamespace(all=lambda: [])

    db = QueryDatabase()
    monkeypatch.setattr(retrieval_service, "embed_text", lambda _text: [0.0] * 384)

    assert retrieval_service.search_documents(
        db,
        "role skills",
        owner_id=owner_id,
    ) == []

    compiled = db.statement.compile(dialect=postgresql.dialect())
    assert "documents.owner_id" in str(compiled)
    assert owner_id in compiled.params.values()


def test_rag_passes_owner_filter_and_preserves_source_citations(monkeypatch):
    owner_id = uuid4()
    search_call = {}

    def fake_search_documents(**kwargs):
        search_call.update(kwargs)
        return [
            {
                "document_id": str(uuid4()),
                "filename": "job.pdf",
                "document_type": "job_description",
                "chunk_index": 0,
                "content": "Python and FastAPI experience required.",
                "cosine_distance": 0.1,
            }
        ]

    monkeypatch.setattr(
        "app.rag_qa_service.search_documents",
        fake_search_documents,
    )
    monkeypatch.setattr(
        "app.rag_qa_service.chat_completion",
        lambda prompt: "Python experience is required. [Source 1]",
    )
    result = answer_from_documents(
        db=object(),
        question="What experience is required?",
        owner_id=owner_id,
    )

    assert search_call["owner_id"] == owner_id
    assert result["answer"].endswith("[Source 1]")
    assert result["sources"][0]["filename"] == "job.pdf"


def test_document_indexing_stores_authenticated_owner(monkeypatch):
    owner_id = uuid4()

    class DocumentDatabase:
        def __init__(self):
            self.documents = []

        def add(self, item):
            if isinstance(item, Document):
                item.id = uuid4()
                self.documents.append(item)

        def flush(self):
            pass

        def commit(self):
            pass

        def refresh(self, _item):
            pass

        def rollback(self):
            pass

    db = DocumentDatabase()
    monkeypatch.setattr(rag_service, "split_text", lambda _text: ["indexed chunk"])
    monkeypatch.setattr(rag_service, "embed_text", lambda _text: [0.0] * 384)

    result = rag_service.index_document(
        db=db,
        filename="job.pdf",
        text="Job description text.",
        owner_id=owner_id,
    )

    assert result["status"] == "indexed"
    assert db.documents[0].owner_id == owner_id
