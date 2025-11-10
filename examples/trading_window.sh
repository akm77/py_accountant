#!/usr/bin/env bash
set -euo pipefail

# Example: export trading balance window to JSON
poetry run python -m presentation.cli.main trading:detailed --base USD --start "$1" --end "$2" --json > trading_balance_window.json
echo "Saved trading balance to trading_balance_window.json"

