import { createClientAccount, createContract, logUsageEvent } from './lib/db/enterprise';
import { generateId } from './lib/utils';

console.log("Injetando dados mockados da TDS...");

const clientId = 'tds-enterprise-001';

// Criar cliente
try {
  createClientAccount({
    id: clientId,
    name: 'TDS (Mock)',
    legal_name: 'TDS Educacional Ltda',
    cnpj: '00.000.000/0001-00',
    segment: 'Education',
    estimated_monthly_revenue_brl: 1100000,
    active_students: 2000,
    total_users: 2200
  });
  console.log("Cliente criado.");
} catch (e) {
  console.log("Cliente já existe ou erro:", e);
}

// Criar contrato
try {
  createContract({
    id: 'contract-tds-op',
    client_id: clientId,
    name: 'TDS AI ECOSYSTEM - Operation',
    contract_type: 'Operation',
    setup_fee_brl: 0,
    monthly_fee_brl: 22000,
    min_margin_brl: 4500
  });
  console.log("Contrato criado.");
} catch (e) {
  console.log("Contrato já existe ou erro:", e);
}

// Injetar alguns dias de uso
const daysToMock = 12; // Vamos simular 12 dias de uso no mês atual
const baseCostPerDay = 250; // Custo diário base
const today = new Date();

let totalEvents = 0;

for (let i = 0; i < daysToMock; i++) {
  // Simula ~50 sessões/eventos por dia
  for (let j = 0; j < 50; j++) {
    // Variância no custo de cada evento
    const costBrl = (Math.random() * 8) + 1; // R$ 1 a 9 por evento
    
    // Distribuir as datas para trás
    const eventDate = new Date(today);
    eventDate.setDate(today.getDate() - i);
    // Ajustar a data no logUsageEvent (precisamos fazer um hackzinho na data se o método não aceitar created_at, mas o método atual usa default current_timestamp)
    // Para contornar, faremos inserções normais, mas se quisermos datas retroativas o correto é atualizar depois, ou não ligar pra data exata e simular só o acumulado de hoje.
    // Vamos apenas inserir como "hoje" porque o Client P&L vai puxar pelo strftime('%Y-%m', created_at) que cobre o mês inteiro!
    
    logUsageEvent({
      id: generateId(),
      client_id: clientId,
      user_id: `aluno-${Math.floor(Math.random() * 2000)}`,
      session_id: `sess-${generateId()}`,
      event_type: 'api_call',
      plan_at_time: 'Core',
      model_provider: 'openai',
      model_name: Math.random() > 0.8 ? 'gpt-4o' : 'gpt-3.5-turbo',
      input_tokens: Math.floor(Math.random() * 2000),
      output_tokens: Math.floor(Math.random() * 500),
      cost_usd: costBrl / 5.5,
      cost_brl: costBrl
    });
    totalEvents++;
  }
}

console.log(`Mock finalizado. ${totalEvents} eventos de uso gerados para o mês atual.`);
