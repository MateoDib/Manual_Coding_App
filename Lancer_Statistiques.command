#!/bin/zsh
set -eu
APP_DIR="${0:A:h}"
export PYTHONDONTWRITEBYTECODE=1
STATS_PYTHON="$APP_DIR/Descriptives_Statistics/.venv/bin/python"
if [[ ! -x "$STATS_PYTHON" ]]; then STATS_PYTHON="$(command -v python3)"; fi
if ! "$STATS_PYTHON" -B -c 'import pandas, networkx, openpyxl, matplotlib' >/dev/null 2>&1; then
  print "Lancez Installer.command dans Descriptives_Statistics, puis réessayez."
  read -r "?Appuyez sur Entrée pour fermer."
  exit 1
fi
"$STATS_PYTHON" -B "$APP_DIR/scripts/statistics.py" "$@"
