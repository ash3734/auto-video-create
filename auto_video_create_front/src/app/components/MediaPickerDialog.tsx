'use client';

/**
 * 장면 하나에 넣을 사진·영상 고르기 (2026-10-20).
 *
 * 자동 추천으로 칸이 다 채워지면, 그 사진을 바꾸는 방법이 "X 로 비우고 → 오른쪽에서 다시
 * 누르기" 또는 "끌어다 놓기" 뿐이었다. 칸이 다 차 있을 때 갤러리를 누르면 **아무 일도
 * 일어나지 않았다**. 모바일은 장면 카드에 고른 사진조차 안 보였다. PO: "이미지를 바꿀 수
 * 있는지가 직관적이지 않다".
 *
 * 그래서 장면 카드마다 "바꾸기" 를 두고, 누르면 이 창에서 그 장면에 넣을 걸 바로 고른다.
 * 다른 장면에 쓰인 걸 고르면 두 장면이 서로 바뀐다 (같은 사진이 두 번 들어가지 않게).
 */
import * as React from 'react';
import { Box, Button, Dialog, DialogContent, DialogTitle, IconButton, Typography } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';

export type PickedMedia = { type: 'image' | 'video' | 'default'; url: string | null } | null;

type Props = {
  /** 고르는 중인 장면 (0부터). null 이면 닫힘 */
  slot: number | null;
  images: string[];
  videos: string[];
  sections: PickedMedia[];
  /** 사진 주소 → 화면에 띄울 주소 (이미지 프록시) */
  imageSrc: (url: string) => string;
  onPick: (slot: number, type: 'image' | 'video', url: string) => void;
  onClose: () => void;
  fullScreen?: boolean;
};

export default function MediaPickerDialog({
  slot, images, videos, sections, imageSrc, onPick, onClose, fullScreen,
}: Props) {
  const [broken, setBroken] = React.useState<Set<string>>(new Set());
  const open = slot !== null;

  const usedAt = (url: string) => sections.findIndex(s => !!s && s.url === url);

  const badge = (url: string) => {
    const at = usedAt(url);
    if (at === -1) return null;
    const here = at === slot;
    return (
      <Box sx={{
        position: 'absolute', top: 6, left: 6, px: 1, py: 0.25, borderRadius: 999,
        fontSize: 11, fontWeight: 600, color: '#fff', pointerEvents: 'none',
        bgcolor: here ? '#1976d2' : 'rgba(0,0,0,0.6)',
      }}>
        {here ? '지금 장면' : `${at + 1}번 장면`}
      </Box>
    );
  };

  const tileSx = (url: string) => ({
    position: 'relative' as const,
    cursor: 'pointer',
    borderRadius: 2,
    overflow: 'hidden',
    bgcolor: '#333',
    outline: usedAt(url) === slot ? '3px solid #1976d2' : '1px solid #e3e6ef',
    outlineOffset: usedAt(url) === slot ? 0 : -1,
    aspectRatio: '1 / 1',
    '&:hover': { opacity: 0.85 },
  });

  const pick = (type: 'image' | 'video', url: string) => {
    if (slot === null) return;
    onPick(slot, type, url);
    onClose();
  };

  const shownImages = images.filter(u => !broken.has(u));

  return (
    <Dialog open={open} onClose={onClose} fullScreen={fullScreen} maxWidth="md" fullWidth
      PaperProps={{ sx: { borderRadius: fullScreen ? 0 : 3 } }}>
      <DialogTitle sx={{ pr: 6, pb: 0.5 }}>
        <Typography component="span" sx={{ fontSize: 18, fontWeight: 700 }}>
          {slot !== null ? `장면 ${slot + 1}에 넣을 사진·영상` : ''}
        </Typography>
        <IconButton onClick={onClose} aria-label="닫기" sx={{ position: 'absolute', right: 8, top: 8 }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        <Typography sx={{ fontSize: 13, color: '#666', mb: 2, wordBreak: 'keep-all' }}>
          누르면 바로 바뀌어요. 다른 장면에 쓰인 걸 고르면 두 장면이 서로 바뀌어요.
        </Typography>

        {videos.length > 0 && (
          <>
            <Typography sx={{ fontSize: 14, fontWeight: 700, mb: 1 }}>영상 {videos.length}개</Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1, mb: 3 }}>
              {videos.map(url => (
                <Box key={url} sx={tileSx(url)} onClick={() => pick('video', url)}
                  role="button" aria-label="이 영상 고르기">
                  {/* #t=0.1 — 모바일 사파리가 첫 프레임을 그리게 한다 */}
                  <video src={`${url}#t=0.1`} muted playsInline preload="metadata"
                    style={{ width: '100%', height: '100%', objectFit: 'cover', pointerEvents: 'none' }} />
                  <Box sx={{
                    position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
                    justifyContent: 'center', pointerEvents: 'none',
                  }}>
                    <PlayArrowIcon sx={{ color: '#fff', fontSize: 36, filter: 'drop-shadow(0 1px 3px rgba(0,0,0,0.6))' }} />
                  </Box>
                  {badge(url)}
                </Box>
              ))}
            </Box>
          </>
        )}

        <Typography sx={{ fontSize: 14, fontWeight: 700, mb: 1 }}>사진 {shownImages.length}장</Typography>
        {shownImages.length === 0 ? (
          <Typography sx={{ fontSize: 13, color: '#999' }}>글에서 가져온 사진이 없어요.</Typography>
        ) : (
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1 }}>
            {shownImages.map(url => (
              <Box key={url} sx={tileSx(url)} onClick={() => pick('image', url)}
                role="button" aria-label="이 사진 고르기">
                <img src={imageSrc(url)} alt="" loading="lazy"
                  onError={() => setBroken(prev => new Set(prev).add(url))}
                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                {badge(url)}
              </Box>
            ))}
          </Box>
        )}

        {fullScreen && (
          <Button fullWidth variant="outlined" onClick={onClose} sx={{ mt: 3 }}>닫기</Button>
        )}
      </DialogContent>
    </Dialog>
  );
}
