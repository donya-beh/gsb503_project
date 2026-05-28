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
.section-header { font-size: 12px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #555; font-family: 'DM Mono', monospace; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #222; }
.metric-card { background: #161616; border: 1px solid #2a2a2a; border-radius: 8px; padding: 20px 24px; margin-bottom: 0; }
.metric-label { font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: #666; margin-bottom: 6px; font-family: 'DM Mono', monospace; }
.metric-value { font-size: 28px; font-weight: 600; color: #76b900; font-family: 'DM Mono', monospace; line-height: 1; word-break: break-word; }
.metric-sub { font-size: 12px; color: #555; margin-top: 4px; font-family: 'DM Mono', monospace; }
</style>
""", unsafe_allow_html=True)

from utils import load_data_for_country, load_sdk_for_country, get_all_countries, load_data, CLUSTER_COLORS, POPULATION, ACCENT_COLORS


def plot_world_map(all_countries_list, selected_countries=None):
    if selected_countries is None:
        selected_countries = []
    import pycountry
    all_world = [c.name for c in pycountry.countries]
    present   = set(all_countries_list)
    missing   = [c for c in all_world if c not in present]
    grey      = [c for c in all_world if c in present and c not in selected_countries]
    selected  = [c for c in all_world if c in selected_countries]
    fig = go.Figure()
    if missing:
        fig.add_trace(go.Choropleth(locations=missing, locationmode="country names",
            z=[0]*len(missing), colorscale=[[0,"#111111"],[1,"#111111"]],
            showscale=False, hovertemplate="<b>%{location}</b><br>No data<extra></extra>",
            marker_line_color="#0d0d0d", marker_line_width=0.5))
    if grey:
        fig.add_trace(go.Choropleth(locations=grey, locationmode="country names",
            z=[1]*len(grey), colorscale=[[0,"#444444"],[1,"#444444"]],
            showscale=False, hovertemplate="<b>%{location}</b><extra></extra>",
            marker_line_color="#0d0d0d", marker_line_width=0.5))
    if selected:
        fig.add_trace(go.Choropleth(locations=selected, locationmode="country names",
            z=[2]*len(selected), colorscale=[[0,"#76b900"],[1,"#76b900"]],
            showscale=False, hovertemplate="<b>%{location}</b> ✓<extra></extra>",
            marker_line_color="#0d0d0d", marker_line_width=0.5))
    fig.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        geo=dict(bgcolor="#0d0d0d", landcolor="#222222", oceancolor="#0d0d0d",
                 showocean=True, showcoastlines=True, coastlinecolor="#2a2a2a",
                 showframe=False, showlakes=False, showcountries=True, countrycolor="#2a2a2a"),
        margin=dict(l=0, r=0, t=0, b=0), height=420,
        font=dict(color="#ffffff", family="monospace"),
    )
    return fig


def plot_cluster_breakdown(df, countries, show_labels=True):
    all_clusters    = list(CLUSTER_COLORS.keys())
    cluster_totals  = {}
    for cluster in all_clusters:
        total = 0
        for country in countries:
            c_devs = df[df["country"] == country].drop_duplicates("developer_id")
            counts = c_devs.groupby("cluster_name")["developer_id"].nunique()
            pcts   = (counts / counts.sum() * 100).round(1) if counts.sum() > 0 else counts
            total += pcts.get(cluster, 0)
        cluster_totals[cluster] = total
    sorted_clusters = sorted(cluster_totals, key=cluster_totals.get, reverse=True)
    fig = go.Figure()
    for cluster in sorted_clusters:
        x_vals, y_vals, text_vals = [], [], []
        for country in countries:
            c_devs = df[df["country"] == country].drop_duplicates("developer_id")
            counts = c_devs.groupby("cluster_name")["developer_id"].nunique()
            pcts   = (counts / counts.sum() * 100).round(1) if counts.sum() > 0 else counts
            pct    = pcts.get(cluster, 0)
            x_vals.append(pct)
            y_vals.append(country[:40] + "..." if len(country) > 40 else country)
            text_vals.append(f"{pct}%" if pct >= 4 else "")
        fig.add_trace(go.Bar(
            name=cluster, x=x_vals, y=y_vals, orientation="h",
            marker_color=CLUSTER_COLORS[cluster], text=text_vals,
            textposition="inside", insidetextanchor="middle",
            textfont=dict(size=10, color="#111111"),
            hovertemplate=f"<b>{cluster}</b><br>%{{x:.1f}}%<extra>%{{y}}</extra>",
        ))
    fig.update_layout(
        barmode="stack", paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", family="monospace", size=11),
        xaxis=dict(title="% of Developers", range=[0, 100], ticksuffix="%",
                   gridcolor="#2a2a2a", zeroline=False, showline=False, tickfont=dict(color="#ffffff")),
        yaxis=dict(showline=False, tickfont=dict(color="#ffffff"), automargin=True, showticklabels=show_labels),
        legend=dict(title="Developer Type", bgcolor="#111111", bordercolor="#2a2a2a",
                    borderwidth=1, font=dict(color="#aaaaaa"), itemsizing="constant",
                    tracegroupgap=0, yanchor="top", y=1, xanchor="left", x=1.01),
        margin=dict(l=20, r=160, t=20, b=40),
        height=max(150, len(countries) * 80),
        hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900", font=dict(color="#ffffff", size=12)),
    )
    return fig


def plot_activity_mix(df, countries, show_titles=True):
    n            = len(countries)
    org_max_pcts = []
    for country in countries:
        c_df   = df[df["country"] == country]
        counts = c_df.groupby("activity").size()
        pcts   = (counts / counts.sum() * 100).round(1)
        org_max_pcts.append(pcts.max() if not pcts.empty else 10)
    spacing = max(0.12, 0.35 / n)
    titles  = [c[:35] for c in countries] if show_titles else None
    fig     = make_subplots(rows=1, cols=n, subplot_titles=titles, horizontal_spacing=spacing)
    for j, country in enumerate(countries):
        c_df   = df[df["country"] == country]
        counts = c_df.groupby("activity").size()
        pcts   = (counts / counts.sum() * 100).round(1).sort_values(ascending=True)
        color  = ACCENT_COLORS[j % len(ACCENT_COLORS)]
        fig.add_trace(go.Bar(
            x=pcts.values, y=pcts.index, orientation="h", marker_color=color,
            text=[f"{p}%" for p in pcts.values], textposition="outside",
            textfont=dict(color="#ffffff", size=10),
            hovertemplate="<b>%{y}</b><br>%{x:.1f}%<extra></extra>",
            showlegend=False,
        ), row=1, col=j + 1)
        fig.update_xaxes(ticksuffix="%", gridcolor="#2a2a2a", zeroline=False, showline=False,
                         tickfont=dict(color="#ffffff"), range=[0, org_max_pcts[j] * 1.3], row=1, col=j + 1)
        fig.update_yaxes(showline=False, tickfont=dict(color="#ffffff"), automargin=True, row=1, col=j + 1)
    max_bars = max(df[df["country"] == c]["activity"].nunique() for c in countries)
    fig.update_layout(
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", family="monospace", size=11),
        height=max(300, max_bars * 30), margin=dict(l=20, r=40, t=40, b=40),
        hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900", font=dict(color="#ffffff", size=12)),
    )
    for annotation in fig.layout.annotations:
        annotation.font.color = "#ffffff"; annotation.font.size = 11
    return fig


def country_kpi_table(df, countries):
    rows = []
    for country in countries:
        c_df   = df[df["country"] == country]
        c_devs = c_df.drop_duplicates("developer_id")
        rows.append({
            "Country":          country,
            "Developers":       c_devs["developer_id"].nunique(),
            "Total Activities": len(c_df),
            "Activity Types":   c_df["activity"].nunique(),
            "Avg Score":        round(c_df["activity_score"].mean(), 1),
            "Std Dev":          round(c_df["activity_score"].std(), 2),
            "Top Cluster":      c_devs["cluster_name"].value_counts().idxmax()
                                if c_devs["cluster_name"].notna().any() else "—",
        })
    return pd.DataFrame(rows).set_index("Country")


def plot_sankey(df, country):
    c_df      = df[df["country"] == country].copy()
    c_df      = c_df.sort_values(["developer_id", "activity_date"])
    sequences = c_df.groupby("developer_id")["activity"].apply(list).reset_index()
    pairs_1_2, pairs_2_3 = [], []
    for _, row in sequences.iterrows():
        acts = row["activity"]
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
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(pad=20, thickness=18, line=dict(color="#0d0d0d", width=0.5),
                  label=[n.split(": ", 1)[1] for n in all_nodes], color=node_colors),
        link=dict(source=sources, target=targets, value=values, color="rgba(255,255,255,0.08)"),
    ))
    fig.update_layout(
        title=dict(text=(f"Developer Activity Pathway: {country}<br>"
                         f"<sup>Left = 1st · Middle = 2nd · Right = 3rd "
                         f"({len(pairs_1_2)} devs with 2+ steps, {len(pairs_2_3)} with 3+)</sup>"),
                   font=dict(color="#ffffff", size=13)),
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#ffffff", size=11, family="monospace"),
        height=500, margin=dict(l=20, r=20, t=80, b=20),
    )
    return fig


def plot_top_products(sdk_df, countries, show_titles=True):
    n = len(countries)
    fig = make_subplots(rows=1, cols=n,
                        subplot_titles=[c[:35] for c in countries] if show_titles else None,
                        horizontal_spacing=max(0.1, 0.3 / n))
    for j, country in enumerate(countries):
        top = (sdk_df[sdk_df["country"] == country]
               .groupby("productname")["downloadcount"].sum()
               .sort_values(ascending=False).head(5).sort_values(ascending=True))
        base_color = ACCENT_COLORS[j % len(ACCENT_COLORS)]
        r, g, b    = int(base_color[1:3],16), int(base_color[3:5],16), int(base_color[5:7],16)
        bar_colors = [f"rgba({r},{g},{b},0.25)" for _ in range(len(top))]
        if bar_colors: bar_colors[-1] = f"rgba({r},{g},{b},1.0)"
        x_max = top.values.max() * 1.6 if len(top) else 1
        fig.add_trace(go.Bar(
            x=top.values, y=top.index, orientation="h", marker_color=bar_colors,
            text=[f"{int(v):,}" for v in top.values], textposition="outside",
            textfont=dict(color="#ffffff", size=10),
            hovertemplate="<b>%{y}</b><br>%{x:,} downloads<extra></extra>",
            showlegend=False,
        ), row=1, col=j + 1)
        fig.update_xaxes(gridcolor="#2a2a2a", zeroline=False, tickfont=dict(color="#ffffff"),
                         range=[0, x_max], row=1, col=j + 1)
        fig.update_yaxes(showline=False, tickfont=dict(color="#ffffff"), automargin=True, row=1, col=j + 1)
    max_bars = max(min(sdk_df[sdk_df["country"] == c]["productname"].nunique(), 5) for c in countries)
    fig.update_layout(paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
                      font=dict(color="#ffffff", family="monospace", size=11),
                      height=max(250, max_bars * 55), margin=dict(l=20, r=20, t=40, b=20),
                      hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900", font=dict(color="#ffffff", size=12)))
    for ann in fig.layout.annotations:
        ann.font.color = "#ffffff"; ann.font.size = 11
    return fig


def plot_top_sdks(sdk_df, countries, show_titles=True):
    n = len(countries)
    fig = make_subplots(rows=1, cols=n,
                        subplot_titles=[c[:35] for c in countries] if show_titles else None,
                        horizontal_spacing=max(0.1, 0.3 / n))
    for j, country in enumerate(countries):
        top = (sdk_df[sdk_df["country"] == country]
               .groupby("sdk_name")["downloadcount"].sum()
               .sort_values(ascending=False).head(5).sort_values(ascending=True))
        base_color = ACCENT_COLORS[j % len(ACCENT_COLORS)]
        r, g, b    = int(base_color[1:3],16), int(base_color[3:5],16), int(base_color[5:7],16)
        bar_colors = [f"rgba({r},{g},{b},0.25)" for _ in range(len(top))]
        if bar_colors: bar_colors[-1] = f"rgba({r},{g},{b},1.0)"
        x_max = top.values.max() * 1.6 if len(top) else 1
        fig.add_trace(go.Bar(
            x=top.values, y=top.index, orientation="h", marker_color=bar_colors,
            text=[f"{int(v):,}" for v in top.values], textposition="outside",
            textfont=dict(color="#ffffff", size=10),
            hovertemplate="<b>%{y}</b><br>%{x:,} downloads<extra></extra>",
            showlegend=False,
        ), row=1, col=j + 1)
        fig.update_xaxes(gridcolor="#2a2a2a", zeroline=False, tickfont=dict(color="#ffffff"),
                         range=[0, x_max], row=1, col=j + 1)
        fig.update_yaxes(showline=False, tickfont=dict(color="#ffffff"), automargin=True, row=1, col=j + 1)
    max_bars = max(min(sdk_df[sdk_df["country"] == c]["sdk_name"].nunique(), 5) for c in countries)
    fig.update_layout(paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
                      font=dict(color="#ffffff", family="monospace", size=11),
                      height=max(250, max_bars * 55), margin=dict(l=20, r=20, t=40, b=20),
                      hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900", font=dict(color="#ffffff", size=12)))
    for ann in fig.layout.annotations:
        ann.font.color = "#ffffff"; ann.font.size = 11
    return fig


def plot_download_comparison(sdk_df, countries):
    totals = sorted({c: round(sdk_df[sdk_df["country"] == c]["downloads_per_100k"].sum(), 1)
                     for c in countries}.items(), key=lambda x: x[1], reverse=False)
    labels = [c[:35] for c, _ in totals]
    values = [v for _, v in totals]
    x_max  = max(values) * 1.2 if values else 1
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=[ACCENT_COLORS[i % len(ACCENT_COLORS)] for i in range(len(labels))],
        text=[f"{v:,.1f}" for v in values], textposition="outside",
        textfont=dict(color="#ffffff", size=11),
        hovertemplate="<b>%{y}</b><br>%{x:,.1f} per 100K people<extra></extra>",
    ))
    fig.update_layout(paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
                      font=dict(color="#ffffff", family="monospace", size=11),
                      xaxis=dict(gridcolor="#2a2a2a", zeroline=False, tickfont=dict(color="#ffffff"), range=[0, x_max]),
                      yaxis=dict(showline=False, tickfont=dict(color="#ffffff"), automargin=True),
                      margin=dict(l=20, r=20, t=10, b=20), height=max(150, len(countries) * 70),
                      hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900", font=dict(color="#ffffff", size=12)))
    return fig


def plot_time_series(sdk_df, countries):
    fig = go.Figure()
    for j, country in enumerate(countries):
        c_df = (sdk_df[sdk_df["country"] == country]
                .groupby("downloaddate")["downloads_per_100k"].sum()
                .resample("ME").sum().reset_index())
        fig.add_trace(go.Scatter(
            x=c_df["downloaddate"], y=c_df["downloads_per_100k"],
            mode="lines+markers", name=country[:35],
            line=dict(color=ACCENT_COLORS[j % len(ACCENT_COLORS)], width=2),
            marker=dict(size=5),
            hovertemplate=f"<b>{country}</b><br>%{{x|%b %Y}}<br>%{{y:,.1f}} per 100K<extra></extra>",
        ))
    fig.update_layout(paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
                      font=dict(color="#ffffff", family="monospace", size=11),
                      xaxis=dict(gridcolor="#2a2a2a", zeroline=False, tickfont=dict(color="#ffffff")),
                      yaxis=dict(title="Downloads per 100K", gridcolor="#2a2a2a", zeroline=False, tickfont=dict(color="#ffffff")),
                      legend=dict(bgcolor="#111111", bordercolor="#2a2a2a", borderwidth=1, font=dict(color="#aaaaaa")),
                      margin=dict(l=20, r=20, t=10, b=40), height=350,
                      hoverlabel=dict(bgcolor="#1a1a1a", bordercolor="#76b900", font=dict(color="#ffffff", size=12)))
    return fig


# ── Page ──────────────────────────────────────────────────────────────────────
try:
    with st.spinner("Loading countries..."):
        all_countries = get_all_countries()
        all_countries = [c for c in all_countries if c != "Unknown"]

    with st.sidebar:
        st.markdown("### 🌍 Geographic Explorer")
        st.markdown("---")
        st.caption("Click countries on the map or use the list below.")
        st.markdown("---")
        sidebar_countries = st.multiselect(
            "Select Countries (up to 3)", options=all_countries,
            max_selections=3, placeholder="Choose countries...",
        )

    st.markdown('<div class="section-header">Developer Distribution by Country</div>', unsafe_allow_html=True)
    st.caption("Click countries on the map to select them. Select up to 3 to compare.")

    if "map_selected" not in st.session_state:
        st.session_state.map_selected = []

    map_event = st.plotly_chart(
        plot_world_map(all_countries, list(dict.fromkeys(sidebar_countries + st.session_state.map_selected))),
        use_container_width=True, on_select="rerun", key="world_map",
    )

    if map_event and map_event.selection and map_event.selection.get("points"):
        for p in map_event.selection["points"]:
            clicked = p.get("location")
            if clicked and clicked in all_countries:
                if clicked in st.session_state.map_selected:
                    st.session_state.map_selected.remove(clicked)
                elif len(st.session_state.map_selected) + len(sidebar_countries) < 3:
                    if clicked not in sidebar_countries:
                        st.session_state.map_selected.append(clicked)

    st.session_state.map_selected = [c for c in st.session_state.map_selected if c not in sidebar_countries]

    with st.sidebar:
        if st.session_state.map_selected:
            st.caption(f"Map selected: {', '.join(st.session_state.map_selected)}")
            if st.button("Clear map selection"):
                st.session_state.map_selected = []
                st.rerun()

    combined           = list(dict.fromkeys(sidebar_countries + st.session_state.map_selected))
    selected_countries = combined[:3]
    mode               = "Single Country" if len(selected_countries) == 1 else "Compare Countries"

    if not selected_countries:
        st.markdown("""
        <div style="margin-top:40px;text-align:center;">
            <div style="font-size:18px;color:#555;font-family:monospace;">
                Select a country from the sidebar or click the map.
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("<br>", unsafe_allow_html=True)

        # Load data only for selected countries
        with st.spinner("Loading data..."):
            dfs = [load_data_for_country(c) for c in selected_countries]
            df  = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]

        if mode == "Single Country":
            country = selected_countries[0]
            st.markdown(f"""
            <div style="border-bottom: 1px solid #222; padding-bottom: 24px; margin-bottom: 28px;">
                <div style="font-size: 32px; font-weight: 600; color: #f0f0f0;">{country}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="section-header">Comparing Countries</div>', unsafe_allow_html=True)

        tab_dev, tab_sdk = st.tabs(["👤 Developer Profiles", "📦 SDK Downloads"])

        with tab_dev:
            if mode == "Single Country":
                c_df   = df[df["country"] == country]
                c_devs = c_df.drop_duplicates("developer_id")
                col1, col2, col3, col4, col5 = st.columns(5)
                for col, label, value, sub in [
                    (col1, "Total Developers", f"{c_devs['developer_id'].nunique():,}", "unique developers"),
                    (col2, "Total Activities", f"{len(c_df):,}",                        "interactions logged"),
                    (col3, "Activity Types",   f"{c_df['activity'].nunique()}",          "distinct activities"),
                    (col4, "Avg Score",        f"{round(c_df['activity_score'].mean(),1)}", f"sigma = {round(c_df['activity_score'].std(),2)}"),
                    (col5, "Top Cluster",      c_devs["cluster_name"].value_counts().idxmax() if c_devs["cluster_name"].notna().any() else "—", ""),
                ]:
                    with col:
                        st.markdown(f"""<div class="metric-card">
                            <div class="metric-label">{label}</div>
                            <div class="metric-value">{value}</div>
                            <div class="metric-sub">{sub}</div>
                        </div>""", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
            else:
                st.markdown('<div class="section-header">At a Glance</div>', unsafe_allow_html=True)
                st.dataframe(country_kpi_table(df, selected_countries), use_container_width=True)
                st.markdown("<br>", unsafe_allow_html=True)

            st.markdown('<div class="section-header">Developer Type Breakdown</div>', unsafe_allow_html=True)
            st.plotly_chart(plot_cluster_breakdown(df, selected_countries,
                            show_labels=(mode != "Single Country")), use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="section-header">Activity Mix</div>', unsafe_allow_html=True)
            st.plotly_chart(plot_activity_mix(df, selected_countries,
                            show_titles=(mode != "Single Country")), use_container_width=True)

            if mode == "Single Country":
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown('<div class="section-header">Developer Activity Pathways</div>', unsafe_allow_html=True)
                sankey = plot_sankey(df, selected_countries[0])
                if sankey:
                    st.plotly_chart(sankey, use_container_width=True)
                else:
                    st.caption("Not enough sequential activity data.")

        with tab_sdk:
            try:
                with st.spinner("Loading SDK data..."):
                    sdk_dfs     = [load_sdk_for_country(c) for c in selected_countries]
                    sdk         = pd.concat(sdk_dfs, ignore_index=True) if len(sdk_dfs) > 1 else sdk_dfs[0]
                    sdk_countries = [c for c in selected_countries if c in sdk["country"].values]

                if not sdk_countries:
                    st.info("No SDK data available for the selected countries.")
                else:
                    if mode == "Single Country":
                        c_sdk      = sdk[sdk["country"] == sdk_countries[0]]
                        total_dl   = int(c_sdk["downloadcount"].sum())
                        top_os     = c_sdk.groupby("operatingsystem")["downloadcount"].sum().idxmax()
                        top_source = c_sdk.groupby("source")["downloadcount"].sum().idxmax()
                        top_prod   = c_sdk.groupby("productname")["downloadcount"].sum().idxmax()
                        top_sdk_nm = c_sdk.groupby("sdk_name")["downloadcount"].sum().idxmax()

                        col1, col2, col3, col4, col5 = st.columns(5)
                        for col, label, value in [
                            (col1, "Total Downloads", f"{total_dl:,}"),
                            (col2, "Top OS",          str(top_os)),
                            (col3, "Top Source",      str(top_source)),
                            (col4, "Top Product",     str(top_prod)),
                            (col5, "Top SDK",         str(top_sdk_nm)),
                        ]:
                            with col:
                                st.markdown(f"""<div class="metric-card">
                                    <div class="metric-label">{label}</div>
                                    <div class="metric-value">{value}</div>
                                </div>""", unsafe_allow_html=True)
                        st.markdown("<br>", unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="section-header">At a Glance</div>', unsafe_allow_html=True)
                        rows = []
                        for c in sdk_countries:
                            c_sdk = sdk[sdk["country"] == c]
                            rows.append({
                                "Country":            c,
                                "Total Downloads":    int(c_sdk["downloadcount"].sum()),
                                "Downloads per 100K": round(c_sdk["downloads_per_100k"].sum(), 1),
                                "Top OS":             c_sdk.groupby("operatingsystem")["downloadcount"].sum().idxmax(),
                                "Top Source":         c_sdk.groupby("source")["downloadcount"].sum().idxmax(),
                                "Top Product":        c_sdk.groupby("productname")["downloadcount"].sum().idxmax(),
                                "Top SDK":            c_sdk.groupby("sdk_name")["downloadcount"].sum().idxmax(),
                            })
                        st.dataframe(pd.DataFrame(rows).set_index("Country"), use_container_width=True)
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown('<div class="section-header">Downloads per 100K by Country</div>', unsafe_allow_html=True)
                        st.plotly_chart(plot_download_comparison(sdk, sdk_countries), use_container_width=True)
                        st.markdown("<br>", unsafe_allow_html=True)

                    st.markdown('<div class="section-header">Downloads per 100K Over Time</div>', unsafe_allow_html=True)
                    st.plotly_chart(plot_time_series(sdk, sdk_countries), use_container_width=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown('<div class="section-header">Top 5 Products (by Download Count)</div>', unsafe_allow_html=True)
                    st.plotly_chart(plot_top_products(sdk, sdk_countries,
                                    show_titles=(mode != "Single Country")), use_container_width=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown('<div class="section-header">Top 5 SDKs (by Download Count)</div>', unsafe_allow_html=True)
                    st.plotly_chart(plot_top_sdks(sdk, sdk_countries,
                                    show_titles=(mode != "Single Country")), use_container_width=True)

            except Exception as e:
                st.error(f"Error loading SDK data: {e}")

except Exception as e:
    st.error(f"Error: {e}")