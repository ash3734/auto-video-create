/**
 * 블로그 주소 정규화 + 검증 (2026-08-27).
 *
 * ## 왜 필요한가
 *
 * 신규 유저 ssonek 의 첫 세션(07:49~07:58) 로그에서 두 가지가 나왔다.
 *
 * 1. **빈 주소로 4번 제출됐다** (`요청 블로그: /`). 입력 검증이 아예 없어서
 *    빈 칸으로도 제출이 되고, 유저는 왕복 한 번을 버린 뒤에야 실패를 본다.
 * 2. **같은 주소가 두 번 붙어서 404** 가 났다.
 *    `https://blog.naver.com/ssonek/224391607813https://blog.naver.com/ssonek/224391607813`
 *    붙여넣기가 안 먹은 줄 알고 한 번 더 붙이면 이렇게 된다. 더 나쁜 건 이게
 *    서버의 블로그 검증을 **통과한다**는 점이다 — 호스트가 blog.naver.com 이고
 *    경로 첫 조각이 본인 아이디라 통과한 뒤, 실제로 긁으러 가서 404 가 난다.
 *    유저에게는 이유를 알 수 없는 실패로만 보인다.
 *
 * ## 설계 메모
 *
 * - 순수 함수로 두어 서버 왕복 없이 즉시 피드백을 준다.
 * - 지원하지 않는 호스트는 여기서 걸러도 **결과가 달라지지 않는다**. 서버의
 *   parse_blog_url 이 이미 그런 주소를 빈 username 으로 처리해 거부하기 때문이다.
 *   다만 메시지가 "등록된 블로그 주소가 아닙니다" 라 원인을 알 수 없어서,
 *   여기서 먼저 무엇이 잘못됐는지 알려준다.
 * - 서버 쪽 방어(호스트 부분일치 우회, 구형 PostView 링크)는 별건으로 남아 있다.
 *   이 파일은 유저가 실제로 겪은 두 경우만 다룬다.
 */

export type BlogUrlResult =
  | { ok: true; url: string }
  | { ok: false; message: string };

/** 서버 parse_blog_url 이 실제로 해석할 수 있는 호스트만 통과시킨다. */
function isSupportedHost(host: string): boolean {
  return (
    host === "blog.naver.com" ||
    host === "m.blog.naver.com" ||
    host === "tistory.com" ||
    host.endsWith(".tistory.com") ||
    host === "brunch.co.kr" ||
    host === "m.brunch.co.kr"
  );
}

/**
 * 입력을 정규화하고 검증한다. 성공하면 서버로 보낼 주소를 돌려준다.
 *
 * 정규화 순서가 중요하다 — 앞뒤 공백 제거 → 중복 붙여넣기 잘라내기 →
 * 스킴 보정 → 파싱 → 호스트 확인. 중복 잘라내기를 파싱보다 먼저 해야
 * 두 번 붙은 주소가 "유효한 URL" 로 파싱돼 통과하는 걸 막을 수 있다.
 */
export function normalizeBlogUrl(raw: string): BlogUrlResult {
  let s = (raw ?? "").trim();

  if (!s) {
    return { ok: false, message: "블로그 주소를 입력해주세요." };
  }

  // 주소가 여러 번 들어있으면 첫 번째만 쓴다.
  // 앞에 제목 같은 텍스트가 붙어 오는 경우(네이버 앱 공유)도 같이 걸러진다.
  const starts: number[] = [];
  const scheme = /https?:\/\//gi;
  let m: RegExpExecArray | null;
  while ((m = scheme.exec(s)) !== null) {
    starts.push(m.index);
  }
  if (starts.length > 1) {
    s = s.slice(starts[0], starts[1]).trim();
  } else if (starts.length === 1) {
    s = s.slice(starts[0]).trim();
  } else {
    // 스킴이 없으면 붙여준다. blog.naver.com/foo 처럼 입력하는 경우가 흔하다.
    s = `https://${s}`;
  }

  // 잘라낸 뒤 끝에 남을 수 있는 구분자 정리
  s = s.replace(/[\s,]+$/, "");

  let parsed: URL;
  try {
    parsed = new URL(s);
  } catch {
    return {
      ok: false,
      message: "주소 형식이 올바르지 않아요. 블로그 글 주소를 그대로 붙여넣어 주세요.",
    };
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return {
      ok: false,
      message: "주소 형식이 올바르지 않아요. 블로그 글 주소를 그대로 붙여넣어 주세요.",
    };
  }

  const host = parsed.hostname.toLowerCase();
  if (!isSupportedHost(host)) {
    return {
      ok: false,
      message: "네이버 블로그, 티스토리, 브런치 주소만 사용할 수 있어요.",
    };
  }

  if (!isPostUrl(host, parsed)) {
    return {
      ok: false,
      message: "블로그 홈 주소예요. 만들고 싶은 글을 연 뒤 그 글의 주소를 복사해서 넣어주세요.",
    };
  }

  return { ok: true, url: parsed.toString() };
}

/**
 * 개별 **글** 주소인가, 블로그 홈인가 (2026-08-30).
 *
 * 호스트만 맞으면 통과시키던 탓에 `m.blog.naver.com/아이디`(블로그 홈)가 그대로
 * 서버까지 갔다. 크롤러가 본문을 못 찾아 실패하고, 그게 장애 알람까지 울렸다.
 * 유저에게는 "다른 글로 시도해주세요" 라고만 보여서 **무엇이 잘못됐는지 알 수 없었다.**
 *
 * 여기서 걸러 왕복을 없애고, 무엇을 해야 하는지 바로 알려준다.
 */
function isPostUrl(host: string, parsed: URL): boolean {
  const parts = parsed.pathname.split("/").filter(Boolean);

  if (host === "blog.naver.com" || host === "m.blog.naver.com") {
    // 구형 공유 링크: /PostView.naver?blogId=..&logNo=..
    if (parsed.searchParams.get("logNo")) return true;
    // 신형: /{아이디}/{글번호}
    return parts.length >= 2 && /^\d+$/.test(parts[1]);
  }

  if (host === "brunch.co.kr" || host === "m.brunch.co.kr") {
    return parts.length >= 2;             // /@작가/글번호
  }

  // 티스토리 — /{글번호} 또는 /entry/{제목}
  return parts.length >= 1 && parts[0] !== "category";
}
