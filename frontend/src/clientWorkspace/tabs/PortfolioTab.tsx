import { useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ConfidencePill, EvidenceBadge } from '../../components/EvidenceBadge';
import { formatInr, formatPct, formatPp } from '../format';

const PIE_COLORS = ['#333A73', '#5b8def', '#c9a227', '#6aa88a', '#d48aa8', '#8b9bb4'];

type Props = {
  data: any;
  crosscheck: any;
  onDrift: (alertId: string, status: string) => Promise<void>;
};

export function PortfolioTab({ data, crosscheck, onDrift }: Props) {
  const [sub, setSub] = useState<'allocation' | 'drift'>('allocation');
  const [sev, setSev] = useState('');
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);

  const comparison = data.drift?.allocation_vs_policy?.rows || [];
  const weightSum = data.drift?.allocation_vs_policy?.weight_sum_pct;
  const weightOk = data.drift?.allocation_vs_policy?.weight_sum_ok;
  const perf = data.snapshot?.performance;

  const chartData = useMemo(
    () =>
      comparison
        .filter((r: any) => r.current_weight_pct != null || r.policy_weight_pct != null)
        .map((r: any) => ({
          name: r.asset_class.replace('Equity - ', '').replace('Debt - ', 'Debt '),
          current: r.current_weight_pct ?? 0,
          policy: r.policy_weight_pct ?? 0,
        })),
    [comparison],
  );

  const alerts = (data.drift?.alerts || []).filter((a: any) => {
    if (sev && a.severity !== sev) return false;
    if (status && (a.status || 'open') !== status) return false;
    if (q) {
      const hay = `${a.title} ${a.rule}`.toLowerCase();
      if (!hay.includes(q.toLowerCase())) return false;
    }
    return true;
  });

  return (
    <div>
      <div className="ws-subnav" role="tablist" aria-label="Portfolio sections">
        <button
          type="button"
          role="tab"
          aria-selected={sub === 'allocation'}
          className={`btn ${sub === 'allocation' ? '' : 'ghost'}`}
          onClick={() => setSub('allocation')}
        >
          Allocation & Performance
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={sub === 'drift'}
          className={`btn ${sub === 'drift' ? '' : 'ghost'}`}
          onClick={() => setSub('drift')}
        >
          Drift Alerts
        </button>
      </div>

      {sub === 'allocation' && (
        <>
          <section className="panel">
            <h2>Current vs policy allocation</h2>
            <p className="muted">{data.drift?.allocation_vs_policy?.note}</p>
            <p>
              Weight sum: <strong>{weightSum == null ? 'N/A' : `${weightSum}%`}</strong>
              {weightOk === false && (
                <span className="warn"> — does not total 100% (not silently normalized)</span>
              )}
            </p>
            <div style={{ width: '100%', height: 280 }}>
              <ResponsiveContainer>
                <BarChart data={chartData} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E8E2D9" />
                  <XAxis type="number" domain={[0, 60]} unit="%" stroke="#737985" fontSize={11} />
                  <YAxis type="category" dataKey="name" width={110} stroke="#737985" fontSize={11} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="current" name="Current %" fill="#333A73" radius={[0, 6, 6, 0]} />
                  <Bar dataKey="policy" name="Policy %" fill="#9db8a3" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Asset class</th>
                  <th>Current</th>
                  <th>Policy</th>
                  <th>Δ pp</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {comparison.map((r: any) => (
                  <tr key={r.asset_class}>
                    <td>{r.asset_class}</td>
                    <td>{formatPct(r.current_weight_pct)}</td>
                    <td>{r.policy_weight_pct == null ? '—' : formatPct(r.policy_weight_pct)}</td>
                    <td>{formatPp(r.delta_pp, 1)}</td>
                    <td>{formatInr(r.market_value, { lakhs: true })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ width: '100%', height: 180, marginTop: 12 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={(data.snapshot?.allocation || []).map((a: any) => ({
                      name: a.asset_class,
                      value: a.weight_pct,
                    }))}
                    dataKey="value"
                    nameKey="name"
                    outerRadius={70}
                  >
                    {(data.snapshot?.allocation || []).map((_: any, i: number) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="panel">
            <h2>Performance comparison</h2>
            <div className="grid-kpi">
              <div className="kpi">
                <div className="label">Portfolio TWR</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {formatPct(perf?.twr_window_pct)}
                </div>
              </div>
              <div className="kpi">
                <div className="label">Benchmark TWR</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {formatPct(perf?.benchmark_twr_pct)}
                </div>
              </div>
              <div className="kpi">
                <div className="label">Active return</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {formatPp(perf?.active_return_pct)}
                </div>
              </div>
              <div className="kpi">
                <div className="label">Modified Dietz</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {formatPct(perf?.modified_dietz_pct)}
                </div>
              </div>
            </div>
            <p className="muted">{perf?.methodology}</p>
            <p className="muted">Returns are from DEMO portfolio series — not transaction cash-flow CSV.</p>

            {crosscheck?.available && (
              <>
                <h3>Cross-check (QuantStats / native)</h3>
                <p className="muted">
                  {crosscheck.quantstats?.used
                    ? 'QuantStats metrics available.'
                    : crosscheck.quantstats?.note || 'Native fallback.'}
                </p>
                <div className="grid-kpi">
                  <div className="kpi">
                    <div className="label">Max drawdown</div>
                    <div className="value" style={{ fontSize: '1.1rem' }}>
                      {crosscheck.native?.max_drawdown == null
                        ? 'N/A'
                        : formatPct(crosscheck.native.max_drawdown * 100)}
                    </div>
                  </div>
                  <div className="kpi">
                    <div className="label">Vol ann ≈</div>
                    <div className="value" style={{ fontSize: '1.1rem' }}>
                      {crosscheck.native?.vol_ann_approx == null
                        ? 'N/A'
                        : formatPct(crosscheck.native.vol_ann_approx * 100)}
                    </div>
                  </div>
                  <div className="kpi">
                    <div className="label">Sharpe ann ≈</div>
                    <div className="value" style={{ fontSize: '1.1rem' }}>
                      {crosscheck.native?.sharpe_ann_approx?.toFixed?.(2) ?? 'N/A'}
                    </div>
                  </div>
                </div>
                <EvidenceBadge evidence={crosscheck.evidence} />
              </>
            )}
          </section>
        </>
      )}

      {sub === 'drift' && (
        <section className="panel">
          <h2>Drift alerts</h2>
          <p className="muted">
            Confirm = acknowledge valid. Dismiss = should not stay active. Resolve = issue addressed.
            Missing data is never distress.
          </p>
          <div className="filters">
            <select value={sev} onChange={(e) => setSev(e.target.value)} aria-label="Severity filter">
              <option value="">All severities</option>
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
            <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter">
              <option value="">All statuses</option>
              <option value="open">open</option>
              <option value="confirmed">confirmed</option>
            </select>
            <input
              placeholder="Search alert…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              aria-label="Search alerts"
            />
          </div>
          {alerts.map((a: any) => (
            <article key={a.alert_id} className="ws-drift-card">
              <button
                type="button"
                className="ws-drift-head"
                onClick={() => setExpanded(expanded === a.alert_id ? null : a.alert_id)}
              >
                <div>
                  <strong>{a.title}</strong>
                  <div className="muted">
                    {a.severity} · {a.status || 'open'}
                    {a.drift_pp != null ? ` · Δ ${a.drift_pp} pp` : ''}
                    {a.is_distress ? '' : ' · not distress'}
                  </div>
                </div>
                <ConfidencePill confidence={a.evidence?.confidence} />
              </button>
              {expanded === a.alert_id && (
                <div className="ws-drift-body">
                  <p>{a.evidence?.claim}</p>
                  <EvidenceBadge evidence={a.evidence} />
                  <div className="filters">
                    <button type="button" className="btn ghost" onClick={() => onDrift(a.alert_id, 'confirmed')}>
                      Confirm
                    </button>
                    <button type="button" className="btn ghost" onClick={() => onDrift(a.alert_id, 'dismissed')}>
                      Dismiss
                    </button>
                    <button type="button" className="btn ghost" onClick={() => onDrift(a.alert_id, 'resolved')}>
                      Resolve
                    </button>
                  </div>
                </div>
              )}
            </article>
          ))}
          {!alerts.length && <p className="muted">No alerts match the current filters.</p>}
        </section>
      )}
    </div>
  );
}
