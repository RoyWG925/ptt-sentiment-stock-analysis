# 檔案名稱: run_thesis_final_charts.py
#
# 目的：
# 1. 讀取所有「每日」與「每小時」的 CSV 資料
# 2. 嚴格按照論文規格，產出 9 張最終版圖表 (A1, A2, C1-C3, D1-D4, H1, H2)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.stats import zscore
import os

# ===================================================================
# 1. 全域設定 (Global Settings)
# ===================================================================

# --- 資料來源 ---
DAILY_CSV = "final_structured_data.csv"
HOURLY_SENT_CSV = "hourly_sentiment_data_PN_Ratio.csv"
HOURLY_PRICE_CSV = "full_hourly_price_data.csv"

# --- 輸出設定 ---
OUTPUT_DIR = "thesis_charts"
os.makedirs(OUTPUT_DIR, exist_ok=True) # 自動建立輸出資料夾

# --- 圖表尺寸與字型 ---
FIG_SIZE = (12, 6)
DPI = 300
try:
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] # 微軟正黑體
    plt.rcParams['axes.unicode_minus'] = False # 解決負號顯示問題
    plt.rcParams['grid.linestyle'] = ':' # 格線：虛線
    plt.rcParams['grid.alpha'] = 0.4   # 格線：透明度
except:
    print("警告： 'Microsoft JhengHei' 字型未安裝，圖表可能顯示方框。")

# --- 事件區間（硬編碼）---
P1_DATES = (pd.to_datetime('2025-03-27'), pd.to_datetime('2025-04-02'))
P2_DATES = (pd.to_datetime('2025-04-07'), pd.to_datetime('2025-04-09'))
P3_DATES = (pd.to_datetime('2025-04-10'), pd.to_datetime('2025-04-16'))
# --- 事件色塊（統一格式）---
P1_SHADE = {'color': 'grey', 'alpha': 0.10}
P2_SHADE = {'color': 'red', 'alpha': 0.12}
P3_SHADE = {'color': 'green', 'alpha': 0.12}

# ===================================================================
# 2. 輔助函式 (Helper Functions)
# ===================================================================

def add_event_shading(ax, df_index):
    """統一的背景色函式"""
    # 確保只在資料範圍內著色
    min_date, max_date = df_index[0], df_index[-1]
    
    # P1
    p1_s = max(P1_DATES[0], min_date); p1_e = min(P1_DATES[1], max_date)
    if p1_s <= p1_e: ax.axvspan(p1_s, p1_e, **P1_SHADE, label='P1')
    # P2
    p2_s = max(P2_DATES[0], min_date); p2_e = min(P2_DATES[1], max_date)
    if p2_s <= p2_e: ax.axvspan(p2_s, p2_e, **P2_SHADE, label='P2')
    # P3
    p3_s = max(P3_DATES[0], min_date); p3_e = min(P3_DATES[1], max_date)
    if p3_s <= p3_e: ax.axvspan(p3_s, p3_e, **P3_SHADE, label='P3')

def format_daily_xaxis(ax):
    """統一的日期格式"""
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.grid(True)

def minmax_scale(s):
    """Min-Max 正規化"""
    return (s - s.min()) / (s.max() - s.min())

def save_chart(fig, filename, size=FIG_SIZE):
    """統一的儲存函式"""
    path = os.path.join(OUTPUT_DIR, filename)
    fig.set_size_inches(size)
    fig.savefig(path, dpi=DPI, bbox_inches='tight')
    plt.close(fig) # 關閉圖表以釋放記憶體
    print(f"[Saved] {path}")

# ===================================================================
# 3. 資料載入與準備 (Data Loading & Prep)
# ===================================================================

def load_daily_data():
    """載入並準備所有每日資料"""
    print("--- 正在載入 'final_structured_data.csv' ---")
    df = pd.read_csv(DAILY_CSV, parse_dates=['Date'], index_col='Date')
    
    # 確保欄位存在
    required_cols = ['R_daily', 'Cumulative_Return', 'S_Overnight', 'S_Intraday', 'PNR_Overnight', 'PNR_Intraday', 'Period', 'Total_ON', 'Total_IN']
    if not all(col in df.columns for col in required_cols):
        print(f"錯誤：{DAILY_CSV} 缺少必要欄位。")
        print(f"  需要：{required_cols}")
        print(f"  實際：{list(df.columns)}")
        return None
        
    # 計算 Volume
    df['Volume'] = df['Total_ON'] + df['Total_IN']
    
    # 計算 Surge
    df['ΔS_Overnight'] = df['S_Overnight'].diff()
    df['ΔS_Intraday'] = df['S_Intraday'].diff()
    
    # 移除第一天 (因為 Surge 會是 NaN)
    return df.iloc[1:]

def load_hourly_data():
    """載入並準備所有每小時資料"""
    print("--- 正在載入每小時資料 (Sentiment + Price) ---")
    try:
        df_sent = pd.read_csv(HOURLY_SENT_CSV)
        df_price = pd.read_csv(HOURLY_PRICE_CSV)
    except FileNotFoundError:
        print("錯誤：找不到每小時資料 CSV，無法繪製 H1/H2。")
        return None
        
    # 合併
    df_hourly = pd.merge(df_sent, df_price, on=['Date', 'Time_Block'], how='inner')
    
    # 計算 Hourly Return (R_hour)
    # R_h[t] = R_cum[t] - R_cum[t-1]
    df_hourly['R_cum'] = df_hourly['Return_Close_vs_9am'] # 使用收盤價的累計報酬
    df_hourly['R_hour'] = df_hourly.groupby('Date')['R_cum'].diff().fillna(df_hourly['R_cum'])
    
    # 計算 Hourly PNR Surge
    df_hourly['PNR_hour_surge'] = df_hourly.groupby('Date')['Sentiment_PN_Ratio'].diff()
    
    return df_hourly

# ===================================================================
# 4. 繪圖主函式 (Plotting Functions)
# ===================================================================

# --- Part A：敘事圖 (2 張) ---
def plot_part_A(df):
    print("--- Part A: 正在繪製敘事圖 (A1, A2) ---")
    
    # 圖 A1：市場 V 型反轉
    fig, ax = plt.subplots()
    ax.plot(df.index, df['Cumulative_Return'], color='orange', marker='o', label='累計市場報酬')
    add_event_shading(ax, df.index)
    format_daily_xaxis(ax)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1%}'))
    ax.set_title('圖 A1：市場 V 型反轉 (累計報酬率)', fontsize=14)
    ax.set_ylabel('累計報酬率 (Cumulative Return)')
    save_chart(fig, 'chart_A1_market_V_shape.png')

    # 圖 A2：PTT 每日總推文量
    fig, ax = plt.subplots()
    ax.bar(df.index, df['Volume'], color='grey', alpha=0.7, label='每日總推文量')
    add_event_shading(ax, df.index)
    format_daily_xaxis(ax)
    ax.set_title('圖 A2：PTT 每日總推文量 (Volume)', fontsize=14)
    ax.set_ylabel('推文總數 (Total Posts)')
    save_chart(fig, 'chart_A2_daily_volume.png')

# --- Part D：核心研究（Daily，4 張）---
def plot_part_D(df):
    print("--- Part D: 正在繪製核心研究圖 (D1, D2, D3, D4) ---")
    
    # D1：隔夜情緒 vs 市場（Z-score）
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    ax1.plot(df.index, zscore(df['S_Overnight']), color='blue', marker='o', label='隔夜情緒 (Z-score)')
    ax2.plot(df.index, zscore(df['Cumulative_Return']), color='orange', marker='s', linestyle='--', label='市場報酬 (Z-score)')
    add_event_shading(ax1, df.index)
    format_daily_xaxis(ax1)
    ax1.set_title('圖 D1：隔夜情緒 vs 市場 (Z-score 標準化)', fontsize=14)
    ax1.set_ylabel('S_Overnight (Z-score)', color='blue')
    ax2.set_ylabel('Cumulative_Return (Z-score)', color='orange')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax2.tick_params(axis='y', labelcolor='orange')
    save_chart(fig, 'chart_D1_overnight_vs_market.png')

    # D2：盤中情緒 vs 市場（Z-score）
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    ax1.plot(df.index, zscore(df['S_Intraday']), color='blue', marker='o', label='盤中情緒 (Z-score)')
    ax2.plot(df.index, zscore(df['Cumulative_Return']), color='orange', marker='s', linestyle='--', label='市場報酬 (Z-score)')
    add_event_shading(ax1, df.index)
    format_daily_xaxis(ax1)
    ax1.set_title('圖 D2：盤中情緒 vs 市場 (Z-score 標準化)', fontsize=14)
    ax1.set_ylabel('S_Intraday (Z-score)', color='blue')
    ax2.set_ylabel('Cumulative_Return (Z-score)', color='orange')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax2.tick_params(axis='y', labelcolor='orange')
    save_chart(fig, 'chart_D2_intraday_vs_market.png')

    # D3：隔夜情緒變化量 vs 當日 R_daily
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    ax1.plot(df.index, df['ΔS_Overnight'], color='blue', marker='o', label='隔夜情緒變化 (ΔS_Overnight)')
    ax2.bar(df.index, df['R_daily'], color='grey', alpha=0.5, width=0.7, label='每日報酬 (R_daily)')
    add_event_shading(ax1, df.index)
    format_daily_xaxis(ax1)
    ax1.axhline(0, color='black', linewidth=0.5)
    ax1.set_title('圖 D3：隔夜情緒變化 (Surge) vs 每日報酬', fontsize=14)
    ax1.set_ylabel('情緒變化量 (Δ)', color='blue')
    ax2.set_ylabel('每日報酬 (R_daily)')
    save_chart(fig, 'chart_D3_overnight_surge_vs_return.png')

    # D4：盤中情緒變化量 vs 當日 R_daily
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    ax1.plot(df.index, df['ΔS_Intraday'], color='blue', marker='o', label='盤中情緒變化 (ΔS_Intraday)')
    ax2.bar(df.index, df['R_daily'], color='grey', alpha=0.5, width=0.7, label='每日報酬 (R_daily)')
    add_event_shading(ax1, df.index)
    format_daily_xaxis(ax1)
    ax1.axhline(0, color='black', linewidth=0.5)
    ax1.set_title('圖 D4：盤中情緒變化 (Surge) vs 每日報酬', fontsize=14)
    ax1.set_ylabel('情緒變化量 (Δ)', color='blue')
    ax2.set_ylabel('每日報酬 (R_daily)')
    save_chart(fig, 'chart_D4_intraday_surge_vs_return.png')

# --- Part C：多尺度比較（3 張）---
def plot_part_C(df):
    print("--- Part C: 正在繪製多尺度比較圖 (C1, C2, C3) ---")
    
    # C1：Z-score 形狀比較 (同 D2)
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    ax1.plot(df.index, zscore(df['S_Intraday']), color='blue', marker='o', label='盤中情緒 (Z-score)')
    ax2.plot(df.index, zscore(df['Cumulative_Return']), color='orange', marker='s', linestyle='--', label='市場報酬 (Z-score)')
    add_event_shading(ax1, df.index)
    format_daily_xaxis(ax1)
    ax1.set_title('圖 C1：Z-score 形狀比較 (同 D2)', fontsize=14, color='darkred') # 標註同 D2
    ax1.set_ylabel('S_Intraday (Z-score)', color='blue')
    ax2.set_ylabel('Cumulative_Return (Z-score)', color='orange')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax2.tick_params(axis='y', labelcolor='orange')
    save_chart(fig, 'chart_C1_zscore_shape.png')

    # C2：Min-Max 正規化比較
    fig, ax = plt.subplots()
    ax.plot(df.index, minmax_scale(df['S_Intraday']), color='blue', marker='o', label='盤中情緒 (Min-Max)')
    ax.plot(df.index, minmax_scale(df['Cumulative_Return']), color='orange', marker='s', linestyle='--', label='市場報酬 (Min-Max)')
    add_event_shading(ax, df.index)
    format_daily_xaxis(ax)
    ax.set_title('圖 C2：Min-Max 正規化比較', fontsize=14)
    ax.set_ylabel('正規化值 (0-1)')
    ax.legend()
    save_chart(fig, 'chart_C2_minmax.png')

    # C3：一階差分（變化速度）比較 (同 D4)
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    ax1.plot(df.index, df['ΔS_Intraday'], color='blue', marker='o', label='盤中情緒變化 (ΔS_Intraday)')
    ax2.bar(df.index, df['R_daily'], color='grey', alpha=0.5, width=0.7, label='每日報酬 (R_daily)')
    add_event_shading(ax1, df.index)
    format_daily_xaxis(ax1)
    ax1.axhline(0, color='black', linewidth=0.5)
    ax1.set_title('圖 C3：一階差分速度比較 (同 D4)', fontsize=14, color='darkred') # 標註同 D4
    ax1.set_ylabel('情緒變化量 (Δ)', color='blue')
    ax2.set_ylabel('每日報酬 (R_daily)')
    save_chart(fig, 'chart_C3_diff_speed.png')

# --- Part H：Hourly Micro（盤中微觀分析 2 張）---
def plot_part_H(df_hourly):
    print("--- Part H: 正在繪製盤中微觀圖 (H1, H2) ---")
    if df_hourly is None:
        print("  > 缺少每小時資料，跳過 Part H。")
        return
        
    for date_str, chart_file, title in [
        ('2025-04-07', 'chart_H1_20250407_hourly.png', '圖 H1：4/7 恐慌盤中：PN Ratio vs Hourly Return'),
        ('2025-04-10', 'chart_H2_20250410_hourly.png', '圖 H2：4/10 反彈盤中：PN Ratio vs Hourly Return')
    ]:
        df_day = df_hourly[df_hourly['Date'] == date_str].copy()
        if df_day.empty:
            print(f"  > 找不到 {date_str} 的每小時資料，跳過 {chart_file}。")
            continue
            
        fig, ax1 = plt.subplots()
        ax2 = ax1.twinx()
        
        # X 軸：Time_Block
        x_labels = df_day['Time_Block']
        x_pos = np.arange(len(x_labels))
        
        # Y1：PN Ratio (藍線)
        ax1.plot(x_pos, df_day['Sentiment_PN_Ratio'], color='blue', marker='o', label='PN Ratio')
        ax1.set_ylabel('情緒 P/N Ratio', color='blue')
        ax1.tick_params(axis='y', labelcolor='blue')
        
        # Y2：R_hour (橘線)
        ax2.plot(x_pos, df_day['R_hour'], color='orange', marker='s', linestyle='--', label='每小時報酬 (R_hour)')
        ax2.set_ylabel('每小時報酬 (R_hour)', color='orange')
        ax2.tick_params(axis='y', labelcolor='orange')
        ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.2%}'))
        
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(x_labels)
        ax1.set_title(title, fontsize=14)
        ax1.grid(True)
        
        # 合併圖例
        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines + lines2, labels + labels2)
        
        save_chart(fig, chart_file)

# ===================================================================
# 5. 主程式 (Main Execution)
# ===================================================================

def main():
    print("🚀 開始執行「論文最終版」圖表生成腳本...")
    
    # 載入資料
    df_daily = load_daily_data()
    df_hourly = load_hourly_data()
    
    if df_daily is None:
        print("❌ 每日資料載入失敗，腳本中斷。")
        return
        
    # 執行所有繪圖任務
    plot_part_A(df_daily)
    plot_part_D(df_daily)
    plot_part_C(df_daily)
    plot_part_H(df_hourly)
    
    print("\n🎉🎉🎉 所有圖表已生成完畢！ 🎉🎉🎉")
    print(f"請檢查 '{OUTPUT_DIR}' 資料夾。")

if __name__ == "__main__":
    main()