import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from collections import Counter

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background-color: #0d0d0d; color: #e8e8e8; }
[data-testid="stSidebar"] { background-color: #111111; border-right: 1px solid #222; }
[data-testid="stSidebar"] * { color: #ccc !important; }
.section-header {
    font-size: 12px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase;
    color: #555; font-family: 'DM Mono', monospace; margin-bottom: 16px;
    padding-bottom: 8px; border-bottom: 1px solid #222;
}
.metric-card {
    background: #161616; border: 1px solid #2a2a2a; border-radius: 8px;
    padding: 20px 24px; margin-bottom: 0; min-height: 110px;
}
.metric-label {
    font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase;
    color: #666; margin-bottom: 6px; font-family: 'DM Mono', monospace;
}
.metric-value {
    font-size: 28px; font-weight: 600; color: #76b900;
    font-family: 'DM Mono', monospace; line-height: 1; word-break: break-word;
}
.metric-sub { font-size: 12px; color: #555; margin-top: 4px; font-family: 'DM Mono', monospace; }
</style>
""", unsafe_allow_html=True)

from utils import load_gt_kpis, load_gt_cluster_dist, load_gt_sequences, load_gt_transition_pairs, CLUSTER_COLORS, CLUSTER_NAME_MAP

ACCENT_COLORS = ["#76b900", "#00c2ff", "#ff6b35", "#b39ddb", "#ffca28", "#ef9a9a", "#80cbc4"]


def plot_cluster_distribution(dist_df):
    sorted_clusters = dist_df.sort_values("pct", ascending=False)
    fig = go.Figure()
    for _, row in sorted_clusters.iterrows():
        fig.add_trace(go.Bar(
            name=row["cluster_name"], x=[row["pct"]], y=[""],
            orientation="h",
            marker_color=CLUSTER_COLORS.get(row["cluster_name"], "#888888"),
            text=f"{row['pct']}%" if row["pct"] >= 4 else "",
            textposition="inside", insidetextanchor="middle",
            textfont=dict(size=11, color="#111111"),
            hovertemplate=f"<b>{row['cluster_name']}</b><br>{row['pct']}%<extra></extra>",
        ))
    fig.update_layout(
        barmode="stack", paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", family="monospace", size=11),
        xaxis=dict(title="% of Developers", range=[0, 100], ticksuffix="%",
                   gridcolor="#2a2a2a", zeroline=False, showline=False,
                   tickfont=dict(color="#ffffff")),
        yaxis=dict(showline=False, showticklabels=False),
        legend=dict(title="Developer Type", bgcolor="#111111", bordercolor="#2a2a2a",
                    borderwidth=1, font=dict(color="#aaaaaa"), itemsizing="constant",
                    tracegroupgap=0, yanchor="top", y=1, xanchor="left", x=1.01),
        margin=dict(l=20, r=160, t=10, b=40), height=120,
        hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900",
                        font=dict(color="#ffffff", size=12)),
    )
    return fig


def plot_transition_heatmap(pairs_df):
    if pairs_df.empty:
        return None
    from_counts = pairs_df.groupby("activity")["count"].sum()
    matrix_data = {}
    for _, row in pairs_df.iterrows():
        frm, to, cnt = row["activity"], row["next_activity"], row["count"]
        total = from_counts[frm]
        if frm not in matrix_data:
            matrix_data[frm] = {}
        matrix_data[frm][to] = round(cnt / total * 100, 1)

    activities = sorted(set(pairs_df["activity"].tolist() + pairs_df["next_activity"].tolist()))
    matrix = pd.DataFrame(0.0, index=activities, columns=activities)
    for frm, tos in matrix_data.items():
        for to, pct in tos.items():
            if frm in matrix.index and to in matrix.columns:
                matrix.loc[frm, to] = pct

    fig = go.Figure(go.Heatmap(
        z=matrix.values, x=list(matrix.columns), y=list(matrix.index),
        colorscale=[[0,"#0d0d0d"],[0.01,"#1a3a00"],[0.3,"#3d6200"],[1.0,"#76b900"]],
        hoverongaps=False,
        hovertemplate="<b>%{y} → %{x}</b><br>%{z:.1f}%<extra></extra>",
        text=[[f"{v:.0f}%" if v > 0 else "" for v in row] for row in matrix.values],
        texttemplate="%{text}", textfont=dict(size=8, color="#ffffff"),
        colorbar=dict(title="Probability (%)", tickfont=dict(color="#aaa"),
                      bgcolor="#111", bordercolor="#2a2a2a"),
    ))
    fig.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", family="monospace", size=10),
        xaxis=dict(tickfont=dict(color="#ffffff"), tickangle=-35, automargin=True, showgrid=False),
        yaxis=dict(tickfont=dict(color="#ffffff"), automargin=True, showgrid=False),
        margin=dict(l=20, r=20, t=20, b=20),
        height=max(400, len(activities) * 40),
        hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900",
                        font=dict(color="#ffffff", size=12)),
    )
    return fig


def plot_sankey(seq_df, title="Developer Activity Pathway"):
    if seq_df.empty:
        return None
    pairs_1_2, pairs_2_3 = [], []
    for dev_id, grp in seq_df.groupby("developer_id"):
        acts = grp.sort_values("seq_rank")["activity"].tolist()
        if len(acts) >= 2: pairs_1_2.append((f"1: {acts[0]}", f"2: {acts[1]}"))
        if len(acts) >= 3: pairs_2_3.append((f"2: {acts[1]}", f"3: {acts[2]}"))
    if not pairs_1_2: return None
    all_flows  = {**Counter(pairs_1_2), **Counter(pairs_2_3)}
    all_nodes  = sorted(set(n for pair in all_flows for n in pair))
    node_index = {n: i for i, n in enumerate(all_nodes)}
    sources, targets, values = [], [], []
    for (src, tgt), val in all_flows.items():
        sources.append(node_index[src]); targets.append(node_index[tgt]); values.append(val)
    node_colors = ["#76b900" if n.startswith("1:") else "#00c2ff" if n.startswith("2:") else "#ff6b35"
                   for n in all_nodes]
    n2, n3 = len(pairs_1_2), len(pairs_2_3)
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(pad=20, thickness=18, line=dict(color="#0d0d0d", width=0.5),
                  label=[n.split(": ", 1)[1] for n in all_nodes], color=node_colors),
        link=dict(source=sources, target=targets, value=values,
                  color="rgba(255,255,255,0.08)"),
    ))
    fig.update_layout(
        title=dict(text=(f"{title}<br><sup>Left = 1st · Middle = 2nd · Right = 3rd "
                         f"({n2:,} devs with 2+ steps, {n3:,} with 3+)</sup>"),
                   font=dict(color="#ffffff", size=13)),
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", size=11, family="monospace"),
        height=520, margin=dict(l=20, r=20, t=80, b=20),
    )
    return fig


# ── Page ──────────────────────────────────────────────────────────────────────
try:
    all_clusters = ["All Clusters"] + list(CLUSTER_NAME_MAP.values())

    with st.sidebar:
        st.markdown("### 📈 Group Trends")
        st.markdown("---")
        st.caption("Select a cluster to drill in, or leave blank to view all.")
        st.markdown("---")
        selected_cluster = st.selectbox("Filter by Cluster", options=all_clusters)

    with st.spinner("Loading data..."):
        kpis_df    = load_gt_kpis()
        dist_df    = load_gt_cluster_dist()
        seq_df     = load_gt_sequences()
        pairs_df   = load_gt_transition_pairs()

    # Filter by cluster
    if selected_cluster == "All Clusters":
        mode     = "All"
        kpi_row  = kpis_df[kpis_df["cluster_name"] == "All"].iloc[0]
        seq_view = seq_df.copy()
        pairs_view = pairs_df[["activity", "next_activity", "count"]].groupby(
            ["activity", "next_activity"])["count"].sum().reset_index()
    else:
        mode     = "Single"
        kpi_row  = kpis_df[kpis_df["cluster_name"] == selected_cluster].iloc[0]
        seq_view = seq_df[seq_df["cluster_name"] == selected_cluster]
        pairs_view = pairs_df[pairs_df["cluster_name"] == selected_cluster][
            ["activity", "next_activity", "count"]]

    # ── Header ──
    label = "All Developers" if mode == "All" else selected_cluster
    st.markdown(f"""
    <div style="border-bottom: 1px solid #222; padding-bottom: 24px; margin-bottom: 28px;">
        <div style="font-size: 32px; font-weight: 600; color: #f0f0f0;">{label}</div>
    </div>""", unsafe_allow_html=True)

    # ── KPI cards ──
    c1, c2, c3, c4 = st.columns(4)
    for col, lbl, value, sub in [
        (c1, "Total Users",         f"{int(kpi_row['total_users']):,}", "unique developers"),
        (c2, "Top Activity",        kpi_row["top_activity"],             "most common"),
        (c3, "Avg Sequence Length", f"{int(kpi_row['avg_seq_len'])}",   "activities per developer"),
        (c4, "Avg Activity Score",  f"{kpi_row['avg_score']}",          f"σ = {kpi_row['std_score']}"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{lbl}</div>
                <div class="metric-value">{value}</div>
                <div class="metric-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if mode == "All":
        st.markdown('<div class="section-header">Cluster Size Distribution</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(plot_cluster_distribution(dist_df), use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

    st.markdown('<div class="section-header">Developer Activity Pathways</div>',
                unsafe_allow_html=True)
    sankey = plot_sankey(seq_view, f"Activity Pathway — {label}")
    if sankey:
        st.plotly_chart(sankey, use_container_width=True)
    else:
        st.caption("Not enough sequential activity data.")

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown('<div class="section-header">Transition Probabilities</div>',
                unsafe_allow_html=True)
    st.caption("Each cell shows the probability (%) of moving from row activity → column activity.")
    heatmap = plot_transition_heatmap(pairs_view)
    if heatmap:
        st.plotly_chart(heatmap, use_container_width=True)
    else:
        st.caption("Not enough data to build transition matrix.")

except Exception as e:
    st.error(f"Error loading data: {e}")