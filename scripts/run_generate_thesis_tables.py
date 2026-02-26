# 檔案名稱: run_generate_thesis_tables.py
#
# 目的：
# 1. 產生論文所需的「正式表格」數據
# 2. 包含：表 4-1 (描述統計)、ANOVA 總表、相關係數矩陣
# 3. 格式化輸出，方便複製到 Word

import pandas as pd
import numpy as np
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_prop_surge_data.csv"
OUTPUT_FILE = "THESIS_FORMAL_TABLES.txt"

# 時期定義
P1_DATES = pd.to_datetime(['2025-03-27', '2025-03-28', '2025-03-31', '2025-04-01', '2025-04-02'])
P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-08', '2025-04-09'])
P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-11', '2025-04-14', '2025-04-15', '2025-04-16'])

# ===================================================================
# 2. 輔助函式
# ===================================================================
def get_sig(p):
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.1: return "*"
    return ""

def calculate_eta_squared(df, col, group_col='Period'):
    # 簡單計算 Eta-squared
    groups = [df[df[group_col]==p][col].dropna() for p in ['P1', 'P2', 'P3']]
    if any(len(g)==0 for g in groups): return np.nan
    
    all_data = np.concatenate(groups)
    sst = np.sum((all_data - np.mean(all_data))**2)
    ssb = sum([len(g) * (np.mean(g) - np.mean(all_data))**2 for g in groups])
    return ssb / sst if sst != 0 else 0

# ===================================================================
# 3. 主程式
# ===================================================================
def main():
    print("🚀 正在生成論文正式表格...")
    
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 找不到 {INPUT_CSV}"); return

    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')

    # --- 資料補全 ---
    if 'Neu_prop' not in df.columns:
        if 'Count_Neu' in df.columns: df['Neu_prop'] = df['Count_Neu'] / df['Total']
        else: df['Neu_prop'] = 1 - df['Pos_prop'] - df['Neg_prop']
    
    # 計算動能 (Lag-2) 用於相關性表
    df['Momentum_2'] = df['Pos_prop'].diff(2)
    
    # 定義 Period
    conditions = [df.index.isin(P1_DATES), df.index.isin(P2_DATES), df.index.isin(P3_DATES)]
    df['Period'] = np.select(conditions, ['P1', 'P2', 'P3'], default='Other')
    
    # 移除無效日期
    df_valid = df[df['Period'] != 'Other'].copy()

    lines = []
    lines.append("=== 論文正式表格數據 (可以直接複製數據製表) ===\n")

    # ========================================================
    # 表 4-1：描述性統計 (Mean & Std)
    # ========================================================
    lines.append("【表 4-1：各時期情緒指標與市場數據之描述性統計 (Mean ± Std)】")
    lines.append("-" * 80)
    
    target_cols = ['Pos_prop', 'Neg_prop', 'Neu_prop', 'Total', 'R_daily']
    display_names = ['正面佔比 (Pos)', '負面佔比 (Neg)', '中性佔比 (Neu)', '討論量 (Total)', '市場報酬 (Return)']
    
    # 製作表格 header
    header = f"{'變數':<20} | {'P1 (前期, N=5)':<20} | {'P2 (衝擊期, N=3)':<20} | {'P3 (暫緩期, N=5)':<20}"
    lines.append(header)
    lines.append("-" * 80)

    for col, name in zip(target_cols, display_names):
        row_str = f"{name:<20} | "
        for p in ['P1', 'P2', 'P3']:
            sub = df_valid[df_valid['Period'] == p][col]
            mean_val = sub.mean()
            std_val = sub.std()
            
            # 根據變數類型格式化
            if col == 'Total':
                val_str = f"{mean_val:.1f} ± {std_val:.1f}"
            else:
                val_str = f"{mean_val:.4f} ± {std_val:.4f}"
            
            row_str += f"{val_str:<20} | "
        lines.append(row_str)
    lines.append("-" * 80 + "\n")


    # ========================================================
    # 表 4-2：ANOVA 變異數分析摘要表 (補充)
    # ========================================================
    lines.append("【表 4-2 (建議)：情緒結構變動之 ANOVA 檢定摘要】")
    lines.append("-" * 80)
    lines.append(f"{'變數':<20} | {'F-value':<10} | {'p-value':<15} | {'Effect Size (η²)':<15}")
    lines.append("-" * 80)
    
    for col, name in zip(['Pos_prop', 'Neg_prop', 'Neu_prop'], ['正面佔比', '負面佔比', '中性佔比']):
        groups = [df_valid[df_valid['Period']==p][col].dropna() for p in ['P1', 'P2', 'P3']]
        f_val, p_val = stats.f_oneway(*groups)
        eta2 = calculate_eta_squared(df_valid, col)
        
        sig = get_sig(p_val)
        lines.append(f"{name:<20} | {f_val:.4f}     | {p_val:.4f} {sig:<3}    | {eta2:.4f}")
    lines.append("-" * 80 + "\n")


    # ========================================================
    # 表 4-3：相關係數矩陣 (Full Matrix)
    # ========================================================
    lines.append("【表 4-3 (建議)：主要變數之 Spearman 相關係數矩陣】")
    lines.append("(包含不顯著的變數，以呈現對比)")
    lines.append("-" * 90)
    
    corr_vars = ['R_daily', 'Pos_prop', 'Momentum_2', 'Total']
    corr_names = ['1. 市場報酬', '2. 正面情緒(Level)', '3. 情緒動能(Lag-2)', '4. 討論量']
    
    # 標頭
    lines.append(f"{'變數':<25} {'1':<10} {'2':<10} {'3':<10} {'4':<10}")
    lines.append("-" * 90)
    
    data_corr = df_valid[corr_vars].dropna()
    
    for i, (row_var, row_name) in enumerate(zip(corr_vars, corr_names)):
        row_str = f"{row_name:<25} "
        for j, col_var in enumerate(corr_vars):
            if j > i: # 上三角留白
                row_str += f"{'-':<10} "
            elif j == i: # 對角線
                row_str += f"{'1.00':<10} "
            else:
                r, p = stats.spearmanr(data_corr[row_var], data_corr[col_var])
                sig = get_sig(p)
                val_str = f"{r:.3f}{sig}"
                row_str += f"{val_str:<10} "
        lines.append(row_str)
        
    lines.append("-" * 90)
    lines.append("註：* p<.10, ** p<.05, *** p<.01")

    # 寫入檔案
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✅ 已生成文件：{OUTPUT_FILE}")
    print("你可以直接打開該檔案，將數據填入 Word 表格中。")

if __name__ == "__main__":
    main()