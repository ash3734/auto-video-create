'use client';

/**
 * React 렌더링이 통째로 터졌을 때의 마지막 방어선 (2026-08-09).
 *
 * 여기까지 오면 유저는 빈 화면을 본다. 그 상태를 우리가 모르는 게 최악이라
 * Sentry 로 먼저 보내고, 유저에게는 다시 시도할 수단을 준다.
 *
 * 유저에게 원인을 설명하지 않는 건 의도적이다 — 에러 내용은 우리 로그에 남고,
 * 유저가 할 수 있는 건 재시도와 문의뿐이다. (2026-08-06 PO 방침)
 */
import * as Sentry from '@sentry/nextjs';
import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="ko">
      <body
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          margin: 0,
          padding: '24px',
          fontFamily:
            "'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif",
          textAlign: 'center',
          color: '#1a1a1a',
          background: '#fafafa',
        }}
      >
        <h2 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 8px' }}>
          화면을 불러오지 못했어요
        </h2>
        <p style={{ fontSize: '14px', color: '#666', margin: '0 0 20px' }}>
          잠시 후 다시 시도해주세요. 계속 문제가 생기면 관리자에게 문의해주세요.
        </p>
        <button
          onClick={() => reset()}
          style={{
            padding: '10px 24px',
            fontSize: '14px',
            fontWeight: 600,
            color: '#fff',
            background: '#1976d2',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
          }}
        >
          다시 시도
        </button>
      </body>
    </html>
  );
}
