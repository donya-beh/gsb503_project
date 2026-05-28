import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
.metric-card { background: #161616; border: 1px solid #2a2a2a; border-radius: 8px;
    padding: 20px 24px; margin-bottom: 0; min-height: 120px; display: flex; flex-direction: column; justify-content: flex-start; }
.metric-label { font-size: 11px; font-weight: 600; letter-spacing: 0.12em;
    text-transform: uppercase; color: #666; margin-bottom: 6px;
    font-family: 'DM Mono', monospace; }
.metric-value { font-size: 28px; font-weight: 600; color: #76b900;
    font-family: 'DM Mono', monospace; line-height: 1; word-break: break-word; }
.metric-sub { font-size: 12px; color: #555; margin-top: 4px;
    font-family: 'DM Mono', monospace; }
</style>
""", unsafe_allow_html=True)

from utils import load_org_kpis, load_org_activity_mix, load_org_cluster_breakdown, load_org_sequences, CLUSTER_COLORS, ACCENT_COLORS
from predictive import render_org_predictive


def plot_cluster_breakdown(cluster_df, orgs):
    all_clusters   = list(CLUSTER_COLORS.keys())
    cluster_totals = {c: cluster_df[cluster_df["cluster_name"] == c]["pct"].sum()
                      for c in all_clusters}
    sorted_clusters = sorted(cluster_totals, key=cluster_totals.get, reverse=True)
    fig = go.Figure()
    for cluster in sorted_clusters:
        x_vals, y_vals, text_vals = [], [], []
        for org in orgs:
            row = cluster_df[(cluster_df["normalized_account_name"] == org) &
                             (cluster_df["cluster_name"] == cluster)]
            pct = float(row["pct"].iloc[0]) if not row.empty else 0
            x_vals.append(pct)
            y_vals.append(org[:40] + "…" if len(org) > 40 else org)
            text_vals.append(f"{pct}%" if pct >= 4 else "")
        fig.add_trace(go.Bar(
            name=cluster, x=x_vals, y=y_vals, orientation="h",
            marker_color=CLUSTER_COLORS.get(cluster, "#888"),
            text=text_vals, textposition="inside", insidetextanchor="middle",
            textfont=dict(size=10, color="#111111"),
            hovertemplate=f"<b>{cluster}</b><br>%{{x:.1f}}%<extra>%{{y}}</extra>",
        ))
    fig.update_layout(
        barmode="stack", paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", family="monospace", size=11),
        xaxis=dict(title="% of Developers", range=[0, 100], ticksuffix="%",
                   gridcolor="#2a2a2a", zeroline=False, showline=False,
                   tickfont=dict(color="#ffffff")),
        yaxis=dict(showline=False, tickfont=dict(color="#ffffff"), automargin=True),
        legend=dict(title="Developer Type", bgcolor="#111111", bordercolor="#2a2a2a",
                    borderwidth=1, font=dict(color="#aaaaaa"), itemsizing="constant",
                    tracegroupgap=0, yanchor="top", y=1, xanchor="left", x=1.01),
        margin=dict(l=20, r=160, t=20, b=40),
        height=max(150, len(orgs) * 80),
        hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900",
                        font=dict(color="#ffffff", size=12)),
    )
    return fig


def plot_activity_mix(act_df, orgs):
    n       = len(orgs)
    spacing = max(0.12, 0.35 / n)
    titles  = [o[:35] + "…" if len(o) > 35 else o for o in orgs] if n > 1 else None
    fig     = make_subplots(rows=1, cols=n, subplot_titles=titles,
                            horizontal_spacing=spacing)
    for j, org in enumerate(orgs):
        org_df = act_df[act_df["normalized_account_name"] == org].sort_values("pct")
        color  = ACCENT_COLORS[j % len(ACCENT_COLORS)]
        fig.add_trace(go.Bar(
            x=org_df["pct"], y=org_df["activity"], orientation="h",
            marker_color=color,
            text=[f"{p}%" for p in org_df["pct"]], textposition="outside",
            textfont=dict(color="#ffffff", size=10),
            hovertemplate="<b>%{y}</b><br>%{x:.1f}%<extra></extra>",
            showlegend=False,
        ), row=1, col=j + 1)
        x_max = org_df["pct"].max() * 1.3 if not org_df.empty else 10
        fig.update_xaxes(ticksuffix="%", gridcolor="#2a2a2a", zeroline=False,
                         showline=False, tickfont=dict(color="#ffffff"),
                         range=[0, x_max], row=1, col=j + 1)
        fig.update_yaxes(showline=False, tickfont=dict(color="#ffffff"),
                         automargin=True, row=1, col=j + 1)
    max_bars = max(len(act_df[act_df["normalized_account_name"] == o]) for o in orgs)
    fig.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", family="monospace", size=11),
        height=max(300, max_bars * 30), margin=dict(l=20, r=40, t=40, b=40),
        hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900",
                        font=dict(color="#ffffff", size=12)),
    )
    for ann in fig.layout.annotations:
        ann.font.color = "#ffffff"; ann.font.size = 11
    return fig


def plot_sankey(seq_df, org_name):
    org_seq = seq_df[seq_df["normalized_account_name"] == org_name]
    if org_seq.empty: return None
    pairs_1_2, pairs_2_3 = [], []
    for dev_id, grp in org_seq.groupby("developer_id"):
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
    node_colors = ["#76b900" if n.startswith("1:") else
                   "#00c2ff" if n.startswith("2:") else "#ff6b35" for n in all_nodes]
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(pad=20, thickness=18, line=dict(color="#0d0d0d", width=0.5),
                  label=[n.split(": ", 1)[1] for n in all_nodes], color=node_colors),
        link=dict(source=sources, target=targets, value=values,
                  color="rgba(255,255,255,0.08)"),
    ))
    fig.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", size=11, family="monospace"),
        height=500, margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig


# ── Page ──────────────────────────────────────────────────────────────────────
try:
    with st.spinner("Loading organizations..."):
        kpis_df    = load_org_kpis()
        act_df     = load_org_activity_mix()
        cluster_df = load_org_cluster_breakdown()
        seq_df     = load_org_sequences()

    all_orgs = kpis_df.sort_values("total_developers", ascending=False)[
        "normalized_account_name"].tolist()

    with st.sidebar:
        st.markdown("### 🏢 Organization Profiles")
        st.markdown("---")
        mode = st.radio("Mode", ["Single Org", "Compare Orgs"], horizontal=True)
        st.markdown("---")
        if mode == "Single Org":
            selected_orgs = [st.selectbox("Select Organization", [""] + all_orgs,
                             format_func=lambda x: "Choose…" if x == "" else x)]
            selected_orgs = [o for o in selected_orgs if o]
        else:
            selected_orgs = st.multiselect("Select Organizations (up to 3)",
                            options=all_orgs, max_selections=3,
                            placeholder="Choose organizations…")

    if not selected_orgs:
        st.markdown("""
        <div style="margin-top:80px;text-align:center;">
            <div style="font-size:48px;margin-bottom:16px;">🏢</div>
            <div style="font-size:18px;color:#555;font-family:monospace;">
                Select an organization from the sidebar.
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        if mode == "Single Org":
            org_name = selected_orgs[0]
            row      = kpis_df[kpis_df["normalized_account_name"] == org_name].iloc[0]
            st.markdown(f"""
            <div style="border-bottom: 1px solid #222; padding-bottom: 24px; margin-bottom: 28px;">
                <div style="font-size: 32px; font-weight: 600; color: #f0f0f0;">{org_name}</div>
            </div>""", unsafe_allow_html=True)

            c1, c2, c3, c4, c5 = st.columns(5)
            for col, label, value, sub in [
                (c1, "Total Developers", f"{int(row['total_developers']):,}", "unique developers"),
                (c2, "Total Activities", f"{int(row['total_activities']):,}", "interactions logged"),
                (c3, "Activity Types",   f"{int(row['activity_types'])}",     "distinct activities"),
                (c4, "Avg Score",        f"{row['avg_score']}",               f"σ = {row['std_score']}"),
                (c5, "Top Cluster",      str(row["top_cluster"]),             ""),
            ]:
                with col:
                    st.markdown(f"""<div class="metric-card">
                        <div class="metric-label">{label}</div>
                        <div class="metric-value">{value}</div>
                        <div class="metric-sub">{sub}</div>
                    </div>""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.markdown('<div class="section-header">Comparing Organizations</div>',
                        unsafe_allow_html=True)
            rows = []
            for org in selected_orgs:
                r = kpis_df[kpis_df["normalized_account_name"] == org].iloc[0]
                rows.append({
                    "Organization":   org,
                    "Developers":     int(r["total_developers"]),
                    "Activities":     int(r["total_activities"]),
                    "Activity Types": int(r["activity_types"]),
                    "Avg Score":      r["avg_score"],
                    "Top Cluster":    r["top_cluster"],
                })
            st.dataframe(pd.DataFrame(rows).set_index("Organization"),
                         use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('<div class="section-header">Developer Type Breakdown</div>',
                    unsafe_allow_html=True)
        cluster_view = cluster_df[cluster_df["normalized_account_name"].isin(selected_orgs)]
        st.plotly_chart(plot_cluster_breakdown(cluster_view, selected_orgs),
                        use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('<div class="section-header">Activity Mix</div>',
                    unsafe_allow_html=True)
        act_view = act_df[act_df["normalized_account_name"].isin(selected_orgs)]
        st.plotly_chart(plot_activity_mix(act_view, selected_orgs),
                        use_container_width=True)

        if mode == "Single Org":
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="section-header">Developer Activity Pathways</div>',
                        unsafe_allow_html=True)
            st.caption("This chart shows the flow of developer activities from first activity on the left, to second activity in the middle, and third activity on the right. The connecting bands show where developers go next. Thicker bands represent paths followed by more developers.")
            sankey = plot_sankey(seq_df, selected_orgs[0])
            if sankey:
                st.plotly_chart(sankey, use_container_width=True)
            else:
                st.caption("Not enough sequential activity data.")
            st.markdown("<br>", unsafe_allow_html=True)
            render_org_predictive(selected_orgs[0])

except Exception as e:
    st.error(f"Error loading data: {e}")