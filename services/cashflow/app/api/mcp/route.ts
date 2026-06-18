/**
 * MCP Transport Route — Streamable HTTP (Web Standard)
 * 
 * Endpoint: /api/mcp
 * 
 * Este endpoint expõe o servidor MCP via Web Standard Streamable HTTP transport.
 * O L2 Atlas se conecta aqui para chamar as ferramentas do L2-Cashflow.
 * 
 * Autenticação via Bearer Token (L2_ATLAS_API_KEY).
 */

import { NextRequest, NextResponse } from 'next/server';
import { createMcpServer } from '@/lib/mcp/server';
import { WebStandardStreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js';

// Validate API key from request
function validateApiKey(request: NextRequest): boolean {
  const apiKey = process.env.L2_ATLAS_API_KEY;
  
  // If no API key is configured, allow all requests (development mode)
  if (!apiKey) return true;

  const authHeader = request.headers.get('Authorization');
  if (!authHeader) return false;

  const token = authHeader.replace('Bearer ', '');
  return token === apiKey;
}

export async function POST(request: NextRequest) {
  if (!validateApiKey(request)) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    );
  }

  try {
    // Create a stateless transport (new instance per request)
    const transport = new WebStandardStreamableHTTPServerTransport({
      sessionIdGenerator: undefined, // stateless mode
      enableJsonResponse: true,      // prefer JSON over SSE for simple request/response
    });

    const server = createMcpServer();
    await server.connect(transport);

    // Parse the body before passing to transport
    const body = await request.json();

    // handleRequest takes a Web Standard Request and returns a Web Standard Response
    const response = await transport.handleRequest(request as unknown as Request, {
      parsedBody: body,
    });

    // Close transport after handling the request
    await server.close();

    return response;
  } catch (error) {
    console.error('[MCP] Error handling request:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}

// Handle GET for server information / SSE stream initialization
export async function GET(request: NextRequest) {
  if (!validateApiKey(request)) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    );
  }

  // If Accept header requests SSE, try to establish SSE connection
  const acceptHeader = request.headers.get('Accept') || '';
  if (acceptHeader.includes('text/event-stream')) {
    try {
      const transport = new WebStandardStreamableHTTPServerTransport({
        sessionIdGenerator: undefined,
      });

      const server = createMcpServer();
      await server.connect(transport);

      return await transport.handleRequest(request as unknown as Request);
    } catch (error) {
      console.error('[MCP] Error handling SSE request:', error);
      return NextResponse.json(
        { error: 'Internal Server Error' },
        { status: 500 }
      );
    }
  }

  // Otherwise return server info
  return NextResponse.json({
    name: 'l2-cashflow',
    version: '1.0.0',
    protocol: 'mcp',
    description: 'L2-Cashflow MCP Server — Financial data tools for L2 Atlas',
    tools: [
      'get_clients',
      'get_client_by_id',
      'get_financial_summary',
      'get_invoices',
      'get_expenses',
      'add_expense',
      'get_ai_usage',
    ],
  });
}

// Handle DELETE for session termination
export async function DELETE(request: NextRequest) {
  if (!validateApiKey(request)) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    );
  }

  // In stateless mode, just acknowledge the delete
  return new NextResponse(null, { status: 200 });
}
