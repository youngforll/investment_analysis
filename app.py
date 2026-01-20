import streamlit as st
import pandas as pd
import os
from datetime import datetime
from scipy import optimize
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# === 1. 页面设置 (紧凑风格) ===
st.set_page_config(page_title="国库仪表盘 V3", layout="wide")

# 自定义 CSS 缩小字号，让界面更紧凑
st.markdown("""
    <style>
    .block-container {padding-top: 3rem; padding-bottom: 1rem;}
    h3 {font-size: 28px !important;} 
    h4 {font-size: 16px !important;}
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h3 style='text-align: center;'>🚀 您的理财收益分析 (XIRR版)</h3>", unsafe_allow_html=True)

# 定义文件名
DATA_FILE = "investment_data.csv" 

# === 2. 核心算法 (XIRR) ===
def calculate_xirr(cash_flows, dates):
    if len(cash_flows) < 2 or sum(cash_flows) == 0: return 0
    min_date = min(dates)
    days = [(d - min_date).days for d in dates]
    def npv(rate):
        # 避免除零错误
        try:
            return sum([cf / ((1 + rate) ** (d / 365)) for cf, d in zip(cash_flows, days)])
        except:
            return 0
    try:
        return optimize.newton(npv, 0.1)
    except:
        return 0.0

# === 3. 初始化数据 ===
if not os.path.exists(DATA_FILE):
    # 结构：[记录时间, 产品名称, 类型(投入本金/当前持仓), 发生日期, 金额, 备注]
    df_init = pd.DataFrame(columns=["记录时间", "产品名称", "类型", "发生日期", "金额", "备注"])
    df_init.to_csv(DATA_FILE, index=False, encoding='utf_8_sig')

df = pd.read_csv(DATA_FILE)

# === 4. 页面布局 ===
col1, col2 = st.columns([1, 2.5]) # 调整比例，右边留更多空间给图

# --- 左侧：录入区 ---
with col1:
    st.markdown("#### 📝 录入单品持仓")
    with st.form("entry_form"):
        product_name = st.text_input("产品名称", placeholder="如：纳斯达克ETF")
        
        st.markdown("**👇 投入资金 (元)**")
        # 槽位 1
        c1, c2 = st.columns(2)
        date1 = c1.date_input("投入日期1", datetime.today())
        princ1 = c2.number_input("本金1", min_value=0.0, step=1000.0)
        
        # 按钮式展开更多槽位
        with st.expander("➕ 追加更多投入笔数"):
            st.caption("至多追加两笔")
            c3, c4 = st.columns(2)
            date2 = c3.date_input("投入日期2", datetime.today())
            princ2 = c4.number_input("本金2", min_value=0.0, step=1000.0)
            
            c5, c6 = st.columns(2)
            date3 = c5.date_input("投入日期3", datetime.today())
            princ3 = c6.number_input("本金3", min_value=0.0, step=1000.0)

        st.markdown("**👇 盘点现状**")
        check_date = st.date_input("盘点日期", datetime.today())
        current_value = st.number_input("🔴 当前总持仓金额（元）", min_value=0.0, step=1000.0)
        note = st.text_input("备注", placeholder="可选")
        
        if st.form_submit_button("💾 执行录入"):
            if product_name and current_value > 0:
                new_rows = []
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 写入逻辑：本金记为负，持仓记为正(临时计算用)
                if princ1 > 0: new_rows.append([now_str, product_name, "投入本金", date1, -princ1, note])
                if princ2 > 0: new_rows.append([now_str, product_name, "投入本金", date2, -princ2, note])
                if princ3 > 0: new_rows.append([now_str, product_name, "投入本金", date3, -princ3, note])
                
                # 记录持仓
                new_rows.append([now_str, product_name, "当前持仓", check_date, current_value, note])
                
                new_df = pd.DataFrame(new_rows, columns=df.columns)
                new_df.to_csv(DATA_FILE, mode='a', header=False, index=False, encoding='utf_8_sig')
                st.success("✅ 已归档")
                st.rerun()
            else:
                st.error("缺关键信息！")

# --- 右侧：双图表展示 ---
with col2:
    if not df.empty:
        df["发生日期"] = pd.to_datetime(df["发生日期"])
        
        # === 数据汇总计算 ===
        summary_list = []
        products = df["产品名称"].unique()
        
        for p in products:
            p_data = df[df["产品名称"] == p]
            # 取最新持仓
            latest_row = p_data[p_data["类型"] == "当前持仓"].sort_values("记录时间").tail(1)
            if latest_row.empty: continue
            
            curr_val = latest_row["金额"].values[0]
            check_day = latest_row["发生日期"].values[0]
            
            # 算本金
            invest_rows = p_data[p_data["类型"] == "投入本金"]
            total_principal = abs(invest_rows["金额"].sum())
            
            # 算 XIRR
            valid_invests = invest_rows[invest_rows["发生日期"] <= check_day]
            if not valid_invests.empty:
                dates_xirr = list(valid_invests["发生日期"]) + [check_day]
                amounts_xirr = list(valid_invests["金额"]) + [curr_val]
                xirr_val = calculate_xirr(amounts_xirr, dates_xirr)
            else:
                xirr_val = 0.0
            
            summary_list.append({
                "产品名称": p,
                "本金": total_principal,
                "绝对收益": curr_val - total_principal,
                "XIRR": xirr_val
            })
            
        summary_df = pd.DataFrame(summary_list)
        
        if not summary_df.empty:
            # === 图表 1: XIRR 纯享版 (Plotly) ===
            st.markdown("#### 各产品收益率")
            
            fig_xirr = go.Figure()
            fig_xirr.add_trace(go.Bar(
                x=summary_df['产品名称'],
                y=summary_df['XIRR'],
                text=(summary_df['XIRR'] * 100).round(2).astype(str) + '%',
                textposition='auto',
                marker_color='#8C1F28',
                name='XIRR'
            ))
            fig_xirr.update_layout(
                yaxis_tickformat='.1%',
                margin=dict(l=20, r=20, t=20, b=20),
                height=250
            )
            st.plotly_chart(fig_xirr, use_container_width=True)
            
            # === 图表 2: 双轴资金透视 (Plotly 强力版) ===
            st.markdown("#### 本金 vs 绝对收益")

            fig_dual = make_subplots(specs=[[{"secondary_y": True}]])

            # 柱子1：本金 (左轴)
            fig_dual.add_trace(
                go.Bar(
                    x=summary_df['产品名称'], 
                    y=summary_df['本金'], 
                    name="本金", 
                    marker_color='#22BABB',
                    offsetgroup=1 
                ),
                secondary_y=False
            )

            # 柱子2：收益 (右轴)
            fig_dual.add_trace(
                go.Bar(
                    x=summary_df['产品名称'], 
                    y=summary_df['绝对收益'], 
                    name="收益", 
                    marker_color='#FA7F08', 
                    offsetgroup=2
                ),
                secondary_y=True
            )

            fig_dual.update_layout(
                barmode='group', # 关键：分组模式
                height=350,
                margin=dict(l=20, r=20, t=30, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            fig_dual.update_yaxes(title_text="本金 (元)", secondary_y=False)
            fig_dual.update_yaxes(title_text="绝对收益 (元)", secondary_y=True)

            st.plotly_chart(fig_dual, use_container_width=True)
            
            # === 历史数据 ===
            with st.expander("📜 查看详细历史流水"):
                st.dataframe(df.sort_values("记录时间", ascending=False))        
    else:
        # 这个 else 是对应 if not df.empty 的
        st.info("👈 请在左侧录入第一笔数据")