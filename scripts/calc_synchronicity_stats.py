# 檔案名稱: calc_synchronicity_stats.py
#
# 目的：計算「情緒 vs 市場」的 Level 同步性 與 變化量同步性
# 變數：Pos_prop, Neg_prop vs Cumulative_Return, R_daily

import pandas as pd
import scipy.stats as stats
import os

# 設定輸入檔案
INPUT_CSV = "final_prop_surge_data.csv"

def run_spearman(x, y, label):
    # 合併並移除 NaN (因為 diff 會產生 NaN)
    df_temp = pd.DataFrame({'x': x, 'y': y}).dropna()
    
    if len(df_temp) < 3:
        print(f"{label}: 樣本數不足")
        return

    corr, p = stats.spearmanr(df_temp['x'], df_temp['y'])
    
    # 判斷顯著性星星
    stars = ""
    if p < 0.01: stars = "***"
    elif p < 0.05: stars = "**"
    elif p < 0.1: stars = "*"
    
    print(f"{label:<55} | rho = {corr:.4f} | p = {p:.4f} {stars}")

def main():
    print("🚀 啟動 Spearman 同步性檢定...\n")

    if not os.path.exists(INPUT_CSV):
        print(f"❌ 錯誤：找不到 {INPUT_CSV}"); return

    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')

    # 確保欄位存在
    required_cols = ['Pos_prop', 'Neg_prop', 'Cumulative_Return', 'R_daily']
    # 如果 R_daily 不在 (舊版 CSV)，重算
    if 'R_daily' not in df.columns:
        df['R_daily'] = df['Cumulative_Return'].diff().fillna(0) # 近似

    print("--- 1. Level 同步性 (趨勢形狀相似度) ---")
    print("(預期：Pos 正相關，Neg 負相關)\n")
    
    run_spearman(df['Pos_prop'], df['Cumulative_Return'], "Pos_prop (Level) vs Cumulative_Return (Level)")
    run_spearman(df['Neg_prop'], df['Cumulative_Return'], "Neg_prop (Level) vs Cumulative_Return (Level)")
    
    print("\n" + "="*60 + "\n")

    print("--- 2. 變化量同步性 (每日漲跌連動度) ---")
    print("(預期：ΔPos 正相關，ΔNeg 負相關)\n")

    # 計算差分
    pos_diff = df['Pos_prop'].diff()
    neg_diff = df['Neg_prop'].diff()
    
    run_spearman(pos_diff, df['R_daily'], "Δ Pos_prop (Change) vs R_daily (Return)")
    run_spearman(neg_diff, df['R_daily'], "Δ Neg_prop (Change) vs R_daily (Return)")

    print("\nDone.")

if __name__ == "__main__":
    main()