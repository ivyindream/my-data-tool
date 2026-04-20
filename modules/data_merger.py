"""
数据合并工作流模块
将多个 Excel 文件按映射表统一列名后合并
"""
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.file_handler import bytes_to_df, df_to_bytes, excel_to_bytes_multi_sheet


def render():
    """渲染数据合并模块页面"""
    st.title("📋 数据合并工作流")
    st.markdown("---")

    # 步骤说明
    st.markdown("""
    ### 使用步骤
    1. **上传映射表** - 上传列标题名称对照表（Excel文件）
    2. **上传数据文件** - 上传要合并的 Excel 文件（支持多选）
    3. **开始处理** - 点击按钮执行合并
    4. **下载结果** - 下载汇总表和质量报告
    """)

    st.markdown("---")

    # ========== 第1步：上传映射表 ==========
    st.subheader("📤 第1步：上传映射表")

    mapping_file = st.file_uploader(
        "上传列标题名称对照表",
        type=['xlsx', 'xls'],
        help="映射表第一行是标准列名，下方是该列的别名"
    )

    if mapping_file:
        try:
            mapping_df = bytes_to_df(mapping_file.getvalue(), mapping_file.name, header=None)
            st.success(f"✅ 映射表已加载，共 {mapping_df.shape[1]} 列")

            # 显示映射表预览
            with st.expander("查看映射表内容"):
                st.dataframe(mapping_df.head(10))
        except Exception as e:
            st.error(f"❌ 读取映射表失败: {e}")
            return
    else:
        st.info("👆 请先上传映射表文件")
        return

    # ========== 第2步：上传数据文件 ==========
    st.markdown("---")
    st.subheader("📤 第2步：上传数据文件")

    data_files = st.file_uploader(
        "上传要合并的 Excel 文件（可多选）",
        type=['xlsx', 'xls'],
        accept_multiple_files=True,
        help="选择包含数据的 Excel 文件，支持多选"
    )

    if data_files:
        st.success(f"✅ 已选择 {len(data_files)} 个文件")
        # 显示文件列表
        for f in data_files:
            st.write(f"  - {f.name}")
    else:
        st.info("👆 请上传至少一个数据文件")
        return

    # ========== 第3步：高级设置 ==========
    with st.expander("⚙️ 高级设置（可选）"):
        st.markdown("""
        **排除关键词**：输入要排除的文件名关键词，多个用逗号分隔
        """)
        exclude_keywords = st.text_input(
            "排除文件",
            value="",
            placeholder="例如：北京,宁夏,测试文件",
            help="文件名中包含这些关键词的文件将被排除"
        )

        st.markdown("""
        **省份名称**：为所有数据统一添加省份名称
        """)
        add_province = st.text_input(
            "统一省份名称（可选）",
            value="",
            placeholder="例如：湖南",
            help="输入后会在所有数据前添加省份列"
        )

    # ========== 第4步：执行合并 ==========
    st.markdown("---")

    if st.button("🚀 开始合并", type="primary", use_container_width=True):
        if not mapping_file or not data_files:
            st.error("请先上传映射表和数据文件")
            return

        with st.spinner("正在处理..."):
            try:
                # 构建映射表
                alias_to_standard, standard_columns = build_mapping(mapping_df)

                # 处理排除关键词
                exclude_list = [k.strip() for k in exclude_keywords.split(',') if k.strip()]

                # 处理文件
                all_data = []
                quality_report = []

                for f in data_files:
                    # 排除检查
                    if exclude_list:
                        if any(kw in f.name for kw in exclude_list):
                            quality_report.append({
                                '文件': f.name,
                                '状态': '已排除',
                                '行数': '-',
                                '匹配列数': '-',
                                '问题': '文件名包含排除关键词'
                            })
                            continue

                    try:
                        df = bytes_to_df(f.getvalue(), f.name)
                        result, issues = process_single_file(
                            df, f.name, alias_to_standard, standard_columns, add_province
                        )

                        if result is not None and not result.empty:
                            all_data.append(result)

                        quality_report.append({
                            '文件': f.name,
                            '状态': '✅ 成功' if not issues else '⚠️ 部分成功',
                            '行数': len(df),
                            '匹配列数': len([c for c in standard_columns if c in result.columns]) if result is not None else 0,
                            '问题': '; '.join(issues) if issues else '无'
                        })

                    except Exception as e:
                        quality_report.append({
                            '文件': f.name,
                            '状态': '❌ 失败',
                            '行数': 0,
                            '匹配列数': 0,
                            '问题': str(e)
                        })

                # 合并所有数据
                if all_data:
                    final_result = pd.concat(all_data, ignore_index=True, sort=False)

                    # 删除全为空的行
                    final_result.dropna(how='all', subset=standard_columns, inplace=True)
                    final_result.reset_index(drop=True, inplace=True)

                    # ========== 显示结果 ==========
                    st.success(f"✅ 合并完成！共 {len(final_result)} 行数据")

                    # 预览
                    st.subheader("📊 数据预览")
                    st.dataframe(final_result.head(20), use_container_width=True)

                    # 统计信息
                    col1, col2, col3 = st.columns(3)
                    col1.metric("总行数", len(final_result))
                    col2.metric("总列数", len(final_result.columns))
                    col3.metric("处理文件数", len(all_data))

                    # 下载按钮
                    st.subheader("📥 下载结果")

                    col_download1, col_download2 = st.columns(2)

                    # 汇总表下载
                    summary_bytes = df_to_bytes(final_result, "汇总表.xlsx", sheet_name="汇总数据")
                    col_download1.download_button(
                        label="📥 下载汇总表",
                        data=summary_bytes,
                        file_name="汇总表.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

                    # 质量报告下载
                    report_df = pd.DataFrame(quality_report)
                    report_bytes = df_to_bytes(report_df, "质量报告.xlsx", sheet_name="质量报告")
                    col_download2.download_button(
                        label="📥 下载质量报告",
                        data=report_bytes,
                        file_name="质量报告.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

                    # 同时下载两个sheet的完整报告
                    full_report = excel_to_bytes_multi_sheet({
                        '汇总数据': final_result,
                        '质量报告': report_df
                    }, "合并结果报告.xlsx")

                    st.download_button(
                        label="📦 下载完整报告（含汇总+质量报告）",
                        data=full_report,
                        file_name="合并结果报告.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        type="secondary"
                    )

                else:
                    st.warning("⚠️ 没有有效数据被处理")

                # 显示质量报告
                if quality_report:
                    st.subheader("📋 处理详情")
                    st.dataframe(pd.DataFrame(quality_report), use_container_width=True)

            except Exception as e:
                st.error(f"❌ 处理失败: {e}")
                import traceback
                st.code(traceback.format_exc())


def build_mapping(mapping_df):
    """
    从映射表构建别名到标准列名的映射

    Args:
        mapping_df: 映射表 DataFrame

    Returns:
        alias_to_standard: dict, 别名到标准名的映射
        standard_columns: list, 标准列名列表
    """
    alias_to_standard = {}
    standard_columns = []

    for col_idx in range(mapping_df.shape[1]):
        std_name = str(mapping_df.iloc[0, col_idx]).strip()

        # 跳过空标题和特定列
        if std_name in ('nan', '标准名称', '省份', ''):
            continue

        # 防止重复
        if std_name in standard_columns:
            continue

        standard_columns.append(std_name)
        alias_to_standard[std_name] = std_name

        # 按行号从小到大遍历别名（行号越小优先级越高）
        for row_idx in range(1, mapping_df.shape[0]):
            alias_val = mapping_df.iloc[row_idx, col_idx]
            if pd.isna(alias_val):
                continue

            alias_str = str(alias_val).strip()
            if alias_str and alias_str not in ('nan', ''):
                # 只有当这个别名还没被分配时才记录
                if alias_str not in alias_to_standard:
                    alias_to_standard[alias_str] = std_name

    return alias_to_standard, standard_columns


def process_single_file(df, filename, alias_to_standard, standard_columns, province_name=""):
    """
    处理单个数据文件

    Args:
        df: DataFrame
        filename: 文件名
        alias_to_standard: 别名映射
        standard_columns: 标准列列表
        province_name: 省份名称

    Returns:
        处理后的 DataFrame, 问题列表
    """
    issues = []

    # 处理重复列名
    if df.columns.duplicated().any():
        dup_cols = df.columns[df.columns.duplicated()].unique()
        issues.append(f'原表有重复列: {list(dup_cols)}')

        cols = list(df.columns)
        seen = {}
        new_cols = []
        for c in cols:
            if c in seen:
                seen[c] += 1
                new_cols.append(f"{c}_{seen[c]}")
            else:
                seen[c] = 0
                new_cols.append(c)
        df.columns = new_cols

    # 空数据检查
    if df.empty:
        issues.append('无数据')
        return None, issues

    # 列名映射
    cols = list(df.columns)
    rename_map = {}
    used_targets = {}

    for col in cols:
        col_str = str(col).strip()
        target = None

        # 精确匹配
        if col_str in alias_to_standard:
            target = alias_to_standard[col_str]
        else:
            # 清洗后匹配（去换行、空格）
            col_clean = col_str.replace('\n', '').replace(' ', '')
            for alias, std in alias_to_standard.items():
                if col_clean == alias.replace('\n', '').replace(' ', ''):
                    target = std
                    break

        if target:
            if target in used_targets:
                issues.append(f'多列→"{target}": 跳过[{col_str}]')
            else:
                if target != col_str and target in df.columns:
                    issues.append(f'列名冲突: 跳过[{col_str}→{target}]')
                else:
                    rename_map[col] = target
                    used_targets[target] = col_str

    df_renamed = df.rename(columns=rename_map)

    # 提取匹配列
    matched = [c for c in standard_columns if c in df_renamed.columns]
    missing = [c for c in standard_columns if c not in df_renamed.columns]

    # 关键列检查
    key_missing = [c for c in ['产品名称'] if c in missing]
    if key_missing:
        issues.append(f'缺关键列: {key_missing}')

    # 构建输出 DataFrame
    df_selected = pd.DataFrame(index=df.index)

    if matched:
        df_selected = df_renamed[[c for c in matched]].copy()

    # 添加省份列
    if province_name:
        df_selected.insert(0, '省份', province_name)
    elif '省份' in standard_columns:
        # 尝试从文件名提取省份
        province = extract_province_from_filename(filename)
        if province:
            df_selected.insert(0, '省份', province)

    # 补全缺失的标准列
    for c in standard_columns:
        if c not in df_selected.columns:
            df_selected[c] = np.nan

    # 确保列顺序
    output_columns = [c for c in standard_columns if c in df_selected.columns]
    if '省份' in df_selected.columns:
        output_columns = ['省份'] + [c for c in output_columns if c != '省份']

    df_selected = df_selected[output_columns]

    return df_selected, issues


def extract_province_from_filename(filename):
    """从文件名提取省份名称"""
    # 常见省份关键词
    provinces = [
        '北京', '天津', '河北', '山西', '内蒙古',
        '辽宁', '吉林', '黑龙江',
        '上海', '江苏', '浙江', '安徽', '福建', '江西', '山东',
        '河南', '湖北', '湖南', '广东', '广西', '海南',
        '重庆', '四川', '贵州', '云南', '西藏',
        '陕西', '甘肃', '青海', '宁夏', '新疆',
        '台湾', '香港', '澳门'
    ]

    for p in provinces:
        if p in filename:
            return p

    return ""
