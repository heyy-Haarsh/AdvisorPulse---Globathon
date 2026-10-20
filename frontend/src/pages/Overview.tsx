import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import { api, type ClientPriority, type Overview as OverviewType } from '../api';
import { PriorityPill } from '../components/PriorityPill';
import { ConfidencePill, EvidenceBadge } from '../components/EvidenceBadge';
import { CopilotPanel } from '../components/CopilotPanel';
import { NextReviewAction } from '../components/NextReviewAction';

const COLORS: Record<string, string> = {
  Critical: '#c45c5c',
  High: '#c47a3a',
  Monitor: '#c9a227',
  'On Track': '#2f8f6b',
};

const PIE_COLORS = ['#5b8def', '#c9a227', '#d48aa8', '#6aa88a'];

function initials(name: string) {
  return name
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

function Spark({ up = true }: { up?: boolean }) {
  const stroke = up ? '#2f8f6b' : '#c45c5c';
  return (
    <svg className="spark" viewBox="0 0 72 36" fill="none" aria-hidden>
      <path
        d={up ? 'M2 28 C14 26, 18 12, 30 14 S48 30, 70 8' : 'M2 8 C14 10, 22 28, 36 22 S54 8, 70 26'}
        stroke={stroke}
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function Overview() {
  const [data, setData] = useState<OverviewType | null>(null);
  const [queue, setQueue] = useState<ClientPriority[]>([]);
  const [selected, setSelected] = useState<ClientPriority | null>(null);
  const [priority, setPriority] = useState('');
  const [tier, setTier] = useState('');
  const [search, setSearch] = useState('');
  const [err, setErr] = useState('');
  const [engineTab, setEngineTab] = useState<'queue' | 'radar'>('queue');
  const [radarSeg, setRadarSeg] = useState('less_observed');
  const [radar, setRadar] = useState<any>(null);

  const load = () => {
    api.overview().then(setData).catch((e) => setErr(String(e)));
    const params: Record<string, string> = {};
    if (priority) params.priority = priority;
    if (tier) params.tier = tier;
    api
      .attention(params)
      .then((r) => setQueue(r.clients.slice(0, 25)))
      .catch((e) => setErr(String(e)));
  };

  const loadRadar = () => {
    api
      .blindSpot(radarSeg)
      .then(setRadar)
      .catch((e) => setErr(String(e)));
  };

  useEffect(() => {
    load();
  }, [priority, tier]);

  useEffect(() => {
    if (engineTab === 'radar') loadRadar();
  }, [engineTab, radarSeg]);

  const decide = async (id: string, action: string) => {
    await api.attentionDecision(id, action);
    load();
    setSelected(null);
  };

  const filteredQueue = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return queue;
    return queue.filter(
      (c) =>
        c.display_name.toLowerCase().includes(q) ||
        c.investor_id.toLowerCase().includes(q)
    );
  }, [queue, search]);

  if (err) return <div className="error">{err} — is the API running on :8000?</div>;
  if (!data) return <div className="loading">Loading advisor overview…</div>;

  const chartData = Object.entries(data.priority_distribution).map(([name, value]) => ({
    name,
    value,
    soft: Math.round(Number(value) * 0.35),
  }));

  const pieData = Object.entries(data.priority_distribution).map(([name, value]) => ({
    name,
    value: Number(value),
  }));

  const reviewPct =
    data.total_clients > 0
      ? Math.round((data.clients_requiring_review / data.total_clients) * 100)
      : 0;

  return (
    <div>
      <div className="page-top">
        <div className="page-header">
          <h1>Overview</h1>
          <p>
            Attention command center — detect, prioritize, and act across{' '}
            {data.total_clients} DEMO clients.{' '}
            <Link className="linkish" to="/attention-engine">
              Open full Attention Engine →
            </Link>
          </p>
        </div>
        <label className="search-pill">
          <svg className="search-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3.5-3.5" />
          </svg>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search attention queue…"
          />
        </label>
      </div>

      <div className="workspace">
        <div className="workspace-main">
          <div className="grid-kpi">
            <div className="kpi sage">
              <div className="label">Client book</div>
              <div className="value">{data.total_clients}</div>
              <div className="delta">DEMO universe</div>
              <Spark />
            </div>
            <div className="kpi peach">
              <div className="label">Need review</div>
              <div className="value">{data.clients_requiring_review}</div>
              <div className={`delta ${reviewPct > 10 ? 'down' : ''}`}>
                {reviewPct}% of book
              </div>
              <Spark up={reviewPct <= 10} />
            </div>
            <div className="kpi lavender">
              <div className="label">Long-tail coverage</div>
              <div className="value">{data.long_tail_count}</div>
              <div className="kpi-note">Signals outside your top relationships</div>
              <div className="kpi-cta">
                <Link className="btn soft" to="/clients">
                  Open clients
                </Link>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>Priority mix this week</h2>
              <span className="muted">
                {data.resolved_suppressed ?? 0} resolved alerts demoted
              </span>
            </div>
            <div style={{ width: '100%', height: 240 }}>
              <ResponsiveContainer>
                <BarChart data={chartData} barCategoryGap="28%">
                  <XAxis dataKey="name" stroke="#9aa1ad" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#9aa1ad" fontSize={12} allowDecimals={false} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{
                      background: '#fff',
                      border: '1px solid #e8e4dc',
                      borderRadius: 14,
                      boxShadow: '0 8px 24px rgba(0,0,0,0.06)',
                    }}
                  />
                  <Bar dataKey="value" stackId="a" radius={[0, 0, 0, 0]}>
                    {chartData.map((e) => (
                      <Cell key={e.name} fill={COLORS[e.name] || '#2a6f6a'} />
                    ))}
                  </Bar>
                  <Bar dataKey="soft" stackId="a" radius={[10, 10, 0, 0]} fillOpacity={0.28}>
                    {chartData.map((e) => (
                      <Cell key={`${e.name}-soft`} fill={COLORS[e.name] || '#2a6f6a'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="muted" style={{ marginBottom: 0 }}>
              {data.illustrative_note}
            </p>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>Attention Engine</h2>
              <div className="filters">
                <button
                  type="button"
                  className={`btn ${engineTab === 'queue' ? '' : 'ghost'}`}
                  onClick={() => setEngineTab('queue')}
                >
                  Queue
                </button>
                <button
                  type="button"
                  className={`btn ${engineTab === 'radar' ? '' : 'ghost'}`}
                  onClick={() => setEngineTab('radar')}
                >
                  Blind Spot Radar
                </button>
              </div>
            </div>

            {engineTab === 'queue' && (
              <>
                <p className="muted" style={{ marginTop: 0 }}>
                  Explainable weighted scores. Severity ≠ confidence. Record decisions so resolved
                  items stop dominating the queue.
                </p>
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
                  <span className="muted">{filteredQueue.length} shown</span>
                </div>

                <div className="two-col">
                  <table>
                    <thead>
                      <tr>
                        <th>Client</th>
                        <th>Severity</th>
                        <th>Confidence</th>
                        <th>Score</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredQueue.map((c) => (
                        <tr
                          key={c.investor_id}
                          className={selected?.investor_id === c.investor_id ? 'row-active' : ''}
                        >
                          <td>
                            <div className="person-cell">
                              <div className="person-avatar">{initials(c.display_name)}</div>
                              <button
                                type="button"
                                className="linkish"
                                onClick={() => setSelected(c)}
                              >
                                {c.display_name}
                              </button>
                            </div>
                          </td>
                          <td>
                            <PriorityPill priority={c.priority} />
                          </td>
                          <td>
                            <ConfidencePill confidence={c.confidence} />
                          </td>
                          <td style={{ fontWeight: 700 }}>{c.score}</td>
                          <td>
                            <Link className="linkish" to={`/clients/${c.investor_id}`}>
                              Profile →
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  <div>
                    {selected ? (
                      <div className="drawer">
                        <h3>{selected.display_name}</h3>
                        <p className="muted">{selected.priority_reason}</p>
                        <EvidenceBadge evidence={selected.evidence} />
                        <ul className="factor-list">
                          {selected.factors.map((f) => (
                            <li key={f.name}>
                              <span>
                                {f.name}
                                <div className="muted">{f.detail}</div>
                              </span>
                              <span className="pts">{f.points}</span>
                            </li>
                          ))}
                        </ul>
                        <NextReviewAction
                          investorId={selected.investor_id}
                          compact
                          onDecided={load}
                        />
                        <div className="filters" style={{ marginTop: '0.75rem' }}>
                          <button
                            type="button"
                            className="btn"
                            onClick={() => decide(selected.investor_id, 'reviewed')}
                          >
                            Mark reviewed
                          </button>
                          <button
                            type="button"
                            className="btn ghost"
                            onClick={() => decide(selected.investor_id, 'follow_up')}
                          >
                            Follow-up
                          </button>
                          <button
                            type="button"
                            className="btn ghost"
                            onClick={() => decide(selected.investor_id, 'dismiss')}
                          >
                            Dismiss
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p className="muted">
                        Select a client to inspect factors and open Next Best Review Action.
                      </p>
                    )}
                  </div>
                </div>
              </>
            )}

            {engineTab === 'radar' && (
              <>
                <p className="muted" style={{ marginTop: 0 }}>
                  Attention need × review obscurity. Switch to <strong>less-observed</strong> to
                  surface overlooked long-tail clients (not assumed unawareness — recorded engagement
                  fields).
                </p>
                <div className="filters">
                  <select value={radarSeg} onChange={(e) => setRadarSeg(e.target.value)}>
                    <option value="less_observed">Less-observed</option>
                    <option value="frequently_reviewed">Frequently reviewed</option>
                    <option value="all">All segments</option>
                  </select>
                  <Link className="linkish" to="/insights/alert-quality">
                    Alert Quality Lab →
                  </Link>
                </div>
                {radar?.hero && (
                  <p>
                    Overlooked case near top:{' '}
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => setSelected(radar.hero)}
                    >
                      {radar.hero.display_name}
                    </button>{' '}
                    <PriorityPill priority={radar.hero.priority} /> score {radar.hero.score}
                  </p>
                )}
                {radar && (
                  <div className="two-col">
                    <div>
                      <div style={{ width: '100%', height: 260 }}>
                        <ResponsiveContainer>
                          <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                            <XAxis
                              type="number"
                              dataKey="review_obscurity"
                              name="Obscurity"
                              stroke="#9aa1ad"
                              fontSize={11}
                              domain={[0, 100]}
                            />
                            <YAxis
                              type="number"
                              dataKey="attention_need"
                              name="Need"
                              stroke="#9aa1ad"
                              fontSize={11}
                              domain={[0, 100]}
                            />
                            <ZAxis range={[60, 160]} />
                            <Tooltip
                              cursor={{ strokeDasharray: '3 3' }}
                              content={({ payload }) => {
                                const p = payload?.[0]?.payload;
                                if (!p) return null;
                                return (
                                  <div
                                    style={{
                                      background: '#fff',
                                      border: '1px solid #e8e4dc',
                                      borderRadius: 12,
                                      padding: 8,
                                    }}
                                  >
                                    <strong>{p.display_name}</strong>
                                    <div className="muted">
                                      need {p.attention_need} · obscurity {p.review_obscurity}
                                    </div>
                                  </div>
                                );
                              }}
                            />
                            <Scatter
                              data={(radar.clients || []).map((c: any) => ({
                                ...c,
                                fill: c.is_blind_spot_hero
                                  ? '#c45c5c'
                                  : COLORS[c.priority] || '#2a6f6a',
                              }))}
                              onClick={(s: any) => s && setSelected(s)}
                            >
                              {(radar.clients || []).map((c: any) => (
                                <Cell
                                  key={c.investor_id}
                                  fill={
                                    c.is_blind_spot_hero
                                      ? '#c45c5c'
                                      : COLORS[c.priority] || '#2a6f6a'
                                  }
                                />
                              ))}
                            </Scatter>
                          </ScatterChart>
                        </ResponsiveContainer>
                      </div>
                      <p className="muted">{radar.methodology}</p>
                      <table>
                        <thead>
                          <tr>
                            <th>Client</th>
                            <th>Need</th>
                            <th>Obscurity</th>
                            <th>Priority</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(radar.clients || []).slice(0, 12).map((c: any) => (
                            <tr
                              key={c.investor_id}
                              className={
                                selected?.investor_id === c.investor_id ? 'row-active' : ''
                              }
                            >
                              <td>
                                <button
                                  type="button"
                                  className="linkish"
                                  onClick={() => setSelected(c)}
                                >
                                  {c.display_name}
                                  {c.is_blind_spot_hero ? ' ★' : ''}
                                </button>
                              </td>
                              <td>{c.attention_need}</td>
                              <td>{c.review_obscurity}</td>
                              <td>
                                <PriorityPill priority={c.priority} />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div>
                      {selected ? (
                        <div className="drawer">
                          <h3>{selected.display_name}</h3>
                          <p className="muted">{selected.priority_reason}</p>
                          {(selected as any).why_now && (
                            <ul className="factor-list">
                              {((selected as any).why_now as string[]).map((w) => (
                                <li key={w}>
                                  <span>{w}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                          <EvidenceBadge evidence={selected.evidence} />
                          <NextReviewAction
                            investorId={selected.investor_id}
                            onDecided={() => {
                              load();
                              loadRadar();
                            }}
                          />
                        </div>
                      ) : (
                        <p className="muted">
                          Click a radar point or row to open evidence + Next Best Review Action.
                        </p>
                      )}
                    </div>
                  </div>
                )}
                {!radar && <div className="loading">Loading radar…</div>}
              </>
            )}
          </div>

          <CopilotPanel />
        </div>

        <aside className="rail">
          <div className="panel">
            <h2>Book composition</h2>
            <div className="donut-wrap">
              <ResponsiveContainer width="100%" height={170}>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={52}
                    outerRadius={70}
                    paddingAngle={3}
                  >
                    {pieData.map((e, i) => (
                      <Cell key={e.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="donut-center">
                <div className="tiny">Total</div>
                <div className="big">{data.total_clients}</div>
              </div>
            </div>
            <div className="legend-bars">
              {pieData.map((e, i) => {
                const pct = data.total_clients
                  ? Math.round((e.value / data.total_clients) * 100)
                  : 0;
                return (
                  <div className="legend-row" key={e.name}>
                    <span>{e.name}</span>
                    <strong>{pct}%</strong>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{
                          width: `${pct}%`,
                          background: PIE_COLORS[i % PIE_COLORS.length],
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>Long-tail signals</h2>
              <Link className="linkish" to="/insights">
                Insights
              </Link>
            </div>
            <ul className="recent-list">
              {data.recently_changed_long_tail.slice(0, 6).map((c) => (
                <li key={c.investor_id}>
                  <div className="person-avatar">{initials(c.display_name)}</div>
                  <div className="recent-meta">
                    <strong>
                      <Link to={`/clients/${c.investor_id}`}>{c.display_name}</Link>
                    </strong>
                    <span className="muted">{c.priority}</span>
                  </div>
                  <div className="recent-amt">{c.score}</div>
                </li>
              ))}
            </ul>
          </div>

          <div className="panel" style={{ background: 'var(--gold-soft)', border: 'none' }}>
            <h2>Advisor tip</h2>
            <p className="muted" style={{ marginTop: 0 }}>
              High-visibility clients still get meeting prep depth. The queue’s incremental value is
              discovering who among the long tail needs attention now.
            </p>
            <Link className="btn" to="/meetings/DEMO-INV-001">
              Open meeting prep
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
