# 檔案名稱: run_get_chart18_data.py
#
# 目的：
# 1. 專注計算「圖 18」所需的數據：社群量能 (Volume) 與 市場波動率 (Volatility)
# 2. 不繪圖，直接輸出數據 CSV 供論文或後續分析使用
#
# 核心指標：
# - Vol_Ratio (量能倍數): 當日討論量 / 平靜期(P1)平均量
# - Abs_R_daily (波動率): 當日股價報酬的絕對值

import pandas as pd
import numpy as np
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_prop_surge_data.csv"
OUTPUT_DATA = "chart_18_volume_volatility_data.csv"

# P1 基準期 (用來計算平均討論量)
P1_START = '2025-03-27'
P1_END = '2025-04-02'

# ===================================================================
# 2. 核心邏輯
# ===================================================================
def generate_chart18_data(df):
    print("--- 開始計算 圖 18 (量能 vs 波動) 數據 ---")

    # 1. 準備 P1 基準值 (Baseline Volume)
    # 我們需要知道「平常」有多少人在討論，才能知道現在是不是「爆量」
    df_p1 = df.loc[P1_START:P1_END]
    mean_vol_p1 = df_p1['Total'].mean()
    
    print(f"  > P1 平靜期 ({P1_START} ~ {P1_END}) 平均日討論量: {mean_vol_p1:.2f} 篇")

    # 2. 計算核心指標
    # 建立一個新的 DataFrame 專門存結果
    result_df = pd.DataFrame(index=df.index)
    
    # A. 基礎資料
    result_df['Total_Volume'] = df['Total']  # 原始篇數
    result_df['Daily_Return'] = df['R_daily'] # 原始漲跌幅
    
    # B. Vol_Ratio (量能倍數)
    # 意義：今日量是平常的幾倍？ (>1 代表比平常熱，>2 代表爆量)
    result_df['Vol_Ratio'] = df['Total'] / mean_vol_p1
    
    # C. Abs_R_daily (波動率)
    # 意義：不管漲跌，只看幅度大小 (取絕對值)
    result_df['Abs_Return_Volatility'] = df['R_daily'].abs()
    
    # D. (進階) 量能突波 (Gap from MA3)
    # 意義：跟過去3天比，今天是不是突然變多？
    vol_ma3 = df['Total'].rolling(window=3).mean()
    result_df['Vol_Gap_MA3'] = df['Total'] - vol_ma3

    return result_df

# ===================================================================
# 主程式
# ===================================================================
def main():
    print("🚀 啟動「圖 18 數據提取工具」...")
    
    # 1. 載入資料
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 錯誤：找不到 {INPUT_CSV}"); return
        
    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    
    # 2. 確保 R_daily 存在
    if 'R_daily' not in df.columns:
        if 'R_Daily' in df.columns: df.rename(columns={'R_Daily': 'R_daily'}, inplace=True)
        elif 'Daily_Return' in df.columns: df.rename(columns={'Daily_Return': 'R_daily'}, inplace=True)
        else: df['R_daily'] = df['Cumulative_Return'].diff().fillna(0)

    # 3. 計算數據
    chart18_df = generate_chart18_data(df)
    
    # 4. 輸出檔案
    # 使用 utf-8-sig 編碼，確保 Excel 開啟時中文不會亂碼
    chart18_df.to_csv(OUTPUT_DATA, encoding='utf-8-sig')
    
    print("-" * 30)
    print(f"✅ 成功！數據已儲存至：{OUTPUT_DATA}")
    print("  包含欄位：")
    print("  - Total_Volume (總篇數)")
    print("  - Vol_Ratio (量能倍數，相對於P1)")
    print("  - Daily_Return (日報酬)")
    print("  - Abs_Return_Volatility (波動率/絕對報酬)")
    print("  - Vol_Gap_MA3 (量能突波)")
    print("-" * 30)

if __name__ == "__main__":
    main()