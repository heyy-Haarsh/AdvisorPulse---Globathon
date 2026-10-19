import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ConfidencePill, EvidenceBadge } from '../../components/EvidenceBadge';
import { EVIDENCE_CATEGORY_MAP } from '../format';

type Props = {
  investorId: string;
  data: any;
};

export function EvidenceTab({ investorId, data }: Props) {
  const parts: any[] = data.structured_summary?.parts || [];
  const categories = useMemo(() => {
    return EVIDENCE_CATEGORY_MAP.map((cat) => {
      const part = parts.find((p) => cat.match.includes(p.id)) || null;
      return { ...cat, part };
    });
  }, [parts]);

  const [selected, setSelected] = useState(categories[0]?.id || 'identity');
  const active = categories.find((c) => c.id === selected) || categories[0];
  const part = active?.part;

  return (
    <div className="ws-evidence">
      <nav className="ws-evidence-nav panel" aria-label="Evidence categories">
        <h2>Summary categories</h2>
        <select
          className="ws-evidence-select"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          aria-label="Select category"
        >
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title}
            </option>
          ))}
        </select>
        <ul className="ws-cat-list">
          {categories.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                className={`ws-cat-btn ${selected === c.id ? 'active' : ''}`}
                onClick={() => setSelected(c.id)}
              >
                <span className="ws-cat-title">{c.title}</span>
                <span className="muted ws-cat-sum">{c.part?.summary?.slice(0, 72) || 'Not available'}</span>
                {c.part?.evidence && <ConfidencePill confidence={c.part.evidence.confidence} />}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <section className="panel ws-evidence-detail">
        {!part ? (
          <p className="muted">
            This category is not populated for the current DEMO records. No content was fabricated.
          </p>
        ) : (
          <>
            <div className="panel-head">
              <h2>{active.title}</h2>
              <ConfidencePill confidence={part.evidence?.confidence} />
            </div>
            <h3>Key conclusion</h3>
            <p>{part.summary}</p>

            {part.metrics && (
              <>
                <h3>Key metrics</h3>
                <div className="grid-kpi">
                  {Object.entries(part.metrics).map(([k, v]) => (
                    <div className="kpi" key={k}>
                      <div className="label">{k}</div>
                      <div className="value" style={{ fontSize: '1.05rem' }}>
                        {typeof v === 'number' ? v.toLocaleString('en-IN') : String(v)}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            <h3>Supporting evidence</h3>
            <EvidenceBadge evidence={part.evidence} />

            {(part.drivers || []).length > 0 && (
              <>
                <h3>Interpretation</h3>
                <ul className="factor-list">
                  {part.drivers.map((d: any, i: number) => (
                    <li key={i}>
                      <span>
                        <strong>{d.factor}</strong>
                        <div className="muted">{d.detail}</div>
                        {d.supported_by && (
                          <div className="muted">Source: {d.supported_by}</div>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            )}

            {(part.evidence?.limitations || part.evidence?.missing_data) && (
              <>
                <h3>Limitations and missing information</h3>
                {part.evidence?.missing_data?.length ? (
                  <p className="warn">Missing: {part.evidence.missing_data.join(', ')}</p>
                ) : null}
                {part.evidence?.limitations?.length ? (
                  <p className="muted">{part.evidence.limitations.join(' ')}</p>
                ) : null}
              </>
            )}

            <h3>Related actions</h3>
            <div className="filters">
              <Link className="btn soft" to={`/clients/${investorId}/portfolio`}>
                Portfolio & Drift
              </Link>
              <Link className="btn soft" to={`/clients/${investorId}/meetings`}>
                Meetings & Advice
              </Link>
              <Link className="btn soft" to={`/clients/${investorId}/review-actions`}>
                Review Actions
              </Link>
              <Link className="btn soft" to={`/clients/${investorId}/simulator`}>
                What-if Simulator
              </Link>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
