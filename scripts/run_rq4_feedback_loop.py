# 檔案名稱: run_rq4_feedback_loop_spearman.py
#
# (✅ V2 - 已升級：所有相關性分析均改用 Spearman)

import pandas as pd
import numpy as np
import os
import warnings
from statsmodels.tsa.stattools import grangercausalitytests 
# ✅ 1. 匯入 spearmanr
from scipy.stats import spearmanr 

# --- 1. 設定區 ---
SENTIMENT_CSV_PATH = "hourly_sentiment_data.csv"
PRICE_CSV_PATH = "full_hourly_price_data.csv"
MAX_LAG = 1 

# ===================================================================
#
# 2. 核心邏輯
#
# ===================================================================

def load_and_prepare_data(sentiment_path, price_path):
    """
    (任務 C - 數據準備)
    (此函數 100% 不變)
    """
    print(f"--- 1/4: 正在載入資料... ---")
    try:
        df_sent = pd.read_csv(sentiment_path)
        df_sent['Date'] = pd.to_datetime(df_sent['Date']).dt.date
    except FileNotFoundError:
        print(f"錯誤：找不到情緒資料檔案 '{sentiment_path}'！"); return None
        
    try:
        df_price = pd.read_csv(price_path)
        df_price['Date'] = pd.to_datetime(df_price['Date']).dt.date
    except FileNotFoundError:
        print(f"錯誤：找不到股價資料檔案 '{price_path}'！"); return None

    # (合併, 篩選, 重新命名... 等邏輯都不變)
    df = pd.merge(df_sent, df_price, on=['Date', 'Time_Block'], how='inner')
    df = df[df['Time_Block'] != 'Overnight'].copy()
    df.rename(columns={'Sentiment_V2': 'S_H'}, inplace=True)
    df['R_Cum'] = df['Return_Close_vs_9am']
    df['R_H'] = df.groupby('Date')['R_Cum'].diff()
    df['R_H'] = df['R_H'].fillna(df['R_Cum'])
    
    print(f"--- 2/4: 建立滯後變數 (Lagged Variables)... ---")
    df['S_H_lag1'] = df.groupby('Date')['S_H'].shift(1)
    df['R_H_lag1'] = df.groupby('Date')['R_H'].shift(1)
    
    df_clean = df.dropna(subset=['S_H_lag1', 'R_H_lag1', 'S_H', 'R_H'])
    
    print(f"  > 原始盤中資料 N={len(df)} (13天 * 5時段 = 65)")
    print(f"  > 清理後可用資料 N={len(df_clean)} (13天 * 4時段 = 52)")
    
    return df_clean[['Date', 'Time_Block', 'S_H', 'R_H', 'S_H_lag1', 'R_H_lag1']]

# ✅✅✅ --- (關鍵修改處) --- ✅✅✅
def run_correlation_analysis(df):
    """(任務 C - 相關性分析) (✅ 已升級為 Spearman)"""
    print("\n--- 3/4: [產出 3] H-1 相關性矩陣 (Spearman Method) ---") # ✅ 標題
    
    # ✅ 2. 矩陣改用 'spearman'
    df_corr = df[['S_H', 'R_H', 'S_H_lag1', 'R_H_lag1']].corr(method='spearman')
    print(df_corr.to_string(float_format="%.4f"))
    print("-" * 50)
    
    # (分析 1) 同時性
    # ✅ 3. 改用 spearmanr
    corr_sh_rh, p_sh_rh = spearmanr(df['S_H'], df['R_H'])
    print(f"(分析 1) 同時性 spearmanr(S_H[t], R_H[t]):   {corr_sh_rh: .4f} (p={p_sh_rh: .4f})")
    
    # (分析 3) 滯後性 (R -> S) (H4a)
    # ✅ 4. 改用 spearmanr
    corr_rh_sh, p_rh_sh = spearmanr(df['R_H_lag1'], df['S_H'])
    print(f"(分析 3) 滯後性 spearmanr(R_H[t-1], S_H[t]): {corr_rh_sh: .4f} (p={p_rh_sh: .4f}) <-- H4a")
    
    # (分析 2) 預測性 (S -> R) (H4b)
    # ✅ 5. 改用 spearmanr
    corr_sh_rh_lag, p_sh_rh_lag = spearmanr(df['S_H_lag1'], df['R_H'])
    print(f"(分析 2) 預測性 spearmanr(S_H[t-1], R_H[t]): {corr_sh_rh_lag: .4f} (p={p_sh_rh_lag: .4f}) <-- H4b")
    print("-" * 50)

def run_granger_causality_test(df):
    """(任務 C - 格蘭傑因果檢定) (此函數 100% 不變)"""
    print("\n--- 4/4: [H4] 格蘭傑因果檢定 (Granger Causality Test) ---")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore") 

        # 檢定 A (S -> R): H4b
        data_sr = df[['R_H', 'S_H']] 
        gc_sr_res = grangercausalitytests(data_sr, maxlag=[MAX_LAG], verbose=False)
        p_value_sr = gc_sr_res[MAX_LAG][0]['ssr_ftest'][1]
        
        # 檢定 B (R -> S): H4a
        data_rs = df[['S_H', 'R_H']] 
        gc_rs_res = grangercausalitytests(data_rs, maxlag=[MAX_LAG], verbose=False)
        p_value_rs = gc_rs_res[MAX_LAG][0]['ssr_ftest'][1]
        
    print(f"檢定 A (H4b: S -> R): S_H 是否 Granger-cause R_H？")
    print(f"  > p-value = {p_value_sr: .4f}")
    print(f"\n檢定 B (H4a: R -> S): R_H 是否 Granger-cause S_H？")
    print(f"  > p-value = {p_value_rs: .4f}")
    
    # (最終論述... 不變)
    print("\n--- [H4] 最終論述 (p < 0.05 為顯著) ---")
    if p_value_sr < 0.05 and p_value_rs < 0.05:
        print("結論：存在「雙向回饋迴圈 (Bidirectional Feedback)」。")
    elif p_value_sr < 0.05:
        print("結論：存在「單向」關係 (情緒驅動市場, S -> R)。")
    elif p_value_rs < 0.05:
        print("結論：存在「單向」關係 (市場驅動情緒, R -> S)。")
    else:
        print("結論：「無」顯著的 Granger-causality 關係。")
    print("=============================================================")

# ===================================================================
# 3. 主程式 (不變)
# ===================================================================
def main():
    # 1. 準備資料
    df_clean = load_and_prepare_data(SENTIMENT_CSV_PATH, PRICE_CSV_PATH)
    
    if df_clean is None:
        print("資料準備失敗，已中斷。")
        return
        
    # 2. 執行相關性分析 (✅ 現在會呼叫 Spearman 版本)
    run_correlation_analysis(df_clean)
    
    # 3. 執行格蘭傑因果檢定
    run_granger_causality_test(df_clean)
    
    print("\n🎉🎉🎉 RQ4 分析完成！ 🎉🎉🎉")

if __name__ == "__main__":
    main()