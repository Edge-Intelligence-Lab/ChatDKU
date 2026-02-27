import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-static';

export async function GET(request: NextRequest) {
  // Mock user data for development
  const mockUser = {
    eppn: 'dev-user@example.edu',
    displayName: 'Development User',
    username: 'dev-user',
    name: 'Development User',
    profile: 'Development user profile for testing',
  };

  return NextResponse.json(mockUser);
}

export async function POST(request: NextRequest) {
  // Handle profile updates
  const body = await request.json();
  
  const mockUser = {
    eppn: 'dev-user@example.edu',
    displayName: 'Development User',
    username: 'dev-user',
    name: 'Development User',
    profile: body.profile || 'Development user profile for testing',
  };

  return NextResponse.json(mockUser);
}
