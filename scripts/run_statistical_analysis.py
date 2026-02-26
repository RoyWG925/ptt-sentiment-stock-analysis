# 檔案名稱: run_statistical_analysis_v2.py
#
# (✅ V3 - 最終版：新增 [H2a] 隔夜情緒 vs 每日報酬 相關性檢定)

import pandas as pd
import numpy as np
import os
import scipy.stats as stats # 用於 T-test, ANOVA, Mann-Whitney, Pearson, Spearman
import warnings

# ===================================================================
# 1. 設定區
# ===================================================================
DATA_FILE_PATH = "event_study_final_data_new_formula.csv"

# ===================================================================
# 2. 核心邏輯
# ===================================================================

def main():
    print(f"--- 1/4: 正在從 {DATA_FILE_PATH} 載入資料... ---")
    if not os.path.exists(DATA_FILE_PATH):
        print(f"錯誤：找不到資料檔案 '{DATA_FILE_PATH}'")
        exit()

    df = pd.read_csv(DATA_FILE_PATH, parse_dates=['Date'], index_col='Date')

    if 'Daily_Return' in df.columns:
        df.rename(columns={'Daily_Return': 'R_Daily'}, inplace=True)

    # (規格 2) 定義 P1, P2, P3 的日期列表
    p1_dates = pd.to_datetime(['2025-03-27', '2025-03-28', '2025-03-31', '2025-04-01', '2025-04-02'])
    p2_dates = pd.to_datetime(['2025-04-07', '2025-04-08', '2025-04-09'])
    p3_dates = pd.to_datetime(['2025-04-10', '2025-04-11', '2025-04-14', '2025-04-15', '2025-04-16'])

    conditions = [df.index.isin(p1_dates), df.index.isin(p2_dates), df.index.isin(p3_dates)]
    choices = ['P1 (前期)', 'P2 (衝擊)', 'P3 (暫緩)']
    df['Period'] = np.select(conditions, choices, default='Other')
    
    # (關鍵) 移除 S_Overnight_V2 是 NaN 的資料 (第一天 3/27)
    df.dropna(subset=['S_Overnight_V2', 'R_Daily'], inplace=True)
    print(f"資料載入並分期 (P1, P2, P3) 完成，共 {len(df)} 筆有效資料 (N=12)。")

    # ===================================================================
    # 3. [任務 B] 描述性統計 (圖表 C)
    # ===================================================================
    print("\n--- 2/4: 正在計算「圖表 C：描述性統計」... ---")
    grouped = df.groupby('Period')
    agg_s = grouped['S_Overnight_V2'].agg(N='count', Mean='mean', Std='std')
    agg_r = grouped['R_Daily'].agg(N='count', Mean='mean', Std='std')
    chart_c = pd.concat([agg_s, agg_r], axis=1, keys=['S_Overnight_V2', 'R_Daily'])
    chart_c = chart_c.reindex(['P1 (前期)', 'P2 (衝擊)', 'P3 (暫緩)'])
    print("\n")
    print("圖表 C：P1, P2, P3 描述性統計")
    print("=====================================================================")
    print(chart_c.to_string(float_format="%.4f"))
    print("=====================================================================")
    print("\n")

    # ===================================================================
    # 4. [任務 C] 推論統計 (T-test / ANOVA)
    # ===================================================================
    print("--- 3/4: 正在執行「推論統計」... ---")
    warnings.filterwarnings("ignore", category=stats.ConstantInputWarning)

    s_p1 = df[df['Period'] == 'P1 (前期)']['S_Overnight_V2']; s_p2 = df[df['Period'] == 'P2 (衝擊)']['S_Overnight_V2']; s_p3 = df[df['Period'] == 'P3 (暫緩)']['S_Overnight_V2']
    r_p1 = df[df['Period'] == 'P1 (前期)']['R_Daily']; r_p2 = df[df['Period'] == 'P2 (衝擊)']['R_Daily']; r_p3 = df[df['Period'] == 'P3 (暫緩)']['R_Daily']

    print("推論統計結果 (Part 1)")
    print("=============================================================")
    print("1. ANOVA (三組總體比較)")
    f_s, p_s = stats.f_oneway(s_p1, s_p2, s_p3)
    f_r, p_r = stats.f_oneway(r_p1, r_p2, r_p3)
    print(f"   - S_Overnight_V2: F-statistic = {f_s: .4f}, p-value = {p_s: .4f}")
    print(f"   - R_Daily:          F-statistic = {f_r: .4f}, p-value = {p_r: .4f}")

    print("\n2. Welch's T-test (成對比較, equal_var=False)")
    t_s_12, p_s_12 = stats.ttest_ind(s_p1, s_p2, equal_var=False)
    t_s_23, p_s_23 = stats.ttest_ind(s_p2, s_p3, equal_var=False)
    print("   S_Overnight_V2:")
    print(f"   - P1 vs P2: t-statistic = {t_s_12: .4f}, p-value = {p_s_12: .4f}")
    print(f"   - P2 vs P3: t-statistic = {t_s_23: .4f}, p-value = {p_s_23: .4f}")
    t_r_12, p_r_12 = stats.ttest_ind(r_p1, r_p2, equal_var=False)
    t_r_23, p_r_23 = stats.ttest_ind(r_p2, r_p3, equal_var=False)
    print("\n   R_Daily:")
    print(f"   - P1 vs P2: t-statistic = {t_r_12: .4f}, p-value = {p_r_12: .4f}")
    print(f"   - P2 vs P3: t-statistic = {t_r_23: .4f}, p-value = {p_r_23: .4f}")

    print("\n3. [任務 A] Mann-Whitney U Test (小樣本嚴謹性檢定)")
    u_stat, p_val_u = stats.mannwhitneyu(r_p2, r_p3, alternative='two-sided')
    print(f"   - R_Daily P2 vs P3: U-statistic = {u_stat: .4f}, p-value = {p_val_u: .4f}")
    print("=============================================================")


    # ✅✅✅ --- (新功能) [H2a] 相關性檢定 --- ✅✅✅
    print("\n推論統計結果 (Part 2)")
    print("=============================================================")
    print("4. [H2a] 隔夜情緒 vs. 每日報酬 (相關性檢定)")
    print("   (檢驗 S_Overnight_V2[t] 與 R_Daily[t] 的同期關係, N=12)")
    
    # 提取 T=12 天的完整序列
    s_all = df['S_Overnight_V2']
    r_all = df['R_Daily']

    # 執行 Pearson 線性相關
    corr_p, p_p = stats.pearsonr(s_all, r_all)
    print(f"   - Pearson (線性) 相關: corr = {corr_p: .4f}, p-value = {p_p: .4f}")

    # 執行 Spearman 等級相關
    corr_s, p_s = stats.spearmanr(s_all, r_all)
    print(f"   - Spearman (等級) 相關: corr = {corr_s: .4f}, p-value = {p_s: .4f}")
    
    print("=============================================================")
    print("\n--- 4/4: 統計分析完成 ---")


# ===================================================================
# 3. 執行
# ===================================================================
if __name__ == "__main__":
    main()