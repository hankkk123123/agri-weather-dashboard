import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
import urllib3

# 關閉 SSL 警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與寬螢幕佈局
st.set_page_config(page_title="嘉義/桃園專屬農事氣象站", layout="wide")
st.title("🌾 嘉義農試所 ✖ 桃園農改場 專屬氣象觀測儀表板")

# 側邊欄系統設定
st.sidebar.header("⚙️ 系統設定")
CWA_API_KEY = st.sidebar.text_input("請輸入氣象署 API 授權碼", type="password")

# 地區與行政區精確設定
STATIONS_CONFIG = {
    "嘉義農試所地區": {"id": "C0M530", "keyword": "嘉義", "county": "嘉義市", "township": "西區"},
    "桃園農改場地區": {"id": "C0H960", "keyword": "桃園農改", "county": "桃園市", "township": "新屋區"}
}

selected_name = st.sidebar.selectbox("切換觀測地點", list(STATIONS_CONFIG.keys()))
config = STATIONS_CONFIG[selected_name]

if not CWA_API_KEY:
    st.warning("👈 請先於左側邊欄輸入您的中央氣象署 API 授權碼以載入即時數據。")
else:
    try:
        # ---- 步驟 1. 抓取即時觀測資料 (O-A0001-001) ----
        obs_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={CWA_API_KEY}"
        obs_res = requests.get(obs_url, verify=False).json()
        all_stations = obs_res['records']['Station']
        
        target_station = None
        for station in all_stations:
            if config['keyword'] in station['StationName']:
                target_station = station
                break
        
        if target_station is None:
            for station in all_stations:
                if station['StationId'] == config['id']:
                    target_station = station
                    break

        if target_station:
            weather_element = target_station['WeatherElement']
            temp = weather_element.get('AirTemperature', 'N/A')
            
            now_data = weather_element.get('Now', {})
            today_rain = now_data.get('Precipitation', 0.0)
            if today_rain == -99 or today_rain is None:
                today_rain = 0.0
                
            hour_rain = now_data.get('Precipitation1H', 0.0)
            daily_rain = now_data.get('Precipitation24H', 0.0)
            hour_rain = 0.0 if hour_rain == -99 else hour_rain
            daily_rain = 0.0 if daily_rain == -99 else daily_rain

            # 渲染大數字卡片
            st.header(f"📍 當前檢視：{selected_name} (測站: {target_station['StationName']})")
            
            col1, col2 = st.columns(2)
            col1.metric(label="🌡️ 即時氣溫", value=f"{temp} °C")
            col2.metric(label="🌧️ 今日累積雨量", value=f"{today_rain} mm")
            
            st.markdown("---")
            
            # 分頁顯示
            tab1, tab2 = st.tabs(["📊 過去降雨紀錄", "🔮 未來天氣預報"])
            
            with tab1:
                st.subheader("📅 當前累積降雨統計")
                obs_time = target_station.get('ObsTime', datetime.now().strftime("%m/%d %H:%M"))
                st.info(f"最後觀測更新時間：{obs_time}")
                
                rain_df = pd.DataFrame({
                    "觀測項目": ["今日累積雨量", "1小時累積", "24小時累積"],
                    "雨量(mm)": [float(today_rain), float(hour_rain), float(daily_rain)]
                })
                fig = px.bar(rain_df, x="觀測項目", y="雨量(mm)", text_auto=True, color="觀測項目",
                             color_discrete_sequence=['#2e4f4f', '#4e7e7e', '#80b3b3'])
                st.plotly_chart(fig, use_container_width=True)
                
            with tab2:
                st.subheader(f"🔮 未來三日 {config['township']} 天氣預報")
                
                # ---- 步驟 2. 抓取預報資料 ----
                api_code = "F-D0047-005" if config['county'] == "桃園市" else "F-D0047-057"
                forecast_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{api_code}?Authorization={CWA_API_KEY}&locationName={config['township']}"
                fore_res = requests.get(forecast_url, verify=False).json()
                
                try:
                    # 尋找匹配的鄉鎮行政區預報數據
                    location_data = fore_res['records']['locations'][0]['location'][0]
                    elements = location_data['weatherElement']
                    
                    wx_element = None
                    t_element = None
                    
                    # 💡 核心修正：使用安全循環搜尋，避免固定索引跳錯
                    for el in elements:
                        if el['elementName'] == 'Wx':
                            wx_element = el
                        elif el['elementName'] == 'T':
                            t_element = el
                    
                    if wx_element and t_element:
                        time_slots = []
                        weather_states = []
                        temps = []
                        
                        # 擷取前 6 個預報時段
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
                    else:
                        st.warning("氣象署回傳的預報資料中缺少天氣現象(Wx)或溫度(T)欄位。")
                except Exception as parse_error:
                    st.warning("🔍 目前該地區氣象預報資料格式解析異常，但觀測數據不受影響。")
                    st.caption(f"解析詳細訊息: {parse_error}")
        else:
            st.error(f"❌ 無法在氣象署找到該地區的觀測站資料。")
            
    except Exception as e:
        st.error(f"系統執行時發生未預期錯誤，請檢查 API 授權碼。")
        st.caption(f"錯誤詳細訊息: {e}")
