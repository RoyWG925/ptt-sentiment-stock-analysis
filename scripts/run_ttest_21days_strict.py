# 檔案名稱: run_ttest_21days_strict.py
#
# 目的：
# 1. 基於「21天嚴格版 (含假日)」資料
# 2. 執行兩兩獨立樣本 T 檢定 (Welch's T-test)
# 3. 計算 Cohen's d 效果量
# 4. 比較 P1 vs P2, P2 vs P3, P1 vs P3

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
OUTPUT_FILE = "THESIS_21DAY_TTEST_TABLE.txt"

# 嚴格定義日期範圍 (Total 21 Days)
QUERY_START = '2025-03-27'
QUERY_END = '2025-04-16'
YEAR = '2025'

# 定義 7 天平衡視窗
P1_DATES = pd.date_range(start='2025-03-27', end='2025-04-02')
P2_DATES = pd.date_range(start='2025-04-03', end='2025-04-09') # 含連假
P3_DATES = pd.date_range(start='2025-04-10', end='2025-04-16')

# ===================================================================
# 2. 輔助函式
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
    return "ns"

def calculate_cohens_d(group1, group2):
    """計算 Cohen's d 效果量"""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    
    # Pooled Standard Deviation
    pooled_sd = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    
    if pooled_sd == 0: return 0
    return (np.mean(group1) - np.mean(group2)) / pooled_sd

# ===================================================================
# 3. 主程式
# ===================================================================
def main():
    print("🚀 啟動「21天版 (含假日)」兩兩 T 檢定分析...")

    # 1. 載入情緒 (從 DB 抓取以包含假日)
    if not os.path.exists(DB_PATH):
        print(f"❌ 找不到資料庫: {DB_PATH}"); return

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

    # 2. 計算每日指標
    daily_counts = df_sent.groupby(['Date', 'label_id']).size().unstack(fill_value=0)
    for c in [0, 1, 2]: 
        if c not in daily_counts.columns: daily_counts[c] = 0
    daily_counts.rename(columns={0: 'Count_Neg', 1: 'Count_Neu', 2: 'Count_Pos'}, inplace=True)
    
    daily_counts['Total'] = daily_counts.sum(axis=1)
    daily_counts['Pos_prop'] = daily_counts['Count_Pos'] / daily_counts['Total']
    daily_counts['Neg_prop'] = daily_counts['Count_Neg'] / daily_counts['Total']
    daily_counts['Neu_prop'] = daily_counts['Count_Neu'] / daily_counts['Total']
    
    daily_counts.index = pd.to_datetime(daily_counts.index)
    
    # 3. 定義 Period
    conditions = [
        daily_counts.index.isin(P1_DATES),
        daily_counts.index.isin(P2_DATES),
        daily_counts.index.isin(P3_DATES)
    ]
    daily_counts['Period'] = np.select(conditions, ['P1', 'P2', 'P3'], default='Other')
    
    df_valid = daily_counts[daily_counts['Period'] != 'Other'].copy()

    # 檢查樣本數
    n_p1 = len(df_valid[df_valid['Period']=='P1'])
    n_p2 = len(df_valid[df_valid['Period']=='P2'])
    n_p3 = len(df_valid[df_valid['Period']=='P3'])
    
    print(f"樣本數檢查: P1={n_p1}, P2={n_p2}, P3={n_p3}")

    # ========================================================
    # 產生報表
    # ========================================================
    lines = []
    lines.append("=== 21天嚴格版 (7-Day Windows) 兩兩 T 檢定表格 ===\n")
    lines.append(f"樣本數：P1={n_p1}, P2={n_p2}, P3={n_p3} (含假日)\n")

    # 定義比較組合
    comparisons = [
        ('P1 vs P2', 'P1', 'P2', '前期 vs 衝擊期 (反應顯著性)'),
        ('P2 vs P3', 'P2', 'P3', '衝擊期 vs 暫緩期 (反彈顯著性)'),
        ('P1 vs P3', 'P1', 'P3', '前期 vs 暫緩期 (是否回歸基準)')
    ]

    targets = [
        ('Pos_prop', '正面佔比'),
        ('Neg_prop', '負面佔比'),
        ('Neu_prop', '中性佔比')
    ]

    for var_col, var_name in targets:
        lines.append(f"【變數：{var_name} ({var_col})】")
        lines.append("-" * 85)
        lines.append(f"{'比較組合':<15} | {'T-value':<10} | {'p-value':<15} | {'Cohen\'s d':<15} | {'意義'}")
        lines.append("-" * 85)

        for comp_name, g1_label, g2_label, desc in comparisons:
            g1 = df_valid[df_valid['Period'] == g1_label][var_col].dropna()
            g2 = df_valid[df_valid['Period'] == g2_label][var_col].dropna()

            if len(g1) > 1 and len(g2) > 1:
                # Welch's t-test (不假設變異數相等)
                t_val, p_val = stats.ttest_ind(g1, g2, equal_var=False)
                d_val = calculate_cohens_d(g1, g2)
                sig = get_sig(p_val)
                
                lines.append(f"{comp_name:<15} | {t_val:.4f}     | {p_val:.4f} {sig:<3}    | {d_val:.4f}          | {desc}")
            else:
                lines.append(f"{comp_name:<15} | (樣本不足)")
        
        lines.append("-" * 85 + "\n")

    # 寫入檔案
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✅ 已生成文件：{OUTPUT_FILE}")
    print("請特別關注 P1 vs P2 的顯著性 (結構斷裂證據) 以及 P2 vs P3 的 Cohen's d (反彈強度)。")

if __name__ == "__main__":
    main()