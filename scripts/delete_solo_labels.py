import sqlite3
import os
import sys

# ==================== 配置 ====================
DB_PATH = "ptt_data_m.db" 
OLD_NAME = "呂筱婕"
NEW_NAME = "呂"
# ==============================================

def rename_annotator_in_db(db_path: str, old_name: str, new_name: str):
    """
    更新 manual_labels_articles_all 和 manual_labels_pushes_all 兩張表中的 annotator 名稱。
    """
    if not os.path.exists(db_path):
        print(f"❌ 錯誤：找不到數據庫檔案 '{db_path}'。請確認檔案是否存在。")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    print(f"==> 準備將標註者名稱從【{old_name}】改為【{new_name}】...")
    
    # --- 1. 更新文章標註表 (manual_labels_articles_all) ---
    sql_articles = f"""
        UPDATE manual_labels_articles_all
        SET annotator = '{new_name}'
        WHERE annotator = '{old_name}';
    """
    cur.execute(sql_articles)
    updated_articles = cur.rowcount
    
    # --- 2. 更新推文標註表 (manual_labels_pushes_all) ---
    sql_pushes = f"""
        UPDATE manual_labels_pushes_all
        SET annotator = '{new_name}'
        WHERE annotator = '{old_name}';
    """
    cur.execute(sql_pushes)
    updated_pushes = cur.rowcount
    
    conn.commit()
    conn.close()
    
    print("\n=== 名稱更新報告 ===")
    print(f"✅ 更新了 manual_labels_articles_all 表：{updated_articles} 筆記錄")
    print(f"✅ 更新了 manual_labels_pushes_all 表：{updated_pushes} 筆記錄")
    print(f"✅ 標註者【{old_name}】已成功更名為【{new_name}】。")


if __name__ == "__main__":
    rename_annotator_in_db(DB_PATH, OLD_NAME, NEW_NAME)