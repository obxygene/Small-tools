# arxiv_search.py — keyword-based arXiv search with markdown output
#
# Usage:
#   python3 arxiv_search.py
#
# Edit the USER CONFIGURATION section below, then run.

import xml.etree.ElementTree as ET
import os
from datetime import datetime
from typing import List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── USER CONFIGURATION ─────────────────────────────────────────────
KEYWORDS = [
    "flat band topology",
    "quantum transport disorder",
    "moiré superconductivity",
]
NUM      = 10    # number of papers to return
CATEGORY = None  # set to a category string below, or leave None to search all
# ── Available arXiv physics categories ────────────────────────────
# Condensed Matter
#   "cond-mat.dis-nn"    # Disordered Systems and Neural Networks
#   "cond-mat.mes-hall"  # Mesoscale and Nanoscale Physics
#   "cond-mat.mtrl-sci"  # Materials Science
#   "cond-mat.other"     # Other Condensed Matter
#   "cond-mat.quant-gas" # Quantum Gases
#   "cond-mat.soft"      # Soft Condensed Matter
#   "cond-mat.stat-mech" # Statistical Mechanics
#   "cond-mat.str-el"    # Strongly Correlated Electrons
#   "cond-mat.supr-con"  # Superconductivity
#
# Quantum Physics & Relativity
#   "quant-ph"           # Quantum Physics
#   "gr-qc"              # General Relativity and Quantum Cosmology
#   "math-ph"            # Mathematical Physics
#
# High Energy Physics
#   "hep-ex"             # Experiment
#   "hep-lat"            # Lattice
#   "hep-ph"             # Phenomenology
#   "hep-th"             # Theory
#
# Nuclear Physics
#   "nucl-ex"            # Nuclear Experiment
#   "nucl-th"            # Nuclear Theory
#
# Astrophysics
#   "astro-ph.CO"        # Cosmology and Nongalactic Astrophysics
#   "astro-ph.EP"        # Earth and Planetary Astrophysics
#   "astro-ph.GA"        # Astrophysics of Galaxies
#   "astro-ph.HE"        # High Energy Astrophysical Phenomena
#   "astro-ph.IM"        # Instrumentation and Methods
#   "astro-ph.SR"        # Solar and Stellar Astrophysics
#
# General Physics
#   "physics.acc-ph"     # Accelerator Physics
#   "physics.ao-ph"      # Atmospheric and Oceanic Physics
#   "physics.app-ph"     # Applied Physics
#   "physics.atom-ph"    # Atomic Physics
#   "physics.atm-clus"   # Atomic and Molecular Clusters
#   "physics.bio-ph"     # Biological Physics
#   "physics.chem-ph"    # Chemical Physics
#   "physics.class-ph"   # Classical Physics
#   "physics.comp-ph"    # Computational Physics
#   "physics.data-an"    # Data Analysis and Statistics
#   "physics.flu-dyn"    # Fluid Dynamics
#   "physics.gen-ph"     # General Physics
#   "physics.geo-ph"     # Geophysics
#   "physics.ins-det"    # Instrumentation and Detectors
#   "physics.med-ph"     # Medical Physics
#   "physics.optics"     # Optics
#   "physics.plasm-ph"   # Plasma Physics
#   "physics.soc-ph"     # Physics and Society
#   "physics.space-ph"   # Space Physics
#
# Nonlinear Sciences
#   "nlin.AO"            # Adaptation and Self-Organizing Systems
#   "nlin.CD"            # Chaotic Dynamics
#   "nlin.CG"            # Cellular Automata and Lattice Gases
#   "nlin.PS"            # Pattern Formation and Solitons
#   "nlin.SI"            # Exactly Solvable and Integrable Systems
# ──────────────────────────────────────────────────────────────────
# ───────────────────────────────────────────────────────────────────

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


def build_query(keywords: List[str], category: str | None) -> str:
    """AND all keywords together; wrap multi-word phrases in quotes."""
    parts = [f'all:"{kw}"' if " " in kw else f"all:{kw}" for kw in keywords]
    kw_query = " AND ".join(parts)
    if category:
        return f"({kw_query}) AND cat:{category}"
    return kw_query


def fetch_papers(keywords: List[str], n: int, category: str | None) -> List[dict]:
    """Query arXiv API and return up to n matching papers."""
    params = {
        "search_query": build_query(keywords, category),
        "sortBy":       "submittedDate",
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


def paper_block(i: int, p: dict) -> List[str]:
    if len(p["authors"]) <= 5:
        authors_str = ", ".join(p["authors"])
    else:
        authors_str = ", ".join(p["authors"][:5]) + f" *et al.* (+{len(p['authors'])-5} more)"
    cats_str = " · ".join(p["cats"]) if p["cats"] else "—"
    return [
        f"### {i}. [{p['title']}]({p['id']})",
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


def to_markdown(papers: List[dict], keywords: List[str], query: str) -> str:
    """Render results as GitHub-flavoured markdown."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "# arXiv Search Results",
        "",
        f"**Date:** {date_str}  ",
        f"**Query:** `{query}`  ",
        f"**Papers found:** {len(papers)}",
        "",
        "---",
        "",
    ]
    if papers:
        for i, p in enumerate(papers, 1):
            lines += paper_block(i, p)
    else:
        lines.append("*No papers found for this query.*")
    return "\n".join(lines)


def main():
    query  = build_query(KEYWORDS, CATEGORY)
    papers = fetch_papers(KEYWORDS, NUM, CATEGORY)
    md     = to_markdown(papers, KEYWORDS, query)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    date_str   = datetime.now().strftime("%Y%m%d")
    filename   = f"arxiv_search_{date_str}.md"
    out_path   = os.path.join(script_dir, filename)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Results written to {out_path}")


if __name__ == "__main__":
    main()
