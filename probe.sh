#!/usr/bin/env bash
# Fetch one fund's two reports as text and print only the lines matching an
# employer regex, plus the certificate table header that gives column order.
#
#   ./probe.sh <Fund name> <employer-regex>
#
# Leaves /tmp/<slug>-2022.txt and /tmp/<slug>-2025.txt for follow-up greps;
# run ./probe.sh --clean <Fund name> to remove them.

set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"

if [ "${1:-}" = "--clean" ]; then
  slug="$(echo "${2:?}" | tr 'A-Z ' 'a-z-')"; rm -f "/tmp/$slug"-20*.txt; exit 0
fi

FUND="${1:?usage: probe.sh <fund> <regex>}"
PATTERN="${2:?missing employer regex}"
SLUG="$(echo "$FUND" | tr 'A-Z ' 'a-z-')"

for YEAR in 2022 2025; do
  TXT="/tmp/$SLUG-$YEAR.txt"
  if [ ! -s "$TXT" ]; then
    URL="$(python3 -c "
import csv,sys
for r in csv.DictReader(open('lgps_fund_report_urls.csv')):
    if r['Fund']==sys.argv[1]: print(r['URL_'+sys.argv[2]]); break
" "$FUND" "$YEAR")"
    [ -n "$URL" ] || { echo "== $YEAR NO_URL"; continue; }
    ./fetch_txt.sh "$URL" "$TXT" 2>&1 | sed "s/^/  [$YEAR] /"
    [ -s "$TXT" ] || { echo "== $YEAR FETCH_OR_CONVERT_FAILED"; continue; }
  fi
  echo "== $YEAR header (column order) =="
  grep -n -i -m2 -A4 'Primary *$\|Primary rate\|Primary  *rate' "$TXT" | head -24
  echo "== $YEAR matches =="
  grep -n -i -E -- "$PATTERN" "$TXT" | head -40
done
