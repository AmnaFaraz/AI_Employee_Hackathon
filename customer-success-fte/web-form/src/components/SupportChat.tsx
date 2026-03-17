'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

// ─── Types ───────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  timestamp: Date;
  ticketNumber?: number;
  wasEscalated?: boolean;
}

interface ChatState {
  messages: Message[];
  isConnected: boolean;
  isTyping: boolean;
  sessionId: string;
  error: string | null;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function generateId(): string {
  return Math.random().toString(36).slice(2, 11);
}

function generateSessionId(): string {
  return `web-${Date.now()}-${generateId()}`;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_URL  = process.env.NEXT_PUBLIC_WS_URL  || 'ws://localhost:8000';

// ─── SupportChat Component ────────────────────────────────────────────────────

export default function SupportChat() {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isConnected: false,
    isTyping: false,
    sessionId: generateSessionId(),
    error: null,
  });
  const [input, setInput] = useState('');
  const [useWebSocket, setUseWebSocket] = useState(true);

  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Auto-scroll ──
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages, state.isTyping]);

  // ── WebSocket setup ──
  const connectWs = useCallback(() => {
    const ws = new WebSocket(`${WS_URL}/api/v1/channels/webform/chat?session_id=${state.sessionId}`);

    ws.onopen = () => {
      setState(s => ({ ...s, isConnected: true, error: null }));
    };

    ws.onmessage = (evt) => {
      const data = JSON.parse(evt.data);

      if (data.type === 'connected') {
        addMessage({ role: 'agent', content: data.message });
      } else if (data.type === 'ack') {
        setState(s => ({ ...s, isTyping: true }));
      } else if (data.type === 'agent_response') {
        setState(s => ({ ...s, isTyping: false }));
        addMessage({
          role: 'agent',
          content: data.content,
          ticketNumber: data.ticket_number,
          wasEscalated: data.was_escalated,
        });
      }
    };

    ws.onerror = () => {
      setState(s => ({ ...s, isConnected: false, error: 'Connection error. Using form mode.' }));
      setUseWebSocket(false);
    };

    ws.onclose = () => {
      setState(s => ({ ...s, isConnected: false }));
    };

    wsRef.current = ws;
  }, [state.sessionId]);

  useEffect(() => {
    if (useWebSocket) connectWs();
    return () => wsRef.current?.close();
  }, [useWebSocket, connectWs]);

  // ── Add message helper ──
  const addMessage = (msg: Omit<Message, 'id' | 'timestamp'>) => {
    setState(s => ({
      ...s,
      messages: [
        ...s.messages,
        { ...msg, id: generateId(), timestamp: new Date() },
      ],
    }));
  };

  // ── Send via WebSocket ──
  const sendViaWs = (content: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ content, session_id: state.sessionId }));
      addMessage({ role: 'user', content });
      return true;
    }
    return false;
  };

  // ── Send via HTTP (fallback) ──
  const sendViaHttp = async (content: string) => {
    addMessage({ role: 'user', content });
    setState(s => ({ ...s, isTyping: true }));

    try {
      const res = await fetch(`${API_URL}/api/v1/channels/webform/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'Web User',
          email: `${state.sessionId}@webform.local`,
          subject: 'Support Request',
          message: content,
          session_id: state.sessionId,
        }),
      });
      const data = await res.json();
      setState(s => ({ ...s, isTyping: false }));
      addMessage({
        role: 'agent',
        content: data.message || 'Your message has been received. Our AI is preparing a response.',
        ticketNumber: data.ticket_number,
      });
    } catch {
      setState(s => ({ ...s, isTyping: false }));
      addMessage({ role: 'system', content: '⚠️ Could not reach support. Please try again.' });
    }
  };

  // ── Handle send ──
  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;
    setInput('');
    inputRef.current?.focus();

    if (useWebSocket && sendViaWs(text)) return;
    await sendViaHttp(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.avatar}>
            <span style={{ fontSize: 20 }}>✦</span>
          </div>
          <div>
            <div style={styles.agentName}>Aria</div>
            <div style={styles.agentStatus}>
              <span style={{
                ...styles.statusDot,
                background: state.isConnected ? '#10b981' : '#f59e0b',
              }} />
              {state.isConnected ? 'AI Online · Instant responses' : 'Connecting…'}
            </div>
          </div>
        </div>
        <div style={styles.headerBadge}>24/7 Support</div>
      </div>

      {/* Messages */}
      <div style={styles.messages}>
        {state.messages.length === 0 && (
          <div style={styles.emptyState}>
            <div style={styles.emptyIcon}>💬</div>
            <div style={styles.emptyTitle}>How can I help you today?</div>
            <div style={styles.emptySubtitle}>Ask me anything about our product</div>
            <div style={styles.quickButtons}>
              {['Billing question', 'Reset password', 'Feature request', 'Report a bug'].map(q => (
                <button key={q} style={styles.quickBtn} onClick={() => {
                  setInput(q);
                  inputRef.current?.focus();
                }}>{q}</button>
              ))}
            </div>
          </div>
        )}

        {state.messages.map(msg => (
          <div key={msg.id} style={{
            ...styles.messageRow,
            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            animation: 'fadeIn 0.2s ease',
          }}>
            {msg.role !== 'user' && (
              <div style={styles.msgAvatar}>✦</div>
            )}
            <div>
              <div style={{
                ...styles.bubble,
                ...(msg.role === 'user' ? styles.bubbleUser : msg.role === 'system' ? styles.bubbleSystem : styles.bubbleAgent),
              }}>
                {msg.content}
              </div>
              <div style={styles.msgMeta}>
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                {msg.ticketNumber && <span style={styles.ticketBadge}>Ticket #{msg.ticketNumber}</span>}
                {msg.wasEscalated && <span style={styles.escalateBadge}>👤 Human escalated</span>}
              </div>
            </div>
          </div>
        ))}

        {state.isTyping && (
          <div style={{ ...styles.messageRow, justifyContent: 'flex-start' }}>
            <div style={styles.msgAvatar}>✦</div>
            <div style={{ ...styles.bubble, ...styles.bubbleAgent, ...styles.typing }}>
              <span style={styles.dot} />
              <span style={{ ...styles.dot, animationDelay: '0.15s' }} />
              <span style={{ ...styles.dot, animationDelay: '0.3s' }} />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Error */}
      {state.error && (
        <div style={styles.errorBanner}>{state.error}</div>
      )}

      {/* Input */}
      <div style={styles.inputArea}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your message… (Enter to send)"
          style={styles.textarea}
          rows={1}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim()}
          style={{
            ...styles.sendBtn,
            opacity: input.trim() ? 1 : 0.4,
          }}
          aria-label="Send message"
        >
          ➤
        </button>
      </div>

      <div style={styles.footer}>
        Powered by <strong>Aria</strong> · Customer Success AI · Responses in &lt;30s
      </div>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  container: {
    width: '100%',
    maxWidth: 480,
    height: '85vh',
    maxHeight: 720,
    background: 'linear-gradient(145deg, #1a1a2e 0%, #16213e 100%)',
    borderRadius: 20,
    border: '1px solid rgba(99,102,241,0.25)',
    boxShadow: '0 25px 60px rgba(0,0,0,0.5), 0 0 40px rgba(99,102,241,0.1)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 20px',
    background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(6,182,212,0.1))',
    borderBottom: '1px solid rgba(99,102,241,0.2)',
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: 12 },
  avatar: {
    width: 42, height: 42, borderRadius: '50%',
    background: 'linear-gradient(135deg, #6366f1, #06b6d4)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    boxShadow: '0 0 20px rgba(99,102,241,0.4)',
  },
  agentName: { fontWeight: 700, fontSize: 15, color: '#f1f5f9' },
  agentStatus: { display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#94a3b8', marginTop: 2 },
  statusDot: { width: 7, height: 7, borderRadius: '50%', flexShrink: 0 },
  headerBadge: {
    fontSize: 10, fontWeight: 600, padding: '4px 10px',
    background: 'rgba(16,185,129,0.15)', color: '#10b981',
    border: '1px solid rgba(16,185,129,0.3)', borderRadius: 20,
    textTransform: 'uppercase', letterSpacing: '0.5px',
  },
  messages: {
    flex: 1, overflowY: 'auto', padding: '20px 16px',
    display: 'flex', flexDirection: 'column', gap: 12,
  },
  emptyState: {
    flex: 1, display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
    padding: '40px 20px', textAlign: 'center',
    gap: 8,
  },
  emptyIcon: { fontSize: 40, marginBottom: 8 },
  emptyTitle: { fontSize: 18, fontWeight: 700, color: '#f1f5f9' },
  emptySubtitle: { fontSize: 13, color: '#94a3b8', marginBottom: 16 },
  quickButtons: { display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginTop: 8 },
  quickBtn: {
    background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.25)',
    borderRadius: 20, padding: '6px 14px', color: '#a5b4fc', fontSize: 12,
    cursor: 'pointer', transition: 'all 0.2s',
  },
  messageRow: { display: 'flex', gap: 10, alignItems: 'flex-end' },
  msgAvatar: {
    width: 30, height: 30, borderRadius: '50%',
    background: 'linear-gradient(135deg, #6366f1, #06b6d4)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 12, flexShrink: 0,
  },
  bubble: {
    maxWidth: 320, padding: '10px 14px', borderRadius: 16,
    fontSize: 14, lineHeight: 1.5, whiteSpace: 'pre-wrap',
  },
  bubbleUser: {
    background: 'linear-gradient(135deg, #6366f1, #4f46e5)',
    color: '#fff', borderBottomRightRadius: 4,
    boxShadow: '0 4px 12px rgba(99,102,241,0.3)',
  },
  bubbleAgent: {
    background: 'rgba(255,255,255,0.06)', color: '#e2e8f0',
    border: '1px solid rgba(255,255,255,0.08)', borderBottomLeftRadius: 4,
  },
  bubbleSystem: {
    background: 'rgba(245,158,11,0.1)', color: '#fbbf24',
    border: '1px solid rgba(245,158,11,0.2)', borderRadius: 10,
    fontSize: 12,
  },
  msgMeta: { fontSize: 10, color: '#475569', marginTop: 4, display: 'flex', gap: 8, alignItems: 'center' },
  ticketBadge: {
    background: 'rgba(99,102,241,0.15)', color: '#a5b4fc',
    padding: '2px 8px', borderRadius: 10, fontSize: 10,
  },
  escalateBadge: {
    background: 'rgba(245,158,11,0.1)', color: '#fbbf24',
    padding: '2px 8px', borderRadius: 10, fontSize: 10,
  },
  typing: { display: 'flex', gap: 5, alignItems: 'center', padding: '12px 16px' },
  dot: {
    width: 7, height: 7, borderRadius: '50%',
    background: '#6366f1', display: 'inline-block',
    animation: 'pulse 1.2s infinite',
  },
  errorBanner: {
    background: 'rgba(239,68,68,0.1)', color: '#fca5a5',
    fontSize: 12, textAlign: 'center', padding: '8px 16px',
    borderTop: '1px solid rgba(239,68,68,0.2)',
  },
  inputArea: {
    display: 'flex', alignItems: 'flex-end', gap: 10,
    padding: '12px 16px',
    borderTop: '1px solid rgba(255,255,255,0.06)',
    background: 'rgba(255,255,255,0.02)',
  },
  textarea: {
    flex: 1, background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(99,102,241,0.2)', borderRadius: 14,
    color: '#f1f5f9', padding: '10px 14px', fontSize: 14,
    resize: 'none', outline: 'none', lineHeight: 1.5,
    fontFamily: 'inherit',
    transition: 'border-color 0.2s',
  },
  sendBtn: {
    width: 44, height: 44, borderRadius: 14, flexShrink: 0,
    background: 'linear-gradient(135deg, #6366f1, #06b6d4)',
    border: 'none', color: '#fff', fontSize: 18,
    cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
    boxShadow: '0 4px 12px rgba(99,102,241,0.3)',
    transition: 'transform 0.1s, opacity 0.2s',
  },
  footer: {
    textAlign: 'center', fontSize: 11, color: '#475569',
    padding: '8px 16px', borderTop: '1px solid rgba(255,255,255,0.04)',
  },
};
