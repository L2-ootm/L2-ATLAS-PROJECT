/**
 * Atlas Inbound Route — REST API
 * 
 * Endpoint: /api/atlas
 * 
 * Recebe comandos e eventos vindos do L2 Atlas para o L2-Cashflow.
 * Pode ser usado para atualizar status de serviços, sincronizar dados, etc.
 * 
 * Autenticação via Bearer Token (L2_ATLAS_API_KEY).
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  clientRepo,
  expenseRepo,
  invoiceRepo,
  getFinancialSummary,
  usageRepo,
} from '@/lib/repositories';

// Validate API key from request
function validateApiKey(request: NextRequest): boolean {
  const apiKey = process.env.L2_ATLAS_API_KEY;
  if (!apiKey) return true; // Dev mode: no key required

  const authHeader = request.headers.get('Authorization');
  if (!authHeader) return false;

  return authHeader.replace('Bearer ', '') === apiKey;
}

/**
 * GET /api/atlas
 * 
 * Returns a summary of available endpoints and system health.
 */
export async function GET(request: NextRequest) {
  if (!validateApiKey(request)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const summary = getFinancialSummary();

  return NextResponse.json({
    service: 'l2-cashflow',
    version: '1.0.0',
    status: 'healthy',
    timestamp: new Date().toISOString(),
    summary,
    endpoints: {
      mcp: '/api/mcp',
      atlas: '/api/atlas',
      webhooks_info: 'Outbound webhooks are dispatched to L2_ATLAS_WEBHOOK_URL',
    },
  });
}

/**
 * POST /api/atlas
 * 
 * Receives commands from L2 Atlas. Supported actions:
 * - get_clients
 * - get_expenses
 * - get_invoices
 * - get_financial_summary
 * - get_ai_usage
 * - ping
 */
export async function POST(request: NextRequest) {
  if (!validateApiKey(request)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { action, params } = body;

    if (!action) {
      return NextResponse.json(
        { error: 'Missing required field: action' },
        { status: 400 }
      );
    }

    switch (action) {
      case 'ping':
        return NextResponse.json({
          success: true,
          pong: true,
          timestamp: new Date().toISOString(),
        });

      case 'get_clients': {
        const clients = params?.activeOnly
          ? clientRepo.getActive()
          : clientRepo.getAll();
        return NextResponse.json({ success: true, data: clients });
      }

      case 'get_expenses': {
        let expenses;
        if (params?.month) {
          expenses = expenseRepo.getByMonth(params.month);
        } else if (params?.clientId) {
          expenses = expenseRepo.getByClient(params.clientId);
        } else {
          expenses = expenseRepo.getAll();
        }
        return NextResponse.json({ success: true, data: expenses });
      }

      case 'get_invoices': {
        let invoices;
        if (params?.status === 'atrasado') {
          invoices = invoiceRepo.getOverdue();
        } else if (params?.status) {
          invoices = invoiceRepo.getByStatus(params.status);
        } else {
          invoices = invoiceRepo.getAll();
        }
        return NextResponse.json({ success: true, data: invoices });
      }

      case 'get_financial_summary': {
        const summary = getFinancialSummary();
        return NextResponse.json({ success: true, data: summary });
      }

      case 'get_ai_usage': {
        const events = params?.clientId
          ? usageRepo.getByClient(params.clientId, params?.limit || 100)
          : usageRepo.getAll(params?.limit || 100);
        return NextResponse.json({ success: true, data: events });
      }

      default:
        return NextResponse.json(
          { error: `Unknown action: ${action}` },
          { status: 400 }
        );
    }
  } catch (error) {
    console.error('[Atlas API] Error:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}
