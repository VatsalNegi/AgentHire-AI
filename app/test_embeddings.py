
from app.embedding_service import embed_text


def main():
    sample_text = (
        "A Python developer should understand APIs, "
        "databases, testing, and problem solving."
    )

    vector = embed_text(sample_text)

    print("Embedding generated successfully.")
    print(f"Vector dimensions: {len(vector)}")
    print(f"First five values: {vector[:5]}")


if __name__ == "__main__":
    main()
