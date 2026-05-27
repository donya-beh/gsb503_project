import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
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
    font-family: 'DM Mono', monospace; line-height: 1;
    word-break: break-word;
}
.metric-sub { font-size: 12px; color: #555; margin-top: 4px; font-family: 'DM Mono', monospace; }
</style>
""", unsafe_allow_html=True)

ACCENT_COLORS = ["#76b900", "#00c2ff", "#ff6b35", "#b39ddb", "#ffca28", "#ef9a9a", "#80cbc4"]

CLUSTER_COLORS = {
    "Lapsed":         "#cccccc",
    "Zero-Touch":     "#a8c4e0",
    "DLI Self-Paced": "#4a90d9",
    "Live Event":     "#b8d98d",
    "On-Demand":      "#7eb3d8",
    "Power Users":    "#76b900",
    "Newcomers":      "#e8a87c",
}


from utils import load_data


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_sequences(df):
    """Return per-developer ordered activity sequences."""
    return (
        df.sort_values(["developer_id", "activity_date"])
        .groupby("developer_id")["activity"]
        .apply(list)
        .reset_index()
    )


def compute_metrics(df):
    seqs = get_sequences(df)
    total_users    = df["developer_id"].nunique()
    unique_seqs    = seqs["activity"].apply(tuple).nunique()
    import math
    avg_seq_len  = math.ceil(seqs["activity"].apply(len).mean())
    top_activity = df["activity"].value_counts().idxmax()
    avg_score    = round(df["activity_score"].mean(), 1)
    std_score    = round(df["activity_score"].std(), 2)

    return total_users, unique_seqs, avg_seq_len, top_activity, avg_score, std_score


# ── Charts ────────────────────────────────────────────────────────────────────
def plot_cluster_distribution(df):
    """Stacked horizontal bar showing cluster proportions across all developers."""
    dev_counts = df.drop_duplicates("developer_id").groupby("cluster_name")["developer_id"].nunique()
    total      = dev_counts.sum()
    pcts       = (dev_counts / total * 100).round(1)

    # Sort clusters by proportion descending
    sorted_clusters = pcts.sort_values(ascending=False).index.tolist()

    fig = go.Figure()
    for cluster in sorted_clusters:
        pct = pcts.get(cluster, 0)
        fig.add_trace(go.Bar(
            name=cluster,
            x=[pct],
            y=[""],
            orientation="h",
            marker_color=CLUSTER_COLORS.get(cluster, "#888888"),
            text=f"{pct}%" if pct >= 4 else "",
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(size=11, color="#111111"),
            hovertemplate=f"<b>{cluster}</b><br>{pct}%<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        paper_bgcolor="#0d0d0d",
        plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", family="monospace", size=11),
        xaxis=dict(title="% of Developers", range=[0, 100], ticksuffix="%",
                   gridcolor="#2a2a2a", zeroline=False, showline=False, tickcolor="#ffffff"),
        yaxis=dict(showline=False, showticklabels=False),
        legend=dict(title="Developer Type", bgcolor="#111111", bordercolor="#2a2a2a",
                    borderwidth=1, font=dict(color="#aaaaaa"), itemsizing="constant",
                    tracegroupgap=0, yanchor="top", y=1, xanchor="left", x=1.01),
        margin=dict(l=20, r=160, t=10, b=40),
        height=120,
        hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900",
                        font=dict(color="#ffffff", size=12)),
    )
    return fig


def plot_transition_heatmap(df):
    seqs = get_sequences(df)
    pairs = []
    for acts in seqs["activity"]:
        for i in range(len(acts) - 1):
            pairs.append((acts[i], acts[i + 1]))

    if not pairs:
        return None

    pair_counts = Counter(pairs)
    activities  = sorted(set(a for p in pairs for a in p))

    # Build probability matrix (row = from, col = to)
    matrix = pd.DataFrame(0.0, index=activities, columns=activities)
    from_counts = Counter(p[0] for p in pairs)
    for (frm, to), cnt in pair_counts.items():
        matrix.loc[frm, to] = round(cnt / from_counts[frm] * 100, 1)

    # Shorten labels
    short = {a: a[:20] + "…" if len(a) > 20 else a for a in activities}
    matrix.index   = [short[a] for a in matrix.index]
    matrix.columns = [short[a] for a in matrix.columns]

    fig = go.Figure(go.Heatmap(
        z=matrix.values,
        x=list(matrix.columns),
        y=list(matrix.index),
        colorscale=[
            [0,   "#0d0d0d"],
            [0.01,"#1a3a00"],
            [0.3, "#3d6200"],
            [1.0, "#76b900"],
        ],
        hoverongaps=False,
        hovertemplate="<b>%{y} → %{x}</b><br>%{z:.1f}%<extra></extra>",
        text=[[f"{v:.0f}%" if v > 0 else "" for v in row] for row in matrix.values],
        texttemplate="%{text}",
        textfont=dict(size=8, color="#ffffff"),
        colorbar=dict(
            title="Probability (%)",
            tickfont=dict(color="#aaa"),
            titlefont=dict(color="#aaa"),
            bgcolor="#111",
            bordercolor="#2a2a2a",
        ),
    ))
    fig.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", family="monospace", size=10),
        xaxis=dict(tickcolor="#ffffff", tickangle=-35, automargin=True, showgrid=False),
        yaxis=dict(tickcolor="#ffffff", automargin=True, showgrid=False),
        margin=dict(l=20, r=20, t=20, b=20),
        height=max(400, len(activities) * 32),
        hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900",
                        font=dict(color="#ffffff", size=12)),
    )
    return fig


def plot_sankey(df, title="Developer Activity Pathway"):
    seqs = get_sequences(df)
    pairs_1_2, pairs_2_3 = [], []
    for acts in seqs["activity"]:
        if len(acts) >= 2: pairs_1_2.append((f"1: {acts[0]}", f"2: {acts[1]}"))
        if len(acts) >= 3: pairs_2_3.append((f"2: {acts[1]}", f"3: {acts[2]}"))

    if not pairs_1_2:
        return None

    all_flows  = {**Counter(pairs_1_2), **Counter(pairs_2_3)}
    all_nodes  = sorted(set(n for pair in all_flows for n in pair))
    node_index = {n: i for i, n in enumerate(all_nodes)}

    sources, targets, values = [], [], []
    for (src, tgt), val in all_flows.items():
        sources.append(node_index[src])
        targets.append(node_index[tgt])
        values.append(val)

    node_colors = [
        "#76b900" if n.startswith("1:") else
        "#00c2ff" if n.startswith("2:") else
        "#ff6b35"
        for n in all_nodes
    ]

    n2 = len(pairs_1_2)
    n3 = len(pairs_2_3)

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=20, thickness=18,
            line=dict(color="#0d0d0d", width=0.5),
            label=[n.split(": ", 1)[1] for n in all_nodes],
            color=node_colors,
        ),
        link=dict(source=sources, target=targets, value=values,
                  color="rgba(255,255,255,0.08)"),
    ))
    fig.update_layout(
        title=dict(
            text=(f"{title}<br>"
                  f"<sup>Left = 1st activity · Middle = 2nd · Right = 3rd "
                  f"({n2:,} devs with 2+ steps, {n3:,} with 3+ steps)</sup>"),
            font=dict(color="#ffffff", size=13),
        ),
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", size=11, family="monospace"),
        height=520, margin=dict(l=20, r=20, t=80, b=20),
    )
    return fig


# ── Page ──────────────────────────────────────────────────────────────────────
try:
    df = load_data()

    all_clusters = sorted(df["cluster_name"].dropna().unique().tolist())

    with st.sidebar:
        st.markdown("### 📈 Full Group Trends")
        st.markdown("---")
        st.caption("Select a cluster to drill in, or leave blank to view all.")
        st.markdown("---")
        selected_cluster = st.selectbox(
            "Filter by Cluster",
            options=["All Clusters"] + all_clusters,
        )

        st.markdown("---")
        st.markdown(
            '<span style="font-size:11px;color:#444;font-family:monospace;">'
            'NVIDIA Developer Analytics<br>Full Group Trends View</span>',
            unsafe_allow_html=True,
        )

    # Determine mode and filter
    if selected_cluster == "All Clusters":
        mode    = "All"
        df_view = df.copy()
    else:
        mode    = "Single"
        df_view = df[df["cluster_name"] == selected_cluster]

    # ── Header ────────────────────────────────────────────────────────────────
    if mode == "All":
        st.markdown("""
        <div style="border-bottom: 1px solid #222; padding-bottom: 24px; margin-bottom: 28px;">
            <div style="font-size: 32px; font-weight: 600; color: #f0f0f0; line-height: 1.1;">
                All Developers
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="border-bottom: 1px solid #222; padding-bottom: 24px; margin-bottom: 28px;">
            <div style="font-size: 32px; font-weight: 600; color: #f0f0f0; line-height: 1.1;">
                {selected_cluster}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── KPI cards ─────────────────────────────────────────────────────────────
    total_users, unique_seqs, avg_seq_len, top_activity, avg_score, std_score = compute_metrics(df_view)

    c1, c2, c3, c4 = st.columns(4)
    for col, label, value, sub in [
        (c1, "Total Users",         f"{total_users:,}",  "unique developers"),
        (c2, "Top Activity",        top_activity,         "most common"),
        (c3, "Avg Sequence Length", f"{avg_seq_len}",     "activities per developer"),
        (c4, "Avg Activity Score",  f"{avg_score}",       f"σ = {std_score}"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
                <div class="metric-sub">{sub}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Cluster size distribution (All mode only) ─────────────────────────────
    if mode == "All":
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-header">Cluster Size Distribution</div>', unsafe_allow_html=True)
        st.plotly_chart(plot_cluster_distribution(df_view), use_container_width=True)

    # ── Sankey (always shown) ─────────────────────────────────────────────────
    st.markdown('<div class="section-header">Developer Activity Pathways</div>', unsafe_allow_html=True)
    title  = f"Activity Pathway — {selected_cluster}" if mode == "Single" else "Activity Pathway — All Developers"
    sankey = plot_sankey(df_view, title=title)
    if sankey:
        st.plotly_chart(sankey, use_container_width=True)
    else:
        st.caption("Not enough sequential activity data.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Transition probability heatmap (always shown) ─────────────────────────
    st.markdown('<div class="section-header">Transition Probabilities</div>', unsafe_allow_html=True)
    st.caption("Each cell shows the probability (%) of moving from row activity → column activity.")
    heatmap = plot_transition_heatmap(df_view)
    if heatmap:
        st.plotly_chart(heatmap, use_container_width=True)
    else:
        st.caption("Not enough data to build transition matrix.")

except FileNotFoundError as e:
    st.error(f"Data file not found: `{e}`\n\nPlace your CSV files alongside this script.")