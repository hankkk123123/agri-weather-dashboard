import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
import urllib3

# 關閉 SSL 警告訊息（畫面看起來比較乾淨）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="嘉義/桃園專屬農事氣象站", layout="wide")
st.title("🌾 嘉義農試所 ✖ 桃園農改場 專屬氣象觀測儀表板")

st.sidebar.header("⚙️ 系統設定")
CWA_API_KEY = st.sidebar.text_input("請輸入氣象署 API 授權碼", type="password")

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
        # ---- 1. 抓取即時觀測與過去降雨資料 (加上 verify=False) ----
        obs_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={CWA_API_KEY}&StationId={current_station['id']}"
        obs_res = requests.get(obs_url, verify=False).json()
        
        station_data = obs_res['records']['Station'][0]
        weather_element = station_data['WeatherElement']
        
        temp = weather_element.get('AirTemperature', 'N/A')
        today_rain = weather_element.get('Now', {}).get('Precipitation', 0.0)
        
        st.header(f"📍 當前檢視：{selected_name} ({current_station['id']})")
        
        col1, col2 = st.columns(2)
        col1.metric(label="🌡️ 即時氣溫", value=f"{temp} °C")
        col2.metric(label="🌧️ 今日累積雨量", value=f"{today_rain} mm")
        
        st.markdown("---")
        
        tab1, tab2 = st.tabs(["📊 過去降雨紀錄", "🔮 未來天氣預報"])
        
        with tab1:
            st.subheader("📅 當前累積降雨統計")
            past_time = station_data.get('ObsTime', datetime.now().strftime("%m/%d %H:%M"))
            st.info(f"最後觀測更新時間：{past_time}")
            
            # 安全防錯取值
            hour_rain = weather_element.get('Now', {}).get('Precipitation1H', 0.0)
            daily_rain = weather_element.get('Now', {}).get('Precipitation24H', 0.0)
            
            rain_df = pd.DataFrame({
                "觀測項目": ["今日累積雨量", "1小時累積", "24小時累積"],
                "雨量(mm)": [float(today_rain), float(hour_rain), float(daily_rain)]
            })
            fig = px.bar(rain_df, x="觀測項目", y="雨量(mm)", text_auto=True, color="觀測項目",
                         color_discrete_sequence=['#2e4f4f', '#4e7e7e', '#80b3b3'])
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.subheader("🔮 未來三日天氣預報")
            api_code = "F-D0047-005" if current_station['county'] == "桃園市" else "F-D0047-057"
            
            # 加上 verify=False
            forecast_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{api_code}?Authorization={CWA_API_KEY}&locationName={current_station['township']}"
            fore_res = requests.get(forecast_url, verify=False).json()
            
            elements = fore_res['records']['locations'][0]['location'][0]['weatherElement']
            
            # 尋找天氣現象 (Wx) 和 溫度 (T)
            wx_element = next(el for el in elements if el['elementName'] == 'Wx')
            t_element = next(el for el in elements if el['elementName'] == 'T')
            
            time_slots = []
            weather_states = []
            temps = []
            
            for t in wx_element['time'][:6]:
                time_slots.append(t['startTime'][5:16].replace('-', '/'))
                weather_states.append(t['elementValue'][0]['value'])
                
            for t in t_element['time'][:6]:
                temps.append(f"{t['elementValue'][0]['value']}°C")
                
            forecast_df = pd.DataFrame({
                "時間段": time_slots,
                "天氣狀態": weather_states,
                "預估氣溫": temps
            })
            
            st.table(forecast_df)
            
    except Exception as e:
        st.error(f"資料載入失敗，請確認 API 授權碼是否正確。")
        st.caption(f"錯誤詳細訊息: {e}")
