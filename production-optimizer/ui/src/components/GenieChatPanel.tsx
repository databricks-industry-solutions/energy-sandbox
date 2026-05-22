import { useState, useRef, useEffect } from 'react';

/* ================================================================
   Genie Chat Panel — Chat-style scripted conversation
   Keyword chips + text input drive the same walkthrough flow.
   ================================================================ */

/** Sanitize HTML — allow only safe tags, strip scripts and event handlers. */
function sanitizeHtml(html: string): string {
  const ALLOWED_TAGS = /^(b|i|em|strong|br|p|ul|ol|li|span|div|sub|sup|a|code|pre|table|tr|td|th|thead|tbody|h[1-6])$/i;
  const tmp = document.createElement('div');
  tmp.innerHTML = html;
  // Remove script tags and event handlers
  const walk = (node: Element) => {
    for (let i = node.children.length - 1; i >= 0; i--) {
      const child = node.children[i];
      if (!ALLOWED_TAGS.test(child.tagName)) {
        child.remove();
        continue;
      }
      // Strip event handler attributes
      for (let j = child.attributes.length - 1; j >= 0; j--) {
        const attr = child.attributes[j].name.toLowerCase();
        if (attr.startsWith('on') || attr === 'href' && child.getAttribute('href')?.startsWith('javascript:')) {
          child.removeAttribute(child.attributes[j].name);
        }
      }
      walk(child);
    }
  };
  walk(tmp);
  return tmp.innerHTML;
}

interface ChatMessage {
  role: 'user' | 'genie' | 'agent' | 'system';
  content: string;
}

/* Each step: the messages to show, plus suggestions for what the user
   can type/click AFTER this step renders (to trigger the next step). */
interface Step {
  messages: ChatMessage[];
  /** Suggestion chips shown after this step. Empty = auto-advance or end. */
  suggestions?: string[];
}

const STEPS: Step[] = [
  /* 0 — Genie opens with status */
  {
    messages: [
      {
        role: 'genie',
        content:
          'Good morning. Here\'s your <strong>Delaware Basin CO₂-EOR</strong> field status.'
          + '<br><br><strong>Production:</strong> 3,190 bbl/d oil · 8,490 Mcf/d gas · 96% uptime'
          + '<br><strong>CO₂ injection:</strong> 9,950 Mcf/d across 4 patterns · recycle at 62%'
          + '<br><strong>Alerts:</strong> 1 critical — Pattern D reservoir pressure at 3,380 psi, approaching the 3,500 fracture threshold. 2 warnings on compressor utilization and injection trunk pressure.'
          + '<br><br>Patterns B and D are tracking plan. Pattern C is deep into cycle 8 with high water cuts across all producers. <strong>Pattern A is the concern</strong> — two producers are declining faster than forecast. Want me to dig in?',
      },
    ],
    suggestions: ['Break down Pattern A', 'Pattern A wells', 'Yes, dig in'],
  },
  /* 1 — User asks → Genie responds with well data */
  {
    messages: [
      {
        role: 'user',
        content: 'Yes, break down Pattern A. Which wells are the problem?',
      },
      {
        role: 'genie',
        content:
          'Pattern A is on CO₂ injection cycle 5, reservoir pressure sitting at 2,950 against a 3,200 target. Injector W-A05 is pushing 2,200 Mcf/d.'
          + '<br><br>Two producers are lagging:'
          + '<br>• <strong>W-A03</strong> — 145 bbl/d, <strong>83% water cut</strong>. Worst in the pattern. CO₂ concentration at 42 mol%.'
          + '<br>• <strong>W-A01</strong> — 185 bbl/d, <strong>77% water cut</strong>. Both in Wolfcamp A, perforated at 7,200–7,650 ft.'
          + '<br><br>A02 and A04 aren\'t great either (72% and 80% water cut) but A03 is the clear candidate for intervention. Slug efficiency has been declining since cycle 3.',
      },
    ],
    suggestions: ['Shut-in economics for A03', 'NPV on redirecting CO₂', 'Cost to fix A03'],
  },
  /* 2 — User asks economics → Genie introduces agent */
  {
    messages: [
      {
        role: 'user',
        content: 'What if we shut in A03 and redirect that CO₂ to A01? What\'s the cost and does the NPV work?',
      },
      {
        role: 'genie',
        content:
          'I can pull the production trends, but the workover costs and NPV models are in the operations database — that\'s what Finance and Planning maintain.'
          + '<br><br>The economics agent has access to all of that. It can run the shut-in scenario, pull the rig schedule, and give you a number. Want me to hand it off?',
      },
    ],
    suggestions: ['Data trust concern', 'Will the numbers match?', 'Hand it off'],
  },
  /* 3 — User raises trust concern → Genie explains */
  {
    messages: [
      {
        role: 'user',
        content: 'Yeah — but last time we had three different cost models floating around in spreadsheets and it took a week to reconcile. Are we going to have that problem again?',
      },
      {
        role: 'genie',
        content:
          'No. The agent reads directly from the same database that Production, Finance, and Reservoir Engineering all write to. There\'s one set of numbers — whoever updated cost assumptions last, that\'s what the model uses.'
          + '<br><br>Right now there are 23 active sessions on that database. Field engineers updating rates, finance revising assumptions, and a couple of optimization runs in the background. Everyone\'s working off the same data.',
      },
    ],
    suggestions: ['Run the scenario', 'Go ahead, connect me', 'Shut in A03'],
  },
  /* 4 — User accepts → Handoff + Agent responds */
  {
    messages: [
      {
        role: 'user',
        content: 'Good. Run the shut-in scenario for A03 — redirect the 2,200 Mcf/d to A01, give me the 90-day NPV with workover cost.',
      },
      { role: 'system', content: 'handoff' },
      {
        role: 'agent',
        content:
          'Done. Shutting in <strong>W-A03</strong> (145 bbl/d, 83% water cut) and redirecting 2,200 Mcf/d to <strong>W-A01</strong>:'
          + '<br><br><strong>A01 incremental recovery:</strong> +38 bbl/d (185 → 223 bbl/d) over 90 days'
          + '<br><strong>A03 workover:</strong> $340K — rod pump replacement + re-perf at 7,200–7,650 ft'
          + '<br><strong>CO₂ credits:</strong> Net neutral. Stored volume maintained via A01. 45Q preserved.'
          + '<br><strong>Compressor:</strong> Station at 88% — redirecting within Pattern A keeps it flat.'
          + '<br><strong>90-day NPV:</strong> <span style="color:#10b981;font-weight:800;">+$1.2M</span> vs. current trajectory'
          + '<br><br><strong style="color:#10b981;">Recommendation: GO.</strong> Shut in A03, redirect CO₂ to A01, schedule workover for next rig window. Breakeven at day 42.',
      },
      {
        role: 'agent',
        content:
          '<div style="font-size:12px;font-weight:700;color:#8b5cf6;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;">Data Sources Queried</div>'
          + '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;">'
          + '<div style="background:rgba(139,92,246,0.08);border-radius:8px;padding:10px;"><strong style="font-size:12px;">Production History</strong><div style="font-size:11px;color:#8b949e;">W-A01/A03 SCADA + decline curves</div></div>'
          + '<div style="background:rgba(139,92,246,0.08);border-radius:8px;padding:10px;"><strong style="font-size:12px;">Workover Costs</strong><div style="font-size:11px;color:#8b949e;">Rig schedule + Wolfcamp A pricing</div></div>'
          + '<div style="background:rgba(139,92,246,0.08);border-radius:8px;padding:10px;"><strong style="font-size:12px;">NPV Model</strong><div style="font-size:11px;color:#8b949e;">90-day cash flow sensitivity</div></div>'
          + '<div style="background:rgba(139,92,246,0.08);border-radius:8px;padding:10px;"><strong style="font-size:12px;">CO₂ Credit Schedule</strong><div style="font-size:11px;color:#8b949e;">45Q qualification + stored volume</div></div>'
          + '</div>',
      },
    ],
    suggestions: ['Add to daily review', 'Schedule this daily', 'Morning routine'],
  },
  /* 5 — User wants daily → Agent confirms → User asks about all agents */
  {
    messages: [
      {
        role: 'user',
        content: 'This is exactly what I need every morning. Can we add the economics agent to the daily operations review? I want it to flag any pattern where a shut-in or redirect would improve NPV by more than $500K.',
      },
      {
        role: 'agent',
        content:
          'Done. I\'ll run a full-field optimization scan every day at 05:00 before your morning review. Any pattern where a shut-in, redirect, or workover scenario improves 90-day NPV by more than $500K will show up as a recommendation in your status briefing.'
          + '<br><br>I\'ll also flag compressor headroom and CO₂ credit impacts so you don\'t get surprises downstream.',
      },
    ],
    suggestions: ['Show all agents', 'What else is available?', 'Full agent list'],
  },
  /* 6 — User asks about agents → Genie shows ecosystem */
  {
    messages: [
      {
        role: 'user',
        content: 'Good. Genie — what other agents do I have access to? Show me the full picture.',
      },
      {
        role: 'genie',
        content:
          'You have access to <strong>5 agents</strong> across your operations. Here\'s how they connect:'
          + '<br><br>'
          + '<div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;font-family:monospace;font-size:11px;line-height:2.2;">'
          + '<div style="color:#8b949e;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">Agent Ecosystem</div>'
          + '<div>'
          + '<span style="color:#06b6d4;">📡 SCADA Data</span>'
          + ' <span style="color:#30363d;">───▶</span> '
          + '<span style="background:#00d4aa22;border:1px solid #00d4aa44;border-radius:6px;padding:3px 8px;color:#00d4aa;">🔮 Genie</span>'
          + ' <span style="color:#30363d;">───▶</span> '
          + '<span style="color:#e6edf3;">You</span>'
          + '</div>'
          + '<div style="margin-left:144px;color:#30363d;">│</div>'
          + '<div style="margin-left:120px;color:#30363d;">┌──┴──┐</div>'
          + '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:4px;">'
          + '<span style="background:#f9731622;border:1px solid #f9731644;border-radius:6px;padding:3px 8px;color:#f97316;">🤖 Economics</span>'
          + '<span style="background:#3b82f622;border:1px solid #3b82f644;border-radius:6px;padding:3px 8px;color:#3b82f6;">🤖 Reservoir</span>'
          + '<span style="background:#a855f722;border:1px solid #a855f744;border-radius:6px;padding:3px 8px;color:#a855f7;">🤖 Compliance</span>'
          + '<span style="background:#10b98122;border:1px solid #10b98144;border-radius:6px;padding:3px 8px;color:#10b981;">🤖 Logistics</span>'
          + '</div>'
          + '<div style="margin-top:10px;color:#30363d;">──────────────────────────────</div>'
          + '<div style="display:flex;gap:6px;margin-top:6px;">'
          + '<span style="background:#06b6d422;border:1px solid #06b6d444;border-radius:6px;padding:3px 8px;color:#06b6d4;">📊 Operations DB</span>'
          + '<span style="background:#f59e0b22;border:1px solid #f59e0b44;border-radius:6px;padding:3px 8px;color:#f59e0b;">📋 Rig Schedule</span>'
          + '<span style="background:#ef444422;border:1px solid #ef444444;border-radius:6px;padding:3px 8px;color:#ef4444;">📈 Market Prices</span>'
          + '</div>'
          + '</div>'
          + '<br><strong>Economics Agent</strong> — workover costs, NPV scenarios, CO₂ credits <span style="color:#10b981;">● active (daily 05:00)</span>'
          + '<br><strong>Reservoir Agent</strong> — pressure forecasts, breakthrough prediction, sweep models'
          + '<br><strong>Compliance Agent</strong> — 45Q reporting, emissions tracking, regulatory filings'
          + '<br><strong>Logistics Agent</strong> — rig scheduling, crew availability, parts procurement'
          + '<br><br>All four read from the same operations database. Genie orchestrates — you ask a question, it routes to the right agent or handles it directly from SCADA.',
      },
    ],
    suggestions: [],
  },
];

export default function GenieChatPanel() {
  const [step, setStep] = useState(0);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const visibleMessages: (ChatMessage & { stepIdx: number })[] = [];
  for (let s = 0; s <= step; s++) {
    for (const msg of STEPS[s].messages) {
      visibleMessages.push({ ...msg, stepIdx: s });
    }
  }

  const currentStep = STEPS[step];
  const canAdvance = step < STEPS.length - 1;
  const suggestions = currentStep.suggestions || [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [step]);

  const advance = () => {
    if (canAdvance) {
      setStep((s) => s + 1);
      setInputValue('');
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim()) advance();
  };

  const handleChipClick = (text: string) => {
    setInputValue(text);
    // Small delay so user sees the chip text appear in input before advancing
    setTimeout(advance, 150);
  };

  return (
    <div className="chat-panel">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-icon">🔮</div>
        <div>
          <div className="chat-header-title">Production Advisor</div>
          <div className="chat-header-sub">Genie Space · Live SCADA data</div>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {visibleMessages.map((msg, i) => {
          if (msg.role === 'system' && msg.content === 'handoff') {
            return (
              <div
                key={i}
                className={`chat-handoff ${msg.stepIdx === step ? 'chat-animate' : ''}`}
              >
                <span>🔮</span>
                <span className="chat-handoff-arrow">→</span>
                <span>🤖</span>
                <span className="chat-handoff-label">Handing off to Economics Agent</span>
              </div>
            );
          }

          const roleClass =
            msg.role === 'user'
              ? 'chat-msg-user'
              : msg.role === 'genie'
                ? 'chat-msg-genie'
                : 'chat-msg-agent';

          const label =
            msg.role === 'user'
              ? 'You'
              : msg.role === 'genie'
                ? '🔮 Genie'
                : '🤖 Economics Agent';

          const labelColor =
            msg.role === 'user'
              ? '#8b949e'
              : msg.role === 'genie'
                ? '#00d4aa'
                : '#f97316';

          return (
            <div
              key={i}
              className={`chat-msg ${roleClass} ${msg.stepIdx === step ? 'chat-animate' : ''}`}
            >
              <div className="chat-msg-label" style={{ color: labelColor }}>
                {label}
              </div>
              <div dangerouslySetInnerHTML={{ __html: sanitizeHtml(msg.content) }} />
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="chat-input-area">
        {/* Suggestion chips */}
        {canAdvance && suggestions.length > 0 && (
          <div className="chat-chips">
            {suggestions.map((s) => (
              <button key={s} className="chat-chip" onClick={() => handleChipClick(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Text input */}
        {canAdvance ? (
          <form className="chat-input-form" onSubmit={handleSubmit}>
            <input
              className="chat-input"
              type="text"
              placeholder="Ask about operations..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
            />
            <button
              className="chat-send-btn"
              type="submit"
              disabled={!inputValue.trim()}
            >
              ↵
            </button>
          </form>
        ) : (
          <button
            className="chat-continue-btn chat-restart-btn"
            onClick={() => { setStep(0); setInputValue(''); }}
          >
            ↺ Restart Demo
          </button>
        )}
      </div>
    </div>
  );
}
