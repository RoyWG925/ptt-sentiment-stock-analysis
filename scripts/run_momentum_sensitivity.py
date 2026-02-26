# 檔案名稱: run_momentum_sensitivity.py
#
# 目的：
# 1. 測試不同天數 (Lag 1~5) 的情緒動能效果
# 2. 找出與市場報酬 (R_daily) 相關性最強的參數
# 3. 產出：動能敏感度比較圖 (Chart 19)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_prop_surge_data.csv"
OUTPUT_CHART_19 = "chart_19_momentum_sensitivity.png"
OUTPUT_REPORT = "momentum_sensitivity_report.txt"

# 設定要測試的 Lag 天數
LAGS_TO_TEST = [1, 2, 3, 4, 5]

# ===================================================================
# 2. 核心邏輯
# ===================================================================
def main():
    print("🚀 啟動「動能參數敏感度 (Momentum Sensitivity)」掃描...")

    if not os.path.exists(INPUT_CSV):
        print(f"❌ 找不到 {INPUT_CSV}"); return

    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')

    # 確保變數存在
    if 'Pos_prop' not in df.columns or 'R_daily' not in df.columns:
        # 嘗試補算
        if 'Count_Pos' in df.columns:
            df['Pos_prop'] = df['Count_Pos'] / df['Total']
        if 'Cumulative_Return' in df.columns and 'R_daily' not in df.columns:
            df['R_daily'] = df['Cumulative_Return'].diff().fillna(0)

    results = []
    
    print(f"\n--- 開始掃描 Lag 1 至 {max(LAGS_TO_TEST)} ---")
    
    # 儲存繪圖數據
    plot_data = {'Lag': [], 'Pos_Corr': [], 'Neg_Corr': []}

    for k in LAGS_TO_TEST:
        # 計算 k日動能
        # Momentum_k = Value_t - Value_{t-k}
        mom_pos = df['Pos_prop'].diff(k)
        mom_neg = df['Neg_prop'].diff(k)
        
        # 移除 NaN (計算相關性時必須移除)
        # 注意：Lag 越長，N 越小
        valid_data = pd.DataFrame({
            'Mom_Pos': mom_pos,
            'Mom_Neg': mom_neg,
            'R_daily': df['R_daily']
        }).dropna()
        
        n_samples = len(valid_data)
        
        # 計算 Spearman
        corr_pos, p_pos = stats.spearmanr(valid_data['Mom_Pos'], valid_data['R_daily'])
        corr_neg, p_neg = stats.spearmanr(valid_data['Mom_Neg'], valid_data['R_daily'])
        
        # 記錄
        res_str = f"Lag-{k} (N={n_samples}): Pos_Rho={corr_pos:.4f} (p={p_pos:.4f}) | Neg_Rho={corr_neg:.4f} (p={p_neg:.4f})"
        print(res_str)
        results.append(res_str)
        
        # 繪圖數據
        plot_data['Lag'].append(k)
        plot_data['Pos_Corr'].append(corr_pos)
        plot_data['Neg_Corr'].append(corr_neg)

    # 寫入報告
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(results))

    # =========================================================
    # 繪圖：敏感度分析 (Chart 19)
    # =========================================================
    print("\n--- 繪製 [圖表 19] 動能敏感度比較 ---")
    
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

    fig, ax = plt.subplots(figsize=(10, 6))
    
    x = np.arange(len(LAGS_TO_TEST))
    width = 0.35
    
    # 畫 Bar
    rects1 = ax.bar(x - width/2, plot_data['Pos_Corr'], width, label='正面情緒動能 (Pos Momentum)', color='green', alpha=0.7)
    rects2 = ax.bar(x + width/2, plot_data['Neg_Corr'], width, label='負面情緒動能 (Neg Momentum)', color='red', alpha=0.7)
    
    ax.set_ylabel('Spearman Correlation with Market Return')
    ax.set_xlabel('Lag Days (動能計算天數)')
    ax.set_title('各時間跨度的社群情緒動能與市場報酬之相關性', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels([f"Lag-{k}" for k in LAGS_TO_TEST])
    ax.axhline(0, color='black', linewidth=0.8)
    ax.legend()
    ax.grid(axis='y', linestyle=':', alpha=0.5)
    
    # 標示數值
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.2f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3 if height > 0 else -12),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9)

    autolabel(rects1)
    autolabel(rects2)

    plt.tight_layout()
    plt.savefig(OUTPUT_CHART_19, dpi=300)
    print(f"  > 已儲存至 {OUTPUT_CHART_19}")
    print(f"  > 統計數據已存至 {OUTPUT_REPORT}")
    
    print("\n🎉🎉🎉 參數掃描完成！看看哪一根柱子最高？ 🎉🎉🎉")

if __name__ == "__main__":
    main()