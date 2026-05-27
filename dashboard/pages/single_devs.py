import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import plotly.graph_objects as go
import numpy as np

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* ── Global background ── */
.stApp {
    background-color: #0d0d0d;
    color: #e8e8e8;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #111111;
    border-right: 1px solid #222;
}
[data-testid="stSidebar"] * {
    color: #ccc !important;
}
[data-testid="stSidebar"] input {
    background: #1a1a1a !important;
    border: 1px solid #333 !important;
    color: #fff !important;
    border-radius: 4px !important;
}

/* ── Metric cards ── */
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

/* ── Header ── */
.profile-header {
    border-bottom: 1px solid #222;
    padding-bottom: 24px;
    margin-bottom: 28px;
}
.profile-id {
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    color: #666;
    letter-spacing: 0.08em;
    margin-bottom: 4px;
}
.profile-title {
    font-size: 32px;
    font-weight: 600;
    color: #f0f0f0;
    line-height: 1.1;
}
.nvidia-badge {
    display: inline-block;
    background: #76b900;
    color: #0d0d0d;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    font-family: 'DM Mono', monospace;
    padding: 3px 10px;
    border-radius: 2px;
    margin-bottom: 10px;
}

/* ── Cluster badge ── */
.cluster-badge {
    display: inline-block;
    background: #1a1a2e;
    color: #00c2ff;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    font-family: 'DM Mono', monospace;
    padding: 3px 10px;
    border-radius: 2px;
    border: 1px solid #00c2ff;
    margin-bottom: 10px;
}

/* ── Section headers ── */
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

/* ── Developer detail row ── */
.detail-row {
    display: flex;
    flex-direction: column;
    padding: 10px 0;
    border-bottom: 1px solid #1c1c1c;
}
.detail-key {
    color: #555;
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 3px;
}
.detail-val {
    color: #ccc;
    font-family: 'DM Mono', monospace;
    font-size: 12px;
    word-break: break-word;
}

/* ── Error / info boxes ── */
.info-box {
    background: #161616;
    border: 1px solid #2a2a2a;
    border-left: 3px solid #76b900;
    border-radius: 4px;
    padding: 16px 20px;
    font-size: 13px;
    color: #aaa;
    font-family: 'DM Mono', monospace;
}

/* ── Matplotlib figure background transparency ── */
.stPlotlyChart, [data-testid="stImage"] {
    border-radius: 8px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# ── Data loading ───────────────────────────────────────────────────────────────
from utils import load_data

# ── Matplotlib style ───────────────────────────────────────────────────────────
plt.rcParams.update({
    "figure.facecolor":  "#0d0d0d",
    "axes.facecolor":    "#0d0d0d",
    "text.color":        "#ffffff",
    "axes.labelcolor":   "#ffffff",
    "xtick.color":       "#ffffff",
    "ytick.color":       "#ffffff",
    "axes.edgecolor":    "#2a2a2a",
    "grid.color":        "#2a2a2a",
    "font.family":       "monospace",
    "font.size":         10,
})

NVIDIA_GREEN = "#76b900"
DARK_GREEN   = "#3d6200"
ACCENT_COLORS = [
    "#76b900", "#00c2ff", "#ff6b35", "#b39ddb",
    "#ffca28", "#ef9a9a", "#80cbc4", "#f48fb1",
    "#ce93d8", "#a5d6a7",
]

# ── Profile-card renderer ─────────────────────────────────────────────────────
def render_profile_card(developer_id: str, df: pd.DataFrame):
    dev_df = df[df["developer_id"].astype(str) == str(developer_id)]

    if dev_df.empty:
        st.markdown(
            f'<div class="info-box">No data found for developer ID <strong>{developer_id}</strong>.</div>',
            unsafe_allow_html=True,
        )
        return

    total_activities  = len(dev_df)
    activity_types    = dev_df["activity"].nunique()
    sorted_days       = dev_df["days_since_activity_1"].sort_values().unique()
    gaps              = pd.Series(sorted_days).diff()
    longest_gap       = int(gaps.max()) if len(gaps) > 1 else 0
    last_seen         = dev_df["activity_date"].max()
    avg_score         = dev_df["activity_score"].mean()
    std_score         = dev_df["activity_score"].std()

    row0              = dev_df.iloc[0]
    org               = row0.get("normalized_account_name", "—")
    industry          = row0.get("industry_segment_vertical", "—")
    country           = row0.get("country", "—")
    region            = row0.get("region", "—")
    first_seen        = dev_df["activity_date"].min()
    dev_areas         = row0.get("development_areas", "—")
    cluster           = row0.get("cluster_name", None)
    cluster_badge     = f'<div class="cluster-badge">{cluster}</div>' if pd.notna(cluster) else ""

    st.markdown(f"""
    <div class="profile-header">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            <div class="nvidia-badge">NVIDIA Developer</div>
            {cluster_badge}
        </div>
        <div class="profile-id">ID · {developer_id}</div>
        <div class="profile-title">{org if pd.notna(org) else "Unknown Organization"}</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        (c1, "Total Activities", f"{total_activities:,}",  "interactions logged"),
        (c2, "Activity Types",   f"{activity_types}",       "distinct activities"),
        (c3, "Avg Score",        f"{avg_score:.1f}",        f"σ = {std_score:.2f}"),
        (c4, "Longest Gap",      f"{longest_gap}d",         "between activities"),
        (c5, "Last Seen",        last_seen.strftime("%b %d, %Y"), ""),
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

    left_col, right_col = st.columns([1, 1.6], gap="large")

    with left_col:
        st.markdown('<div class="section-header">Developer Details</div>', unsafe_allow_html=True)

        detail_pairs = [
            ("Organization",   org if pd.notna(org) else "—"),
            ("Industry",       industry if pd.notna(industry) else "—"),
            ("Country",        country),
            ("Region",         region if pd.notna(region) else "—"),
            ("Dev Areas",      dev_areas if pd.notna(dev_areas) else "—"),
            ("First Activity", first_seen.strftime("%b %d, %Y") if pd.notna(first_seen) else "—"),
            ("Last Activity",  last_seen.strftime("%b %d, %Y")  if pd.notna(last_seen)  else "—"),
        ]

        rows_html = ""
        for k, v in detail_pairs:
            rows_html += f"""
            <div class="detail-row">
                <span class="detail-key">{k}</span>
                <span class="detail-val">{v}</span>
            </div>"""
        st.markdown(rows_html, unsafe_allow_html=True)

    with right_col:
        st.markdown('<div class="section-header">Activity Breakdown</div>', unsafe_allow_html=True)

        breakdown = (
            dev_df.groupby("activity")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=True)
        )

        fig2, ax2 = plt.subplots(figsize=(7, 5))
        fig2.patch.set_facecolor("#0d0d0d")

        bar_colors = [NVIDIA_GREEN if i == len(breakdown) - 1 else DARK_GREEN
                      for i in range(len(breakdown))]

        ax2.barh(breakdown["activity"], breakdown["count"],
                 color=bar_colors, height=0.55, edgecolor="none")

        for i, (_, row) in enumerate(breakdown.iterrows()):
            ax2.text(row["count"] + 0.15, i, str(int(row["count"])),
                     va="center", color="#ffffff", fontsize=9)

        ax2.set_xlabel("Engagement count", labelpad=8)
        ax2.spines[["top", "right", "left"]].set_visible(False)
        ax2.spines["bottom"].set_color("#2a2a2a")
        ax2.grid(axis="x", linestyle="--", alpha=0.25)
        ax2.tick_params(axis="y", length=0)
        plt.tight_layout(pad=1.4)
        st.pyplot(fig2, use_container_width=True)
        plt.close(fig2)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">Activity Timeline — Days Since First Activity</div>',
                unsafe_allow_html=True)

    activity_types_list = dev_df["activity"].unique()
    activity_color_map  = {a: ACCENT_COLORS[i % len(ACCENT_COLORS)]
                           for i, a in enumerate(activity_types_list)}

    dev_df = dev_df.copy()
    dev_df["label"] = dev_df["full_activity_name"].apply(
        lambda x: x[:45] + "…" if len(x) > 45 else x
    )

    x_max = dev_df["days_since_activity_1"].max()

    fig1 = go.Figure()

    for activity_type in activity_types_list:
        subset = dev_df[dev_df["activity"] == activity_type]
        fig1.add_trace(go.Scatter(
            x=subset["days_since_activity_1"],
            y=subset["label"],
            mode="markers",
            name=activity_type,
            marker=dict(color=activity_color_map[activity_type], size=10, opacity=0.9),
            customdata=subset[["full_activity_name", "days_since_activity_1"]].values,
            hovertemplate="<b>%{customdata[0]}</b><br>Day %{customdata[1]}<extra></extra>",
        ))

    fig1.update_layout(
        paper_bgcolor="#0d0d0d",
        plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", family="monospace", size=11),
        xaxis=dict(
            title="Days Since First Activity",
            range=[-x_max * 0.02 if x_max > 0 else -0.5, x_max * 1.05 if x_max > 0 else 1],
            gridcolor="#444444", gridwidth=0.5, zeroline=False, showline=False, tickcolor="#ffffff",
        ),
        yaxis=dict(gridcolor="#2a2a2a", gridwidth=0.5, showline=False, tickcolor="#ffffff", automargin=True),
        legend=dict(title="Activity Type", bgcolor="#111111", bordercolor="#2a2a2a", borderwidth=1, font=dict(color="#aaaaaa")),
        margin=dict(l=280, r=20, t=20, b=60),
        height=max(400, len(dev_df["label"].unique()) * 80),
        hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900", font=dict(color="#ffffff", size=12)),
    )

    st.plotly_chart(fig1, use_container_width=True)

    with st.expander("📋  Raw Activity Log", expanded=False):
        display_cols = ["activity_date", "activity", "activity_name", "activity_type", "activity_score", "days_since_activity_1"]
        available = [c for c in display_cols if c in dev_df.columns]
        tbl = dev_df[available].sort_values("activity_date", ascending=False).reset_index(drop=True)
        tbl["activity_date"] = tbl["activity_date"].dt.strftime("%Y-%m-%d")
        st.dataframe(tbl, use_container_width=True, hide_index=True)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 👤 Single Developer Profile Explorer")
    st.markdown("---")

    try:
        df = load_data()
        all_ids = sorted(df["developer_id"].astype(str).unique())

        st.markdown(f"**{len(all_ids):,}** developers loaded")
        st.markdown("---")

        search_input = st.text_input("Developer ID", placeholder="e.g. 2761701")
        st.markdown("**— or filter & pick —**")

        all_countries         = sorted(df["country"].dropna().unique())
        all_orgs              = sorted(df["normalized_account_name"].dropna().unique())
        all_acts              = sorted(df["activity"].dropna().unique())
        all_industry_segments = sorted(df["industry_segment_vertical"].dropna().unique())
        all_clusters          = sorted(df["cluster_name"].dropna().unique())

        f_country  = st.selectbox("Country", ["Any"] + all_countries)
        f_org      = st.selectbox("Organization", ["Any"] + list(all_orgs))
        f_act      = st.selectbox("Activity type", ["Any"] + all_acts)
        f_industry = st.selectbox("Industry Segment", ["Any"] + all_industry_segments)
        f_cluster  = st.selectbox("Cluster", ["Any"] + all_clusters)

        filtered = df.copy()
        if f_country  != "Any": filtered = filtered[filtered["country"] == f_country]
        if f_org      != "Any": filtered = filtered[filtered["normalized_account_name"] == f_org]
        if f_act      != "Any": filtered = filtered[filtered["activity"] == f_act]
        if f_industry != "Any": filtered = filtered[filtered["industry_segment_vertical"] == f_industry]
        if f_cluster  != "Any": filtered = filtered[filtered["cluster_name"] == f_cluster]

        filtered_ids = sorted(filtered["developer_id"].astype(str).unique())
        st.caption(f"{len(filtered_ids):,} matching developer{'s' if len(filtered_ids) != 1 else ''}")

        selected_from_list = st.selectbox(
            "Select developer",
            options=[""] + filtered_ids,
            format_func=lambda x: "Choose…" if x == "" else x,
            label_visibility="collapsed",
        )

        developer_id = search_input.strip() if search_input.strip() else selected_from_list

        st.markdown("---")
        st.markdown(
            '<span style="font-size:11px;color:#444;font-family:monospace;">'
            'NVIDIA Developer Analytics<br>Profile Card View</span>',
            unsafe_allow_html=True,
        )

    except FileNotFoundError as e:
        df = None
        developer_id = ""
        st.error(f"CSV file not found:\n\n`{e}`\n\nPlace the CSV files alongside this script.")

# ── Main content ───────────────────────────────────────────────────────────────
if df is None:
    st.markdown("""
    <div class="info-box">
        ⚠️  Data files not found. Please place the following CSVs in the same directory as this script:<br><br>
        &nbsp;&nbsp;• <code>activities.csv</code><br>
        &nbsp;&nbsp;• <code>dev_contacts_condensed.csv</code><br>
        &nbsp;&nbsp;• <code>cluster_assignments.csv</code>
    </div>
    """, unsafe_allow_html=True)

elif not developer_id:
    st.markdown("""
    <div style="margin-top:80px;text-align:center;color:#333;">
        <div style="font-size:48px;margin-bottom:16px;">👤</div>
        <div style="font-size:18px;color:#555;font-family:monospace;">Select a developer ID from the sidebar</div>
    </div>
    """, unsafe_allow_html=True)

else:
    render_profile_card(developer_id, df)
