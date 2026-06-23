from db import model,collection 
from dotenv import load_dotenv
load_dotenv()  # 自动读取 .env

def search(query: str, top_k: int = 3) -> list[dict]:
    """向量化问题 → ChromaDB搜索 → 返回 top-k相关块"""
    query_embedding = model.encode([query]).tolist()

    results = collection.query(
        query_embeddings = query_embedding,
        n_results = top_k,
    )

    sources = []
    for i in range(len(results["ids"][0])):
        sources.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "score": float(results["distances"][0][i]),
        })

    return sources 

from openai import OpenAI
import os

client = OpenAI(
    api_key = os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

def ask_llm(question: str, sources: list[dict]) -> str:
    """拼 Prompt + 调用 Deepseek 生成答案"""
    # 拼接检索到的上下文
    context = "\n\n---\n\n".join([s["text"] for s in sources])
    prompt = f"""根据以下年报内容回答问题.如果信息不足,请如实说明.
    年报内容:
    {context}

    问题: {question}

    请用简洁的中文回答,并注明信息来源."""
        
    response = client.chat.completions.create(
        model = "deepseek-chat",
        messages = [
            {"role": "user", "content" : prompt},
        ],
        temperature= 0.3,
    )

    return response.choices[0].message.content

