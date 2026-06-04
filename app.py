import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="嘉義/桃園專屬農事氣象站", layout="wide")
st.title("🌾 嘉義農試所 ✖ 桃園農改場 專屬氣象觀測儀表板")

# 1. 側邊欄設定
st.sidebar.header("⚙️ 系統設定")
CWA_API_KEY = st.sidebar.text_input("請輸入氣象署 API 授權碼", type="password")

# 精確鎖定這兩個測站
STATIONS = {
    "嘉義農試所": {"id": "C0M530", "county": "嘉義市", "township": "東區"},
    "桃園農改場": {"id": "C0H960", "county": "桃園市", "township": "新屋區"}
}

selected_name = st.sidebar.selectbox("切換觀測地點", list(STATIONS.keys()))
current_station = STATIONS[selected_name]

if not CWA_API_KEY:
    st.warning("👈 請先於左側邊欄輸入您的中央氣象署 API 授權碼以載入即時數據。")
else:
    try:
        # ---- 2. 抓取即時觀測與過去降雨資料 (O-A0001-001) ----
        obs_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={CWA_API_KEY}&StationId={current_station['id']}"
        obs_res = requests.get(obs_url).json()
        
        station_data = obs_res['records']['Station'][0]
        weather_element = station_data['WeatherElement']
        
        # 讀取即時氣溫與當日累積雨量
        temp = weather_element['AirTemperature']
        today_rain = weather_element['Now']['Precipitation']
        
        # ---- 3. 畫面主要佈局渲染 ----
        st.header(f"📍 當前檢視：{selected_name} ({current_station['id']})")
        
        # 顯示即時數據資訊
        col1, col2 = st.columns(2)
        col1.metric(label="🌡️ 即時氣溫", value=f"{temp} °C")
        col2.metric(label="🌧️ 今日累積雨量", value=f"{today_rain} mm")
        
        st.markdown("---")
        
        # 建立兩個分頁區隔歷史雨量與預報
        tab1, tab2 = st.tabs(["📊 過去降雨紀錄", "🔮 未來天氣預報"])
        
        with tab1:
            st.subheader("📅 過去 24 小時內降雨趨勢")
            # 從 API 取得過去 24 小時逐時資料 (部分自動站提供)
            # 這裡建立動態欄位呈現
            past_time = weather_element.get('ObservationTime', datetime.now().strftime("%m/%d %H:%M"))
            st.info(f"最後觀測更新時間：{past_time}")
            
            # 建立圖表（此處將即時雨量與過去觀測進行動態生成）
            rain_df = pd.DataFrame({
                "觀測項目": ["今日累積雨量", "1小時累積", "24小時累積"],
                "雨量(mm)": [
                    float(today_rain) if today_rain else 0.0,
                    float(weather_element['text'].get('Hour', 0)) if 'text' in weather_element else 0.0,
                    float(weather_element['text'].get('Daily', 0)) if 'text' in weather_element else 0.0
                ]
            })
            fig = px.bar(rain_df, x="觀測項目", y="雨量(mm)", text_auto=True, color="觀測項目",
                         color_discrete_sequence=['#2e4f4f', '#4e7e7e', '#80b3b3'])
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.subheader("🔮 未來三日逐 3 小時天氣預報")
            # 鄉鎮預報 API 代碼：桃園市 F-D0047-005, 嘉義市 F-D0047-057
            api_code = "F-D0047-005" if current_station['county'] == "桃園市" else "F-D0047-057"
            
            forecast_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{api_code}?Authorization={CWA_API_KEY}&locationName={current_station['township']}"
            fore_res = requests.get(forecast_url).json()
            
            # 解析鄉鎮預報中的天氣現象與溫度
            elements = fore_res['records']['locations'][0]['location'][0]['weatherElement']
            
            time_slots = []
            weather_states = []
            temps = []
            
            # 抓取前 5 個時段的預報 (未來 15 小時)
            for t in elements[0]['time'][:5]:
                time_slots.append(t['startTime'][5:16].replace('-', '/')) # 格式化時間成 06/04 15:00
                weather_states.append(t['elementValue'][0]['value'])
                
            for t in elements[2]['time'][:5]: # 取得溫度
                temps.append(f"{t['elementValue'][0]['value']}°C")
                
            forecast_df = pd.DataFrame({
                "時間段": time_slots,
                "天氣狀態": weather_states,
                "預估氣溫": temps
            })
            
            st.table(forecast_df)
            
    except Exception as e:
        st.error(f"資料載入失敗，可能原因為 API 授權碼錯誤，或是測站目前維護中。")
        st.caption(f"錯誤訊息: {e}")
