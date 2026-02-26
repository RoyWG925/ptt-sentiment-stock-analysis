# 檔案名稱: run_thesis_final_stats.py
#
# 目的：執行論文最終版本的「全面統計檢定 (Checklist)」
# 涵蓋：Overnight/Intraday, Level/Surge, Lag-1, ANOVA, Hourly Micro, Volatility, OLS

import pandas as pd
import numpy as np
import scipy.stats as stats
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.tsa.stattools import ccf
import os

# ===================================================================
# 1. 設定區
# ===================================================================
DAILY_CSV = "final_structured_data.csv"
HOURLY_SENT_CSV = "hourly_sentiment_data_PN_Ratio.csv"
HOURLY_PRICE_CSV = "full_hourly_price_data.csv"

OUTPUT_REPORT = "thesis_final_statistics_report.txt"

# 時期定義
P1_LABEL = 'P1'; P2_LABEL = 'P2'; P3_LABEL = 'P3'

# ===================================================================
# 2. 輔助函式
# ===================================================================
def append_report(text, filepath=OUTPUT_REPORT):
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)

def get_significance(p):
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.1: return "*"
    return "ns"

def run_spearman(df, col_x, col_y, label):
    # 移除 NaN
    data = df[[col_x, col_y]].dropna()
    if len(data) < 3:
        return f"{label}: N<3 (Skipped)"
    
    corr, p = stats.spearmanr(data[col_x], data[col_y])
    sig = get_significance(p)
    return f"{label:<50} | rho = {corr:.4f} | p = {p:.4f} ({sig})"

# ===================================================================
# 3. 資料準備 (Data Prep)
# ===================================================================
def load_and_prep_data():
    # --- 1. 載入日資料 ---
    df_daily = pd.read_csv(DAILY_CSV, parse_dates=['Date'], index_col='Date')
    
    # 確保必要的變數存在 (Surge, Abs Return, Lag)
    # 極性指標 S
    df_daily['S_Overnight_Surge'] = df_daily['S_Overnight'].diff()
    df_daily['S_Intraday_Surge'] = df_daily['S_Intraday'].diff()
    df_daily['S_Overnight_Lag1'] = df_daily['S_Overnight'].shift(1)
    
    # PN Ratio
    df_daily['PNR_Overnight_Surge'] = df_daily['PNR_Overnight'].diff()
    df_daily['PNR_Intraday_Surge'] = df_daily['PNR_Intraday'].diff()
    
    # Volatility (絕對報酬)
    df_daily['Abs_R_daily'] = df_daily['R_daily'].abs()
    
    # --- 2. 載入每小時資料 ---
    df_h_sent = pd.read_csv(HOURLY_SENT_CSV)
    df_h_price = pd.read_csv(HOURLY_PRICE_CSV)
    
    # 統一欄位名稱以利合併
    # (假設 price csv 欄位是 'Return_Open_vs_9am' 等)
    # 我們需要計算 Hourly Return (單小時)
    # 簡單起見，我們使用 price csv 裡的 Close 欄位來算 pct_change
    # 但更準確的是用 full_hourly_price_data 裡的欄位
    
    # 合併
    df_hourly = pd.merge(df_h_sent, df_h_price, on=['Date', 'Time_Block'], how='inner')
    
    # 計算 Hourly Return & Hourly Surge
    # 注意：這裡需要對每個 Date 內的 Time_Block 排序
    df_hourly['Close'] = pd.to_numeric(df_hourly['Close'], errors='coerce')
    
    # 計算每小時報酬 (相對於上一小時 Close，或者用 Open/Close 差)
    # 這裡簡化：用 Return_Close_vs_9am 的差分
    # R_h[t] = R_cum[t] - R_cum[t-1]
    df_hourly['R_cum'] = df_hourly['Return_Close_vs_9am']
    df_hourly['R_hour'] = df_hourly.groupby('Date')['R_cum'].diff().fillna(df_hourly['R_cum'])
    
    # 計算 Sentiment Surge (Hourly)
    df_hourly['S_hour'] = (df_hourly['Sentiment_PN_Ratio'] - 1) / (df_hourly['Sentiment_PN_Ratio'] + 1) # 轉回 S (近似)
    # 或者直接用 PN Ratio
    df_hourly['PNR_hour'] = df_hourly['Sentiment_PN_Ratio']
    
    df_hourly['S_hour_surge'] = df_hourly.groupby('Date')['S_hour'].diff()
    df_hourly['PNR_hour_surge'] = df_hourly.groupby('Date')['PNR_hour'].diff()
    
    return df_daily, df_hourly

# ===================================================================
# 4. 主程式：執行所有檢定
# ===================================================================
def main():
    # 初始化報告
    if os.path.exists(OUTPUT_REPORT): os.remove(OUTPUT_REPORT)
    append_report("=== 畢業論文最終統計檢定報告 (Final Statistics Checklist) ===\n")
    
    df_daily, df_hourly = load_and_prep_data()
    append_report(f"資料載入完成: Daily N={len(df_daily)}, Hourly N={len(df_hourly)}\n")

    # ----------------------------------------------------------------
    # ⭐ Part 1：隔夜情緒 (Overnight)
    # ----------------------------------------------------------------
    append_report("⭐ Part 1：隔夜情緒 (Overnight Sentiment)")
    append_report("--------------------------------------------------")
    
    # 1.1 Level vs Return
    append_report("[1.1] 隔夜情緒水平 vs 當日市場 (Level -> Return)")
    append_report(run_spearman(df_daily, 'S_Overnight', 'R_daily', 'Spearman: S_Overnight vs R_daily'))
    append_report(run_spearman(df_daily, 'PNR_Overnight', 'R_daily', 'Spearman: PNR_Overnight vs R_daily'))
    append_report("")

    # 1.2 Surge vs Return
    append_report("[1.2] 隔夜情緒變化量 vs 當日市場 (Surge -> Return)")
    append_report(run_spearman(df_daily, 'S_Overnight_Surge', 'R_daily', 'Spearman: S_Overnight_Surge vs R_daily'))
    append_report(run_spearman(df_daily, 'PNR_Overnight_Surge', 'R_daily', 'Spearman: PNR_Overnight_Surge vs R_daily'))
    append_report("")

    # 1.3 Lag-1 (Prediction)
    append_report("[1.3] 隔夜情緒跨期預測 (Lag-1 -> Return)")
    append_report(run_spearman(df_daily, 'S_Overnight_Lag1', 'R_daily', 'Spearman: S_Overnight(t-1) vs R_daily(t)'))
    
    # CCF (簡單跑一下 Lag 0, 1)
    ccf_val = ccf(df_daily['R_daily'], df_daily['S_Overnight'].fillna(0), adjusted=False)
    append_report(f"CCF (S leads R): Lag 0={ccf_val[0]:.4f}, Lag 1={ccf_val[1]:.4f}")
    append_report("")

    # 1.4 ANOVA / T-test
    append_report("[1.4] 隔夜情緒在事件視窗的差異檢定 (P1/P2/P3)")
    
    groups = [df_daily[df_daily['Period']==p]['S_Overnight'].dropna() for p in [P1_LABEL, P2_LABEL, P3_LABEL]]
    # ANOVA
    f_stat, p_val = stats.f_oneway(*groups)
    sig = get_significance(p_val)
    append_report(f"ANOVA (S_Overnight): F={f_stat:.4f}, p={p_val:.4f} ({sig})")
    
    # T-test (P1 vs P2, P2 vs P3)
    t12, p12 = stats.ttest_ind(groups[0], groups[1], equal_var=False)
    t23, p23 = stats.ttest_ind(groups[1], groups[2], equal_var=False)
    append_report(f"T-test (P1 vs P2): t={t12:.4f}, p={p12:.4f} ({get_significance(p12)})")
    append_report(f"T-test (P2 vs P3): t={t23:.4f}, p={p23:.4f} ({get_significance(p23)})")
    append_report("")

    # ----------------------------------------------------------------
    # ⭐ Part 2：盤中情緒 (Intraday)
    # ----------------------------------------------------------------
    append_report("⭐ Part 2：盤中情緒 (Intraday Sentiment)")
    append_report("--------------------------------------------------")

    # 2.1 Level vs Return
    append_report("[2.1] 盤中情緒水平 vs 當日市場")
    append_report(run_spearman(df_daily, 'S_Intraday', 'R_daily', 'Spearman: S_Intraday vs R_daily'))
    append_report(run_spearman(df_daily, 'PNR_Intraday', 'R_daily', 'Spearman: PNR_Intraday vs R_daily'))
    append_report("")

    # 2.2 Surge vs Return
    append_report("[2.2] 盤中情緒變化量 vs 當日市場")
    append_report(run_spearman(df_daily, 'S_Intraday_Surge', 'R_daily', 'Spearman: S_Intraday_Surge vs R_daily'))
    append_report(run_spearman(df_daily, 'PNR_Intraday_Surge', 'R_daily', 'Spearman: PNR_Intraday_Surge vs R_daily'))
    append_report("")

    # 2.3 Hourly Micro (4/7 & 4/10)
    append_report("[2.3] 關鍵日盤中微觀反應 (Hourly)")
    for date_str in ['2025-04-07', '2025-04-10']:
        df_day = df_hourly[df_hourly['Date'] == date_str]
        append_report(f"--- Date: {date_str} (N={len(df_day)}) ---")
        # (a) Hourly Level vs Return
        append_report(run_spearman(df_day, 'PNR_hour', 'R_hour', f'  Spearman: PNR_hour vs R_hour'))
        # (b) Hourly Surge vs Return
        append_report(run_spearman(df_day, 'PNR_hour_surge', 'R_hour', f'  Spearman: PNR_hour_surge vs R_hour'))
    append_report("")

    # ----------------------------------------------------------------
    # ⭐ Part 3：情緒 vs 波動度 (Volatility)
    # ----------------------------------------------------------------
    append_report("⭐ Part 3：情緒 vs 波動度 (Volatility |R|)")
    append_report("--------------------------------------------------")
    append_report(run_spearman(df_daily, 'S_Overnight_Surge', 'Abs_R_daily', 'Spearman: S_Overnight_Surge vs |R_daily|'))
    append_report(run_spearman(df_daily, 'S_Intraday_Surge', 'Abs_R_daily', 'Spearman: S_Intraday_Surge vs |R_daily|'))
    append_report(run_spearman(df_daily, 'PNR_Overnight_Surge', 'Abs_R_daily', 'Spearman: PNR_Overnight_Surge vs |R_daily|'))
    append_report("")

    # ----------------------------------------------------------------
    # ⭐ Part 4：多變量 OLS 回歸 (Bonus)
    # ----------------------------------------------------------------
    append_report("⭐ Part 4：多變量 OLS 回歸模型")
    append_report("--------------------------------------------------")
    
    # 模型 1: R_daily ~ S_Overnight + S_Intraday
    try:
        append_report("[Model 1] R_daily ~ S_Overnight + S_Intraday")
        model1 = smf.ols("R_daily ~ S_Overnight + S_Intraday", data=df_daily).fit()
        append_report(str(model1.summary().tables[1]))
    except Exception as e: append_report(f"Model 1 failed: {e}")
    
    append_report("\n")

    # 模型 2: |R_daily| ~ PNR_Overnight_Surge (測試波動度驅動因素)
    try:
        append_report("[Model 2] |R_daily| ~ PNR_Overnight_Surge")
        model2 = smf.ols("Abs_R_daily ~ PNR_Overnight_Surge", data=df_daily).fit()
        append_report(str(model2.summary().tables[1]))
    except Exception as e: append_report(f"Model 2 failed: {e}")

    print(f"\n🎉🎉🎉 最終統計報告已生成：{OUTPUT_REPORT} 🎉🎉🎉")
    print("請打開該文字檔，將數據填入你的論文表格中。")

if __name__ == "__main__":
    main()