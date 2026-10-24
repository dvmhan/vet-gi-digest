"""GitHub Actions 에서 카카오 인가 코드 → refresh token 교환 후 Secret 저장 + 테스트 메시지 전송."""
import json
import os
import subprocess
import sys
import urllib.parse

import requests

REDIRECT = "http://localhost:8080"


def fail(msg: str) -> None:
    print("::error::" + msg.replace("\n", "%0A"))
    sys.exit(1)


raw = os.environ.get("REDIRECT_URL", "").strip()
code = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query).get("code", [raw])[0]
if not code:
    fail("붙여넣은 주소에 code 가 없습니다. http://localhost:8080/?code=... 전체를 붙여넣으세요.")
print(f"::add-mask::{code}")

key = os.environ.get("KAKAO_REST_API_KEY", "").strip()
if not key:
    fail("Secrets 에 KAKAO_REST_API_KEY 가 없습니다.")
if not os.environ.get("GH_TOKEN"):
    fail("Secrets 에 GH_PAT 가 없습니다. (토큰을 저장하려면 필요)")

data = {"grant_type": "authorization_code", "client_id": key, "redirect_uri": REDIRECT, "code": code}
if s := os.environ.get("KAKAO_CLIENT_SECRET", "").strip():
    data["client_secret"] = s
r = requests.post("https://kauth.kakao.com/oauth/token", data=data, timeout=30)
if r.status_code != 200:
    hint = "로그인 링크를 다시 열어 새 주소로 10분 안에 재시도하세요. (주소는 1회용)"
    if "KOE010" in r.text:
        hint = ("앱 인증 실패: KAKAO_REST_API_KEY 값 확인, 클라이언트 시크릿이 켜져 있으면 KAKAO_CLIENT_SECRET 등록 필요"
                + (" (현재 시크릿 등록됨 – 값이 맞는지 확인)" if s else " (현재 시크릿 미등록)"))
    elif "KOE320" in r.text:
        hint = "주소가 이미 사용됐거나 만료됨. 로그인 링크를 다시 열어 새 주소로 재시도하세요."
    fail(f"카카오 토큰 발급 실패: {r.text}\n→ {hint}")
tok = r.json()
for k in ("access_token", "refresh_token"):
    print(f"::add-mask::{tok[k]}")
if "talk_message" not in tok.get("scope", ""):
    fail("'카카오톡 메시지 전송' 동의가 빠졌습니다. 로그인 링크를 다시 열어 체크 후 재시도하세요.")

tmpl = {"object_type": "text", "text": "✅ 수의내과 위클리 카카오톡 연결 완료!\n매주 월요일 아침에 논문 요약이 도착합니다.",
        "link": {"web_url": "https://pubmed.ncbi.nlm.nih.gov/", "mobile_web_url": "https://pubmed.ncbi.nlm.nih.gov/"}}
m = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
                  headers={"Authorization": f"Bearer {tok['access_token']}"},
                  data={"template_object": json.dumps(tmpl, ensure_ascii=False)}, timeout=30)
if not m.ok:
    fail(f"카카오 메시지 전송 실패: {m.text}")
print("::notice::테스트 메시지 전송 성공")

p = subprocess.run(["gh", "secret", "set", "KAKAO_REFRESH_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
                   input=tok["refresh_token"], text=True, capture_output=True)
if p.returncode != 0:
    fail(f"KAKAO_REFRESH_TOKEN 저장 실패 (GH_PAT 권한 확인: 이 저장소 + Secrets Read and write): {p.stderr.strip()}")
print("::notice::KAKAO_REFRESH_TOKEN 저장 완료 – 설정 끝!")
