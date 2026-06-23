import chromadb
from sentence_transformers import SentenceTransformer
import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "1"

model = SentenceTransformer(
    "BAAI/bge-small-zh-v1.5",
    local_files_only=True,
)

client = chromadb.PersistentClient(path="./chroma_data")
collection = client.get_or_create_collection(
    name="annual_reports",
    metadata={"description": "A股年报RAG知识库"},
)
