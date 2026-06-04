import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import urllib3

# 關閉 SSL 警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與寬螢幕佈局
st.set_page_config(page_title="雙區農事氣象觀測站", layout="wide")

# ==================== 🔑 核心功能：網頁進入通行證驗證 ====================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""

if not st.session_state["authenticated"]:
    st.title("🔒 歡迎使用雙區農事氣象觀測站")
    st.markdown("---")
    st.subheader("⚠️ 本網頁內部包含即時氣象連線系統，請先輸入您的中央氣象署 API 授權碼以解鎖網頁：")
    
    input_key = st.text_input("請輸入氣象署 API 授權碼 (Authorization Code)", type="password")
    
    if st.button("確認送出並解鎖網頁", use_container_width=True):
        if input_key.strip():
            with st.spinner("⚡ 正在驗證 API 授權碼有效性..."):
                test_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={input_key}&limit=1"
                try:
                    res = requests.get(test_url, verify=False, timeout=5)
                    if res.status_code == 200 and "records" in res.json():
                        st.session_state["authenticated"] = True
                        st.session_state["api_key"] = input_key
                        st.success("🎉 驗證成功！網頁解鎖中...")
                        st.rerun()
                    else:
                        st.error("❌ 授權碼無效，請確認是否複製完整。")
                except Exception:
                    st.error("❌ 連線至氣象署伺服器失敗。")
        else:
            st.warning("👈 欄位不可為空。")
    st.stop()

# ==================== 🔓 以下為解鎖後的主網頁內容 ====================
CWA_API_KEY = st.session_state["api_key"]

top_col1, top_col2 = st.columns([8, 2])
with top_col1:
    st.title("🌾 嘉義 ✖ 桃園 雙區聯防農事氣象站")
with top_col2:
    if st.button("🔒 鎖定網頁 / 更換 API"):
        st.session_state["authenticated"] = False
        st.session_state["api_key"] = ""
        st.rerun()

try:
    # 預先抓取全台即時觀測資料集
    obs_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={CWA_API_KEY}"
    obs_res = requests.get(obs_url, verify=False).json()
    all_obs_stations = obs_res.get('records', {}).get('Station', [])

    # =========================================================================
    # 🏡 第一區：嘉義農試所地區
    # =========================================================================
    st.markdown("## 🔴 第一區：嘉義農試所地區 (ID: G2L020)")
    
    cy_obs_temp, cy_obs_rain, cy_obs_weather = "N/A", 0.0, "多雲/陰"
    cy_station = next((s for s in all_obs_stations if s['StationId'] == 'G2L020'), None)
    if cy_station:
        we = cy_station.get('WeatherElement', {})
        cy_obs_temp = we.get('AirTemperature', 'N/A')
        cy_obs_weather = we.get('Weather', '多雲')
        cy_obs_rain = we.get('Now', {}).get('Precipitation', 0.0)
        cy_obs_rain = 0.0 if cy_obs_rain == -99 or cy_obs_rain is None else cy_obs_rain
        
    cy_col1, cy_col2, cy_col3 = st.columns(3)
    cy_col1.metric(label="🌤️ 嘉義當日天氣狀況", value=str(cy_obs_weather))
    cy_col2.metric(label="🌡️ 嘉義當日即時氣溫", value=f"{cy_obs_temp} °C")
    cy_col3.metric(label="🌧️ 嘉義當日累積降雨量", value=f"{cy_obs_rain} mm")
    
    st.markdown("#### 📊 嘉義東區未來一週農事氣象矩陣報表")
    cy_forecast_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-059?Authorization={CWA_API_KEY}&locationName=東區"
    
    # 💡 萬能防崩潰大腦核心邏輯
    try:
        cy_f_res = requests.get(cy_forecast_url, verify=False).json()
        # 智慧相容兼顧 locations 與 location 欄位名稱
        records_node = cy_f_res.get('records', {})
        loc_container = records_node.get('locations', [{}])[0].get('location', []) if 'locations' in records_node else records_node.get('location', [])
        
        if loc_container:
            cy_elements = loc_container[0].get('weatherElement', [])
            cy_wx = next((el for el in cy_elements if el['elementName'] in ['天氣現象', 'Wx']), None)
            cy_pop = next((el for el in cy_elements if el['elementName'] in ['12小時降雨機率', 'PoP12h']), None)
            cy_t = next((el for el in cy_elements if el['elementName'] in ['平均溫度', 'T']), None)
            cy_rh = next((el for el in cy_elements if el['elementName'] in ['相對濕度', 'RH']), None)
            cy_wd = next((el for el in cy_elements if el['elementName'] in ['風向', 'WD']), None)
            
            if cy_wx:
                matrix_data = {}
                # 自動偵測陣列長度，防止切片越界
                max_slots = min(12, len(cy_wx['time']))
                for i, t in enumerate(cy_wx['time'][:max_slots]):
                    start_dt = t['startTime']
                    date_label = start_dt[5:10].replace('-', '/')
                    day_part = "白天" if 6 <= int(start_dt[11:13]) < 18 else "晚上"
                    column_name = f"{date_label}\n({day_part})"
                    
                    wx_val = t['elementValue'][0]['value']
                    pop_val = f"{cy_pop['time'][i]['elementValue'][0]['value']}%" if cy_pop and i < len(cy_pop['time']) and str(cy_pop['time'][i]['elementValue'][0]['value']).strip().isdigit() else "0%"
                    t_val = f"{cy_t['time'][i]['elementValue'][0]['value']}°C" if cy_t and i < len(cy_t['time']) else "N/A"
                    rh_val = f"{cy_rh['time'][i]['elementValue'][0]['value']}%" if cy_rh and i < len(cy_rh['time']) else "N/A"
                    wd_val = cy_wd['time'][i]['elementValue'][0]['value'] if cy_wd and i < len(cy_wd['time']) else "N/A"
                    
                    matrix_data[column_name] = {
                        "天氣狀況": wx_val, "預估氣溫": t_val, "降雨機率": pop_val, "相對濕度": rh_val, "預估風向": wd_val
                    }
                st.dataframe(pd.DataFrame(matrix_data), use_container_width=True)
        else:
            st.warning("🔍 氣象署後台目前正在更新交班預報資料，請稍候重新整理網頁。")
    except Exception:
        st.warning("🔍 嘉義一週矩陣預報暫時無法解析。")

    st.markdown("### ---")

    # =========================================================================
    # 🏡 第二區：桃園農改場地區
    # =========================================================================
    st.markdown("## 🟢 第二區：桃園農改場地區 (ID: 72C440)")
    
    ty_obs_temp, ty_obs_rain, ty_obs_weather = "N/A", 0.0, "多雲/陰"
    ty_station = next((s for s in all_obs_stations if s['StationId'] == '72C440'), None)
    if ty_station:
        we = ty_station.get('WeatherElement', {})
        ty_obs_temp = we.get('AirTemperature', 'N/A')
        ty_obs_weather = we.get('Weather', '多雲')
        ty_obs_rain = we.get('Now', {}).get('Precipitation', 0.0)
        ty_obs_rain = 0.0 if ty_obs_rain == -99 or ty_obs_rain is None else ty_obs_rain
        
    ty_col1, ty_col2, ty_col3 = st.columns(3)
    ty_col1.metric(label="🌤️ 桃園當日天氣狀況", value=str(ty_obs_weather))
    ty_col2.metric(label="🌡️ 桃園當日即時氣溫", value=f"{ty_obs_temp} °C")
    ty_col3.metric(label="🌧️ 桃園當日累積降雨量", value=f"{ty_obs_rain} mm")
    
    st.markdown("#### 📊 桃園新屋區未來一週農事氣象矩陣報表")
    ty_forecast_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-007?Authorization={CWA_API_KEY}&locationName=新屋區"
    
    try:
        ty_f_res = requests.get(ty_forecast_url, verify=False).json()
        ty_records = ty_f_res.get('records', {})
        ty_loc_container = ty_records.get('locations', [{}])[0].get('location', []) if 'locations' in ty_records else ty_records.get('location', [])
        
        if ty_loc_container:
            ty_elements = ty_loc_container[0].get('weatherElement', [])
            ty_wx = next((el for el in ty_elements if el['elementName'] in ['天氣現象', 'Wx']), None)
            ty_pop = next((el for el in ty_elements if el['elementName'] in ['12小時降雨機率', 'PoP12h']), None)
            ty_t = next((el for el in ty_elements if el['elementName'] in ['平均溫度', 'T']), None)
            ty_rh = next((el for el in ty_elements if el['elementName'] in ['相對濕度', 'RH']), None)
            ty_wd = next((el for el in ty_elements if el['elementName'] in ['風向', 'WD']), None)
            
            if ty_wx:
                ty_matrix_data = {}
                ty_max_slots = min(12, len(ty_wx['time']))
                for i, t in enumerate(ty_wx['time'][:ty_max_slots]):
                    start_dt = t['startTime']
                    date_label = start_dt[5:10].replace('-', '/')
                    day_part = "白天" if 6 <= int(start_dt[11:13]) < 18 else "晚上"
                    column_name = f"{date_label}\n({day_part})"
                    
                    wx_val = t['elementValue'][0]['value']
                    pop_val = f"{ty_pop['time'][i]['elementValue'][0]['value']}%" if ty_pop and i < len(ty_pop['time']) and str(ty_pop['time'][i]['elementValue'][0]['value']).strip().isdigit() else "0%"
                    t_val = f"{ty_t['time'][i]['elementValue'][0]['value']}°C" if ty_t and i < len(ty_t['time']) else "N/A"
                    rh_val = f"{ty_rh['time'][i]['elementValue'][0]['value']}%" if ty_rh and i < len(ty_rh['time']) else "N/A"
                    wd_val = ty_wd['time'][i]['elementValue'][0]['value'] if ty_wd and i < len(ty_wd['time']) else "N/A"
                    
                    ty_matrix_data[column_name] = {
                        "天氣狀況": wx_val, "預估氣溫": t_val, "降雨機率": pop_val, "相對濕度": rh_val, "預估風向": wd_val
                    }
                st.dataframe(pd.DataFrame(ty_matrix_data), use_container_width=True)
        else:
            st.warning("🔍 氣象署後台目前正在更新交班預報資料，請稍候重新整理網頁。")
    except Exception:
        st.warning("🔍 桃園一週矩陣預報暫時無法解析。")

    st.markdown("### ==========================================================================")

    # =========================================================================
    # 🏡 第三區：CODIS資料上傳區
    # =========================================================================
    st.markdown("## 🔵 第三區：CODIS 歷史資料手動上傳區")
    uploaded_file = st.file_uploader("選擇上傳您的 CODIS CSV 檔案", type=["csv"])
    
    if uploaded_file is not None:
        filename = str(uploaded_file.name)
        detected_location = "未知名測站"
        if "G2L020" in filename or "chiayi" in filename.lower() or "嘉義" in filename:
            detected_location = "📍 嘉義農試所 (G2L020)"
        elif "72C440" in filename or "taoyuan" in filename.lower() or "桃園" in filename:
            detected_location = "📍 桃園農改場 (72C440)"
        
        with st.spinner("📊 正在解析上傳的 CODIS 月報表矩陣..."):
            try:
                try:
                    raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
                except Exception:
                    uploaded_file.seek(0)
                    raw_df = pd.read_csv(uploaded_file, encoding='cp950')
                
                detected_year_month = datetime.now().strftime("%Y/%m")
                for col in raw_df.columns:
                    col_str = str(col)
                    if "202" in col_str and ("/" in col_str or "-" in col_str):
                        detected_year_month = col_str.strip()
                        break
                
                parsed_rows = []
                for idx, row in raw_df.iterrows():
                    try:
                        day_str = str(row.iloc[0]).strip()
                        if not day_str.isdigit():
                            continue
                        day_num = int(day_str)
                        total_val = str(row.iloc[-1]).upper().strip()
                        
                        if 'T' in total_val or 'X' in total_val or 'V' in total_val or '--' in total_val or not total_val:
                            daily_rain_sum = 0.0
                        else:
                            daily_rain_sum = float(total_val)
                            
                        parsed_rows.append({
                            "日期 (Date)": f"{day_num:02d} 號", "每日累積雨量 Precp (mm)": daily_rain_sum
                        })
                    except:
                        continue
                        
                if parsed_rows:
                    result_df = pd.DataFrame(parsed_rows)
                    st.success(f"✅ 解析成功！檔案偵測為：**{detected_location}** ✖ 報表時間：**{detected_year_month}**")
                    
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.subheader("📅 每日累積雨量明細表格")
                        st.dataframe(result_df, use_container_width=True, hide_index=True)
                    with c2:
                        st.subheader("📊 當月總降雨小計")
                        total_month_rain = result_df["每日累積雨量 Precp (mm)"].sum()
                        st.metric(label="全月總降雨量", value=f"{total_month_rain:.1f} mm")
                else:
                    st.error("❌ 無法從此檔案結構中讀取到日總和數據。")
            except Exception as csv_err:
                st.error(f"❌ 讀取 CSV 檔案失敗。")
    else:
        st.info("💡 提示：目前尚未上傳歷史檔案。您可以將下載好的嘉義或桃園 CODIS 降雨量 CSV 直接拖曳進來，系統將自動辨識地區、年月份並立刻輸出每日降雨明細表。")

except Exception as e:
    st.error(f"網頁執行時發生錯誤，請重新整理網頁。")
