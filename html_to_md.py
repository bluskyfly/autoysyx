"""Convert downloaded VuePress HTML pages to clean Markdown."""
import html2text
import re
from pathlib import Path

SRC = Path("/home/curry/code/autoysyx/docs-html")
DST = Path("/home/curry/code/autoysyx/docs-md")
DST.mkdir(exist_ok=True, parents=True)

h = html2text.HTML2Text()
h.body_width = 0  # don't wrap
h.ignore_images = False
h.ignore_links = False
h.protect_links = True
h.unicode_snob = True

for html_file in SRC.rglob("*.html"):
    text = html_file.read_text(encoding="utf-8", errors="ignore")
    # Strip nav/sidebar/footer wrapper: keep only <main>...</main>
    m = re.search(r"<main[^>]*>(.+?)</main>", text, flags=re.DOTALL)
    if m:
        body = m.group(1)
    else:
        body = text
    md = h.handle(body)
    # Trim long whitespace runs
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"

    rel = html_file.relative_to(SRC)
    out_path = DST / rel.with_suffix(".md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")

count = sum(1 for _ in DST.rglob("*.md"))
print(f"Converted {count} pages to {DST}")
