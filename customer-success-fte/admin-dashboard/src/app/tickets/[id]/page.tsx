export const dynamic = 'force-dynamic';
import Link from 'next/link';

async function fetchTicketData(id: string) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const ticketRes = await fetch(`${apiUrl}/api/v1/tickets/${id}`, { cache: 'no-store' });
  if (!ticketRes.ok) return null;
  const ticket = await ticketRes.json();

  let conversation: any[] = [];
  if (ticket.customer_id) {
    const convRes = await fetch(`${apiUrl}/api/v1/customers/${ticket.customer_id}/conversations?limit=100`, { cache: 'no-store' });
    if (convRes.ok) {
       const convData = await convRes.json();
       conversation = convData.conversations.flatMap((c: any) => c.messages).sort((a: any, b: any) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    }
  }

  return { ticket, conversation };
}

export default async function TicketDetailPage({ params }: { params: { id: string } }) {
  const data = await fetchTicketData(params.id);

  if (!data) {
    return (
      <div className="animate-fade-in">
        <h2>Ticket Not Found</h2>
        <Link href="/tickets">← Back to Tickets</Link>
      </div>
    );
  }

  const { ticket, conversation } = data;

  return (
    <div className="animate-fade-in" style={{ display: 'flex', gap: '32px', alignItems: 'flex-start' }}>
      
      {/* Left Column: Conversation */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Link href="/tickets" style={{ color: 'var(--text-muted)', fontSize: '14px', display: 'flex', alignItems: 'center' }}>
            ← Back
          </Link>
          <h2 style={{ fontSize: '20px', fontWeight: 700 }}>Ticket: {ticket.subject || 'Untitled'}</h2>
          <span className={`status-badge ${ticket.status.toLowerCase()}`}>{ticket.status.replace('_', ' ')}</span>
        </div>

        <div className="data-card" style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '600px', overflowY: 'auto' }}>
          {conversation.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', textAlign: 'center' }}>No messages in this thread.</p>
          ) : conversation.map((msg: any) => {
            const isUser = msg.role === 'user';
            const isAgent = msg.role === 'agent' || msg.role === 'assistant';
            
            return (
              <div key={msg.id} style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: isUser ? 'flex-end' : 'flex-start',
                width: '100%'
              }}>
                <div style={{
                  maxWidth: '80%',
                  padding: '12px 16px',
                  borderRadius: '12px',
                  background: isUser ? 'var(--primary-light)' : 'var(--bg-page)',
                  border: isUser ? '1px solid rgba(79, 70, 229, 0.2)' : '1px solid var(--border)',
                  color: isUser ? 'var(--primary)' : 'var(--text-main)',
                  fontSize: '14px',
                  lineHeight: 1.5,
                  whiteSpace: 'pre-wrap'
                }}>
                  {msg.content}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', gap: '8px' }}>
                  <span>{new Date(msg.created_at).toLocaleString()}</span>
                  <span>·</span>
                  <span style={{ textTransform: 'uppercase', fontWeight: 600 }}>{msg.channel}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right Column: Metadata */}
      <div style={{ width: '320px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div className="data-card">
          <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>Details</h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>ID</span>
              <span style={{ fontFamily: 'monospace' }}>{ticket.id.substring(0,8)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Created</span>
              <span>{new Date(ticket.created_at).toLocaleDateString()}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Priority</span>
              <span style={{ textTransform: 'capitalize', fontWeight: 500 }}>{ticket.priority}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Escalation Reason</span>
              <span>{ticket.escalation_reason || 'N/A'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
