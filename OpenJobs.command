#!/bin/bash
# Double-click in Finder: opens new-grad Software Engineering postings in browser
# tabs, a batch at a time, for Tsenta to apply to. Edit OPTIONS to change the defaults
# (run `python3 -m tracker.open_jobs --help` to see them all).
OPTIONS=(--batch 10)
cd "$(dirname "$0")" || exit 1
python3 -m tracker.open_jobs "${OPTIONS[@]}" "$@"
echo
read -r -p "Press Enter to close this window."
