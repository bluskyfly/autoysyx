#!/bin/bash
# Fetch all v24.07 and ics-pa Chinese pages in parallel via curl.
set -u

OUT=/home/curry/code/autoysyx/docs-html
mkdir -p "$OUT"

# List of URLs to fetch (Chinese, v24.07 + ics-pa core).
urls=()
for stage in f e d c b a; do
    for n in $(seq 1 7); do
        urls+=("/2407/$stage/$n.html")
    done
done
urls+=("/2407/")

for n in 0.1 0.2 0.3 0.4 0.5 0.6 \
         1.1 1.2 1.3 1.4 1.5 1.6 1.7 \
         2.1 2.2 2.3 2.4 2.5 \
         3.1 3.2 3.3 3.4 3.5 \
         4.1 4.2 4.3 4.4 4.5 \
         5.1 5.2 5.3 \
         PA0 PA1 PA2 PA3 PA4 PA5 \
         FAQ why exec linux git man i386-intro nemu-isa-api SUMMARY changelog feedback; do
    urls+=("/ics-pa/$n.html")
done
urls+=("/ics-pa/")

# Also schedule/faq/about pages.
urls+=("/2205/" "/2306/")

printf "Total URLs: %d\n" "${#urls[@]}"

fetch_one() {
    local path="$1"
    local out_file="$OUT${path%/}"
    [[ "$path" == */ ]] && out_file="$out_file/index.html"
    mkdir -p "$(dirname "$out_file")"
    if [[ -f "$out_file" ]] && [[ $(stat -c%s "$out_file") -gt 10000 ]]; then
        return 0  # already fetched
    fi
    curl -fsSL --max-time 30 "https://ysyx.oscc.cc/docs${path}" -o "$out_file" 2>/dev/null
    return $?
}

export -f fetch_one
export OUT

printf '%s\n' "${urls[@]}" | xargs -P 8 -I {} bash -c 'fetch_one "$@" && echo "OK: $@" || echo "FAIL: $@"' _ {}

echo "---"
echo "Files written: $(find "$OUT" -type f -name "*.html" | wc -l)"
echo "Total size:    $(du -sh "$OUT" | cut -f1)"
