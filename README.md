# 金融年报 RAG 系统

基于 RAG（检索增强生成）的 A 股年报智能问答系统。上传 PDF 年报，用自然语言提问，系统从年报原文中检索相关内容，结合大模型生成准确答案。

[![Version](https://img.shields.io/badge/version-0.1.0-blue)](#)
[![Python](https://img.shields.io/badge/python-3.12-green)](#)
[![RAG](https://img.shields.io/badge/stack-RAG-orange)](#)

## 架构

```
用户问题
    │
    ▼
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Streamlit   │────▶│    FastAPI      │────▶│   DeepSeek   │
│  前端界面    │     │  /ask  /ingest  │     │  Chat (LLM)  │
└──────────────┘     └───────┬─────────┘     └──────▲───────┘
                             │                       │
                    ┌────────▼─────────┐     ┌───────┴───────┐
                    │  向量检索         │     │  Prompt 拼接   │
                    │  bge-small-zh    │     │  上下文 + 问题 │
                    └────────┬─────────┘     └───────────────┘
                             │
                    ┌────────▼─────────┐
                    │   ChromaDB       │
                    │   annual_reports │
                    │   1,683 块        │
                    └──────────────────┘

PDF 年报 → PyMuPDF 提取文字 → 滑动窗口分块(500字/100重叠) → 向量化 → ChromaDB
```

## 快速开始

```bash
# 1. 安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY=sk-xxx

# 3. 启动后端
cd backend
python -m uvicorn main:app --port 8000 --reload

# 4. 启动前端（新终端）
cd frontend
python -m streamlit run app.py --server.port 8501
```

访问 http://localhost:8501

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/ingest` | 上传 PDF 年报 → 提取文字 → 分块 → 向量化 → 入库 |
| POST | `/ask` | 自然语言提问，检索相关段落 → LLM 生成答案 |

### 示例

```bash
# 上传年报
curl -X POST http://localhost:8000/ingest \
  -F "file=@贵州茅台_2025年报.pdf"

# 返回：{"status":"ok","file":"...","pages":186,"chunks":635}

# 提问
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"贵州茅台2025年营收和净利润是多少？"}'

# 返回：{"answer":"...","sources":[{"id":"...","text":"...","score":0.82}]}
```

## 知识库

| 年报 | 页数 | 块数 |
|------|------|------|
| 贵州茅台 2025 | 186 | ~635 |
| 比亚迪 2025 | 210 | ~582 |
| 宁德时代 2025 | 168 | ~466 |
| **合计** | **564** | **1,683** |

知识库存储在 `backend/chroma_data/`（ChromaDB 持久化模式），首次运行无需重新入库。

## RAG 全链路

| 阶段 | 技术 | 说明 |
|------|------|------|
| PDF 解析 | **PyMuPDF** (fitz) | 逐页提取文字，支持流式读取（无需落盘） |
| 文本分块 | **滑动窗口** | 500 字符/块，100 字符重叠，防止关键信息被切断 |
| 向量化 | **BAAI/bge-small-zh-v1.5** | 512 维中文 Embedding，HuggingFace 离线加载 |
| 向量检索 | **ChromaDB** | 持久化模式，cosine 相似度，top-3 返回 |
| 生成 | **DeepSeek Chat** | 温度 0.3，基于检索内容回答，信息不足时如实说明 |

## 评测

20 题覆盖 3 家公司（茅台/比亚迪/宁德时代），3 个维度：

| 维度 | 题数 | 说明 |
|------|------|------|
| 财务 | 8 | 营收、利润、毛利率、现金流 |
| 业务 | 7 | 销量、研发投入、海外业务 |
| 风险 | 5 | 经营风险、行业风险、技术风险 |

**已知局限**：计算型问题（如「毛利率变化了几个百分点」）需要额外计算层——当前 chunk-and-retrieve 架构只能检索原文数据，无法执行数学运算。这是 RAG 系统的天然边界，需要 Agent + 工具调用补全。

## 项目结构

```
rag-project/
├── backend/
│   ├── main.py           # FastAPI 入口（/ingest, /ask）
│   ├── ingest.py          # PDF 提取 + 滑动窗口分块 + 向量化入库
│   ├── ask.py             # 语义检索 + LLM 生成
│   ├── db.py              # ChromaDB 连接 + Embedding 模型加载
│   └── chroma_data/       # 向量数据库持久化（.gitignore）
├── frontend/
│   └── app.py             # Streamlit 交互界面
├── data/
│   └── pdfs/              # 年报 PDF 源文件
├── requirements.txt
├── .env.example
└── .gitignore
```

## 版本历史

| 版本 | 日期 | 内容 |
|------|------|------|
| **v0.1.0** | 06-05 | 完整 RAG 全链路（PDF→分块→检索→LLM），Streamlit 界面，3 家公司 1,683 块入库，20 题评测 |

## 关联项目

- [ns-agent](https://github.com/Nuan-shu/ns-agent) — 统一 AI Agent 框架（工具注册表 + 金融工具集 + 企业级特性）
- [agent-framework](https://github.com/Nuan-shu/agent-framework) — Agent Loop 原型（v1→v2→v3）
