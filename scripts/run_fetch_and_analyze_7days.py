# 檔案名稱: run_fetch_and_analyze_7days.py
#
# 目的：
# 1. 從原始資料庫 (DB) 重新撈取更廣泛的資料
# 2. 建構每期各 7 天 (Balanced 7-Day) 的數據集
# 3. 執行 ANOVA 並產出正式表格

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
OUTPUT_FILE = "THESIS_7DAY_ANOVA_TABLE.txt"

# 設定更廣泛的抓取區間 (為了湊滿 7 天)
QUERY_START_DATE = '2025-03-20'
QUERY_END_DATE = '2025-04-30'
YEAR = '2025'

# 定義 7 天平衡視窗 (Balanced Windows)
# 請注意：這些日期必須是「交易日」且「資料庫有資料」
P1_DATES_7 = pd.to_datetime([
    '2025-03-25', '2025-03-26', '2025-03-27', '2025-03-28', 
    '2025-03-31', '2025-04-01', '2025-04-02'
])

P2_DATES_7 = pd.to_datetime([
    '2025-04-07', '2025-04-08', '2025-04-09', '2025-04-10', 
    '2025-04-11', '2025-04-14', '2025-04-15'
])

P3_DATES_7 = pd.to_datetime([
    '2025-04-16', '2025-04-17', '2025-04-18', '2025-04-21', 
    '2025-04-22', '2025-04-23', '2025-04-24'
])

# ===================================================================
# 2. 資料處理函式
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
    return ""

def calculate_eta_squared(groups):
    all_data = np.concatenate(groups)
    grand_mean = np.mean(all_data)
    sst = np.sum((all_data - grand_mean)**2)
    ssb = sum([len(g) * (np.mean(g) - grand_mean)**2 for g in groups])
    if sst == 0: return 0
    return ssb / sst

# ===================================================================
# 3. 主程式
# ===================================================================
def main():
    print("🚀 啟動「資料重撈 + 7天平衡版 ANOVA」分析...")

    # 1. 載入股價 (範圍拉大)
    print("--- 1. 載入股價資料 ---")
    try:
        df_stock = pd.read_csv(STOCK_CSV_PATH, usecols=['Date', '收盤價'], encoding='cp950')
        df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
        df_stock = df_stock.set_index('Date').sort_index()
        # 計算報酬率
        df_stock['R_daily'] = df_stock['收盤價'].pct_change().fillna(0)
        # 篩選範圍
        df_stock = df_stock.loc[QUERY_START_DATE:QUERY_END_DATE].copy()
    except Exception as e:
        print(f"❌ 讀取股價失敗: {e}"); return

    # 2. 載入情緒 (從 DB)
    print("--- 2. 從資料庫撈取情緒資料 ---")
    conn = sqlite3.connect(DB_PATH)
    try:
        # 只抓 timestamp 和 label_id 即可，節省記憶體
        query = f"SELECT timestamp, label_id FROM {SENTIMENT_TABLE} WHERE label_id IS NOT NULL"
        df_sent = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"❌ 讀取資料庫失敗: {e}"); conn.close(); return
    conn.close()

    # 時間處理
    df_sent['datetime'] = df_sent['timestamp'].apply(fix_timestamp)
    df_sent.dropna(subset=['datetime'], inplace=True)
    df_sent['Date'] = df_sent['datetime'].dt.date
    
    # 篩選日期範圍
    mask = (df_sent['datetime'] >= pd.to_datetime(QUERY_START_DATE)) & \
           (df_sent['datetime'] <= pd.to_datetime(QUERY_END_DATE))
    df_sent = df_sent.loc[mask].copy()
    
    # 3. 計算每日指標
    print("--- 3. 計算每日情緒指標 ---")
    daily_counts = df_sent.groupby(['Date', 'label_id']).size().unstack(fill_value=0)
    # 補齊欄位
    for c in [0, 1, 2]: 
        if c not in daily_counts.columns: daily_counts[c] = 0
    daily_counts.rename(columns={0: 'Count_Neg', 1: 'Count_Neu', 2: 'Count_Pos'}, inplace=True)
    
    daily_counts['Total'] = daily_counts.sum(axis=1)
    daily_counts['Pos_prop'] = daily_counts['Count_Pos'] / daily_counts['Total']
    daily_counts['Neg_prop'] = daily_counts['Count_Neg'] / daily_counts['Total']
    daily_counts['Neu_prop'] = daily_counts['Count_Neu'] / daily_counts['Total']
    
    daily_counts.index = pd.to_datetime(daily_counts.index)
    
    # 合併股價
    df_final = pd.merge(df_stock, daily_counts, left_index=True, right_index=True, how='inner')

    # 4. 定義 7天 Period
    conditions = [
        df_final.index.isin(P1_DATES_7),
        df_final.index.isin(P2_DATES_7),
        df_final.index.isin(P3_DATES_7)
    ]
    df_final['Period_7day'] = np.select(conditions, ['P1', 'P2', 'P3'], default='Other')
    
    # 只留 P1, P2, P3 的資料
    df_valid = df_final[df_final['Period_7day'] != 'Other'].copy()
    
    # 檢查實際樣本數
    n_p1 = len(df_valid[df_valid['Period_7day']=='P1'])
    n_p2 = len(df_valid[df_valid['Period_7day']=='P2'])
    n_p3 = len(df_valid[df_valid['Period_7day']=='P3'])
    
    print(f"\n📊 實際樣本數檢查:")
    print(f"P1 (Pre):   {n_p1} 天 (目標 7)")
    print(f"P2 (Shock): {n_p2} 天 (目標 7)")
    print(f"P3 (Post):  {n_p3} 天 (目標 7)")
    
    if n_p1 < 7 or n_p2 < 7 or n_p3 < 7:
        print("⚠️ 注意：部分時期資料不足 7 天 (可能因資料庫範圍或休市)。將以現有天數計算。")

    # ========================================================
    # 產生報表
    # ========================================================
    lines = []
    lines.append("=== 7天平衡版 (Balanced 7-Day) 穩健性檢定表格 ===\n")

    # 表 4-1 格式 (描述統計)
    lines.append(f"【表：各時期情緒指標描述性統計 (7-Day Window)】")
    lines.append("-" * 90)
    
    target_cols = ['Pos_prop', 'Neg_prop', 'Neu_prop', 'Total', 'R_daily']
    display_names = ['正面佔比 (Pos)', '負面佔比 (Neg)', '中性佔比 (Neu)', '討論量 (Total)', '市場報酬 (Return)']
    
    header = f"{'變數':<20} | {'P1 (Pre, N=' + str(n_p1) + ')':<22} | {'P2 (Shock, N=' + str(n_p2) + ')':<22} | {'P3 (Post, N=' + str(n_p3) + ')':<22}"
    lines.append(header)
    lines.append("-" * 90)

    for col, name in zip(target_cols, display_names):
        row_str = f"{name:<20} | "
        for p in ['P1', 'P2', 'P3']:
            sub = df_valid[df_valid['Period_7day'] == p][col]
            if len(sub) > 0:
                mean_val = sub.mean()
                std_val = sub.std()
                if col == 'Total':
                    val_str = f"{mean_val:.1f} ± {std_val:.1f}"
                else:
                    val_str = f"{mean_val:.4f} ± {std_val:.4f}"
            else:
                val_str = "無資料"
            row_str += f"{val_str:<22} | "
        lines.append(row_str)
    lines.append("-" * 90 + "\n")

    # 表 4-2 格式 (ANOVA)
    lines.append("【表：情緒結構變動之 ANOVA 檢定 (7-Day Window)】")
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
        else:
            lines.append(f"{name:<20} | (樣本不足)")
            
    lines.append("-" * 80 + "\n")

    # 寫入檔案
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✅ 已生成文件：{OUTPUT_FILE}")

if __name__ == "__main__":
    main()