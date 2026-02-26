# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import jieba
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import os

# =====================
# 設定
# =====================
DB_PATH = "ptt_data_m.db"
OUT_DIR = "./wordclouds"
FONT_PATH = "C:/Windows/Fonts/msjh.ttc"  # 改成你電腦的中文字型

PERIODS = [
    ("前宣布期", "2025-03-27 00:00:00", "2025-04-02 23:59:59"),
    ("核心期",   "2025-04-03 00:00:00", "2025-04-09 23:59:59"),
    ("後續期",   "2025-04-10 00:00:00", "2025-04-16 23:59:59"),
]

# 過濾條件：排除這些詞
FILTER_WORDS = {"水桶", "爆", "新聞", "Re"}

os.makedirs(OUT_DIR, exist_ok=True)

# =====================
# 工具函式
# =====================
def fetch_texts(conn, period, col_type):
    """從 DB 根據時期與類型取文本"""
    start, end = [p[1:] for p in PERIODS if p[0] == period][0]

    if col_type in ("title", "content"):
        col = col_type
        sql = f"""
        SELECT {col}
        FROM sentiments
        WHERE board='Stock'
          AND {col} IS NOT NULL
          AND {col} != ''
          AND title NOT LIKE 'Re:%'
          AND title NOT LIKE '%新聞%'
          AND title NOT LIKE '%水桶%'
          AND timestamp BETWEEN ? AND ?
        """
        df = pd.read_sql_query(sql, conn, params=(start, end))
    else:  # 推文
        sql = f"""
        SELECT p.push_content AS text
        FROM push_comments p
        JOIN sentiments s ON s.id = p.article_id
        WHERE s.board='Stock'
          AND p.push_content IS NOT NULL
          AND p.push_content != ''
          AND p.push_content NOT LIKE '%水桶%'
          AND s.title NOT LIKE 'Re:%'
          AND s.title NOT LIKE '%新聞%'
          AND s.title NOT LIKE '%水桶%'
          AND s.timestamp BETWEEN ? AND ?
        """
        df = pd.read_sql_query(sql, conn, params=(start, end))
        df.rename(columns={"text": "content"}, inplace=True)
    return df["content"].dropna().tolist()

def preprocess_texts(texts):
    """斷詞 + 過濾停用詞"""
    import re
    segs = []
    for t in texts:
        # 去除符號
        t = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", " ", str(t))
        for word in jieba.cut(t):
            word = word.strip()
            if len(word) <= 1:  # 避免單字噪音
                continue
            if word in FILTER_WORDS:
                continue
            segs.append(word)
    return segs

def make_wordcloud(words, filename, title):
    text = " ".join(words)
    wc = WordCloud(
        font_path=FONT_PATH,
        width=1200, height=800,
        background_color="white",
        max_words=200,
        collocations=False
    ).generate(text)

    plt.figure(figsize=(10, 6))
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.title(title, fontsize=18)
    plt.tight_layout()
    plt.savefig(filename, dpi=200)
    plt.close()

# =====================
# 主程式
# =====================
def main():
    conn = sqlite3.connect(DB_PATH)

    for period, _, _ in PERIODS:
        for col in ["title", "content", "push"]:
            print(f"⏳ 處理 {period} - {col} ...")
            texts = fetch_texts(conn, period, col)
            if not texts:
                print(f"⚠️ {period} - {col} 無資料，略過。")
                continue
            words = preprocess_texts(texts)
            out_path = os.path.join(OUT_DIR, f"{period}_{col}_wordcloud.png")
            make_wordcloud(words, out_path, f"{period}：{col}")
            print(f"✅ 已生成 {out_path}")

    conn.close()
    print("🎉 全部完成！結果保存在：", OUT_DIR)

if __name__ == "__main__":
    main()
