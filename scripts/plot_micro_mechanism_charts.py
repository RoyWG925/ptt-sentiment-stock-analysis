# 檔案名稱: plot_micro_mechanism_charts_v2.py
#
# (✅ V2 - 最終修正版)
# 1. 修正了「日期物件」 vs 「字串」的比較錯誤

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from tqdm import tqdm 

# ===================================================================
# 1. 設定區 (不變)
# ===================================================================
SENTIMENT_CSV_PATH = "hourly_sentiment_data.csv"
PRICE_CSV_PATH = "full_hourly_price_data.csv"
CHART_B1_PATH = "chart_B1_micro_4_10.png"
CHART_B2_PATH = "chart_B2_micro_4_07.png"

EVENT_1_DATE_STR = '2025-04-07'
EVENT_1_TITLE = '圖表 B-1：4/7 (恐慌日) 微觀機制分析'
EVENT_1_VLINE_COLOR = 'red'
EVENT_1_VLINE_LABEL = '9:00 開盤 / 4 天恐慌釋放'

EVENT_2_DATE_STR = '2025-04-10'
EVENT_2_TITLE = '圖表 B-2：4/10 (暫緩日) 微觀機制分析'
EVENT_2_VLINE_COLOR = 'green'
EVENT_2_VLINE_LABEL = '9:00 開盤 / 宣布暫緩'

# ===================================================================
#
#
# PART 1: 整合資料並繪圖 (✅ 關鍵修正處)
#
#
# ===================================================================

def plot_micro_chart(df_sentiment_all, df_price_all, date_str, chart_title, vline_color, vline_label, output_path):
    """
    (任務 B & C 的整合繪圖函式)
    """
    print(f"--- 正在繪製圖表：{chart_title} ---")
    
    # ✅✅✅ --- (關鍵修正) --- ✅✅✅
    # 將傳入的「字串」date_str 轉換為「日期物件」
    target_date = pd.to_datetime(date_str).date()
    
    # 1. 準備情緒數據 (使用「日期物件」來篩選)
    df_sent = df_sentiment_all[df_sentiment_all['Date'] == target_date].copy()
    
    if len(df_sent) == 0:
        print(f"  > 警告：在 {SENTIMENT_CSV_PATH} 中找不到 {date_str} 的情緒資料。跳過...")
        return
    if len(df_sent) != 6:
        print(f"  > 警告：{date_str} 的情緒資料不完整 (應有 6 筆，實際 {len(df_sent)} 筆)。")

    # 2. 準備股價數據 (使用「日期物件」來篩選)
    df_price = df_price_all[df_price_all['Date'] == target_date].copy()
    if len(df_price) == 0:
        print(f"  > 警告：在 {PRICE_CSV_PATH} 中找不到 {date_str} 的股價資料。跳過...")
        return
    
    # 3. 整合 DataFrame
    df_merged = pd.merge(
        df_sent, 
        df_price, 
        on=['Date', 'Time_Block'], 
        how='left' 
    )
    
    # 4. 建立最終的「每小時累計報酬率」序列
    df_merged['Hourly_Cumulative_Return'] = np.where(
        df_merged['Time_Block'] == '13:00-13:30', 
        df_merged['Return_Close_vs_9am'],  
        df_merged['Return_Open_vs_9am']   
    )
    df_merged['Hourly_Cumulative_Return'].fillna(0.0, inplace=True) 
    
    df_plot = df_merged.set_index('Time_Block')

    # 5. 繪製圖表 (不變)
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except Exception: print("警告：中文字體設定失敗。")

    fig, ax1 = plt.subplots(figsize=(12, 7)); ax2 = ax1.twinx() 
    ax1.plot(df_plot.index, df_plot['Sentiment_V2'], color='#1f77b4', marker='o', label='情緒極性指數 (Sentiment Polarity)')
    ax1.set_ylabel('情緒極性指數 (Sentiment Polarity)', color='#1f77b4', fontsize=12); ax1.tick_params(axis='y', labelcolor='#1f77b4')
    ax2.plot(df_plot.index, df_plot['Hourly_Cumulative_Return'], color='#ff7f0e', marker='s', linestyle='--', label='每小時累計報酬率 (Hourly Cum. Return)')
    ax2.set_ylabel('每小時累計報酬率 (Hourly Cum. Return)', color='#ff7f0e', fontsize=12); ax2.tick_params(axis='y', labelcolor='#ff7f0e')
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.2%}')) 
    ax1.set_xlabel('時間區塊 (Time Block)', fontsize=12); ax1.grid(axis='x', linestyle=':', alpha=0.5)
    ax1.axvline(0.5, color=vline_color, linestyle='--', linewidth=2, label=vline_label) 
    
    plt.title(chart_title, fontsize=16, pad=20)
    lines, labels = ax1.get_legend_handles_labels(); lines2, labels2 = ax2.get_legend_handles_labels()
    fig.legend(lines + lines2, labels + labels2, loc='lower center', bbox_to_anchor=(0.5, -0.1), ncol=3, fontsize=10)
    
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"  > ✅ 圖表已儲存至: {output_path}")

# ===================================================================
#
#
# PART 2: 主程式 (✅ 關鍵修正處)
#
#
# ===================================================================
def main():
    print(f"========== 正在繪製「圖表 B」 ==========")

    # 1. 載入「每小時情緒」資料
    print(f"--- 1/3: 正在載入 {SENTIMENT_CSV_PATH} ---")
    try:
        df_hourly_sentiment = pd.read_csv(SENTIMENT_CSV_PATH)
        # ✅ 修正：轉換 Date 欄位為 datetime.date object
        df_hourly_sentiment['Date'] = pd.to_datetime(df_hourly_sentiment['Date']).dt.date
    except FileNotFoundError:
        print(f"錯誤：找不到情緒資料檔案 '{SENTIMENT_CSV_PATH}'！"); return
        
    # 2. 載入「每小時股價」資料
    print(f"--- 2/3: 正在載入 {PRICE_CSV_PATH} ---")
    try:
        df_full_hourly_price = pd.read_csv(PRICE_CSV_PATH)
        # ✅ 修正：轉換 Date 欄位為 datetime.date object
        df_full_hourly_price['Date'] = pd.to_datetime(df_full_hourly_price['Date']).dt.date
    except FileNotFoundError:
        print(f"錯誤：找不到股價資料檔案 '{PRICE_CSV_PATH}'！"); return

    print(f"--- 3/3: 開始繪製圖表... ---")
    
    # 3. 繪製 4/10 (暫緩日)
    plot_micro_chart(
        df_sentiment_all = df_hourly_sentiment,
        df_price_all = df_full_hourly_price,
        date_str = EVENT_2_DATE_STR, # '2025-04-10' (str)
        chart_title = EVENT_2_TITLE,
        vline_color = EVENT_2_VLINE_COLOR,
        vline_label = EVENT_2_VLINE_LABEL,
        output_path = CHART_B1_PATH
    )
    
    # 4. 繪製 4/7 (恐慌日)
    plot_micro_chart(
        df_sentiment_all = df_hourly_sentiment,
        df_price_all = df_full_hourly_price,
        date_str = EVENT_1_DATE_STR, # '2025-04-07' (str)
        chart_title = EVENT_1_TITLE,
        vline_color = EVENT_1_VLINE_COLOR,
        vline_label = EVENT_1_VLINE_LABEL,
        output_path = CHART_B2_PATH
    )

    print("\n🎉🎉🎉 所有微觀圖表繪製完成！ 🎉🎉🎉")

if __name__ == "__main__":
    main()