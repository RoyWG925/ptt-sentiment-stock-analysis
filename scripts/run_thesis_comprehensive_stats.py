# 檔案名稱: run_thesis_comprehensive_stats.py
#
# 目的：執行論文最終「全方位」統計檢定 (Full Statistical Checklist)
# 涵蓋：ANOVA, T-test, Effect Size, Volatility, Lag, CCF, Robustness (Extreme removal)

import pandas as pd
import numpy as np
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_prop_surge_data.csv" # 使用包含 Pos_prop 的資料檔
OUTPUT_REPORT = "thesis_full_stats_report.txt"

# 研究期間設定
P1_LABEL = 'P1'; P2_LABEL = 'P2'; P3_LABEL = 'P3'
P1_DATES = pd.to_datetime(['2025-03-27', '2025-03-28', '2025-03-31', '2025-04-01', '2025-04-02'])
P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-08', '2025-04-09'])
P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-11', '2025-04-14', '2025-04-15', '2025-04-16'])

# ===================================================================
# 2. 統計輔助函式 (Effect Size Calculator)
# ===================================================================

def calculate_cohens_d(group1, group2):
    """計算 Cohen's d (效果量)"""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    
    # Pooled Standard Deviation
    pooled_sd = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    
    if pooled_sd == 0: return 0
    return (np.mean(group1) - np.mean(group2)) / pooled_sd

def calculate_eta_squared(groups):
    """計算 ANOVA 的 Eta-squared (η²)"""
    # Flatten all data
    all_data = np.concatenate(groups)
    grand_mean = np.mean(all_data)
    
    # Total Sum of Squares (SST)
    sst = np.sum((all_data - grand_mean)**2)
    
    # Sum of Squares Between (SSB)
    ssb = sum([len(g) * (np.mean(g) - grand_mean)**2 for g in groups])
    
    if sst == 0: return 0
    return ssb / sst

def get_sig_symbol(p):
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.1: return "*"
    return "ns"

# 全域變數用於寫入報告
report_lines = []
def log(text):
    print(text)
    report_lines.append(text)

# ===================================================================
# 3. 資料準備
# ===================================================================

def prepare_data():
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 找不到 {INPUT_CSV}"); return None

    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    
    # 確保變數存在
    # 1. 變化量 (Diff/Surge)
    df['Pos_prop_diff'] = df['Pos_prop'].diff()
    df['Neg_prop_diff'] = df['Neg_prop'].diff()
    
    # 2. 絕對報酬 (Volatility)
    # 優先使用 R_daily, 若無則用 Cumulative_Return 算
    if 'R_daily' not in df.columns:
        df['R_daily'] = df['Cumulative_Return'].diff().fillna(0)
    df['Abs_R_daily'] = df['R_daily'].abs()
    
    # 3. Period 定義
    conditions = [df.index.isin(P1_DATES), df.index.isin(P2_DATES), df.index.isin(P3_DATES)]
    df['Period'] = np.select(conditions, [P1_LABEL, P2_LABEL, P3_LABEL], default='Other')
    
    return df

# ===================================================================
# 4. 執行檢定模組
# ===================================================================

def run_group_diff_tests(df, var_name, label_desc):
    """(A)(B)(C) 執行 ANOVA, T-test, Effect Size"""
    log(f"\n--- 分析變數: {var_name} ({label_desc}) ---")
    
    # 準備群組資料
    g1 = df[df['Period'] == P1_LABEL][var_name].dropna()
    g2 = df[df['Period'] == P2_LABEL][var_name].dropna()
    g3 = df[df['Period'] == P3_LABEL][var_name].dropna()
    
    if len(g1) < 2 or len(g2) < 2 or len(g3) < 2:
        log("  > 樣本不足，跳過檢定")
        return

    # 1. ANOVA
    f_val, p_val = stats.f_oneway(g1, g2, g3)
    eta2 = calculate_eta_squared([g1, g2, g3])
    log(f"[ANOVA] P1/P2/P3: F={f_val:.4f}, p={p_val:.4f} ({get_sig_symbol(p_val)}) | η²={eta2:.4f}")
    
    # 2. T-test (P2 vs P3) - 這是重點
    t_val, p_t = stats.ttest_ind(g2, g3, equal_var=False)
    d_val = calculate_cohens_d(g2, g3)
    log(f"[T-test] P2 vs P3: t={t_val:.4f}, p={p_t:.4f} ({get_sig_symbol(p_t)}) | Cohen's d={d_val:.4f}")

def run_correlation(df, x_col, y_col, method='spearman'):
    clean_df = df[[x_col, y_col]].dropna()
    if len(clean_df) < 3: return np.nan, np.nan
    
    if method == 'spearman':
        corr, p = stats.spearmanr(clean_df[x_col], clean_df[y_col])
    else:
        corr, p = stats.pearsonr(clean_df[x_col], clean_df[y_col])
    return corr, p

# ===================================================================
# 主程式
# ===================================================================

def main():
    df = prepare_data()
    if df is None: return
    
    log("=== 論文最終全方位統計檢定報告 (Thesis Full Stats Report) ===\n")
    
    # -----------------------------------------------------------
    # (A) & (B) & (C) 事件視窗差異與效果量 (Level & Diff)
    # -----------------------------------------------------------
    log(">>> 1. 事件視窗差異檢定 (ANOVA & Effect Size)")
    # Level
    run_group_diff_tests(df, 'Pos_prop', 'Level: 正面佔比')
    run_group_diff_tests(df, 'Neg_prop', 'Level: 負面佔比')
    # Diff (Surge)
    run_group_diff_tests(df, 'Pos_prop_diff', 'Diff: 正面變化量')
    run_group_diff_tests(df, 'Neg_prop_diff', 'Diff: 負面變化量')

    # -----------------------------------------------------------
    # (D) 市場波動度 (Volatility)
    # -----------------------------------------------------------
    log("\n>>> 2. 市場波動度同步性 (|R_daily|)")
    vars_to_test = ['Pos_prop', 'Neg_prop', 'Pos_prop_diff', 'Neg_prop_diff']
    
    for v in vars_to_test:
        corr, p = run_correlation(df, v, 'Abs_R_daily', 'spearman')
        log(f"Spearman: {v} vs |R_daily| -> rho={corr:.4f}, p={p:.4f} ({get_sig_symbol(p)})")

    # -----------------------------------------------------------
    # (E) 單日 Lag 領先/落後檢定
    # -----------------------------------------------------------
    log("\n>>> 3. 單日 Lag-1 領先檢定 (Sentiment[t-1] vs Return[t])")
    # 建立 Lag 變數
    df['Pos_prop_lag1'] = df['Pos_prop'].shift(1)
    df['Neg_prop_lag1'] = df['Neg_prop'].shift(1)
    
    corr_pos, p_pos = run_correlation(df, 'Pos_prop_lag1', 'R_daily')
    log(f"Pos_prop(t-1) vs Return(t): rho={corr_pos:.4f}, p={p_pos:.4f} ({get_sig_symbol(p_pos)})")
    
    corr_neg, p_neg = run_correlation(df, 'Neg_prop_lag1', 'R_daily')
    log(f"Neg_prop(t-1) vs Return(t): rho={corr_neg:.4f}, p={p_neg:.4f} ({get_sig_symbol(p_neg)})")

    # -----------------------------------------------------------
    # (F) CCF 時間序列同步性 (-2 ~ +2)
    # -----------------------------------------------------------
    log("\n>>> 4. CCF 時間序列同步性 (Sentiment vs Cumulative Return)")
    # 使用 Cumulative Return 因為 Level 對 Level 比較容易看趨勢
    target_y = 'Cumulative_Return'
    lags = [-2, -1, 0, 1, 2]
    
    log(f"Target Y: {target_y}")
    for v in ['Pos_prop', 'Neg_prop']:
        log(f"--- {v} ---")
        for lag in lags:
            # Shift x: 如果 lag < 0 (e.g., -1)，代表 x 領先 y (x[t-1] vs y[t])
            # 在 pandas shift 中: df.shift(1) 是把數據往下移，即 t 的位置變成 t-1 的數據
            # 所以 corr(x.shift(1), y) = corr(x[t-1], y[t]) => Lag -1
            
            # 注意：CCF 的定義有時不同，這裡我們定義 Lag k 為 Corr(S[t-k], M[t])
            # k > 0: S 領先 M (S發生在前)
            # k < 0: M 領先 S (M發生在前)
            
            # 這裡我們用明確的 shift 來算
            # Shift(k): 是把數據往下移 k 格。
            # 如果我們要算 S[t-k] vs M[t]，我們要用 S.shift(k)
            
            # Lag -1 (S 領先 1 天): S.shift(1) vs M
            # Lag +1 (M 領先 1 天): S.shift(-1) vs M
            
            # 為了符合這份報告的習慣： Lag -1 代表 S 領先
            shift_val = abs(lag) if lag < 0 else -abs(lag)
            if lag == 0: shift_val = 0
            
            # 修正邏輯：
            # 我們想看 S[t+lag] vs R[t] ? 不，通常是 S[t] vs R[t+k]
            # 簡單點：
            # Lag -1: S[t-1] vs R[t] (S領先) -> S.shift(1)
            # Lag +1: S[t+1] vs R[t] (M領先) -> S.shift(-1)
            
            lag_label = ""
            if lag < 0: 
                shifted_series = df[v].shift(abs(lag))
                lag_label = f"Lag {lag} (S leads)"
            elif lag > 0:
                shifted_series = df[v].shift(-abs(lag))
                lag_label = f"Lag +{lag} (M leads)"
            else:
                shifted_series = df[v]
                lag_label = "Lag  0 (Sync)"
                
            corr, p = run_correlation(pd.DataFrame({'x': shifted_series, 'y': df[target_y]}), 'x', 'y', 'spearman')
            log(f"{lag_label:<18} | rho={corr:.4f}")

    # -----------------------------------------------------------
    # (G) 穩健性檢驗 (Robustness)
    # -----------------------------------------------------------
    log("\n>>> 5. 穩健性檢驗 (Robustness Check)")
    
    # G1. Pearson vs Spearman (Level)
    log("--- [G1] Pearson vs Spearman (Level) ---")
    for v in ['Pos_prop', 'Neg_prop']:
        c_sp, p_sp = run_correlation(df, v, 'Cumulative_Return', 'spearman')
        c_pe, p_pe = run_correlation(df, v, 'Cumulative_Return', 'pearson')
        log(f"{v}: Spearman={c_sp:.3f}** vs Pearson={c_pe:.3f} ({get_sig_symbol(p_pe)})")
        
    # G2. 排除極端值 (Drop 4/7, 4/10)
    log("\n--- [G2] 排除極端值 (Drop 4/7 & 4/10) ---")
    # 建立子集
    drop_dates = pd.to_datetime(['2025-04-07', '2025-04-10'])
    df_robust = df[~df.index.isin(drop_dates)].copy()
    log(f"Original N={len(df)}, Trimmed N={len(df_robust)}")
    
    # 重跑 Level 同步性
    for v in ['Pos_prop', 'Neg_prop']:
        c_orig, p_orig = run_correlation(df, v, 'Cumulative_Return', 'spearman')
        c_trim, p_trim = run_correlation(df_robust, v, 'Cumulative_Return', 'spearman')
        log(f"{v} vs Cum_Return: Orig={c_orig:.3f} -> Trimmed={c_trim:.3f} ({get_sig_symbol(p_trim)})")

    # 寫入檔案
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    print(f"\n🎉🎉🎉 全方位統計報告已生成：{OUTPUT_REPORT} 🎉🎉🎉")

if __name__ == "__main__":
    main()