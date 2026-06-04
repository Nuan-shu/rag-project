import os
from dotenv import load_dotenv
from openai import OpenAI
from db import model, collection

from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")  # 读取项目根目录的 .env

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)


def search(query: str, top_k: int = 3) -> list[dict]:
    """向量化问题 -> ChromaDB 搜索 -> 返回 top-k 相关块"""
    query_embedding = model.encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
    )

    sources = []
    for i in range(len(results["ids"][0])):
        sources.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "score": float(results["distances"][0][i]),
        })

    return sources


def ask_llm(question: str, sources: list[dict]) -> str:
    """拼 Prompt + 调 DeepSeek 生成答案"""
    context = "\n\n---\n\n".join([s["text"] for s in sources])

    prompt = f"""根据以下年报内容回答问题。如果信息不足，请如实说明。

年报内容：
{context}

问题：{question}

请用简洁的中文回答，并注明信息来源。"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    return response.choices[0].message.content
