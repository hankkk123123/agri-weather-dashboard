import streamlit as st
import requests
import pandas as pd
import plotly.express as px # 用來畫漂亮的降雨量圖表

st.set_page_config(page_title="農事氣象觀測儀表板", layout="wide")
st.title("🌾 嘉義農試所 & 桃園農改場 氣象觀測與預報")

# 這裡填入你的氣象署 API Key
CWA_API_KEY = "YOUR_CWA_API_KEY"

# 定義我們要抓取的農業測站 ID (此處為示意 ID，實際 ID 需查氣象署農業站代碼)
STATIONS = {
    "嘉義農試所": "C0M530", 
    "桃園農改場": "C0H960"
}

# 側邊欄供使用者選擇測站
selected_station = st.sidebar.selectbox("選擇要檢視的農事單位", list(STATIONS.keys()))

# 畫面上方切換分頁
tab1, tab2 = st.tabs(["📊 過去一週累積降雨", "🔮 未來一週天氣預報"])

with tab1:
    st.header(f"📅 {selected_station} - 過去 7 天降雨統計")
    
    # 呼叫氣象署歷史觀測資料 API (假定取得過去 7 天 Data)
    # 這裡可用 requests 抓取 API 並轉成 Pandas DataFrame
    # 以下用模擬數據示意圖表效果
    rain_data = pd.DataFrame({
        "日期": ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"],
        "降雨量(mm)": [0.0, 12.5, 4.5, 0.0, 28.0, 0.0, 1.5]
    })
    
    # 使用 Plotly 畫出精美的長條圖
    fig = px.bar(rain_data, x="日期", y="降雨量(mm)", text_auto=True, title="每日降雨量")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header(f"🔮 {selected_station} - 未來天氣預報")
    
    # 呼叫氣象署鄉鎮預報 API 
    # 呈現未來幾天的天氣狀態、最高溫、最低溫、降雨機率
    col1, col2, col3 = st.columns(3)
    col1.metric(label="明天天氣", value="多雲午後短暫雷陣雨", delta="降雨機率 60%")
    col2.metric(label="最高氣溫", value="32 °C")
    col3.metric(label="最低氣溫", value="25 °C")
    
    # 可以用表格呈現未來一週的預報
    st.subheader("一週逐日預報詳細資料")
    # st.dataframe(forecast_df) # 放入解析後的預報表格
