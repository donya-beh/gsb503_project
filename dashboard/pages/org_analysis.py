import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background-color: #0d0d0d; color: #e8e8e8; }
[data-testid="stSidebar"] { background-color: #111111; border-right: 1px solid #222; }
[data-testid="stSidebar"] * { color: #ccc !important; }

.section-header {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #555;
    font-family: 'DM Mono', monospace;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid #222;
}
.metric-card {
    background: #161616;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 0;
}
.metric-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #666;
    margin-bottom: 6px;
    font-family: 'DM Mono', monospace;
}
.metric-value {
    font-size: 28px;
    font-weight: 600;
    color: #76b900;
    font-family: 'DM Mono', monospace;
    line-height: 1;
}
.metric-sub {
    font-size: 12px;
    color: #555;
    margin-top: 4px;
    font-family: 'DM Mono', monospace;
}
.kpi-card {
    background: #161616;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 16px 20px;
}
.kpi-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #666;
    margin-bottom: 6px;
    font-family: 'DM Mono', monospace;
}
.kpi-value {
    font-size: 22px;
    font-weight: 600;
    color: #76b900;
    font-family: 'DM Mono', monospace;
}
.org-header {
    font-size: 16px;
    font-weight: 600;
    color: #f0f0f0;
    font-family: 'DM Mono', monospace;
    padding: 10px 0 6px 0;
    border-bottom: 2px solid #76b900;
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)

# ── Data loading ───────────────────────────────────────────────────────────────
from utils import load_data

# ── Chart: cluster breakdown for one or multiple orgs ─────────────────────────
CLUSTER_COLORS = {
    "Lapsed":         "#cccccc",
    "Zero-Touch":     "#a8c4e0",
    "DLI Self-Paced": "#4a90d9",
    "Live Event":     "#b8d98d",
    "On-Demand":      "#7eb3d8",
    "Power Users":    "#1a4d1a",
    "Newcomers":      "#e8a87c",
}

def plot_cluster_comparison(df, org_names):
    """Stacked horizontal bar chart with one row per org — Plotly version."""
    all_clusters = list(CLUSTER_COLORS.keys())

    # Sort clusters by total proportion across all orgs (largest first)
    cluster_totals = {}
    for cluster in all_clusters:
        total = 0
        for org in org_names:
            org_devs = df[df["normalized_account_name"] == org].drop_duplicates("developer_id")
            counts   = org_devs.groupby("cluster_name")["developer_id"].nunique()
            pcts     = (counts / counts.sum() * 100).round(1)
            total   += pcts.get(cluster, 0)
        cluster_totals[cluster] = total
    sorted_clusters = sorted(cluster_totals, key=cluster_totals.get, reverse=True)

    fig = go.Figure()

    for cluster in sorted_clusters:
        x_vals, y_vals, text_vals = [], [], []
        for org in org_names:
            org_devs   = df[df["normalized_account_name"] == org].drop_duplicates("developer_id")
            counts     = org_devs.groupby("cluster_name")["developer_id"].nunique()
            pcts       = (counts / counts.sum() * 100).round(1)
            pct        = pcts.get(cluster, 0)
            x_vals.append(pct)
            y_vals.append(org[:40] + "…" if len(org) > 40 else org)
            text_vals.append(f"{pct}%" if pct >= 4 else "")

        fig.add_trace(go.Bar(
            name=cluster,
            x=x_vals,
            y=y_vals,
            orientation="h",
            marker_color=CLUSTER_COLORS[cluster],
            text=text_vals,
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(size=10, color="#111111"),
            hovertemplate=f"<b>{cluster}</b><br>%{{x:.1f}}%<extra>%{{y}}</extra>",
        ))

    n_clusters = len(sorted_clusters)
    fig.update_layout(
        barmode="stack",
        paper_bgcolor="#0d0d0d",
        plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", family="monospace", size=11),
        xaxis=dict(
            title="% of Developers",
            range=[0, 100],
            ticksuffix="%",
            gridcolor="#2a2a2a",
            zeroline=False,
            showline=False,
            tickcolor="#ffffff",
        ),
        yaxis=dict(
            showline=False,
            tickcolor="#ffffff",
            automargin=True,
        ),
        legend=dict(
            title="Developer Type",
            bgcolor="#111111",
            bordercolor="#2a2a2a",
            borderwidth=1,
            font=dict(color="#aaaaaa"),
            # Prevent scrolling by showing all items
            itemsizing="constant",
            tracegroupgap=0,
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.01,
        ),
        margin=dict(l=20, r=160, t=20, b=40),
        height=max(150, len(org_names) * 80),
        hoverlabel=dict(
            bgcolor="#1a1a1a",
            bordercolor="#76b900",
            font=dict(color="#ffffff", size=12),
        ),
    )

    return fig


def plot_activity_mix(df, org_names):
    """Separate horizontal bar subplot per org using Plotly."""
    from plotly.subplots import make_subplots

    org_colors = ["#76b900", "#00c2ff", "#ff6b35", "#b39ddb", "#ffca28", "#ef9a9a"]
    n          = len(org_names)

    # Calculate per-org max x value for independent axis scaling
    org_max_pcts = []
    for org in org_names:
        org_df = df[df["normalized_account_name"] == org]
        counts = org_df.groupby("activity").size()
        pcts   = (counts / counts.sum() * 100).round(1)
        org_max_pcts.append(pcts.max() if not pcts.empty else 10)

    # Increase horizontal spacing to prevent overlap
    spacing = max(0.12, 0.35 / n)

    fig = make_subplots(
        rows=1, cols=n,
        subplot_titles=[o[:35] + "…" if len(o) > 35 else o for o in org_names],
        horizontal_spacing=spacing,
    )

    for j, org in enumerate(org_names):
        org_df = df[df["normalized_account_name"] == org]
        counts = org_df.groupby("activity").size()
        pcts   = (counts / counts.sum() * 100).round(1).sort_values(ascending=True)
        color  = org_colors[j % len(org_colors)]

        fig.add_trace(go.Bar(
            x=pcts.values,
            y=pcts.index,
            orientation="h",
            marker_color=color,
            text=[f"{p}%" for p in pcts.values],
            textposition="outside",
            textfont=dict(color="#ffffff", size=10),
            hovertemplate="<b>%{y}</b><br>%{x:.1f}%<extra></extra>",
            showlegend=False,
        ), row=1, col=j + 1)

        fig.update_xaxes(
            ticksuffix="%",
            gridcolor="#2a2a2a",
            zeroline=False,
            showline=False,
            tickcolor="#ffffff",
            range=[0, org_max_pcts[j] * 1.3],
            row=1, col=j + 1,
        )
        fig.update_yaxes(
            showline=False,
            tickcolor="#ffffff",
            automargin=True,
            row=1, col=j + 1,
        )

    max_bars = max(
        df[df["normalized_account_name"] == org]["activity"].nunique()
        for org in org_names
    )

    fig.update_layout(
        paper_bgcolor="#0d0d0d",
        plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", family="monospace", size=11),
        height=max(300, max_bars * 30),
        margin=dict(l=20, r=40, t=40, b=40),
        hoverlabel=dict(
            bgcolor="#1a1a1a",
            bordercolor="#76b900",
            font=dict(color="#ffffff", size=12),
        ),
    )

    for annotation in fig.layout.annotations:
        annotation.font.color = "#ffffff"
        annotation.font.size  = 11

    return fig


def org_kpi_table(df, org_names):
    rows = []
    for org in org_names:
        org_df  = df[df["normalized_account_name"] == org]
        df_devs = org_df.drop_duplicates("developer_id")
        rows.append({
            "Organization":     org,
            "Developers":       df_devs["developer_id"].nunique(),
            "Total Activities": len(org_df),
            "Activity Types":   org_df["activity"].nunique(),
            "Avg Activity Score":        round(org_df["activity_score"].mean(), 1),
            "Activity Score Std Dev":          round(org_df["activity_score"].std(), 2),
            "Top Cluster":      df_devs["cluster_name"].value_counts().idxmax() if df_devs["cluster_name"].notna().any() else "—",
        })
    return pd.DataFrame(rows).set_index("Organization")


def plot_sankey(df, org_name):
    """Sankey diagram showing developer activity pathways (1st → 2nd → 3rd activity)."""
    org_df = df[df["normalized_account_name"] == org_name].copy()
    org_df = org_df.sort_values(["developer_id", "activity_date"])

    # Build ordered activity sequences per developer
    sequences = (
        org_df.groupby("developer_id")["activity"]
        .apply(list)
        .reset_index()
    )

    # Extract step pairs: step1→step2 and step2→step3
    pairs_1_2, pairs_2_3 = [], []
    for _, row in sequences.iterrows():
        acts = row["activity"]
        if len(acts) >= 2:
            pairs_1_2.append((f"1: {acts[0]}", f"2: {acts[1]}"))
        if len(acts) >= 3:
            pairs_2_3.append((f"2: {acts[1]}", f"3: {acts[2]}"))

    if not pairs_1_2:
        return None

    # Count flows
    from collections import Counter
    flows_1_2 = Counter(pairs_1_2)
    flows_2_3 = Counter(pairs_2_3)
    all_flows  = {**flows_1_2, **flows_2_3}

    # Build node list
    all_nodes  = sorted(set(n for pair in all_flows for n in pair))
    node_index = {n: i for i, n in enumerate(all_nodes)}

    sources, targets, values = [], [], []
    for (src, tgt), val in all_flows.items():
        sources.append(node_index[src])
        targets.append(node_index[tgt])
        values.append(val)

    # Color nodes by step prefix
    node_colors = []
    for n in all_nodes:
        if n.startswith("1:"):
            node_colors.append("#76b900")
        elif n.startswith("2:"):
            node_colors.append("#00c2ff")
        else:
            node_colors.append("#ff6b35")

    n_devs_2plus = len(pairs_1_2)
    n_devs_3plus = len(pairs_2_3)

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=20,
            thickness=18,
            line=dict(color="#0d0d0d", width=0.5),
            label=[n.split(": ", 1)[1] for n in all_nodes],
            color=node_colors,
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color="rgba(255,255,255,0.08)",
        ),
    ))

    fig.update_layout(
        title=dict(
            text=(
                f"Developer Activity Pathway: {org_name}<br>"
                f"<sup>Left = 1st activity · Middle = 2nd · Right = 3rd "
                f"({n_devs_2plus} devs with 2+ steps, {n_devs_3plus} with 3+ steps)</sup>"
            ),
            font=dict(color="#ffffff", size=13),
        ),
        paper_bgcolor="#0d0d0d",
        plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", size=11, family="monospace"),
        height=500,
        margin=dict(l=20, r=20, t=80, b=20),
    )

    return fig


# ── Page ──────────────────────────────────────────────────────────────────────

try:
    df       = load_data()
    all_orgs = sorted(df["normalized_account_name"].dropna().unique().tolist())

    # ── Sidebar ──
    with st.sidebar:
        st.markdown("### 🏢 Organization Profile Explorer")
        st.markdown("---")

        mode = st.radio("Mode", ["Single Org", "Compare Orgs"], horizontal=True)
        st.markdown("---")

        if mode == "Single Org":
            selected_orgs = [st.selectbox("Select Organization", [""] + all_orgs,
                                          format_func=lambda x: "Choose…" if x == "" else x)]
            selected_orgs = [o for o in selected_orgs if o]
        else:
            selected_orgs = st.multiselect(
                "Select Organizations (up to 3)",
                options=all_orgs,
                max_selections=3,
                placeholder="Choose organizations…",
            )

        st.markdown("---")
        st.markdown(
            '<span style="font-size:11px;color:#444;font-family:monospace;">'
            'NVIDIA Developer Analytics<br>Organization View</span>',
            unsafe_allow_html=True,
        )

    # ── Empty state ──
    if not selected_orgs:
        st.markdown("""
        <div style="margin-top:80px;text-align:center;">
            <div style="font-size:48px;margin-bottom:16px;">🏢</div>
            <div style="font-size:18px;color:#555;font-family:monospace;">
                Select an organization from the sidebar for single insights,<br>
                or choose multiple organizations to compare.
            </div>
        </div>
        """, unsafe_allow_html=True)

    else:
        # ── Single org header (mirrors developer profile style) ──
        if mode == "Single Org":
            org_name = selected_orgs[0]
            st.markdown(f"""
            <div style="border-bottom: 1px solid #222; padding-bottom: 24px; margin-bottom: 28px;">
                <div style="font-size: 32px; font-weight: 600; color: #f0f0f0; line-height: 1.1;">
                    {org_name}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── KPI cards ──
            org_df   = df[df["normalized_account_name"] == org_name]
            df_devs  = org_df.drop_duplicates("developer_id")

            total_devs      = df_devs["developer_id"].nunique()
            total_acts      = len(org_df)
            unique_acts     = org_df["activity"].nunique()
            avg_score       = round(org_df["activity_score"].mean(), 1)
            std_score       = round(org_df["activity_score"].std(), 2)
            top_cluster     = df_devs["cluster_name"].value_counts().idxmax() if df_devs["cluster_name"].notna().any() else "—"

            c1, c2, c3, c4, c5 = st.columns(5)
            kpis = [
                (c1, "Total Developers",   f"{total_devs:,}",   "unique developers"),
                (c2, "Total Activities",   f"{total_acts:,}",   "interactions logged"),
                (c3, "Activity Types",     f"{unique_acts}",    "distinct activities"),
                (c4, "Avg Score",          f"{avg_score}",      f"σ = {std_score}"),
                (c5, "Top Cluster",        top_cluster,         ""),
            ]
            for col, label, value, sub in kpis:
                with col:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">{label}</div>
                        <div class="metric-value">{value}</div>
                        <div class="metric-sub">{sub}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

        else:
            st.markdown('<div class="section-header">Comparing Organizations</div>', unsafe_allow_html=True)

            # ── KPI comparison table ──
            st.markdown('<div class="section-header">At a Glance</div>', unsafe_allow_html=True)
            kpi_df = org_kpi_table(df, selected_orgs)
            st.dataframe(kpi_df, use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)

        # ── Cluster breakdown ──
        st.markdown('<div class="section-header">Developer Type Breakdown</div>', unsafe_allow_html=True)
        fig1 = plot_cluster_comparison(df, selected_orgs)
        st.plotly_chart(fig1, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Activity mix ──
        st.markdown('<div class="section-header">Activity Mix</div>', unsafe_allow_html=True)
        fig2 = plot_activity_mix(df, selected_orgs)
        st.plotly_chart(fig2, use_container_width=True)

        # ── Sankey (single org only) ──
        if mode == "Single Org":
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="section-header">Developer Activity Pathways</div>', unsafe_allow_html=True)
            sankey = plot_sankey(df, selected_orgs[0])
            if sankey:
                st.plotly_chart(sankey, use_container_width=True)
            else:
                st.caption("Not enough sequential activity data to build a pathway diagram.")

except FileNotFoundError as e:
    st.error(f"Data file not found: `{e}`\n\nPlace your CSV files alongside this script.")