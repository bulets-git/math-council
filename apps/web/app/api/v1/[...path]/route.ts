import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

function getBackendBaseUrl(): string {
  const url =
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'https://api-production-881ea.up.railway.app';
  return url.replace(/\/+$/, '');
}

async function forwardRequest(request: NextRequest, { params }: { params: { path?: string[] } }) {
  const path = params.path ? params.path.join('/') : '';
  const search = request.nextUrl.search;
  const backendBase = getBackendBaseUrl();
  const targetUrl = `${backendBase}/api/v1/${path}${search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    // Exclude host and content-length to avoid proxy conflicts
    if (key.toLowerCase() !== 'host' && key.toLowerCase() !== 'content-length') {
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

    const responseHeaders = new Headers();
    backendResponse.headers.forEach((value, key) => {
      responseHeaders.set(key, value);
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
