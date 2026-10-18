'use client';

/**
 * 첫 화면 문구 · 끝 화면 (2026-10-18, 백로그 3-6).
 *
 * 첫 화면: 첫 장면 처음 1.6초에 큰 문구를 얹는다 (영상이 늦게 시작하지 않는다).
 * 끝 화면: 마지막 장면 뒤에 2.5초 끝 화면을 붙여 댓글·구독·블로그 방문을 권한다.
 * 둘 다 기본은 "없음" — 안 건드리면 지금까지와 같은 영상이다.
 * "직접 입력"을 고르면 입력칸이 열린다. 비워 두면 서버가 아무것도 붙이지 않는다.
 */
import * as React from 'react';
import { Box, TextField, Typography } from '@mui/material';

export type BookendOption = {
  id: string;
  name: string;
  description: string;
  preview?: string;
  is_default: boolean;
};

type RowProps = {
  label: string;
  options: BookendOption[];
  selected: string;
  onSelect: (id: string) => void;
  text: string;
  onText: (t: string) => void;
  placeholder: string;
  maxText: number;
  disabled: boolean;
};

function Row({ label, options, selected, onSelect, text, onText, placeholder, maxText, disabled }: RowProps) {
  const chosen = options.find(o => o.id === selected);
  return (
    <Box sx={{ mb: 2, '&:last-of-type': { mb: 0 } }}>
      <Typography sx={{ fontSize: 12.5, fontWeight: 700, color: '#555', mb: 0.75 }}>{label}</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(96px, 1fr))', gap: 1 }}>
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
            </Box>
          );
        })}
      </Box>

      {selected === 'custom' ? (
        <TextField
          value={text}
          onChange={e => onText(e.target.value.slice(0, maxText))}
          placeholder={placeholder}
          disabled={disabled}
          fullWidth
          size="small"
          multiline
          maxRows={2}
          helperText={`${text.length}/${maxText}자 · 줄바꿈은 두 줄까지`}
          sx={{ mt: 1, bgcolor: '#fff' }}
        />
      ) : chosen?.preview ? (
        <Typography sx={{ mt: 0.75, fontSize: 12, color: '#888', whiteSpace: 'pre-line' }}>
          {chosen.preview}
        </Typography>
      ) : chosen && selected !== 'none' ? (
        <Typography sx={{ mt: 0.75, fontSize: 12, color: '#888' }}>{chosen.description}</Typography>
      ) : null}
    </Box>
  );
}

type Props = {
  intros: BookendOption[];
  outros: BookendOption[];
  intro: string;
  introText: string;
  outro: string;
  outroText: string;
  maxText: number;
  onIntro: (id: string) => void;
  onIntroText: (t: string) => void;
  onOutro: (id: string) => void;
  onOutroText: (t: string) => void;
  disabled?: boolean;
};

export default function BookendPicker({
  intros,
  outros,
  intro,
  introText,
  outro,
  outroText,
  maxText,
  onIntro,
  onIntroText,
  onOutro,
  onOutroText,
  disabled = false,
}: Props) {
  return (
    <Box>
      {intros.length > 0 && (
        <Row
          label="첫 화면 문구 (처음 1.6초)"
          options={intros}
          selected={intro}
          onSelect={onIntro}
          text={introText}
          onText={onIntroText}
          placeholder="예: 글만 쓰면 쇼츠가 나온다고?"
          maxText={maxText}
          disabled={disabled}
        />
      )}
      {outros.length > 0 && (
        <Row
          label="끝 화면 (마지막에 2.5초)"
          options={outros}
          selected={outro}
          onSelect={onOutro}
          text={outroText}
          onText={onOutroText}
          placeholder="예: 다음 편도 기대해 주세요"
          maxText={maxText}
          disabled={disabled}
        />
      )}
    </Box>
  );
}
