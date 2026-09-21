#!/usr/bin/env bash
# Fetch one fund's two reports as text and print only certificate-table lines
# matching an employer regex. Page headers/footers repeat the fund name on
# every page, so they are filtered out; -r shows raw matches instead.
#
#   ./probe.sh [-r] <Fund name> <employer-regex>
#   ./probe.sh --clean <Fund name>
#
# Leaves /tmp/<slug>-2022.txt and /tmp/<slug>-2025.txt for follow-up greps.

set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"

if [ "${1:-}" = "--clean" ]; then
  slug="$(echo "${2:?}" | tr 'A-Z ' 'a-z-')"; rm -f "/tmp/$slug"-20*.txt; exit 0
fi

RAW=0
if [ "${1:-}" = "-r" ]; then RAW=1; shift; fi

FUND="${1:?usage: probe.sh [-r] <fund> <regex>}"
PATTERN="${2:?missing employer regex}"
SLUG="$(echo "$FUND" | tr 'A-Z ' 'a-z-')"

# Running heads/feet and contents-page dot leaders, not certificate rows.
FURNITURE='[Aa]ctuarial valuation as at|Pension Fund( \||$)|valuation report|\.\.\.\.\.\.|^ *(PUBLIC|Version )|[0-9]+ of [0-9]+$|is addressed to'

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
  echo "== $YEAR =="
  if [ "$RAW" = 1 ]; then
    grep -n -i -E -- "$PATTERN" "$TXT" | grep -v -E "$FURNITURE" | head -40
  else
    # A certificate row carries the employer name and at least one rate.
    grep -n -i -E -- "$PATTERN" "$TXT" | grep -v -E "$FURNITURE" \
      | grep -E '[0-9]+\.[0-9] *%|£[0-9]' | head -40
  fi
done
