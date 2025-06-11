import { NextRequest } from 'next/server';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const imageUrl = searchParams.get('url');
  if (!imageUrl) {
    return new Response('No url provided', { status: 400 });
  }
  try {
    const response = await fetch(imageUrl);
    if (!response.ok) {
      return new Response('Failed to fetch image', { status: 502 });
    }
    const contentType = response.headers.get('content-type') || 'image/jpeg';
    const arrayBuffer = await response.arrayBuffer();
    return new Response(arrayBuffer, {
      headers: { 'Content-Type': contentType }
    });
  } catch (e) {
    return new Response('Error fetching image', { status: 500 });
  }
} 