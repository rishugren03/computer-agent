import { NextResponse } from 'next/server'

export async function POST() {
  return NextResponse.json(
    { error: 'Use the /accounts/{id}/session endpoint on the agent API instead' },
    { status: 410 }
  )
}
