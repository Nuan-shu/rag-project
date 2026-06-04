# 金融年报 RAG 系统

基于 RAG（检索增强生成）的 A 股年报智能问答系统。上传 PDF 年报，即可用自然语言提问，系统从年报原文中检索相关内容，结合大模型生成准确答案。

## 快速开始

```bash
# 1. 安装依赖
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt

# 2. 配置 API 密钥
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 启动后端
cd backend
python3 -m uvicorn main:app --port 8000 --reload

# 4. 启动前端（新窗口）
cd frontend
python3 -m streamlit run app.py --server.port 8501
```

访问 http://localhost:8501

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /ingest | 上传 PDF 年报，提取文字 → 分块 → 向量化 → 入库 |
| POST | /ask | 自然语言提问，检索相关段落 → LLM 生成答案 |

## RAG 技术栈

### Embedding 模型

- **BAAI/bge-small-zh-v1.5** — 智源研究院开源中文 Embedding 模型
- 维度：512 维
- 下载源：HuggingFace（本地缓存，离线加载）

### 文本切片

- **滑动窗口分块**（Sliding Window Chunking）
- 块大小：500 字符
- 重叠：100 字符
- 目的：防止关键信息被切断在相邻块之间

### 向量数据库

- **ChromaDB 1.5**（持久化模式）
- 集合名：`annual_reports`
- 元数据：`source`（文件名）、`chunk_id`（块序号）

### 大语言模型

- **DeepSeek Chat**（openai 兼容 API）
- 温度：0.3（低温度减少幻觉）
- 提示策略：检索内容 + 用户问题，要求基于原文回答

### PDF 解析

- **PyMuPDF 1.26**（fitz）

### 后端框架

- **FastAPI** + **Pydantic** 数据校验
- **Uvicorn** ASGI 服务器

### 前端

- **Streamlit** 交互式界面
- 功能：PDF 上传 / 自然语言提问 / 答案展示 / 来源引用

## 评测（20 题）

覆盖三家公司（贵州茅台 / 比亚迪 / 宁德时代），维度：

- 财务（营收、利润、毛利率）
- 业务（销量、研发、海外）
- 风险（经营、行业、技术）

已知局限：计算型问题（如毛利率变化）需要 Agent 计算层，当前 chunk-and-retrieve 架构无法直接回答。

## 项目结构

```
rag-project/
├── backend/
│   ├── main.py      # FastAPI 入口（/ingest, /ask）
│   ├── ingest.py    # PDF 提取 + 分块 + 入库
│   ├── ask.py       # 语义搜索 + LLM 生成
│   └── db.py        # ChromaDB 连接 + Embedding 模型
├── frontend/
│   └── app.py       # Streamlit 界面
├── data/
│   └── pdfs/        # 年报 PDF 源文件
├── chroma_data/     # ChromaDB 持久化数据
├── requirements.txt
├── .env.example
└── .gitignore
```

## 版本

v0.1.0 — 完整 RAG 全链路（PDF 提取 → 分块 → 向量检索 → LLM 生成），Streamlit 交互界面，20 题评测。
