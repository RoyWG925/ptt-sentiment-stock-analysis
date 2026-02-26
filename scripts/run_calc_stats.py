# 檔案名稱: run_calc_stats.py
#
# 目的：
# 1. 計算「正面」、「負面」、「中性」情緒的統計指標 (Z-score, Min-Max, Diff)
# 2. 計算與市場回報的「相關係數 (Correlation)」
# 3. 輸出純數字 CSV 檔案供後續分析

import pandas as pd
import numpy as np
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_prop_surge_data.csv"
OUTPUT_FOLDER = "output_statistics"

# 設定要分析的情緒欄位
SENTIMENT_CONFIG = {
    'Pos': {'col': 'Pos_prop', 'name': '正面情緒'},
    'Neg': {'col': 'Neg_prop', 'name': '負面情緒'},
    'Neu': {'col': 'Neu_prop', 'name': '中性情緒'}
}

# ===================================================================
# 2. 計算邏輯函式
# ===================================================================

def minmax_scale(series):
    """將數據縮放到 0~1 之間"""
    return (series - series.min()) / (series.max() - series.min())

def process_sentiment_metrics(df, sent_key, config):
    """
    針對單一情緒指標，計算各種統計轉換數據
    回傳: (處理後的 DataFrame, 相關係數 Dict)
    """
    col_name = config['col']
    name = config['name']
    
    # 建立一個乾淨的 DataFrame 儲存結果
    # 移除 NaN 以確保計算正確
    sub_df = df[[col_name, 'Cumulative_Return', 'R_daily']].dropna().copy()
    
    # 1. 原始數據 (Raw)
    sub_df[f'{sent_key}_Raw'] = sub_df[col_name]
    
    # 2. Z-score 標準化 (Z)
    sub_df[f'{sent_key}_Z'] = stats.zscore(sub_df[col_name])
    sub_df['Mkt_Cum_Z'] = stats.zscore(sub_df['Cumulative_Return'])
    
    # 3. Min-Max 正規化 (MM)
    sub_df[f'{sent_key}_MM'] = minmax_scale(sub_df[col_name])
    sub_df['Mkt_Cum_MM'] = minmax_scale(sub_df['Cumulative_Return'])
    
    # 4. 變化量 (Diff) - 注意：Diff 會導致第一筆資料變 NaN
    sub_df[f'{sent_key}_Diff'] = sub_df[col_name].diff()
    sub_df['Mkt_Daily_Return'] = sub_df['R_daily'] # 市場的 Diff 就是日報酬
    
    # --- 計算相關係數 (Pearson Correlation) ---
    # 針對「原始值 vs 累計報酬」
    corr_raw = sub_df[col_name].corr(sub_df['Cumulative_Return'])
    
    # 針對「變化量 vs 日報酬」 (這是動能分析最看重的)
    # 需排除第一筆 Diff 為 NaN 的資料
    valid_diff = sub_df.dropna()
    corr_diff = valid_diff[f'{sent_key}_Diff'].corr(valid_diff['Mkt_Daily_Return'])
    
    stats_summary = {
        'Sentiment': name,
        'Corr_Trend (原始值 vs 股價趨勢)': round(corr_raw, 4),
        'Corr_Momentum (變化量 vs 日報酬)': round(corr_diff, 4)
    }
    
    return sub_df, stats_summary

def main():
    print("📊 啟動數據統計轉換工具...")

    # 1. 建立輸出資料夾
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"  > 建立資料夾：{OUTPUT_FOLDER}")

    # 2. 載入資料
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 錯誤：找不到 {INPUT_CSV}"); return
    
    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    print(f"  > 成功載入資料，共 {len(df)} 筆。")

    # 3. 預處理：確保必要欄位存在
    # 確保 R_daily
    if 'R_daily' not in df.columns:
        if 'R_Daily' in df.columns: df.rename(columns={'R_Daily': 'R_daily'}, inplace=True)
        elif 'Daily_Return' in df.columns: df.rename(columns={'Daily_Return': 'R_daily'}, inplace=True)
        else: df['R_daily'] = df['Cumulative_Return'].diff().fillna(0)
    
    # 確保 Neu_prop (加入 clip 防止負數)
    if 'Neu_prop' not in df.columns:
        print("  > 計算中性情緒 (Neu_prop)...")
        if 'Count_Neu' in df.columns and 'Total' in df.columns:
            df['Neu_prop'] = df['Count_Neu'] / df['Total']
        else:
            df['Neu_prop'] = (1 - df['Pos_prop'] - df['Neg_prop']).clip(0, 1)

    # 4. 迴圈計算並存檔
    summary_list = []
    
    for key, config in SENTIMENT_CONFIG.items():
        if config['col'] not in df.columns:
            print(f"  > ⚠️ 跳過 {key} (找不到欄位)")
            continue
            
        print(f"  > 正在處理：{config['name']} ...")
        
        # 核心計算
        result_df, corr_stats = process_sentiment_metrics(df, key, config)
        summary_list.append(corr_stats)
        
        # 儲存該情緒的詳細數據 CSV
        output_path = os.path.join(OUTPUT_FOLDER, f"data_{key}_metrics.csv")
        result_df.to_csv(output_path, encoding='utf-8-sig') # utf-8-sig 防止 Excel 中文亂碼
        print(f"     -> 已儲存詳細數據：{output_path}")

    # 5. 輸出相關係數總表
    print("-" * 30)
    print("📈 相關係數分析結果 (Correlation Summary)：")
    summary_df = pd.DataFrame(summary_list)
    
    # 調整欄位順序
    cols = ['Sentiment', 'Corr_Trend (原始值 vs 股價趨勢)', 'Corr_Momentum (變化量 vs 日報酬)']
    summary_df = summary_df[cols]
    
    # 顯示在終端機
    print(summary_df.to_string(index=False))
    
    # 存檔
    summary_path = os.path.join(OUTPUT_FOLDER, "summary_correlation.csv")
    summary_df.to_csv(summary_path, index=False, encoding='utf-8-sig')
    print("-" * 30)
    print(f"✅ 所有數據處理完成！總表已存至：{summary_path}")

if __name__ == "__main__":
    main()