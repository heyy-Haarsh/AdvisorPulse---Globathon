import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { ConfidencePill, EvidenceBadge } from './EvidenceBadge';
import type { WorkspaceTabId } from '../clientWorkspace/format';

type Msg = {
  role: 'user' | 'assistant';
  text: string;
  result?: any;
};

function promptsFor(tab: WorkspaceTabId, name: string): string[] {
  const who = name || 'this client';
  switch (tab) {
    case 'evidence':
      return [
        `What evidence supports the goal conclusion for ${who}?`,
        'What information is missing?',
        'Explain the goal deviation calculation.',
      ];
    case 'portfolio':
      return [
        'Which drift alerts need attention first?',
        'How does the current allocation compare with policy?',
        'Explain the active return calculation.',
      ];
    case 'meetings':
      return [
        'Summarize the latest meeting notes.',
        'Which advice items remain unresolved?',
        'What commitments are overdue?',
      ];
    case 'review-actions':
      return [
        `Why is this review action recommended for ${who}?`,
        'What alternatives are available?',
        'Prepare a review agenda.',
      ];
    default:
      return [
        `Why is ${who} prioritized now?`,
        'What should I review first?',
        'What are the unresolved issues?',
      ];
  }
}

type Props = {
  investorId: string;
  displayName: string;
  tab: WorkspaceTabId;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function CopilotChatPanel({ investorId, displayName, tab, open, onOpenChange }: Props) {
  const [minimized, setMinimized] = useState(false);
  const [query, setQuery] = useState('');
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationContext, setConversationContext] = useState<Record<string, unknown>>({
    investor_id: investorId,
  });

  // Reset conversation when client changes
  useEffect(() => {
    setMsgs([]);
    setErr('');
    setQuery('');
    setConversationContext({ investor_id: investorId });
  }, [investorId]);

  const suggestions = useMemo(
    () => promptsFor(tab, displayName),
    [tab, displayName],
  );

  const ask = async (q?: string) => {
    const text = (q ?? query).trim();
    if (!text) return;
    setLoading(true);
    setErr('');
    setMsgs((m) => [...m, { role: 'user', text }]);
    setQuery('');
    try {
      const r = await api.copilot(text, investorId, conversationContext);
      if (r.conversation_context) setConversationContext(r.conversation_context);
      const summary = r.denied
        ? r.message || 'Request denied'
        : r.answer?.summary ||
          r.result?.priority_reason ||
          r.message ||
          'See evidence-backed result below.';
      setMsgs((m) => [...m, { role: 'assistant', text: summary, result: r }]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const lastAssistant = [...msgs].reverse().find((m) => m.role === 'assistant');

  if (!open) return null;

  return (
    <div
      className={`copilot-float ${minimized ? 'minimized' : ''}`}
      role="dialog"
      aria-label="Advisor Copilot"
    >
      <div className="copilot-float-head">
        <div>
          <strong>Ask Copilot</strong>
          <div className="muted" style={{ fontSize: '0.78rem' }}>
            Context: {displayName} · {investorId}
          </div>
        </div>
        <div className="filters">
          <button
            type="button"
            className="btn ghost"
            aria-label="New conversation"
            onClick={() => {
              setMsgs([]);
              setErr('');
              setConversationContext({ investor_id: investorId });
            }}
          >
            New
          </button>
          <button
            type="button"
            className="btn ghost"
            aria-label={minimized ? 'Expand' : 'Minimize'}
            onClick={() => setMinimized((v) => !v)}
          >
            {minimized ? '▴' : '–'}
          </button>
          <button
            type="button"
            className="btn ghost"
            aria-label="Close Copilot"
            onClick={() => onOpenChange(false)}
          >
            ✕
          </button>
        </div>
      </div>

      {!minimized && (
        <>
          <div className="copilot-suggestions">
            {suggestions.map((s) => (
              <button key={s} type="button" className="chip" onClick={() => ask(s)}>
                {s}
              </button>
            ))}
          </div>
          <div className="copilot-messages">
            {!msgs.length && (
              <p className="muted">
                Validated analysis only — no invented metrics. Agents power answers behind the scenes.
              </p>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`copilot-msg ${m.role}`}>
                <div className="copilot-msg-body">{m.text}</div>
                {m.result && !m.result.denied && (
                  <div className="copilot-answer-card">
                    {m.result.answer?.title && <h4>{m.result.answer.title}</h4>}
                    {(m.result.answer?.bullets || []).length > 0 && (
                      <ul>
                        {m.result.answer.bullets.slice(0, 6).map((b: string, bi: number) => (
                          <li key={bi}>{b}</li>
                        ))}
                      </ul>
                    )}
                    {(m.result.answer?.claims || []).length > 0 && (
                      <div className="copilot-claims">
                        {(m.result.answer.claims as any[]).slice(0, 4).map((c, ci) => (
                          <div key={ci} className="copilot-claim">
                            <ConfidencePill confidence={c.status} />
                            <span>{c.text}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <EvidenceBadge evidence={m.result.evidence} />
                    {m.result.citations?.length ? (
                      <p className="muted" style={{ fontSize: '0.78rem' }}>
                        Cites: {m.result.citations.slice(0, 5).join(', ')}
                      </p>
                    ) : null}
                    <div className="filters">
                      {(m.result.links || []).map((l: any) => (
                        <Link key={l.href} className="linkish" to={l.href}>
                          {l.label}
                        </Link>
                      ))}
                      <Link className="linkish" to={`/clients/${investorId}/evidence`}>
                        Evidence →
                      </Link>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {loading && <p className="muted">Running validated analysis…</p>}
            {err && (
              <div className="error">
                {err}{' '}
                <button
                  type="button"
                  className="btn ghost"
                  onClick={() => ask(msgs.filter((x) => x.role === 'user').slice(-1)[0]?.text)}
                >
                  Retry
                </button>
              </div>
            )}
            {!!lastAssistant?.result?.follow_ups?.length && !loading && (
              <div className="copilot-suggestions">
                {(lastAssistant!.result.follow_ups as string[]).slice(0, 4).map((f) => (
                  <button key={f} type="button" className="chip" onClick={() => ask(f)}>
                    {f}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="copilot-composer">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about this client…"
              onKeyDown={(e) => e.key === 'Enter' && ask()}
              aria-label="Copilot question"
            />
            <button type="button" className="btn" disabled={loading || !query.trim()} onClick={() => ask()}>
              Send
            </button>
          </div>
        </>
      )}
    </div>
  );
}
