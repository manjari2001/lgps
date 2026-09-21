#!/usr/bin/env bash
# Download one LGPS valuation PDF, convert to layout-preserved text, delete the
# PDF immediately, and leave only the .txt behind for regex extraction.
#
#   ./fetch_txt.sh <pdf-url> <out-txt-path>
#
# Exit codes: 0 ok   2 fetch failed   3 not a PDF

set -uo pipefail
URL="${1:?usage: fetch_txt.sh <pdf-url> <out-txt>}"
OUT="${2:?missing out txt path}"

PDF="$(mktemp /tmp/lgps-XXXXXX.pdf)"
trap 'rm -f "$PDF"' EXIT

if ! curl -fsSL --max-time 300 --retry 3 --retry-delay 2 -o "$PDF" "$URL"; then
  echo "FETCH_FAILED $URL" >&2; exit 2
fi
if [ "$(head -c 4 "$PDF")" != "%PDF" ]; then
  echo "NOT_A_PDF $URL first-bytes: $(head -c 80 "$PDF" | tr -d '\0' | tr '\n' ' ')" >&2
  exit 3
fi

echo "FETCHED $(du -h "$PDF" | cut -f1) $(pdfinfo "$PDF" 2>/dev/null | awk '/^Pages/{print $2}')pp $URL" >&2
pdftotext -layout "$PDF" "$OUT"
rm -f "$PDF"
wc -l "$OUT" >&2
