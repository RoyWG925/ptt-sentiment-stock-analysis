# 檔案名稱: analyze_v1_json_dist.py
#
# 目的：
# 1. 讀取 ptt_raw_consensus 資料夾中的 json 檔
# 2. 分析 V1 模型訓練資料 (train.json) 的情緒分佈
# 3. 產出圖表，用於解釋為何 V1 模型會有偏差

import pandas as pd
import matplotlib.pyplot as plt
import os
import json

# ===================================================================
# 1. 設定區
# ===================================================================
TARGET_FOLDER = "ptt_raw_consensus"
FILES_TO_CHECK = ['train.json', 'validation.json', 'test.json']

# ===================================================================
# 2. 繪圖函式
# ===================================================================
def plot_distribution(df, title, filename):
    """繪製圓餅圖"""
    if df.empty: return

    # 統計標籤
    counts = df['label'].value_counts()
    
    # 設定顏色 (依照論文標準配色)
    # 假設 label 是英文字串: negative, neutral, positive
    colors = []
    labels = counts.index
    for lbl in labels:
        l = str(lbl).lower()
        if 'neg' in l: colors.append('#d62728') # 紅
        elif 'neu' in l: colors.append('#7f7f7f') # 灰
        elif 'pos' in l: colors.append('#2ca02c') # 綠
        else: colors.append('skyblue')

    plt.figure(figsize=(8, 8))
    
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
    except: pass

    plt.pie(counts, labels=labels, autopct='%1.1f%%', colors=colors, startangle=140, textprops={'fontsize': 14})
    plt.title(f'{title} 情緒分佈 (N={len(df)})', fontsize=16)
    
    plt.tight_layout()
    plt.savefig(filename, dpi=300)
    print(f"  > 圖表已儲存至: {filename}")
    plt.close()

# ===================================================================
# 3. 主程式
# ===================================================================
def main():
    print(f"🚀 啟動 V1 原始資料集分析 (路徑: {TARGET_FOLDER})...")

    if not os.path.exists(TARGET_FOLDER):
        print(f"❌ 找不到資料夾: {TARGET_FOLDER}，請確認路徑是否正確。")
        return

    # 儲存所有數據的摘要
    summary_data = []

    for fname in FILES_TO_CHECK:
        fpath = os.path.join(TARGET_FOLDER, fname)
        
        if not os.path.exists(fpath):
            print(f"⚠️ 找不到檔案: {fname}，跳過。")
            continue
        
        print(f"\n--- 分析檔案: {fname} ---")
        try:
            # 讀取 JSON
            df = pd.read_json(fpath)
            
            # 確保有 label 欄位
            if 'label' not in df.columns:
                print(f"  ❌ {fname} 內容格式不符 (缺少 'label' 欄位)")
                continue
                
            # 統計
            counts = df['label'].value_counts()
            total = len(df)
            
            print(f"總筆數: {total}")
            print(counts.to_string())
            
            # 特別針對 train.json 畫圖 (因為這是 V1 的靈魂)
            if fname == 'train.json':
                plot_distribution(df, "V1 訓練集 (Train Set)", "v1_train_set_distribution.png")
                
        except Exception as e:
            print(f"  ❌ 讀取錯誤: {e}")

    print("\n🎉 分析完成！")
    print("請查看 'v1_train_set_distribution.png'，這張圖可以用來解釋 V1 模型的偏差來源。")

if __name__ == "__main__":
    main()