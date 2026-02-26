# 檔案名稱: run_full_analysis_PN_Ratio.py
#
# 目的：(「P/N Ratio」總分析腳本)
# 一次執行，產出所有使用「(P+1)/(N+1)」新公式的分析結果
# 包含：圖表 A, B, C, 以及 RQ2 和 RQ4 的所有統計數據

import pandas as pd
import sqlite3
import numpy as np
import os
import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats
from statsmodels.tsa.stattools import grangercausalitytests
from tqdm import tqdm
import warnings

# ===================================================================
# 1. 全域設定區
# ===================================================================
# --- 資料庫與 TXT 來源 ---
DB_PATH = "ptt_data_m.db"
SENTIMENT_TABLE = "ai_model_predictions_v2_push_only"
STOCK_CSV_PATH = "taiex_open_close.csv"
PRICE_CSV_PATH_HOURLY = "full_hourly_price_data.csv" # 來自 preprocess_hourly_prices.py

# --- 研究期間 ---
RESEARCH_START_DATE = '2025-03-27'
RESEARCH_END_DATE = '2025-04-16'
RESEARCH_YEAR = '2025' 

# --- 輸出路徑 (所有 P/N Ratio 的檔案都會有 _PNR 後綴) ---
OUTPUT_DAILY_DATA_CSV = "event_study_final_data_PN_Ratio.csv"
OUTPUT_HOURLY_DATA_CSV = "hourly_sentiment_data_PN_Ratio.csv"

OUTPUT_CHART_A = "chart_A_V_shape_PN_Ratio.png"
OUTPUT_CHART_B1 = "chart_B1_micro_4_10_PN_Ratio.png"
OUTPUT_CHART_B2 = "chart_B2_micro_4_07_PN_Ratio.png"

# --- 繪圖 P1, P2, P3 區間 ---
P1_DATES = pd.to_datetime(['2025-03-27', '2025-03-28', '2025-03-31', '2025-04-01', '2025-04-02'])
P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-08', '2025-04-09'])
P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-11', '2025-04-14', '2025-04-15', '2025-04-16'])
P1_CHOICE, P2_CHOICE, P3_CHOICE = 'P1 (前期)', 'P2 (衝擊)', 'P3 (暫緩)'

# --- 圖表 B 繪圖設定 ---
EVENT_1_DATE_STR = '2025-04-07'; EVENT_1_TITLE = '王牌圖表 B-2 (P/N Ratio)：4/7 (恐慌日) 微觀機制'
EVENT_1_VLINE_COLOR = 'red'; EVENT_1_VLINE_LABEL = '9:00 開盤 / 4 天恐慌釋放'
EVENT_2_DATE_STR = '2025-04-10'; EVENT_2_TITLE = '王牌圖表 B-1 (P/N Ratio)：4/10 (暫緩日) 微觀機制'
EVENT_2_VLINE_COLOR = 'green'; EVENT_2_VLINE_LABEL = '9:00 開盤 / 宣布暫緩'

# ===================================================================
# 2. 核心函式庫 (Functions)
# ===================================================================

# --- A. 核心公式 ---
def calculate_PN_Ratio(series):
    """
    (✅ 新公式) 計算 P/N Ratio
    (0=Negative, 1=Neutral, 2=Positive)
    """
    if series.empty: return np.nan
    
    n_negative = (series == 0).sum()
    n_positive = (series == 2).sum()
    
    # 拉普拉斯平滑 (Laplace Smoothing)，避免 N=0 時除以零
    return (n_positive + 1) / (n_negative + 1)

# --- B. 資料載入 ---
def load_base_data(db_path, sentiment_table, stock_csv_path):
    """載入 1. 交易日 2. V2 情緒資料"""
    print("--- 正在載入基礎資料 (交易日 & V2 推文)... ---")
    # 載入交易日
    try:
        df_stock = pd.read_csv(stock_csv_path, usecols=['Date', '收盤價'], encoding='cp950', skipinitialspace=True)
    except FileNotFoundError:
        print(f"錯誤：找不到股價檔案 '{stock_csv_path}'。"); return None, None
    df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
    df_stock = df_stock.set_index('Date').sort_index()
    df_stock['Close'] = df_stock['收盤價']
    df_stock['R_Daily'] = df_stock['Close'].pct_change()
    df_stock = df_stock.loc[RESEARCH_START_DATE:RESEARCH_END_DATE].copy()
    df_stock['R_Daily'].fillna(0, inplace=True)
    df_stock['Cumulative_Return'] = (1 + df_stock['R_Daily']).cumprod() - 1
    trading_days = df_stock.index
    print(f"  > 成功載入 {len(trading_days)} 個交易日。")

    # 載入 V2 情緒資料
    conn = sqlite3.connect(db_path)
    query = f"SELECT timestamp, label_id FROM {sentiment_table} WHERE label_id IS NOT NULL"
    try:
        df_sentiment = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"錯誤：讀取資料庫表格 '{sentiment_table}' 失敗。 {e}"); conn.close(); return None, None
    conn.close()
    
    # (輔助函式) 修復時間戳記
    def fix_timestamp(ts_str):
        if not isinstance(ts_str, str): return pd.NaT
        match = re.match(r'(\d{2}/\d{2})\s(\d{2}:\d{2})', ts_str)
        if match:
            datetime_str = f"{RESEARCH_YEAR}/{match.group(1)} {match.group(2)}"
            return pd.to_datetime(datetime_str, format='%Y/%m/%d %H:%M', errors='coerce')
        if 'T' in ts_str: return pd.to_datetime(ts_str, errors='coerce')
        return pd.to_datetime(ts_str, errors='coerce')
        
    df_sentiment['datetime'] = df_sentiment['timestamp'].apply(fix_timestamp)
    df_sentiment.dropna(subset=['datetime'], inplace=True)
    df_sentiment = df_sentiment.set_index('datetime').sort_index()
    print(f"  > V2 PTT 推文資料處理完成，共 {len(df_sentiment)} 筆。")
    
    return df_stock, df_sentiment

# --- C. PART 1 邏輯：建立「每日」資料 ---
def create_daily_data_PN_Ratio(df_stock, df_sentiment):
    print(f"\n========== PART 1: 建立「每日」資料 ({OUTPUT_DAILY_DATA_CSV}) ==========")
    trading_days = df_stock.index
    overnight_scores = []
    intraday_scores = []

    for i in range(len(trading_days)):
        T = trading_days[i]
        
        # 盤中 (T 09:01 ~ T 13:30)
        start_intra = T.replace(hour=9, minute=1, second=0); end_intra = T.replace(hour=13, minute=30, second=0)
        df_intra = df_sentiment.loc[start_intra:end_intra]
        score_intra = calculate_PN_Ratio(df_intra['label_id']) # ✅ 新公式
        intraday_scores.append(score_intra)

        # 隔夜 (T-1 13:31 ~ T 09:00)
        if i == 0: overnight_scores.append(np.nan); continue
        T_minus_1 = trading_days[i-1] 
        start_overnight = T_minus_1.replace(hour=13, minute=31, second=0)
        end_overnight = T.replace(hour=9, minute=0, second=0)
        df_overnight = df_sentiment.loc[start_overnight:end_overnight]
        score_overnight = calculate_PN_Ratio(df_overnight['label_id']) # ✅ 新公式
        overnight_scores.append(score_overnight)

    df_final = df_stock.copy()
    df_final['S_Overnight_PN_Ratio'] = overnight_scores
    df_final['S_Intraday_PN_Ratio'] = intraday_scores
    
    df_final.to_csv(OUTPUT_DAILY_DATA_CSV, encoding='utf-8-sig')
    print(f"  > 成功儲存至: {OUTPUT_DAILY_DATA_CSV}")
    return df_final

# --- D. PART 2 邏輯：繪製「圖表 A」 ---
def plot_chart_A_PN_Ratio(df):
    print(f"\n========== PART 2: 繪製「圖表 A」 ({OUTPUT_CHART_A}) ==========")
    df_plot = df.dropna(subset=['S_Overnight_PN_Ratio']) # 移除第一天
    
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except Exception: print("  > 警告：中文字體設定失敗。")

    fig, ax1 = plt.subplots(figsize=(16, 8)); ax2 = ax1.twinx() 
    
    # Y1 (左) - 情緒
    ax1.plot(df_plot.index, df_plot['S_Overnight_PN_Ratio'], color='blue', marker='o', label='隔夜情緒 P/N Ratio (S_Overnight_PN_Ratio)')
    ax1.set_ylabel('隔夜情緒 P/N Ratio (藍線)', color='blue', fontsize=14)
    ax1.tick_params(axis='y', labelcolor='blue')
    ax1.axhline(1, color='grey', linestyle=':', linewidth=1) # 增加 P/N = 1 的基準線

    # Y2 (右) - 市場
    ax2.plot(df_plot.index, df_plot['Cumulative_Return'], color='orange', marker='s', linestyle='--', label='累計市場報酬率 (Cumulative Return)')
    ax2.set_ylabel('累計市場報酬率 (Cumulative Return, 橘線)', color='orange', fontsize=14)
    ax2.tick_params(axis='y', labelcolor='orange')
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1%}'))

    # X 軸
    ax1.set_xlabel('交易日 (Trading Date)', fontsize=14); ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax1.set_xticks(df_plot.index); plt.setp(ax1.get_xticklabels(), rotation=45, ha='right'); ax1.grid(axis='x', linestyle=':', alpha=0.5) 

    # 背景著色
    ax1.axvspan(P1_DATES[0], P1_DATES[-1], color='grey', alpha=0.2, label='P1: 前期')
    ax1.axvspan(P2_DATES[0], P2_DATES[-1], color='red', alpha=0.2, label='P2: 衝擊期')
    ax1.axvspan(P3_DATES[0], P3_DATES[-1], color='green', alpha=0.2, label='P3: 暫緩期')

    # 事件標註
    ax1.axvline(pd.to_datetime(EVENT_1_DATE_STR), color='red', linestyle='--', linewidth=1.5, label='4/7 關稅衝擊')
    ax1.axvline(pd.to_datetime(EVENT_2_DATE_STR), color='green', linestyle='--', linewidth=1.5, label='4/10 宣布暫緩')

    # 標題與圖例
    plt.title('核心圖表 A (P/N Ratio)：PTT 隔夜情緒 vs. 累計市場報酬率', fontsize=18, pad=20)
    lines, labels = ax1.get_legend_handles_labels(); lines2, labels2 = ax2.get_legend_handles_labels()
    unique_labels = {}; 
    for line, label in zip(lines + lines2, labels + labels2):
        if label not in unique_labels: unique_labels[label] = line
    fig.legend(unique_labels.values(), unique_labels.keys(), loc='lower center', bbox_to_anchor=(0.5, -0.15), ncol=4, fontsize=12)

    plt.tight_layout(rect=[0, 0.05, 1, 0.95]); plt.savefig(OUTPUT_CHART_A, dpi=300, bbox_inches='tight')
    print(f"  > ✅ 成功儲存至: {OUTPUT_CHART_A}")

# --- E. PART 3 邏輯：執行「每日統計」 ---
def run_daily_stats_PN_Ratio(df_full):
    print(f"\n========== PART 3: 執行「每日統計 (RQ2)」(P/N Ratio) ==========")
    
    # 建立 Period 欄位
    conditions = [df_full.index.isin(P1_DATES), df_full.index.isin(P2_DATES), df_full.index.isin(P3_DATES)]
    choices = [P1_CHOICE, P2_CHOICE, P3_CHOICE]
    df_full['Period'] = np.select(conditions, choices, default='Other')
    
    # --- S_Overnight_PN_Ratio (N=12) ---
    print("\n--- 3a. 分析 S_Overnight_PN_Ratio ---")
    df_overnight = df_full.dropna(subset=['S_Overnight_PN_Ratio', 'R_Daily'])
    print(f"  > (N={len(df_overnight)})")
    run_statistical_tests(df_overnight, 'S_Overnight_PN_Ratio', 'R_Daily')

    # --- S_Intraday_PN_Ratio (N=13) ---
    print(f"\n--- 3b. 分析 S_Intraday_PN_Ratio (穩健性檢定) ---")
    df_intraday = df_full.dropna(subset=['S_Intraday_PN_Ratio', 'R_Daily'])
    print(f"  > (N={len(df_intraday)})")
    run_statistical_tests(df_intraday, 'S_Intraday_PN_Ratio', 'R_Daily')

def run_statistical_tests(df, sentiment_var, return_var):
    """(輔助函式) 執行 圖表 C, ANOVA, T-test, U-test, Correlation"""
    
    # 1. 圖表 C
    grouped = df.groupby('Period')
    agg_s = grouped[sentiment_var].agg(N='count', Mean='mean', Std='std')
    agg_r = grouped[return_var].agg(N='count', Mean='mean', Std='std')
    chart_c = pd.concat([agg_s, agg_r], axis=1, keys=[sentiment_var, return_var])
    chart_c = chart_c.reindex([P1_CHOICE, P2_CHOICE, P3_CHOICE])
    print("\n圖表 C：P1, P2, P3 描述性統計")
    print("=====================================================================")
    print(chart_c.to_string(float_format="%.4f"))
    print("=====================================================================")
    
    # 2. 準備統計資料
    warnings.filterwarnings("ignore", category=stats.ConstantInputWarning)
    s_p1 = df[df['Period'] == P1_CHOICE][sentiment_var]; s_p2 = df[df['Period'] == P2_CHOICE][sentiment_var]; s_p3 = df[df['Period'] == P3_CHOICE][sentiment_var]
    r_p1 = df[df['Period'] == P1_CHOICE][return_var]; r_p2 = df[df['Period'] == P2_CHOICE][return_var]; r_p3 = df[df['Period'] == P3_CHOICE][return_var]

    # 3. 執行統計
    print("\n推論統計結果")
    print("=============================================================")
    print("1. ANOVA (三組總體比較)")
    f_s, p_s = stats.f_oneway(s_p1, s_p2, s_p3)
    f_r, p_r = stats.f_oneway(r_p1, r_p2, r_p3)
    print(f"   - {sentiment_var}: F-statistic = {f_s: .4f}, p-value = {p_s: .4f}")
    print(f"   - {return_var}:          F-statistic = {f_r: .4f}, p-value = {p_r: .4f}")

    print("\n2. Welch's T-test (成對比較, equal_var=False)")
    t_s_12, p_s_12 = stats.ttest_ind(s_p1, s_p2, equal_var=False); t_s_23, p_s_23 = stats.ttest_ind(s_p2, s_p3, equal_var=False)
    print(f"   {sentiment_var}:")
    print(f"   - P1 vs P2: t-statistic = {t_s_12: .4f}, p-value = {p_s_12: .4f}")
    print(f"   - P2 vs P3: t-statistic = {t_s_23: .4f}, p-value = {p_s_23: .4f}")
    t_r_12, p_r_12 = stats.ttest_ind(r_p1, r_p2, equal_var=False); t_r_23, p_r_23 = stats.ttest_ind(r_p2, r_p3, equal_var=False)
    print(f"\n   {return_var}:")
    print(f"   - P1 vs P2: t-statistic = {t_r_12: .4f}, p-value = {p_r_12: .4f}")
    print(f"   - P2 vs P3: t-statistic = {t_r_23: .4f}, p-value = {p_r_23: .4f}")

    print("\n3. Mann-Whitney U Test (嚴謹性檢定)")
    u_stat, p_val_u = stats.mannwhitneyu(r_p2, r_p3, alternative='two-sided')
    print(f"   - {return_var} P2 vs P3: U-statistic = {u_stat: .4f}, p-value = {p_val_u: .4f}")

    print("\n4. 相關性檢定 (同期, N={len(df)})")
    s_all = df[sentiment_var]; r_all = df[return_var]
    corr_p, p_p = stats.pearsonr(s_all, r_all); corr_s, p_s = stats.spearmanr(s_all, r_all)
    print(f"   - Pearson (線性) 相關: corr = {corr_p: .4f}, p-value = {p_p: .4f}")
    print(f"   - Spearman (等級) 相關: corr = {corr_s: .4f}, p-value = {p_s: .4f}")
    print("=============================================================")

# --- F. PART 4 邏輯：建立「每小時情緒」資料 ---
def create_hourly_sentiment_data_PN_Ratio(df_sentiment, trading_days):
    print(f"\n========== PART 4: 建立「每小時情緒」資料 ({OUTPUT_HOURLY_DATA_CSV}) ==========")
    all_hourly_data = [] 
    for i, T in enumerate(tqdm(trading_days, desc="處理每小時情緒")):
        T_date = T.date()
        bins = [
            T.replace(hour=9, minute=0, second=0), T.replace(hour=10, minute=0, second=0),
            T.replace(hour=11, minute=0, second=0), T.replace(hour=12, minute=0, second=0),
            T.replace(hour=13, minute=0, second=0), T.replace(hour=13, minute=30, second=0)
        ]
        labels = ['09:00-10:00', '10:00-11:00', '11:00-12:00', '12:00-13:00', '13:00-13:30']
        
        df_intraday = df_sentiment.loc[T.replace(hour=9, minute=0):T.replace(hour=13, minute=30)].copy()
        df_intraday['Time_Block'] = pd.cut(df_intraday.index, bins=bins, labels=labels, right=True, include_lowest=True)
        
        df_agg_intra = df_intraday.groupby('Time_Block', observed=True)['label_id'] \
                                  .apply(calculate_PN_Ratio) \
                                  .reset_index()
        df_agg_intra.rename(columns={'label_id': 'Sentiment_PN_Ratio'}, inplace=True)
        
        score_overnight = np.nan
        if i > 0:
            T_minus_1 = trading_days[i-1]
            start_ovn = T_minus_1.replace(hour=13, minute=31, second=0)
            end_ovn = T.replace(hour=8, minute=59, second=59)
            df_overnight = df_sentiment.loc[start_ovn : end_ovn]
            score_overnight = calculate_PN_Ratio(df_overnight['label_id']) # ✅ 新公式
        
        overnight_row = pd.DataFrame([{'Time_Block': 'Overnight', 'Sentiment_PN_Ratio': score_overnight}])
        df_day = pd.concat([overnight_row, df_agg_intra], ignore_index=True)
        df_day['Date'] = T_date
        all_hourly_data.append(df_day)
        
    df_final = pd.concat(all_hourly_data)
    time_block_order = ['Overnight', '09:00-10:00', '10:00-11:00', '11:00-12:00', '12:00-13:00', '13:00-13:30']
    df_final['Time_Block'] = pd.Categorical(df_final['Time_Block'], categories=time_block_order, ordered=True)
    df_final = df_final[['Date', 'Time_Block', 'Sentiment_PN_Ratio']].sort_values(by=['Date', 'Time_Block'])
    
    df_final.to_csv(OUTPUT_HOURLY_DATA_CSV, index=False, encoding='utf-8-sig')
    print(f"  > 成功儲存至: {OUTPUT_HOURLY_DATA_CSV}")
    return df_final

# --- G. PART 5 邏輯：載入「每小時股價」資料 ---
def load_hourly_price_data(price_csv_path):
    print(f"\n========== PART 5: 載入「每小時股價」資料 ({PRICE_CSV_PATH_HOURLY}) ==========")
    try:
        df_full_hourly_price = pd.read_csv(price_csv_path)
        df_full_hourly_price['Date'] = pd.to_datetime(df_full_hourly_price['Date']).dt.date
        print(f"  > 成功載入 {len(df_full_hourly_price)} 筆每小時股價資料。")
        return df_full_hourly_price
    except FileNotFoundError:
        print(f"錯誤：找不到股價資料檔案 '{price_csv_path}'！")
        print("請先執行 'preprocess_hourly_prices.py'。")
        return None

# --- H. PART 6 邏輯：繪製「圖表 B」 ---
def plot_chart_B_PN_Ratio(df_sentiment_all, df_price_all, date_str, chart_title, vline_color, vline_label, output_path):
    print(f"--- 正在繪製圖表：{chart_title} ---")
    target_date = pd.to_datetime(date_str).date()
    
    # 1. 準備情緒數據
    df_sent = df_sentiment_all[df_sentiment_all['Date'] == target_date].copy()
    if len(df_sent) != 6: print(f"  > 警告：{date_str} 的情緒資料不完整。"); return

    # 2. 準備股價數據
    df_price = df_price_all[df_price_all['Date'] == target_date].copy()
    if len(df_price) == 0: print(f"  > 警告：在股價 CSV 中找不到 {date_str} 的資料。"); return
    
    # 3. 整合
    df_merged = pd.merge(df_sent, df_price, on=['Date', 'Time_Block'], how='left')
    df_merged['Hourly_Cumulative_Return'] = np.where(
        df_merged['Time_Block'] == '13:00-13:30', 
        df_merged['Return_Close_vs_9am'],  
        df_merged['Return_Open_vs_9am']   
    )
    df_merged.loc[df_merged['Time_Block'] == 'Overnight', 'Hourly_Cumulative_Return'] = 0.0 
    df_plot = df_merged.set_index('Time_Block')

    # 4. 繪製
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except Exception: print("  > 警告：中文字體設定失敗。")

    fig, ax1 = plt.subplots(figsize=(12, 7)); ax2 = ax1.twinx() 
    ax1.plot(df_plot.index, df_plot['Sentiment_PN_Ratio'], color='#1f77b4', marker='o', label='情緒 P/N Ratio (Sentiment P/N Ratio)')
    ax1.set_ylabel('情緒 P/N Ratio (藍線)', color='#1f77b4', fontsize=12); ax1.tick_params(axis='y', labelcolor='#1f77b4')
    ax1.axhline(1, color='grey', linestyle=':', linewidth=1) # 增加 P/N = 1 的基準線
    
    ax2.plot(df_plot.index, df_plot['Hourly_Cumulative_Return'], color='#ff7f0e', marker='s', linestyle='--', label='每小時累計報酬率 (Hourly Cum. Return)')
    ax2.set_ylabel('每小時累計報酬率 (Hourly Cum. Return)', color='#ff7f0e', fontsize=12); ax2.tick_params(axis='y', labelcolor='#ff7f0e')
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.2%}')) 
    
    ax1.set_xlabel('時間區塊 (Time Block)', fontsize=12); ax1.grid(axis='x', linestyle=':', alpha=0.5)
    ax1.axvline(0.5, color=vline_color, linestyle='--', linewidth=2, label=vline_label) 
    
    plt.title(chart_title, fontsize=16, pad=20)
    lines, labels = ax1.get_legend_handles_labels(); lines2, labels2 = ax2.get_legend_handles_labels()
    fig.legend(lines + lines2, labels + labels2, loc='lower center', bbox_to_anchor=(0.5, -0.1), ncol=3, fontsize=10)
    
    plt.tight_layout(rect=[0, 0.05, 1, 0.95]); plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"  > ✅ 圖表已儲存至: {output_path}")

# --- I. PART 7 邏輯：執行「每小時統計」 ---
def run_hourly_stats_PN_Ratio(df_hourly_sentiment, df_hourly_prices):
    print(f"\n========== PART 7: 執行「每小時統計 (RQ4)」(P/N Ratio) ==========")
    
    # 1. 準備資料 (同 RQ4 腳本)
    df_sent = df_hourly_sentiment.copy(); df_price = df_hourly_prices.copy()
    df = pd.merge(df_sent, df_price, on=['Date', 'Time_Block'], how='inner')
    df = df[df['Time_Block'] != 'Overnight'].copy()
    
    # 重新命名
    df.rename(columns={'Sentiment_PN_Ratio': 'S_H'}, inplace=True)
    df['R_Cum'] = df['Return_Close_vs_9am']
    df['R_H'] = df.groupby('Date')['R_Cum'].diff()
    df['R_H'] = df['R_H'].fillna(df['R_Cum'])
    
    df['S_H_lag1'] = df.groupby('Date')['S_H'].shift(1)
    df['R_H_lag1'] = df.groupby('Date')['R_H'].shift(1)
    
    df_clean = df.dropna(subset=['S_H_lag1', 'R_H_lag1', 'S_H', 'R_H'])
    print(f"  > 清理後可用資料 N={len(df_clean)}")

    # 2. 相關性分析 (Spearman)
    print("\n--- [RQ4] H-1 相關性矩陣 (Spearman Method) ---")
    df_corr = df_clean[['S_H', 'R_H', 'S_H_lag1', 'R_H_lag1']].corr(method='spearman')
    print(df_corr.to_string(float_format="%.4f"))
    print("-" * 50)
    
    corr_sh_rh, p_sh_rh = stats.spearmanr(df_clean['S_H'], df_clean['R_H'])
    print(f"(分析 1) 同時性 spearmanr(S_H[t], R_H[t]):   {corr_sh_rh: .4f} (p={p_sh_rh: .4f})")
    corr_rh_sh, p_rh_sh = stats.spearmanr(df_clean['R_H_lag1'], df_clean['S_H'])
    print(f"(分析 3) 滯後性 spearmanr(R_H[t-1], S_H[t]): {corr_rh_sh: .4f} (p={p_rh_sh: .4f}) <-- H4a")
    corr_sh_rh_lag, p_sh_rh_lag = stats.spearmanr(df_clean['S_H_lag1'], df_clean['R_H'])
    print(f"(分析 2) 預測性 spearmanr(S_H[t-1], R_H[t]): {corr_sh_rh_lag: .4f} (p={p_sh_rh_lag: .4f}) <-- H4b")
    print("-" * 50)

    # 3. 格蘭傑因果檢定
    print("\n--- [RQ4] 格蘭傑因果檢定 (Granger Causality Test) ---")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore") 
        data_sr = df_clean[['R_H', 'S_H']]; gc_sr_res = grangercausalitytests(data_sr, maxlag=[1], verbose=False)
        p_value_sr = gc_sr_res[1][0]['ssr_ftest'][1]
        data_rs = df_clean[['S_H', 'R_H']]; gc_rs_res = grangercausalitytests(data_rs, maxlag=[1], verbose=False)
        p_value_rs = gc_rs_res[1][0]['ssr_ftest'][1]
        
    print(f"檢定 A (H4b: S -> R): S_H 是否 Granger-cause R_H？ > p-value = {p_value_sr: .4f}")
    print(f"檢定 B (H4a: R -> S): R_H 是否 Granger-cause S_H？ > p-value = {p_value_rs: .4f}")
    print("=============================================================")

# ===================================================================
# 10. 主程式 (「總指揮」)
# ===================================================================
def main():
    print("🚀 正在啟動「P/N Ratio」完整分析流程...")
    
    # 1. 載入基礎資料
    df_stock, df_sentiment = load_base_data(DB_PATH, SENTIMENT_TABLE, STOCK_CSV_PATH)
    if df_stock is None or df_sentiment is None:
        print("❌ 基礎資料載入失敗，已中斷。")
        return

    # 2. 執行「每日」分析 (Part 1, 2, 3)
    df_daily_final = create_daily_data_PN_Ratio(df_stock, df_sentiment)
    plot_chart_A_PN_Ratio(df_daily_final)
    run_daily_stats_PN_Ratio(df_daily_final)
    
    # 3. 執行「每小時」分析 (Part 4, 5, 6, 7)
    df_hourly_sentiment = create_hourly_sentiment_data_PN_Ratio(df_sentiment, df_stock.index)
    df_hourly_prices = load_hourly_price_data(PRICE_CSV_PATH_HOURLY)
    
    if df_hourly_sentiment is None or df_hourly_prices is None:
        print("❌ 每小時資料準備失敗，已中斷「圖表 B」和「RQ4」分析。")
        return

    # 繪製圖表 B-1 (4/10)
    plot_chart_B_PN_Ratio(
        df_hourly_sentiment, df_hourly_prices, 
        EVENT_2_DATE_STR, EVENT_2_TITLE, EVENT_2_VLINE_COLOR, EVENT_2_VLINE_LABEL, OUTPUT_CHART_B1
    )
    # 繪製圖表 B-2 (4/7)
    plot_chart_B_PN_Ratio(
        df_hourly_sentiment, df_hourly_prices,
        EVENT_1_DATE_STR, EVENT_1_TITLE, EVENT_1_VLINE_COLOR, EVENT_1_VLINE_LABEL, OUTPUT_CHART_B2
    )
    
    # 執行 RQ4
    run_hourly_stats_PN_Ratio(df_hourly_sentiment, df_hourly_prices)

    print("\n\n🎉🎉🎉 「P/N Ratio」完整分析流程已全部執行完畢！ 🎉🎉🎉")

if __name__ == "__main__":
    main()