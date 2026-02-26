import sqlite3
import yfinance as yf

def store_taiex_full_in_db(db_path: str, start_date: str, end_date: str):
    """
    用 yfinance 下載 ^TWII，並把 Open/High/Low/Close/Volume 全部存進 SQLite 的 market_index 表。
    """
    # 1️⃣ 下載資料
    df = yf.download("^TWII", start=start_date, end=end_date, progress=False)
    if df.empty:
        raise RuntimeError("無法取得 TAIEX 資料，請檢查網路或日期範圍。")

    # 2️⃣ 連到 DB
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 3️⃣ 建表（含 volume/high/low）
    cur.execute("""
    CREATE TABLE IF NOT EXISTS market_index (
        date        TEXT    PRIMARY KEY,
        open_price  REAL,
        high_price  REAL,
        low_price   REAL,
        close_price REAL,
        volume      INTEGER
    );
    """)

    # 4️⃣ 存每一天
    for idx, row in df.iterrows():
        date_str   = idx.strftime("%Y-%m-%d")
        cur.execute("""
            INSERT OR REPLACE INTO market_index
            (date, open_price, high_price, low_price, close_price, volume)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            date_str,
            float(row["Open"]),
            float(row["High"]),
            float(row["Low"]),
            float(row["Close"]),
            int(row["Volume"])
        ))
    conn.commit()
    cur.close()
    conn.close()
    print(f"已把 {len(df)} 筆 TAIEX 全指標資料存入 {db_path}。")


if __name__ == "__main__":
    store_taiex_full_in_db(
        db_path="ptt_data.db",
        start_date="2025-03-01",
        end_date="2025-05-22"
    )
