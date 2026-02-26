# 檔案名稱: run_pairwise_ttests.py
#
# 目的：
# 1. 執行 P1-P2, P2-P3, P1-P3 的兩兩 T 檢定 (Welch's t-test)
# 2. 計算 Cohen's d 效果量以彌補小樣本 P 值的不足
# 3. 釐清結構斷裂的具體發生點

import pandas as pd
import numpy as np
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_prop_surge_data.csv"
OUTPUT_FILE = "pairwise_ttest_report.txt"

# 定義要比較的變數
TARGET_VARS = {
    'Pos_prop': '正面情緒佔比',
    'Neg_prop': '負面情緒佔比',
    'Neu_prop': '中性情緒佔比',
    'Momentum_2': '情緒動能 (Lag-2)',
    'Total': '討論量 (Volume)'
}

# 定義時期標籤
P1_LABEL = 'P1'
P2_LABEL = 'P2'
P3_LABEL = 'P3'

# 日期定義 (用於篩選)
P1_DATES = pd.to_datetime(['2025-03-27', '2025-03-28', '2025-03-31', '2025-04-01', '2025-04-02'])
P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-08', '2025-04-09'])
P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-11', '2025-04-14', '2025-04-15', '2025-04-16'])

# ===================================================================
# 2. 輔助函式
# ===================================================================
def get_sig(p):
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.1: return "*"
    return "ns"

def calculate_cohens_d(group1, group2):
    """計算 Cohen's d"""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    
    # Pooled Standard Deviation
    pooled_sd = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    
    if pooled_sd == 0: return 0
    return (np.mean(group1) - np.mean(group2)) / pooled_sd

def run_pairwise_comparison(df, var, name, p_a, p_b):
    """執行單組配對比較"""
    g1 = df[df['Period'] == p_a][var].dropna()
    g2 = df[df['Period'] == p_b][var].dropna()
    
    if len(g1) < 2 or len(g2) < 2:
        return f"{p_a} vs {p_b}: 樣本不足"

    # 使用 Welch's t-test (不假設變異數相等，對小樣本較安全)
    t_stat, p_val = stats.ttest_ind(g1, g2, equal_var=False)
    d_val = calculate_cohens_d(g1, g2)
    sig = get_sig(p_val)
    
    # 為了讓報表好看，格式化輸出
    return f"{p_a} vs {p_b} | t={t_stat:6.3f} | p={p_val:.4f} {sig:<3} | d={d_val:6.3f}"

# ===================================================================
# 3. 主程式
# ===================================================================
def main():
    print("🚀 啟動「兩兩 T 檢定 (Pairwise T-test)」分析...")
    
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 找不到 {INPUT_CSV}"); return

    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')

    # 補全變數
    if 'Neu_prop' not in df.columns:
        df['Neu_prop'] = 1 - df['Pos_prop'] - df['Neg_prop']
    if 'Momentum_2' not in df.columns:
        df['Momentum_2'] = df['Pos_prop'].diff(2)

    # 定義 Period
    conditions = [df.index.isin(P1_DATES), df.index.isin(P2_DATES), df.index.isin(P3_DATES)]
    df['Period'] = np.select(conditions, [P1_LABEL, P2_LABEL, P3_LABEL], default='Other')
    
    lines = []
    lines.append("=== 事後兩兩比較報告 (Post-hoc Pairwise T-test) ===\n")
    lines.append("說明：採用 Welch's t-test (不假設變異數相等)。")
    lines.append("顯著性：*** p<.01, ** p<.05, * p<.10\n")

    # 迴圈執行每個變數
    for var_col, var_name in TARGET_VARS.items():
        lines.append(f"--- 分析變數：{var_name} ({var_col}) ---")
        
        # 1. P1 vs P2 (衝擊效應)
        res1 = run_pairwise_comparison(df, var_col, var_name, P1_LABEL, P2_LABEL)
        lines.append(res1)
        
        # 2. P2 vs P3 (反彈效應)
        res2 = run_pairwise_comparison(df, var_col, var_name, P2_LABEL, P3_LABEL)
        lines.append(res2)
        
        # 3. P1 vs P3 (回復效應)
        res3 = run_pairwise_comparison(df, var_col, var_name, P1_LABEL, P3_LABEL)
        lines.append(res3)
        
        lines.append("") # 空行

    # 寫入檔案
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✅ 已生成報告：{OUTPUT_FILE}")
    
    # 直接印出結果預覽
    print("\n" + "\n".join(lines))

if __name__ == "__main__":
    main()