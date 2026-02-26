# 檔案名稱: run_final_defense_checks.py
#
# 目的：回應審核意見的「終極防禦」分析
# 1. 無母數檢定 (Kruskal-Wallis) 解決小樣本非常態問題
# 2. Bootstrapping (重抽樣) 驗證相關係數的信賴區間
# 3. 嚴謹化變數 (Log Volume, Abnormal Volume) 驗證結果

import pandas as pd
import numpy as np
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_prop_surge_data.csv"
OUTPUT_REPORT = "defense_stats_report.txt"

# 參數
BOOTSTRAP_N = 1000  # 重抽樣次數
CONFIDENCE_LEVEL = 0.95

# 時期定義
P1_LABEL = 'P1'; P2_LABEL = 'P2'; P3_LABEL = 'P3'

# ===================================================================
# 2. 統計輔助函式
# ===================================================================

def bootstrap_spearman(x, y, n_boot=1000):
    """執行 Bootstrapping 相關係數檢定"""
    # 移除 NaN
    data = pd.DataFrame({'x': x, 'y': y}).dropna()
    n = len(data)
    if n < 3: return np.nan, np.nan, np.nan
    
    boot_corrs = []
    np.random.seed(42) # 固定種子以求重現
    
    for _ in range(n_boot):
        # 有放回抽樣 (Resample with replacement)
        sample = data.sample(n=n, replace=True)
        # 為了避免抽樣造成常數列 (導致相關係數無法計算)，加一點點極小雜訊或忽略錯誤
        try:
            r, _ = stats.spearmanr(sample['x'], sample['y'])
            if not np.isnan(r):
                boot_corrs.append(r)
        except: pass
        
    boot_corrs = np.array(boot_corrs)
    
    # 計算信賴區間
    lower = np.percentile(boot_corrs, (1 - CONFIDENCE_LEVEL) / 2 * 100)
    upper = np.percentile(boot_corrs, (1 + CONFIDENCE_LEVEL) / 2 * 100)
    mean_corr = np.mean(boot_corrs)
    
    return mean_corr, lower, upper

def get_sig(p):
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.1: return "*"
    return "ns"

# ===================================================================
# 3. 主程式
# ===================================================================
def main():
    print("🚀 啟動「論文防禦機制 (Defense Checks)」分析...")
    
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 找不到 {INPUT_CSV}"); return

    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    
    # 確保變數
    if 'Momentum_2' not in df.columns:
        df['Momentum_2'] = df['Pos_prop'].diff(2)
    if 'R_daily' not in df.columns:
        df['R_daily'] = df['Cumulative_Return'].diff().fillna(0)
    df['Abs_R_daily'] = df['R_daily'].abs()

    # 補全 Neu_prop
    if 'Neu_prop' not in df.columns:
        df['Neu_prop'] = 1 - df['Pos_prop'] - df['Neg_prop']

    lines = []
    lines.append("=== 論文防禦統計報告 (Response to Reviewer) ===\n")

    # -----------------------------------------------------------
    # 1. 小樣本防禦：Kruskal-Wallis H Test (無母數 ANOVA)
    # -----------------------------------------------------------
    lines.append(">>> 1. 小樣本防禦：Kruskal-Wallis H Test (取代 ANOVA)")
    lines.append("(檢驗 P1/P2/P3 差異是否在不假設常態分佈下仍顯著)\n")
    
    for col in ['Pos_prop', 'Neg_prop', 'Neu_prop']:
        g1 = df[df['Period'] == P1_LABEL][col].dropna()
        g2 = df[df['Period'] == P2_LABEL][col].dropna()
        g3 = df[df['Period'] == P3_LABEL][col].dropna()
        
        # K-W Test
        h_stat, p_val = stats.kruskal(g1, g2, g3)
        sig = get_sig(p_val)
        lines.append(f"{col:<10} | H-stat={h_stat:.4f} | p={p_val:.4f} ({sig})")
    
    lines.append("\n" + "-"*60 + "\n")

    # -----------------------------------------------------------
    # 2. 相關性防禦：Bootstrapping CI (95% 信賴區間)
    # -----------------------------------------------------------
    lines.append(f">>> 2. 相關性防禦：Bootstrapping (N={BOOTSTRAP_N}, 95% CI)")
    lines.append("(檢驗相關係數是否僅由極端值驅動，若區間不含 0 則為穩健)\n")
    
    targets = [
        ('Momentum_2', 'R_daily', '動能(Lag-2) vs 報酬'),
        ('Total', 'Abs_R_daily', '討論量 vs 波動率')
    ]
    
    for x_col, y_col, label in targets:
        mean_r, lower, upper = bootstrap_spearman(df[x_col], df[y_col], BOOTSTRAP_N)
        is_robust = "✅ Robust" if (lower > 0 or upper < 0) else "⚠️ Weak"
        lines.append(f"{label}:")
        lines.append(f"  Bootstrap Mean Rho = {mean_r:.4f}")
        lines.append(f"  95% CI = [{lower:.4f}, {upper:.4f}] -> {is_robust}")
    
    lines.append("\n" + "-"*60 + "\n")

    # -----------------------------------------------------------
    # 3. 變數嚴謹度防禦：Log-Volume & Abnormal Volume
    # -----------------------------------------------------------
    lines.append(">>> 3. 變數嚴謹度：Log & Abnormal Volume")
    lines.append("(解決量能變異數過大 (Heteroskedasticity) 問題)\n")
    
    # 3.1 Log Volume (對數)
    df['Log_Total'] = np.log1p(df['Total']) # log(x+1) 避免 0
    
    # 3.2 Abnormal Volume (標準化異常量)
    # 定義：(今日量 - 過去5日均量) / 過去5日標準差 (這裡因樣本少，用 P1 均值/標準差代替)
    p1_mean = df[df['Period'] == P1_LABEL]['Total'].mean()
    p1_std = df[df['Period'] == P1_LABEL]['Total'].std()
    df['Abnormal_Vol'] = (df['Total'] - p1_mean) / p1_std
    
    # 重新檢定相關性
    corr_log, p_log = stats.spearmanr(df['Log_Total'], df['Abs_R_daily'])
    corr_abn, p_abn = stats.spearmanr(df['Abnormal_Vol'], df['Abs_R_daily'])
    
    lines.append(f"Original Volume vs |R|: (參考前值)")
    lines.append(f"Log Volume      vs |R|: rho={corr_log:.4f}, p={p_log:.4f} ({get_sig(p_log)})")
    lines.append(f"Abnormal Volume vs |R|: rho={corr_abn:.4f}, p={p_abn:.4f} ({get_sig(p_abn)})")

    # 寫入檔案
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"\n✅ 防禦報告已生成：{OUTPUT_REPORT}")
    print("請查看內容，若 K-W 檢定與 Bootstrap CI 均通過，你的論文就安全了。")

if __name__ == "__main__":
    main()