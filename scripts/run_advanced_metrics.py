# 檔案名稱: run_advanced_metrics.py
#
# 目的：
# 1. 計算高階衍生指標：偏離度 (Deviation), 動能 (Momentum), 量能 (Volume)
# 2. 尋找比原始變數更強的「隱藏訊號」
# 3. 產出圖表 16, 17, 18

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_prop_surge_data.csv"
OUTPUT_CSV = "final_advanced_metrics_data.csv"
OUTPUT_STATS = "advanced_metrics_stats.txt"

# 輸出圖表
IMG_CHART_16 = "chart_16_deviation_from_mean.png"
IMG_CHART_17 = "chart_17_sentiment_momentum.png"
IMG_CHART_18 = "chart_18_volume_intensity.png"

# P1 基準期 (用來計算 Mean)
P1_START = '2025-03-27'
P1_END = '2025-04-02'

# ===================================================================
# 2. 資料處理與指標計算
# ===================================================================
def calculate_advanced_metrics(df):
    print("--- 計算高階指標 ---")
    
    # 1. 準備 P1 基準值
    df_p1 = df.loc[P1_START:P1_END]
    mean_pos_p1 = df_p1['Pos_prop'].mean()
    mean_neg_p1 = df_p1['Neg_prop'].mean()
    mean_vol_p1 = df_p1['Total'].mean()
    
    print(f"  > P1 Baseline: Pos={mean_pos_p1:.3f}, Neg={mean_neg_p1:.3f}, Vol={mean_vol_p1:.1f}")

    # --- A. 情緒偏離 (Deviation from Event Mean) ---
    # 意義：今日情緒相對於「平靜期(P1)」偏離了多少？
    df['Dev_Pos'] = df['Pos_prop'] - mean_pos_p1
    df['Dev_Neg'] = df['Neg_prop'] - mean_neg_p1
    # Z-score 版本 (更嚴謹)
    df['Z_Dev_Pos'] = (df['Pos_prop'] - mean_pos_p1) / df_p1['Pos_prop'].std()
    
    # --- B. 情緒動能 (Sentiment Momentum) ---
    # 意義：情緒是在加速變好，還是加速變壞？
    # Mom_2: 與 2 天前相比 (t - t-2)
    df['Mom_Pos_2'] = df['Pos_prop'].diff(2)
    df['Mom_Neg_2'] = df['Neg_prop'].diff(2)
    
    # MA Gap: 當前值 - 3日移動平均 (突波偵測)
    # 意義：如果 > 0，代表今日情緒「突然」高於近期平均
    df['MA3_Pos'] = df['Pos_prop'].rolling(window=3).mean()
    df['Gap_MA3_Pos'] = df['Pos_prop'] - df['MA3_Pos']

    # --- C. 情緒版成交量 (Sentiment Volume) ---
    # 意義：市場反轉常伴隨「爆量」
    # Volume Ratio: 今日量 / P1平均量
    df['Vol_Ratio'] = df['Total'] / mean_vol_p1
    # Volume Gap: 今日量 - 3日均量 (突發熱度)
    df['Vol_MA3'] = df['Total'].rolling(window=3).mean()
    df['Gap_MA3_Vol'] = df['Total'] - df['Vol_MA3']

    return df

# ===================================================================
# 3. 統計檢定
# ===================================================================
def run_statistics(df):
    print("\n--- 執行 Spearman 相關性掃描 ---")
    results = []
    results.append("=== Advanced Metrics Correlation Report ===\n")
    
    # 確保市場變數存在
    mkt_target = 'R_daily'
    # 對於 Volume，通常跟「絕對報酬(|R|)」或「成交量」比較相關，這裡我們看 |R_daily|
    df['Abs_R_daily'] = df['R_daily'].abs()

    # 定義要檢測的變數對 (X vs Y)
    pairs = [
        # A. Deviation (看方向) -> R_daily
        ('Dev_Pos', 'R_daily', '偏離均值(正) vs 報酬'),
        ('Z_Dev_Pos', 'R_daily', 'Z-Score(正) vs 報酬'),
        ('Dev_Neg', 'R_daily', '偏離均值(負) vs 報酬'),
        
        # B. Momentum (看趨勢) -> R_daily
        ('Mom_Pos_2', 'R_daily', '動能(Pos lag-2) vs 報酬'),
        ('Gap_MA3_Pos', 'R_daily', 'MA乖離(Pos) vs 報酬'),
        
        # C. Volume (看強度) -> |R_daily| (波動率)
        ('Vol_Ratio', 'Abs_R_daily', '量能倍數 vs 絕對報酬(波動)'),
        ('Gap_MA3_Vol', 'Abs_R_daily', '量能突波 vs 絕對報酬(波動)')
    ]
    
    for col_x, col_y, label in pairs:
        # 移除 NaN (MA 計算會有 NaN)
        temp = df[[col_x, col_y]].dropna()
        if len(temp) < 3: continue
        
        corr, p = stats.spearmanr(temp[col_x], temp[col_y])
        
        star = ""
        if p < 0.01: star = "***"
        elif p < 0.05: star = "**"
        elif p < 0.1: star = "*"
        
        line = f"{label:<30} | rho={corr:.4f} | p={p:.4f} {star}"
        print(line)
        results.append(line)
        
    with open(OUTPUT_STATS, "w", encoding="utf-8") as f:
        f.write("\n".join(results))
    print(f"\n  > 統計報告已存：{OUTPUT_STATS}")

# ===================================================================
# 4. 視覺化
# ===================================================================
def plot_charts(df):
    print("\n--- 繪製進階圖表 ---")
    
    # 設定字體
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

    # --- 圖 16: Deviation (Z-score) vs Market ---
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()
    
    # 畫 Bar: Z_Dev_Pos (正面情緒異常程度)
    # 正值(綠)代表比平常異常樂觀，負值(灰)代表比平常低
    colors = np.where(df['Z_Dev_Pos'] >= 0, 'green', 'grey')
    ax1.bar(df.index, df['Z_Dev_Pos'], color=colors, alpha=0.6, label='正面情緒異常度 (Z-Dev Pos)')
    
    ax2.plot(df.index, df['Cumulative_Return'], color='orange', marker='s', linewidth=2, linestyle='--', label='市場累計報酬')
    
    ax1.set_title('圖 16：正面情緒偏離度 (Deviation from Mean) 與市場', fontsize=14)
    ax1.set_ylabel('Z-Score (相對於 P1 均值)', color='green')
    ax2.set_ylabel('累計報酬率', color='orange')
    ax1.axhline(0, color='black', linewidth=0.8)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    plt.tight_layout()
    plt.savefig(IMG_CHART_16, dpi=300)
    print(f"  > 圖 16 完成：{IMG_CHART_16}")
    
    # --- 圖 17: Momentum (MA Gap) vs Market ---
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()
    
    # 畫 Line: Gap_MA3_Pos (與3日均線的乖離)
    ax1.plot(df.index, df['Gap_MA3_Pos'], color='blue', marker='o', linewidth=2, label='正面情緒動能 (MA Gap)')
    ax1.fill_between(df.index, 0, df['Gap_MA3_Pos'], where=(df['Gap_MA3_Pos']>=0), facecolor='blue', alpha=0.1)
    
    ax2.plot(df.index, df['Cumulative_Return'], color='orange', marker='s', linewidth=2, linestyle='--', label='市場累計報酬')
    
    ax1.set_title('圖 17：情緒動能 (Sentiment Momentum / MA Gap)', fontsize=14)
    ax1.set_ylabel('與 3日均線之乖離', color='blue')
    ax1.axhline(0, color='black', linewidth=0.8)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    plt.tight_layout()
    plt.savefig(IMG_CHART_17, dpi=300)
    print(f"  > 圖 17 完成：{IMG_CHART_17}")
    
    # --- 圖 18: Volume Intensity vs Volatility ---
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()
    
    # 畫 Bar: Vol_Ratio (量能倍數)
    ax1.bar(df.index, df['Vol_Ratio'], color='purple', alpha=0.5, label='討論量倍數 (Volume Ratio)')
    
    # 畫 Line: Abs_R_daily (波動率)
    ax2.plot(df.index, df['Abs_R_daily'], color='red', marker='x', linewidth=2, label='市場波動率 (|Daily Return|)')
    
    ax1.set_title('圖 18：社群量能 (Volume) 與 市場波動率 (Volatility)', fontsize=14)
    ax1.set_ylabel('討論量倍數 (相對於 P1)', color='purple')
    ax2.set_ylabel('絕對報酬率 (波動)', color='red')
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1%}'))
    ax1.axhline(1, color='black', linestyle=':') # 1倍基準線
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    plt.tight_layout()
    plt.savefig(IMG_CHART_18, dpi=300)
    print(f"  > 圖 18 完成：{IMG_CHART_18}")

# ===================================================================
# 主程式
# ===================================================================
def main():
    print("🚀 啟動「高階指標 (Advanced Metrics)」分析...")
    
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 找不到 {INPUT_CSV}"); return
        
    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    
    # 1. 計算
    df_adv = calculate_advanced_metrics(df)
    df_adv.to_csv(OUTPUT_CSV, encoding='utf-8-sig')
    
    # 2. 統計
    run_statistics(df_adv)
    
    # 3. 繪圖
    plot_charts(df_adv)
    
    print("\n🎉🎉🎉 高階指標分析完成！ 🎉🎉🎉")

if __name__ == "__main__":
    main()