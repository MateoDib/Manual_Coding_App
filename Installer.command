#!/bin/zsh
set -eu
APP_DIR="${0:A:h}"
export PYTHONDONTWRITEBYTECODE=1
if ! command -v python3 >/dev/null; then
  print "Installez Python 3.11 à 3.13 depuis python.org, puis relancez ce fichier."
  exit 1
fi
python3 -B -c 'import sys; assert (3,11) <= sys.version_info[:2] <= (3,13), "Python 3.11 à 3.13 requis"'
python3 -B -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -B -m pip install -r "$APP_DIR/requirements.txt"
print "Installation terminée. Ouvrez Lancer_Codage.command."
