import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const backendBase = (process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
  const targetUrl = `${backendBase}/health`;

  try {
    const backendResponse = await fetch(targetUrl, { cache: 'no-store' });
    const data = await backendResponse.json();
    return NextResponse.json(data, { status: backendResponse.status });
  } catch (error: any) {
    return NextResponse.json(
      { status: 'unhealthy', error: error?.message || 'Cannot reach backend' },
      { status: 503 }
    );
  }
}
