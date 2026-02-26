import pandas as pd
import numpy as np
import scipy.stats as stats
import os

INPUT_CSV = "thesis_final_data.csv"
OUTPUT_FILE = "THESIS_FULL_STATS.txt"

def get_sig(p):
    """Returns significance stars based on p-value."""
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.1: return "*"
    return ""

def calculate_eta_squared(groups):
    """Calculates Eta-squared effect size for ANOVA."""
    all_data = np.concatenate(groups)
    sst = np.sum((all_data - np.mean(all_data))**2)
    ssb = sum([len(g) * (np.mean(g) - np.mean(all_data))**2 for g in groups])
    return ssb / sst if sst != 0 else 0

def calculate_cohens_d(g1, g2):
    """Calculates Cohen's d effect size for T-tests."""
    n1, n2 = len(g1), len(g2)
    var1, var2 = np.var(g1, ddof=1), np.var(g2, ddof=1)
    pooled_sd = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    return (np.mean(g1) - np.mean(g2)) / pooled_sd if pooled_sd != 0 else 0

def bootstrap_spearman(df, x, y, n=1000):
    """Performs Bootstrap resampling for Spearman correlation."""
    # Only use trading day data (remove NaN)
    data = df[[x, y]].dropna()
    if len(data) < 3: return np.nan, np.nan, np.nan
    rs = []
    np.random.seed(42)
    for _ in range(n):
        sample = data.sample(n=len(data), replace=True)
        r, _ = stats.spearmanr(sample[x], sample[y])
        if not np.isnan(r): rs.append(r)
    return np.mean(rs), np.percentile(rs, 2.5), np.percentile(rs, 97.5)

def main():
    print("🚀 [Step 2] Starting Statistical Analysis (ANOVA, T-test, Correlation, Bootstrap)...")
    
    if not os.path.exists(INPUT_CSV):
        print(f"Error: {INPUT_CSV} not found. Please run Step 1 first.")
        return

    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    
    # Separate samples: ANOVA uses full sample (N=21), Correlations use trading days (N=13)
    df_full = df.copy()
    df_trade = df[df['Is_Trading_Day'] == True].copy()
    
    f = open(OUTPUT_FILE, "w", encoding="utf-8")
    f.write("=== Thesis Statistical Analysis Results Summary ===\n\n")

    # ------------------------------------------------
    # 4.1 Descriptive Statistics (Table 4-1)
    # ------------------------------------------------
    f.write("【Table 4-1: Descriptive Statistics by Period (N=21, Mean ± Std)】\n")
    cols = ['Pos_prop', 'Neg_prop', 'Neu_prop', 'Total', 'R_daily']
    f.write(f"{'Variable':<15} | {'P1 (N=7)':<20} | {'P2 (N=7)':<20} | {'P3 (N=7)':<20}\n")
    f.write("-" * 85 + "\n")
    for c in cols:
        row = f"{c:<15} | "
        for p in ['P1', 'P2', 'P3']:
            # Note: R_daily is NaN on non-trading days, mean() automatically ignores them
            sub = df_full[df_full['Period']==p][c]
            row += f"{sub.mean():.4f}±{sub.std():.4f}   | "
        f.write(row + "\n")
    f.write("\n")

    # ------------------------------------------------
    # 4.2 ANOVA & Post-hoc (Table 4-2, 4-3)
    # ------------------------------------------------
    f.write("【Table 4-2: Sentiment Structure ANOVA Test (N=21)】\n")
    f.write(f"{'Variable':<10} | {'F-value':<10} | {'p-value':<10} | {'Eta-sq':<10}\n")
    for c in ['Pos_prop', 'Neg_prop', 'Neu_prop']:
        groups = [df_full[df_full['Period']==p][c].dropna() for p in ['P1', 'P2', 'P3']]
        f_val, p_val = stats.f_oneway(*groups)
        eta2 = calculate_eta_squared(groups)
        f.write(f"{c:<10} | {f_val:.4f}     | {p_val:.4f}{get_sig(p_val):<3} | {eta2:.4f}\n")
    f.write("\n")

    f.write("【Table 4-3: Post-hoc Comparisons T-test (Cohen's d)】\n")
    comparisons = [('P1', 'P2'), ('P2', 'P3'), ('P1', 'P3')]
    for c in ['Pos_prop', 'Neg_prop', 'Neu_prop']:
        f.write(f"--- {c} ---\n")
        for p_a, p_b in comparisons:
            g1 = df_full[df_full['Period']==p_a][c].dropna()
            g2 = df_full[df_full['Period']==p_b][c].dropna()
            t_val, p_val = stats.ttest_ind(g1, g2, equal_var=False)
            d_val = calculate_cohens_d(g1, g2)
            f.write(f"{p_a} vs {p_b}: t={t_val:.3f}, p={p_val:.4f}{get_sig(p_val)}, d={d_val:.3f}\n")
    f.write("\n")

    # ------------------------------------------------
    # 4.3 & 4.4 & 4.5 Correlation Analysis (N=13)
    # ------------------------------------------------
    f.write("【H2, H3, H4 Correlation Tests (Spearman, N=13)】\n")
    corrs = [
        ('Pos_prop', 'Cumulative_Return', 'H2: Pos vs Market'),
        ('Neg_prop', 'Cumulative_Return', 'H2: Neg vs Market'),
        ('Neu_prop', 'Cumulative_Return', 'H2: Neu vs Market'),
        ('Pos_diff', 'R_daily', 'Diff: ΔPos vs R'),
        ('Neu_diff', 'R_daily', 'Diff: ΔNeu vs R'),
        ('Neg_diff', 'R_daily', 'Diff: ΔNeg vs R'),
        ('Momentum_2', 'R_daily', 'H3: Mom(2) vs R'),
        ('Momentum_1', 'R_daily', 'H3: Mom(1) vs R'),
        ('Momentum_3', 'R_daily', 'H3: Mom(3) vs R'),
        ('Momentum_4', 'R_daily', 'H3: Mom(4) vs R'),
        ('Momentum_5', 'R_daily', 'H3: Mom(5) vs R'),
        ('Vol_Ratio', 'Abs_R_daily', 'H4: Volume vs |R|'),
        ('Log_Volume', 'Abs_R_daily', 'Robust: LogVol vs |R|')
    ]
    for x, y, label in corrs:
        # Check if columns exist to prevent errors if Step 1 didn't generate them
        if x in df_trade.columns and y in df_trade.columns:
            r, p = stats.spearmanr(df_trade[x], df_trade[y], nan_policy='omit')
            f.write(f"{label:<20} : rho={r:.3f}, p={p:.4f}{get_sig(p)}\n")
        else:
            f.write(f"{label:<20} : Column missing, skipping...\n")
    f.write("\n")

    # ------------------------------------------------
    # 4.6 Robustness Bootstrap (Table 4-5)
    # ------------------------------------------------
    f.write("【Table 4-5: Bootstrap Robustness Test (N=1000)】\n")
    boot_targets = [
        ('Momentum_2', 'R_daily', 'Lag-2 Momentum'),
        ('Vol_Ratio', 'Abs_R_daily', 'Volume Ratio')
    ]
    for x, y, label in boot_targets:
        if x in df_trade.columns and y in df_trade.columns:
            mean_r, lower, upper = bootstrap_spearman(df_trade, x, y)
            f.write(f"{label}: Mean={mean_r:.3f}, 95% CI=[{lower:.3f}, {upper:.3f}]\n")
        else:
            f.write(f"{label}: Column missing, skipping...\n")

    f.close()
    print(f"✅ Statistical report generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()