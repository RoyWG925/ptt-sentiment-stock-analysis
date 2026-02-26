# -*- coding: utf-8 -*-
import argparse, glob, os, sqlite3
from typing import List, Tuple

SCHEMA_LABELS = """
CREATE TABLE IF NOT EXISTS manual_labels_articles_all (
    article_id INTEGER,
    annotator TEXT,
    gold_star_title INTEGER CHECK(gold_star_title BETWEEN 1 AND 3),
    gold_star_content INTEGER CHECK(gold_star_content BETWEEN 1 AND 3),
    labeled_at TEXT DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (article_id, annotator)
);
CREATE TABLE IF NOT EXISTS manual_labels_pushes_all (
    push_id INTEGER,
    annotator TEXT,
    article_id INTEGER,
    gold_star INTEGER CHECK(gold_star BETWEEN 1 AND 3),
    labeled_at TEXT DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (push_id, annotator)
);
"""

def ensure_labels_schema(conn: sqlite3.Connection):
    conn.executescript(SCHEMA_LABELS)
    conn.commit()

def copy_base_tables_from_main(conn_out: sqlite3.Connection, main_db: str):
    """把 main_db 的 sentiments / push_comments 複製到輸出 DB（若不存在）。"""
    conn_out.execute("ATTACH DATABASE ? AS main_src", (main_db,))
    # sentiments
    if conn_out.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='sentiments'").fetchone()[0] == 0:
        conn_out.execute("CREATE TABLE sentiments AS SELECT * FROM main_src.sentiments")
    else:
        # 如果已存在就清空重建（保持和 main 一致）
        conn_out.execute("DELETE FROM sentiments")
        conn_out.execute("INSERT INTO sentiments SELECT * FROM main_src.sentiments")
    # push_comments
    if conn_out.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='push_comments'").fetchone()[0] == 0:
        conn_out.execute("CREATE TABLE push_comments AS SELECT * FROM main_src.push_comments")
    else:
        conn_out.execute("DELETE FROM push_comments")
        conn_out.execute("INSERT INTO push_comments SELECT * FROM main_src.push_comments")

    conn_out.execute("DETACH DATABASE main_src")
    conn_out.commit()

def merge_labels_from_sources(conn_out: sqlite3.Connection, sources: List[str]) -> Tuple[int,int,int,int]:
    """合併多個來源 DB 的標註到輸出 DB。"""
    ensure_labels_schema(conn_out)
    total_ai=total_au=total_pi=total_pu=0

    for i, src in enumerate(sources, 1):
        alias = f"src{i}"
        print(f"➡️  正在合併 {src} ...")
        conn_out.execute(f"ATTACH DATABASE ? AS {alias}", (src,))

        # 合併文章標註
        conn_out.execute(f"""
            INSERT INTO manual_labels_articles_all (article_id, annotator, gold_star_title, gold_star_content, labeled_at)
            SELECT article_id, annotator, gold_star_title, gold_star_content, labeled_at
            FROM {alias}.manual_labels_articles_all
            WHERE (gold_star_title BETWEEN 1 AND 3) OR (gold_star_content BETWEEN 1 AND 3)
            ON CONFLICT(article_id, annotator) DO UPDATE SET
              gold_star_title   = COALESCE(excluded.gold_star_title, manual_labels_articles_all.gold_star_title),
              gold_star_content = COALESCE(excluded.gold_star_content, manual_labels_articles_all.gold_star_content),
              labeled_at        = CASE
                                    WHEN datetime(excluded.labeled_at) > datetime(manual_labels_articles_all.labeled_at)
                                       THEN excluded.labeled_at
                                    ELSE manual_labels_articles_all.labeled_at
                                  END;
        """)

        # 合併推文標註
        conn_out.execute(f"""
            INSERT INTO manual_labels_pushes_all (push_id, annotator, article_id, gold_star, labeled_at)
            SELECT push_id, annotator, article_id, gold_star, labeled_at
            FROM {alias}.manual_labels_pushes_all
            WHERE gold_star BETWEEN 1 AND 3
            ON CONFLICT(push_id, annotator) DO UPDATE SET
              gold_star  = COALESCE(excluded.gold_star, manual_labels_pushes_all.gold_star),
              labeled_at = CASE
                             WHEN datetime(excluded.labeled_at) > datetime(manual_labels_pushes_all.labeled_at)
                               THEN excluded.labeled_at
                             ELSE manual_labels_pushes_all.labeled_at
                           END;
        """)

        # 🔒 關鍵修正：確保釋放鎖定
        conn_out.commit()
        try:
            conn_out.execute("END;")
        except Exception:
            pass
        try:
            conn_out.execute(f"DETACH DATABASE {alias}")
        except sqlite3.OperationalError as e:
            print(f"⚠️ 無法解除連結 {alias}（可能被鎖住），嘗試強制釋放：{e}")
            conn_out.rollback()
            try:
                conn_out.execute(f"DETACH DATABASE {alias}")
            except Exception:
                pass
        conn_out.commit()

    return total_ai, total_au, total_pi, total_pu

def build_consensus(conn_out: sqlite3.Connection):
    """
    產生兩張表：
      consensus_articles(article_id INTEGER, target TEXT CHECK(target IN('title','content')),
                         consensus_star INTEGER, agree_n INTEGER)
      consensus_pushes(push_id INTEGER, consensus_star INTEGER, agree_n INTEGER)
    規則：至少兩位 annotator 同分即視為共識；若多人、同票，取人數最多；仍平手取 2，其次取較小值。
    """
    # 建表（重建）
    conn_out.execute("DROP TABLE IF EXISTS consensus_articles")
    conn_out.execute("""
        CREATE TABLE consensus_articles (
            article_id INTEGER,
            target TEXT CHECK(target IN ('title','content')),
            consensus_star INTEGER CHECK(consensus_star BETWEEN 1 AND 3),
            agree_n INTEGER,
            PRIMARY KEY(article_id, target)
        )
    """)
    conn_out.execute("DROP TABLE IF EXISTS consensus_pushes")
    conn_out.execute("""
        CREATE TABLE consensus_pushes (
            push_id INTEGER PRIMARY KEY,
            consensus_star INTEGER CHECK(consensus_star BETWEEN 1 AND 3),
            agree_n INTEGER
        )
    """)
    conn_out.commit()

    # -------- 文章：title 共識 --------
    # 欄位聚合：每 (article_id, star) 計算多少 annotator
    conn_out.execute("""
        WITH counts AS (
            SELECT article_id, gold_star_title AS star, COUNT(*) AS c
            FROM manual_labels_articles_all
            WHERE gold_star_title BETWEEN 1 AND 3
            GROUP BY article_id, gold_star_title
        ),
        filtered AS (  -- 至少兩人同分
            SELECT article_id, star, c
            FROM counts
            WHERE c >= 2
        ),
        ranked AS (
            SELECT
              article_id, star, c,
              RANK() OVER (PARTITION BY article_id ORDER BY c DESC,
                           CASE star WHEN 2 THEN 0 ELSE 1 END,  -- 2 優先
                           star ASC) AS rnk
            FROM filtered
        )
        INSERT INTO consensus_articles(article_id, target, consensus_star, agree_n)
        SELECT article_id, 'title', star, c
        FROM ranked
        WHERE rnk = 1
    """)
    conn_out.commit()

    # -------- 文章：content 共識 --------
    conn_out.execute("""
        WITH counts AS (
            SELECT article_id, gold_star_content AS star, COUNT(*) AS c
            FROM manual_labels_articles_all
            WHERE gold_star_content BETWEEN 1 AND 3
            GROUP BY article_id, gold_star_content
        ),
        filtered AS (
            SELECT article_id, star, c
            FROM counts
            WHERE c >= 2
        ),
        ranked AS (
            SELECT
              article_id, star, c,
              RANK() OVER (PARTITION BY article_id ORDER BY c DESC,
                           CASE star WHEN 2 THEN 0 ELSE 1 END,
                           star ASC) AS rnk
            FROM filtered
        )
        INSERT INTO consensus_articles(article_id, target, consensus_star, agree_n)
        SELECT article_id, 'content', star, c
        FROM ranked
        WHERE rnk = 1
    """)
    conn_out.commit()

    # -------- 推文共識 --------
    conn_out.execute("""
        WITH counts AS (
            SELECT push_id, gold_star AS star, COUNT(*) AS c
            FROM manual_labels_pushes_all
            WHERE gold_star BETWEEN 1 AND 3
            GROUP BY push_id, gold_star
        ),
        filtered AS (
            SELECT push_id, star, c
            FROM counts
            WHERE c >= 2
        ),
        ranked AS (
            SELECT
              push_id, star, c,
              RANK() OVER (PARTITION BY push_id ORDER BY c DESC,
                           CASE star WHEN 2 THEN 0 ELSE 1 END,
                           star ASC) AS rnk
            FROM filtered
        )
        INSERT INTO consensus_pushes(push_id, consensus_star, agree_n)
        SELECT push_id, star, c
        FROM ranked
        WHERE rnk = 1
    """)
    conn_out.commit()

def show_summary(conn_out: sqlite3.Connection):
    ca_t = conn_out.execute("SELECT COUNT(*) FROM consensus_articles WHERE target='title'").fetchone()[0]
    ca_c = conn_out.execute("SELECT COUNT(*) FROM consensus_articles WHERE target='content'").fetchone()[0]
    cp   = conn_out.execute("SELECT COUNT(*) FROM consensus_pushes").fetchone()[0]
    la   = conn_out.execute("SELECT COUNT(*) FROM manual_labels_articles_all").fetchone()[0]
    lp   = conn_out.execute("SELECT COUNT(*) FROM manual_labels_pushes_all").fetchone()[0]
    print("\n=== 共識統計（至少兩人同分） ===")
    print(f"文章-標題 共識數：{ca_t}")
    print(f"文章-內文 共識數：{ca_c}")
    print(f"推文 共識數   ：{cp}")
    print("\n=== 標註總筆數（合併後） ===")
    print(f"文章標註 rows：{la}")
    print(f"推文標註 rows：{lp}")

def main():
    ap = argparse.ArgumentParser(description="Merge multiple PTT label DBs into a new DB and compute consensus (>=2 annotators).")
    ap.add_argument("--main", required=True, help="主要 DB（複製 sentiments / push_comments 的來源）")
    ap.add_argument("--sources", nargs="*", default=[], help="要合併的其他 DB 清單")
    ap.add_argument("--glob", default="", help="用萬用字元收集來源（例如 'ptt_data*.db'）")
    ap.add_argument("--out", default="ptt_data_m.db", help="輸出合併後的新 DB 檔名")
    args = ap.parse_args()

    # 蒐集來源
    srcs: List[str] = []
    if args.glob:
        srcs.extend(sorted(glob.glob(args.glob)))
    srcs.extend(args.sources)
    # 去掉 --main 本身（避免重複合併）
    srcs = [s for s in srcs if os.path.isfile(s) and os.path.abspath(s) != os.path.abspath(args.main)]

    if not os.path.isfile(args.main):
        print(f"❌ 找不到 --main：{args.main}")
        return
    if not srcs:
        print("❌ 沒有可合併的來源 DB，請用 --sources 或 --glob 指定（會自動排除 --main）。")
        return

    # 建立輸出 DB
    if os.path.exists(args.out):
        os.remove(args.out)
    conn_out = sqlite3.connect(args.out)
    conn_out.execute("PRAGMA journal_mode=WAL;")
    conn_out.execute("PRAGMA synchronous=OFF;")

    print(f"==> 建立輸出 DB：{args.out}")
    print(f"==> 從主庫複製 sentiments / push_comments：{args.main}")
    copy_base_tables_from_main(conn_out, args.main)

    # 先合併 --main 的標註（如果 main 裡也有標）
    print(f"==> 合併主庫標註：{args.main}")
    merge_labels_from_sources(conn_out, [args.main])

    # 再合併其他來源標註
    print(f"==> 合併其他來源：{', '.join(srcs)}")
    merge_labels_from_sources(conn_out, srcs)

    # 建立共識
    print("==> 計算共識（>=2 人同分） ...")
    build_consensus(conn_out)

    # 總結
    show_summary(conn_out)
    conn_out.close()
    print("\n✅ 完成！合併與共識已寫入：", args.out)

if __name__ == "__main__":
    main()
