
from app.llm_service import chat_completion


def main() -> None:
    print("Sending a test request to OpenRouter...")

    try:
        reply = chat_completion(
            "In one sentence, explain what an AI interview assistant does."
        )
        print("\nModel response:")
        print(reply)
        print("\nOpenRouter API test passed.")

    except (ValueError, RuntimeError) as exc:
        print(f"\nOpenRouter API test failed: {exc}")


if __name__ == "__main__":
    main()
