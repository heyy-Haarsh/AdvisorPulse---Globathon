import { useState } from 'react';
import { api } from '../api';
import { EvidenceBadge } from './EvidenceBadge';

export function CopilotPanel({ investorId }: { investorId?: string }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  const ask = async () => {
    setLoading(true);
    setErr('');
    try {
      const r = await api.copilot(query, investorId);
      setResult(r);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`copilot-panel ${open ? 'open' : ''}`}>
      <button type="button" className="btn soft copilot-toggle" onClick={() => setOpen(!open)}>
        {open ? 'Close copilot' : 'Ask copilot'}
      </button>
      {open && (
        <div className="copilot-body panel">
          <div className="panel-head">
            <h2>Advisor Copilot</h2>
            <span className="pill conf Verified">Validated queries</span>
          </div>
          <p className="muted">
            Maps questions to approved analysis functions — not arbitrary SQL. No invented metrics.
            {investorId ? ` Context: ${investorId}` : ''}
          </p>
          <div className="filters">
            <input
              style={{ flex: 1, minWidth: 200 }}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Why is DEMO-INV-001 critical? What if I increase SIP by 10000?"
              onKeyDown={(e) => e.key === 'Enter' && ask()}
            />
            <button type="button" className="btn" onClick={ask} disabled={loading || !query.trim()}>
              {loading ? '…' : 'Ask'}
            </button>
          </div>
          {err && <div className="error">{err}</div>}
          {result?.denied && <div className="warn">{result.message}</div>}
          {result && !result.denied && (
            <div>
              <p>
                <span className="muted">Intent:</span> {result.intent} → {result.mapped_function}
              </p>
              {result.citations?.length ? (
                <p className="muted">Cites: {result.citations.slice(0, 6).join(', ')}</p>
              ) : null}
              <EvidenceBadge evidence={result.evidence} />
              <pre className="json-block">{JSON.stringify(result.result ?? result.message, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
