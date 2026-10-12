
from app.evaluation_service import evaluate_answer


def main() -> None:
    question = "What is a REST API, and how would you create one using FastAPI?"

    candidate_answer = (
        "A REST API lets applications communicate over HTTP. "
        "In FastAPI, we can define endpoints using decorators like "
        "@app.get and @app.post. We can return JSON responses and "
        "use Pydantic models to validate request data."
    )

    expected_answer = (
        "A REST API exposes resources through HTTP methods such as GET, "
        "POST, PUT, and DELETE. FastAPI supports route decorators, "
        "request validation with Pydantic, and JSON responses."
    )

    print("Evaluating candidate answer...\n")

    try:
        result = evaluate_answer(
            question=question,
            candidate_answer=candidate_answer,
            expected_answer=expected_answer,
        )

        print(f"Score: {result['score']}/10")

        print("\nStrengths:")
        for item in result["strengths"]:
            print(f"- {item}")

        print("\nAreas for improvement:")
        for item in result["improvements"]:
            print(f"- {item}")

        print("\nOverall feedback:")
        print(result["feedback"])

        print("\nSample strong answer:")
        print(result["sample_answer"])

        print("\nAnswer evaluation test passed.")

    except (ValueError, RuntimeError) as exc:
        print(f"Test failed: {exc}")


if __name__ == "__main__":
    main()
