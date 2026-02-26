from datetime import datetime
import requests
import re
import time
import logging
import sqlite3
import sys
from bs4 import BeautifulSoup

# ----------------------------
# 看板與頁碼參數 (Stock)
# 從 index8525 → index8657
# ----------------------------
BOARD = "Stock"
START_PAGE = 8493
END_PAGE = 8748

SLEEP_SEC = 1
LOG_FILE = "stock_crawler.log"
# 使用單一資料庫檔案，與 dashboard.py 相同
SQLITE_DB_PATH = "ptt_data.db"

# ----------------------------
# Logging 設定
# ----------------------------
try:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        filename=LOG_FILE,
        filemode='w',
        encoding='utf-8'
    )
    logging.info("Logging initialized (Stock SQLite crawler)")
except Exception as e:
    print(f"Logging init error: {e}")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ----------------------------
# 取得 SQLite 連線
# ----------------------------
def get_sqlite_connection():
    return sqlite3.connect(SQLITE_DB_PATH)

# ----------------------------
# 資料庫初始化
# ----------------------------
def init_db():
    conn = get_sqlite_connection()
    cur = conn.cursor()
    # 與 dashboard.py 相容的 sentiments 表結構
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sentiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        board TEXT,
        title TEXT,
        content TEXT,
        link TEXT UNIQUE
    );
    """
    )
    # 與 dashboard.py 相容的 push_comments 表結構
    cur.execute("""
    CREATE TABLE IF NOT EXISTS push_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        push_tag TEXT,
        push_userid TEXT,
        push_content TEXT,
        push_time TEXT,
        FOREIGN KEY(article_id) REFERENCES sentiments(id) ON DELETE CASCADE
    );
    """
    )
    conn.commit()
    cur.close()
    conn.close()

# ----------------------------
# 解析文章時間
# ----------------------------
def fetch_article_time(soup):
    post_time_str = None
    metalines = soup.find_all("div", class_="article-metaline")
    metalines_right = soup.find_all("div", class_="article-metaline-right")
    for meta in metalines + metalines_right:
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
        except ValueError:
            return datetime.now().replace(microsecond=0)
    return datetime.now().replace(microsecond=0)

# ----------------------------
# 抓取文章內容 + 推文
# ----------------------------
def fetch_content_and_push(link_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    cookies = {"over18": "1"}
    try:
        r = requests.get(link_url, headers=headers, cookies=cookies, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        post_time = fetch_article_time(soup)
        # 文章內容
        main = soup.find(id="main-content")
        if main:
            for tag in main.find_all("div", class_=re.compile("article-metaline")):
                tag.decompose()
            content = main.get_text().strip()
        else:
            content = ""
        # 推文列表
        pushes = []
        for p in soup.find_all("div", class_="push"):
            tag = p.find("span", class_="push-tag")
            user = p.find("span", class_="push-userid")
            cont = p.find("span", class_="push-content")
            time_span = p.find("span", class_="push-ipdatetime")
            pushes.append({
                "tag": tag.text.strip() if tag else "",
                "userid": user.text.strip() if user else "",
                "content": cont.text.lstrip(":").strip() if cont else "",
                "time": time_span.text.strip() if time_span else ""
            })
        return post_time, content, pushes
    except Exception as e:
        logging.error(f"Fetch failed for {link_url}: {e}")
        return datetime.now().replace(microsecond=0), "", []

# ----------------------------
# 寫入 SQLite
# ----------------------------
def save_article_and_push(ts, board, title, content, link, pushes):
    conn = get_sqlite_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO sentiments(timestamp, board, title, content, link) VALUES (?, ?, ?, ?, ?)",
            (ts.isoformat(), board, title, content, link)
        )
        article_id = cur.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        logging.info(f"Duplicate, skip: {link}")
        cur.close()
        conn.close()
        return
    except Exception as e:
        conn.rollback()
        logging.error(f"Insert article failed: {e}")
    for p in pushes:
        try:
            cur.execute(
                "INSERT INTO push_comments(article_id, push_tag, push_userid, push_content, push_time) VALUES (?, ?, ?, ?, ?)",
                (article_id, p['tag'], p['userid'], p['content'], p['time'])
            )
        except Exception as e:
            logging.error(f"Insert push failed: {e}")
    conn.commit()
    cur.close()
    conn.close()

# ----------------------------
# 爬取 Stock 看板
# ----------------------------
def crawl_stock(start_page, end_page):
    step = 1 if end_page > start_page else -1
    total = abs(end_page - start_page) + 1
    count = 0
    page = start_page
    logging.info(f"Crawling {BOARD} from index{start_page} to index{end_page}")
    while (step > 0 and page <= end_page) or (step < 0 and page >= end_page):
        count += 1
        logging.info(f"Page index{page} ({count}/{total})")
        url = f"https://www.ptt.cc/bbs/{BOARD}/index{page}.html"
        headers = {"User-Agent": "Mozilla/5.0"}
        cookies = {"over18": "1"}
        try:
            resp = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for art in soup.select(".r-ent"):
                a = art.select_one(".title a")
                if not a: continue
                title = a.text.strip()
                link = "https://www.ptt.cc" + a['href']
                ts, content, pushes = fetch_content_and_push(link)
                save_article_and_push(ts, BOARD, title, content, link, pushes)
        except Exception as e:
            logging.error(f"Error at page {page}: {e}")
        page += step
        time.sleep(SLEEP_SEC)
    logging.info("Crawling completed.")

# ----------------------------
# 主程式
# ----------------------------
def main():
    init_db()
    crawl_stock(START_PAGE, END_PAGE)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Main error: {e}")
        sys.exit(1)
