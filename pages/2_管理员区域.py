"""
管理员区域页面
"""

import streamlit as st
import hashlib


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def get_admin_hash() -> str:
    try:
        return st.secrets["ADMIN_PASSWORD_HASH"]
    except Exception:
        return hashlib.sha256("admin123".encode()).hexdigest()


def page_admin():
    st.header("🔐 管理员区域")

    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False

    if not st.session_state.admin_logged_in:
        st.markdown("请输入管理员密码以继续。")
        with st.form("admin_login"):
            pw = st.text_input("密码", type="password")
            submitted = st.form_submit_button("登录")
            if submitted:
                if hash_password(pw) == get_admin_hash():
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else:
                    st.error("密码错误，请重试。")
        return

    # 已登录
    st.success("✅ 已以管理员身份登录")
    if st.button("退出登录"):
        st.session_state.admin_logged_in = False
        st.rerun()

    st.divider()
    st.subheader("管理员功能")
    st.info(
        "管理员功能区域。您可以在此查看使用统计、上传持久化映射表，"
        "或通过 Streamlit Cloud 的 Secrets 管理配置。\n\n"
        "**提示**：如需更改密码，请在 Streamlit Cloud 的 App Settings → Secrets 中修改 "
        "`ADMIN_PASSWORD_HASH` 的值（使用 SHA-256 哈希）。"
    )

    st.subheader("上传持久化映射表")
    st.markdown(
        "普通用户每次需要手动上传映射表。作为管理员，您可以在此上传默认映射表，"
        "存储在 session 中供本次会话使用。"
    )
    admin_mapping = st.file_uploader(
        "上传默认映射表（本次会话有效）",
        type=["xlsx", "xls"],
        key="admin_mapping"
    )
    if admin_mapping:
        st.session_state["default_mapping"] = admin_mapping.read()
        st.session_state["default_mapping_name"] = admin_mapping.name
        st.success(f"✅ 默认映射表 `{admin_mapping.name}` 已保存到本次会话")
