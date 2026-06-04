"""
predictive.py — Predictive Model panels for the NVIDIA dashboard
================================================================
Self-contained. Does NOT modify any existing dashboard code. Import it on a
page and call one function; it loads its own data and renders a "Predictive
Model" block that clicks into the existing layout.

These panels surface the two-stage model that ranks every developer by
predicted 90-day value (Stage 1) and recommends their next activities
(Stage 2). The labels stay grounded in the model and the presentation
narrative — priority score, dev value, developer archetype, next-step path —
not generic AI branding.

WHERE IT GOES (recommendation): keep each block INLINE at the bottom of the
existing page, not in a separate tab. The value is seeing the prediction next
to the context that explains it. Each block is visually self-contained under a
"Predictive Model" header so it reads as a grounded extension of the page.

DATA ON S3 (same bucket the dashboard already uses)
---------------------------------------------------
1. predictive_scores.parquet   <- NEW. From prepare_predictive_parquet.py.
                                  One row per developer_id (~73 MB):
                                  priority_rank, priority_percentile,
                                  priority_score, priority_tier(_name),
                                  prob_*, next_activity_1..3(+prob), future_dev_value
2. dashboard_ready.parquet      <- EXISTING. Used only to map developer ->
                                  org / country / cluster for roll-ups.

USAGE — one import + one call per page (no other edits):

  # pages/single_devs.py  (at the end of render_profile_card; pass her dev_df
  #                         so the path can show what the developer already does)
  from predictive import render_dev_predictive
  render_dev_predictive(developer_id, dev_history_df=dev_df)

  # pages/org_analysis.py
  from predictive import render_org_predictive
  render_org_predictive(org_name)

  # pages/geographic_analysis.py
  from predictive import render_geo_map, render_geo_predictive
  render_geo_map()                 # toggleable choropleth (call once, top of page)
  render_geo_predictive(country)   # per-country AI block

  # pages/group_trends.py
  from predictive import render_group_predictive
  render_group_predictive()
"""

from __future__ import annotations

import io
import boto3
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ── CONFIG ─────────────────────────────────────────────────────────────────────
PREDICTIVE_KEY = "predictive_scores.parquet"
DASHBOARD_KEY  = "dashboard_ready.parquet"

# Donya's 1-indexed cluster map (mirrors utils.CLUSTER_NAME_MAP).
CLUSTER_NAME_MAP = {
    1: "Passive Users",
    2: "Training & Event Attendees",
    3: "Technical Power Users",
    4: "True Unicorns",
    5: "Casual Participants",
}

TIER_STYLE = {
    "high_touch":    ("High-Touch",    "#76b900"),
    "lighter_touch": ("Lighter-Touch", "#00c2ff"),
    "not_hv":        ("Standard",      "#666666"),
}
TIER_ORDER = ["high_touch", "lighter_touch", "not_hv"]
GLOBAL_BASELINE_RATE = 0.01  # 1% high-touch base rate

# Per-cluster GTM play. Drives the org-level recommendation header.
CLUSTER_PLAY = {
    "Passive Users": {
        "headline": "Activate",
        "focus": "Low-friction first steps",
        "actions": ["Starter journeys & guided onboarding",
                    "First-download prompts into DevZone",
                    "Welcome sequences that trigger a hands-on action"],
    },
    "Training & Event Attendees": {
        "headline": "Convert learning into usage",
        "focus": "Post-event hands-on follow-through",
        "actions": ["Route DLI / GTC attendees into labs",
                    "Recommend the SDK tied to the course they took",
                    "Post-event DevZone download nudges"],
    },
    "Technical Power Users": {
        "headline": "Deepen with advanced enablement",
        "focus": "Expert-level programs",
        "actions": ["Certification paths & expert workshops",
                    "Early-access / beta technical programs",
                    "Advanced labs and reference architectures"],
    },
    "Casual Participants": {
        "headline": "Broaden adoption",
        "focus": "Expand beyond a single tool",
        "actions": ["Personalized SDK / lab journeys",
                    "Cross-sell adjacent tools to current usage",
                    "Use-case-based content recommendations"],
    },
    "True Unicorns": {
        "headline": "Expand & reference",
        "focus": "Land-and-expand",
        "actions": ["Account expansion / seat growth plays",
                    "Co-marketing, case studies, advocacy",
                    "Early access to flagship releases"],
    },
}


# ── S3 loaders (mirror utils.py exactly) ────────────────────────────────────────
def _s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
        region_name=st.secrets["AWS_REGION"],
    )


def _read_parquet_from_s3(key: str, columns=None) -> pd.DataFrame:
    s3 = _s3_client()
    obj = s3.get_object(Bucket=st.secrets["AWS_BUCKET"], Key=key)
    df = pd.read_parquet(io.BytesIO(obj["Body"].read()), columns=columns)
    df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(show_spinner=False)
def load_predictive() -> pd.DataFrame:
    df = _read_parquet_from_s3(PREDICTIVE_KEY)
    df["developer_id"] = df["developer_id"].astype(str)
    if "priority_rank" not in df.columns:          # fallback if rank not baked in
        df = df.sort_values("priority_score", ascending=False).reset_index(drop=True)
        df["priority_rank"] = (df.index + 1).astype("int32")
        df["priority_percentile"] = 100 * (1 - (df["priority_rank"] - 1) / len(df))
    return df


@st.cache_data(show_spinner=False)
def _dev_to_geo_org() -> pd.DataFrame:
    base = _read_parquet_from_s3(
        DASHBOARD_KEY, columns=["developer_id", "normalized_account_name", "country", "cluster"]
    )
    base["developer_id"] = base["developer_id"].astype(str)
    base = base.drop_duplicates("developer_id")
    base["cluster_name"] = base["cluster"].map(CLUSTER_NAME_MAP)
    pred = load_predictive()[
        ["developer_id", "priority_score", "priority_tier_name", "prob_high_touch"]
    ]
    return base.merge(pred, on="developer_id", how="inner")


@st.cache_data(show_spinner=False)
def _country_aggregates() -> pd.DataFrame:
    m = _dev_to_geo_org()
    g = m.groupby("country")
    out = pd.DataFrame({
        "developers":      g.size(),
        "high_value":      g.apply(lambda d: (d["priority_tier_name"] == "high_touch").sum()),
        "organizations":   g["normalized_account_name"].nunique(),
        "avg_priority":    g["priority_score"].mean() * 100,
    }).reset_index()
    out["pct_high"] = 100 * out["high_value"] / out["developers"]
    # Top-3 organizations per country (by developer count), for the map hover.
    top3 = (m.groupby(["country", "normalized_account_name"]).size()
              .reset_index(name="n")
              .sort_values(["country", "n"], ascending=[True, False]))
    top3 = top3[~top3["normalized_account_name"].isin(
        ["Not Normalized", "Unclassified - Invalid"])]
    top3_str = (top3.groupby("country")
                .head(3)
                .groupby("country")["normalized_account_name"]
                .apply(lambda s: "<br>".join(f"  • {o}" for o in s)))
    out = out.merge(top3_str.rename("top3_orgs"), on="country", how="left")
    out["top3_orgs"] = out["top3_orgs"].fillna("  • —")
    return out


@st.cache_data(show_spinner=False)
def _orgs_by_country() -> pd.DataFrame:
    """Every organization in every country with its dev count, high-value count,
    and avg priority — backs the 'all organizations' table under the map."""
    m = _dev_to_geo_org()
    m = m[~m["normalized_account_name"].isin(["Not Normalized", "Unclassified - Invalid"])]
    g = m.groupby(["country", "normalized_account_name"])
    out = pd.DataFrame({
        "developers": g.size(),
        "high_value": g.apply(lambda d: (d["priority_tier_name"] == "high_touch").sum()),
        "avg_priority": g["priority_score"].mean() * 100,
    }).reset_index()
    out["pct_high"] = 100 * out["high_value"] / out["developers"]
    return out.sort_values(["country", "developers"], ascending=[True, False])


@st.cache_data(show_spinner=False)
def _dominant_cluster_by_country() -> pd.DataFrame:
    """The most common developer archetype in each country — drives the
    recommended play in the geo drill-down (ties geography to the deck's
    cluster-action narrative)."""
    m = _dev_to_geo_org()
    cm = (m.groupby(["country", "cluster_name"]).size()
            .reset_index(name="n")
            .sort_values(["country", "n"], ascending=[True, False]))
    dom = cm.groupby("country").head(1).set_index("country")["cluster_name"]
    return dom


# ── shared styling: model header + node-path look ───────────────────────────────
_CSS = """
<style>
.ai-head { display:flex; align-items:center; gap:10px; margin:22px 0 4px; }
.ai-spark { width:24px; height:24px; flex-shrink:0; }
.ai-title { font-family:'DM Sans',sans-serif; font-size:18px; font-weight:600; color:#76b900; }
.ai-kicker { font-family:'DM Mono',monospace; font-size:10px; font-weight:600;
  letter-spacing:.16em; color:#5a7a30; text-transform:uppercase; }
.ai-sub { font-family:'DM Mono',monospace; font-size:11px; color:#666;
  margin:0 0 14px 34px; letter-spacing:.04em; }
.pred-card { background:#161616; border:1px solid #2a2a2a; border-radius:8px; padding:18px 22px; }
.pred-label { font-size:11px; font-weight:600; letter-spacing:.12em; text-transform:uppercase;
  color:#666; font-family:'DM Mono',monospace; margin-bottom:6px; }
.pred-value { font-size:26px; font-weight:600; font-family:'DM Mono',monospace; line-height:1; }
.pred-sub { font-size:12px; color:#555; margin-top:4px; font-family:'DM Mono',monospace; }
.pred-section { font-size:12px; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  color:#555; font-family:'DM Mono',monospace; margin:16px 0 10px; }
.pred-info { background:#161616; border:1px solid #2a2a2a; border-left:3px solid #76b900;
  border-radius:4px; padding:14px 18px; font-size:13px; color:#aaa; font-family:'DM Mono',monospace; }
.rec-card { background:linear-gradient(135deg,#15211a,#161616); border:1px solid #2a3a2a;
  border-left:3px solid #76b900; border-radius:8px; padding:16px 20px; margin-top:4px; }
.rec-play { font-family:'DM Mono',monospace; color:#76b900; font-size:15px; font-weight:600; }
.rec-focus { font-family:'DM Mono',monospace; color:#888; font-size:11px;
  text-transform:uppercase; letter-spacing:.1em; margin:2px 0 10px; }
.rec-item { font-family:'DM Sans',sans-serif; color:#d8d8d8; font-size:13px; padding:4px 0;
  display:flex; gap:8px; }
.rec-arrow { color:#76b900; }
</style>
"""

# Grounded "priority target" mark — concentric rings + center dot, NVIDIA green.
# Evokes the model ranking developers toward a high-value target, not generic AI.
_SPARK = (
    '<svg class="ai-spark" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="12" cy="12" r="9.5" stroke="#76b900" stroke-width="1.6"/>'
    '<circle cx="12" cy="12" r="5.5" stroke="#76b900" stroke-width="1.6" opacity="0.7"/>'
    '<circle cx="12" cy="12" r="2" fill="#76b900"/>'
    '</svg>'
)


def _inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def _ai_header(title: str, subtitle: str) -> None:
    """Section header for a model panel. `title` is the model-grounded label
    (e.g. 'Predicted Priority'); a small target mark + 'PREDICTIVE MODEL'
    kicker keep it tied to our model rather than generic AI branding."""
    _inject_css()
    st.markdown(
        f'<div class="ai-head">{_SPARK}'
        f'<span><span class="ai-kicker">Predictive Model</span><br>'
        f'<span class="ai-title">{title}</span></span></div>'
        f'<div class="ai-sub">{subtitle}</div>',
        unsafe_allow_html=True)


def _tier(t: str):
    return TIER_STYLE.get(t, ("Unknown", "#666666"))


def _metric(col, label, value, sub):
    with col:
        st.markdown(f"""<div class="pred-card">
            <div class="pred-label">{label}</div>
            <div class="pred-value" style="color:#76b900;">{value}</div>
            <div class="pred-sub">{sub}</div></div>""", unsafe_allow_html=True)


def _clean_activity(name) -> str:
    s = str(name)
    return "Other activity" if s in ("__OTHER__", "Other", "__UNKNOWN__", "nan") else s


# ── 1 · SINGLE DEVELOPER ────────────────────────────────────────────────────────
def render_dev_predictive(developer_id: str, dev_history_df: pd.DataFrame | None = None) -> None:
    """Model block for one developer: rank + dev value + top-1% probability,
    then a node 'path forward' (what they do now -> archetype -> next steps)."""
    _ai_header("Predicted Priority &amp; Path",
               "Where this developer ranks today and the next steps the model recommends")

    pred = load_predictive()
    row = pred[pred["developer_id"] == str(developer_id)]
    if row.empty:
        st.markdown('<div class="pred-info">No prediction for this developer — the model '
                    'scores developers with prior activity; brand-new sign-ups are not scored.</div>',
                    unsafe_allow_html=True)
        return
    r = row.iloc[0]
    total = len(pred)
    tier_label, tier_color = _tier(r["priority_tier_name"])

    # Three forward-looking views of the SAME prediction so they tell one
    # coherent story: absolute rank, where that sits as a percentile, and the
    # calibrated probability. (We intentionally do NOT show the raw Dev Value
    # here — that's the backward-looking training label, it reads 0.00 for ~98%
    # of developers, and putting truth next to a prediction is confusing. Dev
    # Value lives in the group-level validation table, averaged by cluster.)
    pct = float(r["priority_percentile"]) if "priority_percentile" in r else (
        100.0 * (1 - (int(r["priority_rank"]) - 1) / total))
    c1, c2, c3 = st.columns(3)
    _metric(c1, "Developer Rank", f"#{int(r['priority_rank']):,}", f"of {total:,} scored")
    _metric(c2, "Percentile", f"Top {max(0.01, 100 - pct):.1f}%", "by predicted value")
    _metric(c3, "Top-1% Probability", f"{float(r['priority_score'])*100:.1f}%",
            "chance of elite status")

    st.markdown(f'<div class="pred-section">Priority Tier · '
                f'<span style="color:{tier_color}">{tier_label}</span></div>',
                unsafe_allow_html=True)

    # ── node path: [now] -> [archetype] -> [next 1] -> [next 2] -> [next 3]
    nodes = []
    if dev_history_df is not None and len(dev_history_df):
        col = "full_activity_name" if "full_activity_name" in dev_history_df.columns else (
              "activity_name" if "activity_name" in dev_history_df.columns else "activity")
        if col in dev_history_df.columns:
            top_now = dev_history_df[col].value_counts().index[:1]
            if len(top_now):
                nodes.append(("DOING NOW", _clean_activity(top_now[0]), "#3a3a3a", "#888"))
    cluster = None
    if dev_history_df is not None and "cluster_name" in dev_history_df.columns and len(dev_history_df):
        cluster = dev_history_df["cluster_name"].dropna().iloc[0] if dev_history_df["cluster_name"].notna().any() else None
    if cluster:
        nodes.append(("ARCHETYPE", cluster, "#1d2b1d", "#76b900"))
    nexts = [(r.get("next_activity_1"), r.get("next_activity_1_prob")),
             (r.get("next_activity_2"), r.get("next_activity_2_prob")),
             (r.get("next_activity_3"), r.get("next_activity_3_prob"))]
    nexts = [(a, p) for a, p in nexts if pd.notna(a)]
    for i, (a, p) in enumerate(nexts):
        label = "RECOMMENDED NEXT" if i == 0 else f"THEN ({float(p)*100:.0f}%)"
        nodes.append((label, _clean_activity(a), "#10202b", "#00c2ff"))

    if len([n for n in nodes if n[0] not in ("DOING NOW", "ARCHETYPE")]) == 0:
        st.markdown('<div class="pred-info">No recent activity sequence — no next-step '
                    'path available for this developer yet.</div>', unsafe_allow_html=True)
        return

    st.plotly_chart(_workflow_figure(nodes), use_container_width=True,
                    config={"displayModeBar": False})


def _workflow_figure(nodes: list) -> go.Figure:
    """Horizontal node-path graph. nodes = [(kicker, label, fill, accent)].
    Renders as a wide band: cards are positioned in x-axis units, the chart
    fills the container width at a fixed pixel height. No forced aspect ratio
    (that collapses the band when the viewport is tall)."""
    n = len(nodes)
    fig = go.Figure()
    x_gap = 1.0
    half_w = 0.40          # card half-width in x-units (gap between cards = 0.20)
    y_top, y_bot = 0.62, -0.62
    for i, (kicker, label, fill, accent) in enumerate(nodes):
        cx = i * x_gap
        x0, x1 = cx - half_w, cx + half_w
        fig.add_shape(type="rect", x0=x0, y0=y_bot, x1=x1, y1=y_top,
                      line=dict(color=accent, width=2), fillcolor=fill, layer="below")
        # accent bar across the top of the card
        fig.add_shape(type="rect", x0=x0, y0=y_top - 0.14, x1=x1, y1=y_top,
                      line=dict(width=0), fillcolor=accent, layer="below")
        fig.add_annotation(x=cx, y=y_top - 0.30, text=kicker, showarrow=False,
                           font=dict(family="DM Mono, monospace", size=10, color=accent))
        disp = label if len(label) <= 18 else label[:17] + "…"
        fig.add_annotation(x=cx, y=0.02, text=f"<b>{disp}</b>", showarrow=False,
                           font=dict(family="DM Sans, sans-serif", size=14, color="#f5f5f5"))
        if i < n - 1:
            fig.add_annotation(x=(i + 1) * x_gap - half_w, y=0,
                               ax=cx + half_w, ay=0,
                               xref="x", yref="y", axref="x", ayref="y",
                               showarrow=True, arrowhead=3, arrowsize=1.6,
                               arrowwidth=2.5, arrowcolor="#76b900")
    fig.update_layout(
        height=210, paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        margin=dict(l=12, r=12, t=8, b=8), showlegend=False,
        xaxis=dict(visible=False, range=[-0.6, (n - 1) * x_gap + 0.6],
                   fixedrange=True),
        yaxis=dict(visible=False, range=[-0.9, 0.9], fixedrange=True),
    )
    return fig


# ── 2 · ORGANIZATION ────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _org_summary(org_name: str):
    m = _dev_to_geo_org()
    sub = m[m["normalized_account_name"] == org_name]
    if sub.empty:
        return None
    n = len(sub)
    counts = sub["priority_tier_name"].value_counts()
    n_high = int(counts.get("high_touch", 0))
    cmix = sub["cluster_name"].value_counts()
    return {
        "n_devs": n, "n_high": n_high, "pct_high": 100 * n_high / n,
        "avg_score": float(sub["priority_score"].mean()) * 100,
        "dominant_cluster": cmix.index[0] if len(cmix) else None,
        "top_devs": sub.nlargest(8, "priority_score")[
            ["developer_id", "priority_score", "priority_tier_name"]],
    }


def render_org_predictive(org_name: str) -> None:
    """Model block for one organization: high-value density + a GTM play."""
    _ai_header("Account Priority &amp; Play",
               "High-value developer density and what the GTM / FDE team should run next")
    s = _org_summary(org_name)
    if s is None:
        st.markdown('<div class="pred-info">No scored developers for this organization.</div>',
                    unsafe_allow_html=True)
        return

    lift = (s["pct_high"] / 100) / GLOBAL_BASELINE_RATE if s["pct_high"] else 0
    c1, c2, c3 = st.columns(3)
    _metric(c1, "High-Value Density", f"{s['pct_high']:.1f}%",
            f"{s['n_high']:,} of {s['n_devs']:,} devs")
    _metric(c2, "vs Baseline", f"{lift:.1f}×", "the 1% average rate")
    _metric(c3, "Avg Priority", f"{s['avg_score']:.1f}%", "mean P(top-1%)")

    dom = s["dominant_cluster"]
    play = CLUSTER_PLAY.get(dom)
    if play:
        scale = ("This account has a high density of elite developers — treat it as a "
                 "full-scale adoption / expansion target."
                 if s["pct_high"] >= 5 else
                 "Most developers here are early in their journey — focus on moving the "
                 "majority one step deeper.")
        items = "".join(
            f'<div class="rec-item"><span class="rec-arrow">▸</span>{a}</div>'
            for a in play["actions"])
        st.markdown(f"""
        <div class="rec-card">
            <div class="rec-play">{play['headline']}</div>
            <div class="rec-focus">Dominant profile: {dom} · {play['focus']}</div>
            {items}
            <div class="rec-item" style="color:#888;margin-top:8px;">{scale}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="pred-section">Highest-Priority Developers</div>',
                unsafe_allow_html=True)
    tbl = s["top_devs"].copy()
    tbl["priority_score"] = (tbl["priority_score"] * 100).round(1).astype(str) + "%"
    tbl["priority_tier_name"] = tbl["priority_tier_name"].map(lambda t: _tier(t)[0])
    tbl.columns = ["Developer ID", "Priority", "Tier"]
    st.dataframe(tbl, use_container_width=True, hide_index=True)


# ── 3 · GEOGRAPHY ────────────────────────────────────────────────────────────────
# Country centroids (lat, lon) for the countries that appear in the data. Used to
# scatter glowing points for the tactical "where the high-value devs are" map.
_CENTROIDS = {
    "United States": (39.0, -98.0), "China": (35.0, 104.0), "India": (22.0, 79.0),
    "Germany": (51.0, 10.0), "United Kingdom": (54.0, -2.5), "Japan": (36.5, 138.0),
    "Korea, Republic of": (36.5, 127.8), "France": (46.5, 2.5), "Canada": (56.0, -106.0),
    "Brazil": (-10.0, -52.0), "Russian Federation": (60.0, 90.0), "Taiwan": (23.7, 121.0),
    "Turkey": (39.0, 35.0), "Indonesia": (-2.0, 118.0), "Hong Kong": (22.3, 114.2),
    "Australia": (-25.0, 134.0), "Netherlands": (52.2, 5.3), "The Netherlands": (52.2, 5.3),
    "Spain": (40.0, -4.0), "Italy": (42.8, 12.8), "Poland": (52.0, 19.0),
    "Sweden": (62.0, 15.0), "Israel": (31.4, 35.0), "Singapore": (1.35, 103.8),
    "Switzerland": (46.8, 8.2), "Mexico": (23.0, -102.0), "Ukraine": (49.0, 32.0),
    "Vietnam": (16.0, 108.0), "Viet Nam": (16.0, 108.0), "Pakistan": (30.0, 70.0),
    "Argentina": (-38.0, -63.0), "Nigeria": (9.0, 8.0), "Egypt": (26.8, 30.8),
    "Finland": (64.0, 26.0), "Norway": (62.0, 10.0), "Ireland": (53.2, -8.0),
    "Austria": (47.6, 14.1), "Belgium": (50.6, 4.6), "Czechia": (49.8, 15.5),
    "Romania": (45.9, 25.0), "Portugal": (39.5, -8.0), "Denmark": (56.0, 9.5),
    "Bangladesh": (23.7, 90.4), "Thailand": (15.0, 101.0), "Malaysia": (4.2, 102.0),
    "Philippines": (12.9, 121.8), "Saudi Arabia": (24.0, 45.0),
    "United Arab Emirates": (24.0, 54.0), "South Africa": (-29.0, 24.0),
    "Colombia": (4.0, -73.0), "Chile": (-35.0, -71.0), "Greece": (39.0, 22.0),
    "Hungary": (47.2, 19.5), "New Zealand": (-42.0, 173.0), "Iran": (32.0, 53.0),
}


def render_geo_map() -> None:
    """Tactical 'high-value developer' map — Call-of-Duty style: a dark world
    with glowing points clustered where developers (or high-value developers)
    are. Each point is a developer, jittered around its country so dense regions
    light up as clouds. Call once near the top of the geographic page."""
    import math
    _ai_header("Where Value Concentrates",
               "Each glow is a developer. Toggle to light up the whole base or just the high-value tier.")

    layer = st.radio(
        "Map layer", ["High-value developers", "All developers"],
        horizontal=True, label_visibility="collapsed", key="geo_glow_layer")
    high_only = layer.startswith("High-value")

    m = _dev_to_geo_org()
    if high_only:
        m = m[m["priority_tier_name"] == "high_touch"]

    # Per-country counts, then scatter up to a cap of points with jitter around
    # each centroid. Spread scales with sqrt(count) so big hubs form clouds.
    counts = m["country"].value_counts()
    counts = counts[counts.index.isin(_CENTROIDS)]
    total = int(counts.sum())
    cmax = float(counts.max()) if len(counts) else 1.0
    CAP = 5000
    lats, lons, sizes, hover = [], [], [], []
    # Deterministic organic scatter per country (no RNG — reproducible). A
    # golden-angle spiral gives even angular spread; a steep radial power makes
    # the cloud dense+bright at the core and sparse at the edges, like a heat
    # bloom. Per-point size is varied with a cheap trig "noise" so the core
    # sparkles instead of reading as a flat disc.
    for country, cnt in counts.items():
        clat, clon = _CENTROIDS[country]
        n_pts = max(2, int(round(CAP * cnt / total))) if total else 0
        n_pts = min(n_pts, 650)
        spread = 1.2 + 5.0 * math.sqrt(cnt) / max(1.0, math.sqrt(cmax))
        for k in range(n_pts):
            frac = (k + 0.5) / n_pts
            r = spread * (frac ** 0.85)          # steep falloff -> dense core
            theta = k * 2.399963229728653        # golden angle
            wobble = 0.22 * math.sin(theta * 3.1)  # break the perfect circle
            lats.append(clat + (r + wobble) * math.sin(theta))
            lons.append(clon + (r + wobble) * math.cos(theta) * 1.5)
            # inner points slightly bigger/brighter -> glowing core
            sizes.append(3.4 - 1.2 * frac)
        hover.append((country, cnt))

    glow = "#39d0ff" if high_only else "#76ff8a"   # cyan for elite, green for all
    core = "#eaffff" if high_only else "#e8ffe8"

    fig = go.Figure()
    # Stacked layers fake a bloom: broad soft halo -> tighter mid glow -> bright
    # per-point cores (size varies per point for the sparkle).
    fig.add_trace(go.Scattergeo(
        lat=lats, lon=lons, mode="markers",
        marker=dict(size=16, color=glow, opacity=0.06, line=dict(width=0)),
        hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scattergeo(
        lat=lats, lon=lons, mode="markers",
        marker=dict(size=7, color=glow, opacity=0.22, line=dict(width=0)),
        hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scattergeo(
        lat=lats, lon=lons, mode="markers",
        marker=dict(size=sizes, color=core, opacity=0.95, line=dict(width=0)),
        hoverinfo="skip", showlegend=False))
    # invisible per-country hover anchors at centroids, carrying rich stats:
    # total devs, high-value count + %, avg priority, and the top-3 orgs.
    if hover:
        agg = _country_aggregates().set_index("country")
        hc_lat = [_CENTROIDS[c][0] for c, _ in hover]
        hc_lon = [_CENTROIDS[c][1] for c, _ in hover]
        cdata = []
        for c, n in hover:
            row = agg.loc[c] if c in agg.index else None
            if row is not None:
                cdata.append([c, int(row["developers"]), int(row["high_value"]),
                              float(row["pct_high"]), float(row["avg_priority"]),
                              int(row["organizations"]), row["top3_orgs"]])
            else:
                cdata.append([c, n, 0, 0.0, 0.0, 0, "  • —"])
        fig.add_trace(go.Scattergeo(
            lat=hc_lat, lon=hc_lon, mode="markers",
            marker=dict(size=20, color="rgba(0,0,0,0)"),
            customdata=cdata,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "%{customdata[1]:,} developers · %{customdata[5]:,} orgs<br>"
                "<span style='color:#39d0ff'>%{customdata[2]:,} high-value "
                "(%{customdata[3]:.1f}%)</span><br>"
                "Avg priority %{customdata[4]:.1f}%<br>"
                "<br><b>Top organizations</b><br>%{customdata[6]}"
                "<extra></extra>"),
            hoverlabel=dict(bgcolor="#0d1117", bordercolor="#39d0ff",
                            font=dict(color="#e8e8e8", family="DM Mono, monospace", size=11)),
            showlegend=False,
        ))

    fig.update_layout(
        height=460, paper_bgcolor="#0a0a0a", plot_bgcolor="#0a0a0a",
        margin=dict(l=0, r=0, t=0, b=0),
        geo=dict(
            bgcolor="#0a0a0a", showland=True, landcolor="#181b1f",
            showocean=True, oceancolor="#0a0a0a",
            showcountries=True, countrycolor="#23282e", countrywidth=0.4,
            showcoastlines=True, coastlinecolor="#23282e", coastlinewidth=0.4,
            showframe=False, showlakes=False, resolution=110,
            projection_type="equirectangular",
            lataxis=dict(range=[-58, 80]),
        ),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(f"{total:,} {'high-value ' if high_only else ''}developers across "
               f"{len(counts)} countries · hover a cluster for its stats and top organizations")

    # ── Click-equivalent: pick a country to drill into (works on any Streamlit
    #    version; the hover already shows the headline stats).
    agg = _country_aggregates().sort_values("developers", ascending=False)
    choices = ["—"] + agg["country"].tolist()
    pick = st.selectbox("Inspect a country", choices, key="geo_country_pick")
    if pick != "—":
        row = agg[agg["country"] == pick].iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        _metric(c1, "Developers", f"{int(row['developers']):,}", f"{int(row['organizations']):,} orgs")
        _metric(c2, "High-Value", f"{int(row['high_value']):,}", f"{row['pct_high']:.1f}% of country")
        lift = (row["pct_high"] / 100) / GLOBAL_BASELINE_RATE if row["pct_high"] else 0
        _metric(c3, "vs Baseline", f"{lift:.1f}×", "the 1% rate")
        _metric(c4, "Avg Priority", f"{row['avg_priority']:.1f}%", "mean P(top-1%)")

        # Layer the narrative: this country's dominant archetype -> the same
        # recommended play the deck's action story is built around.
        dom = _dominant_cluster_by_country()
        dom_cluster = dom.get(pick)
        play = CLUSTER_PLAY.get(dom_cluster)
        if play:
            items = "".join(f'<div class="rec-item"><span class="rec-arrow">▸</span>{a}</div>'
                            for a in play["actions"][:2])
            st.markdown(f"""
            <div class="rec-card">
                <div class="rec-play">{play['headline']}</div>
                <div class="rec-focus">Most developers here are {dom_cluster} · {play['focus']}</div>
                {items}
            </div>""", unsafe_allow_html=True)

        orgs = _orgs_by_country()
        co = orgs[orgs["country"] == pick].head(10).copy()
        st.markdown(f'<div class="pred-section">Top organizations · {pick}</div>',
                    unsafe_allow_html=True)
        disp = pd.DataFrame({
            "Organization": co["normalized_account_name"],
            "Developers": co["developers"].map("{:,}".format),
            "High-Value": co["high_value"].map("{:,}".format),
            "% High-Value": co["pct_high"].map("{:.1f}%".format),
            "Avg Priority": co["avg_priority"].map("{:.1f}%".format),
        })
        st.dataframe(disp, use_container_width=True, hide_index=True)

    # ── Full breakdown: every organization in every country, on demand.
    with st.expander("📋 All organizations by country", expanded=False):
        orgs = _orgs_by_country()
        full = pd.DataFrame({
            "Country": orgs["country"],
            "Organization": orgs["normalized_account_name"],
            "Developers": orgs["developers"],
            "High-Value": orgs["high_value"],
            "% High-Value": orgs["pct_high"].round(1),
            "Avg Priority": orgs["avg_priority"].round(1),
        })
        st.dataframe(full, use_container_width=True, hide_index=True, height=360)
        st.caption(f"{len(full):,} organization×country rows · sortable; click a column header")


@st.cache_data(show_spinner=False)
def _geo_summary(country: str):
    m = _dev_to_geo_org()
    sub = m[m["country"] == country]
    if sub.empty:
        return None
    n = len(sub)
    counts = sub["priority_tier_name"].value_counts()
    n_high = int(counts.get("high_touch", 0))
    cmix = sub["cluster_name"].value_counts()
    return {
        "n_devs": n, "n_high": n_high, "pct_high": 100 * n_high / n,
        "avg_score": float(sub["priority_score"].mean()) * 100,
        "n_orgs": sub["normalized_account_name"].nunique(),
        "dominant_cluster": cmix.index[0] if len(cmix) else None,
    }


def render_geo_predictive(country: str) -> None:
    """Per-country model block: density + dominant profile + a play."""
    _ai_header("Country Priority &amp; Focus",
               f"High-value density and recommended focus for {country}")
    s = _geo_summary(country)
    if s is None:
        st.markdown('<div class="pred-info">No scored developers for this country.</div>',
                    unsafe_allow_html=True)
        return
    lift = (s["pct_high"] / 100) / GLOBAL_BASELINE_RATE if s["pct_high"] else 0
    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "High-Value Density", f"{s['pct_high']:.1f}%", f"{s['n_high']:,} devs")
    _metric(c2, "vs Baseline", f"{lift:.1f}×", "the 1% rate")
    _metric(c3, "Organizations", f"{s['n_orgs']:,}", "distinct accounts")
    _metric(c4, "Avg Priority", f"{s['avg_score']:.1f}%", "mean P(top-1%)")

    play = CLUSTER_PLAY.get(s["dominant_cluster"])
    if play:
        items = "".join(f'<div class="rec-item"><span class="rec-arrow">▸</span>{a}</div>'
                        for a in play["actions"][:2])
        st.markdown(f"""
        <div class="rec-card">
            <div class="rec-play">{play['headline']}</div>
            <div class="rec-focus">Dominant profile: {s['dominant_cluster']} · {play['focus']}</div>
            {items}
        </div>""", unsafe_allow_html=True)

    # Top organizations in this country (the country-level table). Lives here so
    # the geo level keeps its table whether or not the standalone map is used.
    orgs = _orgs_by_country()
    co = orgs[orgs["country"] == country].head(10).copy()
    if len(co):
        st.markdown(f'<div class="pred-section">Top organizations · {country}</div>',
                    unsafe_allow_html=True)
        disp = pd.DataFrame({
            "Organization": co["normalized_account_name"],
            "Developers": co["developers"].map("{:,}".format),
            "High-Value": co["high_value"].map("{:,}".format),
            "% High-Value": co["pct_high"].map("{:.1f}%".format),
            "Avg Priority": co["avg_priority"].map("{:.1f}%".format),
        })
        st.dataframe(disp, use_container_width=True, hide_index=True)


# ── 4 · GROUP / OVERALL ──────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _group_summary():
    pred = load_predictive()
    counts = pred["priority_tier_name"].value_counts()
    return {"n": len(pred),
            "high": int(counts.get("high_touch", 0)),
            "avg": float(pred["priority_score"].mean()) * 100}


def render_group_predictive() -> None:
    _ai_header("Population Summary",
               "What the two-stage model adds across the whole developer base")
    s = _group_summary()
    c1, c2, c3 = st.columns(3)
    _metric(c1, "Developers Scored", f"{s['n']:,}", "with activity history")
    _metric(c2, "High-Touch (top 1%)", f"{s['high']:,}", "white-glove outreach")
    _metric(c3, "Outreach Lift", "25×", "vs random, at top-1%")
    st.markdown('<div class="pred-info">Sort any developer list by <b>priority_score</b> '
                'to reach ~25× more high-value developers than random outreach, for the '
                'same contact budget.</div>', unsafe_allow_html=True)
