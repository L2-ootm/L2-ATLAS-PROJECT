/**
 * MCP Server — L2-Cashflow Tools for L2 Atlas
 * 
 * Registra as ferramentas (Tools) que o L2 Atlas pode chamar
 * via protocolo MCP para consultar dados financeiros do L2-Cashflow.
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';

import {
  clientRepo,
  expenseRepo,
  invoiceRepo,
  usageRepo,
  getFinancialSummary,
} from '../repositories';

export function createMcpServer(): McpServer {
  const server = new McpServer({
    name: 'l2-cashflow',
    version: '1.0.0',
  });

  // --------------------------------------------------
  // Tool: get_clients
  // --------------------------------------------------
  server.tool(
    'get_clients',
    'Lista todos os clientes do L2-Cashflow. Pode filtrar apenas os ativos.',
    {
      activeOnly: z.boolean().optional().describe('Se true, retorna apenas clientes ativos'),
    },
    async ({ activeOnly }) => {
      const clients = activeOnly ? clientRepo.getActive() : clientRepo.getAll();
      return {
        content: [
          {
            type: 'text' as const,
            text: JSON.stringify(clients, null, 2),
          },
        ],
      };
    }
  );

  // --------------------------------------------------
  // Tool: get_client_by_id
  // --------------------------------------------------
  server.tool(
    'get_client_by_id',
    'Busca um cliente específico pelo ID.',
    {
      clientId: z.string().describe('ID do cliente'),
    },
    async ({ clientId }) => {
      const client = clientRepo.getById(clientId);
      return {
        content: [
          {
            type: 'text' as const,
            text: client
              ? JSON.stringify(client, null, 2)
              : JSON.stringify({ error: 'Cliente não encontrado' }),
          },
        ],
      };
    }
  );

  // --------------------------------------------------
  // Tool: get_financial_summary
  // --------------------------------------------------
  server.tool(
    'get_financial_summary',
    'Retorna um resumo financeiro do mês atual: receita, despesas, saldo, clientes ativos, faturas pendentes/atrasadas.',
    {},
    async () => {
      const summary = await getFinancialSummary();
      return {
        content: [
          {
            type: 'text' as const,
            text: JSON.stringify(summary, null, 2),
          },
        ],
      };
    }
  );

  // --------------------------------------------------
  // Tool: get_invoices
  // --------------------------------------------------
  server.tool(
    'get_invoices',
    'Lista faturas do L2-Cashflow. Pode filtrar por status (pendente, pago, atrasado).',
    {
      status: z.enum(['pendente', 'pago', 'atrasado']).optional().describe('Filtrar por status da fatura'),
    },
    async ({ status }) => {
      let invoices;
      if (status === 'atrasado') {
        invoices = invoiceRepo.getOverdue();
      } else if (status) {
        invoices = invoiceRepo.getByStatus(status);
      } else {
        invoices = invoiceRepo.getAll();
      }
      return {
        content: [
          {
            type: 'text' as const,
            text: JSON.stringify(invoices, null, 2),
          },
        ],
      };
    }
  );

  // --------------------------------------------------
  // Tool: get_expenses
  // --------------------------------------------------
  server.tool(
    'get_expenses',
    'Lista despesas do L2-Cashflow. Pode filtrar por mês (YYYY-MM) ou por cliente.',
    {
      month: z.string().optional().describe('Filtrar por mês no formato YYYY-MM'),
      clientId: z.string().optional().describe('Filtrar por ID do cliente'),
    },
    async ({ month, clientId }) => {
      let expenses;
      if (month) {
        expenses = expenseRepo.getByMonth(month);
      } else if (clientId) {
        expenses = expenseRepo.getByClient(clientId);
      } else {
        expenses = expenseRepo.getAll();
      }
      return {
        content: [
          {
            type: 'text' as const,
            text: JSON.stringify(expenses, null, 2),
          },
        ],
      };
    }
  );

  // --------------------------------------------------
  // Tool: add_expense
  // --------------------------------------------------
  server.tool(
    'add_expense',
    'Registra uma nova despesa no L2-Cashflow.',
    {
      id: z.string().describe('ID único da despesa'),
      category: z.enum(['Software', 'Marketing', 'Equipamento', 'Infraestrutura', 'Pessoal', 'Outros']).describe('Categoria'),
      description: z.string().describe('Descrição da despesa'),
      amount: z.number().describe('Valor em BRL'),
      date: z.string().describe('Data no formato YYYY-MM-DD'),
      clientId: z.string().optional().describe('ID do cliente associado (opcional)'),
      recurring: z.boolean().optional().describe('Se a despesa é recorrente'),
    },
    async ({ id, category, description, amount, date, clientId, recurring }) => {
      const expense = expenseRepo.create({
        id,
        clientId: clientId || null,
        category,
        description,
        amount,
        date,
        recurring: recurring || false,
      });
      return {
        content: [
          {
            type: 'text' as const,
            text: JSON.stringify({ success: true, expense }, null, 2),
          },
        ],
      };
    }
  );

  // --------------------------------------------------
  // Tool: get_ai_usage
  // --------------------------------------------------
  server.tool(
    'get_ai_usage',
    'Retorna eventos de uso de IA (tokens, custos) do L2-Cashflow. Pode filtrar por cliente.',
    {
      clientId: z.string().optional().describe('Filtrar por ID do cliente'),
      limit: z.number().optional().describe('Número máximo de registros (padrão: 100)'),
    },
    async ({ clientId, limit }) => {
      const events = clientId
        ? usageRepo.getByClient(clientId, limit || 100)
        : usageRepo.getAll(limit || 100);
      return {
        content: [
          {
            type: 'text' as const,
            text: JSON.stringify(events, null, 2),
          },
        ],
      };
    }
  );

  return server;
}
