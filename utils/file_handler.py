"""
文件处理工具 - 内存操作，不落盘
所有文件操作使用 BytesIO，保护用户隐私
"""
import io
import pandas as pd


def bytes_to_df(data: bytes, filename: str, **kwargs) -> pd.DataFrame:
    """
    将字节数据转换为 DataFrame

    Args:
        data: 文件字节数据
        filename: 文件名（用于判断格式）
        **kwargs: 传给 pandas 的参数

    Returns:
        DataFrame
    """
    buffer = io.BytesIO(data)

    # 自动识别格式
    ext = filename.lower().split('.')[-1]

    if ext == 'xlsx':
        return pd.read_excel(buffer, engine='openpyxl', **kwargs)
    elif ext == 'xls':
        return pd.read_excel(buffer, engine='xlrd', **kwargs)
    elif ext == 'csv':
        return pd.read_csv(buffer, **kwargs)
    else:
        raise ValueError(f"不支持的格式: {ext}")


def df_to_bytes(df: pd.DataFrame, filename: str, sheet_name: str = 'Sheet1') -> bytes:
    """
    将 DataFrame 转换为 Excel 字节数据

    Args:
        df: DataFrame
        filename: 文件名（用于判断格式）
        sheet_name: 工作表名称

    Returns:
        字节数据
    """
    buffer = io.BytesIO()
    ext = filename.lower().split('.')[-1]

    if ext in ('xlsx', 'xls'):
        df.to_excel(buffer, sheet_name=sheet_name, index=False, engine='openpyxl')
    elif ext == 'csv':
        df.to_csv(buffer, index=False, encoding='utf-8-sig')
    else:
        raise ValueError(f"不支持的格式: {ext}")

    buffer.seek(0)
    return buffer.getvalue()


def excel_to_bytes_multi_sheet(sheets: dict, filename: str) -> bytes:
    """
    将多个 DataFrame 写入同一个 Excel 文件的不同 Sheet

    Args:
        sheets: dict, {sheet_name: DataFrame}
        filename: 输出文件名

    Returns:
        字节数据
    """
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    buffer.seek(0)
    return buffer.getvalue()


def detect_format(data: bytes) -> str:
    """
    检测字节数据的 Excel 格式

    Args:
        data: 文件字节数据（前4字节）

    Returns:
        'xlsx' 或 'xls'
    """
    header = data[:4]

    if header[:2] == b'PK':  # ZIP-based (xlsx, docx, etc.)
        return 'xlsx'
    elif header == b'\xd0\xcf\x11\xe0':  # OLE format (xls)
        return 'xls'

    return 'unknown'
