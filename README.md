# 🩺 수의내과 데일리 (vet-gi-digest)

전 세계 신뢰도 높은 수의 내과 저널과 사람 IBD/FMT 논문을 매일 수집하고, Claude가 한국어로 요약해서 **매일 아침 카카오톡 '나와의 채팅'** 으로 보내주는 앱입니다.

```
PubMed 검색 ─▶ 랭킹(근거수준·저널) ─▶ Claude 한국어 요약 ─▶ HTML 리포트(GitHub Pages)
                                                       └▶ 카카오톡 알림 (헤드라인 + 하이라이트)
```

## 무엇을 모으나요?

| 섹션 | 범위 | 깊이 |
|---|---|---|
| **수의 소화기 심층** | 개·고양이 대상 **CIE, PLE, FMT·장내미생물, 췌장염** (+ 림프종·코발라민·급성 설사 등). 핵심 내과 저널 + Front Vet Sci, BMC Vet Res, Animals, Microbiome 등 확장 저널 | 핵심 결과 3–5개, 연구설계, 대상, 임상적 의미, 한계 |
| **수의 내과 일반** | JVIM, JAVMA, JSAP, Vet J, JFMS, Vet Rec, AJVR, JVECC 등 핵심 저널의 내과 논문 (외과·마취·대동물 제외) | 핵심 결과 1–3개 |
| **사람 IBD/FMT** | Gastroenterology, Gut, Lancet Gastroenterol Hepatol, JCC, IBD, NEJM, Lancet 등의 IBD·크론병·UC·FMT 논문 | 핵심 결과 + 개·고양이 진료에 대한 시사점 |

저널·주제·검색식·섹션별 논문 수는 모두 [`config.yaml`](config.yaml)에서 수정할 수 있습니다.
메타분석·RCT·가이드라인·JVIM 등에 가중치를 주어 상위 논문을 고르고, Claude가 매긴 중요도(★1–5) 순으로 정렬합니다.

## 카카오톡 메시지 예시

```
🩺 10/23 수의내과 데일리
수의 소화기 4 · 수의 내과 9 · 사람 IBD/FMT 3

CIE 개에서 FMT 보조요법 RCT와 PLE 예후인자 연구가 나왔습니다…
                                         [전체 리포트]
```
```
[FMT·CIE] ★★★★☆
만성 장병증 개에서 분변미생물이식(FMT) 보조요법의 효과: 무작위 대조시험
FMT군 8주차 CCECAI 유의 감소, 스테로이드 감량률↑
— J Vet Intern Med                              [요약 보기]
```

카카오 텍스트 메시지는 200자 제한이 있어서 핵심만 보내고, 버튼을 누르면 상세 요약 리포트(GitHub Pages)로 이동합니다.

---

## 설치 (약 20분, 1회)

### 1. GitHub 저장소 만들기
이 폴더를 새 GitHub 저장소(예: `vet-gi-digest`)로 올립니다. 리포트가 공개 페이지로 올라가므로 **공개 저장소**를 권장합니다(내용은 공개 논문 요약뿐입니다).

`Settings → Pages` 에서 **Deploy from a branch → `main` / `docs`** 를 선택합니다.
리포트 주소는 `https://<GitHub아이디>.github.io/vet-gi-digest` 가 됩니다.

### 2. Claude API 키
[console.anthropic.com](https://console.anthropic.com) 에서 API 키를 발급합니다.

### 3. 카카오 개발자 앱 설정 ([developers.kakao.com](https://developers.kakao.com))
1. **애플리케이션 추가** → `앱 키`의 **REST API 키** 복사
2. **카카오 로그인** 활성화 → Redirect URI에 `http://localhost:8080` 등록
3. **카카오 로그인 > 동의항목** → **카카오톡 메시지 전송(talk_message)** 사용 설정
4. **플랫폼 > Web** → 사이트 도메인에 다음을 등록 (메시지 버튼 링크용)
   - `https://<GitHub아이디>.github.io`
   - `https://pubmed.ncbi.nlm.nih.gov`
5. (선택) **보안 > Client Secret** 을 켰다면 그 값도 메모

### 4. 카카오 refresh token 발급 (내 PC에서 1회)
```bash
pip install requests
KAKAO_REST_API_KEY=<REST API 키> python scripts/kakao_auth.py
```
안내대로 로그인하면 `refresh_token` 이 출력됩니다.

### 5. GitHub Secrets / Variables 등록
`Settings → Secrets and variables → Actions`

| 종류 | 이름 | 값 | 필수 |
|---|---|---|---|
| Secret | `ANTHROPIC_API_KEY` | Claude API 키 | ✅ |
| Secret | `KAKAO_REST_API_KEY` | 카카오 REST API 키 | ✅ |
| Secret | `KAKAO_REFRESH_TOKEN` | 4단계에서 받은 토큰 | ✅ |
| Secret | `GH_PAT` | Secrets 쓰기 권한이 있는 GitHub 토큰 (fine-grained, 이 저장소의 *Secrets: Read and write*) | 권장 |
| Secret | `KAKAO_CLIENT_SECRET` | Client Secret (켠 경우만) | |
| Secret | `NCBI_API_KEY`, `NCBI_EMAIL` | NCBI 계정의 API 키 / 이메일 (요청 한도↑) | |
| Variable | `REPORT_BASE_URL` | `https://<GitHub아이디>.github.io/vet-gi-digest` | ✅ |

> **`GH_PAT` 가 필요한 이유**: 카카오 refresh token은 약 2개월 유효하고, 만료 1개월 전부터 새 토큰이 발급됩니다. 앱이 새 토큰을 받으면 GitHub Secret을 자동으로 갱신해서 **재로그인 없이 계속** 동작하게 합니다. `GH_PAT` 가 없으면 두 달마다 4단계를 다시 해야 합니다.

### 6. 테스트
`Actions → daily-digest → Run workflow` 에서 `dry_run` 을 체크해서 실행하면 카카오 전송 없이 로그에 메시지가 찍힙니다. 문제없으면 체크 해제 후 한 번 더 실행해 카카오톡 수신을 확인하세요.

이후 **매일 06:37(KST)** 에 자동 실행됩니다. (GitHub 스케줄은 수 분~수십 분 늦어질 수 있어 7시 전에 시작하도록 했습니다. 시간 변경은 `.github/workflows/daily.yml` 의 `cron` 을 UTC 기준으로 수정하세요.)

---

## 로컬 실행

```bash
pip install -r requirements.txt
export PYTHONPATH=src ANTHROPIC_API_KEY=...        # 없으면 요약 없이 원문 제목만 사용
python -m vetdigest run --dry-run                   # 카카오 전송·상태 저장 없이 메시지 미리보기
python -m vetdigest kakao-test                      # 카카오 연결 테스트 (KAKAO_* 환경변수 필요)
python -m vetdigest run                             # 실제 실행
pytest                                              # 테스트
```

생성물: `docs/daily/YYYY-MM-DD.html` (상세 리포트), `docs/index.html` (아카이브), `data/seen.json` (이미 보낸 PMID — 중복 발송 방지, 90일 보관).

## 비용

- PubMed, GitHub Actions(공개 저장소), GitHub Pages, 카카오 메시지 API: 무료
- Claude API: 하루 최대 40편 요약 기준 대략 **하루 0.3–0.7달러 (월 1–3만 원)**. 논문 수가 많은 날 비용을 줄이려면 `config.yaml` 의 `limits` 를 낮추거나 `claude.effort` 를 `low` 로 바꾸세요.

## 구조

```
config.yaml                  저널·주제·검색식·메시지 수 설정
src/vetdigest/pubmed.py      PubMed 검색/파싱, 근거수준 랭킹
src/vetdigest/summarize.py   Claude 한국어 구조화 요약 (섹션별 깊이 차등)
src/vetdigest/compose.py     카카오 메시지 구성 (200자 제한 대응)
src/vetdigest/kakao.py       카카오 토큰 갱신·나에게 보내기
src/vetdigest/report.py      HTML 리포트/아카이브
scripts/kakao_auth.py        최초 refresh token 발급
.github/workflows/daily.yml  매일 아침 자동 실행 + 토큰 자동 갱신 + 리포트 커밋
```

## 한계 / 참고

- 요약은 **초록 기반**입니다. 전문(full text)을 읽지 않으므로 임상 적용 전에는 원문을 확인하세요.
- PubMed 등록(Entrez date) 기준으로 수집하므로, 저널 온라인 게재 후 PubMed 반영까지 며칠 지연될 수 있습니다.
- 카카오 '나에게 보내기'는 본인 계정에만 발송됩니다. 여러 사람에게 보내려면 카카오톡 채널(비즈니스) 알림톡 등 별도 연동이 필요합니다.
