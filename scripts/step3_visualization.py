# 檔案名稱: step3_visualization.py
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats
import numpy as np
import os

INPUT_CSV = "thesis_final_data.csv"
IMG_DIR = "Thesis_Figures"

def main():
    print("🚀 [Step 3] 啟動圖表繪製...")
    if not os.path.exists(IMG_DIR): os.makedirs(IMG_DIR)
    
    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    
    # 設定中文字型 (請自行確認系統字型名稱，這裡用微軟正黑體範例)
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

    # 背景設定函式 (P1/P2/P3)
    def add_bg(ax):
        # 取得各期日期範圍
        p1 = df[df['Period']=='P1'].index
        p2 = df[df['Period']=='P2'].index
        p3 = df[df['Period']=='P3'].index
        
        if len(p1)>0: ax.axvspan(p1[0], p1[-1], color='gray', alpha=0.1, label='P1 前期')
        if len(p2)>0: ax.axvspan(p2[0], p2[-1], color='red', alpha=0.1, label='P2 衝擊期')
        if len(p3)>0: ax.axvspan(p3[0], p3[-1], color='green', alpha=0.1, label='P3 暫緩期')

    # --- 1. 結構堆疊圖 (4.2) ---
    fig, ax = plt.subplots(figsize=(10, 6))
    # 加總計算比例
    period_counts = df.groupby('Period')[['Count_Neg', 'Count_Neu', 'Count_Pos']].sum().reindex(['P1', 'P2', 'P3'])
    period_pct = period_counts.div(period_counts.sum(axis=1), axis=0) * 100
    
    period_pct.plot(kind='bar', stacked=True, color=['#d62728', '#7f7f7f', '#2ca02c'], ax=ax, width=0.6)
    ax.set_title('圖 4-1：情緒結構變化堆疊圖', fontsize=14)
    ax.set_ylabel('佔比 (%)')
    ax.set_xlabel('時期')
    plt.xticks(rotation=0)
    ax.legend(['負面', '中性', '正面'], loc='upper right')
    plt.tight_layout()
    plt.savefig(f"{IMG_DIR}/Fig_4-1_Structure.png", dpi=300)

    # --- 2. Z-score 同步圖 (4.3) ---
    # 僅使用交易日數據繪圖比較準
    df_trade = df[df['Is_Trading_Day']==True].copy()
    
    fig, ax = plt.subplots(figsize=(12, 6))
    z_pos = stats.zscore(df_trade['Pos_prop'])
    z_mkt = stats.zscore(df_trade['Cumulative_Return'])
    
    ax.plot(df_trade.index, z_pos, color='green', marker='o', linewidth=2, label='正面情緒 (Z-score)')
    ax.plot(df_trade.index, z_mkt, color='orange', marker='s', linewidth=2, linestyle='--', label='市場累積報酬 (Z-score)')
    
    add_bg(ax)
    ax.set_title('圖 4-2：正面情緒與市場走勢同步性 (Z-score)', fontsize=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.legend()
    plt.tight_layout()
    plt.savefig(f"{IMG_DIR}/Fig_4-2_Sync_Zscore.png", dpi=300)

    # --- 3. 動能敏感度圖 (4.5) ---
    # 計算各 Lag 相關係數
    lags = [1, 2, 3, 4, 5]
    corrs = []
    for k in lags:
        # 計算該 Lag 的相關性
        r, _ = stats.spearmanr(df_trade[f'Momentum_{k}'], df_trade['R_daily'], nan_policy='omit')
        corrs.append(r)
        
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(lags, corrs, color=['gray', 'blue', 'gray', 'gray', 'gray'])
    ax.set_title('圖 4-4：動能敏感度分析 (Lag 1-5)', fontsize=14)
    ax.set_xlabel('滯後期數 (Lag)')
    ax.set_ylabel('Spearman 相關係數')
    ax.axhline(0, color='black', linewidth=0.5)
    
    # 標註數值
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.2f}', ha='center', va='bottom')
        
    plt.tight_layout()
    plt.savefig(f"{IMG_DIR}/Fig_4-4_Momentum_Sensitivity.png", dpi=300)

    # --- 4. 量能 vs 波動 (4.6) ---
    fig, ax = plt.subplots(figsize=(12, 6))
    ax2 = ax.twinx()
    
    ax.bar(df_trade.index, df_trade['Vol_Ratio'], color='purple', alpha=0.5, label='討論量倍數')
    ax2.plot(df_trade.index, df_trade['Abs_R_daily'], color='red', marker='x', linewidth=2, label='市場波動度 (|R|)')
    
    add_bg(ax)
    ax.set_title('圖 4-5：討論量倍數與市場波動度', fontsize=14)
    ax.set_ylabel('量能倍數 (相對 P1)')
    ax2.set_ylabel('絕對報酬率')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    # 合併圖例
    lines_1, labels_1 = ax.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')
    
    plt.tight_layout()
    plt.savefig(f"{IMG_DIR}/Fig_4-5_Volume_Volatility.png", dpi=300)
    
    print(f"✅ 所有圖表已生成至：{IMG_DIR}/")

if __name__ == "__main__":
    main()