#!/usr/bin/env python3
"""Creatomate 템플릿에 엔딩 페이드아웃(여운) 추가 — 2026-08-09.

## 배경

유저 VOC: "영상 마지막에 바로 끝나는 것보다 여운을 주는 엔딩이 있으면 좋겠다.
막 신나게 이야기하다가 뚝 끊기는 것 같다."

## 왜 스크립트인가

템플릿이 10개(4·5·6·7·8장면 × prod/test)다. 에디터에서 손으로 열 번 반복하면
하나쯤 빠뜨리고, 그러면 **특정 장면 수에서만 페이드가 없는** 상태가 된다.
2026-08-04 자막 MDV 누락, 2026-08-08 test 5장면 템플릿 삭제가 정확히 같은 계열의 사고였다.

## 무엇을 바꾸는가

1. 루트 `fill_color` → 검정. 내용이 페이드아웃하면 이 배경이 드러나므로
   여기가 "어두워지는" 최종 색이다. 원본은 진회색(#333333)이었다.
2. 루트 오디오(배경음악) → `audio_fade_out` 초 단위 지정.
   화면만 어두워지고 BGM 이 그대로 끊기면 "뚝 끊긴다"는 불만이 절반만 해결된다.
3. **마지막** 장면 composition → 끝점 앵커 exit 페이드.
4. 오버레이 composition(제목/로고 등) → 같은 exit 페이드.
   제목 바가 track 4 로 장면 위에 얹혀 있어서, 장면만 페이드하면
   제목 텍스트만 멀쩡히 남았다가 뚝 끊긴다.

`{"type": "fade", "time": "end", "duration": N, "reversed": true}` 는 **끝점 기준**이라
나레이션 길이에 따라 장면 길이가 매번 달라져도 항상 끝 N초에 걸린다.
우리 파이프라인은 composition 시간을 명시하지 않고 자동 시퀀싱에 맡기므로
(`get_creatomate_vars` 는 api/blog.py 에서 import 만 되고 호출되지 않음)
이 자동 앵커링이 사실상 유일하게 안전한 방법이다.

## 사용

    python3 scripts/add_outro_fade.py 원본.json -o 수정본.json
    python3 scripts/add_outro_fade.py 원본.json --check    # 이미 적용됐는지만 확인

여러 번 돌려도 중복 추가되지 않는다(멱등).
"""
import argparse
import json
import re
import sys

# 페이드 길이(초). PO 가 에디터에서 맞춘 값(2026-08-09 레퍼런스 기준).
FADE_DURATION = 0.1
# 배경음악 페이드. 화면(0.1초)보다 훨씬 길어서 소리가 먼저 잦아든다.
AUDIO_FADE_DURATION = 1.5

# 루트 fill_color 는 **키를 제거**한다 (2026-08-09 PO 레퍼런스와 동일).
# 원본은 rgba(51,51,51,1) 진회색이었는데, 내용이 페이드아웃하면 이 색이 드러나서
# 완전히 어두워지지 않는다. 키를 지우면 Creatomate 기본 배경이 적용된다 —
# 실제로 어떤 색으로 렌더되는지는 샘플로 확인할 것.
REMOVE_ROOT_FILL_COLOR = True

SCENE_NAME_RE = re.compile(r"^composition_(\d+)$")


def _fade_animation(duration=FADE_DURATION):
    """끝점에 앵커된 exit 페이드."""
    return {
        "type": "fade",
        "time": "end",
        "duration": duration,
        "reversed": True,
    }


def _has_exit_fade(element):
    for anim in element.get("animations") or []:
        if anim.get("type") == "fade" and anim.get("time") == "end":
            return True
    return False


def _add_exit_fade(element, duration=FADE_DURATION):
    """이미 있으면 건드리지 않는다. 추가했으면 True."""
    if _has_exit_fade(element):
        return False
    element.setdefault("animations", []).append(_fade_animation(duration))
    return True


def classify_root_elements(template):
    """루트 요소를 역할별로 나눈다.

    반환: (마지막 장면 composition, 오버레이 목록, 루트 오디오 목록)

    장면(composition_1..N)은 **마지막 것만** 페이드 대상이다. 앞 장면들은 영상 중간에
    끝나므로 페이드를 걸면 장면 전환마다 화면이 어두워진다.

    오버레이는 영상 끝까지 화면에 보이는 나머지 전부다. composition 뿐 아니라
    **text/shape/image/video 도 포함**한다 — test 템플릿의 워터마크(`Text-4DM`,
    "AUTO SHORT FORM AI")가 루트 track 5 의 text 요소라서, composition 만 훑으면
    워터마크만 페이드에서 빠져 검은 화면에 흰 글씨로 남는다 (2026-08-09 발견).
    """
    scenes = {}
    overlays = []
    audios = []

    for el in template.get("elements", []):
        name = el.get("name") or ""
        el_type = el.get("type")

        if el_type == "audio":
            audios.append(el)
            continue

        match = SCENE_NAME_RE.match(name) if el_type == "composition" else None
        if match:
            scenes[int(match.group(1))] = el
        else:
            # 이름이 아니라 "장면 번호가 아닌 루트 시각 요소" 로 판단한다.
            # composition_title, compostion_logo(오타), Text-4DM(워터마크) 모두 여기로.
            overlays.append(el)

    last_scene = scenes[max(scenes)] if scenes else None
    return last_scene, overlays, audios


def apply_outro_fade(template, fade=FADE_DURATION, audio_fade=AUDIO_FADE_DURATION):
    """템플릿을 제자리에서 수정하고 변경 내역 목록을 반환."""
    changes = []

    if REMOVE_ROOT_FILL_COLOR and "fill_color" in template:
        changes.append(f"루트 fill_color 제거 (원래 {template['fill_color']})")
        del template["fill_color"]

    last_scene, overlays, audios = classify_root_elements(template)

    if last_scene is None:
        raise SystemExit("composition_N 형태의 장면을 찾지 못했습니다 — 템플릿 구조를 확인하세요.")

    if _add_exit_fade(last_scene, fade):
        changes.append(f"{last_scene['name']}: exit 페이드 {fade}초 추가 (마지막 장면)")

    for el in overlays:
        if _add_exit_fade(el, fade):
            changes.append(f"{el['name']}: exit 페이드 {fade}초 추가 (오버레이)")

    for el in audios:
        if el.get("audio_fade_out") != audio_fade:
            changes.append(f"{el['name']}: audio_fade_out {audio_fade}초 (배경음악)")
            el["audio_fade_out"] = audio_fade

    return changes


def verify(template):
    """페이드가 빠짐없이 적용됐는지 검사. 문제 목록을 반환(비어 있으면 정상)."""
    problems = []
    last_scene, overlays, audios = classify_root_elements(template)

    if REMOVE_ROOT_FILL_COLOR and "fill_color" in template:
        problems.append("루트 fill_color 가 남아 있음 — 페이드 후 진회색이 드러남")

    # 에디터에서 타임라인을 드래그하면 animations[].time 에 그 순간의 초가 그대로 박힌다.
    # 장면 길이는 나레이션에 따라 매번 달라지므로, 고정 숫자면 페이드가 아예 안 걸리거나
    # 영상 한가운데서 어두워진 뒤 검은 화면으로 남는다. 반드시 "end" 여야 한다.
    # (2026-08-09 PO 레퍼런스에 composition_5.animations[0].time = 5.354 로 들어와 있었다.)
    for el in template.get("elements", []):
        for anim in el.get("animations") or []:
            if anim.get("type") == "fade" and isinstance(anim.get("time"), (int, float)):
                problems.append(
                    f"{el.get('name')}: 페이드 time 이 고정 숫자({anim['time']}) — "
                    f'장면 길이가 매번 달라지므로 "end" 여야 함'
                )

    if last_scene is not None and not _has_exit_fade(last_scene):
        problems.append(f"{last_scene['name']}(마지막 장면)에 exit 페이드 없음")
    for el in overlays:
        if not _has_exit_fade(el):
            problems.append(f"{el['name']}(오버레이)에 exit 페이드 없음")
    for el in audios:
        if not el.get("audio_fade_out"):
            problems.append(f"{el['name']}(배경음악)에 audio_fade_out 없음")

    # 앞 장면에 페이드가 잘못 붙으면 전환마다 화면이 어두워진다 — 반드시 잡는다.
    scenes = {}
    for el in template.get("elements", []):
        m = SCENE_NAME_RE.match(el.get("name") or "")
        if m and el.get("type") == "composition":
            scenes[int(m.group(1))] = el
    for idx, el in sorted(scenes.items()):
        if idx != max(scenes) and _has_exit_fade(el):
            problems.append(f"{el['name']}: 마지막 장면이 아닌데 페이드가 있음 (전환마다 어두워짐)")

    return problems


def main():
    parser = argparse.ArgumentParser(description="Creatomate 템플릿에 엔딩 페이드 추가")
    parser.add_argument("input", help="원본 템플릿 JSON")
    parser.add_argument("-o", "--output", help="수정본 저장 경로 (생략 시 stdout)")
    parser.add_argument("--check", action="store_true", help="적용 여부만 검사")
    parser.add_argument("--fade", type=float, default=FADE_DURATION, help="화면 페이드 길이(초)")
    parser.add_argument("--audio-fade", type=float, default=AUDIO_FADE_DURATION,
                        help="배경음악 페이드 길이(초)")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        template = json.load(f)

    if args.check:
        problems = verify(template)
        if problems:
            print(f"[FAIL] {args.input}")
            for p in problems:
                print(f"  - {p}")
            sys.exit(1)
        print(f"[OK] {args.input} — 엔딩 페이드 정상 적용됨")
        return

    changes = apply_outro_fade(template, fade=args.fade, audio_fade=args.audio_fade)

    if not changes:
        print("변경 없음 — 이미 적용된 템플릿입니다.", file=sys.stderr)
    else:
        print(f"변경 {len(changes)}건:", file=sys.stderr)
        for c in changes:
            print(f"  - {c}", file=sys.stderr)

    remaining = verify(template)
    if remaining:
        print("\n[경고] 적용 후에도 남은 문제:", file=sys.stderr)
        for p in remaining:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)

    text = json.dumps(template, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"\n저장: {args.output}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
