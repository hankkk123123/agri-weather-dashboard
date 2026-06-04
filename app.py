import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import urllib3

# 關閉 SSL 警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與寬螢幕佈局
st.set_page_config(page_title="農事氣象觀測站", layout="wide")
st.title("🌾 專屬農事氣象觀測與 CODIS 歷史雨量解析站")

# 側邊欄系統設定
st.sidebar.header("⚙️ 系統設定")
CWA_API_KEY = st.sidebar.text_input("請輸入氣象署 API 授權碼", type="password")

# 核心精確測站與行政區設定
STATIONS_CONFIG = {
    "嘉義農試所地區": {"id": "G2L020", "county": "嘉義市", "township": "東區"},
    "桃園農改場地區": {"id": "72C440", "county": "桃園市", "township": "新屋區"}
}

selected_name = st.sidebar.selectbox("切換當前觀測地點", list(STATIONS_CONFIG.keys()))
config = STATIONS_CONFIG[selected_name]

if not CWA_API_KEY:
    st.warning("👈 請先於左側邊欄輸入您的中央氣象署 API 授權碼以載入即時與預報數據。")
else:
    try:
        # ==================== 區塊一：【當日即時現況 - 氣象署 API】 ====================
        obs_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={CWA_API_KEY}&StationId={config['id']}"
        obs_res = requests.get(obs_url, verify=False).json()
        
        temp = "N/A"
        today_rain = 0.0
        weather_status = "多雲/晴朗"
        station_name = selected_name
        
        if 'records' in obs_res and 'Station' in obs_res['records'] and len(obs_res['records']['Station']) > 0:
            station_node = obs_res['records']['Station'][0]
            station_name = station_node.get('StationName', selected_name)
            weather_element = station_node.get('WeatherElement', {})
            
            # 讀取當日即時氣溫、天氣狀況、當日累積降雨量
            temp = weather_element.get('AirTemperature', 'N/A')
            weather_status = weather_element.get('Weather', '多雲')
            today_rain = weather_element.get('Now', {}).get('Precipitation', 0.0)
            today_rain = 0.0 if today_rain == -99 or today_rain is None else today_rain

        st.header(f"📍 當前即時觀測：{selected_name} ({station_name})")
        
        # 建立三個大數字卡片
        col1, col2, col3 = st.columns(3)
        col1.metric(label="🌤️ 當日天氣狀況", value=str(weather_status))
        col2.metric(label="🌡️ 當日即時氣溫", value=f"{temp} °C")
        col3.metric(label="🌧️ 當日累積降雨量", value=f"{today_rain} mm")
        
        st.markdown("---")

        # ==================== 區塊二：【未來一週天氣預報與降雨機率 - 氣象署 API】 ====================
        st.subheader(f"🔮 未來一週 {config['township']} 天氣狀況與降雨機率預報")
        
        # 呼叫 7 天鄉鎮預報 API (桃園市 F-D0047-007, 嘉義市 F-D0047-059 為一週預報專用代碼)
        week_api_code = "F-D0047-007" if config['county'] == "桃園市" else "F-D0047-059"
        forecast_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{week_api_code}?Authorization={CWA_API_KEY}"
        fore_res = requests.get(forecast_url, verify=False).json()
        
        try:
            locations_list = fore_res['records']['locations'][0]['location']
            target_location = next((loc for loc in locations_list if loc['locationName'] == config['township']), None)
            
            if target_location:
                elements = target_location['weatherElement']
                
                # 尋找 Wx (天氣現象) 與 PoP12h (12小時降雨機率)
                wx_element = next((el for el in elements if el['elementName'] == 'Wx'), None)
                pop_element = next((el for el in elements if el['elementName'] == 'PoP12h'), None)
                
                time_slots = []
                weather_states = []
                pop_probabilities = []
                
                # 抓取未來一週的白天與晚上時段 (前 14 個時段)
                for i, t in enumerate(wx_element['time'][:14]):
                    # 格式化時間段名稱 (例如: 06/04 白天)
                    start_dt = t['startTime']
                    hour_check = int(start_dt[11:13])
                    day_part = "白天" if 6 <= hour_check < 18 else "晚上"
                    time_label = f"{start_dt[5:10].replace('-', '/')} ({day_part})"
                    
                    time_slots.append(time_label)
                    weather_states.append(t['elementValue'][0]['value'])
                    
                    # 降雨機率對接 (降雨機率的時段切分可能與天氣現象略有不同，做安全防錯)
                    if pop_element and i < len(pop_element['time']):
                        pop_val = pop_element['time'][i]['elementValue'][0]['value']
                        pop_probabilities.append(f"{pop_val}%" if str(pop_val).isdigit() else "0%")
                    else:
                        pop_probabilities.append("0%")
                        
                forecast_df = pd.DataFrame({
                    "預報時間段": time_slots,
                    "預估天氣狀態": weather_states,
                    "降雨機率 PoP": pop_probabilities
                })
                # 用漂亮的表格呈現一週預報
                st.dataframe(forecast_df, use_container_width=True, hide_index=True)
            else:
                st.warning(f"在預報資料庫中找不到「{config['township']}」這個行政區。")
        except Exception as e:
            st.warning("🔍 目前該地區一週氣象預報資料暫時無法解析。")
            
        st.markdown("### ==========================================================================")

        # ==================== 區塊三：【手動上傳 CODIS 逐時月報表 CSV 檔案解析】 ====================
        st.header("📂 下一區塊：CODIS 歷史降雨量逐時月報表解析")
        st.write("請從中央氣象署 CODIS 系統下載 **「單項逐時月報表 (降水量)」** 的 CSV 檔並於下方上傳：")
        
        # 建立手動上傳檔案組件
        uploaded_file = st.file_uploader("選擇上傳您的 CODIS CSV 檔案", type=["csv"])
        
        if uploaded_file is not None:
            with st.spinner("📊 正在解析您上傳的 CODIS 報表數據..."):
                try:
                    # 相容 CODIS 導出的不同編碼格式 (utf-8-sig 或 cp950)
                    try:
                        raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
                    except Exception:
                        uploaded_file.seek(0) # 指針歸零重讀
                        raw_df = pd.read_csv(uploaded_file, encoding='cp950')
                    
                    # 尋找包含「日/時」或資料列
                    # 根據 CODIS 單項逐時月報表的特徵：
                    # 橫軸通常是 1~24 小時，最後一欄是「總和」，縱軸是日期
                    
                    # 清洗轉換數據：保留前兩欄以及最後一欄「總和」
                    parsed_rows = []
                    for idx, row in raw_df.iterrows():
                        try:
                            # 檢查第一欄是否為數字日期 (01, 02, 03...)
                            day_str = str(row.iloc[0]).strip()
                            if not day_str.isdigit():
                                continue
                            day_num = int(day_str)
                            
                            # 抓取最後一欄的「總和」作為當日累積雨量
                            total_val = str(row.iloc[-1]).upper().strip()
                            
                            # 過濾 CODIS 常見異常字元
                            if 'T' in total_val or 'X' in total_val or 'V' in total_val or '--' in total_val or not total_val:
                                daily_rain_sum = 0.0
                            else:
                                daily_rain_sum = float(total_val)
                                
                            parsed_rows.append({
                                "日期": f"當月 {day_num:02d} 號",
                                "當日累積雨量 (mm)": daily_rain_sum
                            })
                        except:
                            continue
                            
                    if parsed_rows:
                        result_df = pd.DataFrame(parsed_rows)
                        
                        st.success("✅ CODIS 檔案解析成功！")
                        
                        # 左右分欄：左邊放完整數據表，右邊放月總雨量統計卡片
                        c1, c2 = st.columns([2, 1])
                        with c1:
                            st.subheader("📅 當月每日累積雨量明細表")
                            st.dataframe(result_df, use_container_width=True, hide_index=True)
                        with c2:
                            st.subheader("📊 該月降雨小計")
                            total_month_rain = result_df["當日累積雨量 (mm)"].sum()
                            st.metric(label="整個月份總累積降雨量", value=f"{total_month_rain:.1f} mm")
                            
                            # 順便幫您抓出哪一天下最大
                            max_rain_row = result_df.loc[result_df["當日累積雨量 (mm)"].idxmax()]
                            if max_rain_row["當日累積雨量 (mm)"] > 0:
                                st.info(f"💡 本月降雨量最高單日為：\n**{max_rain_row['日期']}**，下了 **{max_rain_row['當日累積雨量 (mm)']} mm**")
                    else:
                        st.error("❌ 無法從此檔案中辨識出有效的 CODIS 每日總和欄位，請確認您下載的是「單項逐時月報表」。")
                except Exception as csv_err:
                    st.error(f"❌ 讀取 CSV 檔案失敗，請確保上傳的是正確的 CODIS 導出原始檔。")
                    st.caption(f"詳細錯誤報告: {csv_err}")
        else:
            st.info("💡 提示：目前尚未上傳歷史檔案。當您從 CODIS 下載好「降水量(mm)單項逐時月報表」的 CSV 後，直接拖曳到上方框框內，這裡就會自動生出當月每天的累積降雨表格。")

    except Exception as e:
        st.error(f"系統執行時發生錯誤，請確認側邊欄的 API 授權碼是否填寫正確。")
        st.caption(f"詳細錯誤訊息: {e}")
