import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { api, type ClientPriority } from '../api';
import { PriorityPill } from '../components/PriorityPill';
import { ClientWorkspace } from '../clientWorkspace/ClientWorkspace';
import { normalizeTab } from '../clientWorkspace/format';

export default function Clients() {
  const { id, tab } = useParams();
  const navigate = useNavigate();
  const [dir, setDir] = useState<ClientPriority[]>([]);
  const [q, setQ] = useState('');

  useEffect(() => {
    api.clients({ limit: '200', ...(q ? { q } : {}) }).then(async (r) => {
      let list = [...(r.clients || [])];
      if (!q && !list.some((c) => c.investor_id === 'DEMO-INV-001')) {
        try {
          const inv = await api.investor('DEMO-INV-001');
          list = [
            {
              investor_id: 'DEMO-INV-001',
              display_name:
                inv?.snapshot?.investor?.display_name ||
                inv?.investor?.display_name ||
                'Priya Sharma',
              tier: inv?.snapshot?.investor?.tier || 'HNI',
              risk_profile: inv?.snapshot?.investor?.risk_profile || 'Moderate',
              priority: inv?.priority?.priority || 'High',
              score: inv?.priority?.score || 0,
              confidence: inv?.priority?.confidence,
              goal_status: inv?.snapshot?.goal_progress?.status,
            } as ClientPriority,
            ...list,
          ];
        } catch {
          /* keep ranked list */
        }
      }
      setDir(list);
    });
  }, [q]);

  // Legacy /clients/:id → /clients/:id/overview
  if (id && !tab) {
    return <Navigate to={`/clients/${id}/overview`} replace />;
  }

  // Market Shock Simulator is book-level (replaces SIP what-if UI)
  if (id && tab === 'simulator') {
    return <Navigate to={`/what-if/${id}`} replace />;
  }

  // Unknown tab slugs → overview
  if (id && tab && normalizeTab(tab) !== tab) {
    return <Navigate to={`/clients/${id}/${normalizeTab(tab)}`} replace />;
  }

  return (
    <div>
      <div className="page-top">
        <div className="page-header">
          <h1>Clients</h1>
          <p>Directory + tabbed Client Workspace — evidence, portfolio, meetings, review actions.</p>
        </div>
      </div>

      <div className="clients-layout">
        <div className="panel client-dir">
          <label className="search-pill" style={{ marginBottom: '0.85rem', minWidth: 0, width: '100%' }}>
            <svg className="search-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-3.5-3.5" />
            </svg>
            <input
              placeholder="Search name or ID…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              aria-label="Search clients"
            />
          </label>
          <div className="dir-list">
            {dir.map((c) => (
              <button
                type="button"
                key={c.investor_id}
                className={`dir-item ${id === c.investor_id ? 'active' : ''}`}
                onClick={() => navigate(`/clients/${c.investor_id}/overview`)}
              >
                <div className="dir-name">{c.display_name}</div>
                <div className="muted">
                  <PriorityPill priority={c.priority} /> {c.score}
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="client-detail">
          {!id && <p className="muted">Select a client from the directory to open their workspace.</p>}
          {id && <ClientWorkspace investorId={id} />}
        </div>
      </div>
    </div>
  );
}
