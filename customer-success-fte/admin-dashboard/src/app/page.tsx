export const dynamic = 'force-dynamic';

export default async function DashboardPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  
  let metrics = null;
  let adminMetrics = null;
  
  try {
    const res = await fetch(`${apiUrl}/metrics`, { cache: 'no-store' });
    if (res.ok) {
      metrics = await res.json();
    }
    
    const adminRes = await fetch(`${apiUrl}/api/v1/admin/metrics`, { cache: 'no-store' });
    if (adminRes.ok) {
      adminMetrics = await adminRes.json();
    }
  } catch (err) {
    console.error('Failed to fetch metrics', err);
  }

  return (
    <div className="animate-fade-in">
      <h2 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '24px' }}>System Overview</h2>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '24px', marginBottom: '32px' }}>
        <div className="data-card">
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '8px' }}>Total Agent Invocations</p>
          <h3 style={{ fontSize: '32px', fontWeight: 700 }}>{metrics?.total_requests || 0}</h3>
        </div>
        <div className="data-card">
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '8px' }}>Escalation Rate</p>
          <h3 style={{ fontSize: '32px', fontWeight: 700 }}>{metrics && metrics.escalation_rate_pct !== undefined ? metrics.escalation_rate_pct.toFixed(1) : 0}%</h3>
        </div>
        <div className="data-card">
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '8px' }}>Avg Processing Time</p>
          <h3 style={{ fontSize: '32px', fontWeight: 700 }}>{metrics && metrics.avg_processing_ms !== undefined ? metrics.avg_processing_ms.toFixed(0) : 0} ms</h3>
        </div>
      </div>
      
      {adminMetrics && (
        <>
          <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>Channel Breakdown ({adminMetrics.time_range})</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '24px' }}>
             {(adminMetrics.channels || []).map((ch: any) => (
                <div key={ch.channel} className="data-card">
                   <h4 style={{ textTransform: 'uppercase', fontSize: '14px', letterSpacing: '0.5px', marginBottom: '12px', color: 'var(--primary)' }}>{ch.channel}</h4>
                   <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Messages Processed</span>
                      <span style={{ fontWeight: 600 }}>{ch.message_count}</span>
                   </div>
                   <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Tickets Created</span>
                      <span style={{ fontWeight: 600 }}>{ch.ticket_count}</span>
                   </div>
                </div>
             ))}
          </div>
        </>
      )}
    </div>
  );
}
