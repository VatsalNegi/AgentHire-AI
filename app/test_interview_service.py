
from app.interview_service import generate_interview_questions


def main() -> None:
    job_description = """
    Junior Python Developer

    Responsibilities:
    - Develop REST APIs using Python and FastAPI.
    - Work with PostgreSQL and SQLAlchemy.
    - Write unit tests and debug application issues.
    - Collaborate with frontend developers.

    Required skills:
    - Python fundamentals, functions, and classes.
    - REST APIs and HTTP status codes.
    - SQL and relational databases.
    - Git, GitHub, and pytest.
    """

    print("Generating interview questions...\n")

    try:
        result = generate_interview_questions(
            job_description=job_description,
            number_of_questions=5,
        )

        print(f"Role: {result.get('role', 'Not specified')}\n")

        for index, item in enumerate(result["questions"], start=1):
            print(f"{index}. {item['question']}")
            print(f"   Topic: {item['topic']}")
            print(f"   Difficulty: {item['difficulty']}\n")

        print("Interview question generation test passed.")

    except (ValueError, RuntimeError) as exc:
        print(f"Test failed: {exc}")


if __name__ == "__main__":
    main()
