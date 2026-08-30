import { NextRequest } from 'next/server';

/**
 * 완성된 영상을 **다운로드**로 받게 해주는 프록시 (2026-08-30).
 *
 * ## 왜 프록시가 필요한가
 *
 * 완료 화면에 다운로드 버튼이 없어서, 유저는 우클릭 → 다른 이름으로 저장 말고는
 * 영상을 꺼낼 방법이 없었다. 틱톡·인스타는 사실상 휴대폰에서 올리는데 모바일에서는
 * 그마저도 번거롭다. 이틀에 16편을 만든 유저가 16번을 그렇게 했다.
 *
 * 그냥 링크를 걸면 안 되는 이유는 원본 응답 헤더에 있다 —
 *
 *     Content-Type: video/mp4          → 브라우저가 재생해 버린다
 *     (Content-Disposition 없음)        → 다운로드로 취급되지 않는다
 *     (Access-Control-Allow-Origin 없음) → 브라우저 fetch → blob 도 막힌다
 *
 * 그래서 서버에서 받아 `Content-Disposition: attachment` 를 붙여 되돌려준다.
 * 파일은 20초 영상 기준 약 1MB 라 메모리에 올려도 부담이 없다.
 *
 * ## 열린 프록시가 되지 않게
 *
 * url 파라미터를 그대로 받아 가져오면 아무 주소나 우리 서버를 통해 받아갈 수 있다.
 * 렌더 결과가 올라가는 호스트만 허용한다.
 */

// Creatomate 렌더 결과가 올라가는 호스트 (백블레이즈). 그 외는 거절한다.
const ALLOWED_HOSTS = [/^f\d+\.backblazeb2\.com$/, /(^|\.)creatomate\.com$/];

function isAllowed(raw: string): boolean {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return false;
  }
  if (parsed.protocol !== 'https:') return false;
  return ALLOWED_HOSTS.some(re => re.test(parsed.hostname));
}

/**
 * 파일명을 Content-Disposition 에 안전하게 싣는다.
 *
 * HTTP 헤더 값은 ASCII 만 담을 수 있어서, 한글 제목을 그대로 넣으면 응답 생성이
 * 통째로 터진다(500). 영상 제목은 대부분 한글이라 이걸 놓치면 다운로드가
 * **항상** 실패한다 — 실제로 배포 후 확인하다 잡았다.
 *
 * RFC 5987 방식으로 두 벌을 준다: 구형 클라이언트용 ASCII 대체 이름과,
 * 퍼센트 인코딩한 UTF-8 원래 이름. 요즘 브라우저는 filename* 을 우선한다.
 */
function contentDisposition(name: string): string {
  const ascii = name.replace(/[^\x20-\x7E]/g, '').replace(/["\\]/g, '') || 'shorts';
  const encoded = encodeURIComponent(`${name}.mp4`);
  return `attachment; filename="${ascii}.mp4"; filename*=UTF-8''${encoded}`;
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const videoUrl = searchParams.get('url');
  if (!videoUrl) {
    return new Response('No url provided', { status: 400 });
  }
  if (!isAllowed(videoUrl)) {
    return new Response('Not an allowed video host', { status: 400 });
  }

  const raw = (searchParams.get('name') || 'shorts').replace(/[^\w가-힣-]/g, '').slice(0, 60);
  const name = raw || 'shorts';

  try {
    const upstream = await fetch(videoUrl);
    if (!upstream.ok) {
      return new Response('Failed to fetch video', { status: 502 });
    }
    const buf = await upstream.arrayBuffer();
    return new Response(buf, {
      headers: {
        'Content-Type': upstream.headers.get('content-type') || 'video/mp4',
        // 이게 이 프록시의 존재 이유다 — 재생이 아니라 저장으로 만든다.
        'Content-Disposition': contentDisposition(name),
        'Content-Length': String(buf.byteLength),
      },
    });
  } catch (e) {
    return new Response('Error fetching video: ' + e, { status: 500 });
  }
}
