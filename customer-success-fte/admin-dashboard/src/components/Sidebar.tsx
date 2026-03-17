'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Ticket, Users, Settings } from 'lucide-react';

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside style={{ width: 'var(--sidebar-w)', background: 'var(--bg-panel)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '24px', borderBottom: '1px solid var(--border)' }}>
        <h1 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--primary)' }}>CS Digital FTE</h1>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Admin Console</p>
      </div>
      
      <nav style={{ flex: 1, padding: '16px 12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <Link href="/" className="sidebar-link" data-active={pathname === '/'}>
          <LayoutDashboard size={18} /> Dashboard
        </Link>
        <Link href="/tickets" className="sidebar-link" data-active={pathname === '/tickets' || pathname.startsWith('/tickets/')}>
          <Ticket size={18} /> Tickets
        </Link>
        <Link href="/customers" className="sidebar-link" data-active={pathname === '/customers' || pathname.startsWith('/customers/')}>
          <Users size={18} /> Customers
        </Link>
      </nav>

      <div style={{ padding: '16px 12px', borderTop: '1px solid var(--border)' }}>
          <Link href="/settings" className="sidebar-link" data-active={pathname === '/settings'}>
            <Settings size={18} /> Settings
          </Link>
      </div>
    </aside>
  );
}
