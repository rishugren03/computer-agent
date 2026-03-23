import { NextResponse } from 'next/server';
import { prisma } from '@ghost-os/database';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { li_at, JSESSIONID } = body;

    if (!li_at || !JSESSIONID) {
      return NextResponse.json(
        { error: 'Missing required cookies: li_at and JSESSIONID' },
        { status: 400 }
      );
    }

    // Store or update the session
    const session = await prisma.userSession.create({
      data: {
        linkedinCookie: li_at,
        linkedinCsrf: JSESSIONID,
      },
    });

    return NextResponse.json({ success: true, session });
  } catch (error) {
    console.error('Failed to sync session:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
