"""
采购数据合并工具页面
"""

import streamlit as st
from datetime import datetime

from utils import (
    read_excel_bytes,
    build_alias_map,
    merge_all,
    df_to_excel_bytes,
    extract_zip_files,
)


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
            data_files = extract_zip_files(zip_file.read())
            if data_files:
                st.success(f"✅ 解压成功，共识别到 **{len(data_files)}** 个 Excel 文件")
                with st.expander("查看识别到的文件列表"):
                    for p in sorted(data_files.keys()):
                        st.text(p)
            else:
                st.error("ZIP 中未找到 Excel 文件，请确认文件结构是否正确。")
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
