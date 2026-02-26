# 檔案名稱: thesis_stats.py
import pandas as pd
import numpy as np
import scipy.stats as stats
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

INPUT_CSV = os.getenv("OUTPUT_CSV", "data/processed/thesis_final_data.csv")
OUTPUT_FILE = os.getenv("STATS_OUTPUT", "data/outputs/THESIS_FULL_TABLES.txt")

def get_sig(p):
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.1: return "*"
    return ""

def bootstrap_spearman(df, x, y, n=1000):
    data = df[[x, y]].dropna()
    if len(data) < 3: return np.nan, np.nan, np.nan
    rs = []
    for _ in range(n):
        sample = data.sample(n=len(data), replace=True)
        r, _ = stats.spearmanr(sample[x], sample[y])
        if not np.isnan(r): rs.append(r)
    return np.mean(rs), np.percentile(rs, 2.5), np.percentile(rs, 97.5)

def main():
    print("🚀 [Step 2] 啟動統計分析...")
    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    
    f = open(OUTPUT_FILE, "w", encoding="utf-8")
    
    # 1. 描述統計
    f.write("【表 4-1：描述性統計】\n")
    cols = ['Pos_prop', 'Neg_prop', 'Neu_prop', 'Total', 'R_daily']
    f.write(f"{'Variable':<15} | {'P1 (Mean±Std)':<20} | {'P2 (Mean±Std)':<20} | {'P3 (Mean±Std)':<20}\n")
    f.write("-" * 80 + "\n")
    for c in cols:
        row = f"{c:<15} | "
        for p in ['P1', 'P2', 'P3']:
            sub = df[df['Period']==p][c].dropna()
            row += f"{sub.mean():.4f}±{sub.std():.4f}   | "
        f.write(row + "\n")
    f.write("\n")
    
    # 2. 卡方檢定 (結構斷裂)
    f.write("【表 4-2：卡方檢定 (結構斷裂)】\n")
    table = df.groupby('Period')[['Count_Pos', 'Count_Neu', 'Count_Neg']].sum().reindex(['P1', 'P2', 'P3'])
    chi2, p, _, _ = stats.chi2_contingency(table)
    n_total = table.sum().sum()
    cramers_v = np.sqrt(chi2 / (n_total * 2))
    f.write(f"Total N: {n_total}\nChi2: {chi2:.4f}\nP-value: {p:.4e}\nCramer's V: {cramers_v:.4f}\n\n")
    
    # 3. 相關性 (含 Bootstrap)
    f.write("【表 4-3：相關性與 Bootstrap 防禦】\n")
    pairs = [
        ('Pos_prop', 'Cumulative_Return', '正面 vs 趨勢'),
        ('Momentum_2', 'R_daily', '動能(Lag2) vs 報酬'),
        ('Vol_Ratio', 'Abs_R_daily', '量能 vs 波動')
    ]
    for x, y, name in pairs:
        r, p = stats.spearmanr(df[x], df[y], nan_policy='omit')
        mean_boot, lower, upper = bootstrap_spearman(df, x, y)
        f.write(f"{name:<15}: rho={r:.4f} ({get_sig(p)}), 95% CI=[{lower:.4f}, {upper:.4f}]\n")
        
    f.close()
    print(f"✅ 統計表格已生成：{OUTPUT_FILE}")

if __name__ == "__main__":
    main()