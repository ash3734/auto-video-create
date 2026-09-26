'use client';

/**
 * 접히는 설정 카드 (2026-09-27).
 *
 * 자막 스타일 설정이 쓰던 카드 모양을 그대로 일반화한 것이다. 음성 / 말하는 속도 /
 * 배경음악이 각각 펼쳐진 채로 쌓여 있어서, 2페이지에 들어오면 스크립트를 보기까지
 * 한참 스크롤해야 했다. 넷 다 접어 두고 필요한 것만 연다.
 *
 * 헤더에 **지금 값 요약**(summary)을 띄우는 게 핵심이다. 접혀 있어도 뭘 고른
 * 상태인지 보이지 않으면, 접는 순간 "설정한 적 없는 화면"처럼 느껴진다.
 * 자막 카드가 접힌 채로 폰트·색 칩을 보여주던 것과 같은 이유다.
 */
import * as React from 'react';
import { Box, Typography, Collapse } from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';

type Props = {
  title: string;
  /** 제목 옆 회색 배지. 없으면 안 그린다 */
  badge?: string;
  /** 헤더 가운데에 띄울 현재 값 요약 — 접힌 상태에서 유일한 단서다 */
  summary?: React.ReactNode;
  defaultExpanded?: boolean;
  children: React.ReactNode;
};

export default function CollapsibleSection({
  title,
  badge,
  summary,
  defaultExpanded = false,
  children,
}: Props) {
  const [expanded, setExpanded] = React.useState(defaultExpanded);

  return (
    <Box
      sx={{
        width: '100%',
        maxWidth: 1200,
        mx: 'auto',
        mb: 2,
        borderRadius: expanded ? '12px 12px 0 0' : '12px',
        border: '1.5px solid #f2f4f8',
        bgcolor: '#fafbfc',
        boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
        overflow: 'hidden',
      }}
    >
      <Box
        onClick={() => setExpanded(v => !v)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          px: { xs: 2, md: 3 },
          minHeight: 56,
          cursor: 'pointer',
          userSelect: 'none',
          gap: 1.5,
          '&:hover': { bgcolor: '#f0f2f5' },
          transition: 'background 0.15s',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0 }}>
          <Typography sx={{ fontSize: 15, fontWeight: 700, color: '#222' }}>{title}</Typography>
          {badge && (
            <Box
              sx={{
                bgcolor: '#f0f4f8',
                border: '1px solid #dde1ea',
                borderRadius: 999,
                px: 1,
                py: 0.125,
              }}
            >
              <Typography sx={{ fontSize: 11, color: '#888', lineHeight: 1.4 }}>{badge}</Typography>
            </Box>
          )}
        </Box>

        <Box
          sx={{
            display: 'flex',
            gap: 1,
            flex: 1,
            minWidth: 0,
            justifyContent: 'flex-end',
            alignItems: 'center',
          }}
        >
          {summary}
        </Box>

        {expanded ? (
          <KeyboardArrowUpIcon sx={{ color: '#666', fontSize: 20, flexShrink: 0 }} />
        ) : (
          <KeyboardArrowDownIcon sx={{ color: '#666', fontSize: 20, flexShrink: 0 }} />
        )}
      </Box>

      <Collapse in={expanded} timeout={250}>
        <Box sx={{ borderTop: '1.5px solid #f2f4f8', px: { xs: 2, md: 3 }, py: 2.5 }}>
          {children}
        </Box>
      </Collapse>
    </Box>
  );
}

/** 헤더 요약용 작은 회색 칩. 값이 길면 말줄임한다. */
export function SummaryChip({ text }: { text: string }) {
  return (
    <Box
      sx={{
        bgcolor: '#fff',
        border: '1px solid #e3e6ef',
        borderRadius: 999,
        px: 1.25,
        py: 0.25,
        maxWidth: 220,
        minWidth: 0,
      }}
    >
      <Typography
        noWrap
        sx={{ fontSize: 12, color: '#555', fontWeight: 600, lineHeight: 1.5 }}
      >
        {text}
      </Typography>
    </Box>
  );
}
