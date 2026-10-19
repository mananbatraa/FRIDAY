"""FRIDAY dashboard: see every job application and where it stands.

    streamlit run dashboard.py

Reads the same data the tracker writes: the Google Sheet if SHEET_ID is set in
.env, otherwise applications.csv and emails.csv in this folder.
"""
from __future__ import annotations

import warnings
from datetime import date, timedelta

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*OpenSSL.*")

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from tracker.config import Config  # noqa: E402
from tracker.storage import APP_COLUMNS, EMAIL_COLUMNS, open_tables  # noqa: E402

PIPELINE = ["Applied", "Assessment", "Interview", "Offer", "Rejected"]
ACTIVE = ["Assessment", "Interview", "Offer"]
BAR = "#2a78d6"

st.set_page_config(page_title="FRIDAY · Job applications", page_icon="💼", layout="wide")


@st.cache_data(ttl=120, show_spinner="Loading your applications…")
def load() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    config = Config.load()
    creds = None
    if config.sheet_id:
        from tracker.google_auth import get_credentials

        creds = get_credentials(config.credentials_file, config.token_file)
    app_table, email_table = open_tables(creds, config.sheet_id)
    apps = pd.DataFrame(app_table.load(), columns=APP_COLUMNS).fillna("")
    emails = pd.DataFrame(email_table.load(), columns=EMAIL_COLUMNS).fillna("")
    for df, col in ((apps, "Applied on"), (apps, "Last update"), (emails, "Date")):
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    source = "Google Sheet" if config.sheet_id else "applications.csv"
    return apps, emails, source


apps, emails, source = load()

top = st.columns([4, 1])
top[0].title("Job applications")
if top[1].button("Refresh", use_container_width=True):
    load.clear()
    st.rerun()

if apps.empty:
    st.info("No applications yet. Run `python -m tracker.main` first, then refresh this page.")
    st.stop()

# ------------------------------------------------------------------ headline
total = len(apps)
heard_back = int((apps["Status"] != "Applied").sum())
counts = apps["Status"].value_counts()
last_week = int((apps["Applied on"] >= date.today() - timedelta(days=7)).sum())

kpi = st.columns(5)
kpi[0].metric("Applications", total, f"+{last_week} this week" if last_week else None)
kpi[1].metric(f"Heard back ({heard_back} of {total})", f"{heard_back / total:.0%}")
kpi[2].metric("Interviews + assessments", int(counts.get("Interview", 0) + counts.get("Assessment", 0)))
kpi[3].metric("Offers", int(counts.get("Offer", 0)))
kpi[4].metric("Rejected", int(counts.get("Rejected", 0)))

# ------------------------------------------------------------------ charts
left, right = st.columns([3, 2])

with left:
    st.subheader("Applications per day")
    dated = apps.dropna(subset=["Applied on"])
    if dated.empty:
        st.caption("No dates yet.")
    else:
        start = max(min(dated["Applied on"]), date.today() - timedelta(days=60))
        days = pd.DataFrame({"Day": pd.date_range(start, date.today(), freq="D").date})
        per_day = dated.groupby("Applied on").size().rename("Applications").reset_index()
        per_day = days.merge(per_day, how="left", left_on="Day", right_on="Applied on").fillna({"Applications": 0})
        per_day["Day"] = pd.to_datetime(per_day["Day"])
        chart = (
            alt.Chart(per_day)
            .mark_bar(color=BAR, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("yearmonthdate(Day):O", title=None, axis=alt.Axis(format="%b %d", labelAngle=0, labelOverlap=True)),
                y=alt.Y("Applications:Q", title=None, axis=alt.Axis(tickMinStep=1, gridOpacity=0.3)),
                tooltip=[alt.Tooltip("yearmonthdate(Day):T", title="Day", format="%a %b %d"), alt.Tooltip("Applications:Q")],
            )
            .properties(height=260)
        )
        st.altair_chart(chart, use_container_width=True)

with right:
    st.subheader("Where things stand")
    stages = pd.DataFrame({"Status": PIPELINE, "Applications": [int(counts.get(s, 0)) for s in PIPELINE]})
    base = alt.Chart(stages).encode(
        y=alt.Y("Status:N", sort=PIPELINE, title=None, axis=alt.Axis(labelFontSize=13)),
        x=alt.X("Applications:Q", title=None, axis=None),
        tooltip=["Status", "Applications"],
    )
    bars = base.mark_bar(color=BAR, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height=22)
    labels = base.mark_text(align="left", dx=6, fontSize=13).encode(text="Applications:Q")
    st.altair_chart((bars + labels).properties(height=260), use_container_width=True)

# ------------------------------------------------------------------ needs attention
active = apps[apps["Status"].isin(ACTIVE)].sort_values("Last update", ascending=False)
recent_checks = emails[
    (emails["Kind"] == "Verification") & (emails["Date"] >= date.today() - timedelta(days=3))
] if not emails.empty else emails

st.subheader("Needs your attention")
if active.empty and recent_checks.empty:
    st.caption("Nothing right now. Interviews, assessments and offers will show up here.")
else:
    if not active.empty:
        st.dataframe(
            active[["Company", "Role", "Status", "Last update", "Next action", "Latest email"]],
            hide_index=True, use_container_width=True,
            column_config={
                "Latest email": st.column_config.LinkColumn("Email", display_text="Open"),
                "Last update": st.column_config.DateColumn(format="MMM D"),
            },
        )
    if not recent_checks.empty:
        with st.expander(f"{len(recent_checks)} security-code or verification emails in the last 3 days"):
            st.dataframe(
                recent_checks[["Date", "Subject", "Email link"]], hide_index=True, use_container_width=True,
                column_config={"Email link": st.column_config.LinkColumn("Email", display_text="Open")},
            )

# ------------------------------------------------------------------ all applications
st.subheader("All applications")
f1, f2, f3 = st.columns([2, 2, 2])
picked = f1.multiselect("Status", PIPELINE, placeholder="All statuses")
search = f2.text_input("Search company or role", placeholder="e.g. Affirm, intern")
dated_min = min((d for d in apps["Applied on"] if pd.notna(d)), default=date.today())
period = f3.date_input("Applied between", (dated_min, date.today()))

view = apps.copy()
if picked:
    view = view[view["Status"].isin(picked)]
if search:
    needle = search.lower()
    view = view[view["Company"].str.lower().str.contains(needle, regex=False)
                | view["Role"].str.lower().str.contains(needle, regex=False)]
if isinstance(period, (list, tuple)) and len(period) == 2:
    view = view[view["Applied on"].between(period[0], period[1])]

st.caption(f"{len(view)} of {total} applications · data from {source}")
st.dataframe(
    view.sort_values("Applied on", ascending=False),
    hide_index=True, use_container_width=True, height=480,
    column_config={
        "Latest email": st.column_config.LinkColumn("Email", display_text="Open"),
        "Applied on": st.column_config.DateColumn(format="MMM D"),
        "Last update": st.column_config.DateColumn(format="MMM D"),
    },
)

with st.expander("Email log: every email the tracker has read"):
    st.dataframe(
        emails.sort_values("Date", ascending=False).drop(columns=["Message ID"]),
        hide_index=True, use_container_width=True,
        column_config={"Email link": st.column_config.LinkColumn("Email", display_text="Open")},
    )
