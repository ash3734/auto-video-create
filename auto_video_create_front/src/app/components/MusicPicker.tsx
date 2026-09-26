'use client';

/**
 * 배경음악 선택 + 미리듣기 (2026-09-27).
 *
 * ## 세 가지 상태를 구분한다
 * - `''`  기본 음악  → BE 에 bgm_id 를 **안 보낸다**. 템플릿에 박힌 지금까지의 음악이
 *                     그대로 나간다. 초기 선택값이라, 아무것도 안 만지면 결과물이 그대로다.
 * - `'none'` 음악 없음 → 명시적으로 골라야만 적용된다 (BE 가 볼륨 0% 로 처리)
 * - 곡 id        → 고른 곡
 *
 * "기본 음악"을 화면에 노출하는 이유는, 한 번 곡을 골랐다가 **원래대로 되돌릴 방법**이
 * 있어야 하기 때문이다. 이 선택지가 없으면 되돌리려고 '음악 없음'을 고르게 된다.
 *
 * ## 미리듣기 주소는 만료된다
 * Pixabay 라이선스가 음원 파일의 재배포를 금지해서, BE 가 **10분짜리 presigned URL**
 * 로만 준다. 화면을 오래 열어 두면 403 이 나므로, 재생 실패 시 목록을 한 번 다시
 * 받아 재시도한다 (`onExpired`). 이게 없으면 "아까는 되던 ▶ 가 안 된다"가 된다.
 *
 * ## 동시에 하나만 재생
 * VoicePicker 와 같은 규칙. 다른 ▶ 를 누르면 이전 재생은 즉시 멈춘다. 두 컴포넌트가
 * 한 화면에 있으므로 나레이션과 배경음악이 겹쳐 들릴 수 있는데, 이건 의도한 동작이
 * 아니라 각자 멈추는 책임만 진다 — 겹쳐 듣고 싶은 경우가 실제로 있다.
 */
import * as React from 'react';
import { Box, Typography, CircularProgress, IconButton } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import RefreshIcon from '@mui/icons-material/Refresh';

export type MusicTrack = {
  id: string;
  concept: string;
  title: string;
  artist: string;
  seconds: number;
  license: string;
  preview_url: string | null;
};

export type MusicConcept = {
  id: string;
  label: string;
  description: string;
};

/** 기본 음악 = BE 에 아무것도 안 보내는 상태. 빈 문자열로 표현한다. */
export const BGM_TEMPLATE_DEFAULT = '';

type Props = {
  concepts: MusicConcept[];
  tracks: MusicTrack[];
  /** 'none' 은 서버가 알려준 none_id */
  noneId: string;
  selected: string;
  onSelect: (bgmId: string) => void;
  /** 미리듣기 주소가 만료됐을 때 목록을 다시 받아온다. 새 목록을 돌려주면 재시도한다. */
  onExpired: () => Promise<MusicTrack[] | null>;
  disabled?: boolean;
};

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

export default function MusicPicker({
  concepts,
  tracks,
  noneId,
  selected,
  onSelect,
  onExpired,
  disabled = false,
}: Props) {
  const [activeConcept, setActiveConcept] = React.useState(concepts[0]?.id ?? '');
  const [loadingId, setLoadingId] = React.useState<string | null>(null);
  const [playingId, setPlayingId] = React.useState<string | null>(null);
  const [errorId, setErrorId] = React.useState<string | null>(null);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);

  // 고른 곡이 다른 컨셉에 있으면 그 탭을 열어 둔다 — 2페이지로 돌아왔을 때
  // 내가 뭘 골랐는지 안 보이면 고른 적이 없는 것처럼 느껴진다.
  React.useEffect(() => {
    const t = tracks.find(x => x.id === selected);
    if (t) setActiveConcept(t.concept);
  }, [selected, tracks]);

  const stop = React.useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setPlayingId(null);
  }, []);

  // 화면을 벗어나면 소리가 남지 않도록 정리한다.
  React.useEffect(() => stop, [stop]);

  const startAudio = (id: string, url: string, onFail: () => void) => {
    const audio = new Audio(url);
    audio.onended = () => setPlayingId(null);
    audio.onerror = () => {
      setPlayingId(null);
      onFail();
    };
    audioRef.current = audio;
    setPlayingId(id);
    void audio.play().catch(() => {
      setPlayingId(null);
      onFail();
    });
  };

  const play = async (track: MusicTrack) => {
    if (playingId === track.id) {
      stop();
      return;
    }
    stop();
    setErrorId(null);

    if (!track.preview_url) {
      setErrorId(track.id);
      return;
    }

    // 1차 시도. 실패하면 주소 만료로 보고 목록을 다시 받아 한 번만 더 시도한다.
    startAudio(track.id, track.preview_url, () => {
      setLoadingId(track.id);
      void (async () => {
        try {
          const fresh = await onExpired();
          const again = fresh?.find(t => t.id === track.id);
          if (again?.preview_url) {
            startAudio(track.id, again.preview_url, () => setErrorId(track.id));
          } else {
            setErrorId(track.id);
          }
        } catch {
          setErrorId(track.id);
        } finally {
          setLoadingId(null);
        }
      })();
    });
  };

  const row = (
    key: string,
    value: string,
    name: string,
    sub: string,
    track: MusicTrack | null,
    last: boolean,
  ) => {
    const isSelected = selected === value;
    const isLoading = track ? loadingId === track.id : false;
    const isPlaying = track ? playingId === track.id : false;
    const isError = track ? errorId === track.id : false;
    return (
      <Box
        key={key}
        onClick={() => !disabled && onSelect(value)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.25,
          px: 1.5,
          py: 1.25,
          cursor: disabled ? 'default' : 'pointer',
          opacity: disabled ? 0.5 : 1,
          borderBottom: last ? 'none' : '1px solid #e3e6ef',
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
          {isSelected && <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#1976d2' }} />}
        </Box>

        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography noWrap sx={{ fontSize: 13.5, fontWeight: 700, lineHeight: 1.3 }}>
            {name}
          </Typography>
          <Typography
            noWrap
            sx={{ fontSize: 11.5, color: isError ? '#c62828' : '#888', lineHeight: 1.4 }}
          >
            {isError ? '들려드리지 못했어요. 다시 시도해주세요' : sub}
          </Typography>
        </Box>

        {track && (
          <IconButton
            size="small"
            disabled={disabled || isLoading}
            onClick={e => {
              e.stopPropagation(); // 재생만 하고 선택은 바뀌지 않게
              void play(track);
            }}
            sx={{
              border: `1.5px solid ${isError ? '#c62828' : '#1976d2'}`,
              color: isPlaying ? '#fff' : isError ? '#c62828' : '#1976d2',
              bgcolor: isPlaying ? '#1976d2' : 'transparent',
              width: 32,
              height: 32,
              flex: '0 0 auto',
              '&:hover': { bgcolor: isPlaying ? '#1565c0' : 'rgba(25, 118, 210, 0.08)' },
            }}
            aria-label={`${name} 미리듣기`}
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
        )}
      </Box>
    );
  };

  // concepts 가 늦게 도착하면 activeConcept 가 빈 값일 수 있다 — 그러면 곡이
  // 한 개도 안 보이는 화면이 된다. 목록에 없는 값이면 첫 컨셉으로 떨어뜨린다.
  const concept = concepts.some(c => c.id === activeConcept)
    ? activeConcept
    : concepts[0]?.id ?? '';
  const shown = tracks.filter(t => t.concept === concept);

  return (
    <Box sx={{ mb: 2 }}>
      <Typography sx={{ fontSize: 13, fontWeight: 700, mb: 0.5 }}>
        배경음악
        <Box component="span" sx={{ fontSize: 11, fontWeight: 500, color: '#888', ml: 1 }}>
          ▶ 로 미리 들어보세요
        </Box>
      </Typography>

      {/* 컨셉 탭 */}
      <Box sx={{ display: 'flex', gap: 0.75, mb: 1, flexWrap: 'wrap' }}>
        {concepts.map(c => {
          const isActive = concept === c.id;
          return (
            <Box
              key={c.id}
              onClick={() => !disabled && setActiveConcept(c.id)}
              title={c.description}
              sx={{
                px: 1.5,
                py: 0.6,
                borderRadius: 5,
                cursor: disabled ? 'default' : 'pointer',
                opacity: disabled ? 0.5 : 1,
                border: `1.5px solid ${isActive ? '#1976d2' : '#e3e6ef'}`,
                bgcolor: isActive ? 'rgba(25, 118, 210, 0.07)' : '#fff',
                transition: 'background-color 0.15s',
              }}
            >
              <Typography
                sx={{ fontSize: 12.5, fontWeight: 700, color: isActive ? '#1976d2' : '#555' }}
              >
                {c.label}
              </Typography>
            </Box>
          );
        })}
      </Box>

      <Box sx={{ border: '1px solid #e3e6ef', borderRadius: 2, overflow: 'hidden' }}>
        {row('default', BGM_TEMPLATE_DEFAULT, '기본 음악', '지금까지 쓰던 음악 그대로', null, false)}
        {row('none', noneId, '음악 없음', '나레이션만 나가요', null, false)}
        {shown.map((t, i) =>
          row(
            t.id,
            t.id,
            t.title,
            `${t.artist} · ${fmt(t.seconds)}`,
            t,
            i === shown.length - 1,
          ),
        )}
      </Box>
    </Box>
  );
}
