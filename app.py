import streamlit as st
import requests
import pandas as pd
import re
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
    st.title("🌾 嘉義 ✖ 桃園 氣象站")
with top_col2:
    if st.button("🔒 鎖定網頁 / 更換 API"):
        st.session_state["authenticated"] = False
        st.session_state["api_key"] = ""
        st.rerun()

# ----------------- 📦 核心函數：未來一週官網同款矩陣解析大腦 -----------------
def fetch_and_build_week_matrix(api_code, backup_api_code, township_name):
    headers = {"User-Agent": "Mozilla/5.0"}
    # 採用全回傳機制獲取資料，避免 API 端參數過濾不穩定
    primary_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{api_code}?Authorization={CWA_API_KEY}"
    backup_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{backup_api_code}?Authorization={CWA_API_KEY}"
    
    res_json = None
    try:
        res = requests.get(primary_url, headers=headers, verify=False, timeout=5)
        if res.status_code == 200 and "records" in res.json():
            res_json = res.json()
    except:
        pass
        
    if res_json is None:
        try:
            res = requests.get(backup_url, headers=headers, verify=False, timeout=5)
            if res.status_code == 200 and "records" in res.json():
                res_json = res.json()
        except:
            return None

    try:
        records = res_json.get('records', {})
        loc_container = []
        if 'locations' in records and len(records['locations']) > 0:
            loc_container = records['locations'][0].get('location', [])
        elif 'location' in records:
            if isinstance(records['location'], list):
                loc_container = records['location']
            elif isinstance(records['location'], dict):
                loc_container = records['location'].get('location', [])

        if not loc_container:
            for k, v in records.items():
                if isinstance(v, list) and len(v) > 0 and 'location' in str(v[0]):
                    loc_container = v[0].get('location', [])
                    break

        # 在本機記憶體進行行政區匹配（確保去除空格）
        target_loc = next((loc for loc in loc_container if str(loc.get('locationName')).strip() == township_name), None) if loc_container else None
        
        if not target_loc and loc_container:
            for loc in loc_container:
                if township_name in str(loc.get('locationName')):
                    target_loc = loc
                    break
            if not target_loc:
                target_loc = loc_container[0]

        if not target_loc:
            return None

        elements = target_loc.get('weatherElement', [])
        wx_el, pop_el, t_el, rh_el, wd_el = None, None, None, None, None
        
        # 精確對齊 368 鄉鎮一週預報產品規格書規範的繁體中文名稱
        for el in elements:
            name = str(el.get('elementName', '')).strip()
            if name in ['天氣現象', 'Wx', 'Weather']: wx_el = el
            elif name in ['12小時降雨機率', 'PoP12h', 'PoP', '降雨機率', 'ProbabilityOfPrecipitation']: pop_el = el
            elif name in ['平均溫度', 'T', '溫度', 'Temperature']: t_el = el
            elif name in ['平均相對濕度', '相對濕度', 'RH', 'RelativeHumidity']: rh_el = el
            elif name in ['風向', 'WD', 'WindDirection']: wd_el = el

        if not wx_el:
            return None

        matrix_data = {}
        available_slots = len(wx_el.get('time', []))
        display_slots = min(14, available_slots) 

        for i in range(display_slots):
            t_node = wx_el['time'][i]
            start_dt = t_node.get('startTime', '00-00 00:00')
            
            date_label = start_dt[5:10].replace('-', '/')
            hour_part = int(start_dt[11:13]) if len(start_dt) > 13 else 12
            day_part = "白天" if 6 <= hour_part < 18 else "晚上"
            column_name = f"{date_label}\n({day_part})"
            
            def get_val(element, index, fallback="N/A"):
                if element and 'time' in element and index < len(element['time']):
                    t_item = element['time'][index]
                    if 'elementValue' in t_item and len(t_item['elementValue']) > 0:
                        val = t_item['elementValue'][0].get('value', fallback)
                        if str(val).strip() in ['-99', '-99.0', '']: return fallback
                        return val
                return fallback

            if 'elementValue' in t_node and len(t_node['elementValue']) > 0:
                wx_val = str(t_node['elementValue'][0].get('value', '觀測維護中')).strip()
            else:
                wx_val = "觀測維護中"
                
            if wx_val in ['-99', '-99.0', '']: wx_val = "觀測維護中"
            
            pop_val = get_val(pop_el, i, "0")
            pop_display = f"{pop_val}%" if str(pop_val).strip().isdigit() else "0%"
            t_val = f"{get_val(t_el, i, 'N/A')}°C"
            rh_val = f"{get_val(rh_el, i, 'N/A')}%"
            wd_val = get_val(wd_el, i, "微風")

            matrix_data[column_name] = {
                "天氣狀況": wx_val, "預估氣溫": t_val, "降雨機率": pop_display, "相對濕度": rh_val, "預估風向": wd_val
            }
        return pd.DataFrame(matrix_data) if matrix_data else None
    except:
        return None

# =========================================================================

try:
    # 預先抓取全台即時觀測資料集 (O-A0001-001)
    obs_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={CWA_API_KEY}"
    obs_res = requests.get(obs_url, verify=False).json()
    all_obs_stations = obs_res.get('records', {}).get('Station', [])

    # =========================================================================
    # 🏡 第一區：嘉義農試所地區
    # =========================================================================
    st.markdown("## 嘉義農試所區 (ID: G2L020)")
    
    cy_obs_temp, cy_obs_rain, cy_obs_weather = "N/A", 0.0, "自動站無觀測"
    cy_station = next((s for s in all_obs_stations if s['StationId'] == 'G2L020'), None)
    if cy_station:
        we = cy_station.get('WeatherElement', {})
        cy_obs_temp = we.get('AirTemperature', 'N/A')
        if str(cy_obs_temp).strip() in ['-99', '-99.0', '-99.00']: cy_obs_temp = "N/A"
        cy_obs_weather = we.get('Weather', '自動站無觀測')
        if str(cy_obs_weather).strip() in ['-99', '-99.0', '']: cy_obs_weather = "自動站無觀測"
        cy_obs_rain = we.get('Now', {}).get('Precipitation', 0.0)
        if cy_obs_rain in [-99, -99.0, None, '']: cy_obs_rain = 0.0
        
    cy_col1, cy_col2, cy_col3 = st.columns(3)
    cy_col1.metric(label="🌤️ 嘉義當日天氣狀況", value=str(cy_obs_weather))
    cy_col2.metric(label="🌡️ 嘉義當日即時氣溫", value=f"{cy_obs_temp} °C" if cy_obs_temp != "N/A" else "N/A")
    cy_col3.metric(label="🌧️ 嘉義當日累積降雨量", value=f"{cy_obs_rain} mm")
    
    st.markdown("#### 📊 嘉義東區未來一週農事氣象矩陣報表 (白天/晚上)")
    # 正確對齊一週預報法規地理參數：東區
    cy_matrix = fetch_and_build_week_matrix("F-D0047-059", "F-D0047-091", "東區")
    
    if cy_matrix is not None:
        st.dataframe(cy_matrix, use_container_width=True)
    else:
        st.warning("⚠️ 嘉義一週預報資料暫時無法取得。")

    st.markdown("### ---")

    # =========================================================================
    # 🏡 第二區：桃園農改場地區
    # =========================================================================
    st.markdown("## 桃園農改場 (ID: 72C440)")
    
    ty_obs_temp, ty_obs_rain, ty_obs_weather = "N/A", 0.0, "自動站無觀測"
    ty_station = next((s for s in all_obs_stations if s['StationId'] == '72C440'), None)
    if ty_station:
        we = ty_station.get('WeatherElement', {})
        ty_obs_temp = we.get('AirTemperature', 'N/A')
        if str(ty_obs_temp).strip() in ['-99', '-99.0', '-99.00']: ty_obs_temp = "N/A"
        ty_obs_weather = we.get('Weather', '自動站無觀測')
        if str(ty_obs_weather).strip() in ['-99', '-99.0', '']: ty_obs_weather = "自動站無觀測"
        ty_obs_rain = we.get('Now', {}).get('Precipitation', 0.0)
        if ty_obs_rain in [-99, -99.0, None, '']: ty_obs_rain = 0.0
        
    ty_col1, ty_col2, ty_col3 = st.columns(3)
    ty_col1.metric(label="🌤️ 桃園當日天氣狀況", value=str(ty_obs_weather))
    ty_col2.metric(label="🌡️ 桃園當日即時氣溫", value=f"{ty_obs_temp} °C" if ty_obs_temp != "N/A" else "N/A")
    ty_col3.metric(label="🌧️ 桃園當日累積降雨量", value=f"{ty_obs_rain} mm")
    
    st.markdown("#### 📊 桃園新屋區未來一週農事氣象矩陣報表 (白天/晚上)")
    ty_matrix = fetch_and_build_week_matrix("F-D0047-007", "F-D0047-091", "新屋區")
    
    if ty_matrix is not None:
        st.dataframe(ty_matrix, use_container_width=True)
    else:
        st.warning("⚠️ 桃園一週預報資料暫時無法取得。")

    st.markdown("### ==========================================================================")

    # =========================================================================
    # 🏡 第三區：CODIS資料上傳區
    # =========================================================================
    st.markdown("## CODIS 歷史資料手動上傳區")
    uploaded_file = st.file_uploader("選擇上傳您的 CODIS CSV 檔案", type=["csv"])
    
    if uploaded_file is not None:
        filename = str(uploaded_file.name)
        
        detected_location = "未知名測站"
        if "G2L020" in filename or "嘉義" in filename:
            detected_location = "嘉義農試所 (G2L020)"
        elif "72C440" in filename or "桃園" in filename:
            detected_location = "桃園農改場 (72C440)"
            
        detected_year_month = "未知年月"
        match = re.search(r'(20\d{2})[-_]?(\d{2})', filename)
        if match:
            detected_year_month = f"{match.group(1)}年{match.group(2)}月"
        
        with st.spinner("📊 正在解析上傳的 CODIS 月報表矩陣..."):
            try:
                try:
                    raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
                except Exception:
                    uploaded_file.seek(0)
                    raw_df = pd.read_csv(uploaded_file, encoding='cp950')
                
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
                    st.success(f"✅ 解析成功！觀測地點：**{detected_location}** ✖ 資料月份：**{detected_year_month}**")
                    
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.subheader("📅 每日累積雨量明細表格")
                        st.dataframe(result_df, use_container_width=True, hide_index=True)
                    with c2:
                        st.subheader("📊 當月總降雨小計")
                        total_month_rain = result_df["每日累積雨量 Precp (mm)"].sum()
                        st.metric(label="全月總累積降雨量", value=f"{total_month_rain:.1f} mm")
                else:
                    st.error("❌ 無法從此檔案結構中讀取到日總和數據。")
            except Exception as csv_err:
                st.error(f"❌ 讀取 CSV 檔案失敗。")
    else:
        st.info("💡 提示：目前尚未上傳歷史檔案。您可以將下載好的嘉義（G2L020）或桃園（72C440）CODIS 降雨量 CSV 直接拖曳進來，系統將自動從檔案名稱中提取編號與年月，並立刻輸出每日累積雨量。")

except Exception as e:
    st.error(f"網頁執行時發生錯誤，請重新整理網頁。")
