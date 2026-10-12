import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main as main
from app.database import Base
from app.main import (
    InterviewSessionRequest,
    SubmitInterviewAnswerRequest,
    create_interview_session,
    submit_interview_answer,
)
from app.models import InterviewSession, Question, UserProfile


class InterviewSessionIdTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(
            engine,
            tables=[
                Base.metadata.tables[table_name]
                for table_name in (
                    "interview_sessions",
                    "questions",
                    "candidate_answers",
                    "evaluations",
                )
            ],
        )
        self.session_factory = sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )

    def test_created_question_ids_are_usable_for_answer_submission(self):
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
        evaluation_result = {
            "score": 8,
            "strengths": ["Clear explanation"],
            "improvements": ["Add an example"],
            "feedback": "Good answer",
            "sample_answer": "A sample answer",
            "next_action": "Continue",
        }
        authenticated_user = UserProfile(id=uuid4())

        with (
            patch.object(main, "SessionLocal", self.session_factory),
            patch.object(
                main,
                "generate_interview_questions",
                return_value=generated_questions,
            ),
            patch.object(
                main.evaluation_graph,
                "invoke",
                return_value=evaluation_result,
            ),
        ):
            session_response = create_interview_session(
                InterviewSessionRequest(
                    job_description="Software Engineer",
                    number_of_questions=5,
                ),
                current_user=authenticated_user,
            )

            self.assertEqual(session_response.total_questions, 5)
            session_id = UUID(session_response.session_id)
            question_ids = [
                UUID(item.question_id) for item in session_response.questions
            ]
            self.assertEqual(len(set(question_ids)), 5)

            with self.session_factory() as db:
                stored_session = db.get(InterviewSession, session_id)
                stored_questions = (
                    db.query(Question)
                    .filter(Question.session_id == session_id)
                    .order_by(Question.question_order)
                    .all()
                )
            self.assertIsNotNone(stored_session)
            self.assertEqual(stored_session.owner_id, authenticated_user.id)
            self.assertEqual(
                [question.id for question in stored_questions],
                question_ids,
            )

            answer_response = submit_interview_answer(
                session_id=str(session_id),
                question_id=str(question_ids[0]),
                request=SubmitInterviewAnswerRequest(
                    candidate_answer="A testable answer"
                ),
                current_user=UserProfile(id=stored_session.owner_id),
            )
            self.assertEqual(answer_response["session_id"], str(session_id))
            self.assertEqual(
                answer_response["question_id"],
                str(question_ids[0]),
            )


if __name__ == "__main__":
    unittest.main()
