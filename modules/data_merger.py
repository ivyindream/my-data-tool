"""
数据合并工作流模块
将多个 Excel 文件按映射表统一列名后合并，并支持信息匹配数据簿
"""
import streamlit as st
import pandas as pd
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.file_handler import bytes_to_df, df_to_bytes, excel_to_bytes_multi_sheet, excel_to_df_multi_sheet


def render():
    """渲染数据合并模块页面"""
    st.title("📋 数据合并工作流")
    st.markdown("---")

    # 步骤说明
    st.markdown("""
    ### 使用步骤
    1. **上传映射表** - 上传列标题名称对照表（Excel文件）
    2. **上传信息匹配数据簿（可选）** - 上传包含补充信息的Excel，按Sheet第一列匹配
    3. **上传数据文件** - 上传要合并的 Excel 文件（支持多选）
    4. **开始处理** - 点击按钮执行合并
    5. **下载结果** - 下载汇总表和质量报告
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

    # ========== 第1.5步：上传信息匹配数据簿（可选）============
    st.markdown("---")
    st.subheader("📚 第2步：上传信息匹配数据簿（可选）")

    info_book_file = st.file_uploader(
        "上传信息匹配数据簿",
        type=['xlsx', 'xls'],
        help="数据簿中每个sheet的第一列列名应与映射表标准列对应，用于匹配产品/项目名称"
    )

    info_book_sheets = {}  # 存储读取的sheet数据
    selected_sheets = []  # 用户选择的sheet列表

    if info_book_file:
        try:
            info_book_data = info_book_file.getvalue()
            info_book_sheets = excel_to_df_multi_sheet(info_book_data, info_book_file.name)

            if info_book_sheets:
                st.success(f"✅ 信息匹配数据簿已加载，共 {len(info_book_sheets)} 个工作表")

                # 先构建映射表的标准列名（用于验证匹配）
                alias_to_standard, standard_columns = build_mapping(mapping_df)

                # 显示sheet列表供选择，并标注哪些能匹配
                sheet_options = list(info_book_sheets.keys())

                # 检查每个Sheet是否能匹配
                sheet_status = {}
                for sheet_name in sheet_options:
                    df_preview = info_book_sheets[sheet_name].copy()
                    df_preview.columns = [str(col).strip() for col in df_preview.columns]
                    key_col_name = df_preview.columns[0] if len(df_preview.columns) > 0 else ""

                    if key_col_name in standard_columns:
                        sheet_status[sheet_name] = "✅ 可匹配"
                    else:
                        sheet_status[sheet_name] = f"⚠️ 列名「{key_col_name}」不在映射表标准列中，无法匹配"

                # 显示匹配状态
                st.markdown("**📋 Sheet匹配状态：**")
                for sheet_name, status in sheet_status.items():
                    if "✅" in status:
                        st.write(f"  {sheet_name}: {status}")
                    else:
                        st.warning(f"  {sheet_name}: {status}")

                # 只允许选择能匹配的Sheet
                valid_sheets = [s for s in sheet_options if sheet_status[s].startswith("✅")]
                if not valid_sheets:
                    st.warning("⚠️ 没有Sheet能与映射表标准列匹配，将跳过信息匹配步骤")
                    selected_sheets = []
                else:
                    if len(valid_sheets) > 5:
                        valid_sheets = valid_sheets[:5]
                        st.info("ℹ️ 最多支持5个Sheet进行匹配，已自动选择前5个")

                    selected_sheets = st.multiselect(
                        f"选择要匹配的Sheet（已验证可匹配，共 {len(valid_sheets)} 个）",
                        options=valid_sheets,
                        default=valid_sheets,
                        help="只有Sheet第一列列名与映射表标准列匹配的才会显示"
                    )

                # 预览每个选中sheet的内容
                if selected_sheets:
                    with st.expander("📋 查看选中Sheet的预览"):
                        for sheet_name in selected_sheets:
                            df_preview = info_book_sheets[sheet_name].copy()
                            df_preview.columns = [str(col).strip() for col in df_preview.columns]
                            key_col_name = df_preview.columns[0]
                            info_cols = list(df_preview.columns[1:])
                            st.markdown(f"**Sheet: {sheet_name}** (共 {len(df_preview)} 行)")
                            st.markdown(f"🔑 **关键字列: `{key_col_name}`** → 将用此列匹配映射表中的标准列")
                            if info_cols:
                                st.markdown(f"📝 **补充信息列: `{', '.join(info_cols)}`**")
                            st.dataframe(df_preview.head(5))
                            st.markdown("---")
            else:
                st.warning("⚠️ 数据簿中没有找到有效的工作表")
        except Exception as e:
            st.warning(f"⚠️ 读取信息匹配数据簿失败: {e}，将跳过信息匹配步骤")

    # ========== 第2步：上传数据文件 ==========
    st.markdown("---")
    st.subheader("📤 第3步：上传数据文件")

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

                # 构建信息匹配字典（传入标准列名进行验证）
                info_dict, info_columns = build_info_dict(info_book_sheets, selected_sheets, standard_columns)

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
                                '信息匹配': '-',
                                '问题': '文件名包含排除关键词'
                            })
                            continue

                    try:
                        df = bytes_to_df(f.getvalue(), f.name)
                        result, matched_sheets, issues = process_single_file(
                            df, f.name, alias_to_standard, standard_columns,
                            info_dict, info_columns
                        )

                        if result is not None and not result.empty:
                            # 添加数据源列（文件名 + Sheet名称）
                            source_name = matched_sheets if matched_sheets else ''
                            if source_name:
                                source_name = f"{f.name} > {source_name}"
                            if '数据源' not in result.columns:
                                result.insert(len(result.columns), '数据源', source_name)

                            all_data.append(result)

                        matched_sheets_display = matched_sheets if matched_sheets else '❌ 未匹配'
                        quality_report.append({
                            '文件': f.name,
                            '状态': '✅ 成功' if not issues else '⚠️ 部分成功',
                            '行数': len(df),
                            '匹配列数': len([c for c in standard_columns if c in result.columns]) if result is not None else 0,
                            '信息匹配': matched_sheets_display,
                            '问题': '; '.join(issues) if issues else '无'
                        })

                    except Exception as e:
                        quality_report.append({
                            '文件': f.name,
                            '状态': '❌ 失败',
                            '行数': 0,
                            '匹配列数': 0,
                            '信息匹配': '-',
                            '问题': str(e)
                        })

                # 合并所有数据
                if all_data:
                    final_result = pd.concat(all_data, ignore_index=True, sort=False)

                    # 删除全为空的行（排除数据源列）
                    cols_for_check = [c for c in final_result.columns if c != '数据源']
                    if cols_for_check:
                        final_result.dropna(how='all', subset=cols_for_check, inplace=True)
                    final_result.reset_index(drop=True, inplace=True)

                    # ========== 显示结果 ==========
                    st.success(f"✅ 合并完成！共 {len(final_result)} 行数据")

                    # 预览
                    st.subheader("📊 数据预览")
                    st.dataframe(final_result.head(20), use_container_width=True)

                    # 统计信息
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("总行数", len(final_result))
                    col2.metric("总列数", len(final_result.columns))
                    col3.metric("处理文件数", len(all_data))
                    matched_count = len(final_result[final_result['数据源'].notna() & (final_result['数据源'] != '')])
                    col4.metric("已匹配Sheet数", matched_count)

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


def build_info_dict(info_book_sheets, selected_sheets, standard_columns):
    """
    从信息匹配数据簿构建匹配字典（仅保留第一列列名匹配标准列的Sheet）

    Args:
        info_book_sheets: dict, {sheet_name: DataFrame}
        selected_sheets: list, 用户选择的sheet名称列表
        standard_columns: list, 映射表的标准列名列表

    Returns:
        info_dict: dict, {sheet_name: {'key_col': 第一列列名, 'info_cols': [补充列列表], 'mapping': {关键字值: {列名: 值}}}}
        info_columns: list, 需要补充的列名列表（不含关键字列）
    """
    info_dict = {}
    info_columns = []

    for sheet_name in selected_sheets:
        if sheet_name not in info_book_sheets:
            continue

        df = info_book_sheets[sheet_name].copy()
        if df.empty or len(df.columns) < 2:
            continue

        # 清理列名（去除首尾空格）
        df.columns = [str(col).strip() for col in df.columns]

        # 第一列作为关键字列
        key_col = df.columns[0]

        # 【关键】检查第一列列名是否在标准列中
        if key_col not in standard_columns:
            # 不匹配，跳过
            continue

        info_cols = list(df.columns[1:])

        # 初始化sheet的字典
        info_dict[sheet_name] = {
            'key_col': key_col,  # 这个列名就是标准列名
            'info_cols': info_cols,
            'mapping': {}
        }

        # 收集所有信息列
        for col in info_cols:
            if col not in info_columns:
                info_columns.append(col)

        # 构建关键字到行的映射（第一列的值作为关键字）
        for _, row in df.iterrows():
            key_val = row[key_col]
            if pd.isna(key_val):
                continue

            key_str = str(key_val).strip()
            if key_str:
                info_dict[sheet_name]['mapping'][key_str] = {
                    col: row[col] for col in info_cols
                }

    return info_dict, info_columns


def process_single_file(df, filename, alias_to_standard, standard_columns,
                        info_dict=None, info_columns=None):
    """
    处理单个数据文件

    Args:
        df: DataFrame
        filename: 文件名
        alias_to_standard: 别名映射
        standard_columns: 标准列列表
        info_dict: 信息匹配字典
        info_columns: 需要补充的列名列表

    Returns:
        处理后的 DataFrame, 匹配的sheet名称列表, 问题列表
    """
    issues = []
    matched_sheet = None

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
        return None, None, issues

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
    if missing:
        issues.append(f'缺关键列: {missing}')

    # 构建输出 DataFrame
    df_selected = pd.DataFrame(index=df.index)

    if matched:
        df_selected = df_renamed[[c for c in matched]].copy()

    # 补全缺失的标准列
    for c in standard_columns:
        if c not in df_selected.columns:
            df_selected[c] = np.nan

    # 确保列顺序
    output_columns = [c for c in standard_columns if c in df_selected.columns]

    # 信息匹配：根据Sheet第一列的列名（即标准列名）去匹配
    if info_dict:
        matched_sheet = match_info(df_selected, info_dict, info_columns)
    else:
        matched_sheet = None

    # 补充信息列（如果存在的话）
    if info_columns:
        for col in info_columns:
            if col not in df_selected.columns:
                df_selected[col] = np.nan

    # 确保输出列包含：标准列 + 信息匹配列
    output_columns_with_info = output_columns.copy()
    for col in info_columns:
        if col not in output_columns_with_info:
            output_columns_with_info.append(col)

    df_selected = df_selected[output_columns_with_info]

    return df_selected, matched_sheet, issues


def match_info(df, info_dict, info_columns):
    """
    根据Sheet第一列的列名（标准列名）去匹配对应列的信息

    Args:
        df: DataFrame（已映射为标准列）
        info_dict: 信息匹配字典（key_col就是标准列名）
        info_columns: 需要补充的列名列表

    Returns:
        匹配的sheet名称列表
    """
    matched_sheets = []

    # 首先清理列名（去除首尾空格）
    df.columns = [str(col).strip() for col in df.columns]

    # 按sheet顺序匹配
    for sheet_name, sheet_data in info_dict.items():
        key_col_name = sheet_data['key_col']  # 这就是标准列名（如"项目名称"）
        mapping = sheet_data['mapping']
        info_cols = sheet_data['info_cols']

        # 检查数据表是否有对应的标准列
        if key_col_name not in df.columns:
            continue

        sheet_matched = False

        # 遍历每行，用标准列的值去信息匹配表中查找
        for idx, row in df.iterrows():
            key_val = row[key_col_name]
            if pd.isna(key_val):
                continue

            # 清理关键字（去除首尾空格）
            key_str = str(key_val).strip()

            # 在信息匹配表中查找（精确匹配）
            if key_str in mapping:
                # 找到匹配，补充信息
                for col in info_cols:
                    if col in df.columns:
                        # 如果该列已有值，不覆盖
                        if pd.isna(df.at[idx, col]):
                            df.at[idx, col] = mapping[key_str][col]
                    else:
                        # 添加新列
                        df[col] = np.nan
                        df.at[idx, col] = mapping[key_str][col]

                sheet_matched = True

        if sheet_matched:
            matched_sheets.append(sheet_name)

    # 返回匹配的sheet名称列表（逗号分隔）
    return ', '.join(matched_sheets) if matched_sheets else None

