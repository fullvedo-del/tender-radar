#!/usr/bin/env bash
# ESJN (Makedonija) - preuzmi i gurni u repozitorij. Pokrece se na uvijek-upaljenom
# racunaru (npr. Raspberry Pi) na OBICNOJ vezi, jednom dnevno, iz crona.
# Prije prvog pokretanja:
#   1) git clone https://github.com/fullvedo-del/tender-radar.git ~/tender-radar
#   2) izvezi GH_TOKEN (GitHub token, pravo contents: write) i po potrebi REPO_DIR.
# Token NIJE u kodu; cita se iz okruzenja.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/tender-radar}"
: "${GH_TOKEN:?GH_TOKEN nije postavljen}"

cd "$REPO_DIR"
git pull --rebase --quiet
python3 tools/esjn_fetch.py data/esjn_raw.json
git add data/esjn_raw.json
if git diff --cached --quiet; then echo "Nema promjena"; exit 0; fi
git commit -m "ESJN: makedonske nabavke (auto $(date -u +%F))"
git pull --rebase --quiet
git push "https://${GH_TOKEN}@github.com/fullvedo-del/tender-radar.git" HEAD:main
