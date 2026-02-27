import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    let body;
    try {
      body = await request.json();
    } catch (parseError) {
      return new NextResponse(JSON.stringify({ 
        error: 'Invalid request body' 
      }), {
        status: 400,
        headers: {
          'Content-Type': 'application/json',
        },
      });
    }
    
    // Validate required fields
    if (!body.userInput || !body.botAnswer || !body.feedbackReason || body.chatHistoryId === undefined || body.chatHistoryId === null) {
      return new NextResponse(JSON.stringify({ 
        error: 'Missing required fields' 
      }), {
        status: 400,
        headers: {
          'Content-Type': 'application/json',
        },
      });
    }
    
    // Validate chat history ID format
    if (typeof body.chatHistoryId !== 'string' || body.chatHistoryId.trim() === '') {
      return new NextResponse(JSON.stringify({ 
        error: 'Invalid chat history ID' 
      }), {
        status: 400,
        headers: {
          'Content-Type': 'application/json',
        },
      });
    }
    
    console.log('Proxying feedback to backend service');
    
    const backendBase = process.env.BACKEND_INTERNAL_URL || 'http://localhost:9015';
    const backendUrl = process.env.BACKEND_FEEDBACK_URL || `${backendBase.replace(/\/$/, '')}/feedback`;
    
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
