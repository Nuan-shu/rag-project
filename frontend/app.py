import streamlit as st
import requests


API_BASE = "http://localhost:8000"

st.set_page_config(page_title="金融年报RAG助手")
st.title("金融年报 RAG 助手")

st.header("上传年报")

uploaded_file = st.file_uploader(
    "选择 PDF 年报文件",
    type=["pdf"],
    accept_multiple_files=False,
)

if uploaded_file is not None:
    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
    with st.spinner(f"正在处理 {uploaded_file.name}..."):
        resp = requests.post(f"{API_BASE}/ingest", files=files)
    result = resp.json()
    if result["status"] == "ok":
        st.success(f"入库成功！{result['pages']} 页 -> {result['chunks']} 个文本块")
    else:
        st.error(result["message"])

st.divider()
st.header("智能问答")

question = st.text_input("请输入你的问题")
if st.button("提问") and question:
    with st.spinner("正在检索..."):
        resp = requests.post(
            f"{API_BASE}/ask",
            json={"question": question},
        )
    result = resp.json()

    st.subheader("答案")
    st.write(result["answer"])

    st.subheader("参考来源")
    for i, src in enumerate(result["sources"], 1):
        with st.expander(f"来源 {i}（相似度 {src['score']:.2f}）"):
            st.text(src["text"])
