'use client';

/**
 * 화면 배치 선택 (2026-10-18, 백로그 2-1).
 *
 * 배치마다 같은 샘플로 렌더한 미리보기 한 장을 보여준다 (scripts/render_layout_previews.py).
 * 자막 스타일·화면 효과는 따로 고르는 것이라, 여기서는 "사진과 글자가 어디에 놓이는지"만
 * 비교하게 한다. 기본은 지금까지의 배치("기본")라 안 건드리면 결과물이 그대로다.
 */
import * as React from 'react';
import { Box, Button, CircularProgress, TextField, Typography } from '@mui/material';

export type LayoutOption = {
  id: string;
  name: string;
  description: string;
  preview_url: string;
  is_default: boolean;
};

export type PlaceInfo = { name: string; location: string; price: string };

type Props = {
  layouts: LayoutOption[];
  selected: string;
  onSelect: (id: string) => void;
  /** 맛집 정보카드 배치일 때만 쓴다 */
  place: PlaceInfo;
  onPlaceChange: (p: PlaceInfo) => void;
  onFetchPlace: () => void;
  placeLoading: boolean;
  placeMax: number;
  disabled?: boolean;
};

export default function LayoutPicker({
  layouts,
  selected,
  onSelect,
  place,
  onPlaceChange,
  onFetchPlace,
  placeLoading,
  placeMax,
  disabled = false,
}: Props) {
  const field = (key: keyof PlaceInfo, label: string, placeholder: string) => (
    <TextField
      label={label}
      value={place[key]}
      placeholder={placeholder}
      onChange={e => onPlaceChange({ ...place, [key]: e.target.value.slice(0, placeMax) })}
      disabled={disabled || placeLoading}
      size="small"
      fullWidth
      sx={{ bgcolor: '#fff' }}
    />
  );
  return (
    <Box>
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(auto-fill, minmax(150px, 1fr))' },
        gap: 1.5,
      }}
    >
      {layouts.map(l => {
        const isSelected = selected === l.id;
        return (
          <Box
            key={l.id}
            onClick={() => !disabled && onSelect(l.id)}
            sx={{
              cursor: disabled ? 'default' : 'pointer',
              opacity: disabled ? 0.5 : 1,
              borderRadius: 2,
              overflow: 'hidden',
              border: `2px solid ${isSelected ? '#1976d2' : '#e3e6ef'}`,
              bgcolor: isSelected ? 'rgba(25, 118, 210, 0.05)' : '#fff',
              transition: 'border-color 0.15s',
            }}
          >
            <Box sx={{ aspectRatio: '9 / 16', bgcolor: '#222', position: 'relative' }}>
              <img
                src={l.preview_url}
                alt={`${l.name} 배치 미리보기`}
                loading="lazy"
                style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
              />
              {isSelected && (
                <Box
                  sx={{
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    bgcolor: '#1976d2',
                    color: '#fff',
                    fontSize: 11,
                    fontWeight: 700,
                    px: 1,
                    py: 0.25,
                    borderRadius: 1,
                  }}
                >
                  선택됨
                </Box>
              )}
            </Box>
            <Box sx={{ px: 1.25, py: 1 }}>
              <Typography sx={{ fontSize: 13.5, fontWeight: 700, color: isSelected ? '#1976d2' : '#222' }}>
                {l.name}
                {l.is_default && (
                  <Box component="span" sx={{ fontSize: 11, fontWeight: 500, color: '#888', ml: 0.5 }}>
                    · 지금까지 쓰던 배치
                  </Box>
                )}
              </Typography>
              <Typography sx={{ fontSize: 11.5, color: '#888', lineHeight: 1.45, wordBreak: 'keep-all' }}>
                {l.description}
              </Typography>
            </Box>
          </Box>
        );
      })}
    </Box>

      {/* 맛집 정보카드 — 글에서 뽑아 온 값을 고칠 수 있게. 틀린 주소가 영상에 박히면 안 된다.
          비워 둔 줄은 카드에서 빠지고, 셋 다 비면 카드 자체가 나오지 않는다. */}
      {selected === 'info_card' && (
        <Box sx={{ mt: 2, p: 1.75, border: '1px solid #e3e6ef', borderRadius: 2, bgcolor: '#fafbfc' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.25 }}>
            <Typography sx={{ fontSize: 13, fontWeight: 700 }}>카드에 들어갈 가게 정보</Typography>
            <Button size="small" onClick={onFetchPlace} disabled={disabled || placeLoading} sx={{ fontSize: 12 }}>
              {placeLoading ? <CircularProgress size={14} sx={{ mr: 0.75 }} /> : null}
              {placeLoading ? '글에서 찾는 중' : '글에서 다시 가져오기'}
            </Button>
          </Box>
          <Box sx={{ display: 'grid', gap: 1.25 }}>
            {field('name', '가게 이름', '예: 세광양대창 신논현점')}
            {field('location', '위치', '예: 신논현역 3번 출구 앞')}
            {field('price', '가격', '예: 모둠 1인분 18,000원')}
          </Box>
          <Typography sx={{ mt: 1, fontSize: 11.5, color: '#888' }}>
            글에 없는 내용은 비워 둬요. 비운 줄은 카드에서 빠져요.
          </Typography>
        </Box>
      )}
    </Box>
  );
}
