"""GitHub Actions 에서 카카오 인가 코드 → refresh token 교환 후 Secret 저장 + 테스트 메시지 전송."""
import json
import os
import subprocess
import sys
import urllib.parse

import requests

REDIRECT = "http://localhost:8080"
raw = os.environ["REDIRECT_URL"].strip()
code = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query).get("code", [raw])[0]
print(f"::add-mask::{code}")

data = {"grant_type": "authorization_code", "client_id": os.environ["KAKAO_REST_API_KEY"],
        "redirect_uri": REDIRECT, "code": code}
if s := os.environ.get("KAKAO_CLIENT_SECRET"):
    data["client_secret"] = s
r = requests.post("https://kauth.kakao.com/oauth/token", data=data, timeout=30)
if r.status_code != 200:
    sys.exit(f"토큰 발급 실패: {r.text}\n→ 로그인 링크를 다시 열어 새 주소로 10분 안에 재시도하세요.")
tok = r.json()
for k in ("access_token", "refresh_token"):
    print(f"::add-mask::{tok[k]}")

subprocess.run(["gh", "secret", "set", "KAKAO_REFRESH_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
               input=tok["refresh_token"], text=True, check=True)
print("✅ KAKAO_REFRESH_TOKEN 저장 완료")

tmpl = {"object_type": "text", "text": "✅ 수의내과 데일리 카카오톡 연결 완료!\n내일 아침부터 논문 요약이 도착합니다.",
        "link": {"web_url": "https://pubmed.ncbi.nlm.nih.gov/", "mobile_web_url": "https://pubmed.ncbi.nlm.nih.gov/"}}
m = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
                  headers={"Authorization": f"Bearer {tok['access_token']}"},
                  data={"template_object": json.dumps(tmpl, ensure_ascii=False)}, timeout=30)
print("테스트 메시지:", "전송 성공" if m.ok else f"실패 {m.text}")
