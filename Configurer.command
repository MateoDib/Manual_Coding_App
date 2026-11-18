#!/bin/zsh
set -eu
APP_DIR="${0:A:h}"
export PYTHONDONTWRITEBYTECODE=1
SETUP_PYTHON="$APP_DIR/.venv/bin/python"
if [[ ! -x "$SETUP_PYTHON" ]]; then SETUP_PYTHON="$(command -v python3 || true)"; fi
if [[ -z "$SETUP_PYTHON" ]]; then
  print "Installez Python 3.11 à 3.13 depuis python.org, puis relancez Configurer.command."
  read -r "?Appuyez sur Entrée pour fermer."
  exit 1
fi
"$SETUP_PYTHON" -B "$APP_DIR/scripts/configure.py" "$@"
