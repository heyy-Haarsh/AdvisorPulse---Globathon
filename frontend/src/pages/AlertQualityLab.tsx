import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { EvidenceBadge } from '../components/EvidenceBadge';
import { PriorityPill } from '../components/PriorityPill';

function MetricCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string | number;
  note?: string;
}) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className="value" style={{ fontSize: '1.35rem' }}>
        {typeof value === 'number' ? value.toFixed(2) : value}
      </div>
      {note && (
        <div className="muted" style={{ fontSize: '0.75rem' }}>
          {note}
        </div>
      )}
    </div>
  );
}

export default function AlertQualityLab() {
  const [data, setData] = useState<any>(null);
  const [scenario, setScenario] = useState<any>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    api
      .alertQuality()
      .then(setData)
      .catch((e) => setErr(String(e)));
    api.scenario().then(setScenario).catch(() => undefined);
  }, []);

  if (err) return <div className="error">{err}</div>;
  if (!data) return <div className="loading">Computing labeled alert-quality metrics…</div>;

  const pulse = data.pulse || {};
  const baseline = data.baseline || {};

  return (
    <div>
      <div className="page-top">
        <div className="page-header">
          <h1>Alert Quality Lab</h1>
          <p>
            Pulse vs CRM-ish baseline on labeled DEMO scenarios (n={data.n_labeled}). Metrics are
            computed — not invented.
          </p>
        </div>
        <Link className="btn soft" to="/insights">
          ← Insights
        </Link>
      </div>

      <EvidenceBadge evidence={data.evidence} />

      <div className="grid-kpi" style={{ marginTop: '1rem' }}>
        <MetricCard label="Pulse Precision@10" value={pulse.precision_at_10 ?? 0} />
        <MetricCard label="Pulse Precision@20" value={pulse.precision_at_20 ?? 0} />
        <MetricCard label="Pulse Recall@20" value={pulse.recall_at_20 ?? 0} />
        <MetricCard
          label="Pulse FP rate @20"
          value={pulse.false_positive_rate_at_20 ?? 0}
          note="Labeled false_alarm_context in top-20"
        />
        <MetricCard label="Baseline Precision@20" value={baseline.precision_at_20 ?? 0} />
        <MetricCard label="Baseline Recall@20" value={baseline.recall_at_20 ?? 0} />
        <MetricCard
          label="Evidence coverage @20"
          value={pulse.evidence_coverage_top_20 ?? 0}
          note="Material claims with sources"
        />
      </div>
      <p className="muted">{data.methodology}</p>

      {scenario && (
        <div className="panel">
          <h2>Demo contrast story</h2>
          <p className="muted">From GET /api/demo/scenario</p>
          <ul className="factor-list">
            <li>
              <span>
                <Link to={`/clients/${scenario.primary?.investor_id}`}>
                  {scenario.primary?.title}
                </Link>
              </span>
              <PriorityPill priority={scenario.primary?.data?.priority?.priority || 'Critical'} />
            </li>
            <li>
              <span>
                <Link to={`/clients/${scenario.blind_spot?.investor_id}`}>
                  {scenario.blind_spot?.title}
                </Link>
                <div className="muted">{scenario.blind_spot?.why_overlooked}</div>
              </span>
              <PriorityPill
                priority={scenario.blind_spot?.data?.priority?.priority || 'Critical'}
              />
            </li>
            <li>
              <span>
                <Link to={`/clients/${scenario.contrast?.investor_id}`}>
                  {scenario.contrast?.title}
                </Link>
                <div className="muted">{scenario.contrast?.why_not_escalated}</div>
              </span>
              <PriorityPill priority={scenario.contrast?.data?.priority?.priority || 'On Track'} />
            </li>
          </ul>
        </div>
      )}

      <div className="two-col">
        <div className="panel">
          <h2>Pulse top 20</h2>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Client</th>
                <th>Label</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {(data.pulse_top_20 || []).map((c: any) => (
                <tr key={c.investor_id}>
                  <td>{c.rank}</td>
                  <td>
                    <Link to={`/clients/${c.investor_id}`}>{c.display_name}</Link>
                  </td>
                  <td className="muted">{c.label || '—'}</td>
                  <td>{c.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {pulse.material_ranks && (
            <p className="muted">
              Material ranks:{' '}
              {Object.entries(pulse.material_ranks as Record<string, number>)
                .map(([id, r]) => `${id}→#${r}`)
                .join(', ')}
            </p>
          )}
        </div>

        <div className="panel">
          <h2>Baseline top 20 (CRM-ish)</h2>
          <p className="muted">High-visibility first, then stale last_review_date</p>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Client</th>
                <th>Label</th>
                <th>Days</th>
              </tr>
            </thead>
            <tbody>
              {(data.baseline_top_20 || []).map((c: any) => (
                <tr key={c.investor_id}>
                  <td>{c.rank}</td>
                  <td>
                    <Link to={`/clients/${c.investor_id}`}>{c.display_name}</Link>
                  </td>
                  <td className="muted">{c.label || '—'}</td>
                  <td>{c.days_since_review}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {baseline.material_ranks && (
            <p className="muted">
              Material ranks:{' '}
              {Object.entries(baseline.material_ranks as Record<string, number>)
                .map(([id, r]) => `${id}→#${r}`)
                .join(', ')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
