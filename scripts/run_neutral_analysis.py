# 檔案名稱: run_neutral_analysis.py
#
# 目的：
# 1. 檢驗「中性情緒佔比 (Neu_prop)」在事件期間的變化
# 2. 驗證「意見極化」假說 (是否事件發生時，中性言論變少？)

import pandas as pd
import numpy as np
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_prop_surge_data.csv"

# 研究期間
P1_LABEL = 'P1'; P2_LABEL = 'P2'; P3_LABEL = 'P3'
P1_DATES = pd.to_datetime(['2025-03-27', '2025-03-28', '2025-03-31', '2025-04-01', '2025-04-02'])
P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-08', '2025-04-09'])
P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-11', '2025-04-14', '2025-04-15', '2025-04-16'])

# ===================================================================
# 2. 輔助函式
# ===================================================================
def calculate_eta_squared(groups):
    all_data = np.concatenate(groups)
    grand_mean = np.mean(all_data)
    sst = np.sum((all_data - grand_mean)**2)
    ssb = sum([len(g) * (np.mean(g) - grand_mean)**2 for g in groups])
    if sst == 0: return 0
    return ssb / sst

def get_sig(p):
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.1: return "*"
    return "ns"

# ===================================================================
# 3. 主程式
# ===================================================================
def main():
    print("🚀 啟動「中性情緒 (Neutral Prop)」補充檢定...\n")

    if not os.path.exists(INPUT_CSV):
        print(f"❌ 找不到 {INPUT_CSV}"); return

    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')

    # 1. 計算 Neu_prop (如果 CSV 裡沒有)
    if 'Neu_prop' not in df.columns:
        print("  > 計算 Neu_prop...")
        if 'Count_Neu' in df.columns and 'Total' in df.columns:
            df['Neu_prop'] = df['Count_Neu'] / df['Total']
        else:
            # 備用方案：1 - Pos - Neg
            df['Neu_prop'] = 1 - df['Pos_prop'] - df['Neg_prop']

    # 2. 定義 Period
    conditions = [df.index.isin(P1_DATES), df.index.isin(P2_DATES), df.index.isin(P3_DATES)]
    df['Period'] = np.select(conditions, [P1_LABEL, P2_LABEL, P3_LABEL], default='Other')

    # 3. 準備群組資料
    g1 = df[df['Period'] == P1_LABEL]['Neu_prop'].dropna()
    g2 = df[df['Period'] == P2_LABEL]['Neu_prop'].dropna()
    g3 = df[df['Period'] == P3_LABEL]['Neu_prop'].dropna()

    print(f"--- [A] 描述性統計 (Mean) ---")
    print(f"P1 (前期): {g1.mean():.4f}")
    print(f"P2 (衝擊): {g2.mean():.4f}")
    print(f"P3 (暫緩): {g3.mean():.4f}")
    
    print(f"\n--- [B] ANOVA 檢定 (結構性改變) ---")
    f_val, p_val = stats.f_oneway(g1, g2, g3)
    eta2 = calculate_eta_squared([g1, g2, g3])
    print(f"F-statistic = {f_val:.4f}")
    print(f"p-value     = {p_val:.4f} ({get_sig(p_val)})")
    print(f"Eta-squared = {eta2:.4f} (解釋力)")

    print(f"\n--- [C] 相關性檢定 (Neu vs Market) ---")
    # 檢查中性情緒是否與市場走勢有關 (通常預期無關，或是與波動率負相關)
    corr, p = stats.spearmanr(df['Neu_prop'], df['Cumulative_Return'])
    print(f"Neu_prop vs Cum_Return: rho={corr:.4f}, p={p:.4f}")
    
    # 檢查中性情緒是否與「波動率」有關 (恐慌時大家選邊站，中性變少?)
    if 'R_daily' not in df.columns: df['R_daily'] = df['Cumulative_Return'].diff().fillna(0)
    df['Abs_R'] = df['R_daily'].abs()
    corr_vol, p_vol = stats.spearmanr(df['Neu_prop'], df['Abs_R'])
    print(f"Neu_prop vs |Volatility|: rho={corr_vol:.4f}, p={p_vol:.4f}")

    print("\n🎉 完成。")

if __name__ == "__main__":
    main()