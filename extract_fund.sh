#!/usr/bin/env bash
# Download one LGPS valuation PDF, convert it, and print only the rows matching
# an employer name. Never keeps the PDF and never prints the whole document.
#
#   ./extract_fund.sh <pdf-url> <employer-regex> [context-lines]
#
#   ./extract_fund.sh \
#     https://lgpsboard.org/wp-content/uploads/2026/04/ESSX-2025-valuation-report.pdf \
#     'Essex County Council'
#
# Exit codes (use these to populate failures.json):
#   0 match found      2 fetch failed      3 not a PDF      4 no match

set -uo pipefail

URL="${1:?usage: extract_fund.sh <pdf-url> <employer-regex> [context-lines]}"
PATTERN="${2:?missing employer regex}"
CTX="${3:-2}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT     # PDF is deleted however this script exits

PDF="$TMP/report.pdf"
TXT="$TMP/report.txt"

# -f fails loudly on 4xx/5xx instead of saving the error page.
# -L follows redirects. --max-time stops a stalled fetch hanging the run.
if ! curl -fsSL --max-time 180 -o "$PDF" "$URL"; then
  echo "FETCH_FAILED $URL" >&2
  exit 2
fi

# The egress proxy returns a 403 HTML body for a blocked host. Checking the
# magic bytes catches that, plus soft-404 landing pages served with a 200.
if [ "$(head -c 4 "$PDF")" != "%PDF" ]; then
  echo "NOT_A_PDF $URL" >&2
  echo "  first bytes: $(head -c 120 "$PDF" | tr -d '\0' | tr '\n' ' ')" >&2
  exit 3
fi

PAGES="$(pdfinfo "$PDF" 2>/dev/null | awk '/^Pages/ {print $2}')"
echo "FETCHED $URL  ($(du -h "$PDF" | cut -f1), ${PAGES:-?} pages)" >&2

# -layout preserves column alignment, so one employer stays on one line.
pdftotext -layout "$PDF" "$TXT"

# Page number in the text file helps confirm you're in the Rates and
# Adjustments Certificate near the end, not a mention in the summary.
if ! grep -n -i -E -B "$CTX" -A "$CTX" -- "$PATTERN" "$TXT"; then
  echo "NO_MATCH /$PATTERN/ in $URL" >&2
  echo "  try: pdftotext -layout on this file and inspect the certificate by hand," >&2
  echo "  or widen the pattern (council names vary between valuation cycles)" >&2
  exit 4
fi
