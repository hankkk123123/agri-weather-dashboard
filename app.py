import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
import urllib3

# 1. 關閉 SSL 警告訊息（讓 Streamlit 雲端主機畫面保持乾淨）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與寬螢幕佈局
st.set_page_config(page_title="嘉義/桃園專屬農事氣象站", layout="wide")
st.title("🌾 嘉義農試所 ✖ 桃園農改場 專屬氣象觀測儀表板")

# 2. 側邊欄系統設定
st.sidebar.header("⚙️ 系統設定")
CWA_API_KEY = st.sidebar.text_input("請輸入氣象署 API 授權碼", type="password")

# 核心站點配置（嘉義使用「嘉義」主站擴大搜尋，桃園使用「桃園農改」精確搜尋）
STATIONS_CONFIG = {
    "嘉義農試所": {"keyword": "嘉義", "county": "嘉義市", "township": "東區"},
    "桃園農改場": {"keyword": "桃園農改", "county": "桃園市", "township": "新屋區"}
}

selected_name = st.sidebar.selectbox("切換觀測地點", list(STATIONS_CONFIG.keys()))
config = STATIONS_CONFIG[selected_name]

# 3. 主程式邏輯
if not CWA_API_KEY:
    st.warning("👈 請先於左側邊欄輸入您的中央氣象署 API 授權碼以載入即時數據。")
else:
    try:
        # ---- 步驟 A. 抓取全台即時觀測資料 (O-A0001-001) ----
        # 加上 verify=False 跳過 SSL 憑證驗證
        obs_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={CWA_API_KEY}"
        obs_res = requests.get(obs_url, verify=False).json()
        
        all_stations = obs_res['records']['Station']
        
        # 在清單中動態尋找名稱符合關鍵字的測站
        target_station = None
        for station in all_stations:
            if config['keyword'] in station['StationName']:
                target_station = station
                break
                
        if target_station is None:
            st.error(f"❌ 在氣象署資料集中找不到名稱包含「{config['keyword']}」的測站。")
        else:
            weather_element = target_station['WeatherElement']
            station_id = target_station['StationId']
            
            # 安全讀取即時氣溫與當日累積雨量
            temp = weather_element.get('AirTemperature', 'N/A')
            today_rain = weather_element.get('Now', {}).get('Precipitation', 0.0)
            
            # 處理氣象局無降雨或儀器異常值 (-99 代表未降雨或故障)
            if today_rain == -99 or today_rain is None:
                today_rain = 0.0
            
            # 渲染標頭與即時大數據卡片
            st.header(f"📍 當前檢視：{selected_name} (測站真實名稱：{target_station['StationName']} / ID: {station_id})")
            
            col1, col2 = st.columns(2)
            col1.metric(label="🌡️ 即時氣溫", value=f"{temp} °C")
            col2.metric(label="🌧️ 今日累積雨量", value=f"{today_rain} mm")
            
            st.markdown("---")
            
            # 建立分頁
            tab1, tab2 = st.tabs(["📊 過去降雨紀錄", "🔮 未來天氣預報"])
            
            with tab1:
                st.subheader("📅 當前累積降雨統計")
                past_time = target_station.get('ObsTime', datetime.now().strftime("%m/%d %H:%M"))
                st.info(f"最後觀測更新時間：{past_time}")
                
                # 安全獲取 1小時與24小時 累積雨量
                hour_rain = weather_element.get('Now', {}).get('Precipitation1H', 0.0)
                daily_rain = weather_element.get('Now', {}).get('Precipitation24H', 0.0)
                
                # 濾除異常值
                hour_rain = 0.0 if hour_rain == -99 else hour_rain
                daily_rain = 0.0 if daily_rain == -99 else daily_rain
                
                # 建立降雨 DataFrame 並畫出 Plotly 長條圖
                rain_df = pd.DataFrame({
                    "觀測項目": ["今日累積雨量", "1小時累積", "24小時累積"],
                    "雨量(mm)": [float(today_rain), float(hour_rain), float(daily_rain)]
                })
                fig = px.bar(rain_df, x="觀測項目", y="雨量(mm)", text_auto=True, color="觀測項目",
                             color_discrete_sequence=['#2e4f4f', '#4e7e7e', '#80b3b3'])
                st.plotly_chart(fig, use_container_width=True)
                
            with tab2:
                st.subheader("🔮 未來三日鄉鎮逐日天氣預報")
                # 判斷對應縣市預報代碼：桃園市 F-D0047-005, 嘉義市 F-D0047-057
                api_code = "F-D0047-005" if config['county'] == "桃園市" else "F-D0047-057"
                
                # ---- 步驟 B. 抓取未來鄉鎮預報資料 ----
                forecast_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{api_code}?Authorization={CWA_API_KEY}&locationName={config['township']}"
                fore_res = requests.get(forecast_url, verify=False).json()
                
                elements = fore_res['records']['locations'][0]['location'][0]['weatherElement']
                
                # 尋找天氣現象 (Wx) 和 溫度 (T) 欄位
                wx_element = next(el for el in elements if el['elementName'] == 'Wx')
                t_element = next(el for el in elements if el['elementName'] == 'T')
                
                time_slots = []
                weather_states = []
                temps = []
                
                # 抓取前 6 個時段的預報資料
                for t in wx_element['time'][:6]:
                    time_slots.append(t['startTime'][5:16].replace('-', '/'))
                    weather_states.append(t['elementValue'][0]['value'])
                    
                for t in t_element['time'][:6]:
                    temps.append(f"{t['elementValue'][0]['value']}°C")
                    
                # 建立預報表格
                forecast_df = pd.DataFrame({
                    "時間段": time_slots,
                    "天氣狀態": weather_states,
                    "預估氣溫": temps
                })
                
                st.table(forecast_df)
                
    except Exception as e:
        st.error(f"系統執行時發生未預期錯誤，請檢查 API 授權碼或網路連線。")
        st.caption(f"錯誤詳細訊息: {e}")
