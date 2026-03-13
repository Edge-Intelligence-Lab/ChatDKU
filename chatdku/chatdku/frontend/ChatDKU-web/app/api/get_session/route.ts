import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-static';

export async function GET(request: NextRequest) {
  const mockSession = {
    session_id: 'dev-session-' + Date.now(),
  };

  return NextResponse.json(mockSession);
}

export async function POST(request: NextRequest) {
  const mockSession = {
    session_id: 'dev-session-' + Date.now(),
  };

  return NextResponse.json(mockSession);
}
