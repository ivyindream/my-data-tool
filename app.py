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


# ============ 侧边栏导航 ============
def render_sidebar():
    """渲染侧边栏"""
    st.sidebar.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <h2>📊 数据处理工具</h2>
        <p style="color: #666; font-size: 14px;">让数据处理更简单</p>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("---")

    # 获取所有模块
    modules = get_module_list()

    # 模块选择（默认选择第一个）
    module_keys = list(modules.keys())
    module_names = [f"{modules[k]['icon']} {modules[k]['name']}" for k in module_keys]

    # 如果没有选择，默认为第一个
    if 'selected_module' not in st.session_state:
        st.session_state.selected_module = module_keys[0] if module_keys else None

    # 渲染模块列表
    selected = st.sidebar.radio(
        "选择功能模块",
        module_keys,
        format_func=lambda k: f"{modules[k]['icon']} {modules[k]['name']}",
        index=module_keys.index(st.session_state.selected_module) if st.session_state.selected_module in module_keys else 0
    )

    st.session_state.selected_module = selected

    st.sidebar.markdown("---")

    # 管理员模式提示
    st.sidebar.markdown("""
    <div style="padding: 10px; background: #E3F2FD; border-radius: 8px; font-size: 12px;">
        <b>💡 隐私说明</b><br>
        普通模式下，所有数据仅在内存中处理，关闭网页后自动删除。<br>
        如需管理员功能，请访问 <code>?admin=true</code>
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
