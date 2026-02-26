import os
import re
import time
import sys
import logging
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from transformers import AutoTokenizer, pipeline

# ----------------------------
# 參數設定
# ----------------------------
BOARD = "Stock"                       # PTT 看板名稱
START_PAGE = 8601                    # 起始頁面 index
END_PAGE = 8696                       # 結束頁面 index
SLEEP_SEC = 1                         # 每頁爬取間隔（秒）
LOG_FILE = "stock_crawler.log"        # 日誌檔案
SQLITE_DB_PATH = "ptt_data.db"        # SQLite 檔案
MODEL_NAME = "nlptown/bert-base-multilingual-uncased-sentiment"
TITLE_MAX   = 32                      # 標題截斷長度
CONTENT_MAX = 512                     # 內文截斷長度
PUSH_MAX    = 32                      # 推文截斷長度

# ----------------------------
# 日誌設定
# ----------------------------
try:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        filename=LOG_FILE,
        filemode="w",
        encoding="utf-8"
    )
    logging.info("日誌初始化：crawler + sentiment + parent-child")
except Exception as e:
    print(f"日誌初始化錯誤: {e}")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# ----------------------------
# 資料庫初始化
# ----------------------------
def init_db():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cur = conn.cursor()
    # 加速寫入
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=OFF;")
    # 建立 sentiments 表，新增 parent_id 欄位
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sentiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        board TEXT,
        title TEXT,
        content TEXT,
        link TEXT UNIQUE,
        parent_id INTEGER,                           -- 父文章 ID
        title_star_label TEXT,
        title_sentiment TEXT,
        title_score REAL,
        content_star_label TEXT,
        content_sentiment TEXT,
        content_score REAL,
        FOREIGN KEY(parent_id) REFERENCES sentiments(id)
    );
    """)
    # 建立 push_comments 表
    cur.execute("""
    CREATE TABLE IF NOT EXISTS push_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        push_tag TEXT,
        push_userid TEXT,
        push_content TEXT,
        push_time TEXT,
        push_star_label TEXT,
        push_sentiment TEXT,
        push_score REAL,
        FOREIGN KEY(article_id) REFERENCES sentiments(id) ON DELETE CASCADE
    );
    """)
    conn.commit()
    cur.close()
    conn.close()

# 取得 DB 連線並套用加速設定
def get_sqlite_connection():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=OFF;")
    return conn

# ----------------------------
# 情緒分析模型初始化（全精度）
# ----------------------------
os.environ["TOKENIZERS_PARALLELISM"] = "true"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
sentiment_analyzer = pipeline(
    "sentiment-analysis",
    model=MODEL_NAME,
    tokenizer=tokenizer,
    device=0                 # 不指定 torch_dtype，使用預設 float32
)

def star_label_to_sentiment(star_label: str) -> str:
    star = int(star_label[0])
    if star <= 2:
        return "NEGATIVE"
    elif star == 3:
        return "NEUTRAL"
    else:
        return "POSITIVE"

def analyze_text(text: str, max_length: int):
    if not text:
        return "", "", 0.0
    out = sentiment_analyzer(text, truncation=True, max_length=max_length)[0]
    label = out["label"]
    score = float(out["score"])
    sentiment = star_label_to_sentiment(label)
    return label, sentiment, score

# ----------------------------
# 解析文章時間
# ----------------------------
def fetch_article_time(soup):
    post_time_str = None
    metas = soup.find_all("div", class_="article-metaline") + \
            soup.find_all("div", class_="article-metaline-right")
    for meta in metas:
        tag = meta.find("span", class_="article-meta-tag")
        val = meta.find("span", class_="article-meta-value")
        if tag and val and "時間" in tag.text:
            post_time_str = val.text.strip()
            break
    if not post_time_str:
        txt = soup.get_text()
        m = re.search(r"[A-Z][a-z]{2}\s[A-Z][a-z]{2}\s+\d{1,2}\s\d{2}:\d{2}:\d{2}\s\d{4}", txt)
        if m:
            post_time_str = m.group(0)
    if post_time_str:
        try:
            return datetime.strptime(post_time_str, '%a %b %d %H:%M:%S %Y')
        except:
            return datetime.now().replace(microsecond=0)
    return datetime.now().replace(microsecond=0)

# ----------------------------
# 擷取文章、推文，並找出引用父鏈接
# ----------------------------
def fetch_content_and_push(link_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    cookies = {"over18": "1"}
    try:
        r = requests.get(link_url, headers=headers, cookies=cookies, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        post_time = fetch_article_time(soup)

        # 擷取正文
        main = soup.find(id="main-content")
        if not main:
            return post_time, "", [], None

        for tag in main.find_all("div", class_=re.compile("article-metaline")):
            tag.decompose()
        raw = main.get_text().strip()

        # 截斷到分隔線 "--"
        if "--" in raw:
            raw = raw.split("--", 1)[0].rstrip()

        # 分拆行，過濾出 quoted_lines 與 main_lines
        lines = raw.splitlines()
        main_lines = []
        parent_link = None

        for line in lines:
            s = line.lstrip()
            # 若是引用行，並擷取父文章連結
            if s.startswith("※") or s.startswith("："):
                if s.startswith("※ 文章網址"):
                    m = re.search(r"https?://www\.ptt\.cc/bbs/.+?\.html", s)
                    if m:
                        parent_link = m.group(0)
                continue
            main_lines.append(line)

        content = "\n".join(main_lines).strip()

        # 擷取並合併推文
        raw_pushes = []
        for p in soup.find_all("div", class_="push"):
            raw_pushes.append({
                "tag":     (p.find("span", class_="push-tag").text.strip()      if p.find("span", class_="push-tag")      else ""),
                "userid":  (p.find("span", class_="push-userid").text.strip()   if p.find("span", class_="push-userid")   else ""),
                "content": (p.find("span", class_="push-content").text.lstrip(":").strip() if p.find("span", class_="push-content") else ""),
                "time":    (p.find("span", class_="push-ipdatetime").text.strip() if p.find("span", class_="push-ipdatetime") else "")
            })
        pushes = []
        for p in raw_pushes:
            if pushes and p["userid"] == pushes[-1]["userid"] and p["time"] == pushes[-1]["time"]:
                pushes[-1]["content"] += " " + p["content"]
            else:
                pushes.append(p)

        return post_time, content, pushes, parent_link

    except Exception as e:
        logging.error(f"Fetch 失敗：{link_url}，原因：{e}")
        return datetime.now().replace(microsecond=0), "", [], None

# ----------------------------
# 儲存文章與推文到資料庫，並連結 parent-child
# ----------------------------
def save_article_and_push(ts, board, title, content, link,
                          title_res, content_res, pushes, parent_link):
    conn = get_sqlite_connection()
    cur = conn.cursor()

    # 查 parent_id（若有）
    parent_id = None
    if parent_link:
        cur.execute("SELECT id FROM sentiments WHERE link = ?", (parent_link,))
        row = cur.fetchone()
        if row:
            parent_id = row[0]

    # 插入 sentiments
    try:
        cur.execute("""
            INSERT INTO sentiments
            (timestamp, board, title, content, link, parent_id,
             title_star_label, title_sentiment, title_score,
             content_star_label, content_sentiment, content_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ts.isoformat(), board, title, content, link, parent_id,
            title_res[0], title_res[1], title_res[2],
            content_res[0], content_res[1], content_res[2]
        ))
        article_id = cur.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        logging.info(f"重複，跳過：{link}")
        cur.close()
        conn.close()
        return
    except Exception as e:
        conn.rollback()
        logging.error(f"Insert 文章失敗：{e}")
        cur.close()
        conn.close()
        return

    # 插入 push_comments
    for p in pushes:
        sl, st, sc = analyze_text(p["content"], PUSH_MAX)
        try:
            cur.execute("""
                INSERT INTO push_comments
                (article_id, push_tag, push_userid, push_content, push_time,
                 push_star_label, push_sentiment, push_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article_id, p["tag"], p["userid"], p["content"], p["time"],
                sl, st, sc
            ))
        except Exception as e:
            logging.error(f"Insert 推文失敗：{e}")

    conn.commit()
    cur.close()
    conn.close()

# ----------------------------
# 主爬取 + 同步情緒分析 + parent-child 建立
# ----------------------------
def crawl_and_analyze(start_page, end_page):
    step = 1 if end_page > start_page else -1
    total = abs(end_page - start_page) + 1
    count = 0
    page = start_page

    logging.info(f"開始爬取 {BOARD}：index{start_page}→{end_page}")
    while (step > 0 and page <= end_page) or (step < 0 and page >= end_page):
        count += 1
        logging.info(f"第 {count}/{total} 頁 index{page}")
        url = f"https://www.ptt.cc/bbs/{BOARD}/index{page}.html"
        try:
            resp = requests.get(
                url,
                headers={"User-Agent":"Mozilla/5.0"},
                cookies={"over18":"1"},
                timeout=10
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for art in soup.select(".r-ent"):
                a = art.select_one(".title a")
                if not a:
                    continue
                title = a.text.strip()
                link  = "https://www.ptt.cc" + a["href"]

                ts, content, pushes, parent_link = fetch_content_and_push(link)

                # 情緒分析（全精度）
                title_res   = analyze_text(title,   TITLE_MAX)
                content_res = analyze_text(content, CONTENT_MAX)

                save_article_and_push(
                    ts, BOARD, title, content, link,
                    title_res, content_res, pushes, parent_link
                )

        except Exception as e:
            logging.error(f"第 {page} 頁抓取錯誤：{e}")

        page += step
        time.sleep(SLEEP_SEC)

    logging.info("爬取 + 情緒分析 + parent-child 完成。")

# ----------------------------
# 程式進入點
# ----------------------------
def main():
    init_db()
    crawl_and_analyze(START_PAGE, END_PAGE)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"主程式錯誤：{e}")
        sys.exit(1)
