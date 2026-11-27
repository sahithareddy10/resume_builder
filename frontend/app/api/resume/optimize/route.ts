import { NextResponse } from 'next/server';

export const maxDuration = 600;

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8001';

export async function POST(request: Request) {
  const body = await request.text();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 600000);
  try {
    const res = await fetch(`${BACKEND_URL}/api/resume/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      signal: controller.signal,
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { 'Content-Type': res.headers.get('content-type') || 'application/json' },
    });
  } catch (error: any) {
    const timedOut = error?.name === 'AbortError';
    return NextResponse.json(
      {
        success: false,
        error: timedOut
          ? 'Optimization timed out. Keep Ollama open and wait — the local model can take a few minutes.'
          : 'Backend connection failed. Ensure the backend is running on port 8001.',
      },
      { status: timedOut ? 504 : 502 }
    );
  } finally {
    clearTimeout(timer);
  }
}
