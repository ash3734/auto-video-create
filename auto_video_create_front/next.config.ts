import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default withSentryConfig(nextConfig, {
  // 빌드 로그를 Sentry 잡담으로 채우지 않는다 — 진짜 빌드 에러가 묻힌다.
  silent: true,

  // 소스맵 업로드는 SENTRY_AUTH_TOKEN 이 있을 때만 한다.
  // 없으면 스택 트레이스가 압축된 상태로 보이지만(예: `a.b is not a function`),
  // 에러 메시지·발생 URL·직전 행동(breadcrumb)은 그대로 보이므로 원인 파악은 된다.
  // 토큰을 Amplify 환경변수에 넣으면 이 설정이 자동으로 업로드로 바뀐다.
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  sourcemaps: {
    disable: !process.env.SENTRY_AUTH_TOKEN,
  },

  // Sentry SDK 내부 디버그 로거를 번들에서 제거 (용량 절감).
  disableLogger: true,
});
