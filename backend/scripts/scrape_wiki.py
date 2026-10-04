# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.28", "beautifulsoup4>=4.12"]
# ///
"""Build the base knowledge base from The Hunger Games Wiki (Fandom) and Wikipedia.

Both sites publish their text under CC BY-SA, so it can be reused with attribution.
Every generated file keeps its source URL and license in a front-matter block, and the
agent shows that URL as the source of its answers.

Usage (from the backend folder; uv installs httpx + beautifulsoup4 on the fly):
    uv run scripts/scrape_wiki.py --out ../data/wiki
    uv run scripts/scrape_wiki.py --out ../data/wiki --category "Characters" --limit 200
"""

import argparse
import re
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

FANDOM_API = "https://thehungergames.fandom.com/api.php"
FANDOM_PAGE = "https://thehungergames.fandom.com/wiki/"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_PAGE = "https://en.wikipedia.org/wiki/"
HEADERS = {"User-Agent": "HungerGamesAgent/1.0 (university project; RAG knowledge base)"}

FANDOM_PAGES = [
    # Books
    "The Hunger Games (novel)", "Catching Fire (novel)", "Mockingjay (novel)",
    "The Ballad of Songbirds and Snakes", "Sunrise on the Reaping",
    # Main characters
    "Katniss Everdeen", "Peeta Mellark", "Gale Hawthorne", "Primrose Everdeen",
    "Haymitch Abernathy", "Effie Trinket", "Cinna", "Coriolanus Snow", "Alma Coin",
    "Finnick Odair", "Johanna Mason", "Beetee Latier", "Wiress", "Mags", "Annie Cresta",
    "Plutarch Heavensbee", "Seneca Crane", "Caesar Flickerman", "Madge Undersee",
    "Mrs. Everdeen", "Boggs", "Cressida", "Castor", "Pollux", "Paylor", "President Snow",
    "Lucy Gray Baird", "Sejanus Plinth", "Tigris", "Volumnia Gaul", "Casca Highbottom",
    "Maysilee Donner", "Lenore Dove Baird",
    # 74th / 75th Games tributes
    "Rue", "Thresh", "Cato", "Clove", "Glimmer", "Marvel", "Foxface",
    "Enobaria", "Brutus", "Gloss", "Cashmere", "Chaff", "Seeder", "Blight",
    # World
    "Panem", "The Capitol", "District 1", "District 2", "District 3", "District 4",
    "District 5", "District 6", "District 7", "District 8", "District 9", "District 10",
    "District 11", "District 12", "District 13", "Victors Village", "The Seam",
    "Mockingjay (bird)", "Jabberjay", "Tracker jacker", "Nightlock", "Muttation",
    "Tessera", "Reaping", "Avox", "Peacekeepers", "Gamemakers", "Head Gamemaker",
    # Events
    "Hunger Games", "Quarter Quell", "10th Hunger Games", "50th Hunger Games",
    "74th Hunger Games", "75th Hunger Games", "Dark Days", "Second Rebellion",
    "Treaty of Treason", "Victory Tour", "Mockingjay pin",
]

WIKIPEDIA_PAGES = [
    "The Hunger Games", "The Hunger Games (novel)", "Catching Fire", "Mockingjay",
    "The Ballad of Songbirds and Snakes", "Sunrise on the Reaping",
    "List of The Hunger Games characters", "Suzanne Collins",
]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def clean(text: str) -> str:
    text = re.sub(r"\[\d+\]|\[citation needed\]|\[edit\]", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def html_to_markdown(html: str) -> str:
    """Keep headings, paragraphs, lists, infobox facts and simple tables."""
    soup = BeautifulSoup(html, "html.parser")
    for selector in [
        "script", "style", "sup.reference", ".reference", ".mw-editsection", ".navbox",
        ".toc", "#toc", ".gallery", ".wikia-gallery", "figure", ".thumb", ".hatnote",
        ".mw-references-wrap", ".references", ".reflist", ".noprint", ".metadata",
        ".ambox", ".dablink", "table.navbox",
    ]:
        for tag in soup.select(selector):
            tag.decompose()

    lines: list[str] = []

    # Fandom infobox -> "Label: value" lines (district, age, family...)
    for box in soup.select("aside.portable-infobox"):
        facts = []
        for item in box.select(".pi-data"):
            label = item.select_one(".pi-data-label")
            value = item.select_one(".pi-data-value")
            if label and value:
                facts.append(f"- {clean(label.get_text(' '))}: {clean(value.get_text(', '))}")
        if facts:
            lines += ["## Key facts", *facts, ""]
        box.decompose()

    root = soup.select_one(".mw-parser-output") or soup
    for el in root.find_all(["h2", "h3", "h4", "p", "ul", "ol", "table"], recursive=True):
        if el.find_parent(["table", "ul", "ol"]) and el.name != "table":
            continue  # nested; handled by its parent
        if el.name in {"h2", "h3", "h4"}:
            title = clean(el.get_text(" "))
            if title.lower() in {"references", "notes", "external links", "see also", "gallery",
                                 "navigation", "trivia", "behind the scenes", "appearances"}:
                break
            lines += ["", f"{'#' * int(el.name[1])} {title}"]
        elif el.name == "p":
            text = clean(el.get_text(" "))
            if text:
                lines += [text, ""]
        elif el.name in {"ul", "ol"}:
            for li in el.find_all("li", recursive=False):
                text = clean(li.get_text(" "))
                if text:
                    lines.append(f"- {text}")
            lines.append("")
        elif el.name == "table" and "infobox" not in " ".join(el.get("class", [])):
            for row in el.find_all("tr"):
                cells = [clean(c.get_text(" ")) for c in row.find_all(["th", "td"])]
                if any(cells):
                    lines.append(" | ".join(cells))
            lines.append("")

    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def fetch_page(client: httpx.Client, api: str, title: str) -> tuple[str, str] | None:
    params = {
        "action": "parse", "page": title, "prop": "text", "format": "json",
        "redirects": 1, "disableeditsection": 1, "formatversion": 2,
    }
    data = client.get(api, params=params).json()
    if "error" in data:
        # Try a search if the exact title does not exist.
        found = client.get(
            api, params={"action": "query", "list": "search", "srsearch": title, "format": "json", "srlimit": 1}
        ).json().get("query", {}).get("search", [])
        if not found:
            return None
        params["page"] = found[0]["title"]
        data = client.get(api, params=params).json()
        if "error" in data:
            return None
    return data["parse"]["title"], data["parse"]["text"]


def category_members(client: httpx.Client, category: str, limit: int) -> list[str]:
    titles, cont = [], {}
    while len(titles) < limit:
        data = client.get(
            FANDOM_API,
            params={
                "action": "query", "list": "categorymembers", "cmtitle": f"Category:{category}",
                "cmlimit": 50, "cmnamespace": 0, "format": "json", **cont,
            },
        ).json()
        titles += [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
        if "continue" not in data:
            break
        cont = data["continue"]
    return titles[:limit]


def save(out: Path, site: str, title: str, url: str, license_name: str, body: str) -> Path:
    path = out / f"{site}-{slugify(title)}.md"
    path.write_text(
        f"---\ntitle: {title} ({'Hunger Games Wiki' if site == 'fandom' else 'Wikipedia'})\n"
        f"source_url: {url}\nlicense: {license_name}\n---\n# {title}\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="../data/wiki")
    parser.add_argument("--category", action="append", default=[], help="Extra Fandom category to include")
    parser.add_argument("--limit", type=int, default=100, help="Max pages per extra category")
    parser.add_argument("--min-chars", type=int, default=400, help="Skip stubs shorter than this")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        fandom_titles = list(dict.fromkeys(FANDOM_PAGES))
        for category in args.category:
            fandom_titles += [t for t in category_members(client, category, args.limit) if t not in fandom_titles]

        jobs = [("fandom", FANDOM_API, FANDOM_PAGE, "CC BY-SA 3.0", t) for t in fandom_titles]
        jobs += [("wikipedia", WIKIPEDIA_API, WIKIPEDIA_PAGE, "CC BY-SA 4.0", t) for t in WIKIPEDIA_PAGES]

        saved = skipped = 0
        for site, api, base, license_name, title in jobs:
            try:
                result = fetch_page(client, api, title)
            except httpx.HTTPError as exc:
                print(f"  ! {site}: {title}: {exc}")
                continue
            if result is None:
                print(f"  - {site}: not found: {title}")
                skipped += 1
                continue
            real_title, html = result
            body = html_to_markdown(html)
            if len(body) < args.min_chars:
                print(f"  - {site}: too short: {real_title}")
                skipped += 1
                continue
            url = base + real_title.replace(" ", "_")
            path = save(out, site, real_title, url, license_name, body)
            saved += 1
            print(f"  + {path.name} ({len(body):,} chars)")
            time.sleep(0.3)  # be polite with the servers

    print(f"\nDone: {saved} pages saved in {out}, {skipped} skipped.")


if __name__ == "__main__":
    main()
