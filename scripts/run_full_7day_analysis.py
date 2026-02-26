# 檔案名稱: run_full_7day_analysis.py
#
# 目的：
# 1. [資料重構] 從資料庫抓取完整的 21 天資料 (3/27-4/16)
# 2. [平衡設計] 將 P1, P2, P3 嚴格設定為各 7 天
# 3. [完整統計] 執行 描述統計 + ANOVA + 兩兩 T-test
# 4. [格式輸出] 產出符合論文格式的完整表格

import pandas as pd
import numpy as np
import sqlite3
import scipy.stats as stats
import os
import re

# ===================================================================
# 1. 設定區
# ===================================================================
DB_PATH = "ptt_data_m.db"
SENTIMENT_TABLE = "ai_model_predictions_v2_push_only"
STOCK_CSV_PATH = "taiex_open_close.csv"
OUTPUT_FILE = "THESIS_7DAY_FULL_STATS_TABLE.txt"

# 嚴格定義日期範圍 (Total 21 Days)
# P1: 3/27(四) - 4/02(三)
P1_DATES = pd.date_range(start='2025-03-27', end='2025-04-02')
# P2: 4/03(四) - 4/09(三) [含清明連假]
P2_DATES = pd.date_range(start='2025-04-03', end='2025-04-09')
# P3: 4/10(四) - 4/16(三)
P3_DATES = pd.date_range(start='2025-04-10', end='2025-04-16')

QUERY_START = '2025-03-27'
QUERY_END = '2025-04-16'
YEAR = '2025'

# ===================================================================
# 2. 統計輔助函式
# ===================================================================
def fix_timestamp(ts_str):
    if not isinstance(ts_str, str): return pd.NaT
    match = re.match(r'(\d{2}/\d{2})\s(\d{2}:\d{2})', ts_str)
    if match:
        return pd.to_datetime(f"{YEAR}/{match.group(1)} {match.group(2)}", format='%Y/%m/%d %H:%M', errors='coerce')
    if 'T' in ts_str: return pd.to_datetime(ts_str, errors='coerce')
    return pd.to_datetime(ts_str, errors='coerce')

def get_sig(p):
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.1: return "*"
    return "" # 不顯著

def calculate_eta_squared(groups):
    """ANOVA 效果量"""
    all_data = np.concatenate(groups)
    sst = np.sum((all_data - np.mean(all_data))**2)
    ssb = sum([len(g) * (np.mean(g) - np.mean(all_data))**2 for g in groups])
    return ssb / sst if sst != 0 else 0

def calculate_cohens_d(group1, group2):
    """T-test 效果量"""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_sd = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_sd == 0: return 0
    return (np.mean(group1) - np.mean(group2)) / pooled_sd

# ===================================================================
# 3. 主程式
# ===================================================================
def main():
    print("🚀 啟動「7天平衡版 (Balanced Window)」完整統計分析...")

    # --- 1. 載入股價 ---
    print("--- 1. 載入股價 ---")
    try:
        df_stock = pd.read_csv(STOCK_CSV_PATH, usecols=['Date', '收盤價'], encoding='cp950')
        df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
        df_stock = df_stock.set_index('Date').sort_index()
        df_stock['R_daily'] = df_stock['收盤價'].pct_change()
    except:
        print("❌ 股價載入失敗"); return

    # --- 2. 載入情緒 (從 DB) ---
    print("--- 2. 載入情緒 (含假日) ---")
    conn = sqlite3.connect(DB_PATH)
    try:
        df_sent = pd.read_sql_query(f"SELECT timestamp, label_id FROM {SENTIMENT_TABLE} WHERE label_id IS NOT NULL", conn)
    except:
        print("❌ DB 讀取失敗"); conn.close(); return
    conn.close()

    df_sent['datetime'] = df_sent['timestamp'].apply(fix_timestamp)
    df_sent.dropna(subset=['datetime'], inplace=True)
    df_sent['Date'] = df_sent['datetime'].dt.date
    
    # 篩選範圍
    mask = (df_sent['datetime'] >= pd.to_datetime(QUERY_START)) & \
           (df_sent['datetime'] <= pd.to_datetime(QUERY_END) + pd.Timedelta(days=1))
    df_sent = df_sent.loc[mask].copy()

    # --- 3. 計算每日指標 ---
    daily_counts = df_sent.groupby(['Date', 'label_id']).size().unstack(fill_value=0)
    for c in [0, 1, 2]: 
        if c not in daily_counts.columns: daily_counts[c] = 0
    daily_counts.rename(columns={0: 'Count_Neg', 1: 'Count_Neu', 2: 'Count_Pos'}, inplace=True)
    
    daily_counts['Total'] = daily_counts.sum(axis=1)
    daily_counts['Pos_prop'] = daily_counts['Count_Pos'] / daily_counts['Total']
    daily_counts['Neg_prop'] = daily_counts['Count_Neg'] / daily_counts['Total']
    daily_counts['Neu_prop'] = daily_counts['Count_Neu'] / daily_counts['Total']
    
    daily_counts.index = pd.to_datetime(daily_counts.index)
    
    # 合併 (保留所有日期)
    df_final = daily_counts.join(df_stock[['R_daily']], how='left')

    # --- 4. 定義 7天 Period ---
    conditions = [
        df_final.index.isin(P1_DATES),
        df_final.index.isin(P2_DATES),
        df_final.index.isin(P3_DATES)
    ]
    df_final['Period_7day'] = np.select(conditions, ['P1', 'P2', 'P3'], default='Other')
    df_valid = df_final[df_final['Period_7day'] != 'Other'].copy()
    
    # 檢查樣本數
    n_p1 = len(df_valid[df_valid['Period_7day']=='P1'])
    n_p2 = len(df_valid[df_valid['Period_7day']=='P2'])
    n_p3 = len(df_valid[df_valid['Period_7day']=='P3'])
    
    print(f"📊 樣本數確認: P1={n_p1}, P2={n_p2}, P3={n_p3}")

    # ========================================================
    # 產生完整報表
    # ========================================================
    lines = []
    lines.append("=== 7天平衡版 (Balanced 7-Day Window) 完整統計分析 ===\n")
    lines.append(f"資料區間：{QUERY_START} ~ {QUERY_END} (共 21 天)\n")
    lines.append(f"分組設定：P1(前期) / P2(衝擊期) / P3(暫緩期) 各 7 天\n")

    # ---------------------------------------------------
    # Part 1: 描述性統計
    # ---------------------------------------------------
    lines.append(f"【表 A：描述性統計 (Mean ± Std)】")
    lines.append("-" * 100)
    
    target_cols = ['Pos_prop', 'Neg_prop', 'Neu_prop', 'Total', 'R_daily']
    display_names = ['正面佔比 (Pos)', '負面佔比 (Neg)', '中性佔比 (Neu)', '討論量 (Total)', '市場報酬 (Return)']
    
    header = f"{'變數':<20} | {'P1 (N=' + str(n_p1) + ')':<22} | {'P2 (N=' + str(n_p2) + ')':<22} | {'P3 (N=' + str(n_p3) + ')':<22}"
    lines.append(header)
    lines.append("-" * 100)

    for col, name in zip(target_cols, display_names):
        row_str = f"{name:<20} | "
        for p in ['P1', 'P2', 'P3']:
            sub = df_valid[df_valid['Period_7day'] == p][col].dropna()
            if len(sub) > 0:
                mean_val = sub.mean()
                std_val = sub.std()
                if pd.isna(std_val): std_val = 0.0
                
                if col == 'Total':
                    val_str = f"{mean_val:.1f} ± {std_val:.1f}"
                elif col == 'R_daily':
                    val_str = f"{mean_val:.4f} (n={len(sub)})"
                else:
                    val_str = f"{mean_val:.4f} ± {std_val:.4f}"
            else:
                val_str = "無資料"
            row_str += f"{val_str:<22} | "
        lines.append(row_str)
    lines.append("-" * 100 + "\n")

    # ---------------------------------------------------
    # Part 2: ANOVA (整體結構差異)
    # ---------------------------------------------------
    lines.append("【表 B：單因子變異數分析 (One-way ANOVA)】")
    lines.append("-" * 80)
    lines.append(f"{'變數':<20} | {'F-value':<10} | {'p-value':<15} | {'Effect Size (η²)':<15}")
    lines.append("-" * 80)
    
    for col, name in zip(['Pos_prop', 'Neg_prop', 'Neu_prop'], ['正面佔比', '負面佔比', '中性佔比']):
        groups = [df_valid[df_valid['Period_7day']==p][col].dropna() for p in ['P1', 'P2', 'P3']]
        if all(len(g) > 1 for g in groups):
            f_val, p_val = stats.f_oneway(*groups)
            eta2 = calculate_eta_squared(groups)
            sig = get_sig(p_val)
            lines.append(f"{name:<20} | {f_val:.4f}     | {p_val:.4f} {sig:<3}    | {eta2:.4f}")
    lines.append("-" * 80 + "\n")

    # ---------------------------------------------------
    # Part 3: T-test (兩兩比較)
    # ---------------------------------------------------
    lines.append("【表 C：兩兩獨立樣本 T 檢定 (Post-hoc Comparison)】")
    
    comparisons = [('P1 vs P2', 'P1', 'P2'), ('P2 vs P3', 'P2', 'P3'), ('P1 vs P3', 'P1', 'P3')]
    targets = [('Pos_prop', '正面佔比'), ('Neg_prop', '負面佔比'), ('Neu_prop', '中性佔比')]

    for var_col, var_name in targets:
        lines.append(f"\n--- 變數：{var_name} ---")
        lines.append(f"{'比較組合':<15} | {'T-value':<10} | {'p-value':<15} | {'Cohen\'s d':<15}")
        lines.append("-" * 65)

        for comp_name, g1_label, g2_label in comparisons:
            g1 = df_valid[df_valid['Period_7day'] == g1_label][var_col].dropna()
            g2 = df_valid[df_valid['Period_7day'] == g2_label][var_col].dropna()

            if len(g1) > 1 and len(g2) > 1:
                t_val, p_val = stats.ttest_ind(g1, g2, equal_var=False)
                d_val = calculate_cohens_d(g1, g2)
                sig = get_sig(p_val)
                lines.append(f"{comp_name:<15} | {t_val:.4f}     | {p_val:.4f} {sig:<3}    | {d_val:.4f}")
    
    # 寫入檔案
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✅ 已生成完整報表：{OUTPUT_FILE}")
    print("請檢視 P2 (含假日) 的數據，這會提供更完整的情緒反應圖譜。")

if __name__ == "__main__":
    main()