# 檔案名稱: run_final_all_stats.py
#
# 目的：
# 1. 整合 Pos, Neg, Neu 三種情緒指標的統計檢定
# 2. 產出 ANOVA, T-test, Effect Size, Correlation 總表
# 3. 驗證「信心回歸」、「恐慌消退」與「不確定性激增」的三重奏

import pandas as pd
import numpy as np
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_prop_surge_data.csv"
OUTPUT_REPORT = "final_all_sentiment_stats_report.txt"

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
    print("🚀 啟動「全方位情緒 (Pos/Neg/Neu)」統計整合分析...\n")

    if not os.path.exists(INPUT_CSV):
        print(f"❌ 找不到 {INPUT_CSV}"); return

    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')

    # 1. 確保所有變數存在
    # 計算 Neu_prop
    if 'Neu_prop' not in df.columns:
        print("  > 計算中性情緒 (Neu_prop)...")
        if 'Count_Neu' in df.columns and 'Total' in df.columns:
            df['Neu_prop'] = df['Count_Neu'] / df['Total']
        else:
            df['Neu_prop'] = 1 - df['Pos_prop'] - df['Neg_prop']

    # 計算絕對報酬 (波動率)
    if 'R_daily' not in df.columns:
        df['R_daily'] = df['Cumulative_Return'].diff().fillna(0)
    df['Abs_R_daily'] = df['R_daily'].abs()

    # 2. 定義 Period
    conditions = [df.index.isin(P1_DATES), df.index.isin(P2_DATES), df.index.isin(P3_DATES)]
    df['Period'] = np.select(conditions, [P1_LABEL, P2_LABEL, P3_LABEL], default='Other')

    # ===================================================
    # 準備報告內容
    # ===================================================
    report_lines = []
    report_lines.append("=== PTT 情緒組成全方位統計報告 (Pos/Neg/Neu) ===\n")

    # 定義迴圈目標
    targets = [
        ('Pos_prop', '正面情緒 (Positive)'),
        ('Neg_prop', '負面情緒 (Negative)'),
        ('Neu_prop', '中性情緒 (Neutral)')
    ]

    for var_col, var_name in targets:
        header = f"分析目標：{var_name}"
        print(f"\n{'='*60}")
        print(header)
        print(f"{'='*60}")
        
        report_lines.append(f"\n{'='*60}")
        report_lines.append(header)
        report_lines.append(f"{'='*60}")

        # 準備群組資料 (移除 NaN)
        g1 = df[df['Period'] == P1_LABEL][var_col].dropna()
        g2 = df[df['Period'] == P2_LABEL][var_col].dropna()
        g3 = df[df['Period'] == P3_LABEL][var_col].dropna()

        if len(g1)<2 or len(g2)<2 or len(g3)<2:
            print("樣本不足，跳過。"); continue

        # [A] 描述性統計
        mean_txt = f"--- [A] 平均值 (Mean) ---\nP1: {g1.mean():.4f} | P2: {g2.mean():.4f} | P3: {g3.mean():.4f}"
        print(mean_txt)
        report_lines.append(mean_txt)

        # [B] 結構性改變 (ANOVA)
        f_val, p_val = stats.f_oneway(g1, g2, g3)
        eta2 = calculate_eta_squared([g1, g2, g3])
        
        anova_txt = f"\n--- [B] 結構性改變 (ANOVA) ---\nF={f_val:.4f}, p={p_val:.4f} ({get_sig(p_val)}) | η²={eta2:.4f}"
        print(anova_txt)
        report_lines.append(anova_txt)
        
        # [C] 關鍵轉折 (T-test P2 vs P3)
        t_val, p_t = stats.ttest_ind(g2, g3, equal_var=False)
        d_val = calculate_cohens_d(g2, g3)
        
        ttest_txt = f"\n--- [C] 關鍵轉折 (T-test P2 vs P3) ---\nt={t_val:.4f}, p={p_t:.4f} ({get_sig(p_t)}) | Cohen's d={d_val:.4f}"
        print(ttest_txt)
        report_lines.append(ttest_txt)

        # [D] 市場同步性 (Correlation)
        # vs Cumulative Return (Level)
        corr, p = stats.spearmanr(df[var_col], df['Cumulative_Return'])
        # vs Volatility (Abs Return)
        corr_v, p_v = stats.spearmanr(df[var_col], df['Abs_R_daily'])
        
        corr_txt = f"\n--- [D] 市場同步性 (Spearman) ---\nvs 市場趨勢 (Cum_Ret): rho={corr:.4f}, p={p:.4f} ({get_sig(p)})\nvs 市場波動 (|R_daily|): rho={corr_v:.4f}, p={p_v:.4f} ({get_sig(p_v)})"
        print(corr_txt)
        report_lines.append(corr_txt)

    # 寫入檔案
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    print(f"\n🎉🎉🎉 最終全方位統計報告已生成：{OUTPUT_REPORT} 🎉🎉🎉")

if __name__ == "__main__":
    main()