
from pypdf import PdfReader


def extract_text_from_pdf(file_path: str) -> str:
    """Extract readable text from a PDF file."""
    reader = PdfReader(file_path)

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    extracted_text = "\n\n".join(pages).strip()

    if not extracted_text:
        raise ValueError(
            "No readable text was found in the PDF. "
            "Scanned PDFs may require OCR."
        )

    return extracted_text


def extract_text_from_txt(file_path: str) -> str:
    """Read a UTF-8 text file."""
    with open(file_path, "r", encoding="utf-8-sig") as file:
        text = file.read().strip()

    if not text:
        raise ValueError("The text file is empty.")

    return text


def split_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[str]:
    """Split text into overlapping character-based chunks."""
    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be non-negative and smaller than chunk_size."
        )

    text = text.strip()
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == len(text):
            break

        start = end - overlap

    return chunks
