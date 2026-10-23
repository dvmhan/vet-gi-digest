"""실행 진입점: python -m vetdigest run [--dry-run]"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta, timezone

from .compose import build_messages
from .config import ROOT, load_config
from .kakao import KakaoClient
from .pubmed import PubMed, collect
from .report import write_report
from .summarize import Summarizer

log = logging.getLogger("vetdigest")
KST = timezone(timedelta(hours=9))
SEEN_FILE = ROOT / "data" / "seen.json"


def load_seen() -> dict[str, str]:
    return json.loads(SEEN_FILE.read_text()) if SEEN_FILE.exists() else {}


def save_seen(seen: dict[str, str], today: date) -> None:
    cutoff = (today - timedelta(days=90)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    SEEN_FILE.parent.mkdir(exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=0, sort_keys=True))


def run(dry_run: bool, no_kakao: bool) -> None:
    cfg = load_config()
    today = datetime.now(KST).date()
    seen = load_seen()

    sections = collect(cfg, PubMed(), set(seen))
    summarizer = Summarizer(cfg)
    summaries = {sec: summarizer.summarize_section(sec, arts) for sec, arts in sections.items()}

    labels = {k: v["label"] for k, v in cfg["vet_gi_topics"].items()}
    path = write_report(ROOT / "docs", today, sections, summaries, labels)
    log.info("리포트 저장: %s", path)

    base = cfg["kakao"]["report_base_url"]
    messages = build_messages(sections, summaries, base, today, cfg["kakao"]["max_messages"])
    if dry_run or no_kakao:
        for text, url, btn in messages:
            print(f"\n──────── [{btn}] {url}\n{text}")
    else:
        kakao = KakaoClient()
        if not kakao.configured:
            raise SystemExit("KAKAO_REST_API_KEY / KAKAO_REFRESH_TOKEN 이 설정되지 않았습니다.")
        for text, url, btn in messages:
            kakao.send_text(text, url, btn)
        log.info("카카오톡 %d건 전송 완료", len(messages))

    if not dry_run:
        for arts in sections.values():
            for a in arts:
                seen[a.pmid] = today.isoformat()
        save_seen(seen, today)


def kakao_test() -> None:
    kakao = KakaoClient()
    if not kakao.configured:
        raise SystemExit("KAKAO_REST_API_KEY / KAKAO_REFRESH_TOKEN 이 설정되지 않았습니다.")
    kakao.send_text("✅ 수의내과 데일리 연결 테스트 메시지입니다.", "https://pubmed.ncbi.nlm.nih.gov/", "PubMed")
    print("전송 완료 – 카카오톡 '나와의 채팅'을 확인하세요.")


def cli() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="vetdigest")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="논문 수집·요약·리포트·카카오톡 전송")
    r.add_argument("--dry-run", action="store_true", help="카카오 전송/상태 저장 없이 메시지를 화면에 출력")
    r.add_argument("--no-kakao", action="store_true", help="리포트·상태는 저장하되 카카오 전송만 생략")
    sub.add_parser("kakao-test", help="카카오톡 테스트 메시지 전송")
    args = p.parse_args()
    if args.cmd == "run":
        run(args.dry_run, args.no_kakao)
    else:
        kakao_test()


if __name__ == "__main__":
    cli()
