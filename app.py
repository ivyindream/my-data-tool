"""
数据处理工作台 - 首页
基于 Streamlit 构建，支持多页面扩展
"""

import streamlit as st

APP_TITLE = "数据处理工作台"


def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ---------- 首页内容 ----------
    st.title(f"📊 {APP_TITLE}")
    st.markdown("---")

    st.markdown("""
    ### 欢迎使用数据处理工作台

    请从左侧 **页面列表** 选择需要使用的工具。

    ---

    #### 当前可用模块
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.info("📊 **采购数据合并工具**")
        st.markdown(
            "将多个省份的采购数据文件，按照统一的列名映射表，"
            "自动合并为一张汇总表。支持 ZIP 上传、高级筛选、数据质量报告。"
        )

    with col2:
        st.info("🔐 **管理员区域**")
        st.markdown(
            "受密码保护的管理员功能区，可上传持久化映射表，"
            "修改密码等配置。"
        )

    st.markdown("---")

    st.markdown("""
    #### 💡 提示

    - 数据仅在当前会话中存在，**关闭页面后自动清除**
    - 后续可在此平台上扩展更多工作模块
    - 如需调整页面样式，可本地运行预览后再部署
    """)

    with st.expander("🖥️ 如何本地预览（边改边看效果）"):
        st.markdown("""
        如果你想调整页面视觉样式，建议先在**本地运行预览**：

        1. 下载所有文件到本地同一文件夹
        2. 安装依赖：`pip install streamlit pandas openpyxl xlrd`
        3. 进入该文件夹，执行：`streamlit run app.py`
        4. 浏览器会自动打开 `http://localhost:8501`
        5. **每次修改代码并保存，浏览器会自动刷新**，立即看到效果

        完全满意后，再将文件上传到 GitHub 部署到云端。
        """)

    st.markdown("---")
    st.caption("Powered by Streamlit")


if __name__ == "__main__":
    main()
