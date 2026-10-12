from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import cast
from uuid import UUID, uuid4
import json
from app.models import (
    InterviewSession,
    Question,
    CandidateAnswer,
    Evaluation,
    UserProfile,
)
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.auth import get_active_user, get_current_user
from app.admin_routes import router as admin_router
from app.database import SessionLocal
from app.document_schemas import DocumentUploadResponse
from app.document_service import (
    extract_text_from_pdf,
    extract_text_from_txt,
)
from app.interview_graph import (
    InterviewState,
    question_graph,
    evaluation_graph,
    interview_graph,
)
from app.interview_service import generate_interview_questions
from app.rag_qa_service import answer_from_documents
from app.rag_service import index_document
from app.retrieval_service import search_documents
from app.ownership import get_owned_question, get_owned_session
# =========================================================
# APPLICATION SETTINGS
# =========================================================
class Settings(BaseSettings):
    app_name: str = "AgentHire AI"
    app_env: str = "development"
    frontend_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
settings = Settings()
app = FastAPI(
    title=settings.app_name,
    description="Agentic AI interview platform",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip().rstrip("/")
        for origin in settings.frontend_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin_router)
# =========================================================
# SEMANTIC SEARCH SCHEMAS
# =========================================================
class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)
    document_type: str | None = Field(
        default=None,
        max_length=50,
    )
class SearchResult(BaseModel):
    document_id: str
    filename: str
    document_type: str
    chunk_index: int
    content: str
    cosine_distance: float
class SearchResponse(BaseModel):
    query: str
    results_count: int
    results: list[SearchResult]
# =========================================================
# RAG QUESTION-ANSWERING SCHEMAS
# =========================================================
class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=3, ge=1, le=10)
    document_type: str | None = Field(
        default="job_description",
        max_length=50,
    )
class AskSource(BaseModel):
    source_number: int
    document_id: str
    filename: str
    chunk_index: int
class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[AskSource]
# =========================================================
# SINGLE-QUESTION AND COMBINED INTERVIEW SCHEMAS
# =========================================================
class InterviewRunRequest(BaseModel):
    job_description: str = Field(
        min_length=1,
        max_length=12000,
    )
    candidate_answer: str = Field(
        min_length=1,
        max_length=5000,
    )
class InterviewRunResponse(BaseModel):
    question: str
    score: int
    strengths: list[str]
    improvements: list[str]
    feedback: str
    sample_answer: str
    next_action: str
class InterviewQuestionRequest(BaseModel):
    job_description: str = Field(
        min_length=1,
        max_length=12000,
    )
class InterviewQuestionResponse(BaseModel):
    question_id: str
    question: str
    topic: str
    difficulty: str
    expected_answer: str
class InterviewAnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    candidate_answer: str = Field(
        min_length=1,
        max_length=5000,
    )
    expected_answer: str = Field(
        default="",
        max_length=2000,
    )
class InterviewAnswerResponse(BaseModel):
    question: str
    score: int
    strengths: list[str]
    improvements: list[str]
    feedback: str
    sample_answer: str
    next_action: str
# =========================================================
# MULTI-QUESTION SESSION SCHEMAS
# =========================================================
class InterviewSessionRequest(BaseModel):
    job_description: str = Field(
        min_length=1,
        max_length=12000,
    )
    number_of_questions: int = Field(
        default=5,
        ge=1,
        le=5,
    )
class InterviewSessionResponse(BaseModel):
    session_id: str
    total_questions: int
    questions: list[InterviewQuestionResponse]

class SubmitInterviewAnswerRequest(BaseModel):
    candidate_answer: str = Field(min_length=1, max_length=5000)

class InterviewReportQuestion(BaseModel):
    question_id: str
    question_order: int
    question: str
    skill: str
    difficulty: str
    answered: bool
    candidate_answer: str | None = None
    score: int | None = None
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    feedback: str | None = None
    sample_answer: str | None = None


class InterviewReportResponse(BaseModel):
    session_id: str
    job_title: str
    status: str
    total_questions: int
    answered_questions: int
    average_score: float | None
    performance_percentage: float | None
    completed: bool
    strengths: list[str]
    improvement_areas: list[str]
    questions: list[InterviewReportQuestion]


class AuthMeResponse(BaseModel):
    id: str
    role: str
    is_active: bool


# =========================================================
# BASIC ENDPOINTS
# =========================================================
@app.get("/")
def root():
    return {
        "message": "Welcome to AgentHire AI",
        "status": "running",
        "environment": settings.app_env,
    }
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "agenthire-ai-api",
    }


@app.get("/api/v1/auth/me", response_model=AuthMeResponse)
def get_authenticated_profile(
    response: Response,
    current_user: UserProfile = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    return AuthMeResponse(
        id=str(current_user.id),
        role=current_user.role,
        is_active=current_user.is_active,
    )


# =========================================================
# SEMANTIC SEARCH
# =========================================================
@app.post(
    "/api/v1/search",
    response_model=SearchResponse,
)
def semantic_search(
    request: SearchRequest,
    current_user: UserProfile = Depends(get_active_user),
):
    db = SessionLocal()
    try:
        results = search_documents(
            db=db,
            query=request.query,
            limit=request.limit,
            document_type=request.document_type,
            owner_id=current_user.id,
        )
        return SearchResponse(
    query=request.query,
    results_count=len(results),
    results=[
        SearchResult(**item) if isinstance(item, dict) else item
        for item in results
    ],
)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        print(
            f"Semantic search error: "
            f"{type(exc).__name__}: {exc}"
        )
        raise HTTPException(
            status_code=500,
            detail="Semantic search failed. Check server logs.",
        ) from None
    finally:
        db.close()
# =========================================================
# RAG QUESTION-ANSWERING
# =========================================================
@app.post(
    "/api/v1/ask",
    response_model=AskResponse,
)
def ask_documents(
    request: AskRequest,
    current_user: UserProfile = Depends(get_active_user),
):
    db = SessionLocal()
    try:
        result = answer_from_documents(
            db=db,
            question=request.question,
            limit=request.limit,
            document_type=request.document_type,
            owner_id=current_user.id,
        )
        return AskResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        print(
            f"RAG question-answering error: "
            f"{type(exc).__name__}: {exc}"
        )
        raise HTTPException(
            status_code=500,
            detail="Question answering failed. Check server logs.",
        ) from None
    finally:
        db.close()
# =========================================================
# DOCUMENT UPLOAD AND INDEXING
# =========================================================
@app.post(
    "/api/v1/documents/upload",
    response_model=DocumentUploadResponse,
)
def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("job_description"),
    current_user: UserProfile = Depends(get_active_user),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".txt"}:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and TXT files are supported.",
        )
    max_file_size = 5 * 1024 * 1024
    temp_path = None
    db = None
    try:
        content = file.file.read(max_file_size + 1)
        if not content:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )
        if len(content) > max_file_size:
            raise HTTPException(
                status_code=413,
                detail="File size must not exceed 5 MB.",
            )
        with NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        if suffix == ".pdf":
            extracted_text = extract_text_from_pdf(temp_path)
        else:
            extracted_text = extract_text_from_txt(temp_path)
        db = SessionLocal()
        return index_document(
            db=db,
            filename=Path(file.filename or "document").name,
            text=extracted_text,
            document_type=document_type,
            owner_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        print(
            f"Document processing error: "
            f"{type(exc).__name__}: {exc}"
        )
        raise HTTPException(
            status_code=500,
            detail="Document processing failed. Check server logs.",
        ) from None
    finally:
        if db is not None:
            db.close()
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
        file.file.close()
# =========================================================
# STAGE 1: GENERATE ONE INTERVIEW QUESTION
# =========================================================
@app.post(
    "/api/v1/interview/question",
    response_model=InterviewQuestionResponse,
)
def generate_interview_question(
    request: InterviewQuestionRequest,
    current_user: UserProfile = Depends(get_active_user),
):
    try:
        result = question_graph.invoke(
            {"job_description": request.job_description}
        )
        return InterviewQuestionResponse(
            question=result["question"],
            topic=result["topic"],
            difficulty=result["difficulty"],
            expected_answer=result["expected_answer"],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        print(
            f"Question generation error: "
            f"{type(exc).__name__}: {exc}"
        )
        raise HTTPException(
            status_code=502,
            detail="Question generation failed. Check server logs.",
        ) from None
# =========================================================
# STAGE 2: EVALUATE ONE ANSWER
# =========================================================
@app.post(
    "/api/v1/interview/evaluate",
    response_model=InterviewAnswerResponse,
)
def evaluate_interview_answer(
    request: InterviewAnswerRequest,
    current_user: UserProfile = Depends(get_active_user),
):
    try:
        evaluation_input = cast(
            InterviewState,
            {
                "question": request.question,
                "candidate_answer": request.candidate_answer,
                "expected_answer": request.expected_answer,
            },
        )
        result = evaluation_graph.invoke(evaluation_input)
        return InterviewAnswerResponse(
            question=request.question,
            score=result["score"],
            strengths=result["strengths"],
            improvements=result["improvements"],
            feedback=result["feedback"],
            sample_answer=result["sample_answer"],
            next_action=result["next_action"],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        print(
            f"Answer evaluation error: "
            f"{type(exc).__name__}: {exc}"
        )
        raise HTTPException(
            status_code=502,
            detail="Answer evaluation failed. Check server logs.",
        ) from None
# =========================================================
# ORIGINAL COMBINED INTERVIEW ENDPOINT
# =========================================================
@app.post(
    "/api/v1/interview/run",
    response_model=InterviewRunResponse,
)
def run_interview(
    request: InterviewRunRequest,
    current_user: UserProfile = Depends(get_active_user),
):
    try:
        result = interview_graph.invoke(
            {
                "job_description": request.job_description,
                "candidate_answer": request.candidate_answer,
            }
        )
        return InterviewRunResponse(
            question=result["question"],
            score=result["score"],
            strengths=result["strengths"],
            improvements=result["improvements"],
            feedback=result["feedback"],
            sample_answer=result["sample_answer"],
            next_action=result["next_action"],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        print(
            f"Interview workflow error: "
            f"{type(exc).__name__}: {exc}"
        )
        raise HTTPException(
            status_code=502,
            detail="The interview workflow failed. Check server logs.",
        ) from None
# =========================================================
# CREATE A MULTI-QUESTION INTERVIEW SESSION
# =========================================================
@app.post(
    "/api/v1/interview/session",
    response_model=InterviewSessionResponse,
)
def create_interview_session(
    request: InterviewSessionRequest,
    current_user: UserProfile = Depends(get_active_user),
):
    db = SessionLocal()
    try:
        # Generate interview questions using the existing AI service.
        result = generate_interview_questions(
            job_description=request.job_description,
            number_of_questions=request.number_of_questions,
        )
        generated_questions = result.get("questions", [])
        if len(generated_questions) != request.number_of_questions:
            raise RuntimeError(
                "The AI returned an unexpected number of questions."
            )
        # Derive a title from the job description.
        job_title = request.job_description.strip().splitlines()[0][:200]
        # Create and save the interview session.
        session = InterviewSession(
            job_title=job_title,
            job_description=request.job_description,
            owner_id=current_user.id,
            status="created",
        )
        db.add(session)
        db.flush()
        # Save each generated question under this session.
        response_questions = []
        for index, item in enumerate(generated_questions, start=1):
            question = Question(
                session_id=session.id,
                question_text=item["question"],
                skill=item["topic"],
                difficulty=item["difficulty"],
                question_order=index,
            )
            db.add(question)
            db.flush()
            response_questions.append(
                InterviewQuestionResponse(
                    question_id=str(question.id),
                    question=item["question"],
                    topic=item["topic"],
                    difficulty=item["difficulty"],
                    expected_answer=(
                        f"Topic: {item['topic']}. "
                        f"Difficulty: {item['difficulty']}."
                    ),
                )
            )
        # Commit the session and all its questions together.
        db.commit()
        db.refresh(session)
        return InterviewSessionResponse(
            session_id=str(session.id),
            total_questions=len(response_questions),
            questions=response_questions,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="Question generation returned invalid data. "
                   "Check server logs.",
        ) from exc
    except Exception as exc:
        db.rollback()
        print(
            f"Interview session creation error: "
            f"{type(exc).__name__}: {exc}"
        )
        raise HTTPException(
            status_code=502,
            detail="Interview session creation failed. "
                   "Check server logs.",
        ) from None
    finally:
        db.close()

# =========================================================
# PERSIST AN ANSWER AND ITS AI EVALUATION
# =========================================================

@app.post(
    "/api/v1/interview/sessions/{session_id}/questions/{question_id}/answer",
)
def submit_interview_answer(
    session_id: str,
    question_id: str,
    request: SubmitInterviewAnswerRequest,
    current_user: UserProfile = Depends(get_active_user),
):
    db = SessionLocal()
    try:
        try:
            session_uuid = UUID(session_id)
            question_uuid = UUID(question_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid session ID or question ID.",
            ) from exc

        session = get_owned_session(db, session_uuid, current_user.id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found.")

        question = get_owned_question(
            db,
            question_uuid,
            session_uuid,
            current_user.id,
        )
        if question is None:
            raise HTTPException(
                status_code=404,
                detail="Question not found in this interview session.",
            )

        evaluation_input = cast(
            InterviewState,
            {
                "question": question.question_text,
                "candidate_answer": request.candidate_answer.strip(),
                "expected_answer": (
                    f"Topic: {question.skill}. "
                    f"Difficulty: {question.difficulty}."
                ),
            },
        )
        result = evaluation_graph.invoke(evaluation_input)

        answer = CandidateAnswer(
            question_id=question.id,
            answer_text=request.candidate_answer.strip(),
        )
        db.add(answer)
        db.flush()

        evaluation = Evaluation(
            answer_id=answer.id,
            score=result["score"],
            strengths=json.dumps(result["strengths"]),
            improvement_areas=json.dumps(result["improvements"]),
            evidence=result["feedback"],
            feedback=result["feedback"],
            sample_answer=result["sample_answer"],
        )
        db.add(evaluation)
        db.commit()
        db.refresh(answer)
        db.refresh(evaluation)

        return {
            "session_id": str(session.id),
            "question_id": str(question.id),
            "answer_id": str(answer.id),
            "evaluation_id": str(evaluation.id),
            "question": question.question_text,
            "candidate_answer": answer.answer_text,
            "score": evaluation.score,
            "strengths": result["strengths"],
            "improvements": result["improvements"],
            "feedback": evaluation.feedback,
            "sample_answer": evaluation.sample_answer,
            "next_action": result["next_action"],
        }
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="Answer evaluation returned invalid data.",
        ) from exc
    except Exception as exc:
        db.rollback()
        print(f"Persistent answer evaluation error: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=502,
            detail="Answer evaluation failed. Check server logs.",
        ) from None
    finally:
        db.close()


@app.get(
    "/api/v1/interview/sessions/{session_id}/report",
    response_model=InterviewReportResponse,
)
def get_interview_report(
    session_id: str,
    current_user: UserProfile = Depends(get_active_user),
):
    db = SessionLocal()

    try:
        try:
            session_uuid = UUID(session_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid interview session ID.",
            ) from exc

        session = get_owned_session(db, session_uuid, current_user.id)

        if session is None:
            raise HTTPException(
                status_code=404,
                detail="Interview session not found.",
            )

        questions = (
            db.query(Question)
            .filter(Question.session_id == session_uuid)
            .order_by(Question.question_order)
            .all()
        )

        report_questions = []
        all_scores = []
        overall_strengths = []
        overall_improvements = []
        answered_count = 0

        for question in questions:
            answer = (
                db.query(CandidateAnswer)
                .filter(CandidateAnswer.question_id == question.id)
                .order_by(CandidateAnswer.submitted_at.desc())
                .first()
            )

            evaluation = None

            if answer is not None:
                answered_count += 1
                evaluation = (
                    db.query(Evaluation)
                    .filter(Evaluation.answer_id == answer.id)
                    .first()
                )

            score = evaluation.score if evaluation else None

            if score is not None:
                all_scores.append(score)

            strengths = []
            improvements = []
            feedback = None
            sample_answer = None

            if evaluation is not None:
                # The existing database stores strengths and improvement
                # areas as text, so support JSON arrays and plain text.
                try:
                    parsed = json.loads(evaluation.strengths or "[]")
                    if isinstance(parsed, list):
                        strengths = [
                            str(item) for item in parsed
                            if str(item).strip()
                        ]
                    elif isinstance(parsed, str) and parsed.strip():
                        strengths = [parsed]
                except (json.JSONDecodeError, TypeError):
                    if evaluation.strengths.strip():
                        strengths = [evaluation.strengths.strip()]

                try:
                    parsed = json.loads(
                        evaluation.improvement_areas or "[]"
                    )
                    if isinstance(parsed, list):
                        improvements = [
                            str(item) for item in parsed
                            if str(item).strip()
                        ]
                    elif isinstance(parsed, str) and parsed.strip():
                        improvements = [parsed]
                except (json.JSONDecodeError, TypeError):
                    if evaluation.improvement_areas.strip():
                        improvements = [
                            evaluation.improvement_areas.strip()
                        ]

                feedback = evaluation.feedback
                sample_answer = evaluation.sample_answer

                overall_strengths.extend(strengths)
                overall_improvements.extend(improvements)

            report_questions.append(
                InterviewReportQuestion(
                    question_id=str(question.id),
                    question_order=question.question_order,
                    question=question.question_text,
                    skill=question.skill,
                    difficulty=question.difficulty,
                    answered=answer is not None,
                    candidate_answer=(
                        answer.answer_text if answer else None
                    ),
                    score=score,
                    strengths=strengths,
                    improvements=improvements,
                    feedback=feedback,
                    sample_answer=sample_answer,
                )
            )

        total_questions = len(questions)
        average_score = (
            round(sum(all_scores) / len(all_scores), 2)
            if all_scores
            else None
        )
        performance_percentage = (
            round(average_score * 10, 2)
            if average_score is not None
            else None
        )

        # Deduplicate feedback items while preserving their order.
        overall_strengths = list(dict.fromkeys(overall_strengths))
        overall_improvements = list(
            dict.fromkeys(overall_improvements)
        )

        return InterviewReportResponse(
            session_id=str(session.id),
            job_title=session.job_title,
            status=session.status,
            total_questions=total_questions,
            answered_questions=answered_count,
            average_score=average_score,
            performance_percentage=performance_percentage,
            completed=(
                total_questions > 0
                and answered_count == total_questions
            ),
            strengths=overall_strengths,
            improvement_areas=overall_improvements,
            questions=report_questions,
        )

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to generate the interview report.",
        ) from exc
    finally:
        db.close()
