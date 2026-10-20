import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { ConfidencePill, EvidenceBadge } from './EvidenceBadge';

type Msg = {
  role: 'user' | 'assistant';
  text: string;
  result?: any;
};

type CategoryId = 'attention' | 'portfolio' | 'advice' | 'meeting';

export function CopilotPanel({ investorId }: { investorId?: string }) {
  const [open, setOpen] = useState(false);
  const [catalog, setCatalog] = useState<any>(null);
  const [category, setCategory] = useState<CategoryId | null>(null);
  const [showDemos, setShowDemos] = useState(false);
  const [query, setQuery] = useState('');
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationContext, setConversationContext] = useState<Record<string, unknown>>({});

  useEffect(() => {
    api.copilotDemoCatalog().then(setCatalog).catch(() => undefined);
  }, []);

  useEffect(() => {
    // Reset thread when page-level investor context changes
    setMsgs([]);
    setConversationContext(investorId ? { investor_id: investorId } : {});
    setErr('');
  }, [investorId]);

  const quickPrompts = useMemo(() => {
    if (!catalog || !category) return [];
    return catalog.quick_start?.[category] || [];
  }, [catalog, category]);

  const demoGroups = useMemo(() => {
    const scenarios = catalog?.scenarios || [];
    const groups: Record<string, any[]> = {};
    for (const s of scenarios) {
      const g = s.group || 'Other';
      groups[g] = groups[g] || [];
      groups[g].push(s);
    }
    return groups;
  }, [catalog]);

  const ask = async (q?: string) => {
    const text = (q ?? query).trim();
    if (!text) return;
    setLoading(true);
    setErr('');
    setMsgs((m) => [...m, { role: 'user', text }]);
    setQuery('');
    setCategory(null);
    setShowDemos(false);
    try {
      const r = await api.copilot(text, investorId, conversationContext);
      if (r.conversation_context) setConversationContext(r.conversation_context);
      const answer = r.answer;
      const summary = r.denied
        ? r.message || 'Request denied'
        : answer?.summary ||
          r.message ||
          r.result?.priority_reason ||
          'See evidence and structured result below.';
      setMsgs((m) => [...m, { role: 'assistant', text: summary, result: r }]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const lastAssistant = [...msgs].reverse().find((m) => m.role === 'assistant');

  return (
    <div className={`copilot-panel ${open ? 'open' : ''}`}>
      <button type="button" className="btn soft copilot-toggle" onClick={() => setOpen(!open)}>
        {open ? 'Close Copilot' : 'Ask Copilot'}
      </button>
      {open && (
        <div className="copilot-body panel copilot-enhanced">
          <div className="panel-head">
            <h2>Advisor Copilot</h2>
            <span className="pill conf Verified">Validated queries</span>
          </div>
          <p className="muted">
            {catalog?.welcome?.subtitle ||
              'Understand your clients, investigate portfolio changes, and prepare your next review using verified evidence.'}
            {investorId ? ` · Context: ${investorId}` : ''}
          </p>

          {!msgs.length && !loading && (
            <div className="copilot-welcome">
              <h3>{catalog?.welcome?.title || 'Advisor Copilot'}</h3>
              <div className="copilot-cats">
                {(catalog?.categories || [
                  { id: 'attention', label: 'Client Attention' },
                  { id: 'portfolio', label: 'Portfolio & Goals' },
                  { id: 'advice', label: 'Advice & Follow-ups' },
                  { id: 'meeting', label: 'Meeting Preparation' },
                ]).map((c: any) => (
                  <button
                    key={c.id}
                    type="button"
                    className={`btn soft ${category === c.id ? '' : 'ghost'}`}
                    onClick={() => {
                      setCategory(c.id);
                      setShowDemos(false);
                    }}
                  >
                    {c.label}
                  </button>
                ))}
                <button
                  type="button"
                  className={`btn ${showDemos ? '' : 'ghost'}`}
                  onClick={() => {
                    setShowDemos((v) => !v);
                    setCategory(null);
                  }}
                >
                  Demo Scenarios
                </button>
              </div>

              {category && (
                <div className="copilot-suggestions">
                  <p className="muted">Quick-start — clicks run live analysis (not canned numbers).</p>
                  {quickPrompts.map((p: string) => (
                    <button key={p} type="button" className="chip" onClick={() => ask(p)}>
                      {p}
                    </button>
                  ))}
                </div>
              )}

              {showDemos && (
                <div className="copilot-demos">
                  <p className="muted">
                    Curated Globathon scenarios. Each question calls the same validated services as
                    free-form chat.
                  </p>
                  {Object.entries(demoGroups).map(([group, items]) => (
                    <div key={group} className="copilot-demo-group">
                      <h4>{group}</h4>
                      {(items as any[]).map((s) => (
                        <button
                          key={s.id}
                          type="button"
                          className="chip"
                          onClick={() => ask(s.question)}
                          title={`→ ${s.expected_function}`}
                        >
                          {s.title}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="copilot-messages">
            {msgs.map((m, i) => (
              <div key={i} className={`copilot-msg ${m.role}`}>
                <div className="copilot-msg-body">{m.text}</div>
                {m.role === 'assistant' && m.result && !m.result.denied && (
                  <div className="copilot-answer-card">
                    {m.result.answer?.title && <h4>{m.result.answer.title}</h4>}
                    {(m.result.answer?.bullets || []).length > 0 && (
                      <ul>
                        {m.result.answer.bullets.map((b: string, bi: number) => (
                          <li key={bi}>{b}</li>
                        ))}
                      </ul>
                    )}
                    {(m.result.answer?.claims || []).length > 0 && (
                      <div className="copilot-claims">
                        <strong>Claims & evidence</strong>
                        {(m.result.answer.claims as any[]).map((c, ci) => (
                          <div key={ci} className="copilot-claim">
                            <ConfidencePill confidence={c.status} />
                            <span>{c.text}</span>
                            <span className="muted"> · {c.source}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <p className="muted">
                      Intent: {m.result.intent} → {m.result.mapped_function}
                      {m.result.scenario_id ? ` · scenario ${m.result.scenario_id}` : ''}
                    </p>
                    {m.result.citations?.length ? (
                      <p className="muted">Cites: {m.result.citations.slice(0, 8).join(', ')}</p>
                    ) : null}
                    <EvidenceBadge evidence={m.result.evidence} />
                    {(m.result.links || []).length > 0 && (
                      <div className="filters" style={{ marginTop: 8 }}>
                        {(m.result.links as any[]).map((l) => (
                          <Link key={l.href} className="btn soft" to={l.href}>
                            {l.label}
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            {loading && <div className="muted copilot-loading">Running validated analysis…</div>}
          </div>

          {err && (
            <div className="error">
              {err}{' '}
              <button type="button" className="linkish" onClick={() => ask(msgs.filter((m) => m.role === 'user').slice(-1)[0]?.text)}>
                Retry
              </button>
            </div>
          )}

          {!!lastAssistant?.result?.follow_ups?.length && !loading && (
            <div className="copilot-suggestions">
              <span className="muted">Follow-ups</span>
              {(lastAssistant!.result.follow_ups as string[]).map((f) => (
                <button key={f} type="button" className="chip" onClick={() => ask(f)}>
                  {f}
                </button>
              ))}
            </div>
          )}

          <div className="copilot-composer">
            <input
              style={{ flex: 1, minWidth: 180 }}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about attention, goals, advice, meetings…"
              onKeyDown={(e) => e.key === 'Enter' && ask()}
              aria-label="Copilot question"
            />
            <button type="button" className="btn" onClick={() => ask()} disabled={loading || !query.trim()}>
              {loading ? '…' : 'Ask'}
            </button>
            {!!msgs.length && (
              <button
                type="button"
                className="btn ghost"
                onClick={() => {
                  setMsgs([]);
                  setConversationContext(investorId ? { investor_id: investorId } : {});
                  setErr('');
                }}
              >
                New chat
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
