import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import urllib3

# 關閉 SSL 警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與寬螢幕佈局
st.set_page_config(page_title="農事氣象觀測站", layout="wide")
st.title("🌾 全自動農事觀測站 (即時/預報：API ✖ 歷史統計：CODIS單項月報表連線)")

# 側邊欄系統設定
st.sidebar.header("⚙️ 系統設定")
CWA_API_KEY = st.sidebar.text_input("請輸入氣象署 API 授權碼", type="password")

# 核心設定
STATIONS_CONFIG = {
    "嘉義農試所地區": {"id": "G2L020", "keyword": "農試嘉義分所", "county": "嘉義市", "township": "東區"},
    "桃園農改場地區": {"id": "72C440", "keyword": "桃園農改場", "county": "桃園市", "township": "新屋區"}
}

selected_name = st.sidebar.selectbox("切換觀測地點", list(STATIONS_CONFIG.keys()))
config = STATIONS_CONFIG[selected_name]

# 供使用者自由選擇要爬取的歷史月份
current_year = datetime.now().year
current_month = datetime.now().month
month_options = [f"{current_year}-{m:02d}" for m in range(current_month, 0, -1)]
selected_month = st.sidebar.selectbox("選擇 CODIS 讀取月份", month_options)

# ==================== 🛠️ 針對「單項逐時月報表」網頁的客製化解構函數 ====================
def parse_codis_single_element(station_id, year_month, element_id):
    """
    直連 CODIS 單項逐時月報表網頁，並抽取最右側的「總和」欄位
    element_id: 61 代表降水量 (mm), 65 代表降水時數 (h) (依氣象署內部分類代碼)
    """
    year, month = year_month.split('-')
    
    # 精確對接單項逐時月報表的實時查詢 URL
    url = f"https://codis.cwa.gov.tw/HistoryDataQuery/MonthDataQuery.action?command=viewMain&station={station_id}&datepicker={year}-{month}&element={element_id}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        tables = pd.read_html(response.text)
        
        target_table = None
        for table in tables:
            # 單項逐時矩陣橫軸固定有 1~24 小時 + 總和，行數必然大於 24 欄
            if table.shape[1] >= 25:
                target_table = table
                break
                
        if target_table is None:
            return {}
            
        daily_totals = {}
        for idx, row in target_table.iterrows():
            try:
                # 第一欄為日/時 (01, 02, 03...)
                day_str = str(row.iloc[0]).strip()
                if not day_str.isdigit():
                    continue
                day_num = int(day_str)
                
                # 最右側最後一欄 (Index -1) 固定為「總和」
                total_val = str(row.iloc[-1]).upper().strip()
                
                # 清洗異常值 (T 代表微量, -- 代表無降雨或未到該日期)
                if 'T' in total_val or 'X' in total_val or 'V' in total_val or '--' in total_val or not total_val:
                    clean_num = 0.0
                else:
                    try:
                        clean_num = float(total_val)
                    except:
                        clean_num = 0.0
                        
                daily_totals[day_num] = clean_num
            except:
                continue
        return daily_totals
    except:
        return {}

# ==================================================================================

if not CWA_API_KEY:
    st.warning("👈 請先於左側邊欄輸入您的中央氣象署 API 授權碼以載入即時與預報數據。")
else:
    try:
        # ==================== 1. 【當前即時觀測資料 - API】 ====================
        obs_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={CWA_API_KEY}&StationId={config['id']}"
        obs_res = requests.get(obs_url, verify=False).json()
        
        today_rain = 0.0
        weather_status = "多雲/晴朗"
        station_real_name = config['keyword']
        
        if 'records' in obs_res and 'Station' in obs_res['records'] and len(obs_res['records']['Station']) > 0:
            station_node = obs_res['records']['Station'][0]
            station_real_name = station_node.get('StationName', config['keyword'])
            weather_element = station_node.get('WeatherElement', {})
            weather_status = weather_element.get('Weather', '晴朗/多雲')
            today_rain = weather_element.get('Now', {}).get('Precipitation', 0.0)
            today_rain = 0.0 if today_rain == -99 or today_rain is None else today_rain

        st.header(f"📍 當前檢視：{selected_name} (測站官方名稱: {station_real_name} / ID: {config['id']})")
        
        col1, col2 = st.columns(2)
        col1.metric(label="🌤️ 當下天氣狀況 (API)", value=str(weather_status))
        col2.metric(label="🌧️ 當下今日累積降水量 (API)", value=f"{today_rain} mm")
        
        st.markdown("### ---")
        
        # ==================== 2. 【歷史固定區間資料 - 雙頁 CODIS 交叉整合爬蟲】 ====================
        st.subheader(f"📅 CODIS 數據統計：{selected_month} (每 5 天固定區間加總)")
        
        with st.spinner("⏳ 正在跨頁面提取 CODIS 降水量與降水時數總和數據，請稍候..."):
            # 61 代表降水量 (Precp), 65 代表降水時數 (PrecpHour)
            precp_dict = parse_codis_single_element(config['id'], selected_month, "61")
            hour_dict = parse_codis_single_element(config['id'], selected_month, "65")
            
            if precp_dict:
                # 合併兩支單項報表的日總和資料
                combined_rows = []
                for day in range(1, 32):
                    if day in precp_dict:
                        p_val = precp_dict.get(day, 0.0)
                        h_val = hour_dict.get(day, 0.0) # 如果時數頁面沒資料則補 0.0
                        combined_rows.append({"日": day, "Precp": p_val, "PrecpHour": h_val})
                
                df_combined = pd.DataFrame(combined_rows)
                
                # 定義固定 5 天分組邏輯
                def get_interval(day):
                    if 1 <= day <= 5: return "01 ~ 05 號"
                    elif 6 <= day <= 10: return "06 ~ 10 號"
                    elif 11 <= day <= 15: return "11 ~ 15 號"
                    elif 16 <= day <= 20: return "16 ~ 20 號"
                    elif 21 <= day <= 25: return "21 ~ 25 號"
                    else: return "26 號 ~ 月底"
                    
                df_combined['固定日期區間'] = df_combined['日'].apply(get_interval)
                
                # 執行固定區間加總統計
                summary_df = df_combined.groupby('固定日期區間', sort=True)[['Precp', 'PrecpHour']].sum().reset_index()
                summary_df.columns = ["固定日期區間", "區間累積降水量 Precp (mm)", "區間累積降水時數 PrecpHour (h)"]
                
                summary_df["區間累積降水量 Precp (mm)"] = summary_df["區間累積降水量 Precp (mm)"].round(1)
                summary_df["區間累積降水時數 PrecpHour (h)"] = summary_df["區間累積降水時數 PrecpHour (h)"].round(1)
                
                st.dataframe(summary_df, use_container_width=True, hide_index=True)
            else:
                st.warning(f"💡 新版 CODIS 目前尚未完全上架該月份 ({selected_month}) 的單項逐時完整報表。")
                st.info("💡 建議您可以將左側選單的月份切換到上一個月份試試看！")

        st.markdown("### ---")

        # ==================== 3. 【未來天氣預報 - API】 ====================
        st.subheader(f"🔮 未來 3 天 {config['township']} 天氣狀況預報 (API)")
        
        api_code = "F-D0047-005" if config['county'] == "桃園市" else "F-D0047-057"
        forecast_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{api_code}?Authorization={CWA_API_KEY}"
        fore_res = requests.get(forecast_url, verify=False).json()
        
        try:
            locations_list = fore_res['records']['locations'][0]['location']
            target_location = next((loc for loc in locations_list if loc['locationName'] == config['township']), None)
            
            if target_location:
                elements = target_location['weatherElement']
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
            else:
                st.warning(f"在預報資料庫中找不到「{config['township']}」這個行政區。")
        except Exception:
            st.warning("🔍 目前該地區氣象預報資料暫時無法解析。")
            
    except Exception as e:
        st.error(f"系統執行時發生未預期錯誤，請檢查 API 授權碼。")
        st.caption(f"錯誤詳細訊息: {e}")
