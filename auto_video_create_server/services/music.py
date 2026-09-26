"""배경음악 선택 — 곡 목록 + 만료되는 재생 주소 (2026-09-27).

## 지금까지

모든 영상에 **같은 배경음악**이 깔렸다. Creatomate 템플릿 루트의 `Audio-6FR`
(volume 15%) 에 템플릿 기본 음원이 박혀 있고, 우리는 그걸 건드린 적이 없다.
유저가 고를 수 없으니 20편을 만들면 20편이 같은 분위기였다.

## 어떻게 고르게 하는가

Pixabay 에서 컨셉 4종 × 5곡을 PO 가 직접 듣고 골랐다. voices.py 와 같은 이유로
**목록을 코드에 둔다** — (1) 요청의 bgm_id 를 그대로 믿으면 유저가 아무 URL 이나
넣어 영상에 실을 수 있고, (2) 이 파일 자체가 곡별 출처·라이선스 기록이 된다.

## 왜 presigned URL 인가 (중요)

Pixabay Content License 는 상업적 이용과 출처 표기 면제를 허용하지만,
**음원 파일을 그대로 재배포하는 것은 금지**한다. mp3 를 공개 버킷에 올리면 그
주소가 곧 상시 음원 배포처가 되어 이 조항에 걸린다. 그래서

  · 파일은 비공개 버킷(`blog-to-short-form-credits`)에 둔다
  · 미리듣기도, Creatomate 에 넘기는 주소도 **만료되는 presigned URL** 로만 만든다

`auto-video-tts-files` 를 쓰지 않은 이유가 이것이다 — 그 버킷은 정책으로
`s3:GetObject` 가 `*` 에 열려 있어 올리는 순간 영구 공개 주소가 된다.

## 기본값은 "건드리지 않는다"

`bgm_id` 를 안 보내면 `Audio-6FR` 에 아무 수정도 넣지 않는다. 즉 템플릿 기본
음악이 그대로 나간다. 구버전 화면에서 온 요청과 기존 유저의 결과물이 바뀌지
않아야 하기 때문이다 (voices.py 의 DEFAULT_VOICE_ID 와 같은 원칙).

"음악 없음"(`NONE_ID`)은 그래서 **명시적으로 골라야만** 적용된다.
"""
from typing import List, Optional

from utils.s3_utils import s3_client

BUCKET = "blog-to-short-form-credits"   # 비공개 버킷. render_store 와 같은 버킷을 재사용한다.
PREFIX = "music"

# Creatomate 템플릿 루트의 배경음악 element. 4~8장면 템플릿 10개 모두 같은 이름이다.
BGM_ELEMENT = "Audio-6FR"

# 유저가 "음악 없음"을 고른 경우. 빈 문자열/None 과 구분해야 한다 —
# 안 보낸 것(기본 유지)과 끄겠다고 고른 것은 다른 의미다.
NONE_ID = "none"

# 미리듣기 주소 수명. 화면에서 목록을 열어 두고 이것저것 들어보는 시간은 넉넉히 덮되,
# 주소가 복사돼 돌아다니지는 않을 만큼만 준다.
PREVIEW_EXPIRES = 600          # 10분
# 렌더용 주소 수명. Creatomate 가 렌더 시작 시점에 내려받는다. 큐가 밀려도 남도록 1시간.
RENDER_EXPIRES = 3600

CONCEPTS = [
    {"id": "bright", "label": "밝은 일상", "description": "가볍고 경쾌한 일상 브이로그"},
    {"id": "calm", "label": "차분한 정보", "description": "설명·정보 전달에 어울리는 잔잔한 곡"},
    {"id": "upbeat", "label": "경쾌한 리듬", "description": "속도감 있고 리듬이 또렷한 곡"},
    {"id": "emotional", "label": "감성 기록", "description": "어쿠스틱·서정적인 분위기"},
]

# 곡 목록 = 라이선스 기록. 전부 Pixabay Content License (상업적 이용 가능, 출처 표기 불필요).
# seconds 는 파일 크기 ÷ 256kbps 로 낸 근삿값 — 가장 짧은 곡도 70초라, 우리 영상
# (16~30초)은 어떤 곡을 골라도 중간에 끊기지 않는다.
_LICENSE = "Pixabay Content License"
_LICENSE_URL = "https://pixabay.com/service/license-summary/"

TRACKS: List[dict] = [
    # --- 밝은 일상 ---
    {"id": "bright-indie-fun", "concept": "bright", "title": "Indie Fun",
     "artist": "JonasBlakewood", "seconds": 133,
     "source_page": "https://pixabay.com/music/indie-pop-indie-fun-595510/"},
    {"id": "bright-joyful-walk", "concept": "bright", "title": "Joyful Rhythm Walk Funk",
     "artist": "LightBeatsMusic", "seconds": 138,
     "source_page": "https://pixabay.com/music/funk-joyful-rhythm-walk-funk-513936/"},
    {"id": "bright-water-afropop", "concept": "bright", "title": "Water (Afro-pop)",
     "artist": "kontraa", "seconds": 70,
     "source_page": "https://pixabay.com/music/afrobeat-water-afro-pop-music-445661/"},
    {"id": "bright-upbeat-corporate", "concept": "bright", "title": "Upbeat Corporate",
     "artist": "PaulYudin", "seconds": 92,
     "source_page": "https://pixabay.com/music/corporate-upbeat-corporate-corporate-music-595943/"},
    {"id": "bright-exciting", "concept": "bright", "title": "Exciting",
     "artist": "lNPLUSMUSIC", "seconds": 98,
     "source_page": "https://pixabay.com/music/alternative-exciting-exciting-music-607838/"},
    # --- 차분한 정보 ---
    {"id": "calm-cinematic-documentary", "concept": "calm", "title": "Cinematic Documentary",
     "artist": "Lexin_Music", "seconds": 132,
     "source_page": "https://pixabay.com/music/beautiful-plays-cinematic-documentary-115669/"},
    {"id": "calm-reflected-light", "concept": "calm", "title": "Reflected Light",
     "artist": "SergePavkinMusic", "seconds": 225,
     "source_page": "https://pixabay.com/music/beautiful-plays-reflected-light-147979/"},
    {"id": "calm-ambient-piano-strings", "concept": "calm", "title": "Ambient Piano and Strings",
     "artist": "Good_B_Music", "seconds": 217,
     "source_page": "https://pixabay.com/music/beautiful-plays-ambient-piano-and-strings-10711/"},
    {"id": "calm-inspiring-cinematic", "concept": "calm", "title": "Inspiring Cinematic Ambient",
     "artist": "Lexin_Music", "seconds": 190,
     "source_page": "https://pixabay.com/music/beautiful-plays-inspiring-cinematic-ambient-116199/"},
    {"id": "calm-midnight-forest", "concept": "calm", "title": "Midnight Forest",
     "artist": "Syouki_Takahashi", "seconds": 168,
     "source_page": "https://pixabay.com/music/ambient-midnight-forest-184304/"},
    # --- 경쾌한 리듬 ---
    {"id": "upbeat-summer-pop", "concept": "upbeat", "title": "Summer Pop",
     "artist": "JonasBlakewood", "seconds": 133,
     "source_page": "https://pixabay.com/music/pop-summer-pop-546980/"},
    {"id": "upbeat-coffees-cold", "concept": "upbeat", "title": "Coffee's Cold",
     "artist": "vibemode", "seconds": 160,
     "source_page": "https://pixabay.com/music/rock-upbeat-coffeex27s-cold-545907/"},
    {"id": "upbeat-upbeat-music", "concept": "upbeat", "title": "Upbeat Music",
     "artist": "prettyjohn1", "seconds": 103,
     "source_page": "https://pixabay.com/music/pop-upbeat-music-524228/"},
    {"id": "upbeat-pop-music", "concept": "upbeat", "title": "Pop Music",
     "artist": "TheMountain", "seconds": 101,
     "source_page": "https://pixabay.com/music/pop-pop-pop-music-576583/"},
    {"id": "upbeat-indie-rock-dreamy", "concept": "upbeat", "title": "Indie Rock Dreamy",
     "artist": "alex-morgan", "seconds": 188,
     "source_page": "https://pixabay.com/music/rock-indie-rock-dreamy-537459/"},
    # --- 감성 기록 ---
    {"id": "emotional-leva-eternity", "concept": "emotional", "title": "Leva - Eternity",
     "artist": "lemonmusicstudio", "seconds": 145,
     "source_page": "https://pixabay.com/music/acoustic-group-leva-eternity-149473/"},
    {"id": "emotional-coniferous-forest", "concept": "emotional", "title": "Coniferous Forest",
     "artist": "orangery", "seconds": 128,
     "source_page": "https://pixabay.com/music/acoustic-group-coniferous-forest-142569/"},
    {"id": "emotional-beat-of-nature", "concept": "emotional", "title": "The Beat of Nature",
     "artist": "folkacoustic", "seconds": 173,
     "source_page": "https://pixabay.com/music/solo-guitar-the-beat-of-nature-122841/"},
    {"id": "emotional-sunrise-travel", "concept": "emotional", "title": "Acoustic Guitar Sunrise Travel",
     "artist": "alex-morgan", "seconds": 149,
     "source_page": "https://pixabay.com/music/folk-acoustic-guitar-sunrise-travel-573651/"},
    {"id": "emotional-moment", "concept": "emotional", "title": "Moment",
     "artist": "SergeQuadrado", "seconds": 213,
     "source_page": "https://pixabay.com/music/modern-jazz-moment-14023/"},
]

for _t in TRACKS:
    _t.setdefault("license", _LICENSE)
    _t.setdefault("license_url", _LICENSE_URL)

_BY_ID = {t["id"]: t for t in TRACKS}


def s3_key(track_id: str) -> str:
    return f"{PREFIX}/{track_id}.mp3"


def is_allowed(track_id) -> bool:
    """고를 수 있는 곡인지. NONE_ID 는 곡이 아니므로 여기서는 False."""
    return isinstance(track_id, str) and track_id in _BY_ID


def get_track(track_id) -> Optional[dict]:
    return _BY_ID.get(track_id) if isinstance(track_id, str) else None


def _presigned(track_id: str, expires: int) -> Optional[str]:
    try:
        return s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": s3_key(track_id)},
            ExpiresIn=expires,
        )
    except Exception as e:
        # 주소를 못 만들면 그 곡만 빠진다. 목록 전체나 영상 생성을 실패시키지 않는다.
        print(f"[music] presigned 실패 track={track_id}: {e}")
        return None


def preview_url(track_id: str) -> Optional[str]:
    return _presigned(track_id, PREVIEW_EXPIRES)


def render_url(track_id: str) -> Optional[str]:
    return _presigned(track_id, RENDER_EXPIRES)


def available_tracks() -> dict:
    """FE 노출용 목록. 컨셉과 곡을 나눠서 준다.

    preview_url 은 만료되므로 FE 가 저장해 두고 재사용하면 안 된다 —
    화면을 열 때마다 이 엔드포인트를 다시 부르는 것을 전제로 한다.
    """
    return {
        "none_id": NONE_ID,
        "concepts": CONCEPTS,
        "tracks": [
            {
                "id": t["id"],
                "concept": t["concept"],
                "title": t["title"],
                "artist": t["artist"],
                "seconds": t["seconds"],
                "license": t["license"],
                "preview_url": preview_url(t["id"]),
            }
            for t in TRACKS
        ],
    }


def bgm_variables(bgm_id) -> dict:
    """Creatomate modifications 에 넣을 배경음악 설정.

    · 안 보냈거나 모르는 값  → `{}` (템플릿 기본 음악 그대로 — 기존 동작)
    · NONE_ID               → 볼륨 0%
    · 목록에 있는 곡        → presigned URL 로 교체

    "음악 없음"을 `source` 제거가 아니라 **볼륨 0%** 로 구현한 이유: 템플릿의
    `Audio-6FR` 은 source 가 Creatomate 자산 ID 로 박혀 있고, modifications 로
    source 를 빈 값으로 만들었을 때의 동작이 문서에 없다. 400 을 맞으면 영상 생성
    자체가 실패한다. 볼륨 0% 는 이미 문자열 퍼센트(`"15%"`)로 들어 있는 속성을
    같은 형식으로 덮는 것이라 확실하고, 들리는 결과는 같다.
    """
    if bgm_id == NONE_ID:
        return {f"{BGM_ELEMENT}.volume": "0%"}
    if not is_allowed(bgm_id):
        return {}
    url = render_url(bgm_id)
    if not url:
        # 주소를 못 만들었으면 기본 음악으로 흐른다. 무음보다 낫고, 실패시키는 건 더 나쁘다.
        return {}
    return {f"{BGM_ELEMENT}.source": url}
