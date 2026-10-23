"""카카오톡 메시지 구성."""
from __future__ import annotations

from datetime import date

from .models import Article

SECTION_NAME = {"vet_gi": "수의 소화기", "vet_im": "수의 내과", "human": "사람 IBD/FMT"}


def stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def report_url(base: str, day: date, anchor: str = "") -> str:
    if not base:
        return ""
    return f"{base}/daily/{day.isoformat()}.html" + (f"#{anchor}" if anchor else "")


def item_message(a: Article, base: str, day: date) -> tuple[str, str, str]:
    s = a.summary or {}
    tag = "·".join(a.tags) if a.tags else SECTION_NAME[a.section]
    head = f"[{tag}]"
    if imp := s.get("importance"):
        head += f" {stars(imp)}"
    title = s.get("title_ko") or a.title
    line = s.get("kakao_line", "")
    text = f"{head}\n{title}\n\n{line}\n— {a.journal}".replace("\n\n\n", "\n\n")
    url = report_url(base, day, a.pmid) or a.url
    return text, url, "요약 보기" if base else "PubMed"


def build_messages(sections: dict[str, list[Article]], summaries: dict[str, str],
                   base: str, day: date, max_messages: int) -> list[tuple[str, str, str]]:
    counts = {k: len(v) for k, v in sections.items()}
    total = sum(counts.values())
    head = f"🩺 {day:%m/%d} 수의내과 데일리\n" + " · ".join(f"{SECTION_NAME[k]} {n}" for k, n in counts.items())
    if total == 0:
        return [(head + "\n\n오늘은 새로 등록된 논문이 없습니다.", base or "https://pubmed.ncbi.nlm.nih.gov/", "열기")]
    lead = summaries.get("vet_gi") or summaries.get("vet_im") or summaries.get("human") or ""
    msgs = [(f"{head}\n\n{lead}".strip(), report_url(base, day) or "https://pubmed.ncbi.nlm.nih.gov/", "전체 리포트")]

    # 하이라이트 우선순위: 소화기 심층 → 사람 IBD/FMT 1편 → 내과 일반 1편 → 남은 소화기
    gi, hu, im = sections.get("vet_gi", []), sections.get("human", []), sections.get("vet_im", [])
    picks = gi[:3] + hu[:1] + im[:1] + gi[3:] + hu[1:] + im[1:]
    for a in picks[: max(0, max_messages - 1)]:
        msgs.append(item_message(a, base, day))
    return msgs
