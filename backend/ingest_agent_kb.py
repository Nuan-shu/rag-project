"""
ingest_agent_kb.py — 将 agent 工程知识文档索引到 ChromaDB
==========================================================
读取 data/agent-kb/ 下的所有 .md 文件，
分块 → 向量化 → 存入 ChromaDB 新 collection "agent_engineering"
"""

import os
import re
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# ── 配置 ─────────────────────────────────────────────────
os.environ["HF_HUB_OFFLINE"] = "1"         # 离线加载，依赖已缓存的 BGE 模型

KB_DIR = Path(__file__).resolve().parent.parent / "data" / "agent-kb"
CHROMA_PATH = Path(__file__).resolve().parent / "chroma_data"
CHUNK_SIZE = 500        # 每块最大字符数
CHUNK_OVERLAP = 100     # 块间重叠字符数

# ── 1. 加载模型和数据库 ──────────────────────────────────
print("Loading embedding model...")
model = SentenceTransformer("BAAI/bge-small-zh-v1.5", local_files_only=True)

print("Connecting to ChromaDB...")
client = chromadb.PersistentClient(path=str(CHROMA_PATH))

# 新建或获取 collection
collection = client.get_or_create_collection(
    name="agent_engineering",
    metadata={"description": "AI Agent 工程知识库 — 架构分析、技术选型、最佳实践"}
)

# ── 2. 分块函数（按段落边界智能切分） ────────────────────
def chunk_markdown(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """
    按 Markdown 自然边界（段落/标题）切分文本。
    优先在 ## 标题或空行处断开，避免在句子中间截断。
    """
    # 先按双换行（段落边界）拆分
    sections = re.split(r'\n\n+', text)

    chunks = []
    current = ""
    for section in sections:
        section = section.strip()
        if not section:
            continue

        # 如果当前块 + 新段落不超限，合并
        if len(current) + len(section) + 2 <= chunk_size:
            current = (current + "\n\n" + section) if current else section
        else:
            # 当前块保存
            if current:
                chunks.append(current)
            # 新段落开始（可能超长，需硬切）
            if len(section) > chunk_size:
                # 硬切长段落
                for i in range(0, len(section), chunk_size - overlap):
                    sub = section[i:i + chunk_size]
                    if sub.strip():
                        chunks.append(sub.strip())
                current = ""
            else:
                current = section

    if current.strip():
        chunks.append(current.strip())

    return chunks


# ── 3. 主流程：遍历文件 → 分块 → 入库 ───────────────────
def ingest_all():
    md_files = sorted(KB_DIR.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {KB_DIR}")
        return

    total_chunks = 0
    for md_file in md_files:
        print(f"\nProcessing: {md_file.name}")

        with open(md_file, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_markdown(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        print(f"  Split into {len(chunks)} chunks")

        if not chunks:
            continue

        # 向量化
        embeddings = model.encode(chunks).tolist()

        # 生成 ID 和元数据
        ids = [f"{md_file.stem}_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "source": md_file.name,
                "title": md_file.stem,
                "chunk_id": i,
                "total_chunks": len(chunks),
            }
            for i in range(len(chunks))
        ]

        # 入库（如果已存在同 source 的数据先删除）
        existing = collection.get(where={"source": md_file.name})
        if existing["ids"]:
            print(f"  Removing {len(existing['ids'])} existing chunks...")
            collection.delete(ids=existing["ids"])

        collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        total_chunks += len(chunks)
        print(f"  ✓ Stored {len(chunks)} chunks")

    print(f"\n{'='*50}")
    print(f"Ingestion complete. Total: {total_chunks} chunks in collection 'agent_engineering'")
    print(f"Collection size: {collection.count()} documents")


# ── 4. 快速测试搜索 ────────────────────────────────────
def test_search():
    test_queries = [
        "AI工程开发需要学Java吗",
        "Agent的权限系统应该怎么设计",
        "loop_v3和Claude Code的差距有哪些",
    ]

    print(f"\n{'='*50}")
    print("Search Tests:")
    print("=" * 50)

    for query in test_queries:
        print(f"\n🔍 Query: {query}")
        q_embed = model.encode([query]).tolist()
        results = collection.query(
            query_embeddings=q_embed,
            n_results=2,
            include=["documents", "metadatas", "distances"],
        )

        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )):
            relevance = max(0, 1.0 - dist)
            preview = doc[:120].replace("\n", " ")
            print(f"  [{i+1}] {meta['source']} (相关度: {relevance:.2f}) — {preview}...")


if __name__ == "__main__":
    ingest_all()
    test_search()
