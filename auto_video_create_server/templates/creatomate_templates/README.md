# Creatomate 템플릿 JSON

장면 수(4~8) × 환경(prod/test) = **10개** 템플릿의 JSON 사본.

## 왜 리포에 두는가

템플릿은 Creatomate 웹 에디터에만 존재해서, 누가 언제 무엇을 바꿨는지 알 방법이 없었다.
실제로 이런 일들이 있었다.

- **2026-08-04** — 3번 슬롯 자막(`Subtitles-MDV`)이 빠진 줄 알고 코드에서 제외했는데,
  실제 템플릿에는 있었다. 에디터의 "API 사용" 예시가 `dynamic: true` 없는 요소를
  빼고 보여준 탓이었다. 그 결과 3번 장면만 템플릿 기본 폰트로 렌더됐다.
- **2026-08-08** — test 5장면 템플릿이 Creatomate 에서 삭제됐는데 **나흘간 아무도 몰랐다.**
  유저가 영상 생성에 실패하고 제보해서야 알았다.
- **2026-08-09** — `prod_8_slot` 원본 export 파일이 저장 중 비워졌다.

JSON 을 리포에 두면 diff 로 변경을 추적할 수 있고, 위 같은 사고에서 복원할 수 있다.

## 구조

```
source/       원본 (Creatomate 에서 export 한 그대로)
outro_fade/   엔딩 페이드 적용본 — 이걸 Creatomate 에 붙여넣는다
```

파일명은 `{환경}_{장면수}_slot[_outro_fade].json`.

## prod / test 차이

test 템플릿에는 루트 track 5 에 워터마크(`Text-4DM`, "AUTO SHORT FORM AI")가 있고
prod 에는 없다. **prod 에 test 템플릿 ID 가 들어가면 워터마크가 찍힌 영상이 고객에게
나간다** — `services/scene_counts.py` 의 테스트가 이를 강제한다.

## 엔딩 페이드

유저 VOC("영상이 뚝 끊겨서 여운이 없다")로 2026-08-09 에 추가했다.

| 대상 | 설정 |
|---|---|
| 마지막 장면 composition | exit 페이드 0.1초 |
| 오버레이 (제목/로고/워터마크) | exit 페이드 0.1초 |
| 배경음악 `Audio-6FR` | `audio_fade_out` 1.5초 |
| 루트 `fill_color` | 키 제거 (페이드 후 드러나는 배경) |

`"time": "end"` 로 **끝점에 앵커**하는 게 핵심이다. 마지막 장면의 길이는 나레이션에
따라 매번 달라지므로, 에디터에서 타임라인을 드래그해 생기는 고정 숫자(예: `5.354`)를
쓰면 짧은 나레이션에선 페이드가 안 걸리고 긴 나레이션에선 한가운데서 어두워진 채
검은 화면으로 남는다.

## 도구

```bash
# 원본에 엔딩 페이드 적용
python3 scripts/add_outro_fade.py source/prod_5_slot.json -o outro_fade/prod_5_slot_outro_fade.json

# 적용 여부 검사 (고정 숫자 time 도 함께 잡는다)
python3 scripts/add_outro_fade.py outro_fade/prod_5_slot_outro_fade.json --check

# 10개 템플릿이 Creatomate 에 실제로 존재하는지 + 페이드가 들어갔는지
CREATOMATE_API_KEY=... python3 scripts/verify_templates.py
```

템플릿을 바꾸면 `source/` 를 다시 export 해서 갱신하고, `--check` 를 10개 전부
돌려두는 것을 권한다. "특정 장면 수만 누락"이 이 프로젝트에서 반복된 사고 유형이다.
