# 檔案名稱: analyze_v2_training_dist.py
#
# 目的：
# 1. 讀取資料庫中的 manual_labels (V1基底) 和 manual_labels_extra (V2補強)
# 2. 合併這兩份資料，模擬 V2 模型的完整訓練集
# 3. 產出情緒分佈圖，證明 V2 的資料品質/平衡度優於 V1

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os

# ===================================================================
# 1. 設定區
# ===================================================================
DB_PATH = "ptt_data_m.db"
# V2 = V1 Base + Extra Augmentation
TABLES_TO_MERGE = ['manual_labels', 'manual_labels_extra']

# ===================================================================
# 2. 主程式
# ===================================================================
def main():
    print(f"🚀 啟動 V2 模型訓練資料集分析 (合併 {TABLES_TO_MERGE})...")

    if not os.path.exists(DB_PATH):
        print(f"❌ 找不到資料庫: {DB_PATH}"); return

    conn = sqlite3.connect(DB_PATH)
    
    df_list = []
    
    # 讀取並合併資料表
    for table in TABLES_TO_MERGE:
        try:
            query = f"SELECT label FROM {table}"
            df_temp = pd.read_sql_query(query, conn)
            print(f"  > 讀取 {table}: {len(df_temp)} 筆")
            df_list.append(df_temp)
        except Exception as e:
            print(f"  ⚠️ 無法讀取 {table} (可能不存在): {e}")

    conn.close()

    if not df_list:
        print("❌ 沒有讀取到任何資料。")
        return

    # 合併所有資料
    df_v2 = pd.concat(df_list, ignore_index=True)
    
    # 處理標籤 (數字轉文字)
    # 假設 0:Neg, 1:Neu, 2:Pos (依照一般慣例)
    label_map = {0: 'Negative', 1: 'Neutral', 2: 'Positive'}
    
    # 檢查是否為數字型別
    if pd.api.types.is_numeric_dtype(df_v2['label']):
        df_v2['Label_Name'] = df_v2['label'].map(label_map)
    else:
        # 若已經是文字，統一小寫處理
        df_v2['Label_Name'] = df_v2['label'].astype(str).str.lower().str.capitalize()

    # 統計分佈
    counts = df_v2['Label_Name'].value_counts().sort_index()
    proportions = df_v2['Label_Name'].value_counts(normalize=True).sort_index()

    print("\n=== V2 完整訓練資料集 (Total Combined) ===")
    print(f"總樣本數 (N): {len(df_v2)}")
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
    # 確保顏色對應正確
    labels_for_plot = counts.index
    for lbl in labels_for_plot:
        l_str = str(lbl).lower()
        if 'neg' in l_str: colors.append('#d62728')
        elif 'neu' in l_str: colors.append('#7f7f7f')
        elif 'pos' in l_str: colors.append('#2ca02c')
        else: colors.append('skyblue')

    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
    except: pass

    plt.pie(counts, labels=labels_for_plot, autopct='%1.1f%%', colors=colors, startangle=140, textprops={'fontsize': 14})
    plt.title(f'V2 模型完整訓練集分佈 (Base + Extra)\nTotal N={len(df_v2)}', fontsize=16)
    
    output_img = "v2_training_distribution.png"
    plt.tight_layout()
    plt.savefig(output_img, dpi=300)
    
    print(f"\n✅ 分佈圖已儲存至: {output_img}")
    print("💡 觀察重點：V2 的資料量是否更大？分佈是否比 V1 更接近真實情況（或更能平衡類別）？")

if __name__ == "__main__":
    main()