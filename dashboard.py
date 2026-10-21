"""FRIDAY dashboard: a calm, editorial view of your job search.

    streamlit run dashboard.py               # your data
    streamlit run dashboard.py -- --demo     # sample data, no Gmail needed

Reads the same data the tracker writes: the Google Sheet if SHEET_ID is set in
.env, otherwise applications.csv, emails.csv and todos.csv in this folder.
"""
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*OpenSSL.*")

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from tracker import demo  # noqa: E402
from tracker.config import Config  # noqa: E402
from tracker.storage import (  # noqa: E402
    APP_COLUMNS, EMAIL_COLUMNS, TODO_COLUMNS, CsvTable, open_todo_table, open_tables,
)

DEMO = "--demo" in sys.argv[1:]
HERE = Path(__file__).resolve().parent

PIPELINE = ["Applied", "Assessment", "Interview", "Offer", "Rejected"]
ACTIVE = ["Assessment", "Interview", "Offer"]
RANK = {"Applied": 1, "Assessment": 2, "Interview": 3, "Offer": 4}
FUNNEL = [("Applied", 1), ("Screen / assessment", 2), ("Interview loop", 3), ("Offer", 4)]
MODES = ["Remote", "Hybrid", "Onsite"]
RANGES = {"7 days": 7, "30 days": 30, "90 days": 90, "All time": None}
ROUND_COLUMNS = ["When", "Round", "Interviewer", "Meeting link", "Prep doc"]
EDITABLE = ["Status", "Work mode", "Next action", "Notes"]
PIPELINE_PREVIEW = 8

# Palette (see .streamlit/config.toml)
INK = "#cfeaf2"
MUTED = "#6f8da3"
LINE = "#16405a"
CYAN = "#2de2e6"
GOLD = "#f5b942"
STONE = "#16324a"

ARC_REACTOR = (
    '<svg class="reactor" viewBox="0 0 100 100" width="46" height="46" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="50" cy="50" r="46" fill="none" stroke="#2de2e6" stroke-width="2" opacity=".5"/>'
    '<circle cx="50" cy="50" r="36" fill="none" stroke="#2de2e6" stroke-width="5" stroke-dasharray="9 5"/>'
    '<circle cx="50" cy="50" r="24" fill="none" stroke="#2de2e6" stroke-width="2"/>'
    '<polygon points="50,33 64.7,41.5 64.7,58.5 50,67 35.3,58.5 35.3,41.5" fill="#2de2e6" opacity=".9"/>'
    '<circle cx="50" cy="50" r="7" fill="#e9ffff"/></svg>'
)

st.set_page_config(page_title="F.R.I.D.A.Y. · Stark Industries", page_icon="⚛️", layout="wide")
st.markdown(
    f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');
    html, body, [class*="st-"], button, input, textarea {{ font-family: 'Rajdhani', -apple-system, sans-serif; }}
    .stApp {{
        background:
            radial-gradient(circle at 12% -5%, rgba(45,226,230,.13), transparent 42%),
            radial-gradient(circle at 95% 5%, rgba(229,72,77,.09), transparent 36%),
            linear-gradient(rgba(45,226,230,.035) 1px, transparent 1px) 0 0 / 44px 44px,
            linear-gradient(90deg, rgba(45,226,230,.035) 1px, transparent 1px) 0 0 / 44px 44px,
            #060b14;
    }}
    .block-container {{ padding-top: 2rem; max-width: 1320px; }}
    h1, h2, h3, h4 {{ font-family: 'Orbitron', sans-serif !important; font-weight: 600 !important; color: {INK};
                      letter-spacing: .04em; }}
    h3 {{ font-size: .98rem !important; text-transform: uppercase; color: {CYAN} !important; padding: 0 0 .5rem !important; }}
    [data-testid="stIconMaterial"] {{ color: {CYAN}; }}

    /* Brand bar */
    .brandbar {{ display: flex; justify-content: space-between; align-items: center; padding-bottom: .9rem;
        margin-bottom: 1.3rem; border-bottom: 1px solid {LINE}; }}
    .stark {{ font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 1.35rem; letter-spacing: .32em; color: {CYAN};
        text-shadow: 0 0 14px rgba(45,226,230,.55); }}
    .stark small {{ display: block; font-family: 'Rajdhani', sans-serif; font-weight: 600; font-size: .72rem;
        letter-spacing: .38em; color: {GOLD}; margin-top: .15rem; }}
    .friday {{ display: flex; align-items: center; gap: .85rem; text-align: right; }}
    .friday b {{ display: block; font-family: 'Orbitron', sans-serif; font-weight: 700; font-size: 1.3rem;
        letter-spacing: .3em; color: {CYAN}; text-shadow: 0 0 14px rgba(45,226,230,.55); }}
    .friday small {{ display: block; font-size: .72rem; letter-spacing: .2em; color: {MUTED}; text-transform: uppercase; }}
    .reactor {{ filter: drop-shadow(0 0 8px rgba(45,226,230,.8)); animation: pulse 3.2s ease-in-out infinite; }}
    @keyframes pulse {{ 0%, 100% {{ opacity: .75; }} 50% {{ opacity: 1; }} }}

    .eyebrow {{ font-size: .8rem; font-weight: 600; letter-spacing: .28em; color: {GOLD}; text-transform: uppercase; }}
    h1.title {{ font-size: 1.9rem !important; font-weight: 500 !important; text-transform: uppercase; letter-spacing: .18em;
        line-height: 1.25; margin: .35rem 0 .55rem; padding: 0 !important; text-shadow: 0 0 22px rgba(45,226,230,.25); }}
    .summary {{ color: {MUTED}; font-size: 1.1rem; margin: 0; letter-spacing: .02em; }}
    .summary b {{ color: {CYAN}; font-weight: 700; }}

    /* HUD panels with corner brackets */
    div[class*="st-key-tile_"] {{ position: relative; background: rgba(10,22,38,.78); border: 1px solid {LINE};
        border-radius: 4px; box-shadow: 0 0 26px rgba(45,226,230,.07), inset 0 0 40px rgba(45,226,230,.03);
        padding: 1.15rem 1.35rem 1.3rem; }}
    div[class*="st-key-tile_"]::before, div[class*="st-key-tile_"]::after {{ content: ""; position: absolute;
        width: 16px; height: 16px; border: 0 solid {CYAN}; pointer-events: none; }}
    div[class*="st-key-tile_"]::before {{ top: -1px; left: -1px; border-top-width: 2px; border-left-width: 2px; }}
    div[class*="st-key-tile_"]::after {{ bottom: -1px; right: -1px; border-bottom-width: 2px; border-right-width: 2px; }}
    .tile-note {{ color: {MUTED}; font-size: .95rem; margin-top: -.35rem; }}

    /* Pipeline rows */
    .thead {{ color: {GOLD}; font-size: .74rem; font-weight: 700; letter-spacing: .22em; text-transform: uppercase; }}
    div[class*="st-key-row_"] {{ border-top: 1px solid #10304a; padding: .5rem .5rem; border-radius: 3px;
        transition: background .2s ease, box-shadow .2s ease; }}
    div[class*="st-key-row_"]:hover {{ background: rgba(45,226,230,.07); box-shadow: inset 2px 0 0 {CYAN}; }}
    .co {{ font-weight: 700; color: {INK}; line-height: 1.3; font-size: 1.05rem; letter-spacing: .02em; }}
    .role {{ color: {MUTED}; font-size: .92rem; line-height: 1.35; }}
    .touch {{ color: {MUTED}; font-size: .95rem; }}
    div[class*="st-key-drawer_"] {{ background: rgba(45,226,230,.04); border: 1px solid {LINE}; border-radius: 4px;
        padding: 1rem 1.1rem; margin: .4rem 0 .3rem; }}
    .trail {{ color: {MUTED}; font-size: .92rem; line-height: 1.6; }}

    /* Stage badges */
    .badge {{ display: inline-block; padding: 2px 11px; border-radius: 2px; font-size: .74rem; font-weight: 700;
              letter-spacing: .12em; text-transform: uppercase; border: 1px solid; white-space: nowrap; }}
    .b-offer {{ color: #5dffa8; background: rgba(93,255,168,.1); border-color: #2e8f5f; box-shadow: 0 0 10px rgba(93,255,168,.25); }}
    .b-interview {{ color: {CYAN}; background: rgba(45,226,230,.1); border-color: #1d8a90; box-shadow: 0 0 10px rgba(45,226,230,.25); }}
    .b-assessment {{ color: {GOLD}; background: rgba(245,185,66,.1); border-color: #8f6a22; }}
    .b-applied {{ color: #9db6c6; background: rgba(157,182,198,.08); border-color: #2f4b60; }}
    .b-rejected {{ color: #e5484d; background: rgba(229,72,77,.08); border-color: #6f2a2d; opacity: .8; }}

    /* Incoming 48 hours */
    div[class*="st-key-slot_"] {{ border-left: 2px solid {GOLD}; padding: .1rem 0 .4rem .9rem; margin-bottom: .6rem; }}
    .when-day {{ font-size: .78rem; font-weight: 700; letter-spacing: .24em; text-transform: uppercase; color: {GOLD}; }}
    .when-time {{ font-family: 'Orbitron', sans-serif; font-size: 1.35rem; color: {INK}; line-height: 1.25; }}

    /* Funnel */
    .conv {{ color: {MUTED}; font-size: .98rem; line-height: 1.75; }}
    .conv b {{ color: {CYAN}; font-family: 'Orbitron', sans-serif; font-size: .9rem; font-weight: 600; }}

    /* Directives checklist: strike through gently when ticked */
    div.st-key-todos [data-testid="stCheckbox"] p {{ text-decoration: line-through; text-decoration-color: transparent;
        text-decoration-thickness: 1.5px; transition: text-decoration-color .4s ease, color .4s ease; }}
    div.st-key-todos [data-testid="stCheckbox"] label:has(input:checked) p {{ text-decoration-color: {MUTED};
        color: {MUTED}; }}

    /* Buttons, tabs, dialog */
    button[kind="primary"], button[kind="primaryFormSubmit"] {{ background: rgba(45,226,230,.12); border: 1px solid {CYAN};
        color: {CYAN}; border-radius: 3px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
        box-shadow: 0 0 14px rgba(45,226,230,.2); }}
    button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {{ background: rgba(45,226,230,.25);
        border-color: {CYAN}; color: #e9ffff; box-shadow: 0 0 22px rgba(45,226,230,.5); }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 1.6rem; border-bottom: 1px solid {LINE}; }}
    .stTabs [data-baseweb="tab"] p {{ letter-spacing: .14em; text-transform: uppercase; font-weight: 600; }}
    .stTabs [aria-selected="true"] p {{ color: {CYAN}; font-weight: 700; text-shadow: 0 0 10px rgba(45,226,230,.5); }}
    div[data-baseweb="modal"] > div:first-child {{ backdrop-filter: blur(5px); background: rgba(2,6,12,.65); }}
    div[role="dialog"] {{ background: #0a1626; border: 1px solid {CYAN}; border-radius: 4px;
        box-shadow: 0 0 40px rgba(45,226,230,.25); }}
    </style>""",
    unsafe_allow_html=True,
)


def chart_style(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure_axis(labelColor=MUTED, titleColor=MUTED, gridColor="#10263a", domainColor=LINE,
                             tickColor=LINE, labelFont="Rajdhani", labelFontSize=12)
        .configure_view(strokeWidth=0)
        .configure(background="transparent")
    )


# ---------------------------------------------------------------- data

@st.cache_resource
def tables():
    """(applications, emails, to-dos) tables and a label for where the data lives."""
    if DEMO:
        folder = HERE / ".demo"
        return (CsvTable(str(folder / "applications.csv"), APP_COLUMNS),
                CsvTable(str(folder / "emails.csv"), EMAIL_COLUMNS),
                CsvTable(str(folder / "todos.csv"), TODO_COLUMNS)), "sample data"
    config = Config.load()
    creds = None
    if config.sheet_id:
        from tracker.google_auth import get_credentials

        creds = get_credentials(config.credentials_file, config.token_file)
    app_table, email_table = open_tables(creds, config.sheet_id)
    return ((app_table, email_table, open_todo_table(creds, config.sheet_id)),
            "Google Sheet" if config.sheet_id else "applications.csv")


@st.cache_data(ttl=120, show_spinner="Retrieving your applications…")
def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    (app_table, email_table, todo_table), _ = tables()
    if DEMO and not os.path.exists(app_table.path):
        demo.seed(os.path.dirname(app_table.path))
    apps = pd.DataFrame(app_table.load(), columns=APP_COLUMNS).fillna("")
    emails = pd.DataFrame(email_table.load(), columns=EMAIL_COLUMNS).fillna("")
    todos = pd.DataFrame(todo_table.load(), columns=TODO_COLUMNS).fillna("")
    for df, col in ((apps, "Applied on"), (apps, "Last update"), (emails, "Date"), (todos, "Due"), (todos, "Done")):
        dates = pd.to_datetime(df[col], errors="coerce")
        df[col] = [d.date() if pd.notna(d) else None for d in dates]  # None, not NaT, for blanks
    return apps, emails, todos


def _iso(d) -> str:
    return d.isoformat() if isinstance(d, date) else ""


def save_apps(df: pd.DataFrame) -> None:
    rows = df.copy()
    for col in ("Applied on", "Last update"):
        rows[col] = rows[col].apply(_iso)
    tables()[0][0].save(rows.fillna("").to_dict("records"))
    load.clear()


def save_todos(df: pd.DataFrame) -> None:
    rows = df.copy()
    for col in ("Due", "Done"):
        rows[col] = rows[col].apply(_iso)
    tables()[0][2].save(rows.fillna("").to_dict("records"))
    load.clear()


def flash(message: str) -> None:
    st.session_state["flash"] = message


def check_email_now() -> None:
    """Run the tracker in the background and report what changed."""
    with st.spinner("Scanning your inbox for job news…"):
        result = subprocess.run(
            [sys.executable, "-m", "tracker.main", "--background"],
            cwd=HERE, capture_output=True, text=True,
        )
    load.clear()
    output = result.stdout + result.stderr
    changes = [line.strip() for line in output.splitlines() if line.startswith(("  +", "  ~"))]
    if result.returncode != 0:
        st.session_state["check_error"] = output.strip().splitlines()[-1] if output.strip() else "Failed"
    elif changes:
        flash(f"{len(changes)} update{'s' if len(changes) != 1 else ''}: " + "; ".join(c[2:] for c in changes[:5]))
    else:
        flash("No new job emails detected.")


def rounds_of(cell: str) -> list[dict]:
    try:
        rounds = json.loads(cell) if cell else []
    except ValueError:
        return []
    return [r for r in rounds if isinstance(r, dict)]


def rounds_frame(cell: str) -> pd.DataFrame:
    df = pd.DataFrame(rounds_of(cell), columns=ROUND_COLUMNS)
    df["When"] = pd.to_datetime(df["When"], errors="coerce")
    for col in ROUND_COLUMNS[1:]:
        df[col] = df[col].fillna("").astype(str)
    return df


def rounds_json(df: pd.DataFrame) -> str:
    rounds = []
    for _, r in df.iterrows():
        item = {"When": r["When"].isoformat(timespec="minutes") if pd.notna(r["When"]) else ""}
        item.update({c: "" if pd.isna(r[c]) else str(r[c]).strip() for c in ROUND_COLUMNS[1:]})
        if any(item.values()):
            rounds.append(item)
    rounds.sort(key=lambda r: r["When"] or "9999")
    return json.dumps(rounds) if rounds else ""


def badge(status: str) -> str:
    return f'<span class="badge b-{html.escape(status.lower())}">{html.escape(status or "Unknown")}</span>'


def ago(d) -> str:
    if not isinstance(d, date):
        return "–"
    days = (date.today() - d).days
    if days <= 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    return d.strftime("%b %-d")


def day_name(d: date) -> str:
    offset = (d - date.today()).days
    return {0: "Today", 1: "Tomorrow"}.get(offset, d.strftime("%A"))


# ---------------------------------------------------------------- dialogs and callbacks

@st.dialog("Add an application", width="medium")
def add_application() -> None:
    with st.form("add_app", border=False):
        company = st.text_input("Company", placeholder="e.g. Stripe")
        role = st.text_input("Role", placeholder="e.g. Staff Software Engineer, Payments")
        c1, c2, c3 = st.columns(3)
        status = c1.selectbox("Stage", PIPELINE[:4])
        applied = c2.date_input("Applied on", value=date.today(), format="YYYY-MM-DD")
        mode = c3.selectbox("Work mode", [""] + MODES, format_func=lambda m: m or "Not sure")
        action = st.text_input("Next step", placeholder="Optional, e.g. Ask Maya for a referral")
        notes = st.text_area("Notes", placeholder="Optional", height=90)
        if st.form_submit_button("Add application", type="primary", width="stretch"):
            if not company.strip():
                st.error("Add a company name.")
                return
            apps, _, _ = load()
            row = {c: "" for c in APP_COLUMNS}
            row.update({"Company": company.strip(), "Role": role.strip(), "Status": status, "Applied on": applied,
                        "Last update": date.today(), "Next action": action.strip(), "Notes": notes.strip(),
                        "Work mode": mode})
            save_apps(pd.concat([apps, pd.DataFrame([row])], ignore_index=True))
            flash(f"{company.strip()} logged. Good luck, Master.")
            st.rerun()


def toggle_row(idx: int) -> None:
    st.session_state["open_row"] = None if st.session_state.get("open_row") == idx else idx


def tick(kind: str, idx: int, key: str) -> None:
    """Checkbox callback for the follow-up queue."""
    apps, _, todos = load()
    checked = st.session_state[key]
    if kind == "app":
        # A tracker-suggested step: record it as done and clear it from the application.
        row = apps.loc[idx]
        todos.loc[len(todos)] = {"Task": f"{row['Next action']} at {row['Company']}", "Company": row["Company"],
                                 "Due": None, "Done": date.today(), "Source": "tracker"}
        apps.loc[idx, "Next action"] = ""
        save_apps(apps)
    else:
        todos.loc[idx, "Done"] = date.today() if checked else None
    save_todos(todos.reset_index(drop=True))


# ---------------------------------------------------------------- header

apps, emails, todos = load()
_, source = tables()
today = date.today()
now = datetime.now()

name = "" if DEMO else os.environ.get("FRIDAY_NAME", "").strip()
hello = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"
title = demo.TITLE if DEMO else (os.environ.get("SEARCH_TITLE") or (f"{hello}, {name}" if name else hello))

upcoming = []
for idx, row in apps.iterrows():
    for r in rounds_of(row["Rounds"]):
        try:
            when = datetime.fromisoformat(r.get("When", ""))
        except ValueError:
            continue
        if now - timedelta(hours=1) <= when <= now + timedelta(hours=48):
            upcoming.append({**r, "when": when, "Company": row["Company"], "idx": idx})
upcoming.sort(key=lambda r: r["when"])

active = int(apps["Status"].isin(ACTIVE).sum())
open_todos = int((todos["Done"].isna() | (todos["Done"] == "")).sum()) + int((apps["Next action"] != "").sum())
CHEERS = ["All systems nominal", "Ready when you are", "Shall we get to work?", "The odds are in your favor",
          "Suit up"]
random_cheer = CHEERS[today.toordinal() % len(CHEERS)]  # same one all day
summary = [f"<b>{active}</b> active conversation{'s' if active != 1 else ''}"]
if upcoming:
    summary.append(f"<b>{len(upcoming)}</b> round{'s' if len(upcoming) != 1 else ''} in the next 48 hours")
if open_todos:
    summary.append(f"<b>{open_todos}</b> follow-up{'s' if open_todos != 1 else ''}")
summary.append(random_cheer)

st.markdown(
    '<div class="brandbar"><div class="stark">STARK INDUSTRIES</div>'
    f'<div class="friday"><div><b>F.R.I.D.A.Y.</b></div>{ARC_REACTOR}</div></div>',
    unsafe_allow_html=True,
)
top = st.columns([3.4, 2.1], vertical_alignment="bottom")
top[0].markdown(
    f'<div class="eyebrow">System online · {today.strftime("%A, %B %-d")}</div>'
    f'<h1 class="title">{html.escape(title)}</h1>'
    f'<p class="summary">{" · ".join(summary)}</p>',
    unsafe_allow_html=True,
)
with top[1]:
    mode = st.segmented_control("Work mode", ["All"] + MODES, default="All", key="mode",
                                label_visibility="collapsed") or "All"
    b = st.columns([2.2, 1, 1])
    if b[0].button("Add application", icon=":material/add:", type="primary", width="stretch"):
        add_application()
    if b[1].button("", icon=":material/mail:", help="Check email now" if not DEMO else "Not available with sample data",
                   width="stretch", disabled=DEMO):
        check_email_now()
        st.rerun()
    if b[2].button("", icon=":material/refresh:", help="Reload data", width="stretch"):
        load.clear()
        st.rerun()

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon=":material/check:")
if "check_error" in st.session_state:
    st.error(st.session_state.pop("check_error"))

st.write("")
if apps.empty:
    st.info("No applications on record. Scan your inbox with the mail button, or log your first one by hand.")
    st.stop()

in_mode = apps if mode == "All" else apps[apps["Work mode"] == mode]
today_tab, all_apps, history, log = st.tabs(["Today", "All applications", "Company history", "Email log"])

# ---------------------------------------------------------------- today (bento grid)


def drawer(idx: int, row: pd.Series) -> None:
    with st.container(key=f"drawer_{idx}"):
        st.markdown("**Interview rounds**")
        rounds = st.data_editor(
            rounds_frame(row["Rounds"]), num_rows="dynamic", hide_index=True, width="stretch", key=f"rounds_{idx}",
            column_config={
                "When": st.column_config.DatetimeColumn(format="ddd MMM D, h:mm a", step=900, width="medium"),
                "Round": st.column_config.TextColumn(width="medium"),
                "Interviewer": st.column_config.TextColumn(width="medium"),
                "Meeting link": st.column_config.LinkColumn(display_text="Join"),
                "Prep doc": st.column_config.LinkColumn(display_text="Open"),
            },
        )
        c1, c2, c3 = st.columns([1, 1, 2])
        status = c1.selectbox("Stage", PIPELINE, index=PIPELINE.index(row["Status"]) if row["Status"] in PIPELINE
                              else 0, key=f"stage_{idx}")
        work = c2.selectbox("Work mode", [""] + MODES, index=([""] + MODES).index(row["Work mode"])
                            if row["Work mode"] in MODES else 0, format_func=lambda m: m or "Not set",
                            key=f"mode_{idx}")
        action = c3.text_input("Next step", value=row["Next action"], key=f"action_{idx}")
        left, right = st.columns([3, 2], gap="large")
        notes = left.text_area("Notes", value=row["Notes"], height=100, key=f"notes_{idx}")
        trail = emails[emails["Company"].str.lower() == row["Company"].lower()].sort_values("Date", ascending=False)
        if not trail.empty:
            lines = "<br>".join(
                f'{d.strftime("%b %-d") if isinstance(d, date) else ""} · {html.escape(k)} · '
                f'<a href="{html.escape(link)}" target="_blank">{html.escape(s)}</a>'
                for d, k, s, link in trail[["Date", "Kind", "Subject", "Email link"]].head(4).itertuples(index=False)
            )
            right.markdown(f'<div class="trail"><b>Recent emails</b><br>{lines}</div>', unsafe_allow_html=True)
        if st.button("Save details", type="primary", key=f"save_{idx}"):
            fresh, _, _ = load()
            if status != fresh.loc[idx, "Status"]:
                fresh.loc[idx, "Last update"] = today
            fresh.loc[idx, ["Status", "Work mode", "Next action", "Notes", "Rounds"]] = [
                status, work, action.strip(), notes.strip(), rounds_json(rounds)]
            save_apps(fresh)
            flash(f"Saved {row['Company']}")
            st.rerun()


with today_tab:
    main, side = st.columns([1.85, 1], gap="medium")

    # Tile 1: active pipeline
    with main, st.container(key="tile_pipeline"):
        st.markdown("### Active pipeline")
        pipeline = in_mode[in_mode["Status"] != "Rejected"].copy()
        pipeline["rank"] = pipeline["Status"].map(RANK).fillna(0)
        pipeline["touch"] = pd.to_datetime(pipeline["Last update"], errors="coerce")
        pipeline = pipeline.sort_values(["rank", "touch"], ascending=[False, False])
        note = f"{len(pipeline)} open application{'s' if len(pipeline) != 1 else ''}" + ("" if mode == "All" else f" · {mode}")
        st.markdown(f'<div class="tile-note">{note} · click a row\'s arrow for rounds, interviewers and notes</div>',
                    unsafe_allow_html=True)
        if pipeline.empty:
            st.caption(f"Nothing marked {mode} yet. Set the work mode in an application's details."
                       if mode != "All" else "No open applications. Time to deploy one.")
        widths = [3.6, 1.5, 1.3, 1.25]
        head = st.columns(widths)
        for col, label in zip(head, ["Company", "Stage", "Last touch", ""]):
            col.markdown(f'<div class="thead">{label}</div>', unsafe_allow_html=True)
        show_all = st.session_state.get("show_all", False)
        for idx, row in (pipeline if show_all else pipeline.head(PIPELINE_PREVIEW)).iterrows():
            with st.container(key=f"row_{idx}"):
                c = st.columns(widths, vertical_alignment="center")
                extra = f" · {row['Work mode']}" if row["Work mode"] else ""
                c[0].markdown(f'<div class="co">{html.escape(row["Company"])}</div>'
                              f'<div class="role">{html.escape(row["Role"] or "Role not found")}{extra}</div>',
                              unsafe_allow_html=True)
                c[1].markdown(badge(row["Status"]), unsafe_allow_html=True)
                c[2].markdown(f'<div class="touch">{ago(row["Last update"])}</div>', unsafe_allow_html=True)
                with c[3]:
                    a = st.columns(2, gap="small")
                    is_open = st.session_state.get("open_row") == idx
                    a[0].button("", icon=":material/expand_less:" if is_open else ":material/expand_more:",
                                key=f"open_{idx}", help="Rounds, interviewers and notes", on_click=toggle_row,
                                args=(idx,), type="tertiary")
                    if row["Latest email"]:
                        a[1].link_button("", row["Latest email"], icon=":material/mail:", help="Open latest email",
                                         type="tertiary")
                if is_open:
                    drawer(idx, row)
        if len(pipeline) > PIPELINE_PREVIEW:
            label = "Show fewer" if show_all else f"Show all {len(pipeline)}"
            if st.button(label, type="tertiary", key="more"):
                st.session_state["show_all"] = not show_all
                st.rerun()

    # Tile 2: next 48 hours
    with side, st.container(key="tile_next"):
        st.markdown("### Incoming · 48 hours")
        if not upcoming:
            st.markdown('<div class="tile-note">Nothing scheduled. Add a round from a row\'s details in the '
                        'pipeline and it will show up here.</div>', unsafe_allow_html=True)
        for n, r in enumerate(upcoming):
            with st.container(key=f"slot_{n}"):
                st.markdown(
                    f'<div class="when-day">{day_name(r["when"].date())}</div>'
                    f'<div class="when-time">{r["when"].strftime("%-I:%M %p")}</div>'
                    f'<div class="co">{html.escape(r["Company"])}</div>'
                    f'<div class="role">{html.escape(r.get("Round") or "Interview")}</div>',
                    unsafe_allow_html=True,
                )
                if r.get("Interviewer"):
                    st.caption(f":material/person: {r['Interviewer']}")
                links = [(label, r.get(key), icon) for label, key, icon in
                         (("Meeting link", "Meeting link", ":material/videocam:"),
                          ("Prep doc", "Prep doc", ":material/description:")) if r.get(key)]
                if links:
                    lc = st.columns(len(links))
                    for col, (label, url, icon) in zip(lc, links):
                        col.link_button(label, url, icon=icon, width="stretch")

    # Tile 3: funnel
    with side, st.container(key="tile_funnel"):
        st.markdown("### Conversion funnel")
        ranks = in_mode["Status"].map(RANK).fillna(0)
        reached = [int((ranks >= k).sum()) if k > 1 else len(in_mode) for _, k in FUNNEL]
        stages = pd.DataFrame({"Stage": [s for s, _ in FUNNEL], "Applications": reached})
        stages["Label"] = stages["Stage"] + "  " + stages["Applications"].astype(str)
        pick = alt.selection_point(fields=["Stage"], name="pick")
        bars = alt.Chart(stages).mark_bar(cornerRadius=2, height=18, cursor="pointer").encode(
            y=alt.Y("Label:N", sort=list(stages["Label"]), title=None,
                    axis=alt.Axis(labelFontSize=12.5, labelLimit=220, ticks=False, domain=False, labelColor=INK)),
            x=alt.X("Applications:Q", title=None, axis=None),
            color=alt.condition(pick, alt.value(CYAN), alt.value(STONE)),
            tooltip=["Stage", "Applications"],
        ).add_params(pick).properties(height=104)
        event = st.altair_chart(chart_style(bars), use_container_width=True, on_select="rerun", key="funnel")
        steps = []
        for (a_name, _), (b_name, _), a_n, b_n in zip(FUNNEL, FUNNEL[1:], reached, reached[1:]):
            rate = f"{b_n / a_n:.0%}" if a_n else "–"
            steps.append(f"{a_name.split(' /')[0]} → {b_name.split(' /')[0]} <b>{rate}</b>")
        st.markdown(f'<div class="conv">{"<br>".join(steps)}</div>', unsafe_allow_html=True)
        chosen = [p["Stage"] for p in (event.selection.get("pick") or [])] if event else []
        if chosen:
            k = dict(FUNNEL)[chosen[0]]
            hits = in_mode[ranks >= k] if k > 1 else in_mode
            names = ", ".join(hits["Company"].head(12))
            more = f" and {len(hits) - 12} more" if len(hits) > 12 else ""
            st.caption(f"**{chosen[0]}:** {names}{more}")
        else:
            st.caption("Select a bar to see who made it that far.")

    # Tile 4: follow-up queue
    with main, st.container(key="tile_todos"):
        st.markdown("### Directives")
        with st.container(key="todos"):
            items = []
            for idx, row in apps[apps["Next action"] != ""].iterrows():
                items.append(("app", idx, f"{row['Next action']} at {row['Company']}", None, False))
            for idx, t in todos.iterrows():
                done = t["Done"] if isinstance(t["Done"], date) else None
                if done is None or done == today:
                    company = f" at {t['Company']}" if t["Company"] and t["Company"] not in t["Task"] else ""
                    items.append(("todo", idx, f"{t['Task']}{company}",
                                  t["Due"] if isinstance(t["Due"], date) else None, done is not None))
            items.sort(key=lambda i: (i[4], i[3] or date.max))
            if not items:
                st.markdown('<div class="tile-note">All directives complete. Well done.</div>', unsafe_allow_html=True)
            for kind, idx, text, due, done in items:
                due_text = f"  :gray[· due {day_name(due) if 0 <= (due - today).days < 7 else due.strftime('%b %-d')}]" \
                    if due and not done else ""
                key = f"tick_{kind}_{idx}"
                st.checkbox(f"{text}{due_text}", value=done, key=key, on_change=tick, args=(kind, idx, key))
        with st.form("add_todo", border=False, clear_on_submit=True):
            f = st.columns([4, 1.6, 0.6], vertical_alignment="bottom")
            task = f[0].text_input("New follow-up", placeholder="New directive, e.g. Send portfolio to Priya",
                                   label_visibility="collapsed")
            due = f[1].date_input("Due", value=None, label_visibility="collapsed", format="YYYY-MM-DD")
            if f[2].form_submit_button("", icon=":material/add:", width="stretch") and task.strip():
                todos.loc[len(todos)] = {"Task": task.strip(), "Company": "", "Due": due, "Done": None,
                                         "Source": "you"}
                save_todos(todos)
                flash("Directive logged")
                st.rerun()

    # Tile 5: activity
    with side, st.container(key="tile_activity"):
        st.markdown("### Outreach log")
        period = st.segmented_control("Show", list(RANGES), default="30 days", key="range",
                                      label_visibility="collapsed") or "30 days"
        days = RANGES[period]
        since = today - timedelta(days=days - 1) if days else None
        dated = in_mode[in_mode["Applied on"].apply(lambda d: isinstance(d, date) and (since is None or d >= since))]
        if dated.empty:
            st.caption("No applications in this period.")
        else:
            start = since or min(dated["Applied on"])
            per_day = pd.DataFrame({"Day": pd.date_range(start, today, freq="D").date})
            counted = dated.groupby("Applied on").size().rename("Applications")
            per_day["Applications"] = per_day["Day"].map(counted).fillna(0)
            per_day["Day"] = pd.to_datetime(per_day["Day"])
            # Whole-number ticks: list each one when the counts are small, otherwise let Vega pick about five.
            top_count = int(per_day["Applications"].max())
            y_ticks = {"values": list(range(top_count + 1))} if top_count <= 6 else {"tickCount": 5}
            chart = alt.Chart(per_day).mark_bar(color="#1fb6c1", cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
                x=alt.X("yearmonthdate(Day):O", title=None,
                        axis=alt.Axis(format="%b %d", labelAngle=0, labelOverlap=True, ticks=False)),
                y=alt.Y("Applications:Q", title=None, axis=alt.Axis(**y_ticks,
                                                                 format="d", domain=False, ticks=False)),
                tooltip=[alt.Tooltip("yearmonthdate(Day):T", title="Day", format="%a %b %d"),
                         alt.Tooltip("Applications:Q")],
            ).properties(height=170)
            st.altair_chart(chart_style(chart), use_container_width=True)
            st.caption(f"{len(dated)} sent · {int((dated['Status'] != 'Applied').sum())} heard back")

# ---------------------------------------------------------------- all applications (editable)

with all_apps:
    f1, f2, f3 = st.columns([3, 2, 2])
    picked_status = f1.pills("Stage", PIPELINE, selection_mode="multi", key="status_pills")
    search = f2.text_input("Search company or role", placeholder="e.g. Stripe, staff")
    sort_by = f3.selectbox("Sort by", ["Newest first", "Oldest first", "Company A–Z", "Recently updated"])

    view = in_mode.copy()
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

    st.caption(f"{len(view)} of {len(apps)} applications · data from {source} · "
               "edit Stage, Work mode, Next action or Notes right in the table, then press Save")
    edited = st.data_editor(
        view, hide_index=True, width="stretch", height=520, key="editor",
        column_order=["Company", "Role", "Status", "Work mode", "Applied on", "Last update", "Next action",
                      "Latest email", "Notes"],
        disabled=["Company", "Role", "Applied on", "Last update", "Latest email"],
        column_config={
            "Status": st.column_config.SelectboxColumn("Stage", options=PIPELINE, required=True),
            "Work mode": st.column_config.SelectboxColumn(options=MODES),
            "Latest email": st.column_config.LinkColumn("Email", display_text="Open"),
            "Applied on": st.column_config.DateColumn(format="MMM D"),
            "Last update": st.column_config.DateColumn(format="MMM D"),
            "Next action": st.column_config.TextColumn(width="medium"),
            "Notes": st.column_config.TextColumn(width="large"),
        },
    )
    changed = (edited[EDITABLE].fillna("") != view[EDITABLE].fillna("")).any(axis=1)
    n_changed = int(changed.sum())
    if st.button(f"Save {n_changed} change{'s' if n_changed != 1 else ''}", type="primary",
                 disabled=not n_changed):
        updated = apps.copy()
        for idx in edited.index[changed]:
            updated.loc[idx, EDITABLE] = edited.loc[idx, EDITABLE].fillna("")
            if updated.loc[idx, "Status"] != apps.loc[idx, "Status"]:
                updated.loc[idx, "Last update"] = today
        save_apps(updated)
        flash("Saved your changes")
        st.rerun()

# ---------------------------------------------------------------- company history

with history:
    companies = sorted(apps["Company"].unique(), key=str.lower)
    company = st.selectbox("Company", companies, index=None, placeholder="Pick a company to see every email from it")
    if company:
        for _, row in apps[apps["Company"] == company].iterrows():
            with st.container(key=f"tile_hist_{_}"):
                st.markdown(f'<div class="co" style="font-family:Georgia,serif;font-size:1.25rem">'
                            f'{html.escape(company)} &nbsp;{badge(row["Status"])}</div>'
                            f'<div class="role">{html.escape(row["Role"] or "Role not found")} · '
                            f'applied {ago(row["Applied on"]).lower()} · last touch {ago(row["Last update"]).lower()}'
                            f'</div>', unsafe_allow_html=True)
                if row["Next action"]:
                    st.caption(f":material/arrow_forward: {row['Next action']}")
                if row["Notes"]:
                    st.caption(row["Notes"])
        trail = emails[emails["Company"].str.lower() == company.lower()].sort_values("Date")
        if trail.empty:
            st.caption("No logged emails for this company.")
        else:
            timeline = trail.assign(Day=pd.to_datetime(trail["Date"]))
            dots = alt.Chart(timeline).mark_circle(size=160, color=CYAN, stroke="#060b14", strokeWidth=2).encode(
                x=alt.X("Day:T", title=None, axis=alt.Axis(format="%b %d", grid=False)),
                y=alt.Y("Kind:N", sort=PIPELINE + ["Verification", "Other"], title=None),
                tooltip=[alt.Tooltip("Day:T", format="%a %b %d"), "Kind", "Subject"],
            ).properties(height=180)
            st.altair_chart(chart_style(dots), use_container_width=True)
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
