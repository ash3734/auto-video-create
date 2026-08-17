/**
 * Sentry 서버/엣지 런타임 초기화 (2026-08-09).
 *
 * Next.js 가 서버 시작 시 register() 를 한 번 호출한다.
 * 클라이언트 쪽은 instrumentation-client.ts 가 담당한다.
 *
 * 우리 배포는 Amplify 정적 호스팅이 중심이라 서버 런타임에서 나는 에러는 많지 않지만,
 * 서버 컴포넌트/라우트 핸들러가 조용히 실패하는 경우를 잡으려면 있어야 한다.
 */
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

export async function register() {
  if (!dsn) return;

  if (
    process.env.NEXT_RUNTIME === "nodejs" ||
    process.env.NEXT_RUNTIME === "edge"
  ) {
    Sentry.init({
      dsn,
      environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development",
      enabled: process.env.NODE_ENV === "production",
      tracesSampleRate: 0.1,
      sendDefaultPii: false,
    });
  }
}

// 서버 컴포넌트/라우트 핸들러에서 터진 에러를 Sentry 로 넘긴다.
export const onRequestError = Sentry.captureRequestError;
