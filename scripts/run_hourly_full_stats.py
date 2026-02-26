# 檔案名稱: run_hourly_full_stats.py
#
# 目的：
# 1. 將分析維度下鑽至「每小時 (Hourly)」
# 2. 樣本數擴大至 N ~ 65 (13天 * 5小時)
# 3. 執行 ANOVA, T-test, Correlation 驗證盤中微觀結構

import pandas as pd
import numpy as np
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
SENTIMENT_CSV = "hourly_sentiment_data_PN_Ratio.csv"
PRICE_CSV = "full_hourly_price_data.csv"
OUTPUT_FILE = "THESIS_HOURLY_STATS_REPORT.txt"

# 時期定義 (交易日)
P1_DATES = pd.to_datetime(['2025-03-27', '2025-03-28', '2025-03-31', '2025-04-01', '2025-04-02'])
P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-08', '2025-04-09'])
P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-11', '2025-04-14', '2025-04-15', '2025-04-16'])

# ===================================================================
# 2. 統計輔助函式
# ===================================================================
def get_sig(p):
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.1: return "*"
    return "ns"

def calculate_eta_squared(groups):
    all_data = np.concatenate(groups)
    sst = np.sum((all_data - np.mean(all_data))**2)
    ssb = sum([len(g) * (np.mean(g) - np.mean(all_data))**2 for g in groups])
    return ssb / sst if sst != 0 else 0

def calculate_cohens_d(group1, group2):
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_sd = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_sd == 0: return 0
    return (np.mean(group1) - np.mean(group2)) / pooled_sd

# ===================================================================
# 3. 主程式
# ===================================================================
def main():
    print("🚀 啟動「盤中小時級 (Intraday Hourly)」完整統計分析...")

    # 1. 載入資料
    if not os.path.exists(SENTIMENT_CSV) or not os.path.exists(PRICE_CSV):
        print("❌ 找不到必要的 CSV 檔案"); return

    df_sent = pd.read_csv(SENTIMENT_CSV)
    df_price = pd.read_csv(PRICE_CSV)

    # 2. 資料前處理與合併
    # 統一欄位名稱
    if 'datetime' in df_price.columns and 'Date' not in df_price.columns:
        df_price['Date'] = pd.to_datetime(df_price['datetime']).dt.date
    
    # 確保 Date 格式一致 (字串或 datetime)
    df_sent['Date'] = pd.to_datetime(df_sent['Date']).dt.strftime('%Y-%m-%d')
    df_price['Date'] = pd.to_datetime(df_price['Date']).dt.strftime('%Y-%m-%d')
    
    # 合併 (Inner Join 確保只分析有開盤的時段)
    # 排除 Overnight (因為我們關注盤中波動)
    df_sent = df_sent[df_sent['Time_Block'] != 'Overnight']
    
    df = pd.merge(df_sent, df_price, on=['Date', 'Time_Block'], how='inner')
    
    # 3. 補全指標
    # 計算每小時的各類佔比 (需從原始 Count 撈，若 CSV 只有 Ratio 則需還原或直接用 Ratio)
    # 假設 hourly_sentiment_data_PN_Ratio.csv 只有 Sentiment_PN_Ratio
    # 我們需要更細的資料。如果沒有 Count，我們只能分析 PN Ratio。
    # 但為了完整性，我們嘗試計算 (P-N)/Total 若欄位允許
    
    # 如果 CSV 裡沒有 Pos/Neg count，我們主要分析 'Sentiment_PN_Ratio'
    # 並嘗試計算 'R_hour'
    
    # 計算該小時的報酬率 (R_hour)
    # 假設 Close 是該小時收盤價，Open 是該小時開盤價
    # R_hour = (Close - Open) / Open
    if 'Close' in df.columns and 'Open' in df.columns:
        df['R_hour'] = (df['Close'] - df['Open']) / df['Open']
    elif 'Return_Close_vs_9am' in df.columns:
        # 近似：用累計報酬的差分來算單小時
        df['R_hour'] = df.groupby('Date')['Return_Close_vs_9am'].diff().fillna(df['Return_Close_vs_9am'])

    # 4. 定義 Period
    df['Date_dt'] = pd.to_datetime(df['Date'])
    conditions = [
        df['Date_dt'].isin(P1_DATES),
        df['Date_dt'].isin(P2_DATES),
        df['Date_dt'].isin(P3_DATES)
    ]
    df['Period'] = np.select(conditions, ['P1', 'P2', 'P3'], default='Other')
    df_valid = df[df['Period'] != 'Other'].copy()
    
    # 樣本數統計
    n_p1 = len(df_valid[df_valid['Period']=='P1'])
    n_p2 = len(df_valid[df_valid['Period']=='P2'])
    n_p3 = len(df_valid[df_valid['Period']=='P3'])
    
    print(f"📊 小時樣本數: P1={n_p1}, P2={n_p2}, P3={n_p3} (Total N={n_p1+n_p2+n_p3})")

    # ========================================================
    # 產生報表
    # ========================================================
    lines = []
    lines.append("=== 盤中小時級 (Intraday Hourly) 統計分析報告 ===\n")
    lines.append(f"分析單位：每小時 (09:00-13:30)\n總樣本數：{n_p1+n_p2+n_p3}\n")

    # 定義要分析的變數
    # 優先分析 PN Ratio (因為這是該 CSV 的主要產出)
    target_vars = ['Sentiment_PN_Ratio', 'R_hour']
    target_names = ['情緒比值 (PN Ratio)', '小時報酬率 (R_hour)']

    # 1. 描述性統計
    lines.append("【表 H1：小時級描述性統計 (Mean ± Std)】")
    lines.append("-" * 90)
    lines.append(f"{'變數':<20} | {'P1 (N=' + str(n_p1) + ')':<22} | {'P2 (N=' + str(n_p2) + ')':<22} | {'P3 (N=' + str(n_p3) + ')':<22}")
    lines.append("-" * 90)
    
    for col, name in zip(target_vars, target_names):
        row_str = f"{name:<20} | "
        for p in ['P1', 'P2', 'P3']:
            sub = df_valid[df_valid['Period'] == p][col].dropna()
            if len(sub) > 0:
                val_str = f"{sub.mean():.4f} ± {sub.std():.4f}"
            else:
                val_str = "無資料"
            row_str += f"{val_str:<22} | "
        lines.append(row_str)
    lines.append("-" * 90 + "\n")

    # 2. ANOVA
    lines.append("【表 H2：小時級 ANOVA 結構差異檢定】")
    lines.append("-" * 80)
    lines.append(f"{'變數':<20} | {'F-value':<10} | {'p-value':<15} | {'Effect Size (η²)':<15}")
    lines.append("-" * 80)
    
    for col, name in zip(target_vars, target_names):
        groups = [df_valid[df_valid['Period']==p][col].dropna() for p in ['P1', 'P2', 'P3']]
        if all(len(g) > 1 for g in groups):
            f_val, p_val = stats.f_oneway(*groups)
            eta2 = calculate_eta_squared(groups)
            sig = get_sig(p_val)
            lines.append(f"{name:<20} | {f_val:.4f}     | {p_val:.4f} {sig:<3}    | {eta2:.4f}")
    lines.append("-" * 80 + "\n")

    # 3. T-test
    lines.append("【表 H3：小時級兩兩 T 檢定】")
    comparisons = [('P1 vs P2', 'P1', 'P2'), ('P2 vs P3', 'P2', 'P3')]
    
    for var_col, var_name in zip(target_vars, target_names):
        lines.append(f"\n--- 變數：{var_name} ---")
        for comp_name, g1_label, g2_label in comparisons:
            g1 = df_valid[df_valid['Period'] == g1_label][var_col].dropna()
            g2 = df_valid[df_valid['Period'] == g2_label][var_col].dropna()
            if len(g1) > 1 and len(g2) > 1:
                t_val, p_val = stats.ttest_ind(g1, g2, equal_var=False)
                d_val = calculate_cohens_d(g1, g2)
                sig = get_sig(p_val)
                lines.append(f"{comp_name:<10} | t={t_val:.4f} | p={p_val:.4f} {sig:<3} | d={d_val:.4f}")

    # 4. 相關性 (小時級)
    lines.append("\n【表 H4：盤中小時級相關性 (Spearman)】")
    lines.append("(驗證：盤中情緒是否與當下報酬同步?)")
    lines.append("-" * 60)
    
    # 整體相關性
    corr_all, p_all = stats.spearmanr(df_valid['Sentiment_PN_Ratio'], df_valid['R_hour'])
    sig_all = get_sig(p_all)
    lines.append(f"整體 (All Periods): rho={corr_all:.4f}, p={p_all:.4f} ({sig_all})")
    
    # 分期相關性
    for p in ['P1', 'P2', 'P3']:
        sub = df_valid[df_valid['Period'] == p]
        if len(sub) > 2:
            c, pv = stats.spearmanr(sub['Sentiment_PN_Ratio'], sub['R_hour'])
            s = get_sig(pv)
            lines.append(f"{p:<18}: rho={c:.4f}, p={pv:.4f} ({s})")
            
    lines.append("-" * 60)

    # 寫入檔案
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✅ 已生成小時級報表：{OUTPUT_FILE}")
    print("若 ANOVA 在此處顯著，代表情緒結構的改變不僅是日級別的，更是滲透到每小時的微觀層次。")

if __name__ == "__main__":
    main()