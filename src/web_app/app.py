# -*- coding: utf-8 -*-
import sqlite3
from collections import defaultdict, deque
from typing import List, Tuple, Optional
import os
from dotenv import load_dotenv

from flask import Flask, request, redirect, url_for, render_template_string, session
from jinja2 import DictLoader, ChoiceLoader

# 載入環境變數
load_dotenv()

# ============ 基本設定 ============
DB_PATH = os.getenv("DB_PATH", "database/ptt_data.db")
HOST = os.getenv("FLASK_HOST", "0.0.0.0")
PORT = int(os.getenv("FLASK_PORT", "8000"))
DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
SECRET_KEY = os.getenv("FLASK_SECRET_KEY")

if not SECRET_KEY:
    raise ValueError("請在 .env 檔案中設定 FLASK_SECRET_KEY")

# 事件期別（台灣時間）
PERIODS = [
    ("前宣布期", "2025-03-27 00:00:00", "2025-04-02 23:59:59"),
    ("核心期",   "2025-04-03 00:00:00", "2025-04-09 23:59:59"),
    ("後續期",   "2025-04-10 00:00:00", "2025-04-16 23:59:59"),
]
PERIOD_MAP = {p[0]: (p[1], p[2]) for p in PERIODS}

# 一輪的推入樣式：每期 1 標題、1 內文、2 推文
PATTERN = [("title", 1), ("content", 1), ("push", 2)]
# =================================

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ----------------- DB Utils -----------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")
    return conn

def ensure_base_tables():
    """建立必要表：多人標註、queue。"""
    conn = get_conn()
    cur = conn.cursor()
    # 多人標註（三分制）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS manual_labels_articles_all (
            article_id INTEGER,
            annotator TEXT,
            gold_star_title INTEGER CHECK(gold_star_title BETWEEN 1 AND 3),
            gold_star_content INTEGER CHECK(gold_star_content BETWEEN 1 AND 3),
            labeled_at TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY (article_id, annotator)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS manual_labels_pushes_all (
            push_id INTEGER,
            annotator TEXT,
            article_id INTEGER,
            gold_star INTEGER CHECK(gold_star BETWEEN 1 AND 3),
            labeled_at TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY (push_id, annotator)
        );
    """)
    # 固定順序 queue（所有人共用）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS labeling_queue (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT,
            task_type TEXT CHECK(task_type IN ('title','content','push')),
            article_id INTEGER,
            push_id INTEGER
        );
    """)
    conn.commit()
    conn.close()

def period_sql_clause(period_name: Optional[str], ts_col="timestamp"):
    if not period_name or period_name == "全部":
        return "", ()
    start, end = PERIOD_MAP[period_name]
    return f" AND {ts_col} BETWEEN ? AND ? ", (start, end)

# ----------------- Queue Builder -----------------
def fetch_pool(conn) -> Tuple[dict, dict]:
    """依期別取出可用的 article_ids 與 push_ids（已套用看板/標題過濾 & 依時間排序）"""
    art_by_period = {}
    for name, s, e in PERIODS:
        sql = f"""
            SELECT id FROM sentiments
            WHERE board='Stock'
              AND title NOT LIKE 'Re:%'
              AND title NOT LIKE '%新聞%'
              AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC, id ASC
        """
        ids = [r[0] for r in conn.execute(sql, (s, e)).fetchall()]
        art_by_period[name] = deque(ids)

    push_by_period = {}
    for name, s, e in PERIODS:
        sql = f"""
            SELECT p.id
            FROM push_comments p
            JOIN sentiments s ON s.id = p.article_id
            WHERE s.board='Stock'
              AND s.title NOT LIKE 'Re:%'
              AND s.title NOT LIKE '%新聞%'
              AND s.timestamp BETWEEN ? AND ?
            ORDER BY s.timestamp ASC, p.id ASC
        """
        ids = [r[0] for r in conn.execute(sql, (s, e)).fetchall()]
        push_by_period[name] = deque(ids)

    return art_by_period, push_by_period

def queue_exists(conn) -> bool:
    c = conn.execute("SELECT COUNT(*) FROM labeling_queue").fetchone()[0]
    return c > 0

def build_queue(conn):
    """依 PATTERN 把所有期別的資料排成固定順序，存到 labeling_queue。"""
    if queue_exists(conn):
        return  # 已經有 queue 就不重建（避免順序變動）

    art_by_period, push_by_period = fetch_pool(conn)

    # 把每期的 article 序列複製兩份：title 用、content 用（同樣的順序）
    title_by_period = {k: deque(v) for k, v in art_by_period.items()}
    content_by_period = {k: deque(v) for k, v in art_by_period.items()}

    # 檢查是否仍有任何一個期別、任一類型還有剩
    def any_left() -> bool:
        for name, _, _ in PERIODS:
            if title_by_period[name] or content_by_period[name] or push_by_period[name]:
                return True
        return False

    cur = conn.cursor()
    # 以「輪」為單位：三個期別依序跑 PATTERN
    while any_left():
        for period_name, _, _ in PERIODS:
            # 依 PATTERN 依序推入：title×1、content×1、push×2
            for ttype, k in PATTERN:
                for _ in range(k):
                    if ttype == "title":
                        if title_by_period[period_name]:
                            aid = title_by_period[period_name].popleft()
                            cur.execute("INSERT INTO labeling_queue (period, task_type, article_id, push_id) VALUES (?,?,?,NULL)",
                                        (period_name, "title", aid))
                    elif ttype == "content":
                        if content_by_period[period_name]:
                            aid = content_by_period[period_name].popleft()
                            cur.execute("INSERT INTO labeling_queue (period, task_type, article_id, push_id) VALUES (?,?,?,NULL)",
                                        (period_name, "content", aid))
                    else:  # push
                        if push_by_period[period_name]:
                            pid = push_by_period[period_name].popleft()
                            cur.execute("INSERT INTO labeling_queue (period, task_type, article_id, push_id) VALUES (?,?,NULL,?)",
                                        (period_name, "push", pid))
    conn.commit()

# ----------------- Fetch “Next Task” in fixed order -----------------
def next_task_for_annotator(annotator: str, period_filter: str) -> Optional[tuple]:
    """
    從 labeling_queue 依 seq 升序找“你尚未標過的第 1 筆”。
    period_filter 可為 '全部' 或某期名。
    回傳 (seq, period, task_type, article_id, push_id) 或 None
    """
    conn = get_conn()
    extra, params = ("", ())
    if period_filter != "全部":
        extra = " AND q.period = ? "
        params = (period_filter,)

    sql = f"""
    SELECT q.seq, q.period, q.task_type, q.article_id, q.push_id
    FROM labeling_queue q
    WHERE 1=1
      {extra}
      AND (
            (q.task_type='title' AND NOT EXISTS (
                SELECT 1 FROM manual_labels_articles_all a
                WHERE a.article_id = q.article_id AND a.annotator = ?
                  AND a.gold_star_title IS NOT NULL
            ))
         OR (q.task_type='content' AND NOT EXISTS (
                SELECT 1 FROM manual_labels_articles_all a
                WHERE a.article_id = q.article_id AND a.annotator = ?
                  AND a.gold_star_content IS NOT NULL
            ))
         OR (q.task_type='push' AND NOT EXISTS (
                SELECT 1 FROM manual_labels_pushes_all m
                WHERE m.push_id = q.push_id AND m.annotator = ?
                  AND m.gold_star IS NOT NULL
            ))
      )
    ORDER BY q.seq ASC
    LIMIT 1
    """
    row = conn.execute(sql, (*params, annotator, annotator, annotator)).fetchone()
    conn.close()
    return row

def fetch_payload_for_task(seq_row):
    """把 queue 任務變成可顯示的內容。"""
    seq, period, ttype, aid, pid = seq_row
    conn = get_conn()
    if ttype in ("title","content"):
        s = conn.execute("SELECT id, timestamp, title, content FROM sentiments WHERE id=?", (aid,)).fetchone()
        conn.close()
        return {"kind":"article", "seq":seq, "period":period, "task_type":ttype, "article":s}
    else:
        p = conn.execute("""
            SELECT p.id, p.article_id, p.push_content, s.timestamp, s.title
            FROM push_comments p JOIN sentiments s ON s.id=p.article_id
            WHERE p.id=?""", (pid,)).fetchone()
        conn.close()
        return {"kind":"push", "seq":seq, "period":period, "task_type":ttype, "push":p}

# ----------------- Write labels -----------------
def upsert_article(annotator:str, article_id:int, field:str, star:int):
    conn = get_conn()
    # field: 'title' or 'content'
    col = "gold_star_title" if field=="title" else "gold_star_content"
    sql = f"""
        INSERT INTO manual_labels_articles_all (article_id, annotator, {col}, labeled_at)
        VALUES (?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(article_id, annotator) DO UPDATE SET
          {col}=excluded.{col},
          labeled_at=datetime('now','localtime')
    """
    conn.execute(sql, (article_id, annotator, star))
    conn.commit()
    conn.close()

def upsert_push(annotator:str, push_id:int, article_id:int, star:int):
    conn = get_conn()
    sql = """
        INSERT INTO manual_labels_pushes_all (push_id, annotator, article_id, gold_star, labeled_at)
        VALUES (?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(push_id, annotator) DO UPDATE SET
          gold_star=excluded.gold_star,
          labeled_at=datetime('now','localtime')
    """
    conn.execute(sql, (push_id, annotator, article_id, star))
    conn.commit()
    conn.close()

# ----------------- Templates -----------------
BASE_HTML = """
<!doctype html><html lang="zh-Hant"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{{ title or "PTT 情緒標註系統" }}</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif;margin:24px}
.wrap{max-width:1100px;margin:0 auto}
header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.card{border:1px solid #e5e7eb;border-radius:14px;padding:18px;margin:12px 0;box-shadow:0 1px 3px rgba(0,0,0,.05)}
.muted{color:#6b7280;font-size:.9rem}
.title{font-size:1.1rem;font-weight:700;margin:6px 0}
.mono{font-family:ui-monospace,Menlo,Consolas,"SF Mono",monospace;white-space:pre-wrap;word-break:break-word}
.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.btn{padding:10px 14px;border-radius:10px;border:1px solid #d1d5db;background:#fff;cursor:pointer}
.btn.primary{background:#2563eb;color:#fff;border-color:#2563eb}
.btn.gray{background:#f3f4f6}
.pill{padding:6px 10px;border-radius:9999px;background:#f3f4f6;display:inline-block;margin-right:6px}
.score-row{display:flex;gap:10px;margin:10px 0}
.sp{height:8px}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #e5e7eb;padding:8px;text-align:center}
th{background:#f9fafb}
</style></head><body><div class="wrap">
<header>
  <div><strong>PTT 情緒標註系統（三分制/固定順序）</strong></div>
  <div class="muted">
  {% if session.annotator %}
    使用者：<strong>{{ session.annotator }}</strong>
    &nbsp;|&nbsp; 期別視圖：<strong>{{ session.period }}</strong>
    &nbsp;|&nbsp; <a href="{{ url_for('reset') }}">重新設定</a>
    &nbsp;|&nbsp; <a href="{{ url_for('admin') }}">後台儀表板</a>
  {% endif %}
  </div>
</header>
{% block content %}{% endblock %}
</div></body></html>
"""

LOGIN_HTML = """
{% extends "base.html" %}{% block content %}
<div class="card">
  <div class="title">登入 / 設定</div>
  <form method="post" action="{{ url_for('start') }}" class="row">
    <div>使用者 ID：</div>
    <input type="text" name="annotator" required placeholder="例如 A / B / C"/>
    <div>期別視圖：</div>
    <select name="period">
      <option value="全部">全部</option>
      {% for p in periods %}<option value="{{p}}">{{p}}</option>{% endfor %}
    </select>
    <button class="btn primary" type="submit">開始標註</button>
  </form>
  <div class="muted">系統會依 <b>固定 queue</b> 的順序出題：每期 1 標題 → 1 內文 → 2 推文，三期輪替。</div>
</div>
{% endblock %}
"""

TASK_ART_HTML = """
{% extends "base.html" %}{% block content %}
<div class="card">
  <div class="row">
    <div class="pill">SEQ：{{ payload.seq }}</div>
    <div class="pill">期別：{{ payload.period }}</div>
    <div class="pill">任務：{{ '標題' if payload.task_type=='title' else '內文' }}</div>
    <div class="pill">文章 ID：{{ art[0] }}</div>
    <div class="pill">時間：{{ art[1] }}</div>
  </div>
  <div class="sp"></div>
  <div class="title">標題</div>
  <div class="mono">{{ art[2] }}</div>
  <div class="sp"></div>
  <div class="title">內文</div>
  <div class="mono">{{ art[3] or "＜空＞" }}</div>
</div>
<form method="post" action="{{ url_for('label_article') }}" class="card">
  <input type="hidden" name="article_id" value="{{ art[0] }}"/>
  <input type="hidden" name="task_type" value="{{ payload.task_type }}"/>
  <div class="title">給分（1=負面／2=中性／3=正面）</div>
  <div class="score-row">
    {% for s in [1,2,3] %}<label><input type="radio" name="star" value="{{s}}"> {{s}}</label>{% endfor %}
  </div>
  <div class="row">
    <button class="btn primary" name="action" value="save_next">儲存並下一筆</button>
    <button class="btn gray" name="action" value="skip">跳過此筆</button>
  </div>
</form>
{% endblock %}
"""

TASK_PUSH_HTML = """
{% extends "base.html" %}{% block content %}
<div class="card">
  <div class="row">
    <div class="pill">SEQ：{{ payload.seq }}</div>
    <div class="pill">期別：{{ payload.period }}</div>
    <div class="pill">任務：推文</div>
    <div class="pill">推文 ID：{{ push[0] }}</div>
    <div class="pill">所屬文章 ID：{{ push[1] }}</div>
    <div class="pill">文章時間：{{ push[3] }}</div>
  </div>
  <div class="sp"></div>
  <div class="title">所屬文章標題</div>
  <div class="mono">{{ push[4] }}</div>
  <div class="sp"></div>
  <div class="title">推文內容</div>
  <div class="mono">{{ push[2] }}</div>
</div>
<form method="post" action="{{ url_for('label_push') }}" class="card">
  <input type="hidden" name="push_id" value="{{ push[0] }}"/>
  <input type="hidden" name="article_id" value="{{ push[1] }}"/>
  <div class="title">給分（1=負面／2=中性／3=正面）</div>
  <div class="score-row">
    {% for s in [1,2,3] %}<label><input type="radio" name="star" value="{{s}}"> {{s}}</label>{% endfor %}
  </div>
  <div class="row">
    <button class="btn primary" name="action" value="save_next">儲存並下一筆</button>
    <button class="btn gray" name="action" value="skip">跳過此筆</button>
  </div>
</form>
{% endblock %}
"""

ADMIN_HTML = """
{% extends "base.html" %}{% block content %}
<div class="card"><div class="title">後台儀表板</div>
<p class="muted">每期 × 類型（標題/內文/推文）的總樣本數、已被標註的樣本數（至少一人），以及各使用者的完成比例。</p>
</div>
{% for p in periods %}
<div class="card">
  <div class="title">期別：{{ p }}</div>
  <table>
    <thead>
      <tr>
        <th>類型</th>
        <th>總樣本數</th>
        <th>已標註（≥1人）</th>
        {% for u in users %}<th>{{ u }} 完成率</th>{% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for t in ['title','content','push'] %}
      <tr>
        <td>{{ '標題' if t=='title' else ('內文' if t=='content' else '推文') }}</td>
        <td>{{ stats[p][t]['total'] }}</td>
        <td>{{ stats[p][t]['covered'] }}</td>
        {% for u in users %}
          <td>{{ '{:.0f}%'.format(100.0*stats[p][t]['per_user'].get(u,0)/max(stats[p][t]['total'],1)) }}</td>
        {% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endfor %}
{% endblock %}
"""

# Register BASE_HTML as "base.html" so templates using {% extends "base.html" %} work
# regardless of how the app is started (directly or via run_web_app.py).
app.jinja_loader = ChoiceLoader([
    DictLoader({"base.html": BASE_HTML}),
    app.jinja_loader,
])

# ----------------- Routes -----------------
@app.route("/")
def index():
    ensure_base_tables()
    # 若 queue 尚未建立，建一次固定順序
    conn = get_conn()
    build_queue(conn)
    conn.close()

    if "annotator" in session:
        return redirect(url_for("next_item"))
    return render_template_string(LOGIN_HTML, periods=[p[0] for p in PERIODS])

@app.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("index"))

@app.route("/start", methods=["POST"])
def start():
    session["annotator"] = request.form.get("annotator","").strip()
    session["period"] = request.form.get("period","全部")
    if not session["annotator"]:
        return redirect(url_for("index"))
    return redirect(url_for("next_item"))

@app.route("/next")
def next_item():
    annotator = session.get("annotator")
    period = session.get("period","全部")
    if not annotator:
        return redirect(url_for("index"))

    row = next_task_for_annotator(annotator, period)
    if not row:
        msg = "<div class='card'><b>👏 本視圖範圍內的任務已標完。</b> 可到『重新設定』改期別或直接查看後台。</div>"
        return render_template_string(BASE_HTML.replace("{% block content %}{% endblock %}", msg))
    payload = fetch_payload_for_task(row)
    if payload["kind"]=="article":
        return render_template_string(TASK_ART_HTML, payload=payload, art=payload["article"])
    else:
        return render_template_string(TASK_PUSH_HTML, payload=payload, push=payload["push"])

@app.route("/label/article", methods=["POST"])
def label_article():
    annotator = session.get("annotator")
    article_id = int(request.form.get("article_id"))
    task_type = request.form.get("task_type")  # 'title' or 'content'
    action = request.form.get("action")
    star = request.form.get("star", type=int)
    if action=="skip":
        return redirect(url_for("next_item"))
    if star is None:
        return redirect(url_for("next_item"))
    upsert_article(annotator, article_id, task_type, star)
    return redirect(url_for("next_item"))

@app.route("/label/push", methods=["POST"])
def label_push():
    annotator = session.get("annotator")
    push_id = int(request.form.get("push_id"))
    article_id = int(request.form.get("article_id"))
    action = request.form.get("action")
    star = request.form.get("star", type=int)
    if action=="skip":
        return redirect(url_for("next_item"))
    if star is None:
        return redirect(url_for("next_item"))
    upsert_push(annotator, push_id, article_id, star)
    return redirect(url_for("next_item"))

@app.route("/admin")
def admin():
    # 蒐集使用者名單
    conn = get_conn()
    users = set([r[0] for r in conn.execute("SELECT DISTINCT annotator FROM manual_labels_articles_all").fetchall()])
    users |= set([r[0] for r in conn.execute("SELECT DISTINCT annotator FROM manual_labels_pushes_all").fetchall()])
    users = sorted(list(users)) if users else []

    # 統計 per 期 × 類型
    stats = defaultdict(lambda: defaultdict(lambda: {"total":0,"covered":0,"per_user":defaultdict(int)}))

    # 總樣本（依 queue 計，確保與出題一致）
    for pname, _, _ in PERIODS:
        # total
        for ttype in ("title","content","push"):
            total = conn.execute("SELECT COUNT(*) FROM labeling_queue WHERE period=? AND task_type=?", (pname, ttype)).fetchone()[0]
            stats[pname][ttype]["total"] = total

            # covered：至少一人標過
            if ttype in ("title","content"):
                col = "gold_star_title" if ttype=="title" else "gold_star_content"
                covered = conn.execute(f"""
                    SELECT COUNT(DISTINCT q.article_id)
                    FROM labeling_queue q
                    JOIN manual_labels_articles_all a
                      ON a.article_id = q.article_id AND a.{col} IS NOT NULL
                    WHERE q.period=? AND q.task_type=?""", (pname, ttype)).fetchone()[0]
            else:
                covered = conn.execute("""
                    SELECT COUNT(DISTINCT q.push_id)
                    FROM labeling_queue q
                    JOIN manual_labels_pushes_all m
                      ON m.push_id = q.push_id AND m.gold_star IS NOT NULL
                    WHERE q.period=? AND q.task_type='push'""", (pname,)).fetchone()[0]
            stats[pname][ttype]["covered"] = covered

            # per user 完成數
            for u in users:
                if ttype in ("title","content"):
                    col = "gold_star_title" if ttype=="title" else "gold_star_content"
                    cnt = conn.execute(f"""
                        SELECT COUNT(*)
                        FROM labeling_queue q
                        JOIN manual_labels_articles_all a
                          ON a.article_id = q.article_id AND a.{col} IS NOT NULL AND a.annotator=?
                        WHERE q.period=? AND q.task_type=?""", (u, pname, ttype)).fetchone()[0]
                else:
                    cnt = conn.execute("""
                        SELECT COUNT(*)
                        FROM labeling_queue q
                        JOIN manual_labels_pushes_all m
                          ON m.push_id = q.push_id AND m.gold_star IS NOT NULL AND m.annotator=?
                        WHERE q.period=? AND q.task_type='push'""", (u, pname)).fetchone()[0]
                stats[pname][ttype]["per_user"][u] = cnt

    conn.close()
    return render_template_string(ADMIN_HTML, periods=[p[0] for p in PERIODS], users=users, stats=stats)

# ----------------------------------------------
if __name__ == "__main__":
    ensure_base_tables()
    # 首次啟動建立固定順序 queue（若表內已有資料則不動）
    conn = get_conn()
    build_queue(conn)
    conn.close()
    app.run(host=HOST, port=PORT, debug=DEBUG)
