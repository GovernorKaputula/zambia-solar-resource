"""Validate local HTML links, fragments, and unique accessible identifiers."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import sys

class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.ids, self.links, self.h1 = set(), [], 0
        self.path = path
        self.feed(path.read_text(encoding="utf-8"))
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            assert attrs["id"] not in self.ids, f"Duplicate ID in {self.path}: {attrs['id']}"
            self.ids.add(attrs["id"])
        if tag == "h1":
            self.h1 += 1
        for key in ["href", "src"]:
            if key in attrs:
                self.links.append(attrs[key])

root = Path(__file__).resolve().parents[1] / (sys.argv[1] if len(sys.argv)>1 else "dist")
pages = {p.resolve(): Page(p) for p in root.glob("*.html")}
count = 0
for path, page in pages.items():
    assert page.h1 == 1, f"Expected one page heading: {path}"
    for link in page.links:
        parsed = urlsplit(link)
        if parsed.scheme or parsed.netloc:
            continue
        target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
        assert target.is_file(), f"Missing target: {link} in {path}"
        if parsed.fragment:
            assert target in pages and unquote(parsed.fragment) in pages[target].ids, f"Missing fragment: {link}"
        count += 1
print(f"Verified {len(pages)} pages and {count} local links; unique IDs and valid fragments.")
