"""
共享工具函数模块
被所有页面模块调用
"""

import io
import os
import hashlib
import zipfile
import pandas as pd
import numpy as np
from datetime import datetime


# ============================================================
#  密码相关
# ============================================================

def hash_password(pw: str) -> str:
    """对密码进行 SHA-256 哈希"""
    return hashlib.sha256(pw.encode()).hexdigest()


def get_admin_hash(st_secrets=None) -> str:
    """获取管理员密码哈希，支持 st.secrets 或硬编码默认值"""
    if st_secrets is not None:
        try:
            return st_secrets["ADMIN_PASSWORD_HASH"]
        except Exception:
            pass
    # 默认密码 admin123 的 SHA-256（生产环境请在 Secrets 里替换）
    return hashlib.sha256("admin123".encode()).hexdigest()


# ============================================================
#  Excel 处理
# ============================================================

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
    data_files: dict,
    mapping_bytes: bytes,
    exclude_folders: list,
    skip_header_map: dict,
    extra_aliases: dict,
    standard_columns_override: list = None,
) -> tuple:
    """
    主合并函数。
    返回 (result_df | None, quality_report_list, log_lines)
    """
    log_lines = []

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
        first_folder = rel_path.replace('\\', '/').split('/')[0]
        if any(first_folder == exc.strip() for exc in exclude_folders if exc.strip()):
            province = get_province_from_path(rel_path)
            log_lines.append(f"  ⏭ [排除] {rel_path}")
            quality_report.append({
                '文件': rel_path, '省份': province, '行数': '-',
                '匹配列': '-', '缺失列': '-', '问题': '已排除'
            })
            continue

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


def extract_zip_files(zip_bytes: bytes) -> dict:
    """
    从 ZIP bytes 中提取所有 Excel 文件。
    返回 {rel_path: file_bytes}
    """
    data_files = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            for name in zf.namelist():
                if name.endswith('/'):
                    continue
                if not name.lower().endswith(('.xlsx', '.xls')):
                    continue
                if '__MACOSX' in name or name.startswith('.'):
                    continue
                data_files[name] = zf.read(name)
    except Exception:
        pass
    return data_files
