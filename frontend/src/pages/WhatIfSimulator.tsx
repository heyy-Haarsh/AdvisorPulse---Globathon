import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../api';
import { ConfidencePill, EvidenceBadge } from '../components/EvidenceBadge';
import { formatInr, formatPct } from '../clientWorkspace/format';

type ScenarioType = 'stock' | 'index' | 'broad_market';

const PRIORITY_LABEL: Record<string, string> = {
  high: 'High review priority',
  moderate: 'Moderate review priority',
  monitor: 'Monitor',
  insufficient_data: 'Insufficient data',
  no_exposure: 'No supported exposure',
};

const CHART_COLORS = ['#9a3412', '#c2410c', '#a16207', '#78716c', '#57534e', '#0f766e', '#0d9488', '#115e59'];

function formatSignedPct(pct: number) {
  return `${pct > 0 ? '+' : ''}${pct}%`;
}

function formatMoney(value: number | null | undefined, currency = 'INR') {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  if (currency === 'USD') {
    return `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
  return formatInr(value);
}

export default function WhatIfSimulator() {
  const { id: routeFocusId } = useParams();
  const [catalog, setCatalog] = useState<any>(null);
  const [scenarioType, setScenarioType] = useState<ScenarioType>('stock');
  const [instrumentId, setInstrumentId] = useState('NSE:RELIANCE');
  const [instrumentQuery, setInstrumentQuery] = useState('');
  const [pct, setPct] = useState(-12);
  const [includeIndirect, setIncludeIndirect] = useState(true);
  const [showHelp, setShowHelp] = useState(false);
  const [payload, setPayload] = useState<any>(null);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [exposureOnly, setExposureOnly] = useState(true);
  const [sortKey, setSortKey] = useState<'abs_impact' | 'impact_pct' | 'priority'>('abs_impact');
  const [selectedId, setSelectedId] = useState<string | null>(routeFocusId || null);
  const [toast, setToast] = useState('');
  const [busyAction, setBusyAction] = useState('');

  useEffect(() => {
    api
      .marketShockAssumptions()
      .then((c) => {
        setCatalog(c);
        setPct(c.default_price_change_pct ?? c.default_equity_market_shock_pct ?? -12);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    if (routeFocusId) setSelectedId(routeFocusId);
  }, [routeFocusId]);

  const instrumentOptions = useMemo(() => {
    if (!catalog) return [];
    if (scenarioType === 'stock') return catalog.stocks || [];
    if (scenarioType === 'index') return catalog.indices || [];
    return [];
  }, [catalog, scenarioType]);

  const filteredInstruments = useMemo(() => {
    const q = instrumentQuery.trim().toLowerCase();
    if (!q) return instrumentOptions;
    return instrumentOptions.filter(
      (i: any) =>
        String(i.name || '')
          .toLowerCase()
          .includes(q) ||
        String(i.symbol || '')
          .toLowerCase()
          .includes(q) ||
        String(i.instrument_id || '')
          .toLowerCase()
          .includes(q),
    );
  }, [instrumentOptions, instrumentQuery]);

  const selectedInstrument = useMemo(
    () => (catalog?.instruments || []).find((i: any) => i.instrument_id === instrumentId) || null,
    [catalog, instrumentId],
  );

  useEffect(() => {
    // When switching type, pick a sensible default instrument
    if (scenarioType === 'stock') setInstrumentId('NSE:RELIANCE');
    else if (scenarioType === 'index') setInstrumentId('INDEX:NIFTY50');
    else setInstrumentId('');
    setPayload(null);
  }, [scenarioType]);

  const resetDefault = () => {
    setScenarioType('stock');
    setInstrumentId('NSE:RELIANCE');
    setPct(catalog?.default_price_change_pct ?? -12);
    setIncludeIndirect(true);
    setPayload(null);
    setErr('');
  };

  const run = async () => {
    setLoading(true);
    setErr('');
    try {
      const r = await api.marketShockRun({
        scenario_type: scenarioType,
        instrument_id: scenarioType === 'broad_market' ? null : instrumentId,
        price_change_pct: pct,
        include_indirect_exposure: includeIndirect,
        assumptions_version: catalog?.assumptions_version || 'demo-v1',
        scenario_name:
          scenarioType === 'broad_market'
            ? `Broad equity ${formatSignedPct(pct)}`
            : `${selectedInstrument?.symbol || instrumentId} ${formatSignedPct(pct)}`,
      });
      setPayload(r);
      const first =
        routeFocusId ||
        r.results?.find((x: any) => x.exposure_status === 'supported')?.client_id;
      if (first) setSelectedId(first);
    } catch (e) {
      setErr(String(e));
      setPayload(null);
    } finally {
      setLoading(false);
    }
  };

  const results: any[] = payload?.results || [];

  const filtered = useMemo(() => {
    let rows = [...results];
    const q = search.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (r) =>
          String(r.display_name || '')
            .toLowerCase()
            .includes(q) ||
          String(r.client_id || '')
            .toLowerCase()
            .includes(q),
      );
    }
    if (priorityFilter) rows = rows.filter((r) => r.review_priority === priorityFilter);
    if (exposureOnly) rows = rows.filter((r) => r.exposure_status === 'supported');
    const rank: Record<string, number> = {
      high: 0,
      moderate: 1,
      monitor: 2,
      no_exposure: 3,
      insufficient_data: 4,
    };
    rows.sort((a, b) => {
      if (sortKey === 'priority') {
        return (rank[a.review_priority] ?? 9) - (rank[b.review_priority] ?? 9);
      }
      if (sortKey === 'impact_pct') {
        return (b.estimated_portfolio_impact_pct ?? 0) - (a.estimated_portfolio_impact_pct ?? 0);
      }
      return (
        Math.abs(b.estimated_position_impact ?? 0) - Math.abs(a.estimated_position_impact ?? 0)
      );
    });
    return rows;
  }, [results, search, priorityFilter, exposureOnly, sortKey]);

  const selected = useMemo(
    () => results.find((r) => r.client_id === selectedId) || null,
    [results, selectedId],
  );

  const summary = payload?.summary;
  const chartBuckets = payload?.charts?.impact_amount_buckets || payload?.charts?.impact_pct_buckets || [];

  const scenarioBlurb = useMemo(() => {
    if (scenarioType === 'broad_market') {
      return `Simulate a ${formatSignedPct(pct)} broad equity-market movement using documented asset-class sensitivities.`;
    }
    const sym = selectedInstrument?.symbol || instrumentId;
    return `Simulate a ${formatSignedPct(pct)} movement in ${sym} and estimate the effect on client positions directly or indirectly exposed to this instrument.`;
  }, [scenarioType, pct, selectedInstrument, instrumentId]);

  const markReviewed = async () => {
    if (!selected) return;
    setBusyAction('review');
    try {
      await api.marketShockMarkReviewed({
        investor_id: selected.client_id,
        scenario_equity_shock_pct: pct,
        note: 'Reviewed asset-scenario result',
      });
      setToast(`Marked ${selected.display_name} scenario result as reviewed (audit only).`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusyAction('');
    }
  };

  const createFollowUp = async () => {
    if (!selected) return;
    setBusyAction('followup');
    try {
      await api.addCommitment({
        investor_id: selected.client_id,
        action: `Review exposure under ${scenarioType} scenario ${instrumentId || 'BROAD'} ${formatSignedPct(pct)}`,
        status: 'open',
      });
      setToast('Draft follow-up commitment created — confirm in Meetings & Memory.');
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusyAction('');
    }
  };

  return (
    <div className="market-shock-page">
      <div className="page-top">
        <div className="page-header">
          <h1>Market & Asset Scenario Simulator</h1>
          <p>
            Model hypothetical price movements and understand how they could affect every client's
            portfolio.
          </p>
        </div>
        <div className="filters">
          <span className="pill hypo">HYPOTHETICAL</span>
          <span className="pill conf Limited">Demo Data</span>
          {payload?.scenario?.calculation_timestamp && (
            <span className="muted" style={{ fontSize: '0.8rem' }}>
              Calculated {new Date(payload.scenario.calculation_timestamp).toLocaleString()}
            </span>
          )}
          <button type="button" className="btn ghost" onClick={resetDefault}>
            Reset
          </button>
          <button type="button" className="btn soft" onClick={() => setShowHelp((v) => !v)}>
            {showHelp ? 'Hide help' : 'Assumptions / help'}
          </button>
        </div>
      </div>

      {showHelp && (
        <div className="panel market-shock-help">
          <p className="muted">{catalog?.disclaimer}</p>
          <p className="muted">
            Stock scenarios use direct security positions plus documented fund look-through.
            Index scenarios use tracker / sensitivity mappings. Broad-market uses asset-class
            betas. Currencies are never mixed without a validated FX rate.
          </p>
        </div>
      )}

      <section className="panel market-shock-controls">
        <div className="panel-head">
          <h2>Scenario configuration</h2>
          <span className="muted">Not a live market feed · Not a forecast</span>
        </div>

        <div className="market-shock-presets" role="group" aria-label="Scenario type">
          {(
            catalog?.scenario_types || [
              { id: 'stock', label: 'Individual Stock' },
              { id: 'index', label: 'Market Index' },
              { id: 'broad_market', label: 'Broad-Market Scenario' },
            ]
          ).map((t: any) => (
            <button
              key={t.id}
              type="button"
              className={`btn ${scenarioType === t.id ? '' : 'ghost'}`}
              onClick={() => setScenarioType(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {scenarioType !== 'broad_market' && (
          <div className="market-shock-instrument">
            <label>
              Search instrument
              <input
                value={instrumentQuery}
                onChange={(e) => setInstrumentQuery(e.target.value)}
                placeholder="Name, symbol, or ID"
                aria-label="Search instrument"
              />
            </label>
            <label>
              Selected instrument
              <select
                value={instrumentId}
                onChange={(e) => {
                  setInstrumentId(e.target.value);
                  setPayload(null);
                }}
                aria-label="Select instrument"
              >
                {filteredInstruments.map((i: any) => (
                  <option key={i.instrument_id} value={i.instrument_id}>
                    {i.name} — {i.exchange}: {i.symbol} ({i.currency})
                  </option>
                ))}
              </select>
            </label>
            {selectedInstrument && (
              <div className="muted market-shock-ref">
                <div>
                  <strong>Selected instrument:</strong> {selectedInstrument.exchange}:{' '}
                  {selectedInstrument.symbol}
                </div>
                <div>
                  <strong>Reference price:</strong>{' '}
                  {selectedInstrument.reference_price != null
                    ? `${selectedInstrument.currency} ${selectedInstrument.reference_price}`
                    : 'Unavailable'}{' '}
                  · source {selectedInstrument.price_source} · as-of{' '}
                  {selectedInstrument.price_timestamp || 'n/a'}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="market-shock-presets">
          {(catalog?.presets || []).map((p: any) => (
            <button
              key={p.id}
              type="button"
              className={`btn soft ${pct === p.price_change_pct ? '' : 'ghost'}`}
              onClick={() => {
                setPct(Number(p.price_change_pct));
                setPayload(null);
              }}
            >
              {p.label}
            </button>
          ))}
        </div>

        <label className="market-shock-slider-label">
          Hypothetical price movement
          <div className="market-shock-shock-display">
            {formatSignedPct(pct)}{' '}
            <span className="muted" style={{ fontSize: '1rem' }}>
              ({pct === 0 ? 'No change' : pct > 0 ? 'Positive price movement' : 'Negative price movement'})
            </span>
          </div>
          <input
            type="range"
            min={catalog?.slider?.min ?? -30}
            max={catalog?.slider?.max ?? 30}
            step={catalog?.slider?.step ?? 1}
            value={pct}
            onChange={(e) => {
              setPct(Number(e.target.value));
              setPayload(null);
            }}
            aria-label="Price change percent"
          />
          <div className="filters">
            <input
              type="number"
              min={-30}
              max={30}
              step={1}
              value={pct}
              onChange={(e) => {
                const v = Number(e.target.value);
                if (!Number.isNaN(v)) {
                  setPct(Math.max(-30, Math.min(30, Math.round(v))));
                  setPayload(null);
                }
              }}
              aria-label="Editable price change percent"
              style={{ width: 100 }}
            />
            <span className="muted">%</span>
          </div>
        </label>

        <p className="muted">{scenarioBlurb}</p>

        <div className="filters">
          {scenarioType === 'stock' && (
            <label>
              <input
                type="checkbox"
                checked={includeIndirect}
                onChange={(e) => {
                  setIncludeIndirect(e.target.checked);
                  setPayload(null);
                }}
              />{' '}
              Include documented indirect fund exposure
            </label>
          )}
          <button type="button" className="btn" onClick={run} disabled={loading}>
            {loading ? 'Running…' : 'Run Simulation'}
          </button>
        </div>
      </section>

      {err && (
        <div className="error">
          {err}{' '}
          <button type="button" className="linkish" onClick={run}>
            Retry
          </button>
        </div>
      )}
      {toast && (
        <div className="panel">
          {toast}{' '}
          <button type="button" className="linkish" onClick={() => setToast('')}>
            Dismiss
          </button>
        </div>
      )}

      {!payload && !loading && (
        <p className="muted">Configure a scenario and run the simulation to see affected clients.</p>
      )}
      {loading && <p className="muted">Running validated scenario analysis…</p>}

      {payload && !loading && (
        <>
          <section className="kpi-grid market-shock-kpis">
            <div className="kpi">
              <span className="muted">Clients Evaluated</span>
              <strong>{summary?.clients_evaluated ?? '—'}</strong>
            </div>
            <div className="kpi">
              <span className="muted">Clients With Supported Exposure</span>
              <strong>{summary?.clients_with_supported_exposure ?? '—'}</strong>
            </div>
            <div className="kpi">
              <span className="muted">Estimated Aggregate Impact</span>
              <strong>
                {summary?.estimated_aggregate_impact != null
                  ? formatMoney(summary.estimated_aggregate_impact, summary.currency)
                  : 'Unavailable'}
              </strong>
              <span className="muted" style={{ fontSize: '0.75rem' }}>
                {summary?.aggregate_impact_label}
              </span>
            </div>
            <div className="kpi">
              <span className="muted">Clients Potentially Requiring Review</span>
              <strong>{summary?.clients_for_review ?? '—'}</strong>
            </div>
            <div className="kpi">
              <span className="muted">Incomplete Exposure Data</span>
              <strong>{summary?.incomplete_estimates ?? '—'}</strong>
            </div>
          </section>
          <p className="muted">{summary?.coverage_note}</p>

          <div className="panel">
            <div className="panel-head">
              <h2>Estimated impact distribution</h2>
              <span className="muted">Signed position impacts (zero reference)</span>
            </div>
            <div style={{ width: '100%', height: 240 }}>
              <ResponsiveContainer>
                <BarChart data={chartBuckets}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="bucket" tick={{ fontSize: 10 }} />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <ReferenceLine y={0} stroke="#44403c" />
                  <Bar dataKey="count" name="Clients">
                    {chartBuckets.map((_: any, i: number) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Affected clients</h2>
                <p className="muted">
                  Ranked by absolute estimated impact. Gains and losses are both shown — not
                  predicted client behavior.
                </p>
              </div>
            </div>
            <div className="filters market-shock-filters">
              <input
                placeholder="Search name or ID"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
                <option value="">All priorities</option>
                {Object.keys(PRIORITY_LABEL).map((k) => (
                  <option key={k} value={k}>
                    {PRIORITY_LABEL[k]}
                  </option>
                ))}
              </select>
              <select value={sortKey} onChange={(e) => setSortKey(e.target.value as any)}>
                <option value="abs_impact">Sort: |monetary impact|</option>
                <option value="impact_pct">Sort: portfolio % impact</option>
                <option value="priority">Sort: review priority</option>
              </select>
              <label>
                <input
                  type="checkbox"
                  checked={exposureOnly}
                  onChange={(e) => setExposureOnly(e.target.checked)}
                />{' '}
                Supported exposure only
              </label>
            </div>

            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Client</th>
                    <th>Direct exp.</th>
                    <th>Indirect exp.</th>
                    <th>Total exposure</th>
                    <th>Portfolio</th>
                    <th>Est. impact</th>
                    <th>After</th>
                    <th>Port. %</th>
                    <th>Status</th>
                    <th>Review</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice(0, 100).map((r) => (
                    <tr
                      key={r.client_id}
                      className={selectedId === r.client_id ? 'selected' : ''}
                      onClick={() => setSelectedId(r.client_id)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td>
                        <strong>{r.display_name}</strong>
                        <div className="muted">{r.client_id}</div>
                      </td>
                      <td>{formatMoney(r.direct_exposure_value, r.primary_impact_currency)}</td>
                      <td>{formatMoney(r.indirect_exposure_value, r.primary_impact_currency)}</td>
                      <td>{formatMoney(r.total_scenario_exposure, r.primary_impact_currency)}</td>
                      <td>{formatMoney(r.current_portfolio_value)}</td>
                      <td>
                        {r.estimated_position_impact != null
                          ? formatMoney(r.estimated_position_impact, r.primary_impact_currency)
                          : '—'}
                      </td>
                      <td>{formatMoney(r.estimated_portfolio_value_after)}</td>
                      <td>
                        {r.estimated_portfolio_impact_pct != null
                          ? formatPct(r.estimated_portfolio_impact_pct)
                          : '—'}
                      </td>
                      <td>
                        <span className={`pill ms-${r.impact_status}`}>{r.impact_status}</span>
                      </td>
                      <td>
                        <span className={`pill ms-${r.review_priority}`}>
                          {PRIORITY_LABEL[r.review_priority] || r.review_priority}
                        </span>
                      </td>
                      <td>
                        <ConfidencePill confidence={r.confidence} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!filtered.length && (
              <p className="muted">
                No supported portfolio exposure was found for this instrument under current
                filters.
              </p>
            )}
          </section>

          {selected && (
            <section className="panel market-shock-detail">
              <div className="panel-head">
                <h2>
                  {selected.display_name}{' '}
                  <span className="muted">({selected.client_id})</span>
                </h2>
                <ConfidencePill confidence={selected.confidence} />
              </div>
              <h3>Exposure & impact</h3>
              <ul>
                <li>
                  Direct exposure:{' '}
                  {formatMoney(selected.direct_exposure_value, selected.primary_impact_currency)}
                </li>
                <li>
                  Indirect exposure:{' '}
                  {formatMoney(selected.indirect_exposure_value, selected.primary_impact_currency)}
                </li>
                <li>
                  Estimated position impact:{' '}
                  {formatMoney(selected.estimated_position_impact, selected.primary_impact_currency)}{' '}
                  ({selected.impact_status})
                </li>
                <li>
                  Portfolio after scenario:{' '}
                  {formatMoney(selected.estimated_portfolio_value_after)} (
                  {selected.estimated_portfolio_impact_pct != null
                    ? formatPct(selected.estimated_portfolio_impact_pct)
                    : 'n/a'}
                  )
                </li>
              </ul>
              <h3>Position-level impacts</h3>
              {(selected.position_impacts || []).length === 0 ? (
                <p className="muted">
                  {selected.exposure_status === 'no_supported_exposure'
                    ? 'No supported exposure found.'
                    : selected.exposure_status === 'exposure_unknown'
                      ? 'Exposure unknown.'
                      : 'No position details.'}
                </p>
              ) : (
                <ul>
                  {selected.position_impacts.map((p: any) => (
                    <li key={p.position_id}>
                      [{p.exposure_kind}] {p.position_id}: baseline{' '}
                      {formatMoney(p.baseline_value, p.currency)} → impact{' '}
                      {formatMoney(p.estimated_impact, p.currency)} (assumed{' '}
                      {p.assumed_return_pct}%)
                      {p.note ? <span className="muted"> — {p.note}</span> : null}
                    </li>
                  ))}
                </ul>
              )}
              <h3>Why surfaced</h3>
              <ul>
                {(selected.review_reasons || []).map((r: string) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
              <h3>Suggested actions</h3>
              <ul>
                {(selected.suggested_actions || []).map((a: string) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
              {selected.attention_signals?.available && (
                <p className="muted">{selected.attention_signals.note}</p>
              )}
              <EvidenceBadge evidence={selected.evidence} />
              <div className="filters" style={{ marginTop: '0.75rem' }}>
                <Link className="btn soft" to={`/clients/${selected.client_id}/overview`}>
                  Open client profile
                </Link>
                <Link className="btn soft" to={`/meeting-intel/${selected.client_id}`}>
                  Prepare meeting brief
                </Link>
                <button
                  type="button"
                  className="btn soft"
                  disabled={!!busyAction}
                  onClick={createFollowUp}
                >
                  Create draft follow-up
                </button>
                <button
                  type="button"
                  className="btn ghost"
                  disabled={!!busyAction}
                  onClick={markReviewed}
                >
                  Mark scenario reviewed
                </button>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
