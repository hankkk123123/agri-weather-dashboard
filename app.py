import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import urllib3

# 關閉 SSL 警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與寬螢幕佈局
st.set_page_config(page_title="農事氣象觀測站", layout="wide")
st.title("🌾 嘉義農試所 ✖ 桃園農改場 專屬氣象觀測站")

# 側邊欄系統設定
st.sidebar.header("⚙️ 系統設定")
CWA_API_KEY = st.sidebar.text_input("請輸入氣象署 API 授權碼", type="password")

# 地區行政區與 CODIS 精確測站編號配置
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
        # ==================== 1. 撈取【當前即時觀測資料】 ====================
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
            
            # 讀取當下天氣狀況與今日累積降水量
            weather_status = weather_element.get('Weather', '晴朗/多雲 (依測站回傳)')
            today_rain = weather_element.get('Now', {}).get('Precipitation', 0.0)
            today_rain = 0.0 if today_rain == -99 or today_rain is None else today_rain

            # ---------------- 區塊一：當前即時現況 ----------------
            st.header(f"📍 當前檢視：{selected_name} (測站: {target_station['StationName']})")
            
            col1, col2 = st.columns(2)
            col1.metric(label="🌤️ 當下天氣狀況", value=str(weather_status))
            col2.metric(label="🌧️ 當下今日累積降水量", value=f"{today_rain} mm")
            
            st.markdown("### ---")
            
            # ==================== 2. 撈取【過去 5 天日降水紀錄】 ====================
            st.subheader("📅 過去 5 天日降水報表")
            
            history_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0002-001?Authorization={CWA_API_KEY}&StationId={config['id']}"
            history_res = requests.get(history_url, verify=False).json()
            hist_stations = history_res['records']['Station']
            
            if hist_stations:
                daily_records = hist_stations[0].get('StationDailyObs', {}).get('CalendarDay', [])
                
                dates = []
                precps = []      # Precp
                precp_hours = [] # PrecpHour
                
                for day in daily_records:
                    dates.append(day.get('Date', 'N/A'))
                    elements = day.get('WeatherElement', {})
                    
                    p_val = elements.get('Precipitation', 0.0)
                    p_val = 0.0 if p_val == -99 or p_val is None else float(p_val)
                    
                    ph_val = elements.get('PrecipitationDuration', 0.0)
                    ph_val = 0.0 if ph_val == -99 or ph_val is None else float(ph_val)
                    
                    precps.append(p_val)
                    precp_hours.append(ph_val)
                
                # 建立純文字數據表格（對標 CODIS 命名）
                codis_df = pd.DataFrame({
                    "觀測日期 (Date)": dates,
                    "降水量 Precp (mm)": precps,
                    "降水時數 PrecpHour (h)": precp_hours
                })
                # 最新日期排在最上面
                codis_df = codis_df.iloc[::-1].reset_index(drop=True)
                st.dataframe(codis_df, use_container_width=True, hide_index=True)
            else:
                st.warning("暫時無法取得 5 天日觀測降水資料。")

            st.markdown("### ---")

            # ==================== 3. 撈取【未來 3 天天氣預報】 ====================
            st.subheader(f"🔮 未來 3 天 {config['township']} 天氣狀況預報")
            
            api_code = "F-D0047-005" if config['county'] == "桃園市" else "F-D0047-057"
            forecast_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{api_code}?Authorization={CWA_API_KEY}&locationName={config['township']}"
            fore_res = requests.get(forecast_url, verify=False).json()
            
            try:
                location_data = fore_res['records']['locations'][0]['location'][0]
                elements = location_data['weatherElement']
                
                wx_element = next((el for el in elements if el['elementName'] == 'Wx'), None)
                
                if wx_element:
                    time_slots = []
                    weather_states = []
                    
                    # 抓取未來 3 天（每 12 小時或白天/晚上為一期的前 6 個時段）
                    for t in wx_element['time'][:6]:
                        time_slots.append(t['startTime'][5:16].replace('-', '/'))
                        weather_states.append(t['elementValue'][0]['value'])
                        
                    forecast_df = pd.DataFrame({
                        "預報時間段": time_slots,
                        "預估天氣狀態": weather_states
                    })
                    st.table(forecast_df)
                else:
                    st.warning("未取得未來天氣狀態(Wx)欄位。")
            except Exception:
                st.warning("🔍 目前該地區氣象預報資料暫時無法解析。")
        else:
            st.error(f"❌ 無法在氣象署找到該地區的觀測站資料。")
            
    except Exception as e:
        st.error(f"系統執行時發生未預期錯誤，請確認 API 授權碼。")
        st.caption(f"錯誤詳細訊息: {e}")
