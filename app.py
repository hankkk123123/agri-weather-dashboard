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

# ----------------- 📦 核心函數：72小時精細矩陣解析大腦 -----------------
def fetch_and_build_72h_matrix(api_code, backup_api_code, township_name):
    """
    對接 Swagger 逐 3 小時資料集，產出未來 72 小時高精細度農事矩陣
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    primary_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{api_code}?Authorization={CWA_API_KEY}&locationName={township_name}"
    backup_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{backup_api_code}?Authorization={CWA_API_KEY}&locationName={township_name}"
    
    res_json = None
    try:
        res = requests.get(primary_url, headers=headers, verify=False, timeout=8)
        if res.status_code == 200 and "records" in res.json():
            res_json = res.json()
    except:
        pass
        
    if res_json is None:
        try:
            res = requests.get(backup_url, headers=headers, verify=False, timeout=8)
            if res.status_code == 200 and "records" in res.json():
                res_json = res.json()
        except:
            return None

    try:
        records = res_json.get('records', {})
        loc_container = []
        for k, v in records.items():
            if isinstance(v, list) and len(v) > 0 and 'location' in str(v[0]):
                loc_container = v[0].get('location', [])
                break
            elif isinstance(v, dict) and 'location' in v:
                loc_container = v.get('location', [])
                break
        if not loc_container and 'WeatherForecast' in records:
            loc_container = records['WeatherForecast'].get('location', [])

        target_loc = next((loc for loc in loc_container if loc.get('locationName') == township_name), None) if loc_container else None
        if not target_loc and loc_container:
            target_loc = loc_container[0]

        if not target_loc:
            return None

        elements = target_loc.get('weatherElement', [])
        
        # 模糊匹配 72 小時資料集的專屬元素名稱
        wx_el, pop_el, t_el, rh_el, wd_el = None, None, None, None, None
        for el in elements:
            name = str(el.get('elementName', '')).strip()
            if name in ['Wx', '天氣現象']: wx_el = el
            elif name in ['PoP6h', 'PoP12h', 'PoP', '3小時降雨機率', '降雨機率']: pop_el = el
            elif name in ['T', '平均溫度', '溫度']: t_el = el
            elif name in ['RH', '相對濕度']: rh_el = el
            elif name in ['WD', '風向']: wd_el = el

        if not wx_el:
            return None

        matrix_data = {}
        # 72 小時逐 3 小時預報共 24 個時段
        available_slots = len(wx_el.get('time', []))
        display_slots = min(24, available_slots) 

        for i in range(display_slots):
            t_node = wx_el['time'][i]
            # 取得起始時間 (例如 2026-06-04 15:00:00)
            data_time = t_node.get('dataTime', t_node.get('startTime', '00-00 00:00'))
            
            date_label = data_time[5:10].replace('-', '/')
            hour_label = data_time[11:16]
            column_name = f"{date_label}\n{hour_label}"
            
            def get_val(element, index, fallback="N/A"):
                if element and 'time' in element and index < len(element['time']):
                    return element['time'][index]['elementValue'][0]['value']
                return fallback

            wx_val = t_node['elementValue'][0]['value']
            pop_val = get_val(pop_el, i // 2 if pop_el and len(pop_el['time']) <= 12 else i, "0") # 自動平滑降雨時段對齊
            pop_display = f"{pop_val}%" if str(pop_val).strip().isdigit() else "0%"
            t_val = f"{get_val(t_el, i, 'N/A')}°C"
            rh_val = f"{get_val(rh_el, i, 'N/A')}%"
            wd_val = get_val(wd_el, i, "微風")

            matrix_data[column_name] = {
                "天氣狀況": wx_val,
                "預估氣溫": t_val,
                "降雨機率": pop_display,
                "相對濕度": rh_val,
                "預估風向": wd_val
            }
            
        return pd.DataFrame(matrix_data) if matrix_data else None
    except:
        return None

# =========================================================================

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
    
    st.markdown("#### 📊 嘉義東區未來 72 小時逐時精細觀測報表 (每 3 小時更新)")
    # 💡 核心修改：對接 72 小時鄉鎮預報 API (嘉義市 F-D0047-057)
    cy_matrix = fetch_and_build_72h_matrix("F-D0047-057", "F-D0047-089", "東區")
    
    if cy_matrix is not None:
        st.dataframe(cy_matrix, use_container_width=True)
    else:
        st.warning("⚠️ 嘉義 72 小時預報資料暫時無法取得。")

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
    
    st.markdown("#### 📊 桃園新屋區未來 72 小時逐時精細觀測報表 (每 3 小時更新)")
    # 💡 核心修改：對接 72 小時鄉鎮預報 API (桃園市 F-D0047-005)
    ty_matrix = fetch_and_build_72h_matrix("F-D0047-005", "F-D0047-089", "新屋區")
    
    if ty_matrix is not None:
        st.dataframe(ty_matrix, use_container_width=True)
    else:
        st.warning("⚠️ 桃園 72 小時預報資料暫時無法取得。")

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
