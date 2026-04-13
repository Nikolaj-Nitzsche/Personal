"""Search arXiv for recent papers matching keywords and open results in your browser."""

from __future__ import annotations
import argparse
import base64
import importlib
import json
import html
import re
import ssl
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import urlopen
import xml.etree.ElementTree as ET

BASE_URL = "http://export.arxiv.org/api/query"
SEEN_STORE = Path(".arxiv_seen.json")
CONFIG_STORE = Path(".arxiv_config.json")
STATE_STORE = Path(".arxiv_state.json")
DEFAULT_CONFIG = {
    "keywords": ["quantum", "cryo", "NV-centers"],
    "mode": "majority",
    "refresh_interval_hours": 12,
    "max_results": 20,
    "output": "arxiv_results.html",
}


def build_query(keywords: list[str], mode: str) -> str:
    parts = [f"all:{quote_plus(keyword)}" for keyword in keywords]
    if mode == "all":
        return "+AND+".join(parts)
    return "+OR+".join(parts)


def required_matches(keywords: list[str], mode: str) -> int:
    if mode == "any":
        return 1
    if mode == "all":
        return len(keywords)
    return (len(keywords) + 1) // 2


def normalize_text(text: str) -> str:
    normalized = text.casefold()
    normalized = normalized.replace('-', ' ').replace('_', ' ')
    normalized = re.sub(r"[^a-z0-9\s]+", ' ', normalized)
    return re.sub(r"\s+", ' ', normalized).strip()


def filter_entries(entries: list[dict[str, str]], keywords: list[str], mode: str) -> list[dict[str, str]]:
    if not keywords:
        return entries
    required = required_matches(keywords, mode)
    filtered: list[dict[str, str]] = []
    normalized_keywords = [normalize_text(keyword) for keyword in keywords]
    for entry in entries:
        content = normalize_text(
            f"{entry['title']} {entry['summary']} {entry.get('authors','')} {entry.get('categories','')} {entry.get('comment','')} {entry.get('journal_ref','')}"
        )
        matched: list[str] = []
        for original, normalized in zip(keywords, normalized_keywords):
            if normalized and normalized in content:
                matched.append(original)
        if len(matched) >= required:
            entry["match_count"] = len(matched)
            entry["matched_keywords"] = matched
            filtered.append(entry)
    return filtered


def load_config(path: Path) -> dict[str, object]:
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        return DEFAULT_CONFIG.copy()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def normalize_section(section: dict[str, object], defaults: dict[str, object]) -> dict[str, object]:
    label = str(section.get("label", "Section")).strip() or "Section"
    mode = str(section.get("mode", defaults["mode"])) if section.get("mode") is not None else defaults["mode"]
    if mode not in {"any", "majority", "all"}:
        mode = defaults["mode"]
    keywords = [str(item).strip() for item in section.get("keywords", []) if str(item).strip()]
    max_results = int(section.get("max_results", defaults["max_results"])) if section.get("max_results") is not None else defaults["max_results"]
    return {
        "label": label,
        "keywords": keywords,
        "mode": mode,
        "max_results": max_results,
    }


def get_sections(config: dict[str, object]) -> list[dict[str, object]]:
    if isinstance(config.get("sections"), list):
        sections: list[dict[str, object]] = []
        for item in config["sections"]:
            if isinstance(item, dict):
                sections.append(normalize_section(item, DEFAULT_CONFIG))
        return [section for section in sections if section["keywords"]]

    keywords = [str(item).strip() for item in config.get("keywords", DEFAULT_CONFIG["keywords"]) if str(item).strip()]
    if not keywords:
        keywords = DEFAULT_CONFIG["keywords"]
    return [{
        "label": "Default",
        "keywords": keywords,
        "mode": str(config.get("mode", DEFAULT_CONFIG["mode"])),
        "max_results": int(config.get("max_results", DEFAULT_CONFIG["max_results"])),
    }]


def save_config(path: Path, config: dict[str, object]) -> None:
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path: Path, state: dict[str, object]) -> None:
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def create_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    return context


def send_notification(title: str, message: str) -> None:
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=8, threaded=True)
        return
    except Exception:
        pass
    try:
        from plyer import notification
        notification.notify(title=title, message=message, app_name="arXiv Alerts", timeout=8)
        return
    except Exception:
        pass
    print("Notification not sent: install win10toast or plyer in your Python environment to enable desktop alerts.")


def fetch_feed(query: str, max_results: int = 20) -> str:
    url = (
        f"{BASE_URL}?search_query={query}"
        f"&start=0&max_results={max_results}"
        f"&sortBy=submittedDate&sortOrder=descending"
    )
    context = create_ssl_context()
    with urlopen(url, timeout=20, context=context) as response:
        return response.read().decode("utf-8")


def parse_feed(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    results: list[dict[str, str]] = []
    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", default="", namespaces=ns).strip()
        summary = entry.findtext("atom:summary", default="", namespaces=ns).strip()
        published = entry.findtext("atom:published", default="", namespaces=ns).strip()
        authors = [author.findtext("atom:name", default="", namespaces=ns).strip() for author in entry.findall("atom:author", ns)]
        link = ""
        entry_id = entry.findtext("atom:id", default="", namespaces=ns).strip()
        categories = [cat.attrib.get("term", "") for cat in entry.findall("atom:category", ns)]
        comment = entry.findtext("arxiv:comment", default="", namespaces={**ns, "arxiv": "http://arxiv.org/schemas/atom"}).strip()
        journal_ref = entry.findtext("arxiv:journal_ref", default="", namespaces={**ns, "arxiv": "http://arxiv.org/schemas/atom"}).strip()
        for link_node in entry.findall("atom:link", ns):
            if link_node.attrib.get("rel") == "alternate":
                link = link_node.attrib.get("href", "")
                break
        if not link:
            link = entry_id
        results.append({
            "id": entry_id,
            "title": title,
            "summary": summary,
            "published": published,
            "authors": ", ".join(authors),
            "categories": ", ".join(categories),
            "comment": comment,
            "journal_ref": journal_ref,
            "link": link,
        })
    return results


def load_seen_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_seen_ids(path: Path, paper_ids: set[str]) -> None:
    path.write_text(json.dumps(sorted(paper_ids), indent=2), encoding="utf-8")


def get_default_favicon_data_uri() -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect width="100" height="100" rx="20" fill="#1d4ed8"/>'
        '<path d="M28 58 L44 42 L56 54 L72 38" fill="none" stroke="#fff" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    )
    encoded_svg = base64.b64encode(svg.encode('utf-8')).decode('ascii')
    return f"data:image/svg+xml;base64,{encoded_svg}"


def render_html(section_results: list[dict[str, object]], refresh_interval: int, config_path: str, cache_note: str = "") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = "arXiv recent papers by section"
    total_entries = sum(len(section["entries"]) for section in section_results)
    total_new = sum(section.get("new_count", 0) for section in section_results)
    favicon_uri = get_default_favicon_data_uri()
    section_blocks: list[str] = []

    for section in section_results:
        section_label = html.escape(section["label"])
        section_mode = html.escape(section.get("effective_mode", section["mode"]))
        section_keywords = section["keywords"]
        section_new = section.get("new_count", 0)
        section_badge = "<span class=\"section-badge\">NEW</span>" if section_new else ""
        section_status = f"{len(section['entries'])} papers ({section_new} new)"
        keyword_list_html = "".join(f"<li>{html.escape(keyword)}</li>" for keyword in section_keywords)
        section_items: list[str] = []
        for entry in section["entries"]:
            summary = html.escape(entry["summary"]).replace("\n", " ").strip()
            if len(summary) > 260:
                summary = summary[:260].rstrip() + "..."
            published = entry["published"][:10] if entry["published"] else "unknown"
            title_text = html.escape(entry["title"])
            authors_text = html.escape(entry["authors"])
            badge = "<span class=\"badge\">NEW</span>" if entry.get("is_new") else ""
            match_info = ""
            if entry.get("match_count") is not None:
                match_count = entry['match_count']
                matched_keywords = entry.get('matched_keywords', [])
                keywords_label = ", ".join(html.escape(k) for k in matched_keywords)
                match_info = (
                    f"<p class=\"match-info\">Matched {match_count} of {len(section_keywords)} keywords. "
                    f"<strong>Keywords:</strong> {keywords_label}</p>" if matched_keywords else
                    f"<p class=\"match-info\">Matched {match_count} of {len(section_keywords)} keywords.</p>"
                )
            section_items.append(
                f"<article>"
                f"<h2><a href=\"{entry['link']}\" target=\"_blank\">{title_text}</a> {badge}</h2>"
                f"<p><strong>Authors:</strong> {authors_text}</p>"
                f"<p><strong>Published:</strong> {published}</p>"
                f"{match_info}"
                f"<p>{summary}</p>"
                f"</article>"
            )
        if not section_items:
            section_items.append("<p>No results found for this section.</p>")

        section_fallback_html = ""
        if section.get("fallback_note"):
            section_fallback_html = f"<p class=\"fallback\">{html.escape(section.get('fallback_note', ''))}</p>"

        section_blocks.append(
            f"<details class=\"section\">"
            f"<summary><span class=\"section-title\">{section_label}</span> {section_badge} <span class=\"section-count\">{section_status}</span></summary>"
            f"<div class=\"section-body\">"
            f"<p class=\"section-description\"><strong>Keywords:</strong></p>"
            f"<ul class=\"section-keywords\">{keyword_list_html}</ul>"
            f"{section_fallback_html}"
            f"{''.join(section_items)}"
            f"</div>"
            f"</details>"
        )

    sections_html = "".join(section_blocks)
    new_line = f"<strong>{total_new}</strong> new paper(s) since your last check." if total_new else "No new papers since your last run."
    cache_html = f"<p class=\"cache-note\">{html.escape(cache_note)}</p>" if cache_note else ""
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <link rel=\"icon\" href=\"{favicon_uri}\">
    <title>{title}</title>
    <style>
        body {{ font-family: Inter, Arial, sans-serif; margin: 24px; background: #f4f6f8; color: #111827; }}
        .page {{ max-width: 980px; margin: auto; }}
        h1 {{ margin-bottom: 0.25em; font-size: 2.2rem; }}
        .meta {{ margin-bottom: 0.75em; color: #4b5563; }}
        .status {{ margin-bottom: 1.5em; padding: 16px; background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 12px; color: #4338ca; }}
        .fallback {{ margin-top: 0.75em; padding: 14px 18px; background: #fef3c7; border: 1px solid #fde68a; border-radius: 12px; color: #92400e; }}
        .cache-note {{ margin-top: 0.75em; padding: 14px 18px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px; color: #1e40af; }}
        article {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 22px; margin-bottom: 18px; box-shadow: 0 15px 35px rgba(15, 23, 42, 0.08); }}
        h2 {{ margin: 0 0 0.75em; font-size: 1.35rem; }}
        .badge {{ display: inline-flex; align-items: center; margin-left: 0.75rem; padding: 0.2rem 0.65rem; border-radius: 999px; background: #f97316; color: white; font-size: 0.8rem; letter-spacing: 0.02em; transition: opacity 0.25s ease, transform 0.25s ease; }}
        .badge.fade-out {{ opacity: 0; transform: scale(0.75); }}
        .match-info {{ margin: 0.6em 0 0; color: #6b7280; font-size: 0.95rem; }}
        details.section {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 18px 22px; margin-bottom: 18px; box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08); }}
        summary {{ cursor: pointer; list-style: none; display: flex; align-items: center; justify-content: space-between; gap: 10px; font-size: 1.1rem; font-weight: 600; padding: 0; }}
        .section-title {{ color: #111827; }}
        .section-meta {{ color: #4b5563; font-size: 0.95rem; }}
        .section-count {{ background: #eef2ff; color: #1e40af; padding: 0.35rem 0.75rem; border-radius: 999px; font-size: 0.95rem; }}
        .section-badge {{ display: inline-flex; align-items: center; padding: 0.2rem 0.65rem; border-radius: 999px; background: #f97316; color: white; font-size: 0.8rem; }}
        .section-body {{ margin-top: 18px; }}
        .section-description {{ margin-bottom: 0.5rem; color: #374151; }}
        .section-keywords {{ margin: 0; padding-left: 1.2em; color: #1e40af; }}
        .section-keywords li {{ margin-bottom: 0.35em; }}
        a {{ color: #1d4ed8; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        p {{ line-height: 1.75; margin: 0.4em 0; color: #4b5563; }}
        .page-footer {{ margin-top: 24px; padding: 14px 16px; text-align: center; border-top: 4px solid #2563eb; color: #334155; background: #f8fafc; border-radius: 0 0 16px 16px; font-size: 0.95rem; }}
    </style>
    <script>
      document.addEventListener('DOMContentLoaded', function() {{
        document.querySelectorAll('article h2 a[target="_blank"]').forEach(function(link) {{
          link.addEventListener('click', function() {{
            var badge = link.parentElement.querySelector('.badge');
            if (badge) {{
              badge.classList.add('fade-out');
              setTimeout(function() {{ badge.style.display = 'none'; }}, 250);
            }}
          }});
        }});
      }});
    </script>
</head>
<body>
    <div class=\"page\">
        <h1>{title}</h1>
        <p class=\"meta\">Generated: {now} | Refresh interval: {refresh_interval}h</p>
        <div class="status">{new_line} Config: {html.escape(config_path)}</div>
        {cache_html}
        {sections_html}
        <div class="page-footer">Designed and built by Nikolaj Nitzsche © 2026</div>
    </div>
</body>
</html>"""


def write_output(html: str, output_file: Path) -> None:
    output_file.write_text(html, encoding="utf-8")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search arXiv and display recent papers matching keywords.")
    parser.add_argument("keywords", nargs="*", help="Keywords to search for on arXiv. If omitted, keywords are loaded from config.")
    parser.add_argument("--mode", choices=["any", "majority", "all"], help="Search mode: any keyword, majority of keywords, or all keywords.")
    parser.add_argument("--max-results", type=int, help="Maximum number of results to fetch.")
    parser.add_argument("--output", help="HTML output file name.")
    parser.add_argument("--refresh-interval", type=int, help="Refresh interval in hours.")
    parser.add_argument("--config", default=str(CONFIG_STORE), help="Path to the JSON config file.")
    parser.add_argument("--force-refresh", action="store_true", help="Force a new arXiv search even if the cache is still valid.")
    parser.add_argument("--notify", action="store_true", help="Send a desktop notification when new papers are found.")
    parser.add_argument("--no-open", action="store_true", help="Do not open the result file automatically.")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    config_path = Path(args.config)
    config = load_config(config_path)

    cli_keywords = [keyword.strip() for keyword in (args.keywords or []) if keyword.strip()]
    loaded_sections = get_sections(config)

    if cli_keywords:
        mode = args.mode if args.mode else str(config.get("mode", DEFAULT_CONFIG["mode"]))
        section_max_results = args.max_results if args.max_results is not None else int(config.get("max_results", DEFAULT_CONFIG["max_results"]))
        sections = [{
            "label": "Custom search",
            "keywords": cli_keywords,
            "mode": mode,
            "max_results": section_max_results,
        }]
    else:
        sections = loaded_sections

    if not sections or not any(section["keywords"] for section in sections):
        print("Please provide at least one keyword either on the command line or in the config file.")
        return

    output_name = args.output if args.output else str(config.get("output", DEFAULT_CONFIG["output"]))
    refresh_interval = args.refresh_interval if args.refresh_interval is not None else int(config.get("refresh_interval_hours", DEFAULT_CONFIG["refresh_interval_hours"]))

    config_to_save = {
        "refresh_interval_hours": refresh_interval,
        "max_results": int(config.get("max_results", DEFAULT_CONFIG["max_results"])),
        "output": output_name,
    }
    if isinstance(config.get("sections"), list):
        config_to_save["sections"] = config["sections"]
    else:
        config_to_save["keywords"] = cli_keywords if cli_keywords else [str(item) for item in config.get("keywords", DEFAULT_CONFIG["keywords"])]
        config_to_save["mode"] = args.mode if args.mode else str(config.get("mode", DEFAULT_CONFIG["mode"]))
    save_config(config_path, config_to_save)

    cache_note = ""
    state = load_state(STATE_STORE)
    last_fetch = None
    if state.get("last_fetch"):
        try:
            last_fetch = datetime.fromisoformat(state["last_fetch"])
        except Exception:
            last_fetch = None

    should_use_cache = False
    current_query = {
        "sections": [
            {
                "label": section["label"],
                "keywords": section["keywords"],
                "mode": section["mode"],
                "max_results": section["max_results"],
            }
            for section in sections
        ]
    }
    output_path = Path(output_name)
    if not args.force_refresh and output_path.exists():
        if last_fetch is not None and state.get("query") == current_query:
            elapsed = datetime.now() - last_fetch
            if elapsed < timedelta(hours=refresh_interval):
                print(f"Using cached results from {last_fetch.isoformat()} (refresh interval {refresh_interval}h).")
                cache_note = f"Data is cached until {(last_fetch + timedelta(hours=refresh_interval)).isoformat()}. Run with --force-refresh to fetch new results."
                should_use_cache = True
        elif not state and output_path.exists():
            mtime = datetime.fromtimestamp(output_path.stat().st_mtime)
            elapsed = datetime.now() - mtime
            if elapsed < timedelta(hours=refresh_interval):
                print(f"Using cached results from file modified at {mtime.isoformat()} (refresh interval {refresh_interval}h).")
                cache_note = f"Data is cached until {(mtime + timedelta(hours=refresh_interval)).isoformat()}. Run with --force-refresh to fetch new results."
                should_use_cache = True

    if should_use_cache:
        print("Using cached report; no new arXiv search is performed.")
        if not args.no_open:
            webbrowser.open(Path(output_name).resolve().as_uri())
            print("Opened cached results in your browser.")
        return

    print(f"Searching arXiv for {len(sections)} section(s)...")
    seen_ids = load_seen_ids(SEEN_STORE)
    section_results: list[dict[str, object]] = []
    total_new = 0
    total_entries = 0

    for section in sections:
        query = build_query(section["keywords"], section["mode"])
        print(f"Searching section '{section['label']}' ({section['mode']}): {section['keywords']}")
        try:
            feed_xml = fetch_feed(query, max_results=section["max_results"])
        except HTTPError as exc:
            print(f"HTTP error for section '{section['label']}': {exc}")
            continue
        except URLError as exc:
            print(f"Network error for section '{section['label']}': {exc}")
            continue
        except Exception as exc:
            print(f"Unexpected error for section '{section['label']}': {exc}")
            continue

        entries = parse_feed(feed_xml)
        print(f"Fetched {len(entries)} arXiv entries for section '{section['label']}'.")

        effective_mode = section["mode"]
        fallback_note = ""
        filtered_entries = filter_entries(entries, section["keywords"], section["mode"])
        if section["mode"] == "majority" and not filtered_entries:
            fallback_note = (
                f"No papers matched the majority keyword requirement. Showing papers that match any keyword instead."
            )
            filtered_entries = filter_entries(entries, section["keywords"], "any")
            effective_mode = "any"

        section_new = 0
        for entry in filtered_entries:
            paper_id = entry["id"]
            is_new = paper_id not in seen_ids
            entry["is_new"] = is_new
            if is_new:
                section_new += 1
                total_new += 1
            seen_ids.add(paper_id)

        total_entries += len(filtered_entries)
        section_results.append({
            "label": section["label"],
            "mode": section["mode"],
            "effective_mode": effective_mode,
            "keywords": section["keywords"],
            "entries": filtered_entries,
            "new_count": section_new,
            "fallback_note": fallback_note,
        })

    print(f"Found {total_entries} papers ({total_new} new) across {len(section_results)} sections.")
    output_path = Path(output_name).resolve()
    write_output(render_html(section_results, refresh_interval, str(config_path), cache_note), output_path)
    save_seen_ids(SEEN_STORE, seen_ids)
    save_state(STATE_STORE, {"last_fetch": datetime.now().isoformat(), "query": current_query})
    print(f"Saved results to: {output_path}")

    if args.notify and total_new > 0:
        latest_title = ""
        for section in section_results:
            if section["entries"]:
                latest_title = html.escape(section["entries"][0]["title"])
                break
        notification_title = f"arXiv alert: {total_new} new paper(s)"
        notification_message = f"{total_new} new paper(s) found across {len(section_results)} sections. Latest: {latest_title}"
        send_notification(notification_title, notification_message)

    if not args.no_open:
        webbrowser.open(output_path.as_uri())
        print("Opened the result page in your browser.")


if __name__ == "__main__":
    main()
