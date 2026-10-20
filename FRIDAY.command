#!/bin/bash
# Double-click in Finder: checks your email for job updates, then opens the dashboard.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "First run: setting things up (takes a minute)..."
  python3 -m venv .venv || exit 1
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -r requirements.txt || exit 1
  [ -f .env ] || cp .env.example .env
fi
source .venv/bin/activate
if [ ! -f credentials.json ]; then
  echo "credentials.json is missing. Put it in this folder ($(pwd)) and double-click FRIDAY.command again."
  exit 1
fi
python -m tracker.main
echo
echo "Opening the dashboard... (close this window or press Ctrl+C to stop it)"
streamlit run dashboard.py
