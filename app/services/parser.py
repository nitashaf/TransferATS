import io

import PyPDF2
import docx
from fastapi import UploadFile


async def parse_resume(file: UploadFile) -> str:
    content = await file.read()
    name = file.filename.lower()

    if name.endswith(".pdf"):
        return _parse_pdf(content)
    elif name.endswith(".docx"):
        return _parse_docx(content)
    elif name.endswith(".txt"):
        return content.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: {file.filename}. Use PDF, DOCX, or TXT.")


def _parse_pdf(content: bytes) -> str:
    reader = PyPDF2.PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _parse_docx(content: bytes) -> str:
    doc = docx.Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs).strip()
