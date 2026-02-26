# 檔案名稱: smart_consensus_split_push_only.py
import sqlite3
import pandas as pd
from sklearn.model_selection import train_test_split
import os

DB_PATH = "ptt_data_m.db"
# ✅ 關鍵修改：輸出到一個全新的資料夾，才不會覆蓋舊資料
OUTPUT_DIR = "./ptt_raw_consensus_push_only" 

def extract_raw_consensus_data_push_only(): # <-- 已改名
    """
    修改版：只提取「推文」的原始共識數據（無任何清理）
    """
    conn = sqlite3.connect(DB_PATH)
    
    # ===== 提取推文共識（無過濾）=====
    push_query = """
    SELECT 
        COALESCE(pc.push_content, '') AS text,
        cp.consensus_star AS raw_label,
        CASE 
            WHEN cp.consensus_star = 1 THEN 'negative'
            WHEN cp.consensus_star = 2 THEN 'neutral'
            WHEN cp.consensus_star = 3 THEN 'positive'
        END AS label,
        'push' AS data_type,
        cp.agree_n AS agreement_count
    FROM consensus_pushes cp
    LEFT JOIN push_comments pc ON cp.push_id = pc.id
    """
    
    # ✅ 關鍵修改：只執行 push_query
    print("--- 正在從資料庫提取『僅推文』的共識資料... ---")
    push_df = pd.read_sql_query(push_query, conn)
    
    # ✅ 關鍵修改：all_consensus 現在就是 push_df
    all_consensus = push_df
    conn.close()
    
    # ===== 僅基本標籤編碼，無任何文本清理 =====
    label_mapping = {'negative': 0, 'neutral': 1, 'positive': 2}
    all_consensus['label_id'] = all_consensus['label'].map(label_mapping)
    
    # 移除無效標籤（極少數情況）
    all_consensus = all_consensus[all_consensus['label_id'].notna()]
    
    print("\n=== 原始共識數據統計（僅推文）===")
    print(f"總共識樣本：{len(all_consensus)} 筆")
    print(f"數據類型分佈：\n{all_consensus['data_type'].value_counts()}")
    print(f"共識人數分佈：\n{all_consensus['agreement_count'].value_counts()}")
    print(f"標籤分佈：\n{all_consensus['label'].value_counts()}")
    
    # 文本質量統計（僅報告，不過濾）
    all_consensus['text_len'] = all_consensus['text'].str.len()
    print(f"\n文本長度統計：")
    print(f"  空文本：{(all_consensus['text_len'] == 0).sum()} 筆")
    print(f"  超短(<5)：{(all_consensus['text_len'] < 5).sum()} 筆")
    print(f"  平均長度：{all_consensus['text_len'].mean():.1f} 字符")
    
    return all_consensus

def smart_three_way_split_raw(df):
    """智慧三集分割（保留所有數據）"""
    
    # (此函數與你提供的版本 100% 相同，不需修改)
    
    # Step 1: 先分測試集（15%）
    train_val_df, test_df = train_test_split(
        df,
        test_size=0.15,
        random_state=42,
        stratify=df['label']
    )
    
    # Step 2: 訓練 vs 驗證（85% → 70/15）
    train_df, val_df = train_test_split(
        train_val_df,
        test_size=0.15 / 0.85,
        random_state=42,
        stratify=train_val_df['label']
    )
    
    # ===== 保存完整數據集 =====
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for name, split_df in [("train", train_df), ("validation", val_df), ("test", test_df)]:
        # 保存完整資訊
        split_df.to_json(
            f"{OUTPUT_DIR}/{name}.json", 
            orient="records", 
            force_ascii=False
        )
        
        print(f"\n{name}: {len(split_df)}筆")
        print(f"  類型分佈：{split_df['data_type'].value_counts().to_dict()}")
        print(f"  標籤分佈：{split_df['label'].value_counts().to_dict()}")
        print(f"  空文本比例：{(split_df['text_len'] == 0).sum() / len(split_df):.1%}")
    
    return train_df, val_df, test_df

if __name__ == "__main__":
    # 1. 提取「僅推文」的數據
    raw_consensus_push_only = extract_raw_consensus_data_push_only()
    
    # 2. 智慧分割
    train_df, val_df, test_df = smart_three_way_split_raw(raw_consensus_push_only)
    
    print(f"\n✅ 『僅推文』資料集分割完成！")
    print(f"  資料已儲存至： {OUTPUT_DIR}")
    print(f"  訓練集：{len(train_df)} 筆 (70%)")
    print(f"  驗證集：{len(val_df)} 筆 (15%)") 
    print(f"  測試集：{len(test_df)} 筆 (15%)")