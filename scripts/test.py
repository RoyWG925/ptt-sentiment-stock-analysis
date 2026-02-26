# 檔案名稱: preprocess_hourly_prices.py
#
# (✅ V2 - 最終修正版)
# 1. (修正) 修正 TXT 讀取的欄位名稱 (Close, High, Low, Open)
# 2. (修正) 修正 P_baseline (基線) 邏輯，使其抓取 9:00 的「Open」欄
# 3. (修正) 修正 O-H-L-C 抓取邏輯，使其抓取正確的欄位

import pandas as pd
import numpy as np
import os

# --- 1. 設定區 ---
TXT_PRICE_PATH = "hourly_prices.txt"     # 來源：混亂的 TXT
STOCK_CSV_PATH = "taiex_open_close.csv" # 來源：交易日曆
OUTPUT_CSV_PATH = "full_hourly_price_data.csv" # 輸出：乾淨的 CSV

RESEARCH_START_DATE = '2025-03-27'
RESEARCH_END_DATE = '2025-04-16'

# --- 2. 股價解析函數 (✅ 已修正) ---
def parse_day_prices(date_str, df_price_all):
    """
    (✅ 已修正) 解析「單日」的 TXT 資料
    """
    
    # 1. 篩選出當天的所有小時資料
    df_day = df_price_all[df_price_all['Date'] == date_str].copy()
    if df_day.empty:
        print(f"  > 警告：在 TXT 中找不到日期 {date_str} 的資料。")
        return None

    # 2. 定義我們要抓取的 UTC 時間
    time_map = {
        '01:00:00+00:00': '09:00-10:00', # 9:00
        '02:00:00+00:00': '10:00-11:00', # 10:00
        '03:00:00+00:00': '11:00-12:00', # 11:00
        '04:00:00+00:00': '12:00-13:00', # 12:00
        '05:00:00+00:00': '13:00-13:30'  # 13:00
    }

    output_rows = []
    P_baseline = np.nan # 9:00 的 Open 價
    
    # 3. 嘗試獲取 9:00 的基線價格 (✅ 修正：抓取 'Open' 欄)
    try:
        baseline_row = df_day[df_day['Time_UTC'] == '01:00:00+00:00']
        P_baseline = float(baseline_row['Open'].iloc[0]) # ✅ 修正：抓 'Open'
        if P_baseline == 0:
             print(f"  > ❌ 錯誤：{date_str} 的 9:00 基線價格為 0。跳過此天。")
             return None
    except Exception:
        print(f"  > ❌ 錯誤：{date_str} 找不到 9:00 (01:00 UTC) 的基線價格。跳過此天。")
        return None

    # 4. 循環抓取每一小時的 O-H-L-C (✅ 已修正)
    for utc_time, time_block in time_map.items():
        row_data = df_day[df_day['Time_UTC'] == utc_time]
        
        if row_data.empty:
            print(f"  > 警告：{date_str} 缺少 {time_block} (UTC {utc_time}) 的資料。")
            continue
            
        try:
            # ✅ 修正：按照你提供的正確順序 Close, High, Low, Open
            open_price = float(row_data['Open'].iloc[0])
            high_price = float(row_data['High'].iloc[0])
            low_price = float(row_data['Low'].iloc[0])
            close_price = float(row_data['Close'].iloc[0])
            
            # 計算報酬率 (全部都跟 P_baseline 比較)
            return_open = (open_price / P_baseline) - 1
            return_high = (high_price / P_baseline) - 1
            return_low = (low_price / P_baseline) - 1
            return_close = (close_price / P_baseline) - 1
            
            # 儲存 (✅ 修正：按照你想要的順序)
            output_rows.append({
                'Date': date_str,
                'Time_Block': time_block,
                'Close': close_price,       # ✅
                'High': high_price,         # ✅
                'Low': low_price,           # ✅
                'Open': open_price,         # ✅
                'Return_Open_vs_9am': return_open,
                'Return_High_vs_9am': return_high,
                'Return_Low_vs_9am': return_low,
                'Return_Close_vs_9am': return_close
            })

        except Exception as e:
            print(f"  > ❌ 錯誤：處理 {date_str} {time_block} 時失敗: {e}")
            continue
            
    if not output_rows:
        return None
        
    print(f"  > ✅ 成功處理 {date_str}。")
    return pd.DataFrame(output_rows)

# --- 3. 主程式 ---
def main():
    print(f"========== 正在預處理: {TXT_PRICE_PATH} ==========")
    
    # 1. 載入 TXT 檔案 (一次性)
    print(f"--- 1/3: 正在讀取 {TXT_PRICE_PATH} ... ---")
    try:
        df_price_all = pd.read_csv(
            TXT_PRICE_PATH, 
            sep=r'\s+', # 使用正則表達式
            skiprows=2, 
            header=None, 
            names=['Date', 'Time_UTC', 'Close', 'High', 'Low', 'Open'] # ✅ 修正：使用你提供的 6 欄
        )
    except FileNotFoundError:
        print(f"錯誤：找不到每小時股價檔案 '{TXT_PRICE_PATH}'。"); return
    except Exception as e:
        print(f"讀取 TXT 檔案時出錯: {e}"); return
    
    print(f"  > TXT 檔案讀取成功，共 {len(df_price_all)} 行。")

    # 2. 載入交易日曆
    print(f"--- 2/3: 正在從 '{STOCK_CSV_PATH}' 載入「交易日」... ---")
    try:
        df_stock = pd.read_csv(STOCK_CSV_PATH, usecols=['Date'], encoding='cp950', skipinitialspace=True)
    except FileNotFoundError:
        print(f"錯誤：找不到股價檔案 '{STOCK_CSV_PATH}'。"); return
        
    df_stock['Date'] = pd.to_datetime(df_stock['Date'])
    df_stock = df_stock.set_index('Date')
    df_stock = df_stock.loc[RESEARCH_START_DATE:RESEARCH_END_DATE]
    trading_days = df_stock.index
    print(f"  > G 成功載入 {len(trading_days)} 個交易日。")

    # 3. 循環處理每一天
    print(f"--- 3/3: 正在循環處理 {len(trading_days)} 個交易日... ---")
    all_returns_data = []
    
    for T in trading_days:
        date_str = T.strftime('%Y-%m-%d') # e.g., '2025-03-27'
        df_day_returns = parse_day_prices(date_str, df_price_all)
        
        if df_day_returns is not None:
            all_returns_data.append(df_day_returns)
            
    if not all_returns_data:
        print("\n❌ 錯誤：沒有任何一天成功處理！請再次檢查 TXT 檔案格式。")
        return
        
    # 4. 合併並儲存
    df_final = pd.concat(all_returns_data)
    
    # 確保 Time_Block 順序
    time_block_order = ['09:00-10:00', '10:00-11:00', '11:00-12:00', '12:00-13:00', '13:00-13:30']
    df_final['Time_Block'] = pd.Categorical(df_final['Time_Block'], categories=time_block_order, ordered=True)
    df_final.sort_values(by=['Date', 'Time_Block'], inplace=True)
    
    df_final.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
    
    print("\n🎉🎉🎉 每小時股價資料預處理完成！ 🎉🎉🎉")
    print(f"已成功儲存「乾淨」的股價資料至: {OUTPUT_CSV_PATH}")
    print("\n--- 資料預覽 (前 10 筆) ---")
    print(df_final.head(10).to_string())

if __name__ == "__main__":
    main()