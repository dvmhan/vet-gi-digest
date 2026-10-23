"""카카오 refresh token 최초 발급 (내 PC에서 1회 실행).

사전 준비 (developers.kakao.com):
  1) 애플리케이션 추가 → [앱 키]의 'REST API 키' 복사
  2) [카카오 로그인] 활성화, Redirect URI 에 http://localhost:8080 등록
  3) [카카오 로그인 > 동의항목] '카카오톡 메시지 전송(talk_message)' 사용 설정
  4) [플랫폼 > Web] 사이트 도메인에 리포트 주소(https://<id>.github.io)와 https://pubmed.ncbi.nlm.nih.gov 등록

실행:
  KAKAO_REST_API_KEY=xxxx python scripts/kakao_auth.py
"""
import os
import sys
import urllib.parse

import requests

REDIRECT = os.environ.get("KAKAO_REDIRECT_URI", "http://localhost:8080")
key = os.environ.get("KAKAO_REST_API_KEY") or input("REST API 키: ").strip()
secret = os.environ.get("KAKAO_CLIENT_SECRET", "")

auth_url = "https://kauth.kakao.com/oauth/authorize?" + urllib.parse.urlencode(
    {"client_id": key, "redirect_uri": REDIRECT, "response_type": "code", "scope": "talk_message"})
print("\n1) 아래 주소를 브라우저에서 열고 카카오 로그인/동의를 진행하세요:\n\n  " + auth_url)
print("\n2) 'localhost 연결 거부' 페이지가 떠도 정상입니다. 주소창의 전체 URL을 복사해 붙여넣으세요.")
redirected = input("\n리다이렉트된 URL: ").strip()
code = urllib.parse.parse_qs(urllib.parse.urlparse(redirected).query).get("code", [redirected])[0]

data = {"grant_type": "authorization_code", "client_id": key, "redirect_uri": REDIRECT, "code": code}
if secret:
    data["client_secret"] = secret
r = requests.post("https://kauth.kakao.com/oauth/token", data=data, timeout=30)
if r.status_code != 200:
    sys.exit(f"토큰 발급 실패: {r.text}")
tok = r.json()
print("\n✅ 발급 성공. GitHub 저장소 Secrets 에 아래 값을 KAKAO_REFRESH_TOKEN 으로 등록하세요:\n")
print(tok["refresh_token"])
print(f"\n(refresh token 유효기간: 약 {tok.get('refresh_token_expires_in', 0) // 86400}일, 자동 갱신됨)")
