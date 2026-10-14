import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

function getBackendBaseUrl(): string {
  let url = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL;
  // If url is not set, or points to internal docker-compose hostname 'api:8000' or 'localhost' on cloud
  if (!url || url.includes('api:8000') || (process.env.NODE_ENV === 'production' && url.includes('localhost'))) {
    url = 'https://api-production-881ea.up.railway.app';
  }
  return url.replace(/\/+$/, '');
}

async function forwardRequest(request: NextRequest, { params }: { params: { path?: string[] } }) {
  const path = params.path ? params.path.join('/') : '';
  const search = request.nextUrl.search;
  const backendBase = getBackendBaseUrl();
  const targetUrl = `${backendBase}/api/v1/${path}${search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    // Strip headers that interfere with upstream fetch
    const lower = key.toLowerCase();
    if (
      lower !== 'host' &&
      lower !== 'content-length' &&
      lower !== 'accept-encoding' &&
      lower !== 'connection'
    ) {
      headers.set(key, value);
    }
  });

  const method = request.method;
  const body = ['GET', 'HEAD'].includes(method) ? undefined : await request.arrayBuffer();

  try {
    const backendResponse = await fetch(targetUrl, {
      method,
      headers,
      body,
      // @ts-ignore
      duplex: 'half',
      cache: 'no-store',
    });

    const contentType = backendResponse.headers.get('content-type') || '';

    // For JSON responses, decode and use NextResponse.json to ensure correct compression & Content-Length
    if (contentType.includes('application/json')) {
      const data = await backendResponse.json();
      return NextResponse.json(data, {
        status: backendResponse.status,
        statusText: backendResponse.statusText,
      });
    }

    // For streaming responses (e.g. SSE text/event-stream) or others, stream body while stripping mismatching encoding headers
    const responseHeaders = new Headers();
    backendResponse.headers.forEach((value, key) => {
      const lower = key.toLowerCase();
      if (
        lower !== 'content-encoding' &&
        lower !== 'content-length' &&
        lower !== 'transfer-encoding' &&
        lower !== 'connection'
      ) {
        responseHeaders.set(key, value);
      }
    });

    return new Response(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    });
  } catch (error: any) {
    return NextResponse.json(
      { detail: `Failed to proxy request to backend (${targetUrl}): ${error?.message || error}` },
      { status: 502 }
    );
  }
}

export const GET = forwardRequest;
export const POST = forwardRequest;
export const PUT = forwardRequest;
export const PATCH = forwardRequest;
export const DELETE = forwardRequest;
export const HEAD = forwardRequest;
