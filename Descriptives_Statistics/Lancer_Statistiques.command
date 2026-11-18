#!/bin/zsh
set -eu
STATS_DIR="${0:A:h}"
exec "$STATS_DIR/../Lancer_Statistiques.command" "$@"
