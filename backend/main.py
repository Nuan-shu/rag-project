from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from ingest import extract_text, chunk_text, store_chunks
from ask import search, ask_llm
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="金融RAG系统")


class Question(BaseModel):
    question: str


@app.post("/ingest")
async def ingest_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        return {"status": "error", "message": "只接受PDF文件"}

    pdf_bytes = await file.read()

    if len(pdf_bytes) > 50 * 1024 * 1024:
        return {"status": "error", "message": "PDF 过大,请压缩后上传(限制50MB)"}

    full_text, pages = extract_text(pdf_bytes)
    chunks = chunk_text(full_text)
    count = store_chunks(chunks, file.filename)

    return {
        "status": "ok",
        "file": file.filename,
        "pages": len(pages),
        "chunks": count,
    }


@app.post("/ask")
def ask_question(q: Question):
    sources = search(q.question)
    answer = ask_llm(q.question, sources)
    return {
        "answer": answer,
        "sources": sources,
    }
