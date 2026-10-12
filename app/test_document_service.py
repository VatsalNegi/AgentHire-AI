
from app.document_service import split_text


def _sample_chunks():
    sample_text = (
        "AgentHire AI helps recruiters evaluate candidates. "
        * 100
    )
    return split_text(
        sample_text,
        chunk_size=200,
        overlap=30,
    )


def test_split_text_creates_bounded_nonempty_chunks():
    chunks = _sample_chunks()

    assert len(chunks) > 1
    assert all(chunks)
    assert all(len(chunk) <= 200 for chunk in chunks)


def main():
    test_split_text_creates_bounded_nonempty_chunks()
    chunks = _sample_chunks()

    print("Text chunking test passed.")
    print(f"Total chunks: {len(chunks)}")
    print(f"First chunk length: {len(chunks[0])}")
    print(f"Second chunk length: {len(chunks[1])}")


if __name__ == "__main__":
    main()
