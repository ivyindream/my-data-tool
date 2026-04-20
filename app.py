"""
数据处理工具 - Streamlit Web 应用
模块化架构，支持扩展新功能
"""
import streamlit as st
import importlib

from modules import get_module_list, get_module_config
from utils.style import config_page, apply_custom_css


# ============ 页面初始化 ============
config_page()
apply_custom_css()


# ============ 管理员认证 ============
def init_admin_state():
    """初始化管理员状态"""
    if 'admin_logged_in' not in st.session_state:
        st.session_state.admin_logged_in = False
    if 'login_error' not in st.session_state:
        st.session_state.login_error = False


def render_login_form():
    """渲染登录表单"""
    st.sidebar.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <h2>🔐 管理员登录</h2>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("---")

    with st.sidebar.form("login_form", clear_on_submit=True):
        password = st.text_input("输入管理员密码", type="password")
        submitted = st.form_submit_button("登录")

        if submitted:
            # 获取密码（优先使用 Secrets，兼容本地开发）
            try:
                admin_password = st.secrets["ADMIN_PASSWORD"]
            except:
                admin_password = "wme"  # 本地开发默认密码

            if password == admin_password:
                st.session_state.admin_logged_in = True
                st.session_state.login_error = False
                st.rerun()
            else:
                st.session_state.login_error = True
                st.error("密码错误")

    return not st.session_state.admin_logged_in


def render_logged_in_header():
    """渲染已登录状态的头部"""
    st.sidebar.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <h2>📊 数据处理工具</h2>
        <p style="color: #666; font-size: 14px;">管理员模式</p>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("""
    <div style="padding: 8px; background: #E8F5E9; border-radius: 8px; text-align: center; margin: 10px 0;">
        <span style="font-size: 24px;">🔓</span><br>
        <b style="color: #2E7D32;">已登录</b>
    </div>
    """, unsafe_allow_html=True)

    if st.sidebar.button("退出登录", key="logout_btn"):
        st.session_state.admin_logged_in = False
        st.rerun()


# ============ 侧边栏导航 ============
def render_sidebar():
    """渲染侧边栏"""
    init_admin_state()

    # 根据登录状态渲染不同的侧边栏
    if not st.session_state.admin_logged_in:
        # 未登录：显示登录表单
        if render_login_form():
            st.sidebar.markdown("---")
            st.sidebar.info("💡 请输入管理员密码登录")
            return None
    else:
        # 已登录：显示主界面
        render_logged_in_header()
        st.sidebar.markdown("---")

    # 获取所有模块
    modules = get_module_list()

    # 根据权限过滤模块
    available_modules = []
    for key, config in modules.items():
        if config.get('admin_only', False):
            # 管理员专属模块：需要登录
            if st.session_state.admin_logged_in:
                available_modules.append(key)
        else:
            # 公开模块
            available_modules.append(key)

    if not available_modules:
        st.sidebar.warning("没有可用的模块")
        return None

    # 模块选择
    if 'selected_module' not in st.session_state or st.session_state.selected_module not in available_modules:
        st.session_state.selected_module = available_modules[0]

    selected = st.sidebar.radio(
        "选择功能模块",
        available_modules,
        format_func=lambda k: f"{modules[k]['icon']} {modules[k]['name']}",
        index=available_modules.index(st.session_state.selected_module)
    )

    st.session_state.selected_module = selected

    st.sidebar.markdown("---")

    # 隐私说明
    st.sidebar.markdown("""
    <div style="padding: 10px; background: #E3F2FD; border-radius: 8px; font-size: 12px;">
        <b>💡 隐私说明</b><br>
        所有数据仅在内存中处理，关闭网页后自动删除。
    </div>
    """, unsafe_allow_html=True)

    return selected


# ============ 主函数 ============
def main():
    """主函数"""
    # 渲染侧边栏
    selected_module = render_sidebar()

    # 加载并渲染选中模块
    if selected_module:
        config = get_module_config(selected_module)

        if config:
            try:
                # 动态导入模块
                module = importlib.import_module(config['module'])
                render_func = getattr(module, config['function'])

                # 调用渲染函数
                render_func()

            except Exception as e:
                st.error(f"加载模块失败: {e}")
                import traceback
                st.code(traceback.format_exc())
        else:
            st.error("模块配置不存在")


# ============ 入口 ============
if __name__ == "__main__":
    main()
