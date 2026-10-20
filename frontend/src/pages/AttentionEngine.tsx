import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { ConfidencePill, EvidenceBadge } from '../components/EvidenceBadge';
import { PriorityPill } from '../components/PriorityPill';
import { NextReviewAction } from '../components/NextReviewAction';
import { formatPct } from '../clientWorkspace/format';

type Segment = 'all' | 'less_observed';
type KpiKey = 'critical' | 'high' | 'needs_review' | 'overdue_followups' | null;
type SortKey = 'score' | 'priority' | 'days_since_review' | 'goal' | 'overdue';

const PAGE_SIZE = 25;
const PRIORITY_RANK: Record<string, number> = {
  Critical: 4,
  High: 3,
  Monitor: 2,
  'On Track': 1,
};

function daysLabel(days: number | undefined) {
  if (days === undefined || days === null || Number.isNaN(Number(days))) return 'N/A';
  const d = Number(days);
  if (d >= 999) return 'Unknown';
  return `${d}d ago`;
}

export default function AttentionEngine() {
  const [payload, setPayload] = useState<any>(null);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState('');
  const [toast, setToast] = useState('');
  const [showHelp, setShowHelp] = useState(false);

  const [segment, setSegment] = useState<Segment>('all');
  const [kpiFilter, setKpiFilter] = useState<KpiKey>(null);
  const [search, setSearch] = useState('');
  const [priority, setPriority] = useState('');
  const [tier, setTier] = useState('');
  const [confidence, setConfidence] = useState('');
  const [followUp, setFollowUp] = useState('');
  const [reviewStatus, setReviewStatus] = useState('active');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setErr('');
    try {
      const data = await api.attentionEngine();
      setPayload(data);
    } catch (e) {
      setErr(String(e));
      setPayload(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const baseList: any[] = useMemo(() => {
    if (!payload) return [];
    return segment === 'less_observed' ? payload.less_observed_clients || [] : payload.clients || [];
  }, [payload, segment]);

  const filtered = useMemo(() => {
    let rows = [...baseList];
    const q = search.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (c) =>
          String(c.display_name || '')
            .toLowerCase()
            .includes(q) ||
          String(c.investor_id || '')
            .toLowerCase()
            .includes(q),
      );
    }
    if (priority) rows = rows.filter((c) => c.priority === priority);
    if (tier) rows = rows.filter((c) => c.tier === tier);
    if (confidence) rows = rows.filter((c) => c.confidence === confidence);
    if (followUp === 'overdue') rows = rows.filter((c) => c.has_overdue_followup);
    if (followUp === 'none') rows = rows.filter((c) => !c.has_overdue_followup);
    if (reviewStatus === 'active') rows = rows.filter((c) => !c.resolved);
    if (reviewStatus === 'resolved') rows = rows.filter((c) => c.resolved);

    if (kpiFilter === 'critical') rows = rows.filter((c) => !c.resolved && c.priority === 'Critical');
    if (kpiFilter === 'high') rows = rows.filter((c) => !c.resolved && c.priority === 'High');
    if (kpiFilter === 'needs_review') rows = rows.filter((c) => c.needs_review);
    if (kpiFilter === 'overdue_followups') {
      rows = rows.filter((c) => !c.resolved && c.has_overdue_followup);
    }

    rows.sort((a, b) => {
      if (sortKey === 'priority') {
        return (PRIORITY_RANK[b.priority] || 0) - (PRIORITY_RANK[a.priority] || 0);
      }
      if (sortKey === 'days_since_review') {
        return (b.days_since_review || 0) - (a.days_since_review || 0);
      }
      if (sortKey === 'goal') {
        return (
          (a.goal_status?.deviation_pct_vs_expected ?? 0) -
          (b.goal_status?.deviation_pct_vs_expected ?? 0)
        );
      }
      if (sortKey === 'overdue') {
        return (b.overdue_followups_count || 0) - (a.overdue_followups_count || 0);
      }
      // score / default — preserve queue_score when present
      return (b.queue_score ?? b.score ?? 0) - (a.queue_score ?? a.score ?? 0);
    });
    return rows;
  }, [
    baseList,
    search,
    priority,
    tier,
    confidence,
    followUp,
    reviewStatus,
    kpiFilter,
    sortKey,
  ]);

  useEffect(() => {
    setPage(0);
  }, [segment, search, priority, tier, confidence, followUp, reviewStatus, kpiFilter, sortKey]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageRows = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);
  const selected = useMemo(
    () => filtered.find((c) => c.investor_id === selectedId) || null,
    [filtered, selectedId],
  );

  const clearFilters = () => {
    setKpiFilter(null);
    setSearch('');
    setPriority('');
    setTier('');
    setConfidence('');
    setFollowUp('');
    setReviewStatus('active');
    setSortKey('score');
  };

  const decide = async (id: string, action: string) => {
    setBusyId(id);
    setToast('');
    try {
      await api.attentionDecision(id, action);
      setToast(
        action === 'reviewed'
          ? 'Marked reviewed'
          : action === 'follow_up'
            ? 'Follow-up recorded'
            : action === 'dismiss'
              ? 'Dismissed (evidence retained)'
              : 'Updated',
      );
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusyId('');
    }
  };

  const kpis = payload?.kpis || { critical: 0, high: 0, needs_review: 0, overdue_followups: 0 };

  if (loading && !payload) return <div className="loading">Loading Attention Engine…</div>;
  if (err && !payload) return <div className="error">{err}</div>;
  if (!payload) return <div className="error">Attention Engine unavailable.</div>;

  return (
    <div className="ae-page">
      <div className="page-top">
        <div className="page-header">
          <h1>Attention Engine</h1>
          <p>
            Identify the clients who need your attention today, understand why, and take action.
          </p>
        </div>
        <div className="filters ae-top-actions">
          <label className="search-pill">
            <svg className="search-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-3.5-3.5" />
            </svg>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name or client ID…"
              aria-label="Search clients"
            />
          </label>
          <button type="button" className="btn soft" disabled={loading} onClick={load}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
          <button type="button" className="btn ghost" onClick={() => setShowHelp((v) => !v)}>
            How scoring works
          </button>
        </div>
      </div>

      <p className="muted ae-meta">
        Last calculated: {payload.calculated_at ? new Date(payload.calculated_at).toLocaleString() : 'N/A'}{' '}
        · DEMO synthetic book · {payload.counts?.all ?? 0} clients
      </p>

      {showHelp && (
        <div className="panel ae-help">
          <h3>How prioritization works</h3>
          <p className="muted">{payload.methodology}</p>
          <ul>
            {(payload.less_observed_definition?.rules || []).map((r: string) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p className="muted">
            Severity (Critical / High / Monitor / On Track) is separate from evidence confidence
            (Verified / Limited / Insufficient).
          </p>
        </div>
      )}

      {err && <div className="error">{err}</div>}
      {toast && <div className="mi-gemini-banner ok">{toast}</div>}

      <div className="grid-kpi ae-kpis">
        {(
          [
            ['critical', 'Critical', kpis.critical, 'peach'],
            ['high', 'High Priority', kpis.high, 'lavender'],
            ['needs_review', 'Needs Review', kpis.needs_review, 'sage'],
            ['overdue_followups', 'Overdue Follow-ups', kpis.overdue_followups, 'peach'],
          ] as const
        ).map(([key, label, value, tone]) => (
          <button
            key={key}
            type="button"
            className={`kpi ${tone} ae-kpi-btn ${kpiFilter === key ? 'active' : ''}`}
            onClick={() => setKpiFilter(kpiFilter === key ? null : key)}
          >
            <div className="label">{label}</div>
            <div className="value">{value}</div>
            <div className="delta">{kpiFilter === key ? 'Filter on' : 'Click to filter'}</div>
          </button>
        ))}
      </div>

      <div className="ae-segment" role="tablist" aria-label="Attention segment">
        <button
          type="button"
          role="tab"
          aria-selected={segment === 'all'}
          className={`ae-seg-btn ${segment === 'all' ? 'active' : ''}`}
          onClick={() => setSegment('all')}
        >
          All Clients
          <span className="muted">({payload.counts?.all ?? 0})</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={segment === 'less_observed'}
          className={`ae-seg-btn ${segment === 'less_observed' ? 'active' : ''}`}
          onClick={() => setSegment('less_observed')}
        >
          Less-Observed Clients
          <span className="muted">({payload.counts?.less_observed ?? 0})</span>
        </button>
      </div>
      {segment === 'less_observed' && (
        <p className="muted ae-seg-note">
          {payload.less_observed_definition?.label ||
            'Clients with limited recent review activity, ranked by attention priority.'}
          {payload.hero && (
            <>
              {' '}
              Overlooked DEMO case:{' '}
              <button
                type="button"
                className="linkish"
                onClick={() => {
                  setSelectedId(payload.hero.investor_id);
                  setSearch(payload.hero.display_name);
                }}
              >
                {payload.hero.display_name}
              </button>
            </>
          )}
        </p>
      )}

      <div className="panel ae-list-panel">
        <div className="panel-head">
          <h2>Client attention list</h2>
          <span className="muted">
            {filtered.length} shown · page {page + 1}/{pageCount}
          </span>
        </div>

        <div className="filters ae-filters">
          <select value={priority} onChange={(e) => setPriority(e.target.value)} aria-label="Priority">
            <option value="">All priorities</option>
            <option>Critical</option>
            <option>High</option>
            <option>Monitor</option>
            <option>On Track</option>
          </select>
          <select value={tier} onChange={(e) => setTier(e.target.value)} aria-label="Tier">
            <option value="">All tiers</option>
            <option value="high_visibility">High-visibility</option>
            <option value="long_tail">Long-tail</option>
          </select>
          <select
            value={confidence}
            onChange={(e) => setConfidence(e.target.value)}
            aria-label="Confidence"
          >
            <option value="">All confidence</option>
            <option>Verified</option>
            <option>Limited</option>
            <option>Insufficient</option>
          </select>
          <select value={followUp} onChange={(e) => setFollowUp(e.target.value)} aria-label="Follow-up">
            <option value="">Follow-up: any</option>
            <option value="overdue">Overdue</option>
            <option value="none">None overdue</option>
          </select>
          <select
            value={reviewStatus}
            onChange={(e) => setReviewStatus(e.target.value)}
            aria-label="Review status"
          >
            <option value="active">Active (not resolved)</option>
            <option value="resolved">Resolved / dismissed</option>
            <option value="all">All statuses</option>
          </select>
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            aria-label="Sort by"
          >
            <option value="score">Sort: attention score</option>
            <option value="priority">Sort: severity</option>
            <option value="days_since_review">Sort: time since review</option>
            <option value="goal">Sort: goal deviation</option>
            <option value="overdue">Sort: overdue follow-ups</option>
          </select>
          <button type="button" className="btn ghost" onClick={clearFilters}>
            Clear filters
          </button>
        </div>

        <div className="ae-layout">
          <div className="ae-table-wrap">
            <table className="ae-table">
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Priority</th>
                  <th>Score</th>
                  <th>Main reason</th>
                  <th>Goal</th>
                  <th>Last review</th>
                  <th>Follow-up</th>
                  <th>Confidence</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((c) => (
                  <tr
                    key={c.investor_id}
                    className={`${selectedId === c.investor_id ? 'row-active' : ''} ${
                      c.is_blind_spot_hero ? 'ae-hero-row' : ''
                    }`}
                  >
                    <td>
                      <button
                        type="button"
                        className="linkish ae-client-btn"
                        onClick={() => setSelectedId(c.investor_id)}
                      >
                        <strong>{c.display_name}</strong>
                        <span className="muted">
                          {c.investor_id} · {c.tier}
                          {c.is_demo ? ' · DEMO' : ''}
                        </span>
                      </button>
                      {segment === 'less_observed' && c.less_observed_reason && (
                        <div className="ae-less-tag">{c.less_observed_reason}</div>
                      )}
                    </td>
                    <td>
                      <PriorityPill priority={c.priority} />
                    </td>
                    <td className="ae-score">{c.score}</td>
                    <td className="ae-reason">{c.main_reason}</td>
                    <td>
                      {c.goal_status ? (
                        <>
                          <div>{formatPct(c.goal_status.deviation_pct_vs_expected)}</div>
                          <div className="muted">{c.goal_status.goal_name}</div>
                        </>
                      ) : (
                        'N/A'
                      )}
                    </td>
                    <td>{daysLabel(c.days_since_review)}</td>
                    <td>
                      {c.has_overdue_followup ? (
                        <span className="ae-overdue">{c.overdue_followups_count} overdue</span>
                      ) : (
                        <span className="muted">None</span>
                      )}
                    </td>
                    <td>
                      <ConfidencePill confidence={c.confidence} />
                    </td>
                    <td>
                      <div className="ae-row-actions">
                        <button
                          type="button"
                          className="linkish"
                          onClick={() => setSelectedId(c.investor_id)}
                        >
                          Details
                        </button>
                        <Link className="linkish" to={`/clients/${c.investor_id}/overview`}>
                          Profile
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!pageRows.length && (
              <p className="muted ae-empty">No clients match the current filters.</p>
            )}
            <div className="filters ae-pager">
              <button
                type="button"
                className="btn ghost"
                disabled={page <= 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn ghost"
                disabled={page >= pageCount - 1}
                onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
              >
                Next
              </button>
            </div>
          </div>

          <aside className="ae-drawer panel">
            {!selected && (
              <p className="muted">Select a client row to inspect why they need attention.</p>
            )}
            {selected && (
              <>
                <div className="panel-head">
                  <h2>{selected.display_name}</h2>
                  <PriorityPill priority={selected.priority} />
                </div>
                <p className="muted">
                  {selected.investor_id} · score {selected.score} ·{' '}
                  <ConfidencePill confidence={selected.confidence} />
                </p>

                <section className="ae-drawer-sec">
                  <h3>1. Why this client needs attention</h3>
                  <ul>
                    {(selected.why_now || [selected.main_reason]).map((r: string) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                  {selected.less_observed_reason && (
                    <p className="ae-less-tag">{selected.less_observed_reason}</p>
                  )}
                </section>

                <section className="ae-drawer-sec">
                  <h3>2. Priority breakdown</h3>
                  <ul className="factor-list">
                    {(selected.factors || []).map((f: any) => (
                      <li key={`${f.name}-${f.detail}`}>
                        <span>
                          {f.name}
                          <div className="muted">{f.detail}</div>
                          {f.is_data_quality && (
                            <div className="muted">Data-quality factor (not financial distress)</div>
                          )}
                        </span>
                        <span className="pts">{f.points}</span>
                      </li>
                    ))}
                  </ul>
                </section>

                <section className="ae-drawer-sec">
                  <h3>3. Financial and goal context</h3>
                  {selected.goal_status ? (
                    <ul>
                      <li>
                        Goal: <strong>{selected.goal_status.goal_name}</strong>
                      </li>
                      <li>
                        Deviation vs expected:{' '}
                        <strong>{formatPct(selected.goal_status.deviation_pct_vs_expected)}</strong>
                      </li>
                      <li>
                        Progress to target:{' '}
                        <strong>{formatPct(selected.goal_status.progress_to_target_pct)}</strong>
                      </li>
                      <li>Last review: {daysLabel(selected.days_since_review)}</li>
                      <li>
                        Overdue follow-ups: {selected.overdue_followups_count || 0}
                      </li>
                    </ul>
                  ) : (
                    <p className="muted">Goal context unavailable.</p>
                  )}
                </section>

                <section className="ae-drawer-sec">
                  <h3>4. Evidence and confidence</h3>
                  <EvidenceBadge evidence={selected.evidence} />
                </section>

                <section className="ae-drawer-sec">
                  <h3>5. Recommended review action</h3>
                  <p>{selected.recommended_action_stub}</p>
                  <NextReviewAction
                    investorId={selected.investor_id}
                    compact
                    onDecided={load}
                  />
                </section>

                <section className="ae-drawer-sec">
                  <h3>6. Actions</h3>
                  <div className="filters">
                    <button
                      type="button"
                      className="btn"
                      disabled={busyId === selected.investor_id}
                      onClick={() => decide(selected.investor_id, 'reviewed')}
                    >
                      Mark Reviewed
                    </button>
                    <button
                      type="button"
                      className="btn soft"
                      disabled={busyId === selected.investor_id}
                      onClick={() => decide(selected.investor_id, 'follow_up')}
                    >
                      Create Follow-up
                    </button>
                    <button
                      type="button"
                      className="btn ghost"
                      disabled={busyId === selected.investor_id}
                      onClick={() => decide(selected.investor_id, 'dismiss')}
                    >
                      Dismiss
                    </button>
                    <Link className="btn" to={`/clients/${selected.investor_id}/overview`}>
                      View Full Client Profile
                    </Link>
                  </div>
                </section>
              </>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}
