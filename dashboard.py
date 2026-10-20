"""FRIDAY dashboard: see every job application and where it stands.

    streamlit run dashboard.py

Reads the same data the tracker writes: the Google Sheet if SHEET_ID is set in
.env, otherwise applications.csv and emails.csv in this folder.
"""
from __future__ import annotations

import subprocess
import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*OpenSSL.*")

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from tracker.config import Config  # noqa: E402
from tracker.storage import APP_COLUMNS, EMAIL_COLUMNS, open_tables  # noqa: E402

PIPELINE = ["Applied", "Assessment", "Interview", "Offer", "Rejected"]
ACTIVE = ["Assessment", "Interview", "Offer"]
RANGES = {"7 days": 7, "30 days": 30, "90 days": 90, "All time": None}
HERE = Path(__file__).resolve().parent

# Theme colours (see .streamlit/config.toml)
CHARTREUSE = "#D4FF3F"
HOT_PINK = "#FF2DA8"
INK = "#F4F4F2"
MUTED = "#8A8A86"
SURFACE = "#1A1A1C"

st.set_page_config(page_title="FRIDAY · Job applications", page_icon="💼", layout="wide")
st.markdown(
    f"""<style>
    [data-testid="stMetricValue"] {{ color: {CHARTREUSE}; }}
    [data-testid="stMetric"] {{ background: {SURFACE}; border-radius: 12px; padding: 14px 18px; }}
    h1 span.accent {{ color: {HOT_PINK}; }}
    h3 {{ border-left: 4px solid {HOT_PINK}; padding-left: 12px !important; }}
    .stTabs [aria-selected="true"] {{ color: {HOT_PINK}; }}
    .card {{ background: {SURFACE}; border-radius: 12px; padding: 14px 18px; margin-bottom: 10px;
             border-left: 4px solid {CHARTREUSE}; }}
    .card .co {{ font-weight: 700; font-size: 1.05rem; color: {INK}; }}
    .card .meta {{ color: {MUTED}; font-size: 0.9rem; }}
    .card .badge {{ float: right; background: {HOT_PINK}; color: #0B0B0B; font-weight: 700; border-radius: 999px;
                    padding: 2px 10px; font-size: 0.8rem; }}
    .card a {{ color: {CHARTREUSE}; }}
    </style>""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- data

@st.cache_resource
def tables():
    config = Config.load()
    creds = None
    if config.sheet_id:
        from tracker.google_auth import get_credentials

        creds = get_credentials(config.credentials_file, config.token_file)
    return open_tables(creds, config.sheet_id), ("Google Sheet" if config.sheet_id else "applications.csv")


@st.cache_data(ttl=120, show_spinner="Loading your applications…")
def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    (app_table, email_table), _ = tables()
    apps = pd.DataFrame(app_table.load(), columns=APP_COLUMNS).fillna("")
    emails = pd.DataFrame(email_table.load(), columns=EMAIL_COLUMNS).fillna("")
    for df, col in ((apps, "Applied on"), (apps, "Last update"), (emails, "Date")):
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return apps, emails


def save_apps(df: pd.DataFrame) -> None:
    (app_table, _), _ = tables()
    rows = df.copy()
    for col in ("Applied on", "Last update"):
        rows[col] = rows[col].apply(lambda d: d.isoformat() if isinstance(d, date) else (d or ""))
    app_table.save(rows.fillna("").to_dict("records"))
    load.clear()


def check_email_now() -> None:
    """Run the tracker in the background and report what changed."""
    with st.spinner("Checking your email for job updates…"):
        result = subprocess.run(
            [sys.executable, "-m", "tracker.main", "--background"],
            cwd=HERE, capture_output=True, text=True,
        )
    load.clear()
    output = result.stdout + result.stderr
    changes = [line.strip() for line in output.splitlines() if line.startswith(("  +", "  ~"))]
    if result.returncode != 0:
        st.session_state["check_result"] = ("error", output.strip().splitlines()[-1] if output.strip() else "Failed")
    elif changes:
        st.session_state["check_result"] = ("ok", f"{len(changes)} update{'s' if len(changes) != 1 else ''}: "
                                                  + "; ".join(c[2:] for c in changes[:5]))
    else:
        st.session_state["check_result"] = ("ok", "No new job emails.")


def card(row: pd.Series) -> str:
    role = row["Role"] or "Role not found"
    action = f"<br>👉 {row['Next action']}" if row["Next action"] else ""
    link = f' · <a href="{row["Latest email"]}" target="_blank">open email</a>' if row["Latest email"] else ""
    updated = row["Last update"].strftime("%b %d") if isinstance(row["Last update"], date) else ""
    return (f'<div class="card"><span class="badge">{row["Status"]}</span>'
            f'<div class="co">{row["Company"]}</div><div class="meta">{role} · updated {updated}{link}{action}</div></div>')


# ---------------------------------------------------------------- header

apps, emails = load()
(_, _), source = tables()

head = st.columns([5, 1.4, 1])
head[0].markdown('<h1>Job <span class="accent">applications</span></h1>', unsafe_allow_html=True)
if head[1].button("Check email now", type="primary", width="stretch"):
    check_email_now()
    st.rerun()
if head[2].button("Refresh", width="stretch"):
    load.clear()
    st.rerun()

if "check_result" in st.session_state:
    kind, message = st.session_state.pop("check_result")
    (st.toast if kind == "ok" else st.error)(message)

if apps.empty:
    st.info("No applications yet. Click **Check email now** to read your inbox.")
    st.stop()

# ---------------------------------------------------------------- headline numbers

total = len(apps)
counts = apps["Status"].value_counts()
heard_back = int((apps["Status"] != "Applied").sum())
last_week = int((apps["Applied on"] >= date.today() - timedelta(days=7)).sum())

kpi = st.columns(5)
kpi[0].metric("Applications", total, f"+{last_week} this week" if last_week else None)
kpi[1].metric(f"Heard back ({heard_back} of {total})", f"{heard_back / total:.0%}")
kpi[2].metric("Interviews + assessments", int(counts.get("Interview", 0) + counts.get("Assessment", 0)))
kpi[3].metric("Offers", int(counts.get("Offer", 0)))
kpi[4].metric("Rejected", int(counts.get("Rejected", 0)))

overview, all_apps, history, log = st.tabs(["Overview", "All applications", "Company history", "Email log"])

# ---------------------------------------------------------------- overview

with overview:
    period = st.segmented_control("Show", list(RANGES), default="30 days", key="range")
    days = RANGES.get(period or "30 days")
    since = date.today() - timedelta(days=days - 1) if days else None
    in_range = apps if since is None else apps[apps["Applied on"].apply(lambda d: isinstance(d, date) and d >= since)]

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Applications per day")
        dated = in_range[in_range["Applied on"].apply(lambda d: isinstance(d, date))]
        if dated.empty:
            st.caption("No applications in this period.")
        else:
            start = since or min(dated["Applied on"])
            all_days = pd.DataFrame({"Day": pd.date_range(start, date.today(), freq="D").date})
            per_day = dated.groupby("Applied on").size().rename("Applications").reset_index()
            per_day = all_days.merge(per_day, how="left", left_on="Day", right_on="Applied on")
            per_day = per_day.fillna({"Applications": 0})[["Day", "Applications"]]
            per_day["Day"] = pd.to_datetime(per_day["Day"])
            chart = (
                alt.Chart(per_day)
                .mark_bar(color=CHARTREUSE, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("yearmonthdate(Day):O", title=None,
                            axis=alt.Axis(format="%b %d", labelAngle=0, labelOverlap=True)),
                    y=alt.Y("Applications:Q", title=None, axis=alt.Axis(tickMinStep=1, gridOpacity=0.3)),
                    tooltip=[alt.Tooltip("yearmonthdate(Day):T", title="Day", format="%a %b %d"),
                             alt.Tooltip("Applications:Q")],
                )
                .properties(height=270)
            )
            st.altair_chart(chart, use_container_width=True)

    with right:
        st.subheader("Where things stand")
        st.caption("Click a bar to list those applications below.")
        range_counts = in_range["Status"].value_counts()
        stages = pd.DataFrame({"Status": PIPELINE, "Applications": [int(range_counts.get(s, 0)) for s in PIPELINE]})
        stages["Label"] = stages["Status"] + "  " + stages["Applications"].astype(str)
        pick = alt.selection_point(fields=["Status"], name="pick")
        # Streamlit only supports selections on single (non-layered) charts, so counts go in the labels.
        bars = alt.Chart(stages).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height=24, cursor="pointer").encode(
            y=alt.Y("Label:N", sort=list(stages["Label"]), title=None, axis=alt.Axis(labelFontSize=13, labelLimit=200)),
            x=alt.X("Applications:Q", title=None, axis=None),
            tooltip=["Status", "Applications"],
            color=alt.condition(pick, alt.value(CHARTREUSE), alt.value("#4A4A46")),
        ).add_params(pick).properties(height=270)
        event = st.altair_chart(bars, use_container_width=True, on_select="rerun", key="status_chart")

    chosen = [p["Status"] for p in (event.selection.get("pick") or [])] if event else []
    if chosen:
        st.subheader(f"{', '.join(chosen)} · {period or '30 days'}")
        picked = in_range[in_range["Status"].isin(chosen)].sort_values("Last update", ascending=False)
        st.dataframe(
            picked[["Company", "Role", "Status", "Applied on", "Last update", "Latest email"]],
            hide_index=True, width="stretch",
            column_config={
                "Latest email": st.column_config.LinkColumn("Email", display_text="Open"),
                "Applied on": st.column_config.DateColumn(format="MMM D"),
                "Last update": st.column_config.DateColumn(format="MMM D"),
            },
        )

    st.subheader("Needs your attention")
    active = apps[apps["Status"].isin(ACTIVE)].sort_values("Last update", ascending=False)
    if active.empty:
        st.caption("Nothing right now. Interviews, assessments and offers will show up here.")
    else:
        cols = st.columns(2)
        for i, (_, row) in enumerate(active.iterrows()):
            cols[i % 2].markdown(card(row), unsafe_allow_html=True)

    checks = emails[(emails["Kind"] == "Verification")
                    & emails["Date"].apply(lambda d: isinstance(d, date) and d >= date.today() - timedelta(days=3))]
    if not checks.empty:
        with st.expander(f"{len(checks)} security-code or verification emails in the last 3 days"):
            st.dataframe(
                checks[["Date", "Subject", "Email link"]], hide_index=True, width="stretch",
                column_config={"Email link": st.column_config.LinkColumn("Email", display_text="Open")},
            )

# ---------------------------------------------------------------- all applications (editable)

with all_apps:
    f1, f2, f3 = st.columns([3, 2, 2])
    picked_status = f1.pills("Status", PIPELINE, selection_mode="multi", key="status_pills")
    search = f2.text_input("Search company or role", placeholder="e.g. Affirm, intern")
    sort_by = f3.selectbox("Sort by", ["Newest first", "Oldest first", "Company A–Z", "Recently updated"])

    view = apps.copy()
    if picked_status:
        view = view[view["Status"].isin(picked_status)]
    if search:
        needle = search.lower()
        view = view[view["Company"].str.lower().str.contains(needle, regex=False)
                    | view["Role"].str.lower().str.contains(needle, regex=False)]
    view = {
        "Newest first": lambda v: v.sort_values("Applied on", ascending=False),
        "Oldest first": lambda v: v.sort_values("Applied on"),
        "Company A–Z": lambda v: v.sort_values("Company", key=lambda s: s.str.lower()),
        "Recently updated": lambda v: v.sort_values("Last update", ascending=False),
    }[sort_by](view)

    st.caption(f"{len(view)} of {total} applications · data from {source} · "
               "edit Status, Next action or Notes right in the table, then press Save")
    edited = st.data_editor(
        view, hide_index=True, width="stretch", height=520, key="editor",
        disabled=["Company", "Role", "Applied on", "Last update", "Latest email"],
        column_config={
            "Status": st.column_config.SelectboxColumn(options=PIPELINE, required=True),
            "Latest email": st.column_config.LinkColumn("Email", display_text="Open"),
            "Applied on": st.column_config.DateColumn(format="MMM D"),
            "Last update": st.column_config.DateColumn(format="MMM D"),
            "Next action": st.column_config.TextColumn(width="medium"),
            "Notes": st.column_config.TextColumn(width="large"),
        },
    )
    if st.session_state.pop("saved", None):
        st.toast("Saved your changes", icon="✅")
    changed = (edited[["Status", "Next action", "Notes"]] != view[["Status", "Next action", "Notes"]]).any(axis=1)
    save_cols = st.columns([1, 5])
    if save_cols[0].button(f"Save {int(changed.sum())} change{'s' if int(changed.sum()) != 1 else ''}",
                           type="primary", disabled=not changed.any(), width="stretch"):
        updated = apps.copy()
        for idx in edited.index[changed]:
            updated.loc[idx, ["Status", "Next action", "Notes"]] = edited.loc[idx, ["Status", "Next action", "Notes"]]
            if updated.loc[idx, "Status"] != apps.loc[idx, "Status"]:
                updated.loc[idx, "Last update"] = date.today()
        save_apps(updated)
        st.session_state["saved"] = int(changed.sum())
        st.rerun()

# ---------------------------------------------------------------- company history

with history:
    companies = sorted(apps["Company"].unique(), key=str.lower)
    company = st.selectbox("Company", companies, index=None, placeholder="Pick a company to see every email from it")
    if company:
        rows = apps[apps["Company"] == company]
        for _, row in rows.iterrows():
            st.markdown(card(row), unsafe_allow_html=True)
        trail = emails[emails["Company"].str.lower() == company.lower()].sort_values("Date")
        if trail.empty:
            st.caption("No logged emails for this company.")
        else:
            timeline = trail.assign(Day=pd.to_datetime(trail["Date"]), Step=range(len(trail)))
            dots = (
                alt.Chart(timeline)
                .mark_circle(size=180, color=HOT_PINK, stroke="#0B0B0B", strokeWidth=2)
                .encode(
                    x=alt.X("Day:T", title=None, axis=alt.Axis(format="%b %d", grid=False)),
                    y=alt.Y("Kind:N", sort=PIPELINE + ["Verification", "Other"], title=None),
                    tooltip=[alt.Tooltip("Day:T", format="%a %b %d"), "Kind", "Subject"],
                )
                .properties(height=200)
            )
            st.altair_chart(dots, use_container_width=True)
            st.dataframe(
                trail[["Date", "Kind", "Subject", "Email link"]].sort_values("Date", ascending=False),
                hide_index=True, width="stretch",
                column_config={"Email link": st.column_config.LinkColumn("Email", display_text="Open")},
            )

# ---------------------------------------------------------------- email log

with log:
    kinds = sorted(k for k in emails["Kind"].unique() if k)
    chosen_kinds = st.pills("Kind", kinds, selection_mode="multi", key="kind_pills")
    shown = emails if not chosen_kinds else emails[emails["Kind"].isin(chosen_kinds)]
    st.caption(f"{len(shown)} of {len(emails)} emails the tracker has read")
    st.dataframe(
        shown.sort_values("Date", ascending=False).drop(columns=["Message ID"]),
        hide_index=True, width="stretch", height=520,
        column_config={"Email link": st.column_config.LinkColumn("Email", display_text="Open")},
    )
