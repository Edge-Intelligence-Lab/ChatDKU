import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    
    console.log('Proxying request to chat backend service');
    
    const backendBase = process.env.BACKEND_INTERNAL_URL || 'http://localhost:9015';
    const backendUrl = `${backendBase.replace(/\/$/, '')}/chat`;
    console.log(`Sending request to: ${backendUrl}`);
    
    // No built-in way to ignore SSL certificate errors in browser fetch
    // So we use our Next.js server as a proxy
    const backendResponse = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    
    if (!backendResponse.ok) {
      console.error(`Backend error: ${backendResponse.status} ${backendResponse.statusText}`);
      return new NextResponse(`Backend error: ${backendResponse.statusText}`, { 
        status: backendResponse.status 
      });
    }
    
    const data = await backendResponse.text();
    return new NextResponse(data);
  } catch (error) {
    console.error('Error proxying to backend:', error);
    return new NextResponse(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`, { 
      status: 500 
    });
  }
}
