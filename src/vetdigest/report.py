"""전체 리포트 HTML 생성 (GitHub Pages 의 docs/ 에 저장)."""
from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path

from .compose import SECTION_NAME, stars
from .models import Article

CSS = """
:root{--bg:#fafaf9;--fg:#1c1917;--muted:#78716c;--card:#fff;--line:#e7e5e4;--accent:#0f766e;--chip:#ccfbf1}
@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--muted:#a8a29e;--card:#292524;--line:#44403c;--accent:#5eead4;--chip:#134e4a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.5rem;margin:0 0 4px}h2{margin:40px 0 8px;font-size:1.2rem;border-bottom:2px solid var(--accent);padding-bottom:4px}
.muted{color:var(--muted);font-size:.9rem}.lead{background:var(--card);border-left:4px solid var(--accent);padding:12px 14px;border-radius:6px}
article{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:14px 0}
article h3{margin:4px 0 2px;font-size:1.05rem}.orig{color:var(--muted);font-size:.85rem;margin:0 0 8px}
.chip{display:inline-block;background:var(--chip);border-radius:999px;padding:0 8px;font-size:.78rem;margin-right:4px}
.stars{color:#d97706;letter-spacing:1px}dl{margin:8px 0 0}dt{font-weight:600;font-size:.85rem;color:var(--accent);margin-top:8px}dd{margin:2px 0 0}
ul{margin:4px 0;padding-left:20px}a{color:var(--accent)}
"""


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{escape(title)}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>")


def _article(a: Article, topic_labels: dict[str, str]) -> str:
    s = a.summary or {}
    chips = "".join(f'<span class="chip">{escape(topic_labels.get(t, t))}</span>' for t in a.tags)
    imp = f'<span class="stars">{stars(s["importance"])}</span>' if s.get("importance") else ""
    title = escape(s.get("title_ko") or a.title)
    meta = f"{escape(a.authors)} · <i>{escape(a.journal)}</i> {escape(a.pub_date)} · {escape(', '.join(a.pub_types[:2]))}"
    links = f'<a href="{a.url}">PubMed</a>' + (f' · <a href="{a.doi_url}">원문(DOI)</a>' if a.doi else "")
    body = ""
    if s:
        rows = [("연구 설계", s.get("study_design")), ("대상", s.get("population"))]
        body += "".join(f"<dt>{k}</dt><dd>{escape(v)}</dd>" for k, v in rows if v)
        if s.get("key_findings"):
            body += "<dt>핵심 결과</dt><dd><ul>" + "".join(f"<li>{escape(x)}</li>" for x in s["key_findings"]) + "</ul></dd>"
        if s.get("clinical_takeaway"):
            body += f"<dt>임상적 의미</dt><dd>{escape(s['clinical_takeaway'])}</dd>"
        if s.get("limitations"):
            body += f"<dt>한계</dt><dd>{escape(s['limitations'])}</dd>"
        body = f"<dl>{body}</dl>"
    else:
        body = f"<p class=\"muted\">{escape(a.abstract[:600])}{'…' if len(a.abstract) > 600 else ''}</p>"
    return (f'<article id="{a.pmid}">{chips}{imp}<h3>{title}</h3>'
            f'<p class="orig">{escape(a.title)}<br>{meta}<br>{links}</p>{body}</article>')


def write_report(docs: Path, day: date, sections: dict[str, list[Article]],
                 summaries: dict[str, str], topic_labels: dict[str, str]) -> Path:
    daily = docs / "daily"
    daily.mkdir(parents=True, exist_ok=True)
    total = sum(len(v) for v in sections.values())
    body = f"<h1>🩺 수의내과 데일리</h1><p class=\"muted\">{day.isoformat()} · 신규 논문 {total}편 · <a href=\"../index.html\">지난 리포트</a></p>"
    for key in ("vet_gi", "human", "vet_im"):
        arts = sections.get(key, [])
        if not arts:
            continue
        body += f"<h2>{SECTION_NAME[key]} <span class=\"muted\">({len(arts)})</span></h2>"
        if summaries.get(key):
            body += f"<p class=\"lead\">{escape(summaries[key])}</p>"
        body += "".join(_article(a, topic_labels) for a in arts)
    if total == 0:
        body += "<p>오늘은 새로 등록된 논문이 없습니다.</p>"
    path = daily / f"{day.isoformat()}.html"
    path.write_text(_page(f"수의내과 데일리 {day.isoformat()}", body), encoding="utf-8")
    _write_index(docs)
    return path


def _write_index(docs: Path) -> None:
    files = sorted((docs / "daily").glob("*.html"), reverse=True)
    items = "".join(f'<li><a href="daily/{f.name}">{f.stem}</a></li>' for f in files)
    (docs / "index.html").write_text(
        _page("수의내과 데일리", f"<h1>🩺 수의내과 데일리 아카이브</h1><ul>{items}</ul>"), encoding="utf-8")
    (docs / ".nojekyll").touch()
