import streamlit as st
import pandas as pd
import math
import plotly.express as px
from sqlalchemy import create_engine
from scipy.stats import pearsonr, spearmanr
import statsmodels.api as sm
from statsmodels.formula.api import ols

#############################
# 建立 SQLAlchemy engine (SQLite)
#############################
def get_engine():
    db_uri = "sqlite:///ptt_data.db"
    engine = create_engine(db_uri)
    return engine

#############################
# star_label -> 數字
#############################
def star_label_to_int(star_label: str):
    if not star_label:
        return None
    try:
        return int(star_label[0])
    except:
        return None

#############################
# 顏色映射 + HTML 呈現
#############################
def sentiment_color(star_int):
    if star_int == 1:
        return "#d73027"
    elif star_int == 2:
        return "#fc8d59"
    elif star_int == 3:
        return "#fee08b"
    elif star_int == 4:
        return "#d9ef8b"
    elif star_int == 5:
        return "#1a9850"
    return "#cccccc"

def color_star_label(star_label):
    if not star_label:
        return "未知"
    try:
        star_int = int(star_label[0])
        col = sentiment_color(star_int)
        return f"<span style='color:{col}; font-weight:bold;'>{star_label}</span>"
    except:
        return star_label

#############################
# Helper: build WHERE clause for board & date range
#############################
def build_where(board_filter=None, start_date=None, end_date=None):
    clauses = []
    if board_filter and board_filter != "All":
        clauses.append(f"board = '{board_filter}'")
    if start_date:
        clauses.append(f"date(timestamp) >= '{start_date.strftime('%Y-%m-%d')}'")
    if end_date:
        clauses.append(f"date(timestamp) <= '{end_date.strftime('%Y-%m-%d')}'")
    return " AND ".join(clauses) if clauses else ""

#############################
# 讀取文章 (支援看板 & 時間篩選)
#############################
def fetch_articles(board_filter=None, start_date=None, end_date=None):
    engine = get_engine()
    where = build_where(board_filter, start_date, end_date)
    sql = f"""
        SELECT id, timestamp, board, title, content,
               title_star_label, content_star_label
        FROM sentiments
        {f'WHERE {where}' if where else ''}
        ORDER BY timestamp DESC
    """
    df = pd.read_sql_query(sql, engine)
    engine.dispose()
    return df

#############################
# 星等分佈 (1~5)
#############################
def fetch_star_distribution(board_filter=None, start_date=None, end_date=None):
    engine = get_engine()
    where = build_where(board_filter, start_date, end_date)
    # 標題星等
    sql_title = f"""
        SELECT title_star_label AS star_label, COUNT(*) AS cnt
        FROM sentiments
        {f'WHERE {where} AND title_star_label IS NOT NULL' if where else 'WHERE title_star_label IS NOT NULL'}
        GROUP BY title_star_label
    """
    # 內文星等
    sql_content = f"""
        SELECT content_star_label AS star_label, COUNT(*) AS cnt
        FROM sentiments
        {f'WHERE {where} AND content_star_label IS NOT NULL' if where else 'WHERE content_star_label IS NOT NULL'}
        GROUP BY content_star_label
    """
    # 推文星等
    sub_where = build_where(board_filter, start_date, end_date)
    sql_push = f"""
        SELECT p.push_star_label AS star_label, COUNT(*) AS cnt
        FROM push_comments p
        JOIN sentiments s ON p.article_id = s.id
        {f'WHERE {sub_where} AND p.push_star_label IS NOT NULL' if sub_where else 'WHERE p.push_star_label IS NOT NULL'}
        GROUP BY p.push_star_label
    """
    df_title = pd.read_sql_query(sql_title, engine)
    df_content = pd.read_sql_query(sql_content, engine)
    df_push = pd.read_sql_query(sql_push, engine)
    engine.dispose()
    for df in (df_title, df_content, df_push):
        if not df.empty:
            df['star_int'] = df['star_label'].apply(star_label_to_int)
    return df_title, df_content, df_push

#############################
# 時間序列 (timestamp vs star_int) 支援時間篩選
#############################
def fetch_time_series(board_filter=None, start_date=None, end_date=None):
    engine = get_engine()
    where = build_where(board_filter, start_date, end_date)
    sql_sent = f"""
        SELECT id, timestamp, board, title_star_label, content_star_label
        FROM sentiments
        {f'WHERE {where}' if where else ''}
        ORDER BY timestamp ASC
    """
    df_sent = pd.read_sql_query(sql_sent, engine)
    df_push = pd.read_sql_query("SELECT article_id, push_star_label FROM push_comments", engine)
    engine.dispose()
    df_push['push_int'] = df_push['push_star_label'].apply(star_label_to_int)
    df_push_mean = df_push.groupby('article_id', as_index=False)['push_int'] \
                     .mean().rename(columns={'push_int':'push_mean'})
    df = pd.merge(df_sent, df_push_mean, left_on='id', right_on='article_id', how='left')
    df['title_int'] = df['title_star_label'].apply(star_label_to_int)
    df['content_int'] = df['content_star_label'].apply(star_label_to_int)
    return df.dropna(subset=['title_int','content_int','push_mean'])

#############################
# 統計分析: 取 sentiments & push 平均 支援時間篩選
#############################
def get_data_for_analysis(board_filter=None, start_date=None, end_date=None):
    engine = get_engine()
    where = build_where(board_filter, start_date, end_date)
    sql_sent = f"""
        SELECT id, board, title_star_label, content_star_label
        FROM sentiments
        {f'WHERE {where}' if where else ''}
    """
    df_sent = pd.read_sql_query(sql_sent, engine)
    df_push = pd.read_sql_query("SELECT article_id, push_star_label FROM push_comments", engine)
    engine.dispose()
    df_sent['title_int'] = df_sent['title_star_label'].apply(star_label_to_int)
    df_sent['content_int'] = df_sent['content_star_label'].apply(star_label_to_int)
    df_push['push_int'] = df_push['push_star_label'].apply(star_label_to_int)
    df_push_mean = df_push.groupby('article_id', as_index=False)['push_int'] \
                     .mean().rename(columns={'push_int':'push_mean'})
    df = pd.merge(df_sent, df_push_mean, left_on='id', right_on='article_id', how='left')
    return df.dropna(subset=['title_int','content_int','push_mean'])

#############################
# Streamlit 主程式
#############################
st.set_page_config(page_title="PTT Dashboard (SQLite)", layout="wide")

# 選單
menu = st.sidebar.radio("功能選單", ["文章列表", "資料視覺化", "時間序列", "統計分析"], index=0)
if st.sidebar.button("刷新資料"):
    st.experimental_rerun()

# 時間範圍篩選
start_date = st.sidebar.date_input("開始日期", value=None)
end_date = st.sidebar.date_input("結束日期", value=None)

if menu == "文章列表":
    st.title("PTT 文章列表（含情緒）")
    board_selection = st.sidebar.selectbox("篩選看板", ["All", "Gossiping", "NBA", "Stock"])
    df_articles = fetch_articles(board_selection, start_date, end_date)
    total_articles = len(df_articles)
    page_size = 10
    total_pages = math.ceil(total_articles / page_size)
    current_page = st.sidebar.number_input("當前頁碼",
                                           min_value=1,
                                           max_value=max(1,total_pages),
                                           value=1,
                                           step=1)
    st.write(f"當前看板: {board_selection} | 日期: {start_date} ~ {end_date} | 共 {total_articles} 篇文章，每頁 {page_size} 篇，共 {total_pages} 頁，目前第 {current_page} 頁。")
    offset = (current_page - 1) * page_size
    page_df = df_articles.iloc[offset:offset+page_size]
    for _, row in page_df.iterrows():
        st.subheader(f"[{row['board']}] {row['title']}")
        st.write(f"文章ID: {row['id']} | 發文時間: {row['timestamp']}")
        if row.get("title_star_label"):
            st.markdown(f"【標題星等】 {color_star_label(row['title_star_label'])}", unsafe_allow_html=True)
        if row.get("content_star_label"):
            st.markdown(f"【內文星等】 {color_star_label(row['content_star_label'])}", unsafe_allow_html=True)
        content_show = (row['content'] or '')[:1000] + ("..." if row['content'] and len(row['content'])>1000 else '')
        st.write("內文：")
        st.write(content_show)
        pushes = pd.read_sql_query(
            f"SELECT push_tag, push_userid, push_content, push_time, push_star_label FROM push_comments WHERE article_id={row['id']}",
            get_engine()
        )
        if pushes.empty:
            st.write("無推文")
        else:
            with st.expander(f"展開 {len(pushes)} 筆推文"):
                for _, pr in pushes.iterrows():
                    text = f"{pr['push_tag']} {pr['push_userid']}: {pr['push_content']} ({pr['push_time']})"
                    if pr.get('push_star_label'):
                        text += f" | {color_star_label(pr['push_star_label'])}"
                    st.markdown(text, unsafe_allow_html=True)
        st.markdown("---")

elif menu == "資料視覺化":
    st.title("資料視覺化：星等分佈")
    board_selection = st.sidebar.selectbox("篩選看板", ["All", "Gossiping", "NBA", "Stock"])
    df_title, df_content, df_push = fetch_star_distribution(board_selection, start_date, end_date)
    if not df_title.empty:
        st.plotly_chart(px.bar(df_title, x="star_int", y="cnt", title="標題星等分佈"), use_container_width=True)
    if not df_content.empty:
        st.plotly_chart(px.bar(df_content, x="star_int", y="cnt", title="內文星等分佈"), use_container_width=True)
    if not df_push.empty:
        st.plotly_chart(px.bar(df_push, x="star_int", y="cnt", title="推文星等分佈"), use_container_width=True)

elif menu == "時間序列":
    st.title("時間序列分析：星等隨時間變化")
    board_selection = st.sidebar.selectbox("篩選看板", ["All", "Gossiping", "NBA", "Stock"])
    df_ts = fetch_time_series(board_selection, start_date, end_date)
    st.plotly_chart(px.line(df_ts, x="timestamp", y="title_int", title="標題星等隨時間"), use_container_width=True)
    st.plotly_chart(px.line(df_ts, x="timestamp", y="content_int", title="內文星等隨時間"), use_container_width=True)
    st.plotly_chart(px.line(df_ts, x="timestamp", y="push_mean", title="推文平均星等隨時間"), use_container_width=True)

else:  # 統計分析
    st.title("統計分析 (星等)")
    board_selection = st.selectbox("篩選看板", ["All", "Gossiping", "NBA", "Stock"])
    df_all = get_data_for_analysis(board_selection, start_date, end_date)
    st.write(f"篩選: 看板={board_selection}, 日期={start_date}~{end_date}, 有效文章數={len(df_all)}")
    if len(df_all) >= 2:
        st.subheader("描述性統計")
        st.write(df_all[['title_int','content_int','push_mean']].describe().to_dict())
        st.subheader("相關分析")
        for a, b in [("title_int","content_int"), ("title_int","push_mean"), ("content_int","push_mean")]:
            r, p = pearsonr(df_all[a], df_all[b])
            st.write(f"Pearson {a} vs {b}: r={r:.3f}, p={p:.4g}")
        X = sm.add_constant(df_all[['title_int','content_int']])
        y = df_all['push_mean']
        st.subheader("OLS 迴歸")
        st.text(sm.OLS(y, X).fit().summary())
        st.subheader("ANOVA (全看板)")
        df_ab = get_data_for_analysis(None, start_date, end_date)
        if df_ab['board'].nunique() > 1:
            aov = sm.stats.anova_lm(ols('push_mean ~ C(board)', data=df_ab).fit(), typ=2)
            st.dataframe(aov)
        else:
            st.write("板別不足，無法做 ANOVA。")
