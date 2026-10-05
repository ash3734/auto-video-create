'use client';

/**
 * 내가 만든 영상 (2026-10-05, 백로그 4-1).
 *
 * ## 왜 필요한가
 * 지금까지 완성 영상은 **만든 그 화면에서만** 볼 수 있었다. 기다리다 창을 닫거나 이미지
 * 선택으로 돌아가면 크레딧은 빠졌는데 영상을 다시 찾을 방법이 없었다. 서버는 2026-09-20
 * 부터 렌더 기록을 남기고 있었고, 이 화면이 그 기록을 보여준다.
 *
 * ## 별도 페이지가 아니라 창(Dialog)인 이유
 * 영상을 만드는 중간(대본·이미지를 고르는 중)에 열어도 작업이 날아가지 않아야 한다.
 * 페이지를 옮기면 page.tsx 의 상태가 전부 사라진다.
 *
 * ## 주소는 열 때마다 새로 받는다
 * 영상 주소는 1시간 뒤 만료되는 presigned URL 이다. 받아 둔 목록을 다시 쓰면 오래 열어
 * 둔 뒤에는 재생이 안 된다.
 */
import * as React from 'react';
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  IconButton,
  Typography,
  useMediaQuery,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import CloseIcon from '@mui/icons-material/Close';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import RefreshIcon from '@mui/icons-material/Refresh';
import DownloadIcon from '@mui/icons-material/Download';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '';

type RenderState = 'ready' | 'making' | 'failed' | 'expired';

type MyVideo = {
  render_id: string;
  title: string | null;
  scene_count: number | null;
  duration: number | null;
  submitted_at: string | null;
  state: RenderState;
  video_url: string | null;
  download_url: string | null;
};

const STATE_LABEL: Record<Exclude<RenderState, 'ready'>, string> = {
  making: '만드는 중',
  failed: '만들지 못했어요',
  expired: '보관 기간이 지났어요',
};

function formatDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('ko-KR', {
    timeZone: 'Asia/Seoul',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDuration(sec: number | null): string {
  if (!sec || sec <= 0) return '';
  const s = Math.round(sec);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export default function MyVideosButton() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(false);
  const [videos, setVideos] = React.useState<MyVideo[]>([]);
  const [playing, setPlaying] = React.useState<MyVideo | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const userId = localStorage.getItem('user_id') ?? '';
      const res = await fetch(`${API_BASE_URL}/api/blog/my-renders`, {
        headers: { 'X-USER-ID': userId },
      });
      const data = await res.json();
      if (!res.ok || !Array.isArray(data?.renders)) throw new Error(`status ${res.status}`);
      setVideos(data.renders);
    } catch (e) {
      console.error('[shorts] 내 영상 목록 로드 실패', e);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  const openDialog = () => {
    setOpen(true);
    setPlaying(null);
    void load();
  };

  const close = () => {
    setOpen(false);
    setPlaying(null);
  };

  const makingCount = videos.filter(v => v.state === 'making').length;

  return (
    <>
      <Button
        variant="contained"
        color="primary"
        size="small"
        disableElevation
        sx={{ fontWeight: 700, borderRadius: 2, px: { xs: 1.25, sm: 2 }, minWidth: 0, py: 0.5, whiteSpace: 'nowrap' }}
        onClick={openDialog}
      >
        내 영상
      </Button>

      <Dialog
        open={open}
        onClose={close}
        fullScreen={isMobile}
        fullWidth
        maxWidth="md"
        slotProps={{ paper: { sx: { borderRadius: isMobile ? 0 : 3, minHeight: isMobile ? undefined : '70vh' } } }}
      >
        {/* 머리글 */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            px: { xs: 1, sm: 2 },
            py: 1.25,
            borderBottom: '1px solid #eee',
          }}
        >
          {playing ? (
            <IconButton onClick={() => setPlaying(null)} aria-label="목록으로">
              <ArrowBackIcon />
            </IconButton>
          ) : (
            <Box sx={{ width: 8 }} />
          )}
          <Typography sx={{ fontSize: 17, fontWeight: 700, flex: 1, minWidth: 0 }} noWrap>
            {playing ? playing.title || '제목 없음' : '내가 만든 영상'}
          </Typography>
          {!playing && (
            <IconButton onClick={() => void load()} disabled={loading} aria-label="새로고침">
              <RefreshIcon />
            </IconButton>
          )}
          <IconButton onClick={close} aria-label="닫기">
            <CloseIcon />
          </IconButton>
        </Box>

        {/* 본문 */}
        <Box sx={{ p: { xs: 2, sm: 3 }, flex: 1, overflowY: 'auto' }}>
          {playing ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
              <Box
                sx={{
                  width: 360,
                  maxWidth: '100%',
                  aspectRatio: '9 / 16',
                  maxHeight: isMobile ? '68vh' : '62vh',
                  bgcolor: '#111',
                  borderRadius: 3,
                  overflow: 'hidden',
                }}
              >
                <video
                  key={playing.render_id}
                  src={playing.video_url ?? undefined}
                  controls
                  autoPlay
                  playsInline
                  style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
                />
              </Box>
              <Typography sx={{ fontSize: 13, color: '#888' }}>
                {[formatDate(playing.submitted_at), formatDuration(playing.duration)].filter(Boolean).join(' · ')}
              </Typography>
              {playing.download_url && (
                <Button
                  component="a"
                  href={playing.download_url}
                  download
                  variant="contained"
                  startIcon={<DownloadIcon />}
                  sx={{ fontWeight: 700, borderRadius: 2, px: 3 }}
                >
                  다운로드
                </Button>
              )}
            </Box>
          ) : loading && videos.length === 0 ? (
            <Box sx={{ display: 'grid', placeItems: 'center', py: 10 }}>
              <CircularProgress size={28} />
            </Box>
          ) : error ? (
            <Box sx={{ textAlign: 'center', py: 8 }}>
              <Typography sx={{ color: '#666', mb: 2 }}>목록을 불러오지 못했어요.</Typography>
              <Button variant="outlined" onClick={() => void load()}>
                다시 시도
              </Button>
            </Box>
          ) : videos.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 8 }}>
              <Typography sx={{ fontWeight: 700, mb: 1 }}>아직 만든 영상이 없어요</Typography>
              <Typography sx={{ fontSize: 13, color: '#888' }}>
                영상을 만들면 여기에 모여요. 9월 20일 이후에 만든 영상부터 보여요.
              </Typography>
            </Box>
          ) : (
            <>
              {makingCount > 0 && (
                <Typography sx={{ fontSize: 13, color: '#1976d2', mb: 1.5 }}>
                  만드는 중인 영상이 {makingCount}개 있어요. 잠시 뒤 새로고침해 보세요.
                </Typography>
              )}
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(3, 1fr)', md: 'repeat(4, 1fr)' },
                  gap: { xs: 1.5, sm: 2 },
                }}
              >
                {videos.map(v => {
                  const ready = v.state === 'ready' && !!v.video_url;
                  return (
                    <Box
                      key={v.render_id}
                      onClick={() => ready && setPlaying(v)}
                      sx={{
                        cursor: ready ? 'pointer' : 'default',
                        borderRadius: 2,
                        overflow: 'hidden',
                        border: '1px solid #e3e6ef',
                        bgcolor: '#fff',
                        transition: 'box-shadow 0.15s',
                        '&:hover': ready ? { boxShadow: '0 4px 16px rgba(0,0,0,0.08)' } : undefined,
                      }}
                    >
                      <Box
                        sx={{
                          position: 'relative',
                          aspectRatio: '9 / 16',
                          bgcolor: '#f1f3f6',
                          display: 'grid',
                          placeItems: 'center',
                        }}
                      >
                        {ready ? (
                          // 썸네일 대신 영상 첫 장면. #t=0.5 를 붙여야 iOS 사파리도 첫 프레임을 그린다.
                          <video
                            src={`${v.video_url}#t=0.5`}
                            preload="metadata"
                            muted
                            playsInline
                            style={{
                              position: 'absolute',
                              inset: 0,
                              width: '100%',
                              height: '100%',
                              objectFit: 'cover',
                              pointerEvents: 'none',
                            }}
                          />
                        ) : v.state === 'making' ? (
                          <CircularProgress size={22} />
                        ) : null}
                        {!ready && (
                          <Typography
                            sx={{
                              position: 'absolute',
                              bottom: 10,
                              left: 0,
                              right: 0,
                              textAlign: 'center',
                              fontSize: 12,
                              fontWeight: 600,
                              color: v.state === 'failed' ? '#c62828' : '#666',
                            }}
                          >
                            {STATE_LABEL[v.state as Exclude<RenderState, 'ready'>] ?? ''}
                          </Typography>
                        )}
                        {ready && v.duration ? (
                          <Box
                            sx={{
                              position: 'absolute',
                              right: 6,
                              bottom: 6,
                              bgcolor: 'rgba(0,0,0,0.6)',
                              color: '#fff',
                              fontSize: 11,
                              fontWeight: 600,
                              px: 0.75,
                              py: 0.1,
                              borderRadius: 1,
                            }}
                          >
                            {formatDuration(v.duration)}
                          </Box>
                        ) : null}
                      </Box>
                      <Box sx={{ px: 1.25, py: 1 }}>
                        <Typography noWrap sx={{ fontSize: 13.5, fontWeight: 700 }}>
                          {v.title || '제목 없음'}
                        </Typography>
                        <Typography noWrap sx={{ fontSize: 11.5, color: '#888' }}>
                          {formatDate(v.submitted_at)}
                        </Typography>
                      </Box>
                    </Box>
                  );
                })}
              </Box>
              <Typography sx={{ fontSize: 12, color: '#aaa', mt: 2.5, textAlign: 'center' }}>
                최근 30편까지 보여요. 9월 20일 이후에 만든 영상부터 모여 있어요.
              </Typography>
            </>
          )}
        </Box>
      </Dialog>
    </>
  );
}
