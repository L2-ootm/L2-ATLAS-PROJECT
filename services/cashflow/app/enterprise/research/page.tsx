import { researchRepo } from "@/lib/repositories";

export default async function ResearchCenterPage() {
  const clientId = 'tds-enterprise-001';
  
  // Seed some dummy data if empty so the UI doesn't look blank during demo
  let jobs = await researchRepo.getJobsByClient(clientId);
  
  if (jobs.length === 0) {
    await researchRepo.create({
      client_id: clientId,
      query: "Top 10 business schools in Europe requirements",
      priority: "high",
      status: "completed",
      provider_used: "tavily-search",
      cost_brl: 0.12,
      converted_to_knowledge_pack: true,
      created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString()
    });
    await researchRepo.create({
      client_id: clientId,
      query: "MIT financial aid options for international students",
      priority: "normal",
      status: "completed",
      provider_used: "perplexity-sonar",
      cost_brl: 0.08,
      converted_to_knowledge_pack: false,
      created_at: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString()
    });
    jobs = await researchRepo.getJobsByClient(clientId);
  }

  const stats = await researchRepo.getROIStats(clientId);

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <header style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "#F1F3F6", margin: "0 0 8px 0" }}>Research Cost Center</h1>
        <p style={{ color: "#9CA3B4", margin: 0, fontSize: 14 }}>
          Controle os custos da API de Busca Externa e o ROI dos Knowledge Packs.
        </p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 32 }}>
        <div style={{ padding: 24, background: "#11141A", border: "1px solid #1D212A", borderRadius: 12 }}>
          <p style={{ color: "#9CA3B4", margin: "0 0 8px 0", fontSize: 13, textTransform: "uppercase", letterSpacing: 1 }}>Custo Total de Pesquisa</p>
          <div style={{ fontSize: 28, fontWeight: 600, color: "#fff" }}>
            {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(stats.totalSpent)}
          </div>
        </div>
        <div style={{ padding: 24, background: "#11141A", border: "1px solid #1D212A", borderRadius: 12 }}>
          <p style={{ color: "#9CA3B4", margin: "0 0 8px 0", fontSize: 13, textTransform: "uppercase", letterSpacing: 1 }}>Knowledge Packs Criados</p>
          <div style={{ fontSize: 28, fontWeight: 600, color: "#22C55E" }}>
            {stats.packsCreated}
          </div>
        </div>
        <div style={{ padding: 24, background: "#11141A", border: "1px solid #1D212A", borderRadius: 12 }}>
          <p style={{ color: "#9CA3B4", margin: "0 0 8px 0", fontSize: 13, textTransform: "uppercase", letterSpacing: 1 }}>Economia Projetada (Reuso)</p>
          <div style={{ fontSize: 28, fontWeight: 600, color: "#3B82F6" }}>
            {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(stats.estimatedSavings)}
          </div>
        </div>
      </div>

      <div style={{ background: "#11141A", border: "1px solid #1D212A", borderRadius: 12, overflow: "hidden" }}>
        <div style={{ padding: "16px 24px", borderBottom: "1px solid #1D212A" }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "#F1F3F6", margin: 0 }}>Últimas Pesquisas (Jobs)</h2>
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#0B0E14", color: "#9CA3B4", fontSize: 12, textTransform: "uppercase" }}>
              <th style={{ padding: "12px 24px", textAlign: "left" }}>Data</th>
              <th style={{ padding: "12px 24px", textAlign: "left" }}>Query</th>
              <th style={{ padding: "12px 24px", textAlign: "left" }}>Provider</th>
              <th style={{ padding: "12px 24px", textAlign: "right" }}>Custo</th>
              <th style={{ padding: "12px 24px", textAlign: "center" }}>Virou KP?</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id} style={{ borderBottom: "1px solid #1D212A", color: "#E2E8F0", fontSize: 14 }}>
                <td style={{ padding: "16px 24px" }}>{new Date(job.created_at).toLocaleDateString('pt-BR')}</td>
                <td style={{ padding: "16px 24px" }}>{job.query}</td>
                <td style={{ padding: "16px 24px" }}>
                  <span style={{ padding: "4px 8px", background: "#1D212A", borderRadius: 4, fontSize: 12 }}>
                    {job.provider_used || 'pending'}
                  </span>
                </td>
                <td style={{ padding: "16px 24px", textAlign: "right" }}>
                  {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(job.cost_brl)}
                </td>
                <td style={{ padding: "16px 24px", textAlign: "center" }}>
                  {job.converted_to_knowledge_pack ? "✅" : "❌"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
