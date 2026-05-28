"""
predictive.py — drop-in predictive-modeling panels for the NVIDIA dashboard
===========================================================================
Self-contained module. Does NOT modify any existing dashboard code. You import
it on a page and call one render function; it handles its own data loading and
styling.

WHAT IT ADDS
------------
A per-developer "priority score" (probability of being a top-1% high-value
developer over the next 90 days), a 3-tier label (high_touch / lighter_touch /
not_hv), and the model's top-3 predicted next activities. Plus org-level and
country-level roll-ups of those scores.

DATA IT NEEDS ON S3 (same bucket the dashboard already uses)
------------------------------------------------------------
1. predictive_scores.parquet   <- NEW. Produced by prepare_predictive_parquet.py.
                                  One row per developer_id, ~73 MB.
2. dashboard_ready.parquet      <- ALREADY THERE. Used only to map
                                  developer_id -> org / country for roll-ups.

SETUP (one time)
----------------
1. Upload predictive_scores.parquet to your S3 bucket.
2. Drop this file into dashboard/ next to utils.py.
3. (Optional) adjust the two S3 keys in the CONFIG block below if you named the
   file differently.

USAGE — add ONE import + ONE call per page. No other edits.

  # pages/single_devs.py  (inside render_profile_card, after the metric row)
  from predictive import render_dev_predictive
  render_dev_predictive(developer_id)

  # pages/org_analysis.py  (inside the per-org section, after the KPI row)
  from predictive import render_org_predictive
  render_org_predictive(org_name)

  # pages/geographic_analysis.py  (inside the per-country section)
  from predictive import render_geo_predictive
  render_geo_predictive(country)

  # pages/group_trends.py  (anywhere)
  from predictive import render_group_predictive
  render_group_predictive()

Every function is safe to call for any id/org/country — if there's no prediction
it shows a graceful "no prediction available" note instead of erroring.
"""

from __future__ import annotations

import io
import boto3
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ── CONFIG — change here if your S3 keys differ ────────────────────────────────
PREDICTIVE_KEY = "predictive_scores.parquet"   # the new file you upload
DASHBOARD_KEY  = "dashboard_ready.parquet"     # existing file (for org/country map)

# Tier display: name -> (label, color). Matches the dashboard's NVIDIA palette.
TIER_STYLE = {
    "high_touch":    ("High-Touch",    "#76b900"),  # NVIDIA green
    "lighter_touch": ("Lighter-Touch", "#00c2ff"),  # cyan
    "not_hv":        ("Standard",      "#666666"),  # muted gray
}
TIER_ORDER = ["high_touch", "lighter_touch", "not_hv"]

# Global reference numbers (from the production scoring run; for context labels).
GLOBAL_BASELINE_RATE = 0.01   # high-touch base rate in the population (1%)


# ── S3 loading (mirrors utils.py so secrets/config are identical) ──────────────
def _s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
        region_name=st.secrets["AWS_REGION"],
    )


def _read_parquet_from_s3(key: str, columns: list[str] | None = None) -> pd.DataFrame:
    s3 = _s3_client()
    obj = s3.get_object(Bucket=st.secrets["AWS_BUCKET"], Key=key)
    df = pd.read_parquet(io.BytesIO(obj["Body"].read()), columns=columns)
    df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(show_spinner=False)
def load_predictive() -> pd.DataFrame:
    """Per-developer predictive scores. Keyed on developer_id (string)."""
    df = _read_parquet_from_s3(PREDICTIVE_KEY)
    df["developer_id"] = df["developer_id"].astype(str)
    return df


@st.cache_data(show_spinner=False)
def _dev_to_geo_org() -> pd.DataFrame:
    """One row per developer: developer_id -> org + country, joined to scores.
    Used only for org/country roll-ups. Reads just the columns it needs."""
    base = _read_parquet_from_s3(
        DASHBOARD_KEY, columns=["developer_id", "normalized_account_name", "country"]
    )
    base["developer_id"] = base["developer_id"].astype(str)
    base = base.drop_duplicates("developer_id")
    pred = load_predictive()[
        ["developer_id", "priority_score", "priority_tier_name", "prob_high_touch"]
    ]
    return base.merge(pred, on="developer_id", how="inner")


# ── shared styling (additive; complements the dark theme already on each page) ──
_CSS = """
<style>
.pred-wrap { margin-top: 8px; }
.pred-badge { display:inline-block; font-size:10px; font-weight:700; letter-spacing:.15em;
  text-transform:uppercase; font-family:'DM Mono',monospace; padding:4px 12px; border-radius:2px; }
.pred-card { background:#161616; border:1px solid #2a2a2a; border-radius:8px; padding:18px 22px; }
.pred-label { font-size:11px; font-weight:600; letter-spacing:.12em; text-transform:uppercase;
  color:#666; font-family:'DM Mono',monospace; margin-bottom:6px; }
.pred-value { font-size:26px; font-weight:600; font-family:'DM Mono',monospace; line-height:1; }
.pred-sub { font-size:12px; color:#555; margin-top:4px; font-family:'DM Mono',monospace; }
.pred-section { font-size:12px; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  color:#555; font-family:'DM Mono',monospace; margin:18px 0 12px; padding-bottom:8px;
  border-bottom:1px solid #222; }
.pred-info { background:#161616; border:1px solid #2a2a2a; border-left:3px solid #76b900;
  border-radius:4px; padding:14px 18px; font-size:13px; color:#aaa; font-family:'DM Mono',monospace; }
.pred-act { display:flex; align-items:center; gap:10px; padding:7px 0; border-bottom:1px solid #1a1a1a; }
.pred-act-rank { font-size:11px; color:#555; font-family:'DM Mono',monospace; width:22px; }
.pred-act-name { font-size:13px; color:#e8e8e8; flex:1; }
.pred-act-prob { font-size:12px; color:#76b900; font-family:'DM Mono',monospace; }
</style>
"""


def _tier_label_color(tier_name: str) -> tuple[str, str]:
    return TIER_STYLE.get(tier_name, ("Unknown", "#666666"))


def _inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ── 1. SINGLE DEVELOPER ─────────────────────────────────────────────────────────
def render_dev_predictive(developer_id: str) -> None:
    """Predictive panel for one developer. Drop into single_devs.py."""
    _inject_css()
    st.markdown('<div class="pred-section">Predicted Priority &amp; Next Steps</div>',
                unsafe_allow_html=True)

    pred = load_predictive()
    row = pred[pred["developer_id"] == str(developer_id)]
    if row.empty:
        st.markdown(
            '<div class="pred-info">No prediction available for this developer. '
            'The model scores developers with activity history before the prediction '
            'date; brand-new sign-ups are intentionally not scored.</div>',
            unsafe_allow_html=True)
        return
    r = row.iloc[0]

    tier_label, tier_color = _tier_label_color(r["priority_tier_name"])
    score_pct = float(r["priority_score"]) * 100

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown(f"""
        <div class="pred-card">
            <div class="pred-label">Priority Tier</div>
            <div style="margin:6px 0;">
                <span class="pred-badge" style="background:{tier_color};color:#000;">{tier_label}</span>
            </div>
            <div class="pred-sub">model's outreach recommendation</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="pred-card">
            <div class="pred-label">Priority Score</div>
            <div class="pred-value" style="color:{tier_color};">{score_pct:.1f}%</div>
            <div class="pred-sub">P(top-1% value · next 90 days)</div>
        </div>""", unsafe_allow_html=True)

    # Next-activity recommendations (top 3). NaN for devs with no recent sequence.
    acts = [
        (r.get("next_activity_1"), r.get("next_activity_1_prob")),
        (r.get("next_activity_2"), r.get("next_activity_2_prob")),
        (r.get("next_activity_3"), r.get("next_activity_3_prob")),
    ]
    acts = [(a, p) for a, p in acts if pd.notna(a)]
    st.markdown('<div class="pred-section">Recommended Next Activities</div>',
                unsafe_allow_html=True)
    if not acts:
        st.markdown(
            '<div class="pred-info">No recent activity sequence — no next-activity '
            'recommendation for this developer.</div>', unsafe_allow_html=True)
    else:
        rows_html = "".join(
            f'<div class="pred-act"><div class="pred-act-rank">{i}</div>'
            f'<div class="pred-act-name">{_clean_activity(a)}</div>'
            f'<div class="pred-act-prob">{float(p)*100:.0f}%</div></div>'
            for i, (a, p) in enumerate(acts, start=1)
        )
        st.markdown(f'<div class="pred-card">{rows_html}</div>', unsafe_allow_html=True)


def _clean_activity(name: str) -> str:
    """Render the model's special tokens human-friendly."""
    s = str(name)
    if s in ("__OTHER__", "Other", "__UNKNOWN__"):
        return "Other activity"
    return s


# ── 2. ORGANIZATION ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _org_summary(org_name: str) -> dict | None:
    m = _dev_to_geo_org()
    sub = m[m["normalized_account_name"] == org_name]
    if sub.empty:
        return None
    n = len(sub)
    counts = sub["priority_tier_name"].value_counts()
    n_high = int(counts.get("high_touch", 0))
    return {
        "n_devs": n,
        "n_high": n_high,
        "pct_high": 100 * n_high / n,
        "avg_score": float(sub["priority_score"].mean()) * 100,
        "tier_counts": {t: int(counts.get(t, 0)) for t in TIER_ORDER},
        "top_devs": (sub.nlargest(10, "priority_score")
                        [["developer_id", "priority_score", "priority_tier_name"]]),
    }


def render_org_predictive(org_name: str) -> None:
    """Predictive roll-up for one organization. Drop into org_analysis.py."""
    _inject_css()
    st.markdown('<div class="pred-section">Predicted Outreach Priority</div>',
                unsafe_allow_html=True)
    s = _org_summary(org_name)
    if s is None:
        st.markdown('<div class="pred-info">No scored developers for this organization.</div>',
                    unsafe_allow_html=True)
        return

    lift = (s["pct_high"] / 100) / GLOBAL_BASELINE_RATE if s["pct_high"] else 0
    c1, c2, c3 = st.columns(3)
    _metric(c1, "High-Touch Devs", f"{s['n_high']:,}", f"of {s['n_devs']:,} scored")
    _metric(c2, "% High-Touch", f"{s['pct_high']:.1f}%", f"{lift:.1f}× the 1% baseline")
    _metric(c3, "Avg Priority", f"{s['avg_score']:.1f}%", "mean P(top-1%)")

    _tier_bar(s["tier_counts"], s["n_devs"])

    st.markdown('<div class="pred-section">Highest-Priority Developers</div>',
                unsafe_allow_html=True)
    tbl = s["top_devs"].copy()
    tbl["priority_score"] = (tbl["priority_score"] * 100).round(1).astype(str) + "%"
    tbl["priority_tier_name"] = tbl["priority_tier_name"].map(lambda t: _tier_label_color(t)[0])
    tbl.columns = ["Developer ID", "Priority", "Tier"]
    st.dataframe(tbl, use_container_width=True, hide_index=True)


# ── 3. GEOGRAPHY ─────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _geo_summary(country: str) -> dict | None:
    m = _dev_to_geo_org()
    sub = m[m["country"] == country]
    if sub.empty:
        return None
    n = len(sub)
    counts = sub["priority_tier_name"].value_counts()
    n_high = int(counts.get("high_touch", 0))
    return {
        "n_devs": n,
        "n_high": n_high,
        "pct_high": 100 * n_high / n,
        "avg_score": float(sub["priority_score"].mean()) * 100,
        "tier_counts": {t: int(counts.get(t, 0)) for t in TIER_ORDER},
    }


def render_geo_predictive(country: str) -> None:
    """Predictive roll-up for one country. Drop into geographic_analysis.py."""
    _inject_css()
    st.markdown('<div class="pred-section">Predicted Outreach Priority</div>',
                unsafe_allow_html=True)
    s = _geo_summary(country)
    if s is None:
        st.markdown('<div class="pred-info">No scored developers for this country.</div>',
                    unsafe_allow_html=True)
        return

    lift = (s["pct_high"] / 100) / GLOBAL_BASELINE_RATE if s["pct_high"] else 0
    c1, c2, c3 = st.columns(3)
    _metric(c1, "High-Touch Devs", f"{s['n_high']:,}", f"of {s['n_devs']:,} scored")
    _metric(c2, "% High-Touch", f"{s['pct_high']:.1f}%", f"{lift:.1f}× the 1% baseline")
    _metric(c3, "Avg Priority", f"{s['avg_score']:.1f}%", "mean P(top-1%)")
    _tier_bar(s["tier_counts"], s["n_devs"])


# ── 4. GROUP / OVERALL ───────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _group_summary() -> dict:
    pred = load_predictive()
    n = len(pred)
    counts = pred["priority_tier_name"].value_counts()
    return {
        "n_devs": n,
        "tier_counts": {t: int(counts.get(t, 0)) for t in TIER_ORDER},
        "avg_score": float(pred["priority_score"].mean()) * 100,
    }


def render_group_predictive() -> None:
    """Overall predictive summary. Drop into group_trends.py."""
    _inject_css()
    st.markdown('<div class="pred-section">Predictive Model — Population Summary</div>',
                unsafe_allow_html=True)
    s = _group_summary()
    c1, c2, c3 = st.columns(3)
    _metric(c1, "Developers Scored", f"{s['n_devs']:,}", "with activity history")
    _metric(c2, "High-Touch (top 1%)", f"{s['tier_counts']['high_touch']:,}",
            "white-glove outreach")
    _metric(c3, "Outreach Lift", "25×", "vs random, at top-1%")
    _tier_bar(s["tier_counts"], s["n_devs"])
    st.markdown(
        '<div class="pred-info">Sort any developer list by <b>priority_score</b> to '
        'reach ~25× more high-value developers than random outreach, for the same '
        'contact budget.</div>', unsafe_allow_html=True)


# ── small shared renderers ───────────────────────────────────────────────────────
def _metric(col, label: str, value: str, sub: str) -> None:
    with col:
        st.markdown(f"""
        <div class="pred-card">
            <div class="pred-label">{label}</div>
            <div class="pred-value" style="color:#76b900;">{value}</div>
            <div class="pred-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)


def _tier_bar(tier_counts: dict, total: int) -> None:
    """Horizontal stacked bar of the tier mix."""
    if not total:
        return
    fig = go.Figure()
    for t in TIER_ORDER:
        label, color = _tier_label_color(t)
        pct = 100 * tier_counts.get(t, 0) / total
        fig.add_trace(go.Bar(
            x=[pct], y=["tiers"], orientation="h", name=label,
            marker=dict(color=color),
            hovertemplate=f"{label}: {tier_counts.get(t,0):,} (%{{x:.1f}})<extra></extra>",
        ))
    fig.update_layout(
        barmode="stack", height=90, showlegend=True,
        paper_bgcolor="#0d0d0d", plot_bgcolor="#0d0d0d",
        font=dict(color="#aaa", family="monospace", size=11),
        margin=dict(l=8, r=8, t=8, b=8),
        xaxis=dict(visible=False, range=[0, 100]),
        yaxis=dict(visible=False),
        legend=dict(orientation="h", y=-0.4, bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#aaa")),
    )
    st.plotly_chart(fig, use_container_width=True)
