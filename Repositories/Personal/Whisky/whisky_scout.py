#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║           WHISKY PRICE SCOUT  🥃                     ║
║   Sainsbury's (GBP→EUR) vs Drankdozijn (EUR)         ║
╚══════════════════════════════════════════════════════╝

Scrapes whisky listings from both retailers, converts
GBP prices to EUR, uses Claude AI to match bottles,
and generates a self-contained HTML report showing
where Sainsbury's is cheaper than Drankdozijn.

REQUIREMENTS:
    pip install playwright beautifulsoup4 requests anthropic
    playwright install chromium

USAGE:
    # Basic (uses ANTHROPIC_API_KEY env var):
    python3 whisky_scout.py

    # With explicit API key:
    python3 whisky_scout.py --api-key sk-ant-...

    # Custom output file:
    python3 whisky_scout.py --output my_report.html

    # Skip AI matching (use fast fuzzy matching instead):
    python3 whisky_scout.py --no-ai

    # Limit pages scraped (default: 3 per site):
    python3 whisky_scout.py --pages 5
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import webbrowser

import requests
from bs4 import BeautifulSoup

# ── DATA CLASSES ───────────────────────────────────────────────────────────────

@dataclass
class Bottle:
    name: str
    price: float
    currency: str          # 'GBP' or 'EUR'
    url: str = ''
    size_ml: Optional[int] = None
    brand: str = ''
    abv: Optional[float] = None
    image_url: str = ''
    source: str = ''       # 'sainsburys' or 'drankdozijn'

@dataclass
class Match:
    sainsburys: Bottle
    drankdozijn: Bottle
    sainsburys_eur: float
    saving_eur: float      # positive = cheaper at Sainsbury's
    confidence: str        # 'high', 'medium', 'low'

# ── EXCHANGE RATE ──────────────────────────────────────────────────────────────

RATE_SOURCES = [
    # CDN-hosted daily JSON files — no auth, no rate limit
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/gbp.json",
    "https://latest.currency-api.pages.dev/v1/currencies/gbp.json",
]

def get_exchange_rate(session: requests.Session) -> float:
    """Fetch GBP→EUR rate from free APIs; returns hard-coded fallback if all fail."""
    for url in RATE_SOURCES:
        try:
            r = session.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            rate = data.get("gbp", {}).get("eur")
            if rate:
                print(f"  ✅ Exchange rate: 1 GBP = {rate:.4f} EUR  (source: {url.split('/')[2]})")
                return float(rate)
        except Exception as e:
            print(f"  ⚠️  Rate source failed ({url.split('/')[2]}): {e}")

    # Hard-coded fallback — clearly flagged in the report
    fallback = 1.17
    print(f"  ⚠️  All rate sources failed — using fallback: 1 GBP = {fallback} EUR")
    return fallback


# ── SAINSBURY'S SCRAPER ────────────────────────────────────────────────────────

SAINSBURYS_API = (
    "https://www.sainsburys.co.uk/groceries-api/gol-services/product/v1/product"
    "?filter[keyword]=whisky&page_number={page}&page_size=48&sort_order=FAVOURITES_FIRST"
)
SAINSBURYS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.sainsburys.co.uk/",
}


def scrape_sainsburys_api(session: requests.Session, max_pages: int = 3) -> list[Bottle]:
    """Try Sainsbury's internal JSON API first — fastest and most reliable."""
    bottles: list[Bottle] = []

    for page in range(1, max_pages + 1):
        url = SAINSBURYS_API.format(page=page)
        try:
            r = session.get(url, headers=SAINSBURYS_HEADERS, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"    ⚠️  Sainsbury's API page {page} failed: {e}")
            break

        products = data.get("products", [])
        if not products:
            break

        for p in products:
            try:
                name = p.get("name", "").strip()
                retail = p.get("retail_price", {})
                price_str = (
                    retail.get("price")
                    or p.get("price", {}).get("value")
                    or p.get("unit_price", {}).get("price")
                )
                if not name or price_str is None:
                    continue
                price = float(str(price_str).replace("£", "").strip())
                if price <= 0:
                    continue

                # Extract size
                size_ml = None
                for pattern in [r"(\d+)\s*ml", r"(\d+)\s*litre", r"(\d+)cl"]:
                    m = re.search(pattern, name, re.I)
                    if m:
                        val = int(m.group(1))
                        size_ml = val * 10 if "cl" in pattern else (val * 1000 if "litre" in pattern else val)
                        break

                bottles.append(Bottle(
                    name=name,
                    price=price,
                    currency="GBP",
                    url="https://www.sainsburys.co.uk" + p.get("full_url", ""),
                    size_ml=size_ml,
                    image_url=p.get("image", ""),
                    source="sainsburys",
                ))
            except (ValueError, KeyError, TypeError):
                continue

        total = data.get("total_no_records", 0)
        print(f"    Page {page}: {len(products)} products (total: {total})")
        if len(bottles) >= total or page * 48 >= total:
            break
        time.sleep(0.8)

    return bottles


def scrape_sainsburys_playwright(max_pages: int = 3) -> list[Bottle]:
    """Playwright fallback for Sainsbury's — handles JS rendering and cookies."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    bottles: list[Bottle] = []
    print("    🌐 Launching browser for Sainsbury's...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-GB",
            viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "en-GB,en;q=0.9"},
        )
        page = ctx.new_page()

        # Accept cookies if banner appears
        def accept_cookies():
            try:
                page.click('[id*="accept"], [class*="accept-cookie"], #onetrust-accept-btn-handler',
                           timeout=3000)
            except Exception:
                pass

        for pg in range(1, max_pages + 1):
            url = (
                f"https://www.sainsburys.co.uk/shop/gb/groceries/drinks/whisky"
                f"?pageNumber={pg - 1}"
            )
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
                accept_cookies()
                page.wait_for_selector(
                    '[data-test="product-tile"], .gridItem, [class*="product"]',
                    timeout=10000,
                )
            except PWTimeout:
                print(f"    ⚠️  Timeout on Sainsbury's page {pg}")
                break

            soup = BeautifulSoup(page.content(), "html.parser")
            page_bottles = _parse_sainsburys_html(soup)
            bottles.extend(page_bottles)
            print(f"    Page {pg}: {len(page_bottles)} products")
            if len(page_bottles) < 10:
                break
            time.sleep(1.5)

        browser.close()

    return bottles


def _parse_sainsburys_html(soup: BeautifulSoup) -> list[Bottle]:
    bottles = []
    selectors = [
        "[data-test='product-tile']",
        ".gridItem",
        "[class*='product-card']",
        "[class*='ProductCard']",
    ]
    cards = []
    for sel in selectors:
        cards = soup.select(sel)
        if cards:
            break

    for card in cards:
        name_el = (
            card.select_one("[data-test='product-name']")
            or card.select_one(".product-name")
            or card.select_one("h3")
            or card.select_one("h2")
        )
        price_el = (
            card.select_one("[data-test='product-price']")
            or card.select_one(".price")
            or card.select_one("[class*='price']")
        )
        link_el = card.select_one("a[href]")

        name = name_el.get_text(strip=True) if name_el else ""
        price_text = price_el.get_text(strip=True) if price_el else ""
        price_match = re.search(r"[\d.]+", price_text.replace(",", ""))
        if not name or not price_match:
            continue
        price = float(price_match.group())
        if price <= 0 or price > 500:
            continue

        size_ml = None
        for pattern, factor in [(r"(\d+)ml", 1), (r"(\d+)cl", 10), (r"(\d+)\s*litre", 1000)]:
            m = re.search(pattern, name, re.I)
            if m:
                size_ml = int(m.group(1)) * factor
                break

        bottles.append(Bottle(
            name=name,
            price=price,
            currency="GBP",
            url=link_el["href"] if link_el else "",
            size_ml=size_ml,
            source="sainsburys",
        ))
    return bottles


def get_sainsburys_bottles(session: requests.Session, max_pages: int) -> list[Bottle]:
    print("\n🏴󠁧󠁢󠁳󠁣󠁴󠁿  Fetching Sainsbury's whisky listings...")
    bottles = scrape_sainsburys_api(session, max_pages)
    if len(bottles) < 5:
        print("    API returned too few results — switching to browser scrape")
        bottles = scrape_sainsburys_playwright(max_pages)
    print(f"  ✅ Sainsbury's: {len(bottles)} bottles found")
    return bottles


# ── DRANKDOZIJN SCRAPER ────────────────────────────────────────────────────────

DRANK_SEARCH_URLS = [
    "https://www.drankdozijn.nl/categorie/whisky?page={page}&sort=popular",
    "https://www.drankdozijn.nl/whisky?page={page}",
    "https://www.drankdozijn.nl/zoeken?query=whisky&page={page}",
]


def scrape_drankdozijn_playwright(max_pages: int = 3) -> list[Bottle]:
    """Playwright scraper for Drankdozijn — handles their JS-rendered product grid."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    bottles: list[Bottle] = []
    print("    🌐 Launching browser for Drankdozijn...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="nl-NL",
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()

        # Accept cookie banner
        def accept_cookies():
            for selector in [
                "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                "[class*='accept']",
                "[id*='accept']",
                "button:has-text('Akkoord')",
                "button:has-text('Accept')",
                "button:has-text('Accepteer')",
            ]:
                try:
                    page.click(selector, timeout=2000)
                    return
                except Exception:
                    continue

        tried_urls = []
        for url_template in DRANK_SEARCH_URLS:
            url = url_template.format(page=1)
            if url in tried_urls:
                continue
            tried_urls.append(url)
            try:
                page.goto(url, timeout=25000, wait_until="domcontentloaded")
                time.sleep(2)
                accept_cookies()
                time.sleep(1)
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                test_bottles = _parse_drankdozijn_html(soup)
                if test_bottles:
                    print(f"    ✅ Working URL: {url}")
                    bottles.extend(test_bottles)
                    print(f"    Page 1: {len(test_bottles)} products")
                    break
            except Exception as e:
                print(f"    ⚠️  {url}: {e}")

        if not bottles:
            print("    ❌ Could not find working Drankdozijn URL")
            browser.close()
            return []

        # Scrape remaining pages
        working_template = [t for t in DRANK_SEARCH_URLS if t.format(page=1) in tried_urls[-1:]][0]

        for pg in range(2, max_pages + 1):
            url = working_template.format(page=pg)
            try:
                page.goto(url, timeout=25000, wait_until="domcontentloaded")
                time.sleep(2)
                soup = BeautifulSoup(page.content(), "html.parser")
                page_bottles = _parse_drankdozijn_html(soup)
                if not page_bottles:
                    break
                bottles.extend(page_bottles)
                print(f"    Page {pg}: {len(page_bottles)} products")
                time.sleep(1.2)
            except PWTimeout:
                print(f"    ⚠️  Timeout on Drankdozijn page {pg}")
                break

        browser.close()

    return bottles


def _parse_drankdozijn_html(soup: BeautifulSoup) -> list[Bottle]:
    bottles = []

    # Try multiple card selector patterns
    cards = []
    for sel in [
        ".product-card", ".product-tile", "[class*='ProductCard']",
        "[class*='product-card']", "article.product", ".product-item",
        "[data-product-id]",
    ]:
        cards = soup.select(sel)
        if len(cards) > 2:
            break

    # Fallback: look for price-containing divs
    if not cards:
        cards = [el for el in soup.select("div, article, li")
                 if el.select_one("[class*='price']") and el.select_one("h2, h3, h4, [class*='title'], [class*='name']")]

    for card in cards:
        name_el = (
            card.select_one("h2") or card.select_one("h3") or card.select_one("h4")
            or card.select_one("[class*='title']") or card.select_one("[class*='name']")
        )
        price_el = (
            card.select_one("[class*='current-price']")
            or card.select_one("[class*='price-current']")
            or card.select_one("[class*='price']:not([class*='old']):not([class*='from'])")
            or card.select_one(".prijs")
        )
        link_el = card.select_one("a[href]")
        img_el = card.select_one("img[src]")

        name = name_el.get_text(strip=True) if name_el else ""
        price_text = price_el.get_text(strip=True) if price_el else ""

        # Parse European price format (e.g. "€ 34,95" or "34.95")
        price_text = price_text.replace("€", "").replace("\xa0", " ").strip()
        # Handle Dutch number format: "34,95" → 34.95
        if re.search(r"\d,\d{2}$", price_text):
            price_text = price_text.replace(".", "").replace(",", ".")
        else:
            price_text = price_text.replace(",", "")
        price_match = re.search(r"[\d.]+", price_text)

        if not name or not price_match:
            continue
        price = float(price_match.group())
        if price <= 0 or price > 2000:
            continue

        # Extract bottle size
        size_ml = None
        for pattern, factor in [(r"(\d+)\s*ml", 1), (r"(\d+)\s*cl", 10), (r"(\d+)\s*[Ll]iter", 1000)]:
            m = re.search(pattern, name, re.I)
            if m:
                size_ml = int(m.group(1)) * factor
                break

        url = link_el["href"] if link_el else ""
        if url and not url.startswith("http"):
            url = "https://www.drankdozijn.nl" + url

        bottles.append(Bottle(
            name=name,
            price=price,
            currency="EUR",
            url=url,
            size_ml=size_ml,
            image_url=img_el["src"] if img_el else "",
            source="drankdozijn",
        ))

    return bottles


def scrape_drankdozijn_requests(session: requests.Session, max_pages: int = 3) -> list[Bottle]:
    """Try plain HTTP requests first (faster, less resource-heavy)."""
    bottles = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    }
    for pg in range(1, max_pages + 1):
        for url_template in DRANK_SEARCH_URLS:
            url = url_template.format(page=pg)
            try:
                r = session.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(r.text, "html.parser")
                page_bottles = _parse_drankdozijn_html(soup)
                if page_bottles:
                    bottles.extend(page_bottles)
                    print(f"    Page {pg} (requests): {len(page_bottles)} products")
                    break
            except Exception:
                continue
        else:
            break
        time.sleep(0.8)
    return bottles


def get_drankdozijn_bottles(session: requests.Session, max_pages: int) -> list[Bottle]:
    print("\n🇳🇱  Fetching Drankdozijn whisky listings...")
    bottles = scrape_drankdozijn_requests(session, max_pages)
    if len(bottles) < 5:
        print("    Requests scrape insufficient — switching to browser")
        bottles = scrape_drankdozijn_playwright(max_pages)
    # Deduplicate by name
    seen = set()
    unique = []
    for b in bottles:
        key = normalise_name(b.name)
        if key not in seen:
            seen.add(key)
            unique.append(b)
    print(f"  ✅ Drankdozijn: {len(unique)} unique bottles found")
    return unique


# ── NAME NORMALISATION ─────────────────────────────────────────────────────────

def normalise_name(name: str) -> str:
    """Lowercase, strip accents, remove common noise words, collapse whitespace."""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode()
    name = name.lower()
    # Remove size info (we handle it separately)
    name = re.sub(r"\d+\s*(ml|cl|litre|liter|l\b)", "", name)
    # Remove noise
    for noise in ["single malt scotch whisky", "single malt whisky", "scotch whisky",
                  "blended scotch whisky", "irish whiskey", "whiskey", "whisky",
                  "the sainsbury's", "sainsburys", "by sainsbury's", "taste the difference"]:
        name = name.replace(noise, " ")
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def jaccard_similarity(a: str, b: str, ngram: int = 2) -> float:
    """Compute character n-gram Jaccard similarity between two strings."""
    def ngrams(s):
        return set(s[i:i+ngram] for i in range(len(s) - ngram + 1))
    na, nb = ngrams(normalise_name(a)), ngrams(normalise_name(b))
    if not na or not nb:
        return 0.0
    return len(na & nb) / len(na | nb)


# ── AI MATCHING ────────────────────────────────────────────────────────────────

def match_with_ai(
    sainsburys: list[Bottle],
    drank: list[Bottle],
    api_key: str,
    rate: float,
) -> list[dict]:
    """Use Claude to semantically match bottles across both sites."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    # Build compact lists (Claude has a context limit)
    def fmt(b: Bottle, idx: int, show_eur=False) -> str:
        size = f" {b.size_ml}ml" if b.size_ml else ""
        if show_eur:
            eur = b.price * rate
            return f"{idx}: {b.name}{size} [£{b.price:.2f} ≈ €{eur:.2f}]"
        return f"{idx}: {b.name}{size} [€{b.price:.2f}]"

    # Process in batches of 50 vs 50 to stay within context
    BATCH = 50
    all_matches = []

    for s_start in range(0, len(sainsburys), BATCH):
        s_batch = sainsburys[s_start : s_start + BATCH]
        s_lines = "\n".join(fmt(b, s_start + i, show_eur=True) for i, b in enumerate(s_batch))
        d_lines = "\n".join(fmt(b, i, show_eur=False) for i, b in enumerate(drank[:80]))

        prompt = f"""You are a whisky product matching expert. Match Sainsbury's bottles to Drankdozijn bottles.

Rules:
- Match ONLY when you're confident it's the SAME product: same brand, same expression name, same age statement, and ideally same bottle size
- A 12-year Glenfiddich 70cl and a 12-year Glenfiddich 1L are NOT the same
- Ignore minor wording differences (e.g. "Year Old" vs "Years", "Scotch Whisky" vs "Single Malt")
- Index numbers are ABSOLUTE (they represent position in the full list, not this batch)

SAINSBURY'S (prices in GBP, converted to EUR shown):
{s_lines}

DRANKDOZIJN (prices in EUR):
{d_lines}

Return ONLY a JSON array. Each element: {{"s": <sainsburys_index>, "d": <drankdozijn_index>, "c": "high"|"medium"}}
No markdown, no explanation — raw JSON only."""

        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            raw = re.sub(r"```json|```", "", raw).strip()
            batch_matches = json.loads(raw)
            all_matches.extend(batch_matches)
            print(f"    AI batch {s_start//BATCH + 1}: {len(batch_matches)} matches")
            time.sleep(0.5)
        except (json.JSONDecodeError, Exception) as e:
            print(f"    ⚠️  AI batch {s_start//BATCH + 1} failed: {e}")

    return all_matches


def match_fuzzy(sainsburys: list[Bottle], drank: list[Bottle], threshold: float = 0.35) -> list[dict]:
    """Fast fuzzy fallback matching using Jaccard n-gram similarity."""
    matches = []
    for si, sb in enumerate(sainsburys):
        best_score, best_di = 0.0, -1
        for di, db in enumerate(drank):
            score = jaccard_similarity(sb.name, db.name)
            # Boost if sizes match
            if sb.size_ml and db.size_ml and sb.size_ml == db.size_ml:
                score += 0.15
            if score > best_score:
                best_score, best_di = score, di
        if best_score >= threshold:
            confidence = "high" if best_score >= 0.6 else "medium"
            matches.append({"s": si, "d": best_di, "c": confidence})
    return matches


def build_matches(
    raw_matches: list[dict],
    sainsburys: list[Bottle],
    drank: list[Bottle],
    rate: float,
    min_saving: float = 0.0,
) -> tuple[list[Match], list[Match]]:
    """Convert raw index matches into Match objects, split into cheaper/dearer."""
    cheaper, dearer = [], []
    seen_pairs = set()

    for m in raw_matches:
        si, di = m.get("s", -1), m.get("d", -1)
        if si < 0 or di < 0 or si >= len(sainsburys) or di >= len(drank):
            continue
        pair = (si, di)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        sb = sainsburys[si]
        db = drank[di]
        sb_eur = round(sb.price * rate, 2)
        saving = round(db.price - sb_eur, 2)

        match = Match(
            sainsburys=sb,
            drankdozijn=db,
            sainsburys_eur=sb_eur,
            saving_eur=saving,
            confidence=m.get("c", "medium"),
        )
        if saving > 0 and saving >= min_saving:
            cheaper.append(match)
        else:
            dearer.append(match)

    cheaper.sort(key=lambda x: x.saving_eur, reverse=True)
    dearer.sort(key=lambda x: x.saving_eur)
    return cheaper, dearer


# ── HTML REPORT ────────────────────────────────────────────────────────────────

def generate_html_report(
    cheaper: list[Match],
    dearer: list[Match],
    rate: float,
    rate_is_live: bool,
    generated_at: datetime,
    output_path: Path,
    sainsburys_count: int,
    drank_count: int,
) -> None:
    """Render a fully self-contained, styled HTML comparison report."""

    total_savings = sum(m.saving_eur for m in cheaper)
    max_saving = cheaper[0].saving_eur if cheaper else 0

    def card(m: Match, result_type: str) -> str:
        cls = "cheaper" if result_type == "cheaper" else "dearer"
        badge = (
            f'<span class="badge {cls}">Save €{m.saving_eur:.2f}</span>'
            if result_type == "cheaper"
            else f'<span class="badge {cls}">€{abs(m.saving_eur):.2f} pricier</span>'
        )
        conf_dot = {
            "high": '<span class="conf high" title="High confidence match">●</span>',
            "medium": '<span class="conf medium" title="Medium confidence match">●</span>',
        }.get(m.confidence, "")

        sn_url = m.sainsburys.url or "#"
        dd_url = m.drankdozijn.url or "#"

        return f"""
        <div class="card {cls}" data-type="{cls}" data-saving="{m.saving_eur:.2f}">
          <div class="card-name">
            {conf_dot}
            <a href="{sn_url}" target="_blank" rel="noopener">{m.sainsburys.name}</a>
          </div>
          <div class="card-match">
            Matched: <a href="{dd_url}" target="_blank" rel="noopener">{m.drankdozijn.name}</a>
          </div>
          <div class="card-prices">
            <div class="price-block sains">
              <div class="site-label">Sainsbury's</div>
              <div class="price-gbp">£{m.sainsburys.price:.2f}</div>
              <div class="price-eur">≈ €{m.sainsburys_eur:.2f}</div>
            </div>
            <div class="price-arrow">{'↓' if result_type == 'cheaper' else '↑'}</div>
            <div class="price-block drank">
              <div class="site-label">Drankdozijn</div>
              <div class="price-eur main">€{m.drankdozijn.price:.2f}</div>
            </div>
            {badge}
          </div>
        </div>"""

    cheaper_cards = "".join(card(m, "cheaper") for m in cheaper)
    dearer_cards  = "".join(card(m, "dearer")  for m in dearer)
    rate_note = "" if rate_is_live else ' <span class="rate-warn">(fallback — check manually)</span>'
    ts = generated_at.strftime("%d %B %Y, %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Whisky Price Scout Report — {ts}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Inter:wght@300;400;500;600&display=swap');
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --amber:#C07B2A;--amber-lt:#E8A94D;
  --peat:#1C1410;--slate:#2E2620;--oak:#3D2F1F;
  --grain:#F5EFE6;--mist:#EDE5D8;--smoke:#7A6A58;
  --green:#2D6A4F;--green-bg:#D8F3DC;
  --red:#7B2D2D;--red-bg:#F3D8D8;
  --border:rgba(192,123,42,.25);
}}
body{{font-family:'Inter',sans-serif;background:var(--peat);color:var(--grain);min-height:100vh}}

/* HEADER */
header{{
  background:linear-gradient(160deg,var(--oak) 0%,var(--slate) 55%,var(--peat) 100%);
  border-bottom:2px solid var(--amber);
  padding:2.5rem 2rem 2rem;text-align:center;
  position:relative;overflow:hidden;
}}
header::before{{content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse 60% 90% at 50% 0%,rgba(192,123,42,.15) 0%,transparent 70%);
  pointer-events:none}}
.flag-row{{display:flex;align-items:center;justify-content:center;gap:1rem;
  margin-bottom:.75rem;font-size:2rem}}
.vs-pill{{font-size:.7rem;font-weight:600;letter-spacing:.12em;color:var(--amber);
  background:rgba(192,123,42,.15);border:1px solid var(--amber);border-radius:99px;padding:.25rem .75rem}}
h1{{font-family:'Playfair Display',serif;font-size:clamp(1.8rem,4vw,2.8rem);
  font-weight:700;line-height:1.1;margin-bottom:.4rem}}
.subtitle{{color:var(--smoke);font-size:.85rem;font-weight:300}}
.meta{{margin-top:.75rem;font-size:.72rem;color:var(--smoke)}}
.rate-warn{{color:#E07070}}

/* SUMMARY */
.summary{{
  display:grid;grid-template-columns:repeat(5,1fr);gap:1rem;
  max-width:1100px;margin:2rem auto;padding:0 1.25rem;
}}
.stat{{background:var(--slate);border:1px solid var(--border);border-radius:10px;
  padding:1.1rem 1rem;text-align:center}}
.stat .num{{font-family:'Playfair Display',serif;font-size:1.9rem;font-weight:700;line-height:1}}
.stat .lbl{{font-size:.7rem;color:var(--smoke);margin-top:.2rem}}
.stat.g .num{{color:#52B788}}.stat.r .num{{color:#E07070}}
.stat.a .num{{color:var(--amber-lt);font-size:1.3rem}}

/* CONTROLS */
.controls{{max-width:1100px;margin:0 auto 1.25rem;padding:0 1.25rem;
  display:flex;gap:.5rem;flex-wrap:wrap;align-items:center}}
.tab{{background:transparent;border:1px solid var(--border);border-radius:99px;
  color:var(--smoke);font-family:'Inter',sans-serif;font-size:.78rem;font-weight:500;
  padding:.3rem .9rem;cursor:pointer;transition:all .2s}}
.tab:hover{{border-color:var(--amber);color:var(--grain)}}
.tab.active{{background:var(--amber);border-color:var(--amber);color:var(--peat)}}
.search-box{{margin-left:auto;background:var(--slate);border:1px solid var(--border);
  border-radius:7px;color:var(--grain);font-family:'Inter',sans-serif;font-size:.8rem;
  padding:.35rem .8rem;outline:none;width:220px}}
.search-box:focus{{border-color:var(--amber)}}
.search-box::placeholder{{color:var(--smoke)}}

/* CARDS */
.results{{max-width:1100px;margin:0 auto;padding:0 1.25rem 4rem}}
.card{{background:var(--slate);border:1px solid var(--border);border-radius:10px;
  padding:1rem 1.25rem;margin-bottom:.7rem;transition:border-color .2s}}
.card:hover{{border-color:rgba(192,123,42,.5)}}
.card.cheaper{{border-left:3px solid #52B788}}
.card.dearer{{border-left:3px solid #E07070}}
.card[style*="none"]{{display:none}}

.card-name{{font-family:'Playfair Display',serif;font-size:.95rem;margin-bottom:.2rem}}
.card-name a{{color:var(--grain);text-decoration:none}}
.card-name a:hover{{color:var(--amber-lt);text-decoration:underline}}
.card-match{{font-size:.72rem;color:var(--smoke);margin-bottom:.7rem}}
.card-match a{{color:var(--smoke)}}
.card-match a:hover{{color:var(--amber-lt)}}

.card-prices{{display:flex;align-items:center;gap:1rem;flex-wrap:wrap}}
.price-block{{min-width:100px}}
.site-label{{font-size:.65rem;color:var(--smoke);margin-bottom:.15rem}}
.price-gbp{{font-size:.95rem;font-weight:600;font-variant-numeric:tabular-nums}}
.price-eur{{font-size:.72rem;color:var(--smoke)}}
.price-eur.main{{font-size:.95rem;font-weight:600;color:var(--grain)}}
.price-arrow{{font-size:1.4rem;color:var(--smoke)}}
.badge{{border-radius:99px;font-size:.7rem;font-weight:600;padding:.25rem .75rem;margin-left:auto}}
.badge.cheaper{{background:var(--green-bg);color:var(--green)}}
.badge.dearer{{background:var(--red-bg);color:var(--red)}}

.conf{{font-size:.7rem;margin-right:.3rem}}
.conf.high{{color:#52B788}}.conf.medium{{color:var(--amber)}}

/* SECTION HEADER */
.section-hdr{{max-width:1100px;margin:0 auto 1rem;padding:0 1.25rem;
  font-family:'Playfair Display',serif;font-size:1.2rem;display:flex;align-items:center;gap:.75rem}}
.section-hdr span{{font-family:'Inter',sans-serif;font-size:.75rem;color:var(--smoke);font-weight:400}}
.divider{{max-width:1100px;margin:2rem auto;padding:0 1.25rem;border:none;
  border-top:1px solid var(--border)}}

/* EMPTY */
.empty{{color:var(--smoke);text-align:center;padding:2rem;font-size:.875rem}}

footer{{text-align:center;color:var(--smoke);font-size:.7rem;padding:1.5rem;
  border-top:1px solid var(--border)}}

@media(max-width:700px){{
  .summary{{grid-template-columns:1fr 1fr}}
  .card-prices{{gap:.6rem}}
  .search-box{{width:100%;margin-left:0}}
  .controls{{flex-direction:column;align-items:flex-start}}
}}
</style>
</head>
<body>
<header>
  <div class="flag-row"><span>🏴󠁧󠁢󠁳󠁣󠁴󠁿</span><span class="vs-pill">SCOUT</span><span>🇳🇱</span></div>
  <h1>Whisky Price Scout</h1>
  <p class="subtitle">Sainsbury's (GBP→EUR) compared to Drankdozijn (EUR)</p>
  <p class="meta">Generated {ts} · {sainsburys_count} Sainsbury's bottles · {drank_count} Drankdozijn bottles · 1&nbsp;GBP&nbsp;=&nbsp;{rate:.4f}&nbsp;EUR{rate_note}</p>
</header>

<div class="summary">
  <div class="stat g"><div class="num">{len(cheaper)}</div><div class="lbl">Cheaper at Sainsbury's</div></div>
  <div class="stat r"><div class="num">{len(dearer)}</div><div class="lbl">Cheaper at Drankdozijn</div></div>
  <div class="stat g"><div class="num">€{total_savings:.2f}</div><div class="lbl">Total potential saving</div></div>
  <div class="stat g"><div class="num">€{max_saving:.2f}</div><div class="lbl">Biggest single saving</div></div>
  <div class="stat a"><div class="num">{rate:.4f}</div><div class="lbl">GBP → EUR</div></div>
</div>

<div class="controls">
  <button class="tab active" onclick="filter('all',this)">All ({len(cheaper)+len(dearer)})</button>
  <button class="tab" onclick="filter('cheaper',this)">✅ Cheaper at Sainsbury's ({len(cheaper)})</button>
  <button class="tab" onclick="filter('dearer',this)">❌ Pricier at Sainsbury's ({len(dearer)})</button>
  <input class="search-box" type="text" placeholder="🔍 Search bottles…" oninput="search(this.value)" />
</div>

<div class="results" id="cards">
  {'<div class="section-hdr">🟢 Cheaper at Sainsbury\'s <span>sorted by saving, highest first</span></div>' if cheaper else ''}
  {cheaper_cards if cheaper else '<div class="empty">No bottles found cheaper at Sainsbury\'s.</div>'}
  {'<hr class="divider"><div class="section-hdr">🔴 Pricier at Sainsbury\'s <span>sorted by price gap</span></div>' if dearer else ''}
  {dearer_cards}
</div>

<footer>
  Whisky Price Scout · Prices scraped {ts} · Purely informational — verify before purchasing<br>
  <a href="https://www.sainsburys.co.uk/shop/gb/groceries/drinks/whisky" target="_blank" style="color:var(--smoke)">Sainsbury's Whisky</a>
  &nbsp;·&nbsp;
  <a href="https://www.drankdozijn.nl/whisky" target="_blank" style="color:var(--smoke)">Drankdozijn Whisky</a>
</footer>

<script>
function filter(type, btn) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.card').forEach(c => {{
    if (type === 'all') c.style.display = '';
    else c.style.display = c.dataset.type === type ? '' : 'none';
  }});
  currentFilter = type;
}}
let currentFilter = 'all';
function search(q) {{
  q = q.toLowerCase();
  document.querySelectorAll('.card').forEach(c => {{
    const text = c.textContent.toLowerCase();
    const typeOk = currentFilter === 'all' || c.dataset.type === currentFilter;
    c.style.display = (typeOk && (!q || text.includes(q))) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    print(f"\n  📄 Report saved → {output_path.resolve()}")


# ── MAIN ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare Sainsbury's whisky prices (GBP→EUR) with Drankdozijn.nl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY", ""),
                   help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    p.add_argument("--no-ai", action="store_true",
                   help="Skip Claude AI matching; use fast fuzzy matching instead")
    p.add_argument("--pages", type=int, default=3,
                   help="Number of pages to scrape per site (default: 3 ≈ 144 bottles each)")
    p.add_argument("--min-saving", type=float, default=0.0,
                   help="Only show Sainsbury's cheaper bottles above this EUR saving (default: 0)")
    p.add_argument("--output", default="whisky_scout_report.html",
                   help="Output HTML filename (default: whisky_scout_report.html)")
    p.add_argument("--no-open", action="store_true",
                   help="Don't auto-open the report in your browser when done")
    return p.parse_args()


def main():
    args = parse_args()
    print(__doc__.strip().split("REQUIREMENTS")[0])
    print("=" * 54)

    if not args.no_ai and not args.api_key:
        print("⚠️  No Anthropic API key found.")
        print("   Set ANTHROPIC_API_KEY env var, or pass --api-key sk-ant-...")
        print("   Falling back to fuzzy matching (--no-ai mode).\n")
        args.no_ai = True

    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    # ── Step 1: Exchange rate
    print("\n💱  Getting GBP → EUR exchange rate...")
    rate_is_live = True
    try:
        rate = get_exchange_rate(session)
    except Exception as e:
        print(f"  ❌ Exchange rate failed: {e}")
        rate = 1.17
        rate_is_live = False

    # ── Step 2: Scrape
    sainsburys = get_sainsburys_bottles(session, args.pages)
    drank      = get_drankdozijn_bottles(session, args.pages)

    if len(sainsburys) < 3 or len(drank) < 3:
        print("\n❌  Too few products scraped from one or both sites.")
        print("   This usually means the site blocked the scraper.")
        print("   Try running with a VPN, or wait a few minutes and retry.")
        sys.exit(1)

    # ── Step 3: Match
    print(f"\n🔗  Matching bottles ({len(sainsburys)} × {len(drank)})...")
    if args.no_ai:
        print("    Using fuzzy text matching (--no-ai mode)")
        raw_matches = match_fuzzy(sainsburys, drank)
    else:
        print("    Using Claude AI for semantic matching...")
        try:
            raw_matches = match_with_ai(sainsburys, drank, args.api_key, rate)
        except Exception as e:
            print(f"    ⚠️  AI matching failed ({e}) — falling back to fuzzy matching")
            raw_matches = match_fuzzy(sainsburys, drank)

    print(f"  ✅ {len(raw_matches)} bottle pairs matched")

    # ── Step 4: Build result sets
    cheaper, dearer = build_matches(raw_matches, sainsburys, drank, rate, args.min_saving)
    print(f"\n  🟢 Cheaper at Sainsbury's: {len(cheaper)}")
    print(f"  🔴 Cheaper at Drankdozijn: {len(dearer)}")
    if cheaper:
        total = sum(m.saving_eur for m in cheaper)
        print(f"  💰 Total potential saving: €{total:.2f}")
        print(f"  🏆 Best deal: {cheaper[0].sainsburys.name}")
        print(f"       Sainsbury's €{cheaper[0].sainsburys_eur:.2f}  vs  Drankdozijn €{cheaper[0].drankdozijn.price:.2f}  → save €{cheaper[0].saving_eur:.2f}")

    # ── Step 5: Generate report
    output_path = Path(args.output)
    generate_html_report(
        cheaper=cheaper,
        dearer=dearer,
        rate=rate,
        rate_is_live=rate_is_live,
        generated_at=datetime.now(),
        output_path=output_path,
        sainsburys_count=len(sainsburys),
        drank_count=len(drank),
    )

    if not args.no_open:
        webbrowser.open(output_path.resolve().as_uri())
        print("  🌐 Report opened in your default browser")

    print("\n✅  Done!\n")


if __name__ == "__main__":
    main()
