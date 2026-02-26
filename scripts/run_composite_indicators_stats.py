# 檔案名稱: run_composite_indicators_stats.py
#
# 目的：
# 1. 檢定綜合指標：「情緒比值 (PN Ratio)」與「情緒極性 (Polarity S)」
# 2. 透過比較這些綜合指標與單一佔比(Pos_prop)的顯著性差異，
#    來證明「淨值指標」可能存在訊號抵銷 (Signal Dilution) 的問題。

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
# 2. 統計輔助函式
# ===================================================================
def calculate_eta_squared(groups):
    """計算 ANOVA 效果量 η²"""
    all_data = np.concatenate(groups)
    grand_mean = np.mean(all_data)
    sst = np.sum((all_data - grand_mean)**2)
    ssb = sum([len(g) * (np.mean(g) - grand_mean)**2 for g in groups])
    if sst == 0: return 0
    return ssb / sst

def calculate_cohens_d(group1, group2):
    """計算 T-test 效果量 Cohen's d"""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_sd = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_sd == 0: return 0
    return (np.mean(group1) - np.mean(group2)) / pooled_sd

def get_sig(p):
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.1: return "*"
    return "ns"

# ===================================================================
# 3. 主程式
# ===================================================================
def main():
    print("🚀 啟動「綜合指標 (PN Ratio & Polarity)」統計檢定...\n")

    if not os.path.exists(INPUT_CSV):
        print(f"❌ 找不到 {INPUT_CSV}"); return

    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')

    # 1. 確保/計算指標 (現場計算最保險)
    # P/N Ratio = (Pos + 1) / (Neg + 1)
    df['Calc_PN_Ratio'] = (df['Count_Pos'] + 1) / (df['Count_Neg'] + 1)
    
    # Polarity S = (Pos - Neg) / Total
    df['Calc_Polarity_S'] = (df['Count_Pos'] - df['Count_Neg']) / df['Total']

    # 市場變數
    if 'R_daily' not in df.columns:
        df['R_daily'] = df['Cumulative_Return'].diff().fillna(0)
    df['Abs_R_daily'] = df['R_daily'].abs()

    # 2. 定義 Period
    conditions = [df.index.isin(P1_DATES), df.index.isin(P2_DATES), df.index.isin(P3_DATES)]
    df['Period'] = np.select(conditions, [P1_LABEL, P2_LABEL, P3_LABEL], default='Other')

    # ===================================================
    # 迴圈執行分析
    # ===================================================
    targets = [
        ('Calc_PN_Ratio', '情緒比值 (PN Ratio)'),
        ('Calc_Polarity_S', '情緒極性 (Polarity S)')
    ]

    for var_col, var_name in targets:
        print(f"\n{'='*60}")
        print(f"分析目標：{var_name}")
        print(f"{'='*60}")

        # 準備群組
        g1 = df[df['Period'] == P1_LABEL][var_col].dropna()
        g2 = df[df['Period'] == P2_LABEL][var_col].dropna()
        g3 = df[df['Period'] == P3_LABEL][var_col].dropna()

        # [A] 描述性統計
        print(f"--- [A] 平均值 (Mean) ---")
        print(f"P1 (前期): {g1.mean():.4f}")
        print(f"P2 (衝擊): {g2.mean():.4f}")
        print(f"P3 (暫緩): {g3.mean():.4f}")

        # [B] 差異檢定 (ANOVA & T-test)
        print(f"\n--- [B] 差異檢定 ---")
        # ANOVA
        f_val, p_val = stats.f_oneway(g1, g2, g3)
        eta2 = calculate_eta_squared([g1, g2, g3])
        print(f"[ANOVA] P1/P2/P3: F={f_val:.4f}, p={p_val:.4f} ({get_sig(p_val)}) | η²={eta2:.4f}")
        
        # T-test (P2 vs P3)
        t_val, p_t = stats.ttest_ind(g2, g3, equal_var=False)
        d_val = calculate_cohens_d(g2, g3)
        print(f"[T-test] P2 vs P3: t={t_val:.4f}, p={p_t:.4f} ({get_sig(p_t)}) | Cohen's d={d_val:.4f}")

        # [C] 相關性檢定
        print(f"\n--- [C] 市場同步性檢定 ---")
        # vs Cumulative Return (Level)
        corr, p = stats.spearmanr(df[var_col], df['Cumulative_Return'])
        print(f"Spearman vs Cum_Return: rho={corr:.4f}, p={p:.4f} ({get_sig(p)})")
        
        # vs Volatility (Abs Return)
        corr_v, p_v = stats.spearmanr(df[var_col], df['Abs_R_daily'])
        print(f"Spearman vs |Volatility|: rho={corr_v:.4f}, p={p_v:.4f} ({get_sig(p_v)})")

    print("\n🎉 綜合指標檢定完成。")

if __name__ == "__main__":
    main()