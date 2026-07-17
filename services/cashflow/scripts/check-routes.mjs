const baseUrl = process.env.CASHFLOW_TEST_URL || "http://localhost:3000";

const routes = [
  "/dashboard",
  "/clientes",
  "/contratos",
  "/enterprise/pnl",
  "/enterprise/explorer",
  "/enterprise/research",
  "/enterprise/billing",
  "/enterprise/forecast",
  "/enterprise/reports",
  "/enterprise/audit",
  "/faturas",
  "/despesas",
  "/fluxo-caixa",
  "/socios",
  "/relatorios",
];

const failures = [];

for (const route of routes) {
  try {
    const response = await fetch(`${baseUrl}${route}`);
    const result = `${response.status}`.padEnd(4);
    console.log(`${result} ${route}`);
    if (!response.ok) failures.push(`${route} returned HTTP ${response.status}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.log(`ERR  ${route}`);
    failures.push(`${route} could not be reached: ${message}`);
  }
}

if (failures.length > 0) {
  console.error(`\n${failures.length} cashflow route check(s) failed:`);
  for (const failure of failures) console.error(`- ${failure}`);
  process.exitCode = 1;
} else {
  console.log(`\nAll ${routes.length} cashflow routes returned successfully.`);
}
