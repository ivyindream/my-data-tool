"""
模块注册系统
所有模块在这里注册，主程序自动加载
"""

# 模块注册表 - 添加新模块时在这里注册
MODULES = {
    'data_merger': {
        'name': '数据合并',
        'icon': '📋',
        'module': 'modules.data_merger',
        'function': 'render'
    },
    # 【新增模块示例】
    # 'new_module': {
    #     'name': '新模块名称',
    #     'icon': '🔧',
    #     'module': 'modules.new_module',
    #     'function': 'render'
    # },
}


def get_module_list():
    """获取所有已注册的模块列表"""
    return MODULES


def get_module_config(module_key):
    """获取指定模块的配置"""
    return MODULES.get(module_key)


def register_module(key, name, icon, module_path, function_name='render'):
    """
    动态注册新模块

    Args:
        key: 模块标识符
        name: 显示名称
        icon: 图标 emoji
        module_path: 模块路径 (如 'modules.xxx')
        function_name: 渲染函数名
    """
    MODULES[key] = {
        'name': name,
        'icon': icon,
        'module': module_path,
        'function': function_name
    }
