import sqlite3
import pandas as pd
import os
import sys

# ==================== 配置 ====================
DB_PATH = "ptt_data_m.db" 
ARTICLE_CSV = "non_consensus_articles.csv"
PUSH_CSV = "non_consensus_pushes.csv"
# ==============================================

def fetch_non_consensus_data(db_path):
    """查詢並返回未達成共識的 文章標題/內文 和 推文 樣本。"""
    if not os.path.exists(db_path):
        print(f"❌ 錯誤：找不到數據庫檔案 '{db_path}'，請確認是否已運行 db_merger.py。")
        sys.exit(1)

    conn = sqlite3.connect(db_path)

    # 1. 查詢未達成共識的「文章標題/內文」 (修正後的精確查詢)
    q_articles = """
    WITH AllLabeledTasks AS (
        -- 將所有標註結果拆解成獨立的 (article_id, target, annotator, star) 任務
        SELECT article_id, 'title' AS target, annotator, gold_star_title AS star
        FROM manual_labels_articles_all
        WHERE gold_star_title BETWEEN 1 AND 3
        UNION ALL
        SELECT article_id, 'content' AS target, annotator, gold_star_content AS star
        FROM manual_labels_articles_all
        WHERE gold_star_content BETWEEN 1 AND 3
    ),
    GroupedTasks AS (
        -- 計算每個 (article_id, target) 任務有多少人標註
        SELECT article_id, target, COUNT(DISTINCT annotator) AS annotator_count
        FROM AllLabeledTasks
        GROUP BY article_id, target
        HAVING annotator_count >= 2 -- 鎖定至少有兩人標註的任務 (才可能產生歧異)
    ),
    ConsensusTasks AS (
        -- 所有已達成共識的任務 (article_id, target)
        SELECT article_id, target FROM consensus_articles
    )
    -- 找出所有被標註 >= 2 次，但不存在於共識表中的任務
    SELECT
        t1.article_id,
        t1.target,
        s.timestamp,
        s.title,
        s.content,
        s.link,
        GROUP_CONCAT(t2.annotator || ':' || t2.star) AS all_labels
    FROM GroupedTasks t1
    JOIN AllLabeledTasks t2 ON t1.article_id = t2.article_id AND t1.target = t2.target
    JOIN sentiments s ON t1.article_id = s.id
    WHERE (t1.article_id, t1.target) NOT IN ConsensusTasks
    GROUP BY t1.article_id, t1.target
    ORDER BY s.timestamp ASC
    """
    
    # 2. 查詢未達成共識的「推文」
    q_pushes = """
    WITH LabeledPushIDs AS (
        -- 找出所有被至少兩人標註過的推文 ID
        SELECT push_id, COUNT(DISTINCT annotator) AS annotator_count
        FROM manual_labels_pushes_all
        WHERE gold_star BETWEEN 1 AND 3
        GROUP BY push_id
        HAVING annotator_count >= 2
    ),
    NonConsensusPushIDs AS (
        -- 從所有標註推文中，排除已達成共識的
        SELECT push_id
        FROM LabeledPushIDs
        WHERE push_id NOT IN (SELECT push_id FROM consensus_pushes)
    )
    -- 聯結原始數據和所有標註結果
    SELECT 
        p.id AS push_id_db,
        s.id AS article_id_db,
        s.timestamp AS article_timestamp,
        s.title AS article_title,
        p.push_content AS push_text,
        GROUP_CONCAT(mla.annotator || ':' || mla.gold_star) AS all_labels_star
    FROM push_comments p
    JOIN sentiments s ON p.article_id = s.id
    JOIN manual_labels_pushes_all mla ON p.id = mla.push_id
    WHERE p.id IN (SELECT push_id FROM NonConsensusPushIDs)
    GROUP BY p.id
    ORDER BY s.timestamp ASC
    """
    
    df_articles = pd.read_sql_query(q_articles, conn)
    df_pushes = pd.read_sql_query(q_pushes, conn)
    conn.close()
    
    return df_articles, df_pushes

def main():
    df_articles_nc, df_pushes_nc = fetch_non_consensus_data(DB_PATH)

    if df_articles_nc.empty and df_pushes_nc.empty:
        print("✅ 恭喜！文章和推文的歧異樣本數均為 0，無需仲裁。")
        return

    # 輸出文章歧異樣本
    if not df_articles_nc.empty:
        df_articles_nc.to_csv(ARTICLE_CSV, index=False, encoding='utf-8-sig')
        print(f"📄 文章標題/內文 歧異樣本（{len(df_articles_nc)} 筆）已輸出至：{ARTICLE_CSV}")
    else:
        print("✅ 文章標題/內文 歧異樣本數為 0。")

    # 輸出推文歧異樣本
    if not df_pushes_nc.empty:
        df_pushes_nc.to_csv(PUSH_CSV, index=False, encoding='utf-8-sig')
        print(f"💬 推文 歧異樣本（{len(df_pushes_nc)} 筆）已輸出至：{PUSH_CSV}")
    else:
        print("✅ 推文 歧異樣本數為 0。")

if __name__ == "__main__":
    main()