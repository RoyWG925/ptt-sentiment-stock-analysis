import sqlite3
import pandas as pd
import os
import sys

# ==================== 配置 ====================
DB_PATH = "ptt_data_m.db" 
ARTICLE_CSV = "non_consensus_articles.csv"
PUSH_CSV = "non_consensus_pushes.csv"
ARBITRATION_AGREE_N = 3 # 設定共識人數為 3 (黃金標準)
# ==============================================

def insert_arbitrated_consensus(db_path: str, articles_csv: str, pushes_csv: str):
    """
    從 CSV 讀取仲裁結果，並使用 INSERT OR REPLACE 寫入 consensus_articles/pushes 表。
    此版本使用 CSV 中的實際欄位名稱 (article_id, push_id, Arbitrated_Title, Arbitrated_Star)。
    """
    if not os.path.exists(db_path):
        print(f"❌ 錯誤：找不到數據庫檔案 '{db_path}'。")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    total_inserted = 0
    
    print("==> 開始寫入人工仲裁結果到 DB...")

    # --- 1. 處理文章/標題的仲裁結果 ---
    if os.path.exists(articles_csv):
        print(f"  -> 讀取文章仲裁結果：{articles_csv}")
        df_art = pd.read_csv(articles_csv)
        
        # 文章欄位：article_id, Arbitrated_Title, Arbitrated_Content_Star (根據您的圖片確認)
        ID_COL = 'article_id'
        TITLE_STAR_COL = 'Arbitrated_Title_Star'
        CONTENT_STAR_COL = 'Arbitrated_Content_Star'
        
        df_art_clean = df_art.dropna(subset=[TITLE_STAR_COL, CONTENT_STAR_COL], how='all')
        
        try:
            df_art_clean = df_art_clean.astype({TITLE_STAR_COL: 'Int64', CONTENT_STAR_COL: 'Int64'})
        except:
             print("     [警告] 文章仲裁分數可能包含非數字值，已忽略。")

        for _, row in df_art_clean.iterrows():
            article_id = int(row[ID_COL])
            
            # 插入/更新 標題仲裁結果
            if pd.notna(row[TITLE_STAR_COL]):
                star = int(row[TITLE_STAR_COL])
                cur.execute("""
                    INSERT OR REPLACE INTO consensus_articles 
                    (article_id, target, consensus_star, agree_n) 
                    VALUES (?, 'title', ?, ?)
                """, (article_id, star, ARBITRATION_AGREE_N))
                total_inserted += 1

            # 插入/更新 內文仲裁結果
            if pd.notna(row[CONTENT_STAR_COL]):
                star = int(row[CONTENT_STAR_COL])
                cur.execute("""
                    INSERT OR REPLACE INTO consensus_articles 
                    (article_id, target, consensus_star, agree_n) 
                    VALUES (?, 'content', ?, ?)
                """, (article_id, star, ARBITRATION_AGREE_N))
                total_inserted += 1
        
        print(f"  -> 文章/標題仲裁：完成寫入 {len(df_art_clean)} 筆記錄。")
    else:
        print(f"⚠️ 找不到文章仲裁 CSV 檔：{articles_csv}，跳過。")

    # --- 2. 處理推文的仲裁結果 ---
    if os.path.exists(pushes_csv):
        print(f"==> 讀取推文仲裁結果：{pushes_csv}")
        df_push = pd.read_csv(pushes_csv)
        
        # **推文欄位修正：使用正確的 Arbitrated_Star**
        ID_COL = 'push_id'
        STAR_COL = 'Arbitrated_Star' 
        
        df_push_clean = df_push.dropna(subset=[STAR_COL])
        
        try:
            df_push_clean = df_push_clean.astype({STAR_COL: 'Int64'})
        except:
             print("     [警告] 推文仲裁分數可能包含非數字值，已忽略。")

        for _, row in df_push_clean.iterrows():
            push_id = int(row[ID_COL])
            star = int(row[STAR_COL])
            
            cur.execute("""
                INSERT OR REPLACE INTO consensus_pushes 
                (push_id, consensus_star, agree_n) 
                VALUES (?, ?, ?)
            """, (push_id, star, ARBITRATION_AGREE_N))
            total_inserted += 1
        
        print(f"  -> 推文仲裁：完成寫入 {len(df_push_clean)} 筆記錄。")
    else:
        print(f"⚠️ 找不到推文仲裁 CSV 檔：{pushes_csv}，跳過。")

    conn.commit()
    conn.close()
    
    print("\n=== 寫入報告 ===")
    print(f"總共寫入/更新了 {total_inserted} 筆仲裁後的黃金標準記錄。")
    print("數據已準備好進行最終的統計分析。")


if __name__ == "__main__":
    insert_arbitrated_consensus(DB_PATH, ARTICLE_CSV, PUSH_CSV)