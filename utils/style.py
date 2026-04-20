"""
页面样式配置
"""
import streamlit as st


# 页面配置
def config_page():
    """配置页面基本设置"""
    st.set_page_config(
        page_title="数据处理工具",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )


# 自定义CSS样式
CUSTOM_CSS = """
<style>
    /* 主色调 */
    :root {
        --primary: #1E88E5;
        --primary-dark: #1565C0;
        --bg-light: #F5F7FA;
        --text-dark: #212121;
    }

    /* 上传区域样式 */
    .upload-box {
        border: 2px dashed var(--primary);
        border-radius: 10px;
        padding: 30px;
        text-align: center;
        background: var(--bg-light);
        transition: all 0.3s ease;
    }

    .upload-box:hover {
        border-color: var(--primary-dark);
        background: white;
        box-shadow: 0 4px 12px rgba(30, 136, 229, 0.2);
    }

    /* 步骤指示器 */
    .step-indicator {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 20px 0;
    }

    .step-number {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: var(--primary);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
    }

    .step-text {
        font-size: 16px;
        color: var(--text-dark);
    }

    /* 卡片样式 */
    .card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        margin: 10px 0;
    }

    /* 成功提示 */
    .success-box {
        padding: 15px;
        border-radius: 8px;
        background: #E8F5E9;
        border-left: 4px solid #4CAF50;
        margin: 10px 0;
    }

    /* 警告提示 */
    .warning-box {
        padding: 15px;
        border-radius: 8px;
        background: #FFF3E0;
        border-left: 4px solid #FF9800;
        margin: 10px 0;
    }

    /* 隐藏 Streamlit 默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
"""


def apply_custom_css():
    """应用自定义样式"""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def card_container():
    """创建卡片容器"""
    return st.container()
