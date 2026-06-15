from __future__ import annotations

import base64
import html
import mimetypes
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "PPS_USER_GUIDE.md"
HTML_OUT = ROOT / "tmp" / "pdfs" / "PPS_USER_GUIDE.html"
PDF_OUT = ROOT / "PPS_USER_GUIDE.pdf"


def main() -> int:
    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    HTML_OUT.write_text(markdown_to_html(GUIDE.read_text(encoding="utf-8")), encoding="utf-8")
    browser = find_browser()
    if not browser:
        raise SystemExit("Chrome or Edge not found; cannot render PDF.")
    if PDF_OUT.exists():
        PDF_OUT.unlink()
    with tempfile.TemporaryDirectory(prefix="sylabys-guide-pdf-") as user_data:
        cmd = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            f"--user-data-dir={user_data}",
            f"--print-to-pdf={PDF_OUT}",
            HTML_OUT.resolve().as_uri(),
        ]
        subprocess.run(cmd, check=True)
    if not PDF_OUT.exists() or PDF_OUT.stat().st_size == 0:
        raise SystemExit("PDF was not created.")
    return 0


def find_browser() -> Path | None:
    for name in ("chrome", "msedge", "chromium", "google-chrome", "microsoft-edge"):
        found = shutil.which(name)
        if found:
            return Path(found)
    for candidate in (
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ):
        if candidate.exists():
            return candidate
    return None


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    in_code = False
    in_ul = False
    in_ol = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    for line in lines:
        raw = line.rstrip()
        if raw.startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                close_lists()
                out.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            out.append(html.escape(raw) + "\n")
            continue
        if not raw.strip():
            close_lists()
            continue
        image = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", raw.strip())
        if image:
            close_lists()
            alt, src = image.groups()
            out.append(render_image(alt, src))
            continue
        if raw.startswith("#"):
            close_lists()
            level = len(raw) - len(raw.lstrip("#"))
            title = raw[level:].strip()
            level = max(1, min(level, 4))
            out.append(f"<h{level}>{inline(title)}</h{level}>")
            continue
        if raw.startswith("- "):
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline(raw[2:].strip())}</li>")
            continue
        numbered = re.match(r"(\d+)\.\s+(.*)", raw)
        if numbered:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{inline(numbered.group(2).strip())}</li>")
            continue
        close_lists()
        if raw.startswith("http://") or raw.startswith("https://"):
            safe = html.escape(raw)
            out.append(f'<p><a href="{safe}">{safe}</a></p>')
        else:
            out.append(f"<p>{inline(raw)}</p>")
    close_lists()
    body = "".join(out)
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Инструкция для ППС - Sylabys Syllabus Checker</title>
<style>
@page {{ size: A4; margin: 14mm 13mm 15mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Arial, "Segoe UI", sans-serif; color: #111827; font-size: 11px; line-height: 1.42; }}
h1 {{ font-size: 24px; margin: 0 0 14px; }}
h2 {{ font-size: 17px; margin: 20px 0 8px; padding-top: 8px; border-top: 1px solid #d1d5db; page-break-after: avoid; }}
h3 {{ font-size: 13px; margin: 14px 0 6px; page-break-after: avoid; }}
p {{ margin: 5px 0; }}
ul, ol {{ margin: 5px 0 8px 18px; padding: 0; }}
li {{ margin: 2px 0; }}
a {{ color: #1d4ed8; text-decoration: none; }}
pre {{ white-space: pre-wrap; background: #f3f4f6; border: 1px solid #d1d5db; padding: 7px 9px; border-radius: 6px; margin: 7px 0 10px; page-break-inside: avoid; }}
code {{ font-family: Consolas, "Courier New", monospace; font-size: 10px; background: #f3f4f6; padding: 1px 3px; border-radius: 3px; }}
pre code {{ background: transparent; padding: 0; }}
figure {{ margin: 9px 0 14px; page-break-inside: avoid; }}
img {{ display: block; max-width: 100%; max-height: 160mm; object-fit: contain; border: 1px solid #d1d5db; border-radius: 6px; }}
figcaption {{ font-size: 10px; color: #4b5563; margin-top: 4px; }}
strong {{ font-weight: 700; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def render_image(alt: str, src: str) -> str:
    path = (ROOT / src).resolve()
    if not path.exists():
        return f"<p><strong>Изображение не найдено:</strong> {html.escape(src)}</p>"
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    uri = f"data:{mime};base64,{data}"
    return f'<figure><img src="{uri}" alt="{html.escape(alt)}"><figcaption>{html.escape(alt)}</figcaption></figure>'


def inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


if __name__ == "__main__":
    raise SystemExit(main())
