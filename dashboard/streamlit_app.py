import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st
from app.anomaly import detect_anomalies
from app.aggregate import compute_daily_metrics

DB_PATH = "cost_guard.db"

st.set_page_config(page_title="AI Cost Guard", layout="wide")
st.title(" AI Cost Guard — Dashboard de Custos de LLM")


@st.cache_data(ttl=5)
def load_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM events", conn)
    conn.close()
    if not df.empty:
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
    return df


df = load_data()

if df.empty:
    st.warning("Nenhum dado ainda. Rode o proxy e dispare algumas requisições primeiro.")
    st.stop()

total_requests = len(df)
total_cost = df["cost_usd"].sum()
cache_hit_rate = (df["cached"].sum() / total_requests) * 100
rate_limited = (df["status"] == "rate_limited").sum()
budget_blocked = (df["status"] == "budget_blocked").sum()
p95_latency = df["latency_ms"].quantile(0.95)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Requisições totais", f"{total_requests:,}")
col2.metric("Custo total (USD)", f"${total_cost:.4f}")
col3.metric("Cache hit rate", f"{cache_hit_rate:.1f}%")
col4.metric("Bloqueios (rate/budget)", f"{rate_limited + budget_blocked}")
col5.metric("Latência p95", f"{p95_latency:.0f} ms")

st.divider()

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Custo por modelo")
    cost_by_model = df.groupby("model")["cost_usd"].sum().reset_index()
    fig1 = px.bar(cost_by_model, x="model", y="cost_usd", color="model")
    st.plotly_chart(fig1, use_container_width=True)

with col_b:
    st.subheader("Top 10 usuários por gasto")
    cost_by_user = df.groupby("user_id")["cost_usd"].sum().nlargest(10).reset_index()
    fig2 = px.bar(cost_by_user, x="user_id", y="cost_usd", color="cost_usd")
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Custo acumulado ao longo do tempo")
df_sorted = df.sort_values("datetime")
df_sorted["cumulative_cost"] = df_sorted["cost_usd"].cumsum()
fig3 = px.line(df_sorted, x="datetime", y="cumulative_cost")
st.plotly_chart(fig3, use_container_width=True)

col_c, col_d = st.columns(2)

with col_c:
    st.subheader("Distribuição de status das requisições")
    status_counts = df["status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    fig4 = px.pie(status_counts, names="status", values="count", hole=0.4)
    st.plotly_chart(fig4, use_container_width=True)

with col_d:
    st.subheader("Latência ao longo do tempo (ms)")
    fig5 = px.scatter(df_sorted, x="datetime", y="latency_ms", color="cached")
    st.plotly_chart(fig5, use_container_width=True)

st.divider()
st.subheader("Eventos recentes")
st.dataframe(df.sort_values("timestamp", ascending=False).head(50), use_container_width=True)
st.divider()
st.subheader("🚨 Alertas de Anomalia (Z-score)")

anomalies_df = detect_anomalies(df, z_threshold=2.5)

if anomalies_df.empty:
    st.success("Nenhuma anomalia detectada nos dados atuais.")
else:
    st.error(f"{len(anomalies_df)} anomalia(s) detectada(s)!")
    st.dataframe(anomalies_df.sort_values("z_score", ascending=False), use_container_width=True)

st.divider()
st.subheader(" Métricas Consolidadas (Batch Rollup Diário)")

col_date, col_button = st.columns([1, 2])
with col_date:
    selected_date = st.date_input("Data para consolidar", value=date.today() - timedelta(days=1))
with col_button:
    st.write("")
    if st.button("Recalcular métricas dessa data"):
        result = compute_daily_metrics(target_date=selected_date.isoformat())
        st.success(f"Métricas recalculadas: {result['total_requests']} requisições, ${result['total_cost_usd']:.4f}")

conn = sqlite3.connect(DB_PATH)
daily_df = pd.read_sql_query("SELECT * FROM daily_metrics ORDER BY date DESC", conn)
conn.close()

if daily_df.empty:
    st.info("Nenhuma métrica consolidada ainda. Clica no botão acima pra gerar.")
else:
    st.dataframe(daily_df, use_container_width=True)