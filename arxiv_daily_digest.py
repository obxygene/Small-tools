



# python3 arxiv_daily_digest.py              # send email
# python3 arxiv_daily_digest.py --dry-run    # print to terminal only
# python3 arxiv_daily_digest.py --date 2025-03-10   # fetch a specific date
#
# SMTP setup (NetEase 163):
#   1. Log in to 163.com → Settings → POP3/SMTP/IMAP → enable SMTP service.
#   2. Set an "authorization code" (授权码) — this is NOT your login password.
#   3. Fill SMTP_USER (your full 163 address) and SMTP_PASS (authorization code) below.
#   4. 163 uses SSL on port 465 (smtplib.SMTP_SSL).

import argparse
import os
import smtplib
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
from typing import List, Set

# ── USER CONFIGURATION ─────────────────────────────────────────────
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "your_email@example.com")  # <-- fill in or set env var

# SMTP settings — NetEase 163 (use env vars if present, else fill inline defaults)
SMTP_HOST    = os.getenv("SMTP_HOST",    "smtp.163.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "465"))        # 465 = SSL
SMTP_USER    = os.getenv("SMTP_USER",    "your email")  # <-- fill in
SMTP_PASS    = os.getenv("SMTP_PASS",    "your code")        # <-- authorization code (授权码), NOT login password
SENDER_EMAIL = os.getenv("SENDER_EMAIL", SMTP_USER)

# cond-mat subcategories to fetch (comment out unwanted ones)
CATEGORIES = [
    "cond-mat.mes-hall",   # Mesoscale & Nanoscale Physics
    "cond-mat.str-el",     # Strongly Correlated Electrons
    "cond-mat.supr-con",   # Superconductivity
    "cond-mat.quant-gas",  # Quantum Gases
    "cond-mat.stat-mech",  # Statistical Mechanics
    "cond-mat.mtrl-sci",   # Materials Science
    # # "cond-mat.soft",       # Soft Condensed Matter
    "cond-mat.dis-nn",     # Disordered Systems & Neural Networks
]

# Keywords to filter by (case-insensitive match in title OR abstract).
# Set to [] to receive ALL new submissions without any keyword filtering.
KEYWORDS = [
    "transport",
    # "quantum Hall",
    # "Chern",
    "Flat band",
    "Disorder",
]
# ───────────────────────────────────────────────────────────────────

ARXIV_API_URL = "http://export.arxiv.org/api/query"
NS = {
    "atom":    "http://www.w3.org/2005/Atom",
    "arxiv":   "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}

# requests Session with retries/backoff to handle transient network issues
SESSION = requests.Session()
_RETRY_STRAT = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET",),
    respect_retry_after_header=True,
    raise_on_status=False,
)
SESSION.mount("https://", HTTPAdapter(max_retries=_RETRY_STRAT))
SESSION.mount("http://", HTTPAdapter(max_retries=_RETRY_STRAT))
SESSION.headers.update({"User-Agent": "arxiv-digest/1.0"})


def fetch_papers_for_category(category: str, target_date: date, max_results: int = 200) -> List[dict]:
    """Fetch new arXiv submissions for one category on target_date."""
    params = {
        "search_query": f"cat:{category}",
        "sortBy":        "submittedDate",
        "sortOrder":     "descending",
        "max_results":   max_results,
        "start":         0,
    }
    try:
        resp = SESSION.get(ARXIV_API_URL, params=params, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [ERROR] fetching {category}: {e}")
        return []

    root = ET.fromstring(resp.text)
    papers = []

    for entry in root.findall("atom:entry", NS):
        # published date: "2025-03-10T00:00:00Z"
        published_text = entry.findtext("atom:published", default="", namespaces=NS)
        try:
            published = datetime.strptime(published_text, "%Y-%m-%dT%H:%M:%SZ").date()
        except ValueError:
            continue

        if published != target_date:
            # arXiv API returns newest first; once we're past target date we can stop
            if published < target_date:
                break
            continue

        arxiv_id = entry.findtext("atom:id", default="", namespaces=NS).strip()
        title    = " ".join((entry.findtext("atom:title", default="", namespaces=NS) or "").split())
        abstract = " ".join((entry.findtext("atom:summary", default="", namespaces=NS) or "").split())

        authors = [
            a.findtext("atom:name", default="", namespaces=NS)
            for a in entry.findall("atom:author", NS)
        ]

        cats = [
            t.get("term", "")
            for t in entry.findall("atom:category", NS)
        ]

        papers.append({
            "id":       arxiv_id,
            "title":    title,
            "abstract": abstract,
            "authors":  authors,
            "cats":     cats,
            "date":     published,
        })

    return papers


def fetch_all_papers(target_date: date) -> List[dict]:
    """Fetch, deduplicate, and optionally keyword-filter papers across all categories."""
    seen_ids: Set[str] = set()
    all_papers: List[dict] = []

    for cat in CATEGORIES:
        print(f"  Fetching {cat} ...")
        # polite delay between category requests to avoid hitting arXiv rate limits
        time.sleep(2)
        for paper in fetch_papers_for_category(cat, target_date):
            if paper["id"] not in seen_ids:
                seen_ids.add(paper["id"])
                all_papers.append(paper)

    if KEYWORDS:
        kw_lower = [k.lower() for k in KEYWORDS]
        def matches(p):
            text = (p["title"] + " " + p["abstract"]).lower()
            return any(kw in text for kw in kw_lower)
        all_papers = [p for p in all_papers if matches(p)]

    return all_papers


# ── HTML builder ──────────────────────────────────────────────────

def _cat_badge(cat: str) -> str:
    return (
        f'<span style="display:inline-block;background:#e8f4f8;border:1px solid #b0d4e8;'
        f'border-radius:3px;padding:1px 5px;font-size:11px;margin:1px;">{cat}</span>'
    )


def build_html(papers: List[dict], target_date: date) -> str:
    date_str    = target_date.strftime("%Y-%m-%d")
    kw_display  = ", ".join(KEYWORDS) if KEYWORDS else "none (all papers)"
    cat_display = ", ".join(CATEGORIES)

    rows = []
    for i, p in enumerate(papers, 1):
        authors_str = "; ".join(p["authors"][:6])
        if len(p["authors"]) > 6:
            authors_str += f" … (+{len(p['authors'])-6} more)"
        badges = " ".join(_cat_badge(c) for c in p["cats"])
        rows.append(f"""
        <div style="margin-bottom:24px;padding:14px 16px;background:#fafafa;
                    border-left:4px solid #1a73e8;border-radius:4px;">
          <div style="font-size:13px;color:#888;margin-bottom:4px;">#{i}</div>
          <a href="{p['id']}" style="font-size:16px;font-weight:bold;color:#1a0dab;
             text-decoration:none;">{p['title']}</a>
          <div style="margin:4px 0;font-size:13px;color:#444;">{authors_str}</div>
          <div style="margin-bottom:6px;">{badges}</div>
          <p style="font-size:13px;color:#333;margin-top:6px;line-height:1.5;">
            <b>Abstract:</b> {p['abstract']}
          </p>
        </div>""")

    body_rows = "\n".join(rows) if rows else "<p>No papers matched today.</p>"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:860px;margin:auto;padding:20px;">
  <h2 style="color:#1a73e8;">arXiv cond-mat Digest &mdash; {date_str}</h2>
  <p style="color:#555;font-size:13px;">
    <b>Papers found:</b> {len(papers)}<br>
    <b>Categories:</b> {cat_display}<br>
    <b>Keywords filter:</b> {kw_display}
  </p>
  <hr style="border:none;border-top:1px solid #ddd;margin:16px 0;">
  {body_rows}
  <hr style="border:none;border-top:1px solid #ddd;margin:16px 0;">
  <p style="font-size:11px;color:#aaa;">Generated by arxiv_daily_digest.py</p>
</body></html>"""


def build_plain(papers: List[dict], target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    lines = [f"arXiv cond-mat Digest — {date_str}", f"{len(papers)} paper(s)\n"]
    for i, p in enumerate(papers, 1):
        authors_str = "; ".join(p["authors"][:4])
        if len(p["authors"]) > 4:
            authors_str += " et al."
        lines.append(f"[{i}] {p['title']}")
        lines.append(f"    Authors : {authors_str}")
        lines.append(f"    URL     : {p['id']}")
        lines.append(f"    Cats    : {', '.join(p['cats'])}")
        lines.append(f"    Abstract: {p['abstract'][:300]}...")
        lines.append("")
    return "\n".join(lines)


# ── Email sender ──────────────────────────────────────────────────

def send_email(subject: str, html_body: str, plain_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body,  "html",  "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())

        print(f"Email sent to {RECIPIENT_EMAIL}")
    except smtplib.SMTPAuthenticationError as e:
        print("[SMTP ERROR] Authentication failed when sending email.")
        print("  - Check SMTP_USER (full 163 address) and SMTP_PASS (授权码, NOT login password).")
        print("  - Enable SMTP in 163 webmail: Settings → POP3/SMTP/IMAP → enable SMTP.")
        print("  - Ensure SENDER_EMAIL matches the authenticated account.")
        # Save the generated message to a local .eml for manual inspection/send
        try:
            safe_subject = "".join(c for c in subject if c.isalnum() or c in " _-()").strip()
            fname = f"arxiv_digest_{safe_subject or 'message'}.eml"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(msg.as_string())
            print(f"Saved email to {fname} for manual sending.")
        except Exception:
            pass


# ── Main ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="arXiv cond-mat daily digest emailer")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print digest to terminal instead of sending email")
    parser.add_argument("--date", default=None,
                        help="Fetch papers for this date (YYYY-MM-DD). Defaults to today.")
    args = parser.parse_args()

    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD.")
            return
    else:
        target_date = date.today()
        # arXiv posts yesterday's submissions in the morning; fall back one day if nothing found
        # (handled below)

    print(f"Fetching arXiv cond-mat papers for {target_date} ...")
    papers = fetch_all_papers(target_date)

    # If today returns nothing (e.g., run early morning before arXiv updates),
    # automatically try yesterday.
    if not papers and not args.date:
        yesterday = target_date - timedelta(days=1)
        print(f"No papers found for {target_date}, trying {yesterday} ...")
        target_date = yesterday
        papers = fetch_all_papers(target_date)

    print(f"Found {len(papers)} paper(s) after filtering.")

    html_body  = build_html(papers, target_date)
    plain_body = build_plain(papers, target_date)
    subject    = f"arXiv cond-mat digest — {target_date} ({len(papers)} papers)"

    if args.dry_run:
        print("\n" + "=" * 70)
        print(plain_body)
        print("=" * 70)
        print("[dry-run] Email NOT sent.")
    else:
        send_email(subject, html_body, plain_body)


if __name__ == "__main__":
    main()
