# Small Tools

A collection of small utility scripts.

---

## arxiv_daily_digest.py

Fetches daily new arXiv submissions in condensed matter physics (`cond-mat`), filters by keywords, and emails a formatted HTML digest.

### Usage

```bash
python3 arxiv_daily_digest.py              # send email
python3 arxiv_daily_digest.py --dry-run    # print digest to terminal, no email sent
python3 arxiv_daily_digest.py --date 2025-03-10   # fetch a specific date
```

### Configuration

Edit the `USER CONFIGURATION` block at the top of the script:

| Variable | Description |
|---|---|
| `RECIPIENT_EMAIL` | Email address to receive the digest |
| `SMTP_USER` | Your SMTP sender address |
| `SMTP_PASS` | SMTP authorization code / app password |
| `CATEGORIES` | List of `cond-mat` subcategories to fetch |
| `KEYWORDS` | Filter papers by keyword in title/abstract; set `[]` for all papers |

All SMTP variables can also be overridden via environment variables (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SENDER_EMAIL`).

### Default categories

- `cond-mat.mes-hall` — Mesoscale & Nanoscale Physics
- `cond-mat.str-el` — Strongly Correlated Electrons
- `cond-mat.supr-con` — Superconductivity
- `cond-mat.quant-gas` — Quantum Gases
- `cond-mat.stat-mech` — Statistical Mechanics
- `cond-mat.mtrl-sci` — Materials Science
- `cond-mat.dis-nn` — Disordered Systems & Neural Networks

### Dependencies

```bash
pip install requests urllib3
```

All other libraries (`smtplib`, `xml.etree.ElementTree`, `argparse`, `datetime`) are Python stdlib.

### Automatic daily schedule (macOS launchd)

Place a plist under `~/Library/LaunchAgents/` with a `StartCalendarInterval` entry, then:

```bash
launchctl load   ~/Library/LaunchAgents/<your.plist>
launchctl unload ~/Library/LaunchAgents/<your.plist>  # to reload after edits
```

---

## get_bibtex_from_ads.py

Fetches a BibTeX entry from the [NASA Astrophysics Data System (ADS)](https://ui.adsabs.harvard.edu/) given a DOI, and copies it to the clipboard.

### Usage

```bash
python3 get_bibtex_from_ads.py
# prompts: enter a DOI
```

Prints the BibTeX entry and automatically copies it to the clipboard.

### Setup

1. Obtain an ADS API token from: https://ui.adsabs.harvard.edu/user/settings/token
2. Set it as an environment variable:
   ```bash
   export ADS_API_TOKEN="your_token_here"
   ```
   Or paste it directly into line 25 of the script in place of `'YourToken'`.

### Dependencies

```bash
pip install requests pyperclip
```
