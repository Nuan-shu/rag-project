from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from ingest import extract_text, chunk_text, store_chunks
from ask import search, ask_llm


app = FastAPI(title="金融RAG系统")


class Question(BaseModel):
    question: str
    top_k: int = 3


@app.post("/ingest")
async def ingest_pdf(file: UploadFile = File(...)):
    # 1. 校验：只接受 PDF
    if not file.filename.endswith(".pdf"):
        return {"status": "error", "message": "只接受 PDF 文件"}

    # 2. 读取文件字节
    pdf_bytes = await file.read()

    # 3. 大小限制：50MB
    if len(pdf_bytes) > 50 * 1024 * 1024:
        return {"status": "error", "message": "PDF 过大，请压缩后上传（限制 50MB）"}

    # 4. 提取文字
    full_text, pages = extract_text(pdf_bytes)

    # 5. 分块
    chunks = chunk_text(full_text)

    # 6. 入库
    count = store_chunks(chunks, file.filename)

    return {
        "status": "ok",
        "filename": file.filename,
        "pages": len(pages),
        "chunks": count,
    }


@app.post("/ask")
async def ask_question(q: Question):
    # 1. 语义搜索
    sources = search(q.question, q.top_k)

    if not sources:
        return {"answer": "未找到相关信息", "sources": []}

    # 2. LLM 生成答案
    answer = ask_llm(q.question, sources)

    return {
        "answer": answer,
        "sources": [
            {"text": s["text"][:200], "score": s["score"]}
            for s in sources
        ],
    }
