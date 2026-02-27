import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-static';

export async function GET(request: NextRequest) {
  // Mock session data for development
  const mockSession = {
    session_id: 'dev-session-' + Date.now(),
    user: {
      eppn: 'dev-user@example.edu',
      displayName: 'Development User',
    },
    csrf_token: 'dev-csrf-token',
  };

  return NextResponse.json(mockSession);
}

export async function POST(request: NextRequest) {
  // Handle session creation/update
  const mockSession = {
    session_id: 'dev-session-' + Date.now(),
    user: {
      eppn: 'dev-user@example.edu',
      displayName: 'Development User',
    },
    csrf_token: 'dev-csrf-token',
  };

  return NextResponse.json(mockSession);
}
