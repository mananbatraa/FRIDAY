#!/bin/bash
# Double-click in Finder: checks your email for job updates, then opens the dashboard.
cd "$(dirname "$0")" || exit 1
source .venv/bin/activate
python -m tracker.main
echo
echo "Opening the dashboard... (close this window or press Ctrl+C to stop it)"
streamlit run dashboard.py
