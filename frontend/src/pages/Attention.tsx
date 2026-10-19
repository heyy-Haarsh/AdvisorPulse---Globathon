import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type ClientPriority } from '../api';
import { PriorityPill } from '../components/PriorityPill';

export default function Attention() {
  const [clients, setClients] = useState<ClientPriority[]>([]);
  const [priority, setPriority] = useState('');
  const [tier, setTier] = useState('');
  const [selected, setSelected] = useState<ClientPriority | null>(null);
  const [err, setErr] = useState('');

  const load = () => {
    const params: Record<string, string> = {};
    if (priority) params.priority = priority;
    if (tier) params.tier = tier;
    api
      .attention(params)
      .then((r) => setClients(r.clients))
      .catch((e) => setErr(String(e)));
  };

  useEffect(() => {
    load();
  }, [priority, tier]);

  const mark = async (id: string) => {
    await api.markReviewed(id, true);
    load();
    if (selected?.investor_id === id) {
      setSelected({ ...selected, marked_reviewed: true });
    }
  };

  if (err) return <div className="error">{err}</div>;

  return (
    <div>
      <div className="page-header">
        <h1>Attention Prioritization</h1>
        <p>
          Transparent ranking across the wider book. Factors and thresholds are configurable —
          not an opaque AI score.
        </p>
      </div>

      <div className="filters">
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="">All priorities</option>
          <option>Critical</option>
          <option>High</option>
          <option>Monitor</option>
          <option>On Track</option>
        </select>
        <select value={tier} onChange={(e) => setTier(e.target.value)}>
          <option value="">All tiers</option>
          <option value="high_visibility">High-visibility</option>
          <option value="long_tail">Long-tail</option>
        </select>
        <span className="muted">{clients.length} clients</span>
      </div>

      <div className="two-col">
        <div className="panel" style={{ maxHeight: '70vh', overflow: 'auto' }}>
          <h2>Ranked clients</h2>
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Client</th>
                <th>Priority</th>
                <th>Score</th>
                <th>Last review</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c, i) => (
                <tr
                  key={c.investor_id}
                  onClick={() => setSelected(c)}
                  style={{ cursor: 'pointer', opacity: c.marked_reviewed ? 0.55 : 1 }}
                >
                  <td>{i + 1}</td>
                  <td>
                    {c.display_name}
                    {c.marked_reviewed ? ' ✓' : ''}
                  </td>
                  <td>
                    <PriorityPill priority={c.priority} />
                  </td>
                  <td>{c.score}</td>
                  <td className="muted">{c.last_review_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h2>Why this ranking?</h2>
          {!selected && <p className="muted">Select a client to inspect factors.</p>}
          {selected && (
            <>
              <h3 style={{ marginTop: 0 }}>
                <Link to={`/investor/${selected.investor_id}`}>{selected.display_name}</Link>
              </h3>
              <p>
                <PriorityPill priority={selected.priority} /> score {selected.score}
              </p>
              <p className="muted">{selected.priority_reason}</p>
              {selected.data_quality_issue && (
                <div className="warn">
                  Data-quality flag present — missing/stale data is not treated as financial distress.
                </div>
              )}
              <ul className="factor-list">
                {selected.factors.map((f) => (
                  <li key={f.name + f.detail}>
                    <div>
                      <strong>{f.name}</strong>
                      <div className="muted">{f.detail}</div>
                    </div>
                    <div className="pts">{f.points} pts</div>
                  </li>
                ))}
              </ul>
              <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
                <button className="btn" onClick={() => mark(selected.investor_id)}>
                  Mark reviewed
                </button>
                <Link className="btn ghost" to={`/meeting/${selected.investor_id}`}>
                  Meeting prep
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
