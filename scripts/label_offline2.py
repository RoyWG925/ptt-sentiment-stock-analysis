# -*- coding: utf-8 -*-
import sqlite3
from typing import Optional, Tuple
import PySimpleGUI as sg
from dataclasses import dataclass

# ================== 基本設定 ==================
# 標註工具將讀寫此資料庫檔案
# 確保與 build_interleaved_queue_v6.py 使用的 DB 一致
DB_PATH = "ptt_data_n.db"

# 期間設定（用於 UI 下拉選單）
PERIODS = [
    ("前宣布期", "2025-03-27 00:00:00", "2025-04-02 23:59:59"),
    ("核心期",   "2025-04-03 00:00:00", "2025-04-09 23:59:59"),
    ("後續期",   "2025-04-10 00:00:00", "2025-04-16 23:59:59"),
]
# ==============================================


# ------------------ 資料庫相關函式 (DB Utils) ------------------
def get_conn():
    """取得資料庫連線"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def ensure_tables(conn: sqlite3.Connection):
    """確保所有必要的標註記錄資料表都存在"""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS manual_labels_articles_all (
            article_id INTEGER, annotator TEXT, gold_star_title INTEGER,
            gold_star_content INTEGER, labeled_at TEXT,
            PRIMARY KEY (article_id, annotator)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS manual_labels_pushes_all (
            push_id INTEGER, annotator TEXT, article_id INTEGER,
            gold_star INTEGER, labeled_at TEXT,
            PRIMARY KEY (push_id, annotator)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS labeling_queue (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, period TEXT, task_type TEXT,
            article_id INTEGER, push_id INTEGER
        );
    """)
    conn.commit()

def next_task_for_annotator(conn, annotator: str, period_filter: str) -> Optional[Tuple]:
    """
    從已排序的 labeling_queue 中，找出目前標註者尚未標註的第一筆任務。
    """
    params = [annotator, annotator, annotator]
    period_sql = ""
    if period_filter != "全部":
        period_sql = " AND q.period = ? "
        params.insert(0, period_filter)

    sql = f"""
    SELECT q.seq, q.period, q.task_type, q.article_id, q.push_id
    FROM labeling_queue q
    WHERE 1=1
      {period_sql}
      AND NOT (
          (q.task_type = 'title' AND EXISTS (
              SELECT 1 FROM manual_labels_articles_all a
              WHERE a.article_id = q.article_id AND a.annotator = ? AND a.gold_star_title IS NOT NULL
          )) OR
          (q.task_type = 'content' AND EXISTS (
              SELECT 1 FROM manual_labels_articles_all a
              WHERE a.article_id = q.article_id AND a.annotator = ? AND a.gold_star_content IS NOT NULL
          )) OR
          (q.task_type = 'push' AND EXISTS (
              SELECT 1 FROM manual_labels_pushes_all m
              WHERE m.push_id = q.push_id AND m.annotator = ?
          ))
      )
    ORDER BY q.seq ASC
    LIMIT 1
    """
    return conn.execute(sql, params).fetchone()

def get_progress(conn: sqlite3.Connection, annotator: str, period_filter: str) -> Tuple[int, int]:
    """計算標註進度"""
    total_params = []
    period_sql_total = ""
    if period_filter != "全部":
        period_sql_total = " WHERE period = ? "
        total_params.append(period_filter)
    total_count = conn.execute(f"SELECT COUNT(*) FROM labeling_queue {period_sql_total}", total_params).fetchone()[0]

    done_params = [annotator, annotator, annotator]
    if period_filter != "全部":
       done_params.append(period_filter)

    period_sql_done = " AND q.period = ? " if period_filter != "全部" else ""
    done_count_sql = f"""
    SELECT COUNT(DISTINCT q.seq) FROM labeling_queue q
    WHERE (
        (q.task_type = 'title' AND EXISTS (SELECT 1 FROM manual_labels_articles_all a WHERE a.article_id = q.article_id AND a.annotator = ? AND a.gold_star_title IS NOT NULL)) OR
        (q.task_type = 'content' AND EXISTS (SELECT 1 FROM manual_labels_articles_all a WHERE a.article_id = q.article_id AND a.annotator = ? AND a.gold_star_content IS NOT NULL)) OR
        (q.task_type = 'push' AND EXISTS (SELECT 1 FROM manual_labels_pushes_all m WHERE m.push_id = q.push_id AND m.annotator = ?))
    ) {period_sql_done}
    """
    my_done_count = conn.execute(done_count_sql, done_params).fetchone()[0]
    
    return my_done_count, total_count

@dataclass
class ArticlePayload:
    seq: int; period: str; task_type: str; article_id: int
    timestamp: str; title: str; content: Optional[str]

@dataclass
class PushPayload:
    seq: int; period: str; task_type: str; push_id: int; article_id: int
    timestamp: str; article_title: str; text: str

def fetch_payload(conn, seq_row) -> Optional[object]:
    """根據佇列資訊，從資料庫讀取要顯示的文本內容"""
    seq, period, ttype, aid, pid = seq_row
    if ttype in ("title", "content"):
        row = conn.execute("SELECT id, timestamp, title, content FROM sentiments WHERE id=?", (aid,)).fetchone()
        if not row: return None
        return ArticlePayload(seq, period, ttype, row[0], row[1], row[2], row[3] or "")
    elif ttype == "push":
        row = conn.execute("""
            SELECT p.id, p.article_id, s.timestamp, s.title, p.push_content
            FROM push_comments p JOIN sentiments s ON s.id = p.article_id WHERE p.id=?
        """, (pid,)).fetchone()
        if not row: return None
        return PushPayload(seq, period, ttype, row[0], row[1], row[2], row[3] or "", row[4] or "")
    return None

def upsert_article_label(conn, annotator: str, article_id: int, field: str, star: int):
    """寫入或更新文章的標註結果"""
    col = "gold_star_title" if field == "title" else "gold_star_content"
    sql = f"""
        INSERT INTO manual_labels_articles_all (article_id, annotator, {col}, labeled_at)
        VALUES (?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(article_id, annotator) DO UPDATE SET
          {col}=excluded.{col}, labeled_at=datetime('now','localtime')
    """
    conn.execute(sql, (article_id, annotator, star)); conn.commit()

def upsert_push_label(conn, annotator: str, push_id: int, article_id: int, star: int):
    """寫入或更新推文的標註結果"""
    sql = """
        INSERT INTO manual_labels_pushes_all (push_id, annotator, article_id, gold_star, labeled_at)
        VALUES (?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(push_id, annotator) DO UPDATE SET
          gold_star=excluded.gold_star, labeled_at=datetime('now','localtime')
    """
    conn.execute(sql, (push_id, annotator, article_id, star)); conn.commit()

# ================== UI（PySimpleGUI） ==================
def show_login() -> Optional[Tuple[str, str]]:
    """登入視窗，並提示使用者先執行佇列生成腳本"""
    sg.theme("SystemDefault")
    layout = [
        [sg.Text("⚠️ 開始前，請務必先執行 `build_interleaved_queue.py` 更新智慧佇列！", text_color='red')],
        [sg.Text("_"*60)],
        [sg.Text("使用者 ID (必填)", size=(15,1)), sg.Input(key="-UID-", size=(25,1))],
        [sg.Text("期別過濾", size=(15,1)), sg.Combo(values=["全部"]+[p[0] for p in PERIODS], default_value="全部", key="-PERIOD-", readonly=True, size=(25,1))],
        [sg.Button("開始標註", bind_return_key=True), sg.Button("離開")]
    ]
    win = sg.Window("PTT 情緒標註 - 登入", layout)
    
    while True:
        ev, vals = win.read()
        if ev in (sg.WINDOW_CLOSED, "離開"):
            win.close(); return None
        if ev == "開始標註":
            uid = (vals.get("-UID-") or "").strip()
            if not uid:
                sg.popup_ok("請輸入使用者 ID")
                continue
            win.close()
            return uid, vals.get("-PERIOD-", "全部")

def show_main(annotator: str, period_view: str):
    """主標註循環視窗"""
    conn = get_conn()
    ensure_tables(conn)

    while True:
        done_count, total_count = get_progress(conn, annotator, period_view)
        
        row = next_task_for_annotator(conn, annotator, period_view)
        if not row:
            sg.popup_ok(f"恭喜！此視圖 ({period_view}) 範圍內的任務已全部標註完畢！\n\n您的總進度: {done_count} / {total_count}")
            break

        payload = fetch_payload(conn, row)
        if not payload: continue

        progress_text = f"使用者: {annotator} | 篩選: {period_view} | 進度: {done_count} / {total_count}"

        if isinstance(payload, ArticlePayload):
            kind = "標題" if payload.task_type == "title" else "內文"
            header = f"【文章任務】期別：{payload.period}｜佇列序號：{payload.seq}"
            layout = [
                [sg.Text(header, size=(100,1))],
                [sg.Text(progress_text, size=(100,1), justification='center', key="-PROGRESS-")],
                [sg.Text("_"*120)],
                [sg.Text("標題:", size=(5,1)), sg.Multiline(payload.title, size=(95,3), disabled=True)],
                [sg.Text("內文:", size=(5,1)), sg.Multiline(payload.content or "＜空＞", size=(95,20), disabled=True)],
                [sg.Text(f"請為此篇【{kind}】評分 (1=負, 2=中, 3=正):")],
                [sg.Radio("1", "STAR", key="-S1-"), sg.Radio("2", "STAR", key="-S2-", default=True), sg.Radio("3", "STAR", key="-S3-")],
                [sg.Button("儲存 (Enter)", bind_return_key=True), sg.Button("跳過"), sg.Button("結束")]
            ]
            win = sg.Window(f"PTT 標註 - {annotator}", layout, finalize=True)
            
            ev, vals = win.read()
            win.close()
            
            if ev in (sg.WINDOW_CLOSED, "結束"): break
            if ev == "跳過": continue
            if ev == "儲存 (Enter)":
                star = 1 if vals["-S1-"] else 3 if vals["-S3-"] else 2
                upsert_article_label(conn, annotator, payload.article_id, payload.task_type, star)

        elif isinstance(payload, PushPayload):
            header = f"【推文任務】期別：{payload.period}｜佇列序號：{payload.seq}"
            layout = [
                [sg.Text(header, size=(100,1))],
                [sg.Text(progress_text, size=(100,1), justification='center', key="-PROGRESS-")],
                [sg.Text("_"*120)],
                [sg.Text("所屬文章:", size=(10,1)), sg.Multiline(payload.article_title, size=(90,3), disabled=True)],
                [sg.Text("推文內容:", size=(10,1)), sg.Multiline(payload.text, size=(90,10), disabled=True)],
                [sg.Text("請為此則【推文】評分 (1=負, 2=中, 3=正):")],
                [sg.Radio("1", "STAR", key="-S1-"), sg.Radio("2", "STAR", key="-S2-", default=True), sg.Radio("3", "STAR", key="-S3-")],
                [sg.Button("儲存 (Enter)", bind_return_key=True), sg.Button("跳過"), sg.Button("結束")]
            ]
            win = sg.Window(f"PTT 標註 - {annotator}", layout, finalize=True)

            ev, vals = win.read()
            win.close()

            if ev in (sg.WINDOW_CLOSED, "結束"): break
            if ev == "跳過": continue
            if ev == "儲存 (Enter)":
                star = 1 if vals["-S1-"] else 3 if vals["-S3-"] else 2
                upsert_push_label(conn, annotator, payload.push_id, payload.article_id, star)
    
    conn.close()

# ================== 進入點 ==================
if __name__ == "__main__":
    login_info = show_login()
    if login_info:
        annotator_id, period_filter = login_info
        show_main(annotator_id, period_filter)

