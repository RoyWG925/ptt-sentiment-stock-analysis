# 檔案名稱: run_hourly_stats_prop.py
#
# 目的：
# 1. [資料重構] 從 DB 重新計算「每小時」的 Pos/Neg/Neu 佔比
# 2. [微觀分析] 檢驗盤中每一小時的情緒結構是否在 P1/P2/P3 有顯著差異
# 3. [同步性] 檢驗盤中情緒佔比與「該小時報酬率」的相關性

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
PRICE_CSV = "full_hourly_price_data.csv"
OUTPUT_FILE = "THESIS_HOURLY_PROP_STATS.txt"

# 研究期間
YEAR = '2025'
P1_DATES = pd.to_datetime(['2025-03-27', '2025-03-28', '2025-03-31', '2025-04-01', '2025-04-02'])
P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-08', '2025-04-09'])
P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-11', '2025-04-14', '2025-04-15', '2025-04-16'])

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
    print("🚀 啟動「盤中小時級 (Intraday Hourly Prop)」統計分析...")

    # --- 1. 讀取情緒資料 (從 DB 重算 Prop) ---
    print("--- 1. 從 DB 計算每小時情緒佔比 ---")
    conn = sqlite3.connect(DB_PATH)
    try:
        df_sent = pd.read_sql_query(f"SELECT timestamp, label_id FROM {SENTIMENT_TABLE} WHERE label_id IS NOT NULL", conn)
    except:
        print("❌ DB 讀取失敗"); conn.close(); return
    conn.close()

    df_sent['datetime'] = df_sent['timestamp'].apply(fix_timestamp)
    df_sent.dropna(subset=['datetime'], inplace=True)
    
    # 定義 Time Block
    # 只取 09:00 ~ 13:30
    df_sent = df_sent.set_index('datetime').sort_index()
    df_sent = df_sent.between_time('09:00', '13:30').copy()
    
    # 建立 Date 與 Block
    df_sent['Date'] = df_sent.index.date
    
    # 為了與 Price CSV 對齊，我們手動切分 Block
    # 09:00-10:00, 10:00-11:00, ...
    # 這裡用 resampling 或 cut 都可以
    # 簡單起見，用 hour 判斷
    df_sent['Hour'] = df_sent.index.hour
    df_sent['Minute'] = df_sent.index.minute
    
    def get_block(h, m):
        if h == 9: return '09:00-10:00'
        if h == 10: return '10:00-11:00'
        if h == 11: return '11:00-12:00'
        if h == 12: return '12:00-13:00'
        if h == 13 and m <= 30: return '13:00-13:30'
        return None

    df_sent['Time_Block'] = df_sent.apply(lambda x: get_block(x['Hour'], x['Minute']), axis=1)
    df_sent = df_sent.dropna(subset=['Time_Block'])
    
    # Groupby 計算
    hourly_counts = df_sent.groupby(['Date', 'Time_Block', 'label_id']).size().unstack(fill_value=0)
    for c in [0, 1, 2]: 
        if c not in hourly_counts.columns: hourly_counts[c] = 0
    hourly_counts.rename(columns={0: 'Count_Neg', 1: 'Count_Neu', 2: 'Count_Pos'}, inplace=True)
    
    # 計算 Prop
    hourly_counts['Total'] = hourly_counts.sum(axis=1)
    # 避免 Total=0
    hourly_counts = hourly_counts[hourly_counts['Total'] > 0].copy()
    
    hourly_counts['Pos_prop'] = hourly_counts['Count_Pos'] / hourly_counts['Total']
    hourly_counts['Neg_prop'] = hourly_counts['Count_Neg'] / hourly_counts['Total']
    hourly_counts['Neu_prop'] = hourly_counts['Count_Neu'] / hourly_counts['Total']
    
    # 重設 index 變成 columns
    hourly_df = hourly_counts.reset_index()
    hourly_df['Date'] = pd.to_datetime(hourly_df['Date']) # 統一格式

    # --- 2. 讀取股價資料 ---
    print("--- 2. 合併每小時股價 ---")
    if not os.path.exists(PRICE_CSV):
        print("❌ 找不到股價 CSV"); return

    df_price = pd.read_csv(PRICE_CSV)
    df_price['Date'] = pd.to_datetime(df_price['Date'])
    
    # 合併
    df_merged = pd.merge(hourly_df, df_price, on=['Date', 'Time_Block'], how='inner')
    
    # 計算該小時的報酬率 (R_hour)
    # 我們用累積報酬的差分來近似
    # Groupby Date, 然後 diff Return_Close_vs_9am
    # (因為 Return_Close_vs_9am 是累計的: 10點是9-10點漲幅, 11點是9-11點漲幅)
    # 所以 11點的單小時漲幅 = 11點累計 - 10點累計
    df_merged['R_hour'] = df_merged.groupby('Date')['Return_Close_vs_9am'].diff()
    # 第一個時段 (09:00-10:00) 的 diff 會是 NaN，應該填補為原本的值
    df_merged['R_hour'] = df_merged['R_hour'].fillna(df_merged['Return_Close_vs_9am'])

    # --- 3. 定義 Period ---
    conditions = [
        df_merged['Date'].isin(P1_DATES),
        df_merged['Date'].isin(P2_DATES),
        df_merged['Date'].isin(P3_DATES)
    ]
    df_merged['Period'] = np.select(conditions, ['P1', 'P2', 'P3'], default='Other')
    df_valid = df_merged[df_merged['Period'] != 'Other'].copy()
    
    n_samples = len(df_valid)
    print(f"📊 分析樣本數: {n_samples} 個小時區塊")

    # ========================================================
    # 產生報表
    # ========================================================
    lines = []
    lines.append("=== 盤中小時級 (Intraday Hourly Prop) 完整統計報告 ===\n")
    lines.append(f"分析單位：每小時 (09:00-13:30)\n總樣本數：{n_samples}\n")

    targets = [
        ('Pos_prop', '正面佔比'),
        ('Neg_prop', '負面佔比'),
        ('Neu_prop', '中性佔比')
    ]

    # ---------------------------------------------------
    # 1. 描述性統計
    # ---------------------------------------------------
    lines.append("【表 H1：小時級描述性統計 (Mean ± Std)】")
    lines.append("-" * 90)
    lines.append(f"{'變數':<20} | {'P1':<20} | {'P2':<20} | {'P3':<20}")
    lines.append("-" * 90)
    
    for col, name in targets:
        row_str = f"{name:<20} | "
        for p in ['P1', 'P2', 'P3']:
            sub = df_valid[df_valid['Period'] == p][col].dropna()
            val_str = f"{sub.mean():.4f} ± {sub.std():.4f}"
            row_str += f"{val_str:<20} | "
        lines.append(row_str)
    lines.append("-" * 90 + "\n")

    # ---------------------------------------------------
    # 2. ANOVA (結構改變)
    # ---------------------------------------------------
    lines.append("【表 H2：小時級 ANOVA 結構差異檢定】")
    lines.append("(檢驗：情緒結構改變是否滲透到每小時的微觀層次)")
    lines.append("-" * 80)
    lines.append(f"{'變數':<20} | {'F-value':<10} | {'p-value':<15} | {'Effect Size (η²)':<15}")
    lines.append("-" * 80)
    
    for col, name in targets:
        groups = [df_valid[df_valid['Period']==p][col].dropna() for p in ['P1', 'P2', 'P3']]
        if all(len(g) > 1 for g in groups):
            f_val, p_val = stats.f_oneway(*groups)
            eta2 = calculate_eta_squared(groups)
            sig = get_sig(p_val)
            lines.append(f"{name:<20} | {f_val:.4f}     | {p_val:.4f} {sig:<3}    | {eta2:.4f}")
    lines.append("-" * 80 + "\n")

    # ---------------------------------------------------
    # 3. 相關性 (同步性)
    # ---------------------------------------------------
    lines.append("【表 H3：盤中小時級相關性 (Spearman)】")
    lines.append("(檢驗：盤中情緒是否與『該小時』的報酬率 R_hour 同步)")
    lines.append("-" * 90)
    lines.append(f"{'變數':<20} | {'P1':<20} | {'P2 (衝擊期)':<20} | {'P3':<20} | {'全期間'}")
    lines.append("-" * 90)
    
    for col, name in targets:
        row_str = f"{name:<20} | "
        
        # 分期跑相關性
        for p in ['P1', 'P2', 'P3']:
            sub = df_valid[df_valid['Period'] == p]
            if len(sub) > 2:
                c, pv = stats.spearmanr(sub[col], sub['R_hour'])
                row_str += f"{c:.3f} {get_sig(pv):<3}       | "
            else:
                row_str += "N/A                 | "
        
        # 全期間
        c_all, pv_all = stats.spearmanr(df_valid[col], df_valid['R_hour'])
        row_str += f"{c_all:.3f} {get_sig(pv_all):<3}"
        
        lines.append(row_str)
    lines.append("-" * 90)

    # 寫入檔案
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✅ 已生成小時級 (Prop) 報表：{OUTPUT_FILE}")
    print("請重點檢查 P2 衝擊期的相關性，通常在恐慌時同步性最高。")

if __name__ == "__main__":
    main()