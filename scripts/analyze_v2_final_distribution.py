# 檔案名稱: analyze_v2_final_distribution.py
#
# 目的：
# 1. 根據 ultimate_data_manager.py 的設定
# 2. 從 DB 讀取 "v2_training_set_master" (真正的 V2 訓練集)
# 3. 分析其情緒分佈 (Pos/Neg/Neu)
# 4. 產出圓餅圖

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os

# ===================================================================
# 1. 設定區
# ===================================================================
DB_PATH = "ptt_data_m.db"
TABLE_NAME = "v2_training_set_master" # 這是 GUI 裡定義的訓練集表格

# ===================================================================
# 2. 主程式
# ===================================================================
def main():
    print(f"🚀 正在讀取 V2 最終訓練集 ({TABLE_NAME})...")

    if not os.path.exists(DB_PATH):
        print(f"❌ 找不到資料庫: {DB_PATH}"); return

    conn = sqlite3.connect(DB_PATH)
    
    try:
        # 讀取資料
        query = f"SELECT label_id FROM {TABLE_NAME}"
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"❌ 讀取資料表失敗: {e}")
        print("請確認你是否已經使用 GUI 工具建立了這個表格。")
        conn.close()
        return
    conn.close()

    if len(df) == 0:
        print("⚠️ 表格是空的！(N=0)")
        return

    # 映射標籤
    # 0: Negative, 1: Neutral, 2: Positive
    label_map = {0: 'Negative', 1: 'Neutral', 2: 'Positive'}
    df['Label_Name'] = df['label_id'].map(label_map)

    # 統計分佈
    counts = df['Label_Name'].value_counts().sort_index()
    proportions = df['Label_Name'].value_counts(normalize=True).sort_index()

    print(f"\n=== V2 訓練集 (v2_training_set_master) 統計 ===")
    print(f"總樣本數 (N): {len(df)}")
    print("-" * 30)
    print(f"{'類別':<10} | {'數量':<8} | {'比例 (%)'}")
    print("-" * 30)
    
    for label in counts.index:
        count = counts[label]
        prop = proportions[label] * 100
        print(f"{label:<10} | {count:<8} | {prop:.2f}%")
    print("-" * 30)

    # 繪圖
    plt.figure(figsize=(8, 8))
    
    # 設定顏色
    colors = []
    labels_for_plot = counts.index
    for lbl in labels_for_plot:
        l_str = str(lbl).lower()
        if 'neg' in l_str: colors.append('#d62728') # 紅
        elif 'neu' in l_str: colors.append('#7f7f7f') # 灰
        elif 'pos' in l_str: colors.append('#2ca02c') # 綠
        else: colors.append('skyblue')

    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
    except: pass

    plt.pie(counts, labels=labels_for_plot, autopct='%1.1f%%', colors=colors, startangle=140, textprops={'fontsize': 14})
    plt.title(f'V2 模型最終訓練集分佈\n(Source: v2_training_set_master, N={len(df)})', fontsize=16)
    
    output_img = "v2_final_training_distribution.png"
    plt.tight_layout()
    plt.savefig(output_img, dpi=300)
    
    print(f"\n✅ 分佈圖已儲存至: {output_img}")

if __name__ == "__main__":
    main()