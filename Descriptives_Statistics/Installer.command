#!/bin/zsh
set -eu
STATS_DIR="${0:A:h}"
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m venv "$STATS_DIR/.venv"
"$STATS_DIR/.venv/bin/python" -B -m pip install -r "$STATS_DIR/requirements.txt"
print "Installation terminée. Ouvrez Lancer_Statistiques.command."
