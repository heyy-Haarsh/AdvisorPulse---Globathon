import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { api } from '../api';
import { PriorityPill } from '../components/PriorityPill';

const PIE_COLORS = ['#2dd4bf', '#3b82f6', '#a78bfa', '#fbbf24', '#94a3b8'];

export default function Investor() {
  const { id = 'DEMO-INV-001' } = useParams();
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    setData(null);
    api.investor(id).then(setData).catch((e) => setErr(String(e)));
  }, [id]);

  if (err) return <div className="error">{err}</div>;
  if (!data) return <div className="loading">Loading investor dynamic summary…</div>;

  const { snapshot, priority, summary } = data;
  const gp = snapshot.goal_progress;
  const alloc = snapshot.allocation.map((a: any) => ({
    name: a.asset_class,
    value: a.weight_pct,
  }));

  return (
    <div>
      <div className="page-header">
        <h1>
          {snapshot.investor.display_name}{' '}
          <PriorityPill priority={priority.priority} />
        </h1>
        <p>
          Investor Dynamic Summary — {snapshot.disclaimer} Risk: {snapshot.investor.risk_profile}.
          Score {priority.score}.
        </p>
      </div>

      {snapshot.missing_data_warnings?.length > 0 && (
        <div className="warn" style={{ marginBottom: '1rem' }}>
          {snapshot.missing_data_warnings.join(' ')}
        </div>
      )}

      <div className="grid-kpi">
        <div className="kpi">
          <div className="label">Portfolio value</div>
          <div className="value" style={{ fontSize: '1.35rem' }}>
            ₹{(snapshot.portfolio_value / 1e5).toFixed(1)}L
          </div>
        </div>
        <div className="kpi">
          <div className="label">Vs expected path</div>
          <div
            className="value"
            style={{
              fontSize: '1.35rem',
              color: gp.deviation_pct_vs_expected < 0 ? 'var(--critical)' : 'var(--ontrack)',
            }}
          >
            {gp.deviation_pct_vs_expected.toFixed(1)}%
          </div>
        </div>
        <div className="kpi">
          <div className="label">Active return</div>
          <div className="value" style={{ fontSize: '1.35rem' }}>
            {snapshot.performance.active_return_pct?.toFixed(2)} pp
          </div>
        </div>
        <div className="kpi">
          <div className="label">Goal progress</div>
          <div className="value" style={{ fontSize: '1.35rem' }}>
            {gp.progress_to_target_pct.toFixed(0)}%
          </div>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <h2>Goal trajectory</h2>
          <p>
            <strong>{gp.goal_name}</strong> — target ₹{(gp.target_amount / 1e5).toFixed(1)}L by{' '}
            {gp.target_date}
          </p>
          <p className="muted">{gp.methodology}</p>
          <table>
            <tbody>
              <tr>
                <td>Current mapped value</td>
                <td>₹{gp.current_value.toLocaleString('en-IN')}</td>
              </tr>
              <tr>
                <td>Expected path (as of now)</td>
                <td>₹{gp.expected_path_value.toLocaleString('en-IN')}</td>
              </tr>
              <tr>
                <td>Deviation</td>
                <td>
                  ₹{gp.deviation_amount.toLocaleString('en-IN')} (
                  {gp.deviation_pct_vs_expected.toFixed(1)}%)
                </td>
              </tr>
              <tr>
                <td>Years remaining</td>
                <td>{gp.years_remaining}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h2>Asset allocation</h2>
          <div style={{ width: '100%', height: 220 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={alloc} dataKey="value" nameKey="name" outerRadius={80} label>
                  {alloc.map((_: any, i: number) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <h2>Performance vs expectation</h2>
          <p className="muted">{snapshot.performance.methodology}</p>
          <table>
            <tbody>
              <tr>
                <td>Portfolio TWR (window)</td>
                <td>{snapshot.performance.twr_window_pct}%</td>
              </tr>
              <tr>
                <td>Benchmark TWR</td>
                <td>{snapshot.performance.benchmark_twr_pct}%</td>
              </tr>
              <tr>
                <td>Modified Dietz (approx.)</td>
                <td>
                  {snapshot.performance.modified_dietz_pct != null
                    ? `${snapshot.performance.modified_dietz_pct}%`
                    : 'n/a'}
                </td>
              </tr>
              <tr>
                <td>Comparison period</td>
                <td>{snapshot.gap_explanation.comparison_period}</td>
              </tr>
              <tr>
                <td>Confidence</td>
                <td>{snapshot.gap_explanation.confidence}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h2>Why the gap? (qualified drivers)</h2>
          <ul className="factor-list">
            {snapshot.gap_explanation.factors.map((f: any) => (
              <li key={f.factor}>
                <div>
                  <strong>{f.factor}</strong>
                  <div className="muted">{f.detail}</div>
                  <div className="muted">Supported by: {f.supported_by}</div>
                </div>
              </li>
            ))}
          </ul>
          <p className="muted" style={{ marginTop: '0.75rem' }}>
            Limitations: {(snapshot.gap_explanation.limitations || []).join(' ')}
          </p>
        </div>
      </div>

      <div className="panel">
        <h2>Evidence-linked AI summary</h2>
        <p>{summary.summary_text}</p>
        <p className="muted">
          Mode: {summary.mode} · LLM used: {String(summary.llm_used)} ·{' '}
          {summary.fabrication_guard}
        </p>
        <h3>Suggested advisor review actions</h3>
        <ul>
          {summary.suggested_actions.map((a: any) => (
            <li key={a.action}>
              <strong>{a.action}</strong> — <span className="muted">{a.rationale}</span>
            </li>
          ))}
        </ul>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
          <Link className="btn" to={`/meeting/${id}`}>
            Meeting preparation
          </Link>
          <Link className="btn ghost" to={`/notes/${id}`}>
            Advisor notes
          </Link>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <h2>Historical advice</h2>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Recommendation</th>
                <th>Follow-up</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.advice_history.map((a: any) => (
                <tr key={a.advice_id}>
                  <td>{a.advice_date}</td>
                  <td>{a.recommendation}</td>
                  <td>{a.follow_up_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="panel">
          <h2>Changes since last review</h2>
          <p className="muted">Last review: {snapshot.data_timestamps.last_review_date}</p>
          <ul>
            {(snapshot.changes_since_last_review || []).map((c: any, i: number) => (
              <li key={i}>
                [{c.type}] {c.detail}
              </li>
            ))}
          </ul>
          <p className="muted">
            Data as of {snapshot.data_timestamps.as_of} · holdings{' '}
            {snapshot.data_timestamps.holdings_as_of} · freshness{' '}
            {snapshot.data_timestamps.data_freshness_days}d
          </p>
        </div>
      </div>
    </div>
  );
}
