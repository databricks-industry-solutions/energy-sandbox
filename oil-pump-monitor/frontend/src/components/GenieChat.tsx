import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Bot, User, AlertTriangle, XCircle, CheckCircle, Loader, Zap, RefreshCw, ChevronRight } from 'lucide-react';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  critical_pumps?: string[];
  recommendations?: string[];
  isLoading?: boolean;
  timestamp?: Date;
}

interface ScanResult {
  status?: string;
  message?: string;
  response?: string;
  critical_pumps?: string[];
  recommendations?: string[];
  affected_pumps?: string[];
  trigger?: string;
}

const QUICK_PROMPTS = [
  "What's the overall field status right now?",
  "Are there any bearing fault signatures?",
  "Which pump needs the most urgent attention?",
  "Analyze vibration trends over the last 15 minutes",
  "Check for cavitation on all pumps",
  "Give me a maintenance priority list",
];

function RecommendationCard({ items }: { items: string[] }) {
  if (!items?.length) return null;
  return (
    <div style={{
      background: '#0c1a2e', border: '1px solid #1e3a5f',
      borderRadius: 8, padding: '10px 14px', marginTop: 10
    }}>
      <div style={{ fontSize: 11, color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 5 }}>
        <Zap size={10} /> Action Items
      </div>
      {items.map((rec, i) => (
        <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 5, alignItems: 'flex-start' }}>
          <ChevronRight size={11} color='#38bdf8' style={{ marginTop: 2, flexShrink: 0 }} />
          <span style={{ fontSize: 12, color: '#cbd5e1', lineHeight: 1.4 }}>{rec}</span>
        </div>
      ))}
    </div>
  );
}

function CriticalAlert({ pumps }: { pumps: string[] }) {
  if (!pumps?.length) return null;
  return (
    <div style={{
      background: '#1a000088', border: '1px solid #ef4444',
      borderRadius: 8, padding: '8px 14px', marginTop: 8,
      display: 'flex', alignItems: 'center', gap: 8
    }}>
      <XCircle size={13} color='#ef4444' />
      <span style={{ fontSize: 12, color: '#f87171', fontWeight: 600 }}>
        CRITICAL: {pumps.join(', ')}
      </span>
    </div>
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';

  if (isSystem) {
    return (
      <div style={{
        textAlign: 'center', padding: '6px 0',
        fontSize: 11, color: '#475569', fontStyle: 'italic'
      }}>
        {msg.content}
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex', gap: 10, marginBottom: 16,
      flexDirection: isUser ? 'row-reverse' : 'row',
      alignItems: 'flex-start'
    }}>
      {/* Avatar */}
      <div style={{
        width: 30, height: 30, borderRadius: '50%', flexShrink: 0,
        background: isUser ? '#1e3a5f' : '#1a0d2e',
        border: `1px solid ${isUser ? '#38bdf8' : '#7c3aed'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center'
      }}>
        {isUser
          ? <User size={14} color='#38bdf8' />
          : <Bot size={14} color='#a78bfa' />}
      </div>

      {/* Bubble */}
      <div style={{ maxWidth: '80%' }}>
        <div style={{
          background: isUser ? '#0f2a4a' : '#0d0d1f',
          border: `1px solid ${isUser ? '#1e3a5f' : '#1e1b3a'}`,
          borderRadius: isUser ? '12px 4px 12px 12px' : '4px 12px 12px 12px',
          padding: '10px 14px',
        }}>
          {msg.isLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Loader size={13} color='#a78bfa' style={{ animation: 'spin 1s linear infinite' }} />
              <span style={{ fontSize: 13, color: '#64748b', fontStyle: 'italic' }}>
                Analyzing field data...
              </span>
            </div>
          ) : (
            <div style={{ fontSize: 13, color: '#e2e8f0', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
              {msg.content}
            </div>
          )}
        </div>

        {!msg.isLoading && (
          <>
            <CriticalAlert pumps={msg.critical_pumps || []} />
            <RecommendationCard items={msg.recommendations || []} />
          </>
        )}

        {msg.timestamp && !msg.isLoading && (
          <div style={{ fontSize: 10, color: '#334155', marginTop: 4,
            textAlign: isUser ? 'right' : 'left' }}>
            {msg.timestamp.toLocaleTimeString('en-US', { hour12: false })}
          </div>
        )}
      </div>
    </div>
  );
}

export function GenieChat({ onCriticalAlert }: { onCriticalAlert?: (pumps: string[]) => void }) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: "I'm Genie, your Bakken Field Operations AI. I have real-time access to all 6 pump sensors — vibration amplitude, frequency spectra, RPM, temperature, and wellbore pressure.\n\nAsk me anything about field status, fault diagnosis, or maintenance priorities.",
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [lastScan, setLastScan] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto proactive scan every 60 seconds
  useEffect(() => {
    const runScan = async () => {
      try {
        const r = await fetch('/api/agent/scan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        const data: ScanResult = await r.json();
        if (data.status !== 'nominal' && data.response) {
          const ts = new Date();
          setLastScan(ts.toLocaleTimeString('en-US', { hour12: false }));
          setMessages(prev => [
            ...prev,
            {
              role: 'system' as const,
              content: `⚡ Proactive scan at ${ts.toLocaleTimeString('en-US', { hour12: false })}`,
            },
            {
              role: 'assistant' as const,
              content: data.response!,
              critical_pumps: data.critical_pumps || data.affected_pumps || [],
              recommendations: data.recommendations || [],
              timestamp: ts,
            }
          ]);
          if (data.critical_pumps?.length && onCriticalAlert) {
            onCriticalAlert(data.critical_pumps);
          }
        }
      } catch { /* silent */ }
    };

    // Initial scan after 5s startup
    const initTimer = setTimeout(runScan, 5000);
    const interval = setInterval(runScan, 60000);
    return () => { clearTimeout(initTimer); clearInterval(interval); };
  }, [onCriticalAlert]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: Message = { role: 'user', content: text.trim(), timestamp: new Date() };
    const loadingMsg: Message = { role: 'assistant', content: '', isLoading: true };

    setMessages(prev => [...prev, userMsg, loadingMsg]);
    setInput('');
    setLoading(true);

    try {
      // Build conversation history (exclude system/loading msgs)
      const history = [...messages, userMsg]
        .filter(m => m.role !== 'system' && !m.isLoading)
        .map(m => ({ role: m.role, content: m.content }));

      const r = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history }),
      });

      const data = await r.json();

      const assistantMsg: Message = {
        role: 'assistant',
        content: data.response || data.detail || 'No response received.',
        critical_pumps: data.critical_pumps || [],
        recommendations: data.recommendations || [],
        timestamp: new Date(),
      };

      setMessages(prev => [...prev.slice(0, -1), assistantMsg]);

      if (data.critical_pumps?.length && onCriticalAlert) {
        onCriticalAlert(data.critical_pumps);
      }
    } catch (e) {
      setMessages(prev => [
        ...prev.slice(0, -1),
        {
          role: 'assistant',
          content: 'Connection error. Please check that the Foundation Model endpoint is configured.',
          timestamp: new Date(),
        }
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }, [messages, loading, onCriticalAlert]);

  const handleManualScan = async () => {
    setScanning(true);
    try {
      const r = await fetch('/api/agent/scan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      const data: ScanResult = await r.json();
      const ts = new Date();
      setLastScan(ts.toLocaleTimeString('en-US', { hour12: false }));
      if (data.status === 'nominal') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: '✓ Field scan complete — all pumps operating within normal parameters.',
          timestamp: ts,
        }]);
      } else if (data.response) {
        setMessages(prev => [...prev,
          { role: 'system', content: `⚡ Manual scan at ${ts.toLocaleTimeString('en-US', { hour12: false })}` },
          {
            role: 'assistant',
            content: data.response!,
            critical_pumps: data.critical_pumps || data.affected_pumps || [],
            recommendations: data.recommendations || [],
            timestamp: ts,
          }
        ]);
        if (data.critical_pumps?.length && onCriticalAlert) onCriticalAlert(data.critical_pumps);
      }
    } catch { /* silent */ } finally {
      setScanning(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 600 }}>
      {/* Header */}
      <div style={{
        background: '#0a0e1a', borderBottom: '1px solid #1e1b3a',
        padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        borderRadius: '12px 12px 0 0'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 32, height: 32, background: '#1a0d2e', borderRadius: 8,
            border: '1px solid #7c3aed', display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Bot size={16} color='#a78bfa' />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0' }}>Genie Operations AI</div>
            <div style={{ fontSize: 10, color: '#64748b' }}>
              {loading ? (
                <span style={{ color: '#a78bfa' }}>● Analyzing...</span>
              ) : (
                <span style={{ color: '#22c55e' }}>● Connected · Claude claude-sonnet-4-6</span>
              )}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {lastScan && (
            <span style={{ fontSize: 10, color: '#475569' }}>Last scan: {lastScan}</span>
          )}
          <button
            onClick={handleManualScan}
            disabled={scanning}
            style={{
              background: '#0f172a', border: '1px solid #334155', borderRadius: 6,
              padding: '5px 10px', cursor: scanning ? 'not-allowed' : 'pointer',
              fontSize: 11, color: scanning ? '#475569' : '#94a3b8',
              display: 'flex', alignItems: 'center', gap: 5
            }}
          >
            <RefreshCw size={11} style={{ animation: scanning ? 'spin 1s linear infinite' : 'none' }} />
            {scanning ? 'Scanning...' : 'Scan Field'}
          </button>
        </div>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '16px',
        background: '#060b18', minHeight: 400, maxHeight: 520
      }}>
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Quick prompts */}
      <div style={{
        background: '#0a0e1a', borderTop: '1px solid #1e293b',
        padding: '8px 12px', display: 'flex', gap: 6, flexWrap: 'wrap'
      }}>
        {QUICK_PROMPTS.map((p, i) => (
          <button
            key={i}
            onClick={() => sendMessage(p)}
            disabled={loading}
            style={{
              background: '#0f172a', border: '1px solid #1e293b', borderRadius: 20,
              padding: '4px 10px', cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: 11, color: loading ? '#334155' : '#64748b',
              whiteSpace: 'nowrap', transition: 'all 0.15s'
            }}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Input */}
      <div style={{
        background: '#0a0e1a', borderTop: '1px solid #1e293b',
        padding: '12px 16px', display: 'flex', gap: 10, alignItems: 'flex-end',
        borderRadius: '0 0 12px 12px'
      }}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about pump status, fault diagnosis, maintenance..."
          rows={2}
          style={{
            flex: 1, background: '#0f172a', border: '1px solid #1e293b',
            borderRadius: 8, padding: '10px 14px', color: '#e2e8f0',
            fontSize: 13, resize: 'none', outline: 'none',
            fontFamily: 'inherit', lineHeight: 1.5
          }}
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={loading || !input.trim()}
          style={{
            width: 40, height: 40, borderRadius: 8, border: 'none',
            background: loading || !input.trim() ? '#1e293b' : '#4f46e5',
            cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'background 0.15s', flexShrink: 0
          }}
        >
          {loading
            ? <Loader size={16} color='#64748b' style={{ animation: 'spin 1s linear infinite' }} />
            : <Send size={16} color={!input.trim() ? '#475569' : '#fff'} />}
        </button>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
