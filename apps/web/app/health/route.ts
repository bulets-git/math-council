import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  let backendBase = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!backendBase || backendBase.includes('api:8000') || (process.env.NODE_ENV === 'production' && backendBase.includes('localhost'))) {
    backendBase = 'https://api-production-881ea.up.railway.app';
  }
  backendBase = backendBase.replace(/\/+$/, '');
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
