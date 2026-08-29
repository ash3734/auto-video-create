'use client';

/**
 * 나레이션 음성 선택 + 미리듣기 (2026-08-17).
 *
 * ## 미리듣기는 유저의 실제 스크립트로 만든다
 * 제네릭한 샘플 문장 대신 화면에 이미 떠 있는 **스크립트 1**을 읽힌다. 자기 콘텐츠가
 * 그 목소리로 어떻게 들리는지가 진짜 판단 근거이기 때문이다. 음성끼리 비교하려면
 * 텍스트가 같아야 하므로 기준 문장은 하나로 고정한다. (PO 제안)
 *
 * ## 이 컴포넌트가 책임지는 것
 * - 동시에 하나만 재생 — 다른 ▶ 를 누르면 이전 재생은 즉시 멈춘다
 * - 생성 중 로딩 표시 — 첫 재생은 API 호출이라 1초 안팎 걸린다. 스피너가 없으면
 *   "눌렀는데 반응이 없다"가 된다 (2026-08-06 에 같은 문제를 겪었다)
 * - 실패해도 선택은 계속 가능 — 미리듣기는 부가 기능이고 영상 제작이 본체다
 *
 * ## 배속 (2026-08-29)
 * 음성과 배속은 같이 듣고 정하는 것이라 한 블록에 둔다. 미리듣기도 선택한 배속으로
 * 나가므로 **만들기 전에 실제 결과물과 같은 속도**를 확인할 수 있다.
 * 배속은 상대값이고 1배가 지금까지의 속도라, 안 건드리면 결과물이 그대로다.
 */
import * as React from 'react';
import { Box, Typography, CircularProgress, IconButton } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import RefreshIcon from '@mui/icons-material/Refresh';

export type Voice = {
  voice_id: string;
  name: string;
  description: string;
  is_default: boolean;
};

export type Speed = {
  value: number;
  name: string;
  description: string;
  is_default: boolean;
};

type Props = {
  voices: Voice[];
  selected: string;
  onSelect: (voiceId: string) => void;
  /** 선택 가능한 배속. 목록을 못 받으면 빈 배열 → 배속 UI 를 숨긴다 */
  speeds: Speed[];
  selectedSpeed: number;
  onSelectSpeed: (value: number) => void;
  /** 미리듣기 기준 문장 — select 화면의 스크립트 1 */
  previewText: string;
  /** 스크립트 편집 중이거나 영상 생성 중이면 잠근다 */
  disabled?: boolean;
  /** 기준 문장이 확정되지 않은 이유 (편집 중 등). 있으면 미리듣기만 막는다 */
  previewBlockedReason?: string | null;
  apiBaseUrl: string;
  authHeaders: () => Record<string, string>;
};

export default function VoicePicker({
  voices,
  selected,
  onSelect,
  speeds,
  selectedSpeed,
  onSelectSpeed,
  previewText,
  disabled = false,
  previewBlockedReason = null,
  apiBaseUrl,
  authHeaders,
}: Props) {
  const [loadingId, setLoadingId] = React.useState<string | null>(null);
  const [playingId, setPlayingId] = React.useState<string | null>(null);
  const [errorId, setErrorId] = React.useState<string | null>(null);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);
  // (voice_id → url) 로컬 캐시. 서버도 S3 로 캐시하지만, 같은 세션에서 재생할 때
  // 네트워크 왕복 자체를 없애 즉시 재생되게 한다.
  const urlCache = React.useRef<Record<string, string>>({});

  const stop = React.useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setPlayingId(null);
  }, []);

  // 화면을 벗어나면 소리가 남지 않도록 정리한다.
  React.useEffect(() => stop, [stop]);

  // 기준 문장이나 배속이 바뀌면 캐시를 버린다 — 옛 음성이 재생되면 안 된다.
  // 배속을 빼먹으면 0.7배를 고르고도 앞서 받아둔 1.25배 음성이 흘러나온다.
  React.useEffect(() => {
    urlCache.current = {};
    stop();
  }, [previewText, selectedSpeed, stop]);

  const play = async (voiceId: string) => {
    if (playingId === voiceId) {
      stop();
      return;
    }
    stop();
    setErrorId(null);

    const cached = urlCache.current[voiceId];
    if (cached) {
      startAudio(voiceId, cached);
      return;
    }

    setLoadingId(voiceId);
    try {
      const res = await fetch(`${apiBaseUrl}/api/blog/voice-preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ voice_id: voiceId, text: previewText, speed: selectedSpeed }),
      });
      const data = await res.json();
      if (data?.status !== 'success' || !data?.url) {
        console.error('[shorts] 음성 미리듣기 실패', data);
        setErrorId(voiceId);
        return;
      }
      urlCache.current[voiceId] = data.url;
      startAudio(voiceId, data.url);
    } catch (e) {
      console.error('[shorts] 음성 미리듣기 예외', e);
      setErrorId(voiceId);
    } finally {
      setLoadingId(null);
    }
  };

  const startAudio = (voiceId: string, url: string) => {
    const audio = new Audio(url);
    audio.onended = () => setPlayingId(null);
    audio.onerror = () => {
      setErrorId(voiceId);
      setPlayingId(null);
    };
    audioRef.current = audio;
    setPlayingId(voiceId);
    void audio.play().catch(() => {
      setErrorId(voiceId);
      setPlayingId(null);
    });
  };

  const previewDisabled = disabled || !!previewBlockedReason || !previewText.trim();

  return (
    <Box sx={{ mb: 2 }}>
      <Typography sx={{ fontSize: 13, fontWeight: 700, mb: 0.5 }}>
        음성
        <Box component="span" sx={{ fontSize: 11, fontWeight: 500, color: '#888', ml: 1 }}>
          {previewBlockedReason ?? '▶ 로 스크립트 1을 들어보세요'}
        </Box>
      </Typography>

      <Box sx={{ border: '1px solid #e3e6ef', borderRadius: 2, overflow: 'hidden' }}>
        {voices.map((v, i) => {
          const isSelected = selected === v.voice_id;
          const isLoading = loadingId === v.voice_id;
          const isPlaying = playingId === v.voice_id;
          const isError = errorId === v.voice_id;
          return (
            <Box
              key={v.voice_id}
              onClick={() => !disabled && onSelect(v.voice_id)}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.25,
                px: 1.5,
                py: 1.25,
                cursor: disabled ? 'default' : 'pointer',
                opacity: disabled ? 0.5 : 1,
                borderBottom: i === voices.length - 1 ? 'none' : '1px solid #e3e6ef',
                bgcolor: isSelected ? 'rgba(25, 118, 210, 0.07)' : '#fff',
                boxShadow: isSelected ? 'inset 3px 0 0 #1976d2' : 'none',
                transition: 'background-color 0.15s',
              }}
            >
              <Box
                sx={{
                  width: 17,
                  height: 17,
                  borderRadius: '50%',
                  border: `2px solid ${isSelected ? '#1976d2' : '#bbb'}`,
                  display: 'grid',
                  placeItems: 'center',
                  flex: '0 0 auto',
                }}
              >
                {isSelected && (
                  <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#1976d2' }} />
                )}
              </Box>

              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontSize: 13.5, fontWeight: 700, lineHeight: 1.3 }}>
                  {v.name}
                </Typography>
                <Typography
                  sx={{ fontSize: 11.5, color: isError ? '#c62828' : '#888', lineHeight: 1.4 }}
                >
                  {isError
                    ? '들려드리지 못했어요. 다시 시도해주세요'
                    : `${v.description}${v.is_default ? ' · 기본' : ''}`}
                </Typography>
              </Box>

              <IconButton
                size="small"
                disabled={previewDisabled || isLoading}
                onClick={e => {
                  e.stopPropagation(); // 재생만 하고 선택은 바뀌지 않게
                  void play(v.voice_id);
                }}
                sx={{
                  border: `1.5px solid ${isError ? '#c62828' : '#1976d2'}`,
                  color: isPlaying ? '#fff' : isError ? '#c62828' : '#1976d2',
                  bgcolor: isPlaying ? '#1976d2' : 'transparent',
                  width: 32,
                  height: 32,
                  '&:hover': { bgcolor: isPlaying ? '#1565c0' : 'rgba(25, 118, 210, 0.08)' },
                }}
                aria-label={`${v.name} 음성 미리듣기`}
              >
                {isLoading ? (
                  <CircularProgress size={14} />
                ) : isError ? (
                  <RefreshIcon sx={{ fontSize: 16 }} />
                ) : isPlaying ? (
                  <PauseIcon sx={{ fontSize: 16 }} />
                ) : (
                  <PlayArrowIcon sx={{ fontSize: 18 }} />
                )}
              </IconButton>
            </Box>
          );
        })}
      </Box>

      {/* 배속 — 목록을 못 받으면 통째로 숨긴다. 서버가 기본값(1배)으로 처리하므로
          UI 가 없다고 영상 생성이 막히지는 않는다. */}
      {speeds.length > 0 && (
        <Box sx={{ mt: 1.5 }}>
          <Typography sx={{ fontSize: 13, fontWeight: 700, mb: 0.5 }}>
            말하는 속도
            <Box component="span" sx={{ fontSize: 11, fontWeight: 500, color: '#888', ml: 1 }}>
              ▶ 로 바뀐 속도를 들어볼 수 있어요
            </Box>
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            {speeds.map(s => {
              const isSelected = Math.abs(selectedSpeed - s.value) < 1e-6;
              return (
                <Box
                  key={s.value}
                  onClick={() => !disabled && onSelectSpeed(s.value)}
                  sx={{
                    flex: 1,
                    textAlign: 'center',
                    py: 0.9,
                    borderRadius: 2,
                    cursor: disabled ? 'default' : 'pointer',
                    opacity: disabled ? 0.5 : 1,
                    border: `1.5px solid ${isSelected ? '#1976d2' : '#e3e6ef'}`,
                    bgcolor: isSelected ? 'rgba(25, 118, 210, 0.07)' : '#fff',
                    transition: 'background-color 0.15s',
                  }}
                >
                  <Typography
                    sx={{
                      fontSize: 13.5,
                      fontWeight: 700,
                      lineHeight: 1.3,
                      color: isSelected ? '#1976d2' : '#333',
                    }}
                  >
                    {s.name}
                  </Typography>
                  <Typography sx={{ fontSize: 11, color: '#888', lineHeight: 1.4 }}>
                    {s.description}
                  </Typography>
                </Box>
              );
            })}
          </Box>
        </Box>
      )}
    </Box>
  );
}
