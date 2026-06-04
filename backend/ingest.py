import fitz  # pymupdf 的导入名是 fitz


def extract_text(pdf_bytes: bytes) -> tuple[str, list[str]]:
    """从 PDF 字节中提取文字，返回 (全文, 分页列表)"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []

    for page in doc:
        text = page.get_text()
        pages.append(text)

    doc.close()
    full_text = "\n".join(pages)
    return full_text, pages


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """滑动窗口分块"""
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap  # 下一块的起点，往前退 overlap

    return chunks


from db import model, collection


def store_chunks(chunks: list[str], filename: str) -> int:
    """向量化所有文本块并存入 ChromaDB"""
    embeddings = model.encode(chunks).tolist()

    ids = [f"{filename}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": filename, "chunk_id": i} for i in range(len(chunks))]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return len(chunks)
