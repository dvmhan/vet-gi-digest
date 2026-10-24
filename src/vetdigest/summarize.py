"""Claude로 논문 초록을 한국어로 요약."""
from __future__ import annotations

import json
import logging
import os

import anthropic

from .models import Article

log = logging.getLogger(__name__)

SYSTEM = """당신은 소동물 내과(특히 소화기) 전문 수의사를 위한 학술 큐레이터입니다.
주어진 PubMed 논문 초록만 근거로 한국어 요약을 작성합니다.

원칙:
- 초록에 없는 수치나 결론을 지어내지 않습니다. 초록이 없으면 제목 수준에서만 요약하고 그렇게 밝힙니다.
- 질환명·약물명·검사명은 한국어 뒤 괄호에 영문을 병기합니다. 예: 단백소실성 장병증(PLE), 부데소나이드(budesonide).
- 연구 설계, 대상(종·두수/환자 수), 핵심 수치(민감도, 생존기간, OR/HR, p값 등)를 우선 담습니다.
- 'clinical_takeaway'는 임상 현장에서 진료 방식이 바뀌는지, 아직 근거가 약한지를 솔직하게 씁니다.
- 'importance'는 임상적 파급력과 근거 수준을 함께 고려한 1–5 점수입니다(5=진료 지침을 바꿀 수준, 1=예비/증례).
- 'kakao_line'은 카카오톡 알림용 한 줄(공백 포함 80자 이내)로, 핵심 결과를 담습니다."""

SECTION_GUIDE = {
    "vet_gi": "수의 소화기 심층 섹션입니다. 만성 염증성 장병증(CIE), 단백소실성 장병증(PLE), 분변미생물이식(FMT)·장내미생물, 췌장염은 독자의 핵심 관심사이므로 key_findings를 3–5개로 자세히, 방법론적 한계도 구체적으로 적어주세요.",
    "vet_im": "수의 내과 일반 섹션입니다. key_findings는 1–3개로 간결하게 적어주세요.",
    "human": "사람 IBD·크론병·궤양성대장염·FMT 섹션입니다. key_findings는 2–3개로 적고, clinical_takeaway에는 사람 의학 결과가 개·고양이 소화기 진료에 주는 시사점(있다면)을 함께 적어주세요.",
}

ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "pmid": {"type": "string"},
        "title_ko": {"type": "string"},
        "study_design": {"type": "string"},
        "population": {"type": "string"},
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "clinical_takeaway": {"type": "string"},
        "limitations": {"type": "string"},
        "importance": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "kakao_line": {"type": "string"},
    },
    "required": ["pmid", "title_ko", "study_design", "population", "key_findings",
                 "clinical_takeaway", "limitations", "importance", "kakao_line"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {
        "section_summary": {"type": "string", "description": "이 섹션 오늘 동향 2–3문장"},
        "items": {"type": "array", "items": ITEM_SCHEMA},
    },
    "required": ["section_summary", "items"],
    "additionalProperties": False,
}


def _render(a: Article) -> str:
    tags = f"\n주제 태그: {', '.join(a.tags)}" if a.tags else ""
    return (f"<article pmid=\"{a.pmid}\">\n제목: {a.title}\n저널: {a.journal_full} ({a.journal}), {a.pub_date}"
            f"\n출판 유형: {', '.join(a.pub_types)}{tags}\n초록:\n{a.abstract or '(초록 없음)'}\n</article>")


class Summarizer:
    def __init__(self, cfg: dict):
        self.model = cfg["claude"]["model"]
        self.effort = cfg["claude"].get("effort", "medium")
        self.enabled = bool(os.environ.get("ANTHROPIC_API_KEY"))
        self.client = anthropic.Anthropic() if self.enabled else None

    def summarize_section(self, section: str, arts: list[Article]) -> str:
        """arts[i].summary 를 채우고 섹션 요약 문자열을 반환."""
        if not arts:
            return ""
        if not self.enabled:
            log.warning("ANTHROPIC_API_KEY 없음 – 요약 없이 원문 제목만 사용")
            return ""
        prompt = (f"{SECTION_GUIDE[section]}\n\n아래 {len(arts)}편 각각에 대해 요약하세요. "
                  "pmid는 그대로 돌려주세요.\n\n" + "\n\n".join(_render(a) for a in arts))
        try:
            with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=64000,
                system=SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": SCHEMA}},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                msg = stream.get_final_message()
        except anthropic.RateLimitError as e:
            log.error("Claude 요청 한도 초과: %s", e)
            print(f"::warning::Claude 요청 한도 초과 ({section})")
            return ""
        except anthropic.APIStatusError as e:
            log.error("Claude API 오류 %s: %s", e.status_code, e.message)
            print(f"::warning::Claude API 오류 {e.status_code} ({section}): {e.message}")
            return ""
        except anthropic.APIConnectionError as e:
            log.error("Claude 연결 실패: %s", e)
            print(f"::warning::Claude 연결 실패 ({section})")
            return ""

        if msg.stop_reason in ("refusal", "max_tokens"):
            log.error("요약 중단 (stop_reason=%s)", msg.stop_reason)
            print(f"::warning::요약 중단 stop_reason={msg.stop_reason} ({section})")
            return ""
        text = next((b.text for b in msg.content if b.type == "text"), "")
        data = json.loads(text)
        by_id = {it["pmid"]: it for it in data["items"]}
        for a in arts:
            a.summary = by_id.get(a.pmid)
        # 중요도 높은 순으로 재정렬
        arts.sort(key=lambda a: ((a.summary or {}).get("importance", 0), a.score), reverse=True)
        return data["section_summary"]
