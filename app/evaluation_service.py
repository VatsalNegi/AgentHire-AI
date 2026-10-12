
import json

from app.llm_service import chat_completion


def evaluate_answer(
    question: str,
    candidate_answer: str,
    expected_answer: str = "",
) -> dict:
    """Evaluate a candidate's interview answer using an LLM."""

    if not question or not question.strip():
        raise ValueError("Interview question cannot be empty.")

    if not candidate_answer or not candidate_answer.strip():
        raise ValueError("Candidate answer cannot be empty.")

    prompt = f"""
You are AgentHire AI, a technical interview evaluator.

Evaluate the candidate's answer based on technical correctness,
relevance, clarity, and the key concepts addressed.

Be constructive and fair. Do not penalize harmless wording differences.
Do not assume the candidate lacks knowledge simply because an answer
is concise. Do not invent facts about the candidate.

Return ONLY valid JSON, without Markdown fences, using this structure:

{{
  "score": 7,
  "strengths": [
    "Correctly explains the main concept"
  ],
  "improvements": [
    "Could provide a practical example"
  ],
  "feedback": "A concise overall assessment",
  "sample_answer": "A technically accurate example of a strong answer"
}}

Rules:
- score must be an integer from 0 to 10.
- strengths and improvements must be lists of strings.
- feedback and sample_answer must be strings.
- Base your assessment on the question and the supplied answer.
- Use the expected answer as guidance when one is provided.
- If the expected answer is missing, assess against standard technical
  knowledge relevant to the question.
- Return exactly one JSON object.

INTERVIEW QUESTION:
{question[:3000]}

EXPECTED ANSWER OR KEY CONCEPTS:
{expected_answer[:4000] if expected_answer.strip() else "Not provided"}

CANDIDATE ANSWER:
{candidate_answer[:5000]}
""".strip()

    response = chat_completion(prompt)

    try:
        result = json.loads(response)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "The AI returned invalid JSON. Please try again."
        ) from exc

    if not isinstance(result, dict):
        raise ValueError("The evaluation response must be a JSON object.")

    score = result.get("score")

    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 10:
        raise ValueError("The evaluation score must be an integer from 0 to 10.")

    for field in ("strengths", "improvements"):
        if not isinstance(result.get(field), list):
            raise ValueError(f"'{field}' must be a list.")

        if not all(
            isinstance(item, str) and item.strip()
            for item in result[field]
        ):
            raise ValueError(f"Every item in '{field}' must be non-empty text.")

    for field in ("feedback", "sample_answer"):
        if not isinstance(result.get(field), str) or not result[field].strip():
            raise ValueError(f"'{field}' must be non-empty text.")

    return result
