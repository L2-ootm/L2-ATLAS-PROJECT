import { NextRequest, NextResponse } from 'next/server';
import { evaluateStudentRisk } from '@/lib/engine/degradation';

export async function POST(request: NextRequest) {
  // Simples verificação de segurança para CRON/Workers
  const authHeader = request.headers.get('Authorization');
  const cronSecret = process.env.CRON_SECRET || 'dev-secret-key';

  if (authHeader !== `Bearer ${cronSecret}` && process.env.NODE_ENV === 'production') {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { userId, clientId } = body;

    if (!userId || !clientId) {
      return NextResponse.json({ error: 'Missing userId or clientId' }, { status: 400 });
    }

    const result = await evaluateStudentRisk(userId, clientId);

    return NextResponse.json({
      success: true,
      data: result
    });

  } catch (error) {
    console.error('[Engine API] Error evaluating student risk:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
