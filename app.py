import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import urllib3

# 關閉 SSL 警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與寬螢幕佈局
st.set_page_config(page_title="農事氣象觀測站", layout="wide")
st.title("🌾 嘉義農試所 ✖ 桃園農改場 專屬固定歷史區間觀測站")

# 側邊欄系統設定
st.sidebar.header("⚙️ 系統設定")
CWA_API_KEY = st.sidebar.text_input("請輸入氣象署 API 授權碼", type="password")

# 地區與 CODIS 精確測站編號配置 (C-B0024-001 歷史資料集需使用完全精確的 StationId)
STATIONS_CONFIG = {
    "嘉義農試所地區": {"id": "C0M530", "county": "嘉義市", "township": "西區"},
    "桃園農改場地區": {"id": "C0H960", "county": "桃園市", "township": "新屋區"}
}

selected_name = st.sidebar.selectbox("切換觀測地點", list(STATIONS_CONFIG.keys()))
config = STATIONS_CONFIG[selected_name]

# 💡 方案 A 核心核心功能：供使用者自由選擇月份
current_year = datetime.now().year
current_month = datetime.now().month

# 產生最近幾個月的選項供挑選
month_options = []
for m in range(current_month, 0, -1):
    month_options.append(f"{current_year}-{m:02d}")
# 額外加上去年年底兩個月做為備用
month_options.extend([f"{current_year-1}-12", f"{current_year-1}-11"])

selected_month = st.sidebar.selectbox("選擇歷史查詢月份", month_options)

if not CWA_API_KEY:
    st.warning("👈 請先於左側邊欄輸入您的中央氣象署 API 授權碼以載入數據。")
else:
    try:
        # ==================== 1. 撈取【當前即時觀測資料】 ====================
        obs_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={CWA_API_KEY}&StationId={config['id']}"
        obs_res = requests.get(obs_url, verify=False).json()
        
        # 讀取當下天氣狀況與今日累積降水量
        today_rain = 0.0
        weather_status = "多雲/晴朗"
        
        if 'records' in obs_res and 'Station' in obs_res['records'] and len(obs_res['records']['Station']) > 0:
            weather_element = obs_res['records']['Station'][0]['WeatherElement']
            weather_status = weather_element.get('Weather', '晴朗/多雲')
            today_rain = weather_element.get('Now', {}).get('Precipitation', 0.0)
            today_rain = 0.0 if today_rain == -99 or today_rain is None else today_rain

        # ---------------- 區塊一：當前即時現況 ----------------
        st.header(f"📍 當前檢視：{selected_name} (測站ID: {config['id']})")
        
        col1, col2 = st.columns(2)
        col1.metric(label="🌤️ 當下天氣狀況", value=str(weather_status))
        col2.metric(label="🌧️ 當下今日累積降水量", value=f"{today_rain} mm")
        
        st.markdown("### ---")
        
        # ==================== 2. 撈取【CODIS 歷史月觀測資料並進行固定 5 天分組】 ====================
        st.subheader(f"📅 歷史月份資料： {selected_month} (每 5 天固定區間加總報表)")
        
        # 呼叫 C-B0024-001 歷史氣候日統計 API
        hist_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/C-B0024-001?Authorization={CWA_API_KEY}&StationId={config['id']}&Month={selected_month.split('-')[1]}"
        hist_res = requests.get(hist_url, verify=False).json()
        
        if 'records' in hist_res and 'ClimateState' in hist_res['records'] and len(hist_res['records']['ClimateState']) > 0:
            daily_data = hist_res['records']['ClimateState'][0]['TestData']
            
            raw_dates = []
            raw_precps = []
            raw_hours = []
            
            for row in daily_data:
                # 取得日期（格式通常為數字 1, 2, 3 代表當月號數）
                day_num = int(row.get('Day', 0))
                if day_num == 0:
                    continue
                    
                raw_dates.append(day_num)
                
                # 撈取 Precp 降水量
                p_val = row.get('Precipitation', 0.0)
                p_val = 0.0 if p_val == -99 or p_val is None or str(p_val).startswith('-') else float(p_val)
                raw_precps.append(p_val)
                
                # 撈取 PrecpHour 降水時數
                ph_val = row.get('PrecipitationDuration', 0.0)
                ph_val = 0.0 if ph_val == -99 or ph_val is None or str(ph_val).startswith('-') else float(ph_val)
                raw_hours.append(ph_val)
            
            # 建立 DataFrame 進行區間切分
            df = pd.DataFrame({
                "日": raw_dates,
                "Precp": raw_precps,
                "PrecpHour": raw_hours
            })
            
            # 💡 核心邏輯：定義每 5 天一期的固定區間
            def get_interval(day):
                if 1 <= day <= 5: return "01 ~ 05 號"
                elif 6 <= day <= 10: return "06 ~ 10 號"
                elif 11 <= day <= 15: return "11 ~ 15 號"
                elif 16 <= day <= 20: return "16 ~ 20 號"
                elif 21 <= day <= 25: return "21 ~ 25 號"
                else: return "26 號 ~ 月底"
                
            df['日期區間'] = df['日'].apply(get_interval)
            
            # 依區間進行分組加總 (Groupby Sum)
            summary_df = df.groupby('日期區間', sort=False)[['Precp', 'PrecpHour']].sum().reset_index()
            
            # 修改欄位名稱對標您的格式
            summary_df.columns = ["固定日期區間", "累積降水量 Precp (mm)", "累積降水時數 PrecpHour (h)"]
            
            # 在網頁印出乾淨漂亮的固定報表
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
        else:
            st.warning(f"氣象署歷史氣候資料庫中，暫時無該選定月份 ({selected_month}) 的日觀測存檔。")

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
            
    except Exception as e:
        st.error(f"系統執行時發生未預期錯誤，請檢查 API 授權碼。")
        st.caption(f"錯誤詳細訊息: {e}")
