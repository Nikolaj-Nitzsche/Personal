import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "arxiv_paper_finder.py"


def test_storage_paths_are_relative_to_script_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("arxiv_paper_finder", None)

    spec = importlib.util.spec_from_file_location("arxiv_paper_finder", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    script_dir = MODULE_PATH.resolve().parent
    assert module.SEEN_STORE == script_dir / ".arxiv_seen.json"
    assert module.CONFIG_STORE == script_dir / ".arxiv_config.json"
    assert module.STATE_STORE == script_dir / ".arxiv_state.json"


def test_render_html_keeps_new_badges_for_new_entries():
    spec = importlib.util.spec_from_file_location("arxiv_paper_finder", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    html = module.render_html(
        [
            {
                "label": "General NV centers",
                "mode": "majority",
                "effective_mode": "majority",
                "keywords": ["NV centers"],
                "entries": [
                    {
                        "id": "123",
                        "title": "Example paper",
                        "summary": "A test summary",
                        "published": "2026-07-29",
                        "authors": "A. Author",
                        "categories": "quant-ph",
                        "comment": "",
                        "journal_ref": "",
                        "link": "https://example.com",
                        "is_new": True,
                    }
                ],
                "new_count": 1,
                "fallback_note": "",
            }
        ],
        refresh_interval=12,
        config_path=".arxiv_config.json",
    )

    assert '<span class="badge">NEW</span>' in html
