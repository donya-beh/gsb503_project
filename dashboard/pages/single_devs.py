import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background-color: #0d0d0d; color: #e8e8e8; }
[data-testid="stSidebar"] { background-color: #111111; border-right: 1px solid #222; }
[data-testid="stSidebar"] * { color: #ccc !important; }
[data-testid="stSidebar"] input { background: #1a1a1a !important; border: 1px solid #333 !important; color: #fff !important; border-radius: 4px !important; }
.metric-card { background: #161616; border: 1px solid #2a2a2a; border-radius: 8px; padding: 20px 24px; margin-bottom: 0; }
.metric-label { font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: #666; margin-bottom: 6px; font-family: 'DM Mono', monospace; }
.metric-value { font-size: 28px; font-weight: 600; color: #76b900; font-family: 'DM Mono', monospace; line-height: 1; word-break: break-word; }
.metric-sub { font-size: 12px; color: #555; margin-top: 4px; font-family: 'DM Mono', monospace; }
.profile-header { border-bottom: 2px solid #76b900; padding-bottom: 20px; margin-bottom: 24px; }
.profile-id { font-size: 12px; color: #555; font-family: 'DM Mono', monospace; margin-bottom: 4px; }
.profile-title { font-size: 28px; font-weight: 600; color: #f0f0f0; }
.nvidia-badge { display: inline-block; background: #76b900; color: #000; font-size: 10px; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; font-family: 'DM Mono', monospace; padding: 3px 10px; border-radius: 2px; }
.cluster-badge { display: inline-block; background: #00c2ff22; border: 1px solid #00c2ff55; color: #00c2ff; font-size: 10px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; font-family: 'DM Mono', monospace; padding: 3px 10px; border-radius: 2px; }
.section-header { font-size: 12px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #555; font-family: 'DM Mono', monospace; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #222; }
.info-box { background: #161616; border: 1px solid #2a2a2a; border-left: 3px solid #76b900; border-radius: 4px; padding: 16px 20px; font-size: 13px; color: #aaa; font-family: 'DM Mono', monospace; }
</style>
""", unsafe_allow_html=True)

from utils import load_developer_sample, CLUSTER_COLORS

plt.rcParams.update({
    "figure.facecolor": "#0d0d0d", "axes.facecolor": "#0d0d0d",
    "text.color": "#ffffff", "axes.labelcolor": "#ffffff",
    "xtick.color": "#ffffff", "ytick.color": "#ffffff",
    "axes.edgecolor": "#2a2a2a", "grid.color": "#2a2a2a",
    "font.family": "monospace", "font.size": 10,
})

ACCENT_COLORS = ["#76b900","#00c2ff","#ff6b35","#b39ddb","#ffca28","#ef9a9a","#80cbc4","#f48fb1","#ce93d8","#a5d6a7"]


def render_profile_card(developer_id: str, df: pd.DataFrame):
    dev_df = df[df["developer_id"].astype(str) == str(developer_id)]
    if dev_df.empty:
        st.markdown(f'<div class="info-box">No data found for developer ID <strong>{developer_id}</strong>.</div>', unsafe_allow_html=True)
        return

    total_activities = len(dev_df)
    activity_types   = dev_df["activity"].nunique()
    sorted_days      = dev_df["days_since_activity_1"].sort_values().unique()
    gaps             = pd.Series(sorted_days).diff()
    longest_gap      = int(gaps.max()) if len(gaps) > 1 else 0
    last_seen        = dev_df["activity_date"].max()
    avg_score        = dev_df["activity_score"].mean()
    std_score        = dev_df["activity_score"].std()
    row0             = dev_df.iloc[0]
    org              = row0.get("normalized_account_name", "—")
    cluster          = row0.get("cluster_name", None)
    cluster_badge    = f'<div class="cluster-badge">{cluster}</div>' if pd.notna(cluster) else ""

    st.markdown(f"""
    <div class="profile-header">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            <div class="nvidia-badge">NVIDIA Developer</div>
            {cluster_badge}
        </div>
        <div class="profile-id">ID · {developer_id}</div>
        <div class="profile-title">{org if pd.notna(org) else "Unknown Organization"}</div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    for col, label, value, sub in [
        (c1, "Total Activities", f"{total_activities:,}",        "interactions logged"),
        (c2, "Activity Types",   f"{activity_types}",             "distinct activities"),
        (c3, "Avg Score",        f"{avg_score:.1f}",              f"σ = {std_score:.2f}"),
        (c4, "Longest Gap",      f"{longest_gap}d",               "between activities"),
        (c5, "Last Seen",        last_seen.strftime("%b %d, %Y"), ""),
    ]:
        with col:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
                <div class="metric-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown('<div class="section-header">Developer Details</div>', unsafe_allow_html=True)
        details = {
            "Organization":   row0.get("normalized_account_name", "—"),
            "Country":        row0.get("country", "—"),
            "Region":         row0.get("region", "—"),
            "Industry":       row0.get("industry_segment_vertical", "—"),
            "Dev Areas":      row0.get("development_areas", "—"),
            "Account Type":   row0.get("account_type", "—"),
            "First Activity": dev_df["activity_date"].min().strftime("%b %d, %Y"),
            "Last Activity":  last_seen.strftime("%b %d, %Y"),
        }
        for k, v in details.items():
            st.markdown(f"""
            <div style="display:flex;padding:8px 0;border-bottom:1px solid #1a1a1a;">
                <div style="font-size:11px;color:#555;font-family:monospace;width:130px;flex-shrink:0;">{k}</div>
                <div style="font-size:13px;color:#e8e8e8;word-break:break-word;">{v if pd.notna(v) else "—"}</div>
            </div>""", unsafe_allow_html=True)

    with right_col:
        st.markdown('<div class="section-header">Activity Breakdown</div>', unsafe_allow_html=True)
        act_counts = dev_df["activity"].value_counts()
        colors     = [ACCENT_COLORS[i % len(ACCENT_COLORS)] for i in range(len(act_counts))]
        fig, ax    = plt.subplots(figsize=(5, max(2, len(act_counts) * 0.4)))
        bars = ax.barh(act_counts.index[::-1], act_counts.values[::-1],
                       color=colors[::-1], height=0.6)
        for bar, val in zip(bars, act_counts.values[::-1]):
            ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                    str(val), va="center", ha="left", color="#ffffff", fontsize=9)
        ax.set_xlabel("Count", color="#ffffff")
        ax.tick_params(colors="#ffffff")
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">Activity Timeline</div>', unsafe_allow_html=True)

    act_types = dev_df["activity"].unique()
    color_map = {a: ACCENT_COLORS[i % len(ACCENT_COLORS)] for i, a in enumerate(act_types)}
    dev_df    = dev_df.copy()
    dev_df["label"] = dev_df["full_activity_name"].apply(
        lambda x: x[:45] + "…" if len(str(x)) > 45 else x)

    fig1 = go.Figure()
    for act_type in act_types:
        sub = dev_df[dev_df["activity"] == act_type]
        fig1.add_trace(go.Scatter(
            x=sub["days_since_activity_1"], y=sub["label"],
            mode="markers", name=act_type,
            marker=dict(size=10, color=color_map[act_type],
                        line=dict(width=1, color="#0d0d0d")),
            hovertemplate="<b>%{y}</b><br>Day %{x}<extra></extra>",
        ))
    fig1.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", family="monospace", size=10),
        xaxis=dict(title="Days since first activity", gridcolor="#444444",
                   zeroline=False, showline=False, tickfont=dict(color="#ffffff")),
        yaxis=dict(gridcolor="#2a2a2a", showline=False,
                   tickfont=dict(color="#ffffff"), automargin=True),
        legend=dict(title="Activity Type", bgcolor="#111111", bordercolor="#2a2a2a",
                    borderwidth=1, font=dict(color="#aaaaaa")),
        margin=dict(l=280, r=20, t=20, b=60),
        height=max(400, len(dev_df["label"].unique()) * 80),
        hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900",
                        font=dict(color="#ffffff", size=12)),
    )
    st.plotly_chart(fig1, use_container_width=True)

    with st.expander("📋 Raw Activity Log", expanded=False):
        display_cols = ["activity_date", "activity", "activity_name",
                        "activity_type", "activity_score", "days_since_activity_1"]
        available = [c for c in display_cols if c in dev_df.columns]
        tbl = dev_df[available].sort_values("activity_date", ascending=False).reset_index(drop=True)
        tbl["activity_date"] = tbl["activity_date"].dt.strftime("%Y-%m-%d")
        st.dataframe(tbl, use_container_width=True, hide_index=True)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 👤 Developer Profiles")
    st.markdown("---")

    try:
        with st.spinner("Loading developers..."):
            meta = load_developer_sample()[[
                "developer_id", "country", "normalized_account_name",
                "activity", "industry_segment_vertical", "cluster_name"
            ]]

        all_ids       = sorted(meta["developer_id"].astype(str).unique())
        all_countries = sorted(meta["country"].dropna().unique())
        all_orgs      = sorted(meta["normalized_account_name"].dropna().unique())
        all_acts      = sorted(meta["activity"].dropna().unique())
        all_industry  = sorted(meta["industry_segment_vertical"].dropna().unique())
        all_clusters  = sorted(meta["cluster_name"].dropna().unique())

        st.markdown(f"**{len(all_ids):,}** developers loaded")
        st.markdown("---")

        search_input = st.text_input("Developer ID", placeholder="e.g. 2761701")
        st.markdown("**— or filter & pick —**")

        f_country  = st.selectbox("Country",          ["Any"] + list(all_countries))
        f_org      = st.selectbox("Organization",     ["Any"] + list(all_orgs))
        f_act      = st.selectbox("Activity type",    ["Any"] + list(all_acts))
        f_industry = st.selectbox("Industry Segment", ["Any"] + list(all_industry))
        f_cluster  = st.selectbox("Cluster",          ["Any"] + list(all_clusters))

        filtered = meta.copy()
        if f_country  != "Any": filtered = filtered[filtered["country"] == f_country]
        if f_org      != "Any": filtered = filtered[filtered["normalized_account_name"] == f_org]
        if f_act      != "Any": filtered = filtered[filtered["activity"] == f_act]
        if f_industry != "Any": filtered = filtered[filtered["industry_segment_vertical"] == f_industry]
        if f_cluster  != "Any": filtered = filtered[filtered["cluster_name"] == f_cluster]

        filtered_ids = sorted(filtered["developer_id"].astype(str).unique())
        st.caption(f"{len(filtered_ids):,} matching developer{'s' if len(filtered_ids) != 1 else ''}")

        selected_from_list = st.selectbox(
            "Select developer", options=[""] + filtered_ids,
            format_func=lambda x: "Choose…" if x == "" else x,
            label_visibility="collapsed",
        )
        developer_id = search_input.strip() if search_input.strip() else selected_from_list

    except Exception as e:
        developer_id = ""
        st.error(f"Error loading data: {e}")

# ── Main ───────────────────────────────────────────────────────────────────────
if not developer_id:
    st.markdown("""
    <div style="margin-top:80px;text-align:center;color:#333;">
        <div style="font-size:48px;margin-bottom:16px;">👤</div>
        <div style="font-size:18px;color:#555;font-family:monospace;">
            Select a developer ID from the sidebar
        </div>
    </div>""", unsafe_allow_html=True)
else:
    with st.spinner("Loading developer profile..."):
        full_df  = load_developer_sample()
        dev_df   = full_df[full_df["developer_id"].astype(str) == str(developer_id)]
    render_profile_card(developer_id, dev_df)