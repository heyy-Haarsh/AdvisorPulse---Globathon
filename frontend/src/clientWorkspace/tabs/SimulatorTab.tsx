import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../../api';
import { EvidenceBadge } from '../../components/EvidenceBadge';
import { formatInr, formatPct } from '../format';

type ScenarioType = 'sip_contribution' | 'allocation_change' | 'market_movement' | 'security_holding_change';

type Props = {
  investorId: string;
  data: any;
};

export function SimulatorTab({ investorId, data }: Props) {
  const [scenario, setScenario] = useState<ScenarioType>('sip_contribution');
  const [sipDelta, setSipDelta] = useState(10000);
  const [returnDelta, setReturnDelta] = useState(0);
  const [years, setYears] = useState<number | ''>('');
  const [lump, setLump] = useState(0);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [shocks, setShocks] = useState<Record<string, number>>({});
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [scenarioName, setScenarioName] = useState('Scenario A');

  const alloc = data.snapshot?.allocation || [];

  useEffect(() => {
    const w: Record<string, number> = {};
    const s: Record<string, number> = {};
    for (const a of alloc) {
      w[a.asset_class] = Number(a.weight_pct) || 0;
      s[a.asset_class] = 0;
    }
    setWeights(w);
    setShocks(s);
    setResult(null);
  }, [investorId, alloc.length]);

  const weightSum = useMemo(
    () => Object.values(weights).reduce((a, b) => a + Number(b || 0), 0),
    [weights],
  );

  const run = async () => {
    setBusy(true);
    setErr('');
    try {
      let body: any = { scenario_type: scenario };
      if (scenario === 'sip_contribution') {
        body = {
          ...body,
          sip_delta: sipDelta,
          return_delta_pp: returnDelta,
          lump_sum: lump,
          years_override: years === '' ? undefined : Number(years),
        };
      } else if (scenario === 'allocation_change') {
        body = { ...body, proposed_weights: weights };
      } else if (scenario === 'market_movement') {
        body = { ...body, market_shocks: shocks };
      }
      const r = await api.whatif(investorId, body);
      setResult(r);
      if (r.error) setErr(r.error);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setResult(null);
    setErr('');
    if (scenario === 'sip_contribution') {
      setSipDelta(10000);
      setReturnDelta(0);
      setLump(0);
      setYears('');
    } else {
      const w: Record<string, number> = {};
      const s: Record<string, number> = {};
      for (const a of alloc) {
        w[a.asset_class] = Number(a.weight_pct) || 0;
        s[a.asset_class] = 0;
      }
      setWeights(w);
      setShocks(s);
    }
  };

  const compareChart = useMemo(() => {
    if (!result) return [];
    if (result.scenario_type === 'sip_contribution' && result.baseline) {
      return [
        { name: 'Baseline', value: result.baseline.projected_value },
        { name: 'Scenario', value: result.alternative.projected_value },
        { name: 'Target', value: result.inputs?.target_amount },
      ];
    }
    if (result.scenario_type === 'allocation_change' && result.scenario_allocation) {
      return result.scenario_allocation.map((r: any) => ({
        name: r.asset_class.replace('Equity - ', ''),
        current: result.baseline_allocation?.find((b: any) => b.asset_class === r.asset_class)
          ?.weight_pct,
        scenario: r.weight_pct,
      }));
    }
    if (result.scenario_type === 'market_movement' && result.rows) {
      return result.rows.map((r: any) => ({
        name: r.asset_class.replace('Equity - ', ''),
        baseline: r.baseline_value,
        scenario: r.scenario_value,
      }));
    }
    return [];
  }, [result]);

  return (
    <div className="ws-sim">
      <aside className="panel ws-sim-config">
        <h2>Scenario configuration</h2>
        <span className="pill hypo">HYPOTHETICAL</span>
        <label className="muted">
          Scenario name
          <input value={scenarioName} onChange={(e) => setScenarioName(e.target.value)} />
        </label>
        <label className="muted">
          Type
          <select
            value={scenario}
            onChange={(e) => {
              setScenario(e.target.value as ScenarioType);
              setResult(null);
            }}
          >
            <option value="sip_contribution">SIP / contribution change</option>
            <option value="allocation_change">Allocation change</option>
            <option value="market_movement">Hypothetical market movement</option>
            <option value="security_holding_change">Stock / security holding change</option>
          </select>
        </label>

        {scenario === 'sip_contribution' && (
          <>
            <label className="muted">
              SIP Δ (INR / mo)
              <input type="number" value={sipDelta} onChange={(e) => setSipDelta(Number(e.target.value))} />
            </label>
            <label className="muted">
              Return Δ (pp)
              <input
                type="number"
                value={returnDelta}
                onChange={(e) => setReturnDelta(Number(e.target.value))}
              />
            </label>
            <label className="muted">
              Horizon years (optional)
              <input
                type="number"
                value={years}
                onChange={(e) => setYears(e.target.value === '' ? '' : Number(e.target.value))}
              />
            </label>
            <label className="muted">
              Lump sum (alt seed only)
              <input type="number" value={lump} onChange={(e) => setLump(Number(e.target.value))} />
            </label>
          </>
        )}

        {scenario === 'allocation_change' && (
          <>
            <p className="muted">Edit proposed weights. Sum must be within 2pp of 100%. AUM unchanged.</p>
            <p>
              Sum: <strong>{weightSum.toFixed(1)}%</strong>
            </p>
            {Object.keys(weights).map((ac) => (
              <label key={ac} className="muted">
                {ac}
                <input
                  type="number"
                  value={weights[ac]}
                  onChange={(e) => setWeights({ ...weights, [ac]: Number(e.target.value) })}
                />
              </label>
            ))}
          </>
        )}

        {scenario === 'market_movement' && (
          <>
            <p className="muted">Shock % by asset class (e.g. -10). Not a forecast.</p>
            {Object.keys(shocks).map((ac) => (
              <label key={ac} className="muted">
                {ac} shock %
                <input
                  type="number"
                  value={shocks[ac]}
                  onChange={(e) => setShocks({ ...shocks, [ac]: Number(e.target.value) })}
                />
              </label>
            ))}
          </>
        )}

        {scenario === 'security_holding_change' && (
          <p className="warn">
            Security-level lots/prices are not exposed in this DEMO. Use allocation or market
            movement scenarios instead. Running will return an honest unsupported response.
          </p>
        )}

        <div className="filters">
          <button type="button" className="btn" disabled={busy} onClick={run}>
            {busy ? 'Running…' : 'Run scenario'}
          </button>
          <button type="button" className="btn ghost" onClick={reset}>
            Reset
          </button>
        </div>
        <p className="muted" style={{ fontSize: '0.8rem' }}>
          Local naming only — scenarios are not persisted to portfolio records. Save/export backend
          is not implemented.
        </p>
      </aside>

      <section className="panel ws-sim-main">
        <h2>{scenarioName} — comparison</h2>
        {err && <div className="error">{err}</div>}
        {!result && !err && (
          <p className="muted">Configure a scenario and run to compare baseline vs hypothetical.</p>
        )}
        {result && !result.error && result.scenario_type === 'sip_contribution' && (
          <>
            <div className="grid-kpi">
              <div className="kpi">
                <div className="label">Baseline projection</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {formatInr(result.baseline?.projected_value, { lakhs: true })}
                </div>
              </div>
              <div className="kpi">
                <div className="label">Alternative</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {formatInr(result.alternative?.projected_value, { lakhs: true })}
                </div>
              </div>
              <div className="kpi">
                <div className="label">Delta vs baseline</div>
                <div className="value" style={{ fontSize: '1.2rem' }}>
                  {formatInr(result.delta_vs_baseline, { lakhs: true })}
                </div>
              </div>
            </div>
          </>
        )}
        {result && result.scenario_type === 'market_movement' && !result.error && (
          <div className="grid-kpi">
            <div className="kpi">
              <div className="label">Baseline AUM</div>
              <div className="value" style={{ fontSize: '1.2rem' }}>
                {formatInr(result.baseline_portfolio_value, { lakhs: true })}
              </div>
            </div>
            <div className="kpi">
              <div className="label">Scenario AUM</div>
              <div className="value" style={{ fontSize: '1.2rem' }}>
                {formatInr(result.scenario_portfolio_value, { lakhs: true })}
              </div>
            </div>
            <div className="kpi">
              <div className="label">Change</div>
              <div className="value" style={{ fontSize: '1.2rem' }}>
                {formatInr(result.delta_value, { lakhs: true })} ({formatPct(result.delta_pct)})
              </div>
            </div>
          </div>
        )}
        {result && result.scenario_type === 'allocation_change' && !result.error && (
          <p>
            Portfolio value held constant at{' '}
            <strong>{formatInr(result.portfolio_value, { lakhs: true })}</strong> — reallocation only.
          </p>
        )}

        {compareChart.length > 0 && (
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={compareChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E8E2D9" />
                <XAxis dataKey="name" stroke="#737985" fontSize={11} />
                <YAxis stroke="#737985" fontSize={11} />
                <Tooltip />
                <Legend />
                {result?.scenario_type === 'sip_contribution' && (
                  <Bar dataKey="value" name="Projected value" fill="#333A73" />
                )}
                {result?.scenario_type === 'allocation_change' && (
                  <>
                    <Bar dataKey="current" name="Current %" fill="#9db8a3" />
                    <Bar dataKey="scenario" name="Scenario %" fill="#333A73" />
                  </>
                )}
                {result?.scenario_type === 'market_movement' && (
                  <>
                    <Bar dataKey="baseline" name="Baseline value" fill="#9db8a3" />
                    <Bar dataKey="scenario" name="Scenario value" fill="#333A73" />
                  </>
                )}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      <aside className="panel ws-sim-meta">
        <h2>Assumptions & limitations</h2>
        {(result?.assumptions || []).map((a: string) => (
          <p key={a} className="muted">
            {a}
          </p>
        ))}
        {result?.formula && (
          <p>
            <strong>Formula:</strong> {result.formula}
          </p>
        )}
        <EvidenceBadge evidence={result?.evidence} />
        {!result && (
          <p className="muted">
            Allocation ≠ market price change. SIP projections ≠ guaranteed outcomes. Transaction CSV
            is never used for investment returns.
          </p>
        )}
      </aside>
    </div>
  );
}
