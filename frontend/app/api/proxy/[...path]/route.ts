import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8001';

export async function GET(request: Request) {
 const url = new URL(request.url);
 return proxyFetch('GET', `${BACKEND_URL}${url.pathname}${url.search}`);
}

export async function POST(request: Request) {
 const url = new URL(request.url);
 const contentType = request.headers.get('content-type') || '';

 if (contentType.includes('multipart/form-data')) {
 // Forward FormData (file uploads) without reading as text
 const formData = await request.formData();
 const backendFormData = new FormData();
 for (const [key, value] of formData.entries()) {
 backendFormData.append(key, value);
 }
 const res = await fetch(`${BACKEND_URL}${url.pathname}${url.search}`, {
 method: 'POST',
 headers: { 'Content-Type': contentType },
 body: backendFormData,
 });
 const responseBody = await res.text();
 return new NextResponse(responseBody, {
 status: res.status,
 headers: { 'Content-Type': res.headers.get('content-type') || 'application/json' },
 });
 }

 const body = await request.text();
 return proxyFetch('POST', `${BACKEND_URL}${url.pathname}${url.search}`, body, request.headers);
}

export async function PUT(request: Request) {
 const url = new URL(request.url);
 const body = await request.text();
 return proxyFetch('PUT', `${BACKEND_URL}${url.pathname}${url.search}`, body, request.headers);
}

export async function DELETE(request: Request) {
 const url = new URL(request.url);
 return proxyFetch('DELETE', `${BACKEND_URL}${url.pathname}${url.search}`);
}

async function proxyFetch(
 method: string,
 url: string,
 body?: string,
 headers?: Headers
): Promise<NextResponse> {
 try {
 const fetchHeaders: HeadersInit = {};

 if (headers) {
 for (const [key, value] of headers.entries()) {
 if (key !== 'host') {
 fetchHeaders[key] = value;
 }
 }
 }

 const res = await fetch(url, {
 method,
 headers: fetchHeaders,
 body: body || undefined,
 });

 const responseBody = await res.text();

 return new NextResponse(responseBody, {
 status: res.status,
 headers: {
 'Content-Type': res.headers.get('content-type') || 'application/json',
 },
 });
 } catch (error) {
 return NextResponse.json(
 { detail: 'Backend connection failed. Ensure the backend is running on port 8001.' },
 { status: 502 }
 );
 }
}
