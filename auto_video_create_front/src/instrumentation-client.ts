/**
 * Sentry 클라이언트 초기화 — 유저 브라우저에서 나는 에러를 수집한다 (2026-08-09).
 *
 * ## 왜 필요한가
 *
 * 지금까지 FE 에러를 볼 방법이 전혀 없었다. Amplify 는 빌드 로그만 보여주고,
 * 유저 브라우저에서 무슨 일이 나는지는 PO 가 직접 그 화면을 재현해야만 알 수 있었다.
 * 2026-08-06 에 "숏폼 만들기를 눌러도 아무 반응이 없다"는 문제를 쫓을 때,
 * 람다 로그에는 요청 자체가 안 찍혀서 원인을 못 찾다가 콘솔 로그를 심고 나서야
 * FE 가 test 서버를 보고 있었다는 걸 알았다. 그 콘솔 로그도 PO 가 직접
 * 브라우저를 열어야만 보인다 — 유료 유저 브라우저의 에러는 여전히 안 보인다.
 *
 * ## 설계 메모
 *
 * - DSN 은 환경변수로 받는다. 없으면 초기화를 건너뛰므로 로컬에서 조용하다.
 *   (DSN 은 브라우저에 노출되는 게 정상인 값이다 — 전송만 가능하고 조회는 불가)
 * - 개발 중 에러로 무료 티어(월 5천 이벤트)를 태우지 않도록 production 빌드에서만 켠다.
 * - `[shorts]` 콘솔 로그는 Sentry 기본 통합이 breadcrumb 으로 자동 수집한다.
 *   덕분에 에러 하나를 열면 **직전에 어떤 API 를 호출했고 무슨 응답을 받았는지**가
 *   시간순으로 같이 보인다. 따로 계측할 필요가 없다.
 */
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

/**
 * 전송량 제한 — 무료 티어(월 5천 이벤트)를 폭주로 태우지 않기 위한 안전장치.
 *
 * 렌더 루프 안에서 에러가 나면 초당 수십 건이 발생할 수 있다. 그러면 하루도 못 가
 * 한도가 소진되고, 정작 중요한 에러가 오는 달 말에는 아무것도 못 받는다.
 *
 * 중복 제거(dedupe)는 Sentry 기본 통합이 해주지만, 그건 **연속된 동일 에러**만
 * 막는다. 서로 다른 에러가 번갈아 터지는 경우는 못 막으므로 총량 제한이 따로 필요하다.
 *
 * 한 브라우저 세션 기준이라 유저 수만큼 곱해지지만, 지금 규모에서는 이 정도가
 * "폭주는 막고 진짜 에러는 놓치지 않는" 균형점이다.
 */
const RATE_LIMIT_WINDOW_MS = 60_000;
const MAX_EVENTS_PER_WINDOW = 5;
const MAX_EVENTS_PER_PAGELOAD = 20;

let windowStartedAt = Date.now();
let eventsInWindow = 0;
let eventsTotal = 0;

function withinRateLimit(): boolean {
  const now = Date.now();
  if (now - windowStartedAt > RATE_LIMIT_WINDOW_MS) {
    windowStartedAt = now;
    eventsInWindow = 0;
  }
  if (eventsTotal >= MAX_EVENTS_PER_PAGELOAD) return false;
  if (eventsInWindow >= MAX_EVENTS_PER_WINDOW) return false;
  eventsInWindow += 1;
  eventsTotal += 1;
  return true;
}

if (dsn) {
  Sentry.init({
    dsn,
    // prod / test 를 구분해야 "이거 어느 환경 에러지?" 로 시간을 안 버린다.
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development",
    // 로컬 개발 에러는 보내지 않는다 (무료 티어 절약).
    enabled: process.env.NODE_ENV === "production",

    // 성능 추적은 낮게. 지금 규모에선 에러 수집이 본체고, 트레이스는 덤이다.
    // 필요해지면 올리면 된다.
    tracesSampleRate: 0.1,

    // IP·쿠키 등 자동 수집은 끈 채로 둔다(기본값). 아래에서 user_id 만 명시적으로 붙인다.
    sendDefaultPii: false,

    // 우리 코드와 무관한 잡음만 걸러낸다. 여기에 많이 넣을수록 사각지대가 커지므로
    // "명백히 우리가 손댈 수 없는 것"만 넣는다.
    ignoreErrors: [
      // 브라우저 렌더 최적화 경고 — 기능에 영향 없고 크롬에서 흔하다.
      /ResizeObserver loop/,
    ],
    denyUrls: [
      // 브라우저 확장 프로그램이 낸 에러는 우리가 고칠 수 없다.
      /^chrome-extension:\/\//,
      /^moz-extension:\/\//,
      /^safari-web-extension:\/\//,
    ],

    beforeSend(event) {
      // 폭주 차단이 먼저다 — 한도를 넘으면 아예 만들지 않고 버린다.
      if (!withinRateLimit()) return null;

      // 어떤 유저에게서 난 에러인지 알아야 재현과 응대가 된다.
      // localStorage 는 시크릿 모드 등에서 던질 수 있으므로 반드시 감싼다.
      try {
        const userId = window.localStorage.getItem("user_id");
        if (userId) {
          event.user = { ...event.user, id: userId };
        }
      } catch {
        // 읽기 실패는 무시 — 에러 리포트 자체를 잃는 것보다 낫다.
      }
      return event;
    },
  });
}

// App Router 페이지 전환을 트레이스에 연결한다 (Next.js 15.3+ 규약).
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
