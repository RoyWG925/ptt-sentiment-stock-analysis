# 檔案名稱: run_hourly_correlation_matrix.py
#
# 目的：
# 1. [微觀探索] 盤中小時級 (Hourly) 情緒與市場的同步性
# 2. [指標比較] 比較 Prop, PN Ratio, Polarity S 哪個跟市場最貼合
# 3. [波動驗證] 同步檢查情緒與「波動率 (|R|)」的關係

import pandas as pd
import numpy as np
import sqlite3
import scipy.stats as stats
import matplotlib.pyplot as plt
import seaborn as sns
import os
import re

# ===================================================================
# 1. 設定區
# ===================================================================
DB_PATH = "ptt_data_m.db"
SENTIMENT_TABLE = "ai_model_predictions_v2_push_only"
PRICE_CSV = "full_hourly_price_data.csv"
OUTPUT_REPORT = "hourly_correlation_matrix.txt"
OUTPUT_CHART = "hourly_correlation_heatmap.png"

# 研究期間
YEAR = '2025'
P1_DATES = pd.to_datetime(['2025-03-27', '2025-03-28', '2025-03-31', '2025-04-01', '2025-04-02'])
P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-08', '2025-04-09'])
P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-11', '2025-04-14', '2025-04-15', '2025-04-16'])

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

# ===================================================================
# 3. 主程式
# ===================================================================
def main():
    print("🚀 啟動「盤中微觀同步性 (Hourly Synchronicity)」全指標掃描...")

    # --- 1. 從 DB 撈取並計算每小時指標 ---
    print("--- 1. 計算每小時多重情緒指標 ---")
    conn = sqlite3.connect(DB_PATH)
    try:
        df_sent = pd.read_sql_query(f"SELECT timestamp, label_id FROM {SENTIMENT_TABLE} WHERE label_id IS NOT NULL", conn)
    except:
        print("❌ DB 讀取失敗"); conn.close(); return
    conn.close()

    df_sent['datetime'] = df_sent['timestamp'].apply(fix_timestamp)
    df_sent.dropna(subset=['datetime'], inplace=True)
    
    # 鎖定盤中 09:00 - 13:30
    df_sent = df_sent.set_index('datetime').sort_index()
    df_sent = df_sent.between_time('09:00', '13:30').copy()
    
    # 建立 Time Block
    df_sent['Date'] = df_sent.index.date
    df_sent['Hour'] = df_sent.index.hour
    
    def get_block(h):
        if h == 9: return '09:00-10:00'
        if h == 10: return '10:00-11:00'
        if h == 11: return '11:00-12:00'
        if h == 12: return '12:00-13:00'
        return '13:00-13:30' # 13點以後都算

    df_sent['Time_Block'] = df_sent['Hour'].apply(get_block)
    
    # 統計各類數量
    hourly_counts = df_sent.groupby(['Date', 'Time_Block', 'label_id']).size().unstack(fill_value=0)
    for c in [0, 1, 2]: 
        if c not in hourly_counts.columns: hourly_counts[c] = 0
    hourly_counts.rename(columns={0: 'Neg', 1: 'Neu', 2: 'Pos'}, inplace=True)
    
    # 計算各種指標
    hourly_counts['Total'] = hourly_counts.sum(axis=1)
    hourly_counts = hourly_counts[hourly_counts['Total'] > 0].copy()
    
    # A. 比例類 (Proportions)
    hourly_counts['Pos_prop'] = hourly_counts['Pos'] / hourly_counts['Total']
    hourly_counts['Neg_prop'] = hourly_counts['Neg'] / hourly_counts['Total']
    hourly_counts['Neu_prop'] = hourly_counts['Neu'] / hourly_counts['Total']
    
    # B. 比值類 (Ratios)
    hourly_counts['PN_Ratio'] = (hourly_counts['Pos'] + 1) / (hourly_counts['Neg'] + 1)
    
    # C. 極性類 (Polarity)
    hourly_counts['Polarity_S'] = (hourly_counts['Pos'] - hourly_counts['Neg']) / hourly_counts['Total']
    
    # D. 量能類 (Volume)
    hourly_counts['Volume'] = hourly_counts['Total']

    # 轉回 DataFrame
    df_metrics = hourly_counts.reset_index()
    df_metrics['Date'] = pd.to_datetime(df_metrics['Date'])

    # --- 2. 結合股價 ---
    print("--- 2. 結合每小時市場數據 ---")
    if not os.path.exists(PRICE_CSV):
        print("❌ 找不到股價 CSV"); return
        
    df_price = pd.read_csv(PRICE_CSV)
    df_price['Date'] = pd.to_datetime(df_price['Date'])
    
    df = pd.merge(df_metrics, df_price, on=['Date', 'Time_Block'], how='inner')
    
    # 計算小時報酬 (R_hour)
    df['R_hour'] = df.groupby('Date')['Return_Close_vs_9am'].diff().fillna(df['Return_Close_vs_9am'])
    
    # 計算小時波動 (|R_hour|)
    df['Abs_R_hour'] = df['R_hour'].abs()

    # --- 3. 定義時期 ---
    conditions = [
        df['Date'].isin(P1_DATES),
        df['Date'].isin(P2_DATES),
        df['Date'].isin(P3_DATES)
    ]
    df['Period'] = np.select(conditions, ['P1', 'P2', 'P3'], default='Other')
    df = df[df['Period'] != 'Other'].copy()

    # ========================================================
    # 執行相關性分析
    # ========================================================
    print("--- 3. 執行 Spearman 相關性矩陣 ---")
    
    # 定義要測試的情緒變數
    sent_vars = ['Pos_prop', 'Neg_prop', 'Neu_prop', 'PN_Ratio', 'Polarity_S', 'Volume']
    sent_labels = ['正面佔比', '負面佔比', '中性佔比', 'PN比值', '淨情緒(S)', '討論量']
    
    # 定義要測試的市場變數
    mkt_vars = ['R_hour', 'Abs_R_hour']
    mkt_labels = ['報酬率(R)', '波動率(|R|)']
    
    results = []
    
    # 儲存給 Heatmap 用的資料
    heatmap_data = pd.DataFrame(index=[f"{l}" for l in sent_labels], columns=mkt_labels)

    lines = []
    lines.append("=== 盤中小時級 (Hourly) 同步性相關分析 ===\n")
    
    # 針對「全期間」跑一次
    lines.append(f"【全期間 (N={len(df)})】")
    for sv, sl in zip(sent_vars, sent_labels):
        row_res = []
        for mv, ml in zip(mkt_vars, mkt_labels):
            r, p = stats.spearmanr(df[sv], df[mv])
            sig = get_sig(p)
            lines.append(f"{sl:<10} vs {ml:<10} | rho={r:.4f} {sig}")
            
            # 存入 Heatmap (只存 R_hour 的相關性，比較直觀)
            if mv == 'R_hour':
                heatmap_data.loc[sl, '報酬率(R)'] = r
            elif mv == 'Abs_R_hour':
                heatmap_data.loc[sl, '波動率(|R|)'] = r
        lines.append("-" * 40)
    
    # 針對「各時期」跑
    heatmap_p2 = heatmap_data.copy() # 專門存 P2 的數據
    
    for period in ['P1', 'P2', 'P3']:
        sub_df = df[df['Period'] == period]
        lines.append(f"\n【{period} 時期 (N={len(sub_df)})】")
        
        for sv, sl in zip(sent_vars, sent_labels):
            for mv, ml in zip(mkt_vars, mkt_labels):
                r, p = stats.spearmanr(sub_df[sv], sub_df[mv])
                sig = get_sig(p)
                lines.append(f"{sl:<10} vs {ml:<10} | rho={r:.4f} {sig}")
                
                if period == 'P2':
                    if mv == 'R_hour': heatmap_p2.loc[sl, '報酬率(R)'] = r
                    if mv == 'Abs_R_hour': heatmap_p2.loc[sl, '波動率(|R|)'] = r
        lines.append("-" * 40)

    # 寫入報告
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  > 文字報告已存：{OUTPUT_REPORT}")

    # ========================================================
    # 繪製熱力圖 (P2 衝擊期專用 - 因為這裡最重要)
    # ========================================================
    print("--- 4. 繪製熱力圖 (P2 衝擊期) ---")
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

    plt.figure(figsize=(8, 6))
    sns.heatmap(heatmap_p2.astype(float), annot=True, cmap='coolwarm', center=0, fmt=".2f", linewidths=.5)
    plt.title('P2 衝擊期：盤中情緒與市場之微觀同步性 (Spearman)', fontsize=14)
    plt.tight_layout()
    plt.savefig(OUTPUT_CHART, dpi=300)
    print(f"  > 熱力圖已存：{OUTPUT_CHART}")
    
    print("\n🎉🎉🎉 小時級探索完成！請查看報告與熱力圖。 🎉🎉🎉")

if __name__ == "__main__":
    main()