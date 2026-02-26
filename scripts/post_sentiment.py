from datetime import datetime
import os
import logging
import sqlite3
import sys
import torch
from transformers import pipeline, AutoTokenizer
from queue import Queue
import threading
import gc
from torch.amp import autocast
from functools import lru_cache
import psutil
import time

# ----------------------------
# 環境 & 執行緒設定
# ----------------------------
os.environ["TOKENIZERS_PARALLELISM"] = "true"
torch.set_num_threads(max(1, psutil.cpu_count(logical=False)))  # 使用物理核心數

# ----------------------------
# Logging 設定
# ----------------------------
try:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename="post_sentiment.log",
        filemode='a',
        encoding='utf-8'
    )
    logging.info("Logging initialized (post-sentiment, batch mode, optimized)")
except Exception as e:
    print(f"Logging init error: {e}")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ----------------------------
# SQLite 資料庫 & PRAGMA 優化
# ----------------------------
SQLITE_DB_PATH = "ptt_data.db"

def get_sqlite_connection(in_memory=False):
    if in_memory:
        conn = sqlite3.connect(":memory:")
        disk_conn = sqlite3.connect(SQLITE_DB_PATH)
        disk_conn.backup(conn)
        disk_conn.close()
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=OFF;")
    cur.execute("PRAGMA temp_store=MEMORY;")
    cur.execute("PRAGMA cache_size=10000;")
    return conn

# ----------------------------
# 初始化情緒分析模型（GPU + 混合精度）
# ----------------------------
MODEL_NAME = "nlptown/bert-base-multilingual-uncased-sentiment"
try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
    sentiment_analyzer = pipeline(
        "sentiment-analysis",
        model=MODEL_NAME,
        tokenizer=tokenizer,
        device=0,
        torch_dtype="auto"
    )
    sentiment_analyzer.model.half()
    logging.info("Sentiment analyzer initialized (GPU, mixed precision)")
except Exception as e:
    logging.error(f"Model initialization failed: {e}")
    sys.exit(1)

# ----------------------------
# star_label 轉換為情緒
# ----------------------------
def star_label_to_sentiment(star_label: str) -> str:
    star = int(star_label[0])
    if star <= 2:
        return "NEGATIVE"
    elif star == 3:
        return "NEUTRAL"
    else:
        return "POSITIVE"

# ----------------------------
# 確保需要的欄位已存在並新增索引
# ----------------------------
def ensure_db_columns():
    conn = get_sqlite_connection()
    cur = conn.cursor()
    cols = [
        ("sentiments", "title_star_label TEXT"),
        ("sentiments", "title_sentiment TEXT"),
        ("sentiments", "title_score REAL"),
        ("sentiments", "content_star_label TEXT"),
        ("sentiments", "content_sentiment TEXT"),
        ("sentiments", "content_score REAL"),
        ("push_comments", "push_star_label TEXT"),
        ("push_comments", "push_sentiment TEXT"),
        ("push_comments", "push_score REAL"),
    ]
    for tbl, col_def in cols:
        try:
            cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass
    # 新增索引以加速 IS NULL 查詢
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sentiments_null ON sentiments (title_star_label, content_star_label) WHERE title_star_label IS NULL OR content_star_label IS NULL")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_push_null ON push_comments (push_star_label) WHERE push_star_label IS NULL")
    conn.commit()
    cur.close()
    conn.close()

# ----------------------------
# 預處理文本
# ----------------------------
def preprocess_text(text, max_length):
    if not text:
        return ""
    text = text.strip().replace("\n", " ").replace("\r", "")
    return text[:max_length]

# ----------------------------
# 快取 tokenization
# ----------------------------
@lru_cache(maxsize=10000)
def tokenize_text(text, max_length):
    return tokenizer(text, truncation=True, max_length=max_length, return_tensors="pt")

# ----------------------------
# 資料庫寫入執行緒
# ----------------------------
def db_writer(queue, db_path, table_name):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    batch_updates = []
    batch_size = 10000  # 每 10000 筆提交一次
    total_updated = 0  # 追蹤更新的總筆數
    log_interval = 500  # 每 500 筆記錄日誌
    while True:
        updates = queue.get()
        if updates is None:  # 結束信號
            if batch_updates:
                if table_name == "sentiments":
                    cur.executemany("""
                        UPDATE sentiments
                        SET title_star_label = ?, title_sentiment = ?, title_score = ?,
                            content_star_label = ?, content_sentiment = ?, content_score = ?
                        WHERE id = ?
                    """, batch_updates)
                elif table_name == "push_comments":
                    cur.executemany("""
                        UPDATE push_comments
                        SET push_star_label = ?, push_sentiment = ?, push_score = ?
                        WHERE id = ?
                    """, batch_updates)
                conn.commit()
                total_updated += len(batch_updates)
                logging.info(f"Updated {total_updated-len(batch_updates)+1}–{total_updated} / {total_updated} records in {table_name}")
            cur.close()
            conn.close()
            break
        batch_updates.extend(updates)
        total_updated += len(updates)
        # 每 500 筆記錄日誌
        if total_updated % log_interval < len(updates) or total_updated % log_interval == 0:
            logging.info(f"Updated {total_updated-len(updates)+1}–{total_updated} / {total_updated} records in {table_name}")
        # 每 10000 筆提交
        if len(batch_updates) >= batch_size:
            if table_name == "sentiments":
                cur.executemany("""
                    UPDATE sentiments
                    SET title_star_label = ?, title_sentiment = ?, title_score = ?,
                        content_star_label = ?, content_sentiment = ?, content_score = ?
                    WHERE id = ?
                """, batch_updates)
            elif table_name == "push_comments":
                cur.executemany("""
                    UPDATE push_comments
                    SET push_star_label = ?, push_sentiment = ?, push_score = ?
                    WHERE id = ?
                """, batch_updates)
            conn.commit()
            batch_updates.clear()
        queue.task_done()

# ----------------------------
# 通用批次推論函式（使用 for 迴圈）
# ----------------------------
def batch_inference(texts, batch_size=32, max_length=512):
    results = []
    for i in range(0, len(texts), batch_size):
        start_time = time.time()
        batch = texts[i:i + batch_size]
        with autocast('cuda'):
            out = sentiment_analyzer(
                batch,
                batch_size=batch_size,
                truncation=True,
                max_length=max_length
            )
        for item in out:
            star_label = item["label"]
            confidence = item["score"]
            sentiment = star_label_to_sentiment(star_label)
            results.append((star_label, sentiment, confidence))
        torch.cuda.empty_cache()  # 釋放 GPU 記憶體
        elapsed_time = time.time() - start_time
        logging.debug(f"Batch inference ({len(batch)} items) took {elapsed_time:.2f} seconds")
    return results

# ----------------------------
# 生成器用於資料庫查詢
# ----------------------------
def chunk_generator(cursor, chunk_size):
    while True:
        chunk = cursor.fetchmany(chunk_size)
        if not chunk:
            break
        yield chunk

# ----------------------------
# 分析 sentiments (title & content)
# ----------------------------
def analyze_sentiments_main():
    TITLE_BATCH, TITLE_MAX = 64, 64
    CONT_BATCH, CONT_MAX = 32, 256
    chunk_size = max(TITLE_BATCH, CONT_BATCH)

    # 使用記憶體資料庫
    conn = get_sqlite_connection(in_memory=True)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, content
        FROM sentiments
        WHERE title_star_label IS NULL OR content_star_label IS NULL
        ORDER BY id ASC
    """)

    update_queue = Queue()
    writer_thread = threading.Thread(target=db_writer, args=(update_queue, SQLITE_DB_PATH, "sentiments"))
    writer_thread.start()

    processed = 0
    total = 0

    try:
        for chunk in chunk_generator(cur, chunk_size):
            total += len(chunk)
            ids = [r[0] for r in chunk]
            titles = [preprocess_text(r[1] or "", TITLE_MAX) for r in chunk]
            conts = [preprocess_text(r[2] or "", CONT_MAX) for r in chunk]

            title_res = batch_inference(titles, batch_size=TITLE_BATCH, max_length=TITLE_MAX)
            content_res = batch_inference(conts, batch_size=CONT_BATCH, max_length=CONT_MAX)

            updates = []
            for i, art_id in enumerate(ids):
                t_star, t_sent, t_score = title_res[i]
                c_star, c_sent, c_score = content_res[i]
                updates.append((t_star, t_sent, t_score, c_star, c_sent, c_score, art_id))

            update_queue.put(updates)
            processed += len(updates)

            logging.info(f"Processed articles {total-len(chunk)+1}–{total} / {total}")
            del chunk, titles, conts, title_res, content_res, updates
            gc.collect()

        update_queue.put(None)
        writer_thread.join()

        # 將記憶體資料庫寫回磁碟
        disk_conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.backup(disk_conn)
        disk_conn.close()

        if processed > 0:
            logging.info(f"Final commit of {processed} sentiment updates.")

    except KeyboardInterrupt:
        logging.warning(f"Interrupted by user at article #{total+1}. Exiting early.")
    finally:
        cur.close()
        conn.close()
        logging.info("Sentiment batch update stopped.")

# ----------------------------
# 分析 push_comments
# ----------------------------
def analyze_push_comments():
    PUSH_BATCH, PUSH_MAX = 512, 64
    chunk_size = PUSH_BATCH

    # 使用記憶體資料庫
    conn = get_sqlite_connection(in_memory=True)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, push_content
        FROM push_comments
        WHERE push_star_label IS NULL
        ORDER BY id ASC
    """)

    update_queue = Queue()
    writer_thread = threading.Thread(target=db_writer, args=(update_queue, SQLITE_DB_PATH, "push_comments"))
    writer_thread.start()

    processed = 0
    total = 0

    try:
        for chunk in chunk_generator(cur, chunk_size):
            total += len(chunk)
            push_ids = [r[0] for r in chunk]
            texts = [preprocess_text(r[1] or "", PUSH_MAX) for r in chunk]

            push_res = batch_inference(texts, batch_size=PUSH_BATCH, max_length=PUSH_MAX)
            updates = [
                (star, sent, score, pid)
                for (star, sent, score), pid in zip(push_res, push_ids)
            ]

            update_queue.put(updates)
            processed += len(updates)

            logging.info(f"Processed push_comments {total-len(chunk)+1}–{total} / {total}")
            del chunk, push_ids, texts, push_res, updates
            gc.collect()

        update_queue.put(None)
        writer_thread.join()

        # 將記憶體資料庫寫回磁碟
        disk_conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.backup(disk_conn)
        disk_conn.close()

        if processed > 0:
            logging.info(f"Final commit of {processed} push_comment updates.")

    except KeyboardInterrupt:
        logging.warning(f"Interrupted by user at push_comment #{total+1}. Exiting early.")
    finally:
        cur.close()
        conn.close()
        logging.info("Push_comments batch update stopped.")

# ----------------------------
# Main
# ----------------------------
def main():
    ensure_db_columns()
    analyze_sentiments_main()
    analyze_push_comments()
    logging.info("Post-sentiment batch analysis done.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Main error: {e}")
        sys.exit(1)