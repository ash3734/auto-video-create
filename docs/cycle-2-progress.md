# Cycle 2 Progress — 일반 블로그 지원 추가

PR: [#40](https://github.com/ash3734/auto-video-create/pull/40)
브랜치: `feat/cycle-2-general-blog-support`
시작일: 2026-05-10

---

## Phase 진행 현황

- [x] **B-0 architect** — 시스템 설계 / API 계약 / 데이터 모델 (2026-05-10)
- [x] **B-0.5 branch-prep** — 브랜치 + Draft PR #40 (2026-05-10)
- [x] **B-1 infra** — 2026-05-15 ✅
- [ ] **B-3 frontend** — pending
- [ ] **B-2 backend** — pending
- [ ] **C-0 QA** — pending
- [ ] **release: test 머지 → 검증 → prod 머지** — pending

---

## B-1 (infra) — 완료

### 작업
- AWS Lambda 환경변수 점검 (test/prod 양쪽)
  - `OPENAI_API_KEY` / `CREATOMATE_API_KEY` / `SUPERTONE_API_KEY` / `ALLOWED_ORIGINS` 모두 존재
  - `ENV` 값 분리 확인: test Lambda = `test` / prod Lambda = `production`
- S3 fallback 이미지 업로드
  - 경로: `s3://auto-video-tts-files/static/default-bg.png` (1080×1920 PNG, 29 KB)
  - 공개 URL: https://auto-video-tts-files.s3.ap-northeast-2.amazonaws.com/static/default-bg.png
  - 내용: 비주얼 스펙의 `linear-gradient(135deg, #e8f0fe → #f3f4f6)` 를 PNG export
  - 용도: `services/ai_background.py` 의 DALL-E 호출 실패 시 fallback
- 신규 terraform / AWS 리소스 변경 없음

### B-2 backend 인계 사항
- `services/ai_background.py` 에서 fallback URL 사용:
  ```
  https://auto-video-tts-files.s3.ap-northeast-2.amazonaws.com/static/default-bg.png
  ```
- 또는 환경변수 `DEFAULT_BG_URL` 로 분리하고 싶다면 Lambda 환경변수에 추가 필요 (선택)
- DALL-E 3 호출에는 기존 `OPENAI_API_KEY` 그대로 사용

### 변경 없음
- `infra/main.tf` 14 개 리소스 모두 변경 없음
- IAM Role / Policy / API Gateway / Amplify 모두 변경 없음
- 신규 secret 없음
