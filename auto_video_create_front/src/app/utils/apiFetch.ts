/**
 * 서버 호출 공통 래퍼 — X-USER-ID 헤더 + 동시에 나가는 GET 수 제한 (2026-10-21).
 *
 * ## 왜 제한하나
 * 첫 화면이 설정 목록(음성·속도·음악·배치·효과·첫/끝 화면·장면 수·글꼴·자막 템플릿)을
 * **한꺼번에 9~10개** 부른다. 배포 직후처럼 서버(Lambda)가 식어 있으면 요청마다 새 실행이
 * 떠서, 이 AWS 계정의 동시 실행 한도 **10개(prod·test 합계)**를 혼자 다 쓴다.
 * 2026-10-20 21:56 test 에서 실제로 13건이 거절돼(throttle) 5xx 알람이 울렸다. prod 도
 * 같은 화면이라, 두 사람이 동시에 들어오거나 다른 사람의 영상 생성과 겹치면 똑같이 터진다.
 *
 * GET 만 MAX_PARALLEL_GETS 개씩 줄 세운다. 목록 GET 은 수십 ms 라 순서대로 받아도 체감이
 * 없고, 앞 요청이 데운 실행을 다음 요청이 그대로 쓴다. POST(글 추출·영상 생성)는 사람이
 * 누른 동작이라 기다리게 하지 않는다.
 */
const MAX_PARALLEL_GETS = 2;

let running = 0;
const waiting: Array<() => void> = [];

function acquire(): Promise<void> {
  if (running < MAX_PARALLEL_GETS) {
    running++;
    return Promise.resolve();
  }
  return new Promise(resolve => waiting.push(() => { running++; resolve(); }));
}

function release() {
  running--;
  const next = waiting.shift();
  if (next) next();
}

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const userId = typeof window !== "undefined" ? localStorage.getItem("user_id") : null;
  const init: RequestInit = {
    ...options,
    headers: { ...(options.headers || {}), "X-USER-ID": userId ?? "" },
  };
  const method = (options.method || "GET").toUpperCase();
  if (method !== "GET") return fetch(url, init);

  await acquire();
  try {
    return await fetch(url, init);
  } finally {
    release();
  }
}
