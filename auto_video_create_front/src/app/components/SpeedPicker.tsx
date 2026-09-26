'use client';

/**
 * 말하는 속도 선택 (2026-09-27 에 VoicePicker 에서 분리).
 *
 * 마크업은 옮겨온 그대로다. 설정 네 가지(자막·음성·속도·배경음악)를 각각 접을 수
 * 있게 하면서, 음성 카드 안에 속도가 딸려 있으면 "속도만 접는다"가 불가능해
 * 떼어냈다.
 *
 * 미리듣기는 여전히 **음성 카드**에 있다. 속도를 바꾸면 그 미리듣기가 바뀐 속도로
 * 나가므로, 음성 카드 헤더에 현재 속도를 같이 띄워 둔다 — 안 그러면 어떤 속도로
 * 듣고 있는지 모른 채 고르게 된다.
 */
import * as React from 'react';
import { Box, Typography } from '@mui/material';

export type Speed = {
  value: number;
  name: string;
  description: string;
  is_default: boolean;
};

type Props = {
  speeds: Speed[];
  selected: number;
  onSelect: (value: number) => void;
  disabled?: boolean;
};

export default function SpeedPicker({ speeds, selected, onSelect, disabled = false }: Props) {
  return (
    <Box sx={{ display: 'flex', gap: 1 }}>
      {speeds.map(s => {
        const isSelected = Math.abs(selected - s.value) < 1e-6;
        return (
          <Box
            key={s.value}
            onClick={() => !disabled && onSelect(s.value)}
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
  );
}
