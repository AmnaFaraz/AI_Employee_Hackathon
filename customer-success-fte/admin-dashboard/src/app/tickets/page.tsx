import Link from 'next/link';

export const dynamic = 'force-dynamic';

export default async function TicketsPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  let tickets: any[] = [];

  try {
    const res = await fetch(`${apiUrl}/api/v1/tickets?page_size=50`, { cache: 'no-store' });
    if (res.ok) {
      tickets = await res.json();
    }
  } catch (err) {
    console.error('Failed to fetch tickets', err);
  }

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h2 style={{ fontSize: '24px', fontWeight: 700 }}>Support Tickets</h2>
      </div>

      <div className="data-card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ background: 'var(--bg-page)', borderBottom: '1px solid var(--border)' }}>
              <th style={{ padding: '16px', fontWeight: 600, fontSize: '14px', color: 'var(--text-muted)' }}>Ticket ID</th>
              <th style={{ padding: '16px', fontWeight: 600, fontSize: '14px', color: 'var(--text-muted)' }}>Subject</th>
              <th style={{ padding: '16px', fontWeight: 600, fontSize: '14px', color: 'var(--text-muted)' }}>Status</th>
              <th style={{ padding: '16px', fontWeight: 600, fontSize: '14px', color: 'var(--text-muted)' }}>Priority</th>
              <th style={{ padding: '16px', fontWeight: 600, fontSize: '14px', color: 'var(--text-muted)' }}>Created</th>
              <th style={{ padding: '16px', fontWeight: 600, fontSize: '14px', color: 'var(--text-muted)' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {tickets.length === 0 ? (
              <tr><td colSpan={6} style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>No tickets found</td></tr>
            ) : tickets.map((t) => (
              <tr key={t.id} style={{ borderBottom: '1px solid var(--border)', transition: 'background 0.2s' }}>
                <td style={{ padding: '16px', fontSize: '14px', fontFamily: 'monospace' }}>{t.id.substring(0,8)}</td>
                <td style={{ padding: '16px', fontSize: '14px', fontWeight: 500 }}>{t.subject || 'No Subject'}</td>
                <td style={{ padding: '16px' }}>
                  <span className={`status-badge ${t.status.toLowerCase()}`}>{t.status.replace('_', ' ')}</span>
                </td>
                <td style={{ padding: '16px', fontSize: '14px', textTransform: 'capitalize' }}>{t.priority}</td>
                <td style={{ padding: '16px', fontSize: '14px', color: 'var(--text-muted)' }}>
                  {new Date(t.created_at).toLocaleDateString()}
                </td>
                <td style={{ padding: '16px' }}>
                  <Link href={`/tickets/${t.id}`} style={{ color: 'var(--primary)', fontSize: '14px', fontWeight: 500 }}>
                    View &rarr;
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
