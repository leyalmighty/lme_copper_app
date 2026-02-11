import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
from engine import ForwardCurveEngine
import time

st.set_page_config(page_title="LME Copper Pro", layout="wide")

# Xóa Cache cũ để đảm bảo nhận code mới từ engine.py
st.cache_resource.clear()

@st.cache_resource
def get_engine():
    return ForwardCurveEngine('LME_copper.xlsx')

try:
    engine = get_engine()
except Exception as e:
    st.error(f"Lỗi khởi tạo Engine: {e}")
    st.stop()

# Xử lý Index chuẩn
dt_idx = pd.to_datetime(engine.df.index)
all_dates = dt_idx.strftime('%Y-%m-%d').tolist()

if 'current_idx' not in st.session_state:
    st.session_state.current_idx = len(all_dates) - 1
if 'playing' not in st.session_state:
    st.session_state.playing = False

st.title("📊 LME Copper Forward Curve Professional")
st.divider()

tab1, tab2, tab3 = st.tabs(["📈 Market Dynamics", "🔗 Correlation", "🧬 PCA Strategy"])

with tab1:
    # --- 1. TIME SERIES ---
    st.subheader("1. Diễn biến lịch sử")
    selected_tenors = st.multiselect("Kỳ hạn so sánh:", engine.tenors, default=['CASH', '3M', '15M'], key="ms_main")
    if selected_tenors:
        st.plotly_chart(px.line(engine.df[selected_tenors], height=350), use_container_width=True, key="ts_main")

    st.write("---")

    # --- 2. THỐNG KÊ & PHÂN PHỐI ---
    st.subheader("2. Thống kê & Phân phối")
    col_sel, _ = st.columns([1, 2])
    with col_sel:
        sel_tenor = st.selectbox("Chọn kỳ hạn phân tích:", engine.tenors, key="sb_stats")
    
    stats = engine.get_basic_stats(sel_tenor)
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Giá TB", f"{stats.get('Mean', 0):.1f}")
    m2.metric("Vol (Ann)", f"{stats.get('Annual Vol', 0):.2%}")
    m3.metric("Skewness", f"{stats.get('Skewness', 0):.2f}")
    m4.metric("Kurtosis", f"{stats.get('Kurtosis', 0):.2f}")

    # --- FIX LỖI KEYERROR Ở ĐÂY ---
    # Sử dụng .get() để lấy dữ liệu an toàn, nếu không có trả về Series rỗng
    returns_data = stats.get('Returns', pd.Series(dtype=float))
    
    if not returns_data.empty:
        # Chuyển sang DataFrame để vẽ Histogram dễ hơn
        df_hist = pd.DataFrame({'Ret (%)': returns_data * 100})
        fig_dist = px.histogram(
            df_hist, x='Ret (%)', marginal="box", nbins=50,
            title=f"Phân phối lợi nhuận ngày (%) - {sel_tenor}",
            color_discrete_sequence=['#2E86C1'], opacity=0.7
        )
        st.plotly_chart(fig_dist, use_container_width=True, key="dist_chart")
    else:
        st.info("Chưa đủ dữ liệu để vẽ biểu đồ phân phối.")

    st.divider()

    # --- 3. BẢNG DỮ LIỆU ---
    st.subheader("3. Bảng dữ liệu chi tiết")
    with st.expander("Mở rộng & Xuất Excel"):
        try:
            st.download_button("📥 Tải Excel", engine.to_excel(), "LME_Data.xlsx", key="dl_excel")
        except:
            st.warning("Cần cài đặt: pip install xlsxwriter")
        st.dataframe(engine.df, use_container_width=True)

    st.divider()

    # --- 4. ANIMATION ---
    st.subheader("4. Curve Animation")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.session_state.current_idx = st.select_slider(
            "Timeline", options=range(len(all_dates)), 
            value=st.session_state.current_idx,
            format_func=lambda x: all_dates[x], key="sl_anim"
        )
    with c2:
        speed = st.slider("Tốc độ (s)", 0.05, 0.5, 0.1, key="spd_anim")
    with c3:
        st.write("###")
        if st.button("▶️ Play / Stop", key="btn_anim"):
            st.session_state.playing = not st.session_state.playing

    plot_spot = st.empty()
    def get_curve(idx):
        d = engine.df.iloc[idx]
        spread = float(d['CASH'] - d['3M'])
        state = "BACKWARDATION" if spread > 0 else "CONTANGO"
        color = "red" if spread > 0 else "green"
        fig = px.line(x=engine.tenors, y=d, markers=True, title=f"{all_dates[idx]} | <span style='color:{color}'>{state}</span>")
        fig.update_layout(yaxis=dict(range=[d.min()*0.995, d.max()*1.005]), height=450)
        return fig

    if st.session_state.playing:
        for i in range(st.session_state.current_idx, len(all_dates)):
            if not st.session_state.playing: break
            st.session_state.current_idx = i
            plot_spot.plotly_chart(get_curve(i), use_container_width=True, key=f"fr_{i}")
            time.sleep(speed)
        st.session_state.playing = False
        st.rerun()
    else:
        plot_spot.plotly_chart(get_curve(st.session_state.current_idx), use_container_width=True, key="static")

with tab2:
    st.header("Correlation Matrix")
    corr = engine.get_correlation_matrix()
    if not corr.empty:
        st.plotly_chart(px.imshow(corr, text_auto=".2f", height=700, color_continuous_scale='RdBu_r'), key="corr_mat")
    else:
        st.warning("Dữ liệu không đủ để tính tương quan.")

with tab3:
    st.header("PCA Analysis")
    evr, comp = engine.run_pca_analysis()
    if not comp.empty:
        st.write(f"PC1: {evr[0]:.2%} | PC2: {evr[1]:.2%}")
        st.plotly_chart(px.line(comp, markers=True), use_container_width=True, key="pca_ln")
    else:
        st.warning("Không thể chạy PCA do dữ liệu chứa quá nhiều lỗi hoặc NaN.")