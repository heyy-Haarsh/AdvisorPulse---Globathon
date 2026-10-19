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
    api.clients({ limit: '80', ...(q ? { q } : {}) }).then((r) => setDir(r.clients));
  }, [q]);

  // Legacy /clients/:id → /clients/:id/overview
  if (id && !tab) {
    return <Navigate to={`/clients/${id}/overview`} replace />;
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
          <p>Directory + tabbed Client Workspace — evidence, portfolio, meetings, simulator, review actions.</p>
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
