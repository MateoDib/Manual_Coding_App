#!/bin/zsh
set -eu
APP_DIR="${0:A:h}"
export PYTHONDONTWRITEBYTECODE=1
APP_PYTHON="$APP_DIR/.venv/bin/python"
if [[ ! -x "$APP_PYTHON" ]]; then
  print "Lancez d’abord Installer.command dans ce dossier."
  read -r "?Appuyez sur Entrée pour fermer."
  exit 1
fi
"$APP_PYTHON" -B "$APP_DIR/scripts/launch.py" coding "$@"
