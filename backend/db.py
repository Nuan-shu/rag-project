import chromadb
from sentence_transformers import SentenceTransformer
import os

# 强制 HuggingFace 离线模式（模型已在本地缓存）
os.environ["HF_HUB_OFFLINE"] = "1"

# 1. 加载 embedding 模型（只加载一次，全局复用）
model = SentenceTransformer("BAAI/bge-small-zh-v1.5", local_files_only=True)

# 2. ChromaDB 客户端 + collection
client = chromadb.PersistentClient(path="./chroma_data")
collection = client.get_or_create_collection(
    name="annual_reports",
    metadata={"description": "A股年报RAG知识库"}
)
