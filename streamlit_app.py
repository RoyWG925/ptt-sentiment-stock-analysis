# -*- coding: utf-8 -*-
import sqlite3
from collections import defaultdict, deque
from typing import Optional

import pandas as pd
import streamlit as st

# ================== 基本設定 ==================
DB_PATH = "ptt_data.db"
PERIODS = [
    ("前宣布期", "2025-03-27 00:00:00", "2025-04-02 23:59:59"),
    ("核心期",   "2025-04-03 00:00:00", "2025-04-09 23:59:59"),
    ("後續期",   "2025-04-10 00:00:00", "2025-04-16 23:59:59"),
]
PERIOD_MAP = {p[0]: (p[1], p[2]) for p in PERIODS}
PATTERN = [("title", 1), ("content", 1), ("push", 2)]  # 每期每輪：1標題→1內文→2推文
# ==============================================

# -------------- DB Utilities --------------
@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")
    return conn

def ensure_tables(conn):
    cur = conn.cursor()
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

def queue_exists(conn) -> bool:
    c = conn.execute("SELECT COUNT(*) FROM labeling_queue").fetchone()[0]
    return c > 0

def fetch_pool(conn):
    """依期別取出可用的 article_ids 與 push_ids（套過濾，依時間排序）"""
    art_by_period = {}
    for name, s, e in PERIODS:
        sql = """
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
        sql = """
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

def build_queue(conn):
    """依 PATTERN 與期別輪替，建固定順序 queue（只在空時建立）"""
    if queue_exists(conn):
        return
    art_by_period, push_by_period = fetch_pool(conn)
    title_by_period = {k: deque(v) for k, v in art_by_period.items()}
    content_by_period = {k: deque(v) for k, v in art_by_period.items()}

    def any_left():
        for name, _, _ in PERIODS:
            if title_by_period[name] or content_by_period[name] or push_by_period[name]:
                return True
        return False

    cur = conn.cursor()
    while any_left():
        for period_name, _, _ in PERIODS:
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

def next_task_for_annotator(conn, annotator: str, period_filter: str):
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
    return conn.execute(sql, (*params, annotator, annotator, annotator)).fetchone()

def fetch_payload_for_task(conn, seq_row):
    seq, period, ttype, aid, pid = seq_row
    if ttype in ("title","content"):
        s = conn.execute("SELECT id, timestamp, title, content FROM sentiments WHERE id=?", (aid,)).fetchone()
        return {"kind":"article", "seq":seq, "period":period, "task_type":ttype, "article":s}
    else:
        p = conn.execute("""
            SELECT p.id, p.article_id, p.push_content, s.timestamp, s.title
            FROM push_comments p JOIN sentiments s ON s.id=p.article_id
            WHERE p.id=?""", (pid,)).fetchone()
        return {"kind":"push", "seq":seq, "period":period, "task_type":ttype, "push":p}

def upsert_article(conn, annotator:str, article_id:int, field:str, star:int):
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

def upsert_push(conn, annotator:str, push_id:int, article_id:int, star:int):
    sql = """
        INSERT INTO manual_labels_pushes_all (push_id, annotator, article_id, gold_star, labeled_at)
        VALUES (?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(push_id, annotator) DO UPDATE SET
          gold_star=excluded.gold_star,
          labeled_at=datetime('now','localtime')
    """
    conn.execute(sql, (push_id, annotator, article_id, star))
    conn.commit()

# ============== UI ==============
st.set_page_config(page_title="PTT 情緒標註系統（三分制/固定順序）", layout="wide")
st.markdown("<style>.mono{font-family: ui-monospace, Menlo, Consolas; white-space: pre-wrap; word-break: break-word}</style>", unsafe_allow_html=True)

conn = get_conn()
ensure_tables(conn)
build_queue(conn)  # 若 queue 尚未建，會自動建立

# Sidebar：登入與控制
with st.sidebar:
    st.header("登入 / 設定")
    annotator = st.text_input("使用者 ID（必填）", value=st.session_state.get("annotator",""))
    period_view = st.selectbox("期別視圖", ["全部"]+[p[0] for p in PERIODS], index=0)
    st.session_state["annotator"] = annotator
    st.session_state["period_view"] = period_view

    st.divider()
    st.subheader("管理功能")
    if st.button("🔁 重建 queue（小心）"):
        # 會清空 queue 再重建；標註資料不受影響
        conn.execute("DELETE FROM labeling_queue;")
        conn.commit()
        build_queue(conn)
        st.success("已重建 queue。")

tabs = st.tabs(["標註", "後台儀表板"])

# ------------- Tab 1：標註 -------------
with tabs[0]:
    if not annotator.strip():
        st.info("請先在左側輸入『使用者 ID』。")
    else:
        row = next_task_for_annotator(conn, annotator, period_view)
        if not row:
            st.success("👏 本視圖範圍內的任務已標完。可切換期別或前往『後台儀表板』查看進度。")
        else:
            payload = fetch_payload_for_task(conn, row)
            st.caption(f"SEQ: {payload['seq']} ｜ 期別: {payload['period']} ｜ 任務: {'標題' if payload['task_type']=='title' else ('內文' if payload['task_type']=='content' else '推文')}")
            if payload["kind"] == "article":
                art_id, ts, title, content = payload["article"]
                st.write("**文章 ID**：", art_id, "　**時間**：", ts)
                st.write("**標題**")
                st.code(title, language=None)
                st.write("**內文**")
                st.markdown(f"<div class='mono'>{content if content else '＜空＞'}</div>", unsafe_allow_html=True)

                st.subheader("給分（1=負面、2=中性、3=正面）")
                star = st.radio("為此任務給分：",
                                options=[1,2,3],
                                format_func=lambda x: f"{x} 分",
                                horizontal=True,
                                key=f"art_{art_id}_{payload['task_type']}")
                colA, colB = st.columns(2)
                if colA.button("💾 儲存並下一筆", type="primary", use_container_width=True):
                    upsert_article(conn, annotator, art_id, payload["task_type"], int(star))
                    st.experimental_rerun()
                if colB.button("⏭ 跳過此筆", use_container_width=True):
                    # 不寫入，直接跳下一筆（依序）
                    st.experimental_rerun()

            else:  # push
                pid, aid, ptxt, ts, atitle = payload["push"]
                st.write("**推文 ID**：", pid, "　**所屬文章 ID**：", aid, "　**時間**：", ts)
                st.write("**所屬文章標題**")
                st.code(atitle, language=None)
                st.write("**推文內容**")
                st.code(ptxt, language=None)

                st.subheader("給分（1=負面、2=中性、3=正面）")
                star = st.radio("為此推文給分：",
                                options=[1,2,3],
                                format_func=lambda x: f"{x} 分",
                                horizontal=True,
                                key=f"push_{pid}")
                colA, colB = st.columns(2)
                if colA.button("💾 儲存並下一筆", type="primary", use_container_width=True):
                    upsert_push(conn, annotator, pid, aid, int(star))
                    st.experimental_rerun()
                if colB.button("⏭ 跳過此筆", use_container_width=True):
                    st.experimental_rerun()

# ------------- Tab 2：後台儀表板 -------------
with tabs[1]:
    st.subheader("各期 × 類型 完成度")
    # 使用 queue 當「總樣本」的基準（與出題一致）
    users = set([r[0] for r in conn.execute("SELECT DISTINCT annotator FROM manual_labels_articles_all").fetchall()])
    users |= set([r[0] for r in conn.execute("SELECT DISTINCT annotator FROM manual_labels_pushes_all").fetchall()])
    users = sorted(users) if users else []

    stats = defaultdict(lambda: defaultdict(lambda: {"total":0,"covered":0,"per_user":defaultdict(int)}))
    for pname, _, _ in PERIODS:
        for ttype in ("title","content","push"):
            total = conn.execute("SELECT COUNT(*) FROM labeling_queue WHERE period=? AND task_type=?", (pname, ttype)).fetchone()[0]
            stats[pname][ttype]["total"] = total
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

    # 渲染表格
    for pname, _, _ in PERIODS:
        st.markdown(f"### 期別：{pname}")
        header = ["類型","總樣本","已標註（≥1人）"] + [f"{u} 完成率" for u in users]
        rows = []
        for ttype in ("title","content","push"):
            total = stats[pname][ttype]["total"]
            covered = stats[pname][ttype]["covered"]
            row = [
                "標題" if ttype=="title" else ("內文" if ttype=="content" else "推文"),
                total,
                covered
            ]
            for u in users:
                pct = 0.0 if total==0 else 100.0*stats[pname][ttype]["per_user"].get(u,0)/total
                row.append(f"{pct:.0f}%")
            rows.append(row)
        st.dataframe(pd.DataFrame(rows, columns=header), use_container_width=True)
