
from app.interview_graph import InterviewState, interview_graph


def main() -> None:
    initial_state: InterviewState = {
        "job_description": """
        Junior Python Developer

        Required skills:
        - Python fundamentals, functions, and classes.
        - REST APIs and FastAPI.
        - SQL and PostgreSQL.
        - Git, GitHub, and pytest.

        Responsibilities:
        - Build and maintain REST APIs.
        - Write unit tests and debug application issues.
        - Work with databases and collaborate with frontend developers.
        """,
        "candidate_answer": (
            "A REST API lets applications communicate over HTTP. "
            "GET retrieves data, POST creates data, PUT updates data, "
            "and DELETE removes data. FastAPI lets us define these "
            "endpoints using decorators such as @app.get and @app.post."
        ),
    }

    print("Running AgentHire AI interview graph...\n")

    try:
        result = interview_graph.invoke(initial_state)

        print(f"Generated question: {result['question']}")
        print(f"\nCandidate answer: {initial_state['candidate_answer']}")
        print(f"\nScore: {result['score']}/10")

        print("\nStrengths:")
        for item in result["strengths"]:
            print(f"- {item}")

        print("\nAreas for improvement:")
        for item in result["improvements"]:
            print(f"- {item}")

        print(f"\nFeedback: {result['feedback']}")
        print(f"\nSample answer:\n{result.get('sample_answer', 'No sample answer generated.')}")
        print(f"\nNext action: {result['next_action']}")
        print("\nLangGraph workflow test passed.")

    except Exception as exc:
        print(f"Workflow test failed: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()