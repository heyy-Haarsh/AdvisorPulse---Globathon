import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { EvidenceBadge } from '../components/EvidenceBadge';
import { PriorityPill } from '../components/PriorityPill';
import { CopilotPanel } from '../components/CopilotPanel';

export default function Insights() {
  const [data, setData] = useState<any>(null);
  const [selected, setSelected] = useState<any>(null);
  const [txn, setTxn] = useState<any>(null);
  const [dq, setDq] = useState<any>(null);
  const [exceptions, setExceptions] = useState<any[]>([]);
  const [dqBusy, setDqBusy] = useState(false);
  const [err, setErr] = useState('');
  const [tab, setTab] = useState<'patterns' | 'dq'>('patterns');

  const refreshDq = async () => {
    const ex = await api.txnExceptions();
    setExceptions(ex.exceptions || []);
    api.txnSignals().then(setTxn).catch(() => undefined);
  };

  useEffect(() => {
    api
      .patterns()
      .then(setData)
      .catch((e) => setErr(String(e)));
    api.txnSignals().then(setTxn).catch(() => undefined);
    api.txnExceptions().then((r) => setExceptions(r.exceptions || [])).catch(() => undefined);
  }, []);

  const runDirtyDemo = async () => {
    setDqBusy(true);
    try {
      const r = await api.validateTxnDemoDirty();
      setDq(r);
      await refreshDq();
    } catch (e) {
      setErr(String(e));
    } finally {
      setDqBusy(false);
    }
  };

  const onUpload = async (file: File | null) => {
    if (!file) return;
    setDqBusy(true);
    try {
      const r = await api.validateTxnUpload(file);
      setDq(r);
      await refreshDq();
    } catch (e) {
      setErr(String(e));
    } finally {
      setDqBusy(false);
    }
  };

  const resolveEx = async (id: string) => {
    await api.resolveTxnException(id, 'accept_normalized');
    await refreshDq();
  };

  const doImport = async () => {
    setDqBusy(true);
    try {
      const r = await api.importTransactions();
      setDq((prev: any) => ({ ...prev, import_result: r }));
      await refreshDq();
    } catch (e) {
      setErr(String(e));
    } finally {
      setDqBusy(false);
    }
  };

  if (err) return <div className="error">{err}</div>;
  if (!data) return <div className="loading">Discovering cross-client patterns…</div>;

  return (
    <div>
      <div className="page-top">
        <div className="page-header">
          <h1>Insights</h1>
          <p>
            Explainable cohorts across {data.total_clients} DEMO clients — rule-based, not causal claims.
          </p>
        </div>
        <div className="filters">
          <button
            type="button"
            className={`btn ${tab === 'patterns' ? '' : 'ghost'}`}
            onClick={() => setTab('patterns')}
          >
            Patterns
          </button>
          <button
            type="button"
            className={`btn ${tab === 'dq' ? '' : 'ghost'}`}
            onClick={() => setTab('dq')}
          >
            Data Quality
          </button>
          <Link className="btn soft" to="/insights/alert-quality">
            Alert Quality Lab
          </Link>
        </div>
      </div>

      {tab === 'patterns' && (
        <>
      <EvidenceBadge evidence={data.evidence} />

      <div className="two-col" style={{ marginTop: '1rem' }}>
        <div className="panel">
          <h2>Cohorts</h2>
          <table>
            <thead>
              <tr>
                <th>Pattern</th>
                <th>Count</th>
                <th>Rule</th>
              </tr>
            </thead>
            <tbody>
              {(data.cohorts || []).map((c: any) => (
                <tr key={c.id} className={selected?.id === c.id ? 'row-active' : ''}>
                  <td>
                    <button type="button" className="linkish" onClick={() => setSelected(c)}>
                      {c.title}
                    </button>
                    {!c.is_distress_signal && <span className="muted"> · data quality</span>}
                  </td>
                  <td>{c.count}</td>
                  <td className="muted">{c.rule}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h2>Drill-down</h2>
          {selected ? (
            <>
              <p>{selected.explanation}</p>
              <table>
                <thead>
                  <tr>
                    <th>Client</th>
                    <th>Priority</th>
                    <th>Score</th>
                    <th>Goal Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {(selected.clients || []).map((c: any) => (
                    <tr key={c.investor_id}>
                      <td>
                        <Link to={`/clients/${c.investor_id}`}>{c.display_name}</Link>
                      </td>
                      <td>
                        <PriorityPill priority={c.priority} />
                      </td>
                      <td>{c.score}</td>
                      <td>{c.goal_deviation?.toFixed?.(1) ?? '—'}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {selected.truncated && <p className="muted">Showing first 40 members.</p>}
            </>
          ) : (
            <p className="muted">Select a cohort to drill into clients.</p>
          )}
        </div>
      </div>

      {txn && (
        <div className="panel">
          <h2>Layer-1 cash-flow signals (not investment returns)</h2>
          <p className="muted">
            Duplicates flagged: {txn.signals?.duplicates_flagged ?? txn.ingestion_report?.duplicates_flagged ?? 0}.{' '}
            {(txn.signals?.limitations || []).join(' ')}
          </p>
          {txn.signals?.available && (
            <div className="grid-kpi">
              <div className="kpi">
                <div className="label">Credits</div>
                <div className="value" style={{ fontSize: '1.1rem' }}>
                  ₹{(txn.signals.total_credits / 1000).toFixed(0)}k
                </div>
              </div>
              <div className="kpi">
                <div className="label">Debits</div>
                <div className="value" style={{ fontSize: '1.1rem' }}>
                  ₹{(txn.signals.total_debits / 1000).toFixed(0)}k
                </div>
              </div>
              <div className="kpi">
                <div className="label">Net</div>
                <div className="value" style={{ fontSize: '1.1rem' }}>
                  ₹{(txn.signals.net_cashflow / 1000).toFixed(0)}k
                </div>
              </div>
            </div>
          )}
        </div>
      )}
        </>
      )}

      {tab === 'dq' && (
        <div className="panel" style={{ marginTop: '1rem' }}>
          <h2>Transaction Data Quality</h2>
          <p className="warn">
            Cash-flow layer is not linked to DEMO-INV-* portfolio investors. Tens–hundreds of rows
            cannot establish spending baselines or distress; transactions ≠ investment returns.
          </p>
          <div className="filters">
            <button type="button" className="btn" disabled={dqBusy} onClick={runDirtyDemo}>
              Validate dirty demo CSV
            </button>
            <label className="btn ghost" style={{ cursor: 'pointer' }}>
              Upload CSV
              <input
                type="file"
                accept=".csv"
                style={{ display: 'none' }}
                onChange={(e) => onUpload(e.target.files?.[0] || null)}
              />
            </label>
            <button type="button" className="btn soft" disabled={dqBusy} onClick={doImport}>
              Import staged → signals
            </button>
          </div>
          {dq?.summary && (
            <div className="grid-kpi" style={{ marginTop: '1rem' }}>
              <div className="kpi">
                <div className="label">Rows read</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {dq.summary.rows_read}
                </div>
              </div>
              <div className="kpi">
                <div className="label">Duplicates</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {dq.summary.duplicates_flagged}
                </div>
              </div>
              <div className="kpi">
                <div className="label">Invalid dates</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {dq.summary.invalid_dates}
                </div>
              </div>
              <div className="kpi">
                <div className="label">Currency normalized</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {dq.summary.currency_normalized}
                </div>
              </div>
              <div className="kpi">
                <div className="label">Missing category</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {dq.summary.missing_category}
                </div>
              </div>
              <div className="kpi">
                <div className="label">Category suggestions</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {dq.summary.category_suggestions}
                </div>
              </div>
            </div>
          )}
          {(dq?.summary?.limitations || []).map((l: string) => (
            <p key={l} className="muted">
              {l}
            </p>
          ))}
          <h3>Exception review</h3>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>User</th>
                <th>Reasons</th>
                <th>Suggested cat</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {exceptions.slice(0, 40).map((ex: any) => (
                <tr key={ex.exception_id}>
                  <td className="muted">{ex.transaction_id}</td>
                  <td>{ex.user_id}</td>
                  <td>{(ex.reasons || []).join(', ')}</td>
                  <td>{ex.category_suggested || '—'}</td>
                  <td>{ex.status}</td>
                  <td>
                    {ex.status === 'open' && (
                      <button
                        type="button"
                        className="btn ghost"
                        onClick={() => resolveEx(ex.exception_id)}
                      >
                        Resolve
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!exceptions.length && (
            <p className="muted">No staged exceptions — run validate on the dirty demo CSV.</p>
          )}
          {dq?.import_result && (
            <p className="muted">Import: {JSON.stringify(dq.import_result)}</p>
          )}
        </div>
      )}

      <CopilotPanel />
    </div>
  );
}
