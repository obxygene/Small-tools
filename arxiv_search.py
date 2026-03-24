# arxiv_search.py — keyword-based arXiv search with markdown output
#
# Usage:
#   python3 arxiv_search.py "flat band topology" -n 10
#   python3 arxiv_search.py "quantum transport disorder" -n 5 -o results.md
#   python3 arxiv_search.py "superconductivity moiré" -n 20 --cat cond-mat.supr-con

import argparse
import time
import xml.etree.ElementTree as ET
from typing import List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── HTTP session with retries ──────────────────────────────────────
SESSION = requests.Session()
_RETRY = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET",),
    respect_retry_after_header=True,
)
SESSION.mount("https://", HTTPAdapter(max_retries=_RETRY))
SESSION.mount("http://",  HTTPAdapter(max_retries=_RETRY))
SESSION.headers.update({"User-Agent": "arxiv-search/1.0"})

ARXIV_API = "http://export.arxiv.org/api/query"
NS = {
    "atom":    "http://www.w3.org/2005/Atom",
    "arxiv":   "http://arxiv.org/schemas/atom",
}


def build_query(keywords: str, category: str | None) -> str:
    """Combine keyword and optional category filter into arXiv search_query."""
    # Wrap phrase in quotes for exact matching, otherwise use AND logic
    kw_query = f'all:"{keywords}"' if " " in keywords else f"all:{keywords}"
    if category:
        return f"({kw_query}) AND cat:{category}"
    return kw_query


def fetch_papers(keywords: str, n: int, category: str | None) -> List[dict]:
    """Query arXiv API and return up to n matching papers."""
    params = {
        "search_query": build_query(keywords, category),
        "sortBy":       "relevance",
        "sortOrder":    "descending",
        "max_results":  n,
        "start":        0,
    }

    print(f"Searching arXiv for: {params['search_query']!r} (top {n}) ...")
    try:
        resp = SESSION.get(ARXIV_API, params=params, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] {e}")
        return []

    root = ET.fromstring(resp.text)
    papers = []

    for entry in root.findall("atom:entry", NS):
        arxiv_id  = (entry.findtext("atom:id", default="", namespaces=NS) or "").strip()
        title     = " ".join((entry.findtext("atom:title",   default="", namespaces=NS) or "").split())
        abstract  = " ".join((entry.findtext("atom:summary", default="", namespaces=NS) or "").split())
        published = (entry.findtext("atom:published", default="", namespaces=NS) or "")[:10]  # YYYY-MM-DD

        authors = [
            a.findtext("atom:name", default="", namespaces=NS)
            for a in entry.findall("atom:author", NS)
        ]
        cats = [t.get("term", "") for t in entry.findall("atom:category", NS)]

        papers.append({
            "id":       arxiv_id,
            "title":    title,
            "abstract": abstract,
            "authors":  authors,
            "cats":     cats,
            "date":     published,
        })

    return papers


def to_markdown(papers: List[dict], keywords: str) -> str:
    """Render results as GitHub-flavoured markdown."""
    lines = [
        f"# arXiv Search Results",
        f"",
        f"**Query:** `{keywords}`  ",
        f"**Papers found:** {len(papers)}",
        f"",
        "---",
        "",
    ]

    for i, p in enumerate(papers, 1):
        # Authors: show first 5, then et al.
        if len(p["authors"]) <= 5:
            authors_str = ", ".join(p["authors"])
        else:
            authors_str = ", ".join(p["authors"][:5]) + f" *et al.* (+{len(p['authors'])-5} more)"

        cats_str = " · ".join(p["cats"]) if p["cats"] else "—"

        lines += [
            f"## {i}. [{p['title']}]({p['id']})",
            f"",
            f"**Authors:** {authors_str}  ",
            f"**Date:** {p['date']}  ",
            f"**Categories:** {cats_str}  ",
            f"**arXiv:** <{p['id']}>",
            f"",
            f"> {p['abstract']}",
            f"",
            "---",
            "",
        ]

    if not papers:
        lines.append("*No papers found for this query.*")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Search arXiv by keywords and output a markdown list of papers."
    )
    parser.add_argument(
        "keywords",
        help='Search keywords, e.g. "flat band topology" or "quantum transport"',
    )
    parser.add_argument(
        "-n", "--num",
        type=int,
        default=10,
        metavar="N",
        help="Number of papers to return (default: 10)",
    )
    parser.add_argument(
        "--cat",
        default=None,
        metavar="CATEGORY",
        help='Restrict to an arXiv category, e.g. "cond-mat.mes-hall"',
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="FILE",
        help="Write markdown to this file instead of printing to stdout",
    )
    args = parser.parse_args()

    papers = fetch_papers(args.keywords, args.num, args.cat)
    md = to_markdown(papers, args.keywords)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Results written to {args.output}")
    else:
        print("\n" + md)


if __name__ == "__main__":
    main()
