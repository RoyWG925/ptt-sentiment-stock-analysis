# 檔案名稱: run_final_structure_analysis.py
#
# (✅ V2 - 修正 AttributeError 繪圖錯誤)
# 1. 改用 Pandas 計算 Z-score 以保留日期索引
# 2. 產出最終結構化數據與圖表

import pandas as pd
import sqlite3
import numpy as np
import os
import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats
import warnings

# ===================================================================
# 1. 設定區
# ===================================================================
DB_PATH = "ptt_data_m.db"
SENTIMENT_TABLE = "ai_model_predictions_v2_push_only"
STOCK_CSV_PATH = "taiex_open_close.csv"

# 輸出檔案
OUTPUT_DATA_CSV = "final_structured_data.csv"
OUTPUT_STATS_TXT = "final_structured_stats.txt"
OUTPUT_CHART_OVERNIGHT = "chart_final_overnight_impact.png"

# 研究期間
RESEARCH_START = '2025-03-27'; RESEARCH_END = '2025-04-16'; YEAR = '2025'
P1_DATES = pd.to_datetime(['2025-03-27', '2025-03-28', '2025-03-31', '2025-04-01', '2025-04-02'])
P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-08', '2025-04-09'])
P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-11', '2025-04-14', '2025-04-15', '2025-04-16'])

# ===================================================================
# 2. 資料處理核心 (Feature Engineering)
# ===================================================================

def fix_timestamp(ts_str):
    if not isinstance(ts_str, str): return pd.NaT
    match = re.match(r'(\d{2}/\d{2})\s(\d{2}:\d{2})', ts_str)
    if match: return pd.to_datetime(f"{YEAR}/{match.group(1)} {match.group(2)}", format='%Y/%m/%d %H:%M', errors='coerce')
    if 'T' in ts_str: return pd.to_datetime(ts_str, errors='coerce')
    return pd.to_datetime(ts_str, errors='coerce')

def prepare_structured_data():
    print("--- 1. 資料重構 (Split Overnight/Intraday) ---")
    
    # 1. 載入股價
    try:
        df_stock = pd.read_csv(STOCK_CSV_PATH, usecols=['Date', '收盤價'], encoding='cp950')
    except:
        print(f"錯誤：找不到 {STOCK_CSV_PATH}"); return None

    df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
    df_stock = df_stock.set_index('Date').sort_index().loc[RESEARCH_START:RESEARCH_END].copy()
    df_stock['R_daily'] = df_stock['收盤價'].pct_change().fillna(0)
    df_stock['Cumulative_Return'] = (1 + df_stock['R_daily']).cumprod() - 1
    
    # 2. 載入情緒
    conn = sqlite3.connect(DB_PATH)
    try:
        df_sent = pd.read_sql_query(f"SELECT timestamp, label_id FROM {SENTIMENT_TABLE} WHERE label_id IS NOT NULL", conn)
    except:
        print(f"錯誤：找不到資料表"); conn.close(); return None
    conn.close()
    
    df_sent['datetime'] = df_sent['timestamp'].apply(fix_timestamp)
    df_sent.dropna(subset=['datetime'], inplace=True)
    
    # 3. 定義 Session
    df_sent['hour'] = df_sent['datetime'].dt.hour
    df_sent['Session'] = np.where(df_sent['hour'] < 9, 'Overnight', 'Intraday')
    df_sent['Date'] = df_sent['datetime'].dt.date
    
    # 4. Groupby & Pivot
    daily_counts = df_sent.groupby(['Date', 'Session', 'label_id']).size().unstack(fill_value=0)
    for c in [0, 1, 2]: 
        if c not in daily_counts.columns: daily_counts[c] = 0
    daily_counts.rename(columns={0: 'Neg', 1: 'Neu', 2: 'Pos'}, inplace=True)
    
    # 分拆成兩個 DataFrame
    try:
        df_on = daily_counts.xs('Overnight', level='Session').copy()
        df_in = daily_counts.xs('Intraday', level='Session').copy()
    except KeyError:
        # 防呆：如果某天沒有 Overnight 資料
        print("警告：資料中缺少 Overnight 或 Intraday 部分數據，嘗試補零...")
        df_on = pd.DataFrame(columns=['Neg', 'Neu', 'Pos'])
        df_in = pd.DataFrame(columns=['Neg', 'Neu', 'Pos'])

    # 重新命名欄位並計算 Total
    df_on.columns = [f"{c}_ON" for c in df_on.columns]
    df_on['Total_ON'] = df_on.sum(axis=1)
    
    df_in.columns = [f"{c}_IN" for c in df_in.columns]
    df_in['Total_IN'] = df_in.sum(axis=1)
    
    # 合併回主表
    df_final = pd.merge(df_stock, df_on, left_index=True, right_index=True, how='left').fillna(0)
    df_final = pd.merge(df_final, df_in, left_index=True, right_index=True, how='left').fillna(0)
    
    # --- 5. 計算核心指標 ---
    print("--- 2. 計算核心指標 (S & PNR) ---")
    
    # (1) 極性指標 S = (P - N) / T
    df_final['S_Overnight'] = (df_final['Pos_ON'] - df_final['Neg_ON']) / df_final['Total_ON'].replace(0, np.nan)
    df_final['S_Intraday']  = (df_final['Pos_IN'] - df_final['Neg_IN']) / df_final['Total_IN'].replace(0, np.nan)
    
    # (2) P/N Ratio PNR = (P + 1) / (N + 1)
    df_final['PNR_Overnight'] = (df_final['Pos_ON'] + 1) / (df_final['Neg_ON'] + 1)
    df_final['PNR_Intraday']  = (df_final['Pos_IN'] + 1) / (df_final['Neg_IN'] + 1)
    
    # (3) Surge (差分 / 脈衝)
    df_final['S_Overnight_Surge'] = df_final['S_Overnight'].diff().fillna(0)
    df_final['PNR_Overnight_Surge'] = df_final['PNR_Overnight'].diff().fillna(0)
    
    # 定義 Period
    conditions = [df_final.index.isin(P1_DATES), df_final.index.isin(P2_DATES), df_final.index.isin(P3_DATES)]
    df_final['Period'] = np.select(conditions, ['P1', 'P2', 'P3'], default='Other')
    
    # 儲存
    df_final.to_csv(OUTPUT_DATA_CSV, encoding='utf-8-sig')
    print(f"  > 資料處理完成：{OUTPUT_DATA_CSV}")
    
    return df_final

# ===================================================================
# 3. 統計分析
# ===================================================================

def run_final_statistics(df):
    print("\n--- 3. 執行最終統計檢定 ---")
    lines = []
    lines.append("=== 最終結構化分析報告 (Structured Analysis) ===\n")
    
    # 分析 A：隔夜情緒 (Overnight) vs 市場 (Daily Return)
    lines.append("--- [分析 A] 隔夜情緒 vs. 當日市場 (Overnight Sentiment vs R_daily) ---")
    
    vars_to_test = ['S_Overnight', 'S_Overnight_Surge', 'PNR_Overnight', 'PNR_Overnight_Surge']
    
    for var in vars_to_test:
        valid_data = df.dropna(subset=[var, 'R_daily'])
        if len(valid_data) < 3: continue
        sp_corr, sp_p = stats.spearmanr(valid_data[var], valid_data['R_daily'])
        lines.append(f"{var} vs R_daily: Spearman corr={sp_corr:.4f}, p={sp_p:.4f}")
        
    lines.append("\n")
    
    # 分析 B：盤中情緒 (Intraday) vs 市場
    lines.append("--- [分析 B] 盤中情緒 vs. 當日市場 (Intraday Sentiment vs R_daily) ---")
    vars_intra = ['S_Intraday', 'PNR_Intraday']
    
    for var in vars_intra:
        valid_data = df.dropna(subset=[var, 'R_daily'])
        if len(valid_data) < 3: continue
        sp_corr, sp_p = stats.spearmanr(valid_data[var], valid_data['R_daily'])
        lines.append(f"{var} vs R_daily: Spearman corr={sp_corr:.4f}, p={sp_p:.4f}")

    lines.append("\n")
    
    # 分析 C：事件視窗平均
    lines.append("--- [分析 C] 事件視窗平均值 (Event Window Means) ---")
    cols_mean = ['R_daily', 'S_Overnight', 'PNR_Overnight', 'S_Overnight_Surge', 'PNR_Overnight_Surge']
    means = df.groupby('Period')[cols_mean].mean().reindex(['P1', 'P2', 'P3'])
    lines.append(means.to_string())

    with open(OUTPUT_STATS_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  > 統計報告已產出：{OUTPUT_STATS_TXT}")
    print("\n" + "\n".join(lines))

# ===================================================================
# 4. 繪圖 (針對 Overnight) - ✅ 已修正繪圖邏輯
# ===================================================================

def plot_final_chart(df):
    print("\n--- 4. 繪製最終圖表 (Overnight Metrics) ---")
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    
    # --- 子圖 1: S_Overnight (極性) vs Market ---
    ax1_r = ax1.twinx()
    
    # ✅ 修正：使用 Pandas 計算 Z-score 以保留索引
    # 1. 準備數據 (移除 NaN)
    valid_s = df['S_Overnight'].dropna()
    # 2. 確保有數據
    if len(valid_s) > 0:
        # 3. 計算 Z-score (手動計算或用 apply)
        s_z = (valid_s - valid_s.mean()) / valid_s.std()
        
        # 4. 對應的市場數據 (使用相同的 Index)
        valid_m = df.loc[s_z.index, 'Cumulative_Return']
        m_z = (valid_m - valid_m.mean()) / valid_m.std()
        
        ax1.plot(s_z.index, s_z, color='blue', marker='o', label='隔夜極性 (S_Overnight, Z-score)')
        ax1_r.plot(m_z.index, m_z, color='orange', marker='s', linestyle='--', label='市場累計報酬 (Z-score)')
    
    ax1.set_title('(A) 隔夜極性指標 (S_Overnight) 與市場趨勢', fontsize=14)
    ax1.axhline(0, color='black', linewidth=0.8)
    ax1.legend(loc='upper left')
    ax1_r.legend(loc='upper right')
    
    # --- 子圖 2: PNR_Overnight_Surge vs Market Daily Return ---
    ax2_r = ax2.twinx()
    width = 0.4
    
    # 處理 NaN
    pnr_surge = df['PNR_Overnight_Surge'].fillna(0)
    colors = np.where(pnr_surge >= 0, 'green', 'red')
    
    ax2.bar(df.index, pnr_surge, width, color=colors, alpha=0.6, label='PN Ratio 脈衝 (Surge)')
    ax2_r.plot(df.index, df['R_daily'], color='purple', marker='x', linewidth=2, label='當日報酬率 (R_daily)')
    
    ax2.set_title('(B) 隔夜 P/N 比值脈衝 (PNR Surge) 與 當日報酬率', fontsize=14)
    ax2.axhline(0, color='black', linewidth=0.8)
    ax2.set_ylabel('Δ P/N Ratio')
    ax2_r.set_ylabel('Daily Return')
    
    # 背景色塊
    for ax in [ax1, ax2]:
        for label, color, dates in [('P1', 'grey', P1_DATES), ('P2', 'red', P2_DATES), ('P3', 'green', P3_DATES)]:
            # 找出交集日期
            valid_dates = df.index.intersection(dates)
            if not valid_dates.empty:
                # 稍微擴大一點範圍讓色塊好看
                start = valid_dates[0] - pd.Timedelta(hours=12)
                end = valid_dates[-1] + pd.Timedelta(hours=12)
                ax.axvspan(start, end, color=color, alpha=0.1)
                
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    plt.tight_layout()
    plt.savefig(OUTPUT_CHART_OVERNIGHT, dpi=300)
    print(f"  > 圖表已儲存：{OUTPUT_CHART_OVERNIGHT}")

# ===================================================================
# 主程式
# ===================================================================
def main():
    print("🚀 啟動「最終結構化分析 (Final Structured Analysis)」...")
    
    df = prepare_structured_data()
    if df is not None:
        run_final_statistics(df)
        plot_final_chart(df)
        print("\n✅ 全部完成。這份數據就是你論文需要的最終版本。")

if __name__ == "__main__":
    main()