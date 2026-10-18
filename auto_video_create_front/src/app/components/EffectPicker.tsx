'use client';

/**
 * 화면 효과 — 사진 움직임 · 장면 전환 (2026-10-18, 백로그 3-7).
 *
 * 두 줄로 나눈 이유: 둘은 서로 독립이다. "확대는 하고 전환은 없이"처럼 조합해서 고른다.
 * 기본값은 둘 다 "없음"이라, 안 건드리면 지금까지와 같은 영상이 나온다.
 */
import * as React from 'react';
import { Box, Typography } from '@mui/material';

export type EffectOption = {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
};

type RowProps = {
  label: string;
  options: EffectOption[];
  selected: string;
  onSelect: (id: string) => void;
  disabled: boolean;
};

function Row({ label, options, selected, onSelect, disabled }: RowProps) {
  return (
    <Box sx={{ mb: 1.75, '&:last-of-type': { mb: 0 } }}>
      <Typography sx={{ fontSize: 12.5, fontWeight: 700, color: '#555', mb: 0.75 }}>{label}</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 1 }}>
        {options.map(o => {
          const isSelected = selected === o.id;
          return (
            <Box
              key={o.id}
              onClick={() => !disabled && onSelect(o.id)}
              sx={{
                textAlign: 'center',
                py: 0.9,
                px: 1,
                borderRadius: 2,
                cursor: disabled ? 'default' : 'pointer',
                opacity: disabled ? 0.5 : 1,
                border: `1.5px solid ${isSelected ? '#1976d2' : '#e3e6ef'}`,
                bgcolor: isSelected ? 'rgba(25, 118, 210, 0.07)' : '#fff',
                transition: 'background-color 0.15s',
              }}
            >
              <Typography
                sx={{ fontSize: 13.5, fontWeight: 700, lineHeight: 1.3, color: isSelected ? '#1976d2' : '#333' }}
              >
                {o.name}
              </Typography>
              <Typography sx={{ fontSize: 11, color: '#888', lineHeight: 1.4, wordBreak: 'keep-all' }}>
                {o.description}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}

type Props = {
  motions: EffectOption[];
  transitions: EffectOption[];
  motion: string;
  transition: string;
  onSelectMotion: (id: string) => void;
  onSelectTransition: (id: string) => void;
  disabled?: boolean;
};

export default function EffectPicker({
  motions,
  transitions,
  motion,
  transition,
  onSelectMotion,
  onSelectTransition,
  disabled = false,
}: Props) {
  return (
    <Box>
      {motions.length > 0 && (
        <Row label="사진 움직임" options={motions} selected={motion} onSelect={onSelectMotion} disabled={disabled} />
      )}
      {transitions.length > 0 && (
        <Row
          label="장면 전환"
          options={transitions}
          selected={transition}
          onSelect={onSelectTransition}
          disabled={disabled}
        />
      )}
    </Box>
  );
}
