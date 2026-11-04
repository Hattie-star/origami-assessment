import io
import math
import time
from datetime import datetime

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageOps
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="折纸康复测评｜角点偏差", page_icon="📐", layout="wide")
st.title("📐 折纸精细动作康复评估｜教学原型")
st.caption("照片角点测量 + 用时记录 + 前后测对比。半自动测量工具，非已验证的临床量表或全自动AI识别。")

if "records" not in st.session_state:
    st.session_state.records = {}
if "points" not in st.session_state:
    st.session_state.points = {}
if "timer_starts" not in st.session_state:
    st.session_state.timer_starts = {}

with st.expander("使用说明与测量前提（请先阅读）", expanded=True):
    st.markdown("""1. 把折叠后的作品平放在测评底板上，**手机垂直俯拍**，四个定位标记尽可能完整入镜，纸张和校准线保持在同一平面。\n2. 上传照片，先按提示点选 **两个已知实际距离** 的校准端点（例如放在纸面旁的标准100 mm刻度两端），再点选 **理想目标角点** 和 **实际折后角点**。\n3. 程序按像素距离比例换算毫米值；**透视、纸张翘起、点击误差会影响结果**。请在正式使用前用直尺复核。\n4. 本版为半自动点选，不声称能从照片判断用时、动作协调或是否独立。用时由现场计时并记录，提示等级由教师观察。\n5. 前测、后测须使用相同任务、纸张和评分规则。**已生成的底板示意图片不是保证1:1尺寸的工程图**，打印后一定要用实体尺核对其标尺；未核对前不能直接作为毫米标定标准。""")

student = st.text_input("学生匿名编号", value="S01", help="不要填写真实姓名、诊断或其他身份信息。")
phase = st.radio("测评阶段", ["前测", "后测"], horizontal=True)
col_timer, col_time = st.columns([2, 2])
start_key = (student, phase)
with col_timer:
    b1, b2 = st.columns(2)
    if b1.button("▶ 开始计时", use_container_width=True):
        st.session_state.timer_starts[start_key] = time.monotonic()
        st.toast("开始计时")
    if b2.button("■ 停止计时", use_container_width=True):
        started = st.session_state.timer_starts.pop(start_key, None)
        if started is not None:
            st.session_state[f"secs_{student}_{phase}"] = round(time.monotonic() - started, 1)
        else:
            st.warning("请先点击开始计时")
with col_time:
    secs = st.number_input("实际完成用时（秒，可手动校正）", min_value=0.0, max_value=3600.0, step=0.5, key=f"secs_{student}_{phase}")

prompt = st.selectbox("教师观察：最高提示等级", ["独立", "口头/视觉提示", "示范提示", "身体辅助"])
source = st.radio("图片来源", ["上传照片", "现场拍照"], horizontal=True)
upload = st.file_uploader("上传测评照片", type=["jpg", "jpeg", "png"], key=f"upload_{phase}") if source == "上传照片" else st.camera_input("拍摄折纸作品", key=f"camera_{phase}")

if upload is not None:
    raw = ImageOps.exif_transpose(Image.open(upload)).convert("RGB")
    max_width = 900
    width = min(max_width, raw.width)
    height = round(raw.height * width / raw.width)
    img = raw.resize((width, height), Image.Resampling.LANCZOS)
    shot_sig = (student, phase, getattr(upload, "name", "camera"), len(upload.getvalue()), hash(upload.getvalue()))
    if st.session_state.get("last_sig") != shot_sig:
        st.session_state.points[shot_sig] = []
        st.session_state["last_sig"] = shot_sig

    steps = ["校准点1", "校准点2", "目标角点", "实际角点"]
    pts = st.session_state.points.get(shot_sig, [])
    calibration_mm = st.number_input("两个校准点之间的真实距离（mm）", min_value=10.0, max_value=1000.0, value=100.0, step=10.0)
    st.info(f"当前点选：**{steps[len(pts)] if len(pts)<4 else '已完成'}**。请按顺序在下图点击；如点错可撤销。")
    draw = img.copy()
    d = ImageDraw.Draw(draw)
    for index, (x, y) in enumerate(pts):
        r = 8
        color = ["#0077bb", "#0077bb", "#27a776", "#d65b2b"][index]
        d.ellipse((x-r, y-r, x+r, y+r), outline=color, width=3)
        d.text((x+10, y-12), f"{index+1}", fill=color)
    if len(pts) == 4:
        d.line((*pts[2], *pts[3]), fill="#d65b2b", width=3)
    display_key = f"coord_{phase}_{len(pts)}_{hash(shot_sig)}"
    clicked = streamlit_image_coordinates(draw, key=display_key)
    if clicked and len(pts) < 4:
        xy = (int(clicked["x"]), int(clicked["y"]))
        st.session_state.points[shot_sig].append(xy)
        st.rerun()

    u1, u2 = st.columns(2)
    if u1.button("↩ 撤销上一个点", disabled=not pts, use_container_width=True):
        st.session_state.points[shot_sig].pop()
        st.rerun()
    if u2.button("重置四个点", disabled=not pts, use_container_width=True):
        st.session_state.points[shot_sig] = []
        st.rerun()

    if len(pts) == 4:
        cal_px = math.dist(pts[0], pts[1])
        corner_px = math.dist(pts[2], pts[3])
        if cal_px < 5:
            st.error("校准点距离太小，请重试。")
        else:
            deviation_mm = corner_px / cal_px * calibration_mm
            # Explicit boundaries: <=3, <=8, >8; do not leave a gap for decimals.
            grade = 2 if deviation_mm <= 3 else (1 if deviation_mm <= 8 else 0)
            timing_score = 2 if 0 < secs <= 60 else (1 if 60 < secs <= 120 else 0)
            independence_score = 2 if prompt == "独立" else (1 if prompt == "口头/视觉提示" else 0)
            st.subheader("计算结果")
            a,b,c = st.columns(3)
            a.metric("角点偏差", f"{deviation_mm:.1f} mm")
            b.metric("角点分（0–2）", f"{grade} 分")
            c.metric("用时", f"{secs:.1f} 秒")
            st.caption("示例分级：≤3 mm为2分，>3至8 mm为1分，>8 mm为0分。此阈值是教学原型规则，需本校评估校准，不代表标准化常模。")
            st.caption("用时示例分：≤60秒2分，>60至120秒1分，>120秒0分；实际教学可根据学生基线调整，调整后前后测需一致。")
            st.write(f"用时分 **{timing_score}/2** ｜ 独立性分 **{independence_score}/2** ｜ 演示合计 **{grade + timing_score + independence_score}/6**")
            if secs <= 0:
                st.warning("尚未录入有效完成时间，时间分暂计0分。")
            if st.button(f"保存{phase}结果", type="primary"):
                st.session_state.records[(student, phase)] = {
                    "匿名编号":student,"阶段":phase,"角点偏差_mm":round(deviation_mm,2),
                    "角点分":grade,"用时_s":round(secs,1),"用时分":timing_score,
                    "提示等级":prompt,"独立性分":independence_score,
                    "演示总分_6":grade+timing_score+independence_score,
                    "记录时间":datetime.now().isoformat(timespec="seconds")}
                st.success(f"已保存{phase}结果（仅保存在当前浏览器会话中，请及时下载）")

recs = [v for (sid, _),v in st.session_state.records.items() if sid == student]
if recs:
    st.divider()
    st.subheader("前后测结果")
    df = pd.DataFrame(recs).sort_values("阶段", key=lambda x:x.map({"前测":0,"后测":1}))
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.download_button("⬇ 下载测评记录 CSV", data=df.to_csv(index=False).encode("utf-8-sig"), file_name=f"origami_{student}_results.csv", mime="text/csv")
    if len(recs) == 2:
        both = df.set_index("阶段")
        delta = float(both.loc["后测","角点偏差_mm"])-float(both.loc["前测","角点偏差_mm"])
        st.metric("角点偏差变化（后测－前测）",f"{delta:+.2f} mm", delta_color="inverse")
        st.bar_chart(df.set_index("阶段")[["角点偏差_mm"]])
        st.caption("仅显示本次课堂内表现变化；一次前后测不等于长期康复效果证明。")

st.divider()
st.caption("数据说明：不连接数据库，不在代码中主动保存原始照片；云部署时照片仍会经过部署服务器处理。涉及真实学生图片时，请优先校内本地部署并取得必要授权。")
