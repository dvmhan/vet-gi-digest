"""카카오톡 '나에게 보내기' (Kakao Talk Message API)."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import requests

from .config import ROOT

log = logging.getLogger(__name__)

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
TEXT_LIMIT = 200          # 텍스트 템플릿 최대 글자 수
LOCAL_TOKEN_FILE = ROOT / ".kakao_tokens.json"


def clip(text: str, limit: int = TEXT_LIMIT) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


class KakaoClient:
    """REST API 키 + refresh token 으로 access token 을 발급받아 메시지를 보냅니다.

    refresh token 은 약 2개월 유효하며, 만료 1개월 전부터 갱신 시 새 토큰이 발급됩니다.
    새 토큰은 로컬 파일(.kakao_tokens.json)에 저장하고, KAKAO_NEW_TOKEN_FILE 이 지정되어 있으면
    그 경로에도 써서 GitHub Actions 가 Secret 을 갱신할 수 있게 합니다.
    """

    def __init__(self):
        self.rest_key = os.environ.get("KAKAO_REST_API_KEY", "")
        self.client_secret = os.environ.get("KAKAO_CLIENT_SECRET", "")
        saved = {}
        if LOCAL_TOKEN_FILE.exists():
            saved = json.loads(LOCAL_TOKEN_FILE.read_text())
        self.refresh_token = saved.get("refresh_token") or os.environ.get("KAKAO_REFRESH_TOKEN", "")
        self.access_token = ""

    @property
    def configured(self) -> bool:
        return bool(self.rest_key and self.refresh_token)

    def refresh(self) -> None:
        data = {"grant_type": "refresh_token", "client_id": self.rest_key, "refresh_token": self.refresh_token}
        if self.client_secret:
            data["client_secret"] = self.client_secret
        r = requests.post(TOKEN_URL, data=data, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"카카오 토큰 갱신 실패 ({r.status_code}): {r.text}\n"
                               "→ refresh token 만료 시 scripts/kakao_auth.py 를 다시 실행하세요.")
        tok = r.json()
        self.access_token = tok["access_token"]
        if new := tok.get("refresh_token"):
            log.info("카카오 refresh token 이 갱신되었습니다.")
            self.refresh_token = new
            LOCAL_TOKEN_FILE.write_text(json.dumps({"refresh_token": new}))
            if out := os.environ.get("KAKAO_NEW_TOKEN_FILE"):
                Path(out).write_text(new)

    def send_text(self, text: str, url: str, button: str = "자세히 보기") -> None:
        if not self.access_token:
            self.refresh()
        template = {
            "object_type": "text",
            "text": clip(text),
            "link": {"web_url": url, "mobile_web_url": url},
            "button_title": button[:14],
        }
        r = requests.post(
            MEMO_URL,
            headers={"Authorization": f"Bearer {self.access_token}"},
            data={"template_object": json.dumps(template, ensure_ascii=False)},
            timeout=30,
        )
        if r.status_code != 200 or r.json().get("result_code") != 0:
            raise RuntimeError(f"카카오 메시지 전송 실패 ({r.status_code}): {r.text}")
