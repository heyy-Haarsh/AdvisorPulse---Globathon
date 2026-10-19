import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { EvidenceBadge } from './EvidenceBadge';
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
    case 'simulator':
      return [
        'Explain the difference between baseline and scenario SIP projections.',
        'Which assumptions have the largest effect?',
        'What happens to allocation if mid-cap weight changes?',
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

  // Reset conversation when client changes
  useEffect(() => {
    setMsgs([]);
    setErr('');
    setQuery('');
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
      const r = await api.copilot(text, investorId);
      const summary =
        r.denied
          ? r.message || 'Request denied'
          : [
              r.result?.priority_reason || r.result?.summary || r.message || 'See structured result.',
              r.intent ? `Intent: ${r.intent} → ${r.mapped_function}` : '',
            ]
              .filter(Boolean)
              .join('\n');
      setMsgs((m) => [...m, { role: 'assistant', text: summary, result: r }]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

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
                  <>
                    <EvidenceBadge evidence={m.result.evidence} />
                    {m.result.citations?.length ? (
                      <p className="muted" style={{ fontSize: '0.78rem' }}>
                        Cites: {m.result.citations.slice(0, 5).join(', ')}
                      </p>
                    ) : null}
                    <div className="filters">
                      <Link className="linkish" to={`/clients/${investorId}/evidence`}>
                        Evidence →
                      </Link>
                      <Link className="linkish" to={`/clients/${investorId}/portfolio`}>
                        Portfolio →
                      </Link>
                      <Link className="linkish" to={`/clients/${investorId}/review-actions`}>
                        Review action →
                      </Link>
                    </div>
                    <details>
                      <summary className="muted">Raw structured result</summary>
                      <pre className="json-block">
                        {JSON.stringify(m.result.result ?? m.result.message, null, 2)}
                      </pre>
                    </details>
                  </>
                )}
              </div>
            ))}
            {loading && <p className="muted">Analyzing…</p>}
            {err && (
              <div className="error">
                {err}{' '}
                <button type="button" className="btn ghost" onClick={() => ask(msgs.at(-1)?.text)}>
                  Retry
                </button>
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
