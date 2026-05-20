"""Extract embedded HTML content from VuePress SPA JS files and convert to Markdown."""
import re
import json
import html as html_lib
from pathlib import Path

ASSETS_DIR = Path("/home/curry/code/autoysyx/docs-mirror/ysyx.oscc.cc/docs/assets")
OUTPUT_DIR = Path("/home/curry/code/autoysyx/docs-extracted")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# Pass 1 — find metadata files (start with `const e=JSON.parse(`)
metadata_records = {}
for js_file in ASSETS_DIR.glob("*.html.*.js"):
    text = js_file.read_text(encoding="utf-8")
    if "JSON.parse(" not in text[:30]:
        continue
    m = re.search(r"JSON\.parse\('(.+?)'\)", text)
    if not m:
        continue
    try:
        raw = m.group(1).replace("\\'", "'").replace('\\\\', '\\')
        data = json.loads(raw)
        page_name = js_file.name.split(".html.")[0]
        metadata_records[js_file.name] = (page_name, data)
    except Exception:
        pass

# Group by `path` to find the canonical metadata per page
metadata_by_path = {}
for fname, (page_name, data) in metadata_records.items():
    path = data.get("path", "")
    metadata_by_path.setdefault(path, []).append((fname, page_name, data))


def js_to_text(content: str) -> str:
    """Decode JS unicode escapes and strip HTML tags."""
    try:
        content = bytes(content, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        pass
    content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
    content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
    content = re.sub(r"<a\s+[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"[\2](\1)", content, flags=re.DOTALL)
    content = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", content, flags=re.DOTALL)
    content = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", content, flags=re.DOTALL)
    content = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", content, flags=re.DOTALL)
    content = re.sub(r"<h4[^>]*>(.*?)</h4>", r"\n#### \1\n", content, flags=re.DOTALL)
    content = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", content, flags=re.DOTALL)
    content = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", content, flags=re.DOTALL)
    content = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", content, flags=re.DOTALL)
    content = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", content, flags=re.DOTALL)
    content = re.sub(r"<em[^>]*>(.*?)</em>", r"*\1*", content, flags=re.DOTALL)
    content = re.sub(r"<br\s*/?>", "\n", content)
    content = re.sub(r"</?div[^>]*>", "", content, flags=re.DOTALL)
    content = re.sub(r"</?span[^>]*>", "", content, flags=re.DOTALL)
    content = re.sub(r"</?ul[^>]*>", "", content, flags=re.DOTALL)
    content = re.sub(r"</?ol[^>]*>", "", content, flags=re.DOTALL)
    content = re.sub(r"<[^>]+>", "", content, flags=re.DOTALL)
    content = html_lib.unescape(content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def extract_page_content(js_path: Path) -> str | None:
    """Extract embedded HTML strings from VuePress component JS files.

    The minifier emits content via `f(`HTML`)` or `f(`HTML`, N)` where `f` is a one-letter alias
    for vue's `createStaticVNode`. Inputs are template literals (backticks) for big blocks and
    quoted strings for short ones.
    """
    text = js_path.read_text(encoding="utf-8")
    if "JSON.parse(" in text[:30]:
        return None
    candidates = []
    candidates += re.findall(r"=\w\(`((?:[^`\\]|\\.)*)`(?:,\s*\d+)?\)", text, flags=re.DOTALL)
    candidates += re.findall(r"=\w\('((?:[^'\\]|\\.)*)'(?:,\s*\d+)?\)", text, flags=re.DOTALL)
    candidates += re.findall(r"=\w\(\"((?:[^\"\\]|\\.)*)\"(?:,\s*\d+)?\)", text, flags=re.DOTALL)
    candidates = [c for c in candidates if "<" in c and ">" in c and len(c) > 50]
    if not candidates:
        return None
    candidates.sort(key=len, reverse=True)
    parts = candidates[:5]
    return "\n\n".join(js_to_text(p) for p in parts)


# Pass 2 — for each path, find a content file (a JS file with the same page_name prefix that is NOT metadata)
written = 0
errors = 0
for path, recs in sorted(metadata_by_path.items()):
    if not path or path == "/" or path.endswith("/404.html"):
        continue
    fname, page_name, data = recs[0]
    title = data.get("title", path)
    headers = data.get("headers", [])

    out_rel = path.lstrip("/")
    if out_rel.endswith("/"):
        out_rel += "index.html"
    out_rel = out_rel.replace(".html", ".md")
    out_path = OUTPUT_DIR / out_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)

    body_parts = []
    for content_js in ASSETS_DIR.glob(f"{page_name}.html.*.js"):
        if content_js.name in metadata_records:
            continue
        body = extract_page_content(content_js)
        if body and len(body) > 100:
            body_parts.append((content_js.name, body))
    body_parts.sort(key=lambda x: len(x[1]), reverse=True)

    if not body_parts:
        out_path.write_text(f"# {title}\n\n*[no content extracted]*\n\n_path: {path}_\n", encoding="utf-8")
        errors += 1
        continue

    header_lines = "\n".join(
        f"- {'  ' * (h.get('level', 2) - 2)}[{h.get('title', '')}](#{h.get('slug', '')})"
        for h in headers
    )
    out_path.write_text(
        f"# {title}\n\n_source: https://ysyx.oscc.cc{path}_\n\n"
        + (f"## Outline\n{header_lines}\n\n" if header_lines else "")
        + "---\n\n"
        + body_parts[0][1]
        + "\n",
        encoding="utf-8",
    )
    written += 1

print(f"Wrote {written} pages, {errors} pages had no content extracted")
print(f"Output dir: {OUTPUT_DIR}")
