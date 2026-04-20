"""
采购数据合并工具 - Web 版
基于 Streamlit 构建，可部署到 Streamlit Cloud
"""

import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import zipfile
import tempfile
import hashlib
from datetime import datetime

# ============================================================
#  全局配置
# ============================================================

# 管理员密码（SHA-256 哈希值，修改密码请替换此处）
# 默认密码为 admin123，可在 Streamlit Cloud Secrets 中配置
def get_admin_hash():
    try:
        return st.secrets["ADMIN_PASSWORD_HASH"]
    except Exception:
        # 默认密码 admin123 的 SHA-256（生产环境请务必在 Secrets 里替换）
        return hashlib.sha256("admin123".encode()).hexdigest()

APP_TITLE = "数据处理工作台"
MODULE_NAME = "采购数据合并工具"

# ============================================================
#  工具函数
# ============================================================

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def detect_format(file_bytes: bytes):
    """检测 Excel 文件实际格式（不依赖后缀名）"""
    if file_bytes[:2] == b'PK':
        return 'xlsx'
    elif file_bytes[:4] == b'\xd0\xcf\x11\xe0':
        return 'xls'
    return None


def read_excel_bytes(file_bytes: bytes, skip_rows: int = 0):
    """从 bytes 读取 Excel，自动识别格式"""
    fmt = detect_format(file_bytes)
    buf = io.BytesIO(file_bytes)
    if fmt == 'xlsx':
        return pd.read_excel(buf, engine='openpyxl', header=skip_rows)
    elif fmt == 'xls':
        return pd.read_excel(buf, engine='xlrd', header=skip_rows)
    else:
        # 兜底：交给 pandas 自行尝试
        return pd.read_excel(buf, header=skip_rows)


def build_alias_map(mapping_df: pd.DataFrame, extra_aliases: dict) -> tuple[dict, list]:
    """从映射表 DataFrame 构建 {别名: 标准列名} 和有序标准列列表"""
    alias_to_standard = {}
    standard_columns = []

    for col_idx in range(mapping_df.shape[1]):
        std_name = str(mapping_df.iloc[0, col_idx]).strip()
        if std_name in ('nan', '标准名称', '省份', ''):
            continue
        if std_name in standard_columns:
            continue
        standard_columns.append(std_name)
        alias_to_standard[std_name] = std_name

        for row_idx in range(1, mapping_df.shape[0]):
            alias_val = mapping_df.iloc[row_idx, col_idx]
            if pd.isna(alias_val):
                continue
            alias_str = str(alias_val).strip()
            if alias_str and alias_str != 'nan':
                if alias_str not in alias_to_standard:
                    alias_to_standard[alias_str] = std_name

    for alias, std in extra_aliases.items():
        if alias and std:
            alias_to_standard[alias.strip()] = std.strip()

    return alias_to_standard, standard_columns


def get_province_from_path(rel_path: str) -> str:
    """从相对路径提取省份名（第一级文件夹名）"""
    parts = rel_path.replace('\\', '/').split('/')
    name = parts[0] if parts else rel_path
    # 去除常见年份前缀
    for prefix in ['2026年1-3月', '2026年第一季度', '2025年', '2024年']:
        name = name.replace(prefix, '')
    return name.strip()


def process_single_file(
    file_bytes: bytes,
    filename: str,
    rel_path: str,
    alias_to_standard: dict,
    standard_columns: list,
    skip_rows: int = 0,
) -> tuple:
    """
    处理单个 Excel 文件。
    返回 (df_selected | None, report_dict)
    """
    province = get_province_from_path(rel_path)
    file_issues = []

    try:
        df = read_excel_bytes(file_bytes, skip_rows)
    except Exception as e:
        return None, {
            '文件': rel_path, '省份': province, '行数': 0,
            '匹配列': 0, '缺失列': '', '问题': f'读取失败: {e}'
        }

    if df.empty:
        return None, {
            '文件': rel_path, '省份': province, '行数': 0,
            '匹配列': 0, '缺失列': '', '问题': '无数据'
        }

    # 处理重复列名
    if df.columns.duplicated().any():
        dup_cols = df.columns[df.columns.duplicated()].unique()
        file_issues.append(f'原表有重复列: {list(dup_cols)}')
        seen = {}
        new_cols = []
        for c in df.columns:
            if c in seen:
                seen[c] += 1
                new_cols.append(f"{c}_{seen[c]}")
            else:
                seen[c] = 0
                new_cols.append(c)
        df.columns = new_cols

    row_count = len(df)

    # 列名映射
    rename_map = {}
    used_targets = {}
    for col in df.columns:
        col_str = str(col).strip()
        target = None
        if col_str in alias_to_standard:
            target = alias_to_standard[col_str]
        else:
            col_clean = col_str.replace('\n', '').replace(' ', '')
            for alias, std in alias_to_standard.items():
                if col_clean == alias.replace('\n', '').replace(' ', ''):
                    target = std
                    break
        if target:
            if target in used_targets:
                file_issues.append(
                    f'多列→"{target}": 优先保留[{used_targets[target]}], 跳过[{col_str}]'
                )
            else:
                if target != col_str and target in df.columns:
                    file_issues.append(
                        f'列名冲突: 原始已有[{target}], 跳过别名映射[{col_str}→{target}]'
                    )
                else:
                    rename_map[col] = target
                    used_targets[target] = col_str

    df_renamed = df.rename(columns=rename_map)

    matched = [c for c in standard_columns if c in df_renamed.columns]
    missing = [c for c in standard_columns if c not in df_renamed.columns]

    key_missing = [c for c in ['产品名称'] if c in missing]
    if key_missing:
        file_issues.append(f'缺关键列: {key_missing}')

    df_selected = pd.DataFrame(index=df.index)
    if matched:
        df_selected = df_renamed[[c for c in matched]].copy()

    df_selected['省份'] = province
    for c in standard_columns:
        if c not in df_selected.columns:
            df_selected[c] = np.nan

    output_columns = list(dict.fromkeys(['省份'] + standard_columns))
    df_selected = df_selected[output_columns]

    issue_str = '; '.join(file_issues) if file_issues else '无'
    report = {
        '文件': rel_path, '省份': province, '行数': row_count,
        '匹配列': len(matched), '缺失列': ','.join(missing) if missing else '-',
        '问题': issue_str
    }
    return df_selected, report


def merge_all(
    data_files: dict,           # {rel_path: bytes}
    mapping_bytes: bytes,
    exclude_folders: list,
    skip_header_map: dict,      # {rel_path: skip_rows}
    extra_aliases: dict,
    standard_columns_override: list = None,
) -> tuple:
    """
    主合并函数。
    返回 (result_df | None, quality_report_list, log_lines)
    """
    log_lines = []

    # 读映射表
    try:
        mapping_df = read_excel_bytes(mapping_bytes, skip_rows=0)
    except Exception as e:
        return None, [], [f"❌ 映射表读取失败: {e}"]

    alias_to_standard, standard_columns = build_alias_map(mapping_df, extra_aliases)
    if standard_columns_override:
        standard_columns = standard_columns_override

    log_lines.append(f"📋 标准列（{len(standard_columns)} 个）: {', '.join(standard_columns)}")

    all_data = []
    quality_report = []

    for rel_path, file_bytes in data_files.items():
        # 排除检查
        first_folder = rel_path.replace('\\', '/').split('/')[0]
        if any(first_folder == exc.strip() for exc in exclude_folders if exc.strip()):
            province = get_province_from_path(rel_path)
            log_lines.append(f"  ⏭ [排除] {rel_path}")
            quality_report.append({
                '文件': rel_path, '省份': province, '行数': '-',
                '匹配列': '-', '缺失列': '-', '问题': '已排除'
            })
            continue

        # 跳过非 Excel 文件
        if not rel_path.lower().endswith(('.xlsx', '.xls')):
            continue

        skip = skip_header_map.get(rel_path, 0)
        df_sel, report = process_single_file(
            file_bytes, os.path.basename(rel_path), rel_path,
            alias_to_standard, standard_columns, skip
        )

        quality_report.append(report)
        if df_sel is not None:
            all_data.append(df_sel)
            status = "⚠️" if report['问题'] != '无' else "✅"
            log_lines.append(
                f"  {status} {rel_path} — {report['行数']} 行 | "
                f"匹配 {report['匹配列']}/{len(standard_columns)} | {report['问题']}"
            )
        else:
            log_lines.append(f"  ❌ {rel_path} — {report['问题']}")

    if not all_data:
        return None, quality_report, log_lines + ["❌ 无有效数据，请检查文件格式或映射表。"]

    result = pd.concat(all_data, ignore_index=True, sort=False)
    result.dropna(how='all', subset=standard_columns, inplace=True)
    result.reset_index(drop=True, inplace=True)

    log_lines.append(f"\n✅ 合并完成！共 {len(result)} 行，{len(standard_columns)} 列")
    return result, quality_report, log_lines


def df_to_excel_bytes(result_df: pd.DataFrame, quality_report: list) -> bytes:
    """将结果和质量报告打包成 Excel bytes"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        result_df.to_excel(writer, sheet_name='汇总数据', index=False)
        if quality_report:
            pd.DataFrame(quality_report).to_excel(
                writer, sheet_name='数据质量报告', index=False
            )
    return output.getvalue()


# ============================================================
#  页面：数据合并工作流
# ============================================================

def page_merge_tool():
    st.header("📊 采购数据合并工具")
    st.markdown(
        "将多个省份的采购数据文件，按照统一的列名映射表，自动合并为一张汇总表。"
    )

    st.divider()

    # ---------- 步骤 1：上传映射表 ----------
    st.subheader("第一步：上传列标题映射表")
    st.markdown(
        "请上传 `列标题名称.xlsx` 文件。"
        "该文件第一行为标准列名，下方各行为各省文件中可能出现的别名。"
    )
    mapping_file = st.file_uploader(
        "选择映射表文件",
        type=["xlsx", "xls"],
        key="mapping_upload",
        help="格式：第一行 = 标准列名，第2行起 = 各省别名"
    )

    st.divider()

    # ---------- 步骤 2：上传数据文件 ----------
    st.subheader("第二步：上传省份数据文件")
    upload_mode = st.radio(
        "上传方式",
        ["📦 ZIP 压缩包（推荐，保留省份文件夹结构）", "📄 直接上传多个 Excel 文件"],
        horizontal=True,
        key="upload_mode"
    )

    data_files = {}  # {rel_path: bytes}

    if "ZIP" in upload_mode:
        st.markdown(
            "请将所有省份文件夹**直接压缩成 ZIP**（不要额外套一层文件夹），"
            "每个省份对应一个子文件夹，文件夹名即为省份名。"
        )
        zip_file = st.file_uploader(
            "上传 ZIP 压缩包",
            type=["zip"],
            key="zip_upload"
        )
        if zip_file:
            try:
                with zipfile.ZipFile(io.BytesIO(zip_file.read()), 'r') as zf:
                    for name in zf.namelist():
                        if name.endswith('/'):
                            continue
                        if not name.lower().endswith(('.xlsx', '.xls')):
                            continue
                        # 忽略 macOS 系统文件
                        if '__MACOSX' in name or name.startswith('.'):
                            continue
                        data_files[name] = zf.read(name)
                st.success(f"✅ 解压成功，共识别到 **{len(data_files)}** 个 Excel 文件")
                with st.expander("查看识别到的文件列表"):
                    for p in sorted(data_files.keys()):
                        st.text(p)
            except Exception as e:
                st.error(f"ZIP 解压失败：{e}")
    else:
        st.markdown(
            "直接上传所有省份的 Excel 文件。"
            "**注意：** 系统将以文件名（去掉扩展名）作为省份名。"
        )
        excel_files = st.file_uploader(
            "上传数据文件（可多选）",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
            key="excel_upload"
        )
        if excel_files:
            for f in excel_files:
                data_files[f.name] = f.read()
            st.success(f"✅ 已上传 **{len(data_files)}** 个文件")

    st.divider()

    # ---------- 高级设置（可折叠）----------
    with st.expander("⚙️ 高级设置（可选，不填则使用默认值）"):
        st.markdown("**排除的省份**（输入文件夹名，每行一个）")
        exclude_input = st.text_area(
            "排除省份",
            placeholder="例：\n北京\n宁夏\n黑龙江",
            height=100,
            label_visibility="collapsed",
            key="exclude_input"
        )

        st.markdown("**需要跳过表头行的文件**（格式：`文件相对路径 = 跳过行数`，每行一个）")
        skip_input = st.text_area(
            "跳过表头",
            placeholder="例：\n安徽/安徽订单.xlsx = 1\n广东/广东数据.xls = 2",
            height=100,
            label_visibility="collapsed",
            key="skip_input"
        )

        st.markdown("**补充列名别名**（格式：`别名 = 标准列名`，每行一个）")
        alias_input = st.text_area(
            "额外别名",
            placeholder="例：\n采购产品 = 产品名称\n订购量 = 订单数量",
            height=100,
            label_visibility="collapsed",
            key="alias_input"
        )

    # ---------- 解析高级设置 ----------
    exclude_folders = [line.strip() for line in exclude_input.strip().splitlines() if line.strip()]
    skip_header_map = {}
    for line in skip_input.strip().splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            try:
                skip_header_map[k.strip()] = int(v.strip())
            except ValueError:
                pass
    extra_aliases = {}
    for line in alias_input.strip().splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            extra_aliases[k.strip()] = v.strip()

    st.divider()

    # ---------- 步骤 3：开始合并 ----------
    st.subheader("第三步：开始合并")

    can_run = mapping_file is not None and len(data_files) > 0
    if not can_run:
        missing = []
        if mapping_file is None:
            missing.append("映射表")
        if len(data_files) == 0:
            missing.append("省份数据文件")
        st.info(f"⬆️ 请先完成上传：{' 和 '.join(missing)}")

    run_btn = st.button(
        "🚀 开始合并",
        type="primary",
        disabled=not can_run,
        use_container_width=True
    )

    if run_btn and can_run:
        mapping_bytes = mapping_file.read()

        with st.spinner("正在处理中，请稍候……"):
            result_df, quality_report, log_lines = merge_all(
                data_files=data_files,
                mapping_bytes=mapping_bytes,
                exclude_folders=exclude_folders,
                skip_header_map=skip_header_map,
                extra_aliases=extra_aliases,
            )

        # 显示处理日志
        with st.expander("📋 处理日志", expanded=True):
            for line in log_lines:
                st.text(line)

        if result_df is not None:
            st.success(f"✅ 合并完成！共 **{len(result_df)}** 行数据")

            # 预览前 20 行
            st.subheader("数据预览（前 20 行）")
            st.dataframe(result_df.head(20), use_container_width=True)

            # 质量报告
            if quality_report:
                st.subheader("数据质量报告")
                report_df = pd.DataFrame(quality_report)
                problems = report_df[~report_df['问题'].isin(['无', '已排除'])]
                if len(problems) > 0:
                    st.warning(f"⚠️ {len(problems)} 个文件存在问题，请查看下方报告")
                st.dataframe(report_df, use_container_width=True)

            # 下载按钮
            st.subheader("第四步：下载结果")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"采购数据汇总_{timestamp}.xlsx"
            excel_bytes = df_to_excel_bytes(result_df, quality_report)

            st.download_button(
                label="⬇️ 下载汇总表（含质量报告）",
                data=excel_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
            )
            st.caption("💡 下载后数据将从服务器自动清除，不会被保存。")
        else:
            st.error("合并失败，请检查文件和映射表是否正确。")


# ============================================================
#  页面：管理员区域
# ============================================================

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


# ============================================================
#  主应用入口
# ============================================================

def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # 侧边栏导航
    with st.sidebar:
        st.title(f"📊 {APP_TITLE}")
        st.markdown("---")
        page = st.radio(
            "选择功能模块",
            ["采购数据合并", "管理员区域"],
            key="nav"
        )
        st.markdown("---")
        st.markdown(
            "**使用说明**\n\n"
            "1. 准备好映射表和各省数据\n"
            "2. 按步骤上传文件\n"
            "3. 点击开始合并\n"
            "4. 下载结果文件\n\n"
            "数据仅在当前会话中存在，\n关闭页面后自动清除。"
        )
        st.markdown("---")
        st.caption("Powered by Streamlit")

    if page == "采购数据合并":
        page_merge_tool()
    elif page == "管理员区域":
        page_admin()


if __name__ == "__main__":
    main()
