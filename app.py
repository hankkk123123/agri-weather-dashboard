import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import urllib3

# 關閉 SSL 警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與寬螢幕佈局
st.set_page_config(page_title="雙區農事氣象觀測站", layout="wide")
st.title("🌾 嘉義 ✖ 桃園 雙區聯防農事氣象與 CODIS 歷史雨量解析站")

# 側邊欄系統設定
st.sidebar.header("⚙️ 系統設定")
CWA_API_KEY = st.sidebar.text_input("請輸入氣象署 API 授權碼", type="password")

if not CWA_API_KEY:
    st.warning("👈 請先於左側邊欄輸入您的中央氣象署 API 授權碼以載入即時與預報數據。")
else:
    try:
        # 預先抓取全台即時觀測資料集 (O-A0001-001)，減少 API 呼叫次數
        obs_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={CWA_API_KEY}"
        obs_res = requests.get(obs_url, verify=False).json()
        all_obs_stations = obs_res.get('records', {}).get('Station', [])

        # =========================================================================
        # 🏡 第一區：嘉義農試所地區
        # =========================================================================
        st.markdown("## 🔴 第一區：嘉義農試所地區 (ID: G2L020)")
        
        # 1. 處理嘉義即時資料
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
        
        # 2. 處理嘉義未來一週預報 (F-D0047-091)
        st.markdown("#### 🔮 嘉義東區未來一週天氣與降雨機率")
        cy_forecast_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-091?Authorization={CWA_API_KEY}&locationName=東區"
        cy_fore_res = requests.get(cy_forecast_url, verify=False).json()
        
        try:
            cy_loc_nodes = cy_fore_res['records']['WeatherForecast']['location']
            # 精確鎖定嘉義市的東區
            cy_target = next((loc for loc in cy_loc_nodes if "嘉義市" in str(loc.get('geocode', '')) or loc['locationName'] == '東區'), None)
            if not cy_target and cy_loc_nodes:
                cy_target = cy_loc_nodes[0]
                
            if cy_target:
                cy_elements = cy_target['weatherElement']
                cy_wx = next((el for el in cy_elements if el['elementName'] == 'Wx'), None)
                cy_pop = next((el for el in cy_elements if el['elementName'] in ['PoP', 'PoP12h']), None)
                
                cy_slots, cy_states, cy_pops = [], [], []
                for i, t in enumerate(cy_wx['time'][:14]):
                    start_dt = t['startTime']
                    day_part = "白天" if 6 <= int(start_dt[11:13]) < 18 else "晚上"
                    cy_slots.append(f"{start_dt[5:10].replace('-', '/')} ({day_part})")
                    cy_states.append(t['elementValue'][0]['value'])
                    
                    if cy_pop and i < len(cy_pop['time']):
                        p_val = cy_pop['time'][i]['elementValue'][0]['value']
                        cy_pops.append(f"{p_val}%" if str(p_val).strip().isdigit() else "0%")
                    else:
                        cy_pops.append("0%")
                        
                cy_df = pd.DataFrame({"預報時間段": cy_slots, "預估天氣狀態": cy_states, "降雨機率 PoP": cy_pops})
                st.dataframe(cy_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.caption(f"嘉義預報暫時無法解析 (除錯訊息: {e})")

        st.markdown("### ==========================================================================")

        # =========================================================================
        # 🏡 第二區：桃園農改場地區
        # =========================================================================
        st.markdown("## 🟢 第二區：桃園農改場地區 (ID: 72C440)")
        
        # 1. 處理桃園即時資料
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
        
        # 2. 處理桃園未來一週預報 (F-D0047-091)
        st.markdown("#### 🔮 桃園新屋區未來一週天氣與降雨機率")
        ty_forecast_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-091?Authorization={CWA_API_KEY}&locationName=新屋區"
        ty_fore_res = requests.get(ty_forecast_url, verify=False).json()
        
        try:
            ty_loc_nodes = ty_fore_res['records']['WeatherForecast']['location']
            ty_target = next((loc for loc in ty_loc_nodes if loc['locationName'] == '新屋區'), None)
            if not ty_target and ty_loc_nodes:
                ty_target = ty_loc_nodes[0]
                
            if ty_target:
                ty_elements = ty_target['weatherElement']
                ty_wx = next((el for el in ty_elements if el['elementName'] == 'Wx'), None)
                ty_pop = next((el for el in ty_elements if el['elementName'] in ['PoP', 'PoP12h']), None)
                
                ty_slots, ty_states, ty_pops = [], [], []
                for i, t in enumerate(ty_wx['time'][:14]):
                    start_dt = t['startTime']
                    day_part = "白天" if 6 <= int(start_dt[11:13]) < 18 else "晚上"
                    ty_slots.append(f"{start_dt[5:10].replace('-', '/')} ({day_part})")
                    ty_states.append(t['elementValue'][0]['value'])
                    
                    if ty_pop and i < len(ty_pop['time']):
                        p_val = ty_pop['time'][i]['elementValue'][0]['value']
                        ty_pops.append(f"{p_val}%" if str(p_val).strip().isdigit() else "0%")
                    else:
                        ty_pops.append("0%")
                        
                ty_df = pd.DataFrame({"預報時間段": time_slots if 'time_slots' in locals() else ty_slots, "預估天氣狀態": ty_states, "降雨機率 PoP": ty_pops})
                st.dataframe(ty_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.caption(f"桃園預報暫時無法解析 (除錯訊息: {e})")

        st.markdown("### ==========================================================================")

        # =========================================================================
        # 🏡 第三區：CODIS資料上傳區
        # =========================================================================
        st.markdown("## 🔵 第三區：CODIS 歷史資料手動上傳區")
        st.write("請將從 CODIS 下載的 **「單項逐時月報表 (降水量)」** CSV 檔案上傳至下方：")
        
        uploaded_file = st.file_uploader("選擇上傳您的 CODIS CSV 檔案", type=["csv"])
        
        if uploaded_file is not None:
            filename = str(uploaded_file.name)
            
            # 💡 智慧辨識一：偵測站點名稱
            detected_location = "未知名測站"
            if "G2L020" in filename or "chiayi" in filename.lower() or "嘉義" in filename:
                detected_location = "📍 嘉義農試所 (G2L020)"
            elif "72C440" in filename or "taoyuan" in filename.lower() or "桃園" in filename:
                detected_location = "📍 桃園農改場 (72C440)"
            
            with st.spinner("📊 正在解析上傳的 CODIS 月報表矩陣..."):
                try:
                    # 嘗試多種編碼讀取
                    try:
                        raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
                    except Exception:
                        uploaded_file.seek(0)
                        raw_df = pd.read_csv(uploaded_file, encoding='cp950')
                    
                    # 💡 智慧辨識二：從 CODIS 內部的主結構安全撈取「年月份」
                    detected_year_month = datetime.now().strftime("%Y/%m") # 預設值
                    
                    # 嘗試從第一列或欄位文字動態去抓取年月份 (例如 CODIS 檔案常有 2026/06 的字樣)
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
                            
                            # 單項逐時報表的最末一欄固定是該日的「總和」
                            total_val = str(row.iloc[-1]).upper().strip()
                            
                            if 'T' in total_val or 'X' in total_val or 'V' in total_val or '--' in total_val or not total_val:
                                daily_rain_sum = 0.0
                            else:
                                daily_rain_sum = float(total_val)
                                
                            parsed_rows.append({
                                "日期 (Date)": f"{day_num:02d} 號",
                                "每日累積雨量 Precp (mm)": daily_rain_sum
                            })
                        except:
                            continue
                            
                    if parsed_rows:
                        result_df = pd.DataFrame(parsed_rows)
                        
                        # 顯示智慧識別出的站點與年月份結果
                        st.success(f"✅ 解析成功！檔案偵測為：**{detected_location}** ✖ 報表時間：**{detected_year_month}**")
                        
                        # 雙欄位排版呈現表格與統計
                        c1, c2 = st.columns([2, 1])
                        with c1:
                            st.subheader("📅 每日累積雨量明細表格")
                            st.dataframe(result_df, use_container_width=True, hide_index=True)
                        with c2:
                            st.subheader("📊 當月總降雨小計")
                            total_month_rain = result_df["每日累積雨量 Precp (mm)"].sum()
                            st.metric(label="全月總降雨量", value=f"{total_month_rain:.1f} mm")
                            
                            max_rain = result_df.loc[result_df["每日累積雨量 Precp (mm)"].idxmax()]
                            if max_rain["每日累積雨量 Precp (mm)"] > 0:
                                st.info(f"💡 本月下雨最大單日：\n**{max_rain['日期 (Date)']}**，降雨量達 **{max_rain['每日累積雨量 Precp (mm)']} mm**")
                    else:
                        st.error("❌ 無法從此檔案結構中讀取到日總和數據，請確認您下載的是 CODIS 的「單項逐時月報表」。")
                except Exception as csv_err:
                    st.error(f"❌ 讀取 CSV 檔案失敗。錯誤詳細原因: {csv_err}")
        else:
            st.info("💡 提示：目前尚未上傳歷史檔案。您可以將下載好的嘉義或桃園 CODIS 降雨量 CSV 直接拖曳進來，系統將自動辨識地區、年月份並立刻輸出每日降雨明細表。")

    except Exception as e:
        st.error(f"系統執行時發生未預期錯誤，請確認側邊欄的 API 授權碼是否填寫正確。")
        st.caption(f"詳細錯誤訊息: {e}")
