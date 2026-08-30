'use client';

/**
 * 배포용 문구 — 만든 영상을 SNS 에 올릴 때 쓸 문구를 플랫폼별로 조립해 보여준다.
 * (2026-08-30, 유저 요청: "제목 설명 태그 등등도 생성")
 *
 * ## 왜 플랫폼별로 나누는가
 *
 * 실제로 갈리는 건 두 가지뿐이다 — **제목 칸이 따로 있는가**(유튜브만 그렇다)와
 * 해시태그를 몇 개 쓰는가. 나머지 셋은 캡션 한 칸이다.
 *
 *   유튜브 쇼츠  제목 100자(60자만 보임) + 설명 별도 · 해시태그 15개
 *   인스타 릴스  캡션 2,200자 · 해시태그 최대 30개
 *   틱톡        캡션 2,200자 · 짧을수록 유리
 *   페이스북     캡션 길이 여유 · 해시태그는 효과가 거의 없다
 *
 * 그래서 **모델은 재료 3개(제목/설명/해시태그)만 만들고, 조립은 여기서 한다.**
 * 플랫폼마다 따로 생성하면 API 호출이 4배가 되는데 얻는 게 없다.
 *
 * 어느 플랫폼이든 앞 100자 남짓만 잘리기 전에 보이므로, 조립할 때 항상 핵심을
 * 맨 앞에 둔다.
 */
import * as React from 'react';
import { Box, Typography, Button, Tabs, Tab } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckIcon from '@mui/icons-material/Check';

export type SeoCopy = {
  title: string;
  description: string;
  /** 유튜브 설명란용 긴 버전. 없으면 description 으로 대신한다. */
  description_long?: string;
  hashtags: string[];
};

type Props = {
  seo: SeoCopy;
};

type Field = { label: string; value: string; hint?: string };

const tag = (t: string) => `#${t}`;

/** 플랫폼별 조립 규칙. 순수 문자열 조합이라 비용이 없다. */
function buildFields(platform: string, seo: SeoCopy): Field[] {
  const tags = seo.hashtags ?? [];
  const desc = seo.description || '';
  const title = seo.title || '';

  if (platform === 'youtube') {
    // 유튜브만 제목 칸이 따로 있다. 제목은 60자까지만 화면에 보인다.
    // 설명란은 유튜브가 영상을 이해하고 검색에 노출시키는 재료라 긴 버전을 쓴다.
    const longDesc = seo.description_long || desc;
    const body = [longDesc, tags.slice(0, 15).map(tag).join(' '), '#Shorts']
      .filter(Boolean)
      .join('\n\n');
    return [
      { label: '제목', value: title, hint: '60자까지 보여요' },
      { label: '설명', value: body },
    ];
  }
  if (platform === 'instagram') {
    // 첫 줄이 훅이다 — 제목을 맨 앞에 세운다.
    return [{
      label: '캡션',
      value: [title, desc, tags.slice(0, 15).map(tag).join(' ')].filter(Boolean).join('\n\n'),
    }];
  }
  if (platform === 'tiktok') {
    // 틱톡은 캡션이 길면 불리하다 — 한 줄 + 해시태그 5개.
    return [{
      label: '캡션',
      value: [title, tags.slice(0, 5).map(tag).join(' ')].filter(Boolean).join('\n\n'),
    }];
  }
  // 페이스북 — 해시태그는 효과가 거의 없어 넣지 않는다.
  return [{ label: '게시글', value: [title, desc].filter(Boolean).join('\n\n') }];
}

const PLATFORMS = [
  { key: 'youtube', name: '유튜브' },
  { key: 'instagram', name: '인스타그램' },
  { key: 'tiktok', name: '틱톡' },
  { key: 'facebook', name: '페이스북' },
];

export default function PublishKit({ seo }: Props) {
  const [tabIdx, setTabIdx] = React.useState(0);
  const [copied, setCopied] = React.useState<string | null>(null);

  // 문구가 없으면 블록 자체를 숨긴다 — 빈 상자를 보여줄 이유가 없다.
  const hasCopy = !!(seo && (seo.title || seo.description || (seo.hashtags?.length ?? 0) > 0));
  if (!hasCopy) return null;

  const platform = PLATFORMS[tabIdx].key;
  const fields = buildFields(platform, seo);

  const copy = async (key: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // clipboard API 가 막힌 브라우저 폴백 — 임시 textarea 로 복사한다.
      const ta = document.createElement('textarea');
      ta.value = value;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch { /* 복사 실패는 무시 */ }
      document.body.removeChild(ta);
    }
    setCopied(key);
    setTimeout(() => setCopied(c => (c === key ? null : c)), 1600);
  };

  return (
    <Box sx={{ width: '100%', maxWidth: 560, mx: 'auto', mt: 4 }}>
      <Typography sx={{ fontSize: 14, fontWeight: 700, mb: 0.5 }}>
        배포용 문구
        <Box component="span" sx={{ fontSize: 11.5, fontWeight: 500, color: '#888', ml: 1 }}>
          올릴 곳을 고르고 복사하세요
        </Box>
      </Typography>

      <Box sx={{ border: '1px solid #e3e6ef', borderRadius: 2, overflow: 'hidden' }}>
        <Tabs
          value={tabIdx}
          onChange={(_, v) => setTabIdx(v)}
          variant="fullWidth"
          sx={{ borderBottom: '1px solid #e3e6ef', minHeight: 40, '& .MuiTab-root': { minHeight: 40, fontSize: 13, fontWeight: 700 } }}
        >
          {PLATFORMS.map(p => <Tab key={p.key} label={p.name} />)}
        </Tabs>

        <Box sx={{ p: 1.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {fields.map(f => {
            const key = `${platform}:${f.label}`;
            const isCopied = copied === key;
            return (
              <Box key={key}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography sx={{ fontSize: 12, fontWeight: 700, color: '#555' }}>
                    {f.label}
                    {f.hint && (
                      <Box component="span" sx={{ fontSize: 11, fontWeight: 500, color: '#999', ml: 0.75 }}>
                        {f.hint}
                      </Box>
                    )}
                  </Typography>
                  <Button
                    size="small"
                    variant={isCopied ? 'contained' : 'outlined'}
                    color={isCopied ? 'success' : 'primary'}
                    startIcon={isCopied ? <CheckIcon sx={{ fontSize: 15 }} /> : <ContentCopyIcon sx={{ fontSize: 15 }} />}
                    onClick={() => void copy(key, f.value)}
                    sx={{ fontSize: 12, fontWeight: 700, py: 0.25, minWidth: 78 }}
                  >
                    {isCopied ? '복사됨' : '복사'}
                  </Button>
                </Box>
                <Box
                  sx={{
                    fontSize: 13,
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'keep-all',
                    bgcolor: '#fafbfc',
                    border: '1px solid #eef0f5',
                    borderRadius: 1.5,
                    p: 1.25,
                    maxHeight: 190,
                    overflowY: 'auto',
                  }}
                >
                  {f.value}
                </Box>
              </Box>
            );
          })}
        </Box>
      </Box>
    </Box>
  );
}
