# 檔案名稱: run_relative_surge_analysis.py
#
# 目的：
# 1. 計算 [Relative Surge] 指標 (相對於 P1 基準期的倍數)
# 2. 解決「樣本數少無法做 Rolling Window」的問題
# 3. 產出：圖表 9 (異常情緒倍數 vs 市場) 與 統計檢定

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_prop_surge_data.csv" # 讀取上一步產生的檔案
OUTPUT_CHART_9 = "chart_9_relative_surge.png"

# P1 (基準期) 定義
P1_START = '2025-03-27'
P1_END = '2025-04-02'

# ===================================================================
# 2. 核心邏輯
# ===================================================================

def main():
    print("🚀 啟動「Relative Surge (異常情緒)」補充分析...")

    # 1. 載入資料
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 錯誤：找不到 {INPUT_CSV}，請先執行 run_full_analysis_PN_Ratio.py")
        return
    
    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    
    # ✅✅✅ (關鍵修正) 補算絕對報酬率 ✅✅✅
    # 用來計算與 Total Surge 的相關性
    if 'R_daily' in df.columns:
        df['Abs_R_daily'] = df['R_daily'].abs()
    else:
        # 防呆：如果 CSV 欄位名稱不同，嘗試用 Close 計算
        df['R_daily'] = df['Close'].pct_change().fillna(0)
        df['Abs_R_daily'] = df['R_daily'].abs()

    print("--- 1. 計算 P1 基準值 (Baseline Mean) ---")
    # 篩選 P1 資料
    df_p1 = df.loc[P1_START:P1_END]
    
    # 計算 P1 平均 (作為分母)
    # 我們關心的是：負面佔比、正面佔比、總討論量
    baseline_neg_prop = df_p1['Neg_prop'].mean()
    baseline_pos_prop = df_p1['Pos_prop'].mean()
    baseline_total = df_p1['Total'].mean()
    
    print(f"  > P1 Neg Prop Mean: {baseline_neg_prop:.4f}")
    print(f"  > P1 Pos Prop Mean: {baseline_pos_prop:.4f}")
    print(f"  > P1 Total Vol Mean: {baseline_total:.1f}")

    print("\n--- 2. 計算 Relative Surge (今日 / P1平均) ---")
    # 公式：Value_t / Baseline
    # > 1 代表異常偏高 (Abnormal High)
    df['Rel_Neg_Surge'] = df['Neg_prop'] / baseline_neg_prop
    df['Rel_Pos_Surge'] = df['Pos_prop'] / baseline_pos_prop
    df['Rel_Total_Surge'] = df['Total'] / baseline_total

    # 顯示 4/7 和 4/10 的數據 (驗證用)
    print("\n[關鍵日數據驗證]")
    try:
        # 使用 strftime 防止日期格式問題
        d1 = pd.to_datetime('2025-04-07')
        d2 = pd.to_datetime('2025-04-10')
        
        if d1 in df.index:
            print("4/7 (恐慌日):")
            print(df.loc[d1][['Rel_Neg_Surge', 'Rel_Pos_Surge', 'Rel_Total_Surge']])
        
        if d2 in df.index:
            print("\n4/10 (反彈日):")
            print(df.loc[d2][['Rel_Neg_Surge', 'Rel_Pos_Surge', 'Rel_Total_Surge']])
    except Exception as e: 
        print(f"日期索引錯誤 (不影響繪圖): {e}")

    print("\n--- 3. 統計檢定 (Spearman) ---")
    # 檢驗：異常情緒倍數 是否與 市場報酬 相關
    
    sp_neg, p_neg = stats.spearmanr(df['Rel_Neg_Surge'], df['R_daily'])
    sp_pos, p_pos = stats.spearmanr(df['Rel_Pos_Surge'], df['R_daily'])
    
    # 這是你最想看的：波動幅度 vs 討論熱度
    sp_tot, p_tot = stats.spearmanr(df['Rel_Total_Surge'], df['Abs_R_daily']) 
    
    print(f"Rel_Neg vs Return: corr={sp_neg:.3f}, p={p_neg:.3f}")
    print(f"Rel_Pos vs Return: corr={sp_pos:.3f}, p={p_pos:.3f}")
    print(f"Rel_Total vs |Return| (波動率): corr={sp_tot:.3f}, p={p_tot:.3f}")

    print("\n--- 4. 繪製「圖表 9」 ---")
    plot_chart_9(df)

def plot_chart_9(df):
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax2 = ax1.twinx()

    # 繪製 Relative Surge (Bar Chart)
    width = 0.35
    # 負面異常 (紅色)
    ax1.bar(df.index - pd.Timedelta(hours=3), df['Rel_Neg_Surge'], width, color='red', alpha=0.6, label='負面異常倍數 (Relative Neg)')
    # 正面異常 (綠色)
    ax1.bar(df.index + pd.Timedelta(hours=3), df['Rel_Pos_Surge'], width, color='green', alpha=0.6, label='正面異常倍數 (Relative Pos)')
    
    # 繪製基準線 (y=1 代表正常)
    ax1.axhline(1, color='black', linestyle='-', linewidth=1.5, label='P1 基準線 (Normal Level)')
    
    # Y1 設定
    ax1.set_ylabel('異常情緒倍數 (Ratio to P1 Mean)', fontsize=12)
    # 自動調整 Y 軸上限，避免 bar 頂到天花板
    y_max = df[['Rel_Neg_Surge', 'Rel_Pos_Surge']].max().max()
    ax1.set_ylim(0, y_max * 1.3) 
    
    # 繪製市場 (Line Chart)
    ax2.plot(df.index, df['Cumulative_Return'], color='orange', marker='s', linestyle='--', linewidth=2, label='累計市場報酬 (Cumulative Return)')
    ax2.set_ylabel('累計市場報酬率', color='orange', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='orange')
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1%}'))

    # X 軸與背景
    ax1.set_xlabel('交易日', fontsize=12)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    # 背景色塊
    P1_DATES = pd.to_datetime(['2025-03-27', '2025-04-02'])
    P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-09'])
    P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-16'])
    
    ax1.axvspan(P1_DATES[0], P1_DATES[1], color='grey', alpha=0.1, label='P1')
    ax1.axvspan(P2_DATES[0], P2_DATES[1], color='red', alpha=0.1, label='P2')
    ax1.axvspan(P3_DATES[0], P3_DATES[1], color='green', alpha=0.1, label='P3')

    # 標題與圖例
    plt.title('圖 9：情緒異常倍數 (Relative Surge) 與市場反應', fontsize=16)
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    # 過濾重複圖例
    by_label = dict(zip(labels1 + labels2, lines1 + lines2))
    target_keys = ['負面異常倍數 (Relative Neg)', '正面異常倍數 (Relative Pos)', '累計市場報酬 (Cumulative Return)', 'P1 基準線 (Normal Level)']
    plt.legend([by_label[k] for k in target_keys], target_keys, loc='upper left')

    plt.tight_layout()
    plt.savefig(OUTPUT_CHART_9, dpi=300)
    print(f"✅ [圖表 9] 已儲存至: {OUTPUT_CHART_9}")

if __name__ == "__main__":
    main()