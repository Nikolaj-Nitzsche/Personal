"""Open a browser tab showing the word 'test'."""

import tempfile
import webbrowser
from pathlib import Path
from webbrowser import BackgroundBrowser


def open_in_edge(url: str) -> None:
    edge_paths = [
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for path in edge_paths:
        if Path(path).exists():
            webbrowser.register("edge", None, BackgroundBrowser(path))
            webbrowser.get("edge").open_new_tab(url)
            print("Opened a new browser tab with 'test' in Microsoft Edge.")
            return
    print("Microsoft Edge not found. Opening the default browser instead.")
    webbrowser.open_new_tab(url)


def main() -> None:
    html = """
<html lang='en'>
  <head>
    <meta charset='utf-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>test</title>
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: linear-gradient(135deg, #0f172a, #111827 45%, #1d4ed8 100%);
        color: #f8fafc;
        font-family: Inter, Arial, sans-serif;
      }
      .card {
        padding: 3rem 4rem;
        border-radius: 28px;
        box-shadow: 0 28px 80px rgba(15, 23, 42, 0.25);
        background: rgba(15, 23, 42, 0.88);
        border: 1px solid rgba(148, 163, 184, 0.16);
        text-align: center;
        max-width: 520px;
        width: calc(100% - 32px);
      }
      h1 {
        margin: 0;
        font-size: 4rem;
        letter-spacing: -0.08em;
      }
      p {
        margin: 1.5rem 0 0;
        color: #cbd5e1;
        font-size: 1rem;
        line-height: 1.7;
      }
    </style>
  </head>
  <body>
    <div class='card'>
      <h1>test</h1>
      <p>A simple modern page opened in Microsoft Edge.</p>
    </div>
  </body>
</html>
"""
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as temp_file:
        temp_file.write(html)
        temp_path = Path(temp_file.name)
    open_in_edge(temp_path.as_uri())


if __name__ == "__main__":
    main()
