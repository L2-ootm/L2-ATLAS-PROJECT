import { createPlusSubscription, logBillingEvent } from './lib/db/enterprise';
import { generateId } from './lib/utils';

console.log("Injetando dados mockados de Billing Plus (TDS)...");

const clientId = 'tds-enterprise-001';
const GATEWAY_FEE_RATE = 0.0499; // 4.99%
const L2_SHARE_RATE = 0.30;      // 30% L2
const CLIENT_SHARE_RATE = 0.70;  // 70% Cliente

// Criar 15 assinaturas Plus
const plans = ['LeticIA Plus', 'LeticIA Plus Pro'];
const gateways = ['stripe', 'hotmart'];
const subIds: string[] = [];

for (let i = 0; i < 15; i++) {
  const subId = generateId();
  subIds.push(subId);
  const plan = i < 10 ? plans[0] : plans[1];
  const price = plan === 'LeticIA Plus' ? 29.90 : 49.90;
  const gw = gateways[i % 2];

  try {
    createPlusSubscription({
      id: subId,
      client_id: clientId,
      user_id: `aluno-plus-${i + 1}`,
      plan_name: plan,
      price_brl: price,
      gateway: gw,
      gateway_subscription_id: `sub_${gw}_${generateId()}`,
      started_at: '2026-06-01'
    });
  } catch (e) {
    console.log(`Sub ${i} já existe ou erro`, e);
  }
}

console.log(`${subIds.length} assinaturas criadas.`);

// Criar eventos de pagamento para cada assinatura (simulando pagamento do mês)
let totalEvents = 0;
for (let i = 0; i < subIds.length; i++) {
  const plan = i < 10 ? plans[0] : plans[1];
  const price = plan === 'LeticIA Plus' ? 29.90 : 49.90;
  const gatewayFee = price * GATEWAY_FEE_RATE;
  const net = price - gatewayFee;
  const l2Share = net * L2_SHARE_RATE;
  const clientShare = net * CLIENT_SHARE_RATE;

  try {
    logBillingEvent({
      id: generateId(),
      subscription_id: subIds[i],
      client_id: clientId,
      user_id: `aluno-plus-${i + 1}`,
      event_type: 'payment_received',
      amount_brl: price,
      gateway_fee_brl: gatewayFee,
      net_amount_brl: net,
      l2_share_brl: l2Share,
      client_share_brl: clientShare,
      gateway_transaction_id: `txn_${generateId()}`,
      period_start: '2026-06-01',
      period_end: '2026-06-30'
    });
    totalEvents++;
  } catch (e) {
    console.log(`Evento ${i} erro`, e);
  }
}

console.log(`${totalEvents} eventos de billing gerados.`);
console.log("Mock de Billing Plus finalizado!");
