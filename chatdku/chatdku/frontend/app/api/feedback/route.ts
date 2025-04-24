import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    
    console.log('Proxying feedback to backend service');
    
    const backendUrl = 'https://10.200.14.82:9013/save-feedback';
    
    const backendResponse = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    
    if (!backendResponse.ok) {
      console.error(`Backend feedback error: ${backendResponse.status}`);
      return new NextResponse(`Error from backend: ${backendResponse.statusText}`, {
        status: backendResponse.status,
      });
    }
    
    return new NextResponse(JSON.stringify({ success: true }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  } catch (error) {
    console.error('Error proxying feedback to backend:', error);
    return new NextResponse(JSON.stringify({ 
      success: false, 
      error: error instanceof Error ? error.message : 'Unknown error' 
    }), {
      status: 500,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }
}
