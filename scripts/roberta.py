import sqlite3
from transformers import AutoTokenizer, pipeline
import os

# ----------------------------
# 參數設定
# ----------------------------
DB_PATH    = "ptt_data.db"                             # SQLite 資料庫
MODEL_NAME = "uer/roberta-base-finetuned-jd-binary-chinese"  # 中文情緒分類模型
PUSH_MAX   = 64                                        # 推文截斷長度

# ----------------------------
# 情緒分析模型初始化
# ----------------------------
os.environ["TOKENIZERS_PARALLELISM"] = "true"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
sentiment_analyzer = pipeline(
    "sentiment-analysis",
    model=MODEL_NAME,
    tokenizer=tokenizer,
    device=0
)

# ----------------------------
# 在 push_comments 表新增欄位（若不存在）
# ----------------------------
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE push_comments ADD COLUMN new_label TEXT;")
    cur.execute("ALTER TABLE push_comments ADD COLUMN new_score REAL;")
except sqlite3.OperationalError:
    # 欄位已存在時會拋錯，忽略即可
    pass
conn.commit()

# ----------------------------
# 抓取所有需要更新的推文
# ----------------------------
cur.execute("""
    SELECT id, push_content
    FROM push_comments
    WHERE new_label IS NULL
""")
rows = cur.fetchall()

# ----------------------------
# 對每則推文做情緒分析並更新到資料庫
# ----------------------------
for row in rows:
    pid, text = row
    # 呼叫 pipeline，截斷到 PUSH_MAX
    out = sentiment_analyzer(text, truncation=True, max_length=PUSH_MAX)[0]
    label = out["label"]
    score = float(out["score"])

    # 寫回資料庫
    cur.execute("""
        UPDATE push_comments
        SET new_label = ?, new_score = ?
        WHERE id = ?
    """, (label, score, pid))

# ----------------------------
# 收尾
# ----------------------------
conn.commit()
cur.close()
conn.close()

print(f"共更新 {len(rows)} 筆推文情緒結果。")
