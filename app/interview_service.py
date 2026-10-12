
import json

from app.llm_service import chat_completion


def generate_interview_questions(
    job_description: str,
    number_of_questions: int = 5,
) -> dict:
    """Generate structured interview questions from a job description."""

    if not job_description or not job_description.strip():
        raise ValueError("Job description cannot be empty.")

    if not 1 <= number_of_questions <= 5:
        raise ValueError("Generate between 1 and 5 questions per request.")

    prompt = f"""
Generate exactly {number_of_questions} interview questions for the job
description below.

Return ONLY valid JSON. Do not use Markdown or code fences.
Keep each question concise.

Required format:
{{
  "role": "Junior Python Developer",
  "questions": [
    {{
      "question": "What is a REST API?",
      "topic": "REST APIs",
      "difficulty": "Easy"
    }}
  ]
}}

Each question must contain:
- question: a clear interview question
- topic: the skill being assessed
- difficulty: exactly Easy, Medium, or Hard

Base questions on the job description. Do not invent requirements.

JOB DESCRIPTION:
{job_description[:6000]}
""".strip()

    response = chat_completion(prompt)

    try:
        result = json.loads(response)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "The AI returned incomplete or invalid JSON. Please try again."
        ) from exc

    if not isinstance(result, dict):
        raise ValueError("The AI response must be a JSON object.")

    questions = result.get("questions")

    if not isinstance(questions, list):
        raise ValueError("The AI response does not contain a valid questions list.")

    if len(questions) != number_of_questions:
        raise ValueError(
            f"Expected {number_of_questions} questions, "
            f"but received {len(questions)}."
        )

    for item in questions:
        if not isinstance(item, dict):
            raise ValueError("A question has an invalid format.")

        for field in ("question", "topic", "difficulty"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"A question is missing the '{field}' field.")

        if item["difficulty"] not in {"Easy", "Medium", "Hard"}:
            raise ValueError("A question has an invalid difficulty label.")

    return result
