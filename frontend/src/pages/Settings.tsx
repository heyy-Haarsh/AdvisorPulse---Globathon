import { useEffect, useState } from 'react';
import { api } from '../api';

export default function Settings() {
  const [settings, setSettings] = useState<any>(null);
  const [audit, setAudit] = useState<any[]>([]);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  const load = () => {
    api
      .settings()
      .then(setSettings)
      .catch((e) => setErr(String(e)));
    api.audit().then((r) => setAudit(r.entries || []));
  };

  useEffect(() => {
    load();
  }, []);

  const save = async () => {
    setMsg('');
    try {
      const saved = await api.saveSettings({
        weights: settings.weights,
        goal_deviation_critical_pct: Number(settings.goal_deviation_critical_pct),
        goal_deviation_high_pct: Number(settings.goal_deviation_high_pct),
        active_return_high_pp: Number(settings.active_return_high_pp),
        stale_data_days: Number(settings.stale_data_days),
        stale_review_days: Number(settings.stale_review_days),
        note_retention_days: Number(settings.note_retention_days),
      });
      setSettings(saved);
      setMsg('Settings saved. Attention scores will refresh on next load.');
    } catch (e) {
      setErr(String(e));
    }
  };

  if (err && !settings) return <div className="error">{err}</div>;
  if (!settings) return <div className="loading">Loading settings…</div>;

  const w = settings.weights || {};

  return (
    <div>
      <div className="page-top">
        <div className="page-header">
          <h1>Settings</h1>
          <p>Data sources, privacy posture, attention weights, and retention — demo configuration.</p>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <h2>Attention weights</h2>
          <p className="muted">Must remain explainable. Changes are audited.</p>
          {Object.keys(w).map((k) => (
            <label key={k} className="setting-row">
              <span>{k}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={w[k]}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    weights: { ...w, [k]: Number(e.target.value) },
                  })
                }
              />
            </label>
          ))}
          <label className="setting-row">
            <span>Goal critical %</span>
            <input
              type="number"
              value={settings.goal_deviation_critical_pct}
              onChange={(e) =>
                setSettings({ ...settings, goal_deviation_critical_pct: e.target.value })
              }
            />
          </label>
          <label className="setting-row">
            <span>Goal high %</span>
            <input
              type="number"
              value={settings.goal_deviation_high_pct}
              onChange={(e) =>
                setSettings({ ...settings, goal_deviation_high_pct: e.target.value })
              }
            />
          </label>
          <label className="setting-row">
            <span>Stale data days</span>
            <input
              type="number"
              value={settings.stale_data_days}
              onChange={(e) => setSettings({ ...settings, stale_data_days: e.target.value })}
            />
          </label>
          <label className="setting-row">
            <span>Note retention days</span>
            <input
              type="number"
              value={settings.note_retention_days}
              onChange={(e) => setSettings({ ...settings, note_retention_days: e.target.value })}
            />
          </label>
          <button type="button" className="btn" onClick={save}>
            Save
          </button>
          {msg && <p className="muted">{msg}</p>}
        </div>

        <div className="panel">
          <h2>Privacy & data sources</h2>
          <ul className="factor-list">
            <li>
              <span>
                Demo auth
                <div className="muted">{settings.privacy?.demo_auth_note}</div>
              </span>
            </li>
            <li>
              <span>
                Transcription mode
                <div className="muted">{settings.privacy?.transcription_mode} — mocked/local only</div>
              </span>
            </li>
            <li>
              <span>
                PII in logs
                <div className="muted">{settings.privacy?.log_pii ? 'enabled' : 'disabled (recommended)'}</div>
              </span>
            </li>
            <li>
              <span>
                Portfolio data
                <div className="muted">data/synthetic_*.csv — labeled is_demo=true</div>
              </span>
            </li>
            <li>
              <span>
                Transactions
                <div className="muted">
                  data/sample_transactions.csv — cash-flow layer only, never investment returns
                </div>
              </span>
            </li>
          </ul>
        </div>
      </div>

      <div className="panel">
        <h2>Audit log (no PII payloads)</h2>
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Action</th>
              <th>Meta</th>
            </tr>
          </thead>
          <tbody>
            {audit
              .slice()
              .reverse()
              .slice(0, 30)
              .map((e, i) => (
                <tr key={i}>
                  <td className="muted">{String(e.ts).slice(0, 19)}</td>
                  <td>{e.action}</td>
                  <td className="muted">{JSON.stringify(e.meta)}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
