import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, type ClientPriority } from '../api';
import { ConfidencePill, EvidenceBadge } from '../components/EvidenceBadge';
import { PriorityPill } from '../components/PriorityPill';
import { formatInr } from '../clientWorkspace/format';

type Stage = 'prepare' | 'live' | 'minutes' | 'history';

const MEETING_TYPES = [
  'portfolio_review',
  'goal_planning',
  'risk_profile_review',
  'investment_advice_follow_up',
  'sip_contribution_review',
  'financial_milestone',
  'general_client_review',
];

export default function MeetingIntelligence() {
  const { clientId, meetingId, stage: stageParam } = useParams();
  const navigate = useNavigate();
  const stage = (stageParam as Stage) || (meetingId ? 'prepare' : 'history');

  const [clients, setClients] = useState<ClientPriority[]>([]);
  const [selectedClient, setSelectedClient] = useState(clientId || 'DEMO-INV-001');
  const [gemini, setGemini] = useState<any>(null);
  const [meetings, setMeetings] = useState<any[]>([]);
  const [meeting, setMeeting] = useState<any>(null);
  const [brief, setBrief] = useState<any>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [pasteText, setPasteText] = useState('');
  const [noteText, setNoteText] = useState('');
  const [noteCat, setNoteCat] = useState('decision');
  const [elapsed, setElapsed] = useState(0);
  const [form, setForm] = useState({
    title: '',
    meeting_type: 'portfolio_review',
    channel: 'online',
    purpose: 'Quarterly portfolio review',
    expected_duration_min: 45,
  });

  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);

  const refreshList = async (iid?: string) => {
    const r = await api.meetingIntelList(iid || selectedClient);
    setMeetings(r.meetings || []);
    setGemini(r.gemini);
  };

  const loadMeeting = async (mid: string) => {
    const m = await api.meetingIntelGet(mid);
    setMeeting(m);
    return m;
  };

  useEffect(() => {
    api.clients({ limit: '80' }).then((r) => setClients(r.clients));
    api.meetingIntelStatus().then(setGemini).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (clientId) setSelectedClient(clientId);
  }, [clientId]);

  useEffect(() => {
    refreshList(selectedClient).catch((e) => setErr(String(e)));
  }, [selectedClient]);

  useEffect(() => {
    if (meetingId) {
      loadMeeting(meetingId)
        .then(async (m) => {
          if (stage === 'prepare' || !m.prep_brief) {
            try {
              const b = await api.meetingIntelPrepare(meetingId);
              setBrief(b);
            } catch {
              /* brief optional until created */
            }
          } else {
            setBrief(null);
          }
        })
        .catch((e) => setErr(String(e)));
    } else {
      setMeeting(null);
      setBrief(null);
    }
  }, [meetingId, stage]);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      if (mediaRef.current && mediaRef.current.state !== 'inactive') {
        try {
          mediaRef.current.stop();
        } catch {
          /* ignore */
        }
      }
    };
  }, []);

  const go = (s: Stage, mid?: string, cid?: string) => {
    const c = cid || selectedClient;
    const m = mid || meetingId;
    if (s === 'history') navigate(`/meeting-intel/${c}/history`);
    else if (m) navigate(`/meeting-intel/${c}/${m}/${s}`);
    else navigate(`/meeting-intel/${c}/history`);
  };

  const createMeeting = async () => {
    setBusy(true);
    setErr('');
    try {
      const m = await api.meetingIntelCreate({
        investor_id: selectedClient,
        ...form,
        title: form.title || undefined,
      });
      const b = await api.meetingIntelPrepare(m.meeting_id);
      setBrief(b);
      setMeeting(m);
      await refreshList();
      navigate(`/meeting-intel/${selectedClient}/${m.meeting_id}/prepare`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const saveAgenda = async (agenda: string[]) => {
    if (!meetingId) return;
    const m = await api.meetingIntelPatch(meetingId, { agenda });
    setMeeting(m);
  };

  const confirmConsent = async () => {
    if (!meetingId) return;
    setBusy(true);
    try {
      const m = await api.meetingIntelConsent(
        meetingId,
        'Advisor confirms required participant consent for recording under firm policy.',
      );
      setMeeting(m);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const startLive = async () => {
    if (!meetingId) return;
    setBusy(true);
    setErr('');
    try {
      const m = await api.meetingIntelStart(meetingId);
      setMeeting(m);
      go('live', meetingId);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const startBrowserRecording = async () => {
    if (!meetingId) return;
    setErr('');
    if (meeting?.consent_status !== 'confirmed') {
      setErr('Confirm consent before recording.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];
      const rec = new MediaRecorder(stream);
      mediaRef.current = rec;
      rec.ondataavailable = (ev) => {
        if (ev.data.size) chunksRef.current.push(ev.data);
      };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (timerRef.current) window.clearInterval(timerRef.current);
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' });
        setBusy(true);
        try {
          await api.meetingIntelUploadAudio(meetingId, blob, `${meetingId}.webm`);
          await api.meetingIntelRecordingState(meetingId, 'stopped');
          await loadMeeting(meetingId);
        } catch (e) {
          setErr(String(e));
        } finally {
          setBusy(false);
        }
      };
      rec.start(1000);
      setElapsed(0);
      timerRef.current = window.setInterval(() => setElapsed((s) => s + 1), 1000);
      await api.meetingIntelRecordingState(meetingId, 'recording');
      await loadMeeting(meetingId);
    } catch (e) {
      setErr(`Microphone unavailable or permission denied: ${e}`);
    }
  };

  const stopBrowserRecording = () => {
    if (mediaRef.current && mediaRef.current.state !== 'inactive') {
      mediaRef.current.stop();
    }
  };

  const pauseRecording = async () => {
    if (mediaRef.current?.state === 'recording') {
      mediaRef.current.pause();
      if (timerRef.current) window.clearInterval(timerRef.current);
      if (meetingId) {
        await api.meetingIntelRecordingState(meetingId, 'paused');
        await loadMeeting(meetingId);
      }
    }
  };

  const resumeRecording = async () => {
    if (mediaRef.current?.state === 'paused') {
      mediaRef.current.resume();
      timerRef.current = window.setInterval(() => setElapsed((s) => s + 1), 1000);
      if (meetingId) {
        await api.meetingIntelRecordingState(meetingId, 'recording');
        await loadMeeting(meetingId);
      }
    }
  };

  const onUploadFile = async (file: File | null) => {
    if (!file || !meetingId) return;
    setBusy(true);
    setErr('');
    try {
      await api.meetingIntelUploadAudio(meetingId, file, file.name);
      await loadMeeting(meetingId);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const runTranscribe = async () => {
    if (!meetingId) return;
    setBusy(true);
    setErr('');
    try {
      await api.meetingIntelTranscribe(meetingId);
      await loadMeeting(meetingId);
      go('minutes', meetingId);
    } catch (e) {
      setErr(String(e));
      await loadMeeting(meetingId);
    } finally {
      setBusy(false);
    }
  };

  const pasteTranscript = async () => {
    if (!meetingId || !pasteText.trim()) return;
    setBusy(true);
    try {
      await api.meetingIntelPasteTranscript(meetingId, pasteText.trim());
      await loadMeeting(meetingId);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const genMinutes = async () => {
    if (!meetingId) return;
    setBusy(true);
    setErr('');
    try {
      await api.meetingIntelGenerateMinutes(meetingId);
      await loadMeeting(meetingId);
      go('minutes', meetingId);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const approve = async () => {
    if (!meetingId) return;
    setBusy(true);
    try {
      await api.meetingIntelApproveMinutes(meetingId);
      await loadMeeting(meetingId);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const makeCommitments = async () => {
    if (!meetingId) return;
    setBusy(true);
    try {
      await api.meetingIntelCommitments(meetingId);
      await loadMeeting(meetingId);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const addNote = async () => {
    if (!meetingId || !noteText.trim()) return;
    const m = await api.meetingIntelNote(meetingId, { text: noteText, category: noteCat });
    setMeeting(m);
    setNoteText('');
  };

  const fmtTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  };

  return (
    <div className="mi-page">
      <div className="page-top">
        <div className="page-header">
          <h1>Meeting Intelligence</h1>
          <p>
            Prepare → record/upload → Gemini transcript → structured MoM → approve → commitments.
            AI drafts stay advisor-controlled.
          </p>
        </div>
        <div className="filters">
          <select
            value={selectedClient}
            onChange={(e) => {
              setSelectedClient(e.target.value);
              navigate(`/meeting-intel/${e.target.value}/history`);
            }}
            aria-label="Select client"
          >
            {clients.map((c) => (
              <option key={c.investor_id} value={c.investor_id}>
                {c.display_name} ({c.investor_id})
              </option>
            ))}
          </select>
          <Link className="btn soft" to={`/clients/${selectedClient}/meetings`}>
            Client workspace →
          </Link>
        </div>
      </div>

      <div className={`mi-gemini-banner ${gemini?.configured ? 'ok' : 'warn'}`}>
        Gemini: {gemini?.configured ? `configured · ${gemini.model}` : 'not configured — set GEMINI_API_KEY in .env'}
        {!gemini?.configured && (
          <span className="muted">
            {' '}
            Prep briefs still work from analytics. Transcription & minutes require the API key.
          </span>
        )}
      </div>

      {err && <div className="error">{err}</div>}

      <nav className="ws-tabs" aria-label="Meeting stages">
        {(['prepare', 'live', 'minutes', 'history'] as Stage[]).map((s) => (
          <button
            key={s}
            type="button"
            className={`ws-tab ${stage === s ? 'active' : ''}`}
            onClick={() => go(s, meetingId)}
          >
            {s === 'prepare'
              ? '1. Preparation'
              : s === 'live'
                ? '2. Live Meeting'
                : s === 'minutes'
                  ? '3. Minutes & Insights'
                  : '4. History'}
          </button>
        ))}
      </nav>

      {stage === 'history' && (
        <div className="panel">
          <div className="panel-head">
            <h2>Meeting history — {selectedClient}</h2>
            <button type="button" className="btn" onClick={() => go('prepare')}>
              Prepare Meeting
            </button>
          </div>
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th>Scheduled</th>
                <th>Status</th>
                <th>Minutes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {meetings.map((m) => (
                <tr key={m.meeting_id}>
                  <td>{m.title}</td>
                  <td className="muted">{m.meeting_type}</td>
                  <td>{m.scheduled_at?.slice?.(0, 16)}</td>
                  <td>{m.status}</td>
                  <td>{m.minutes_status}</td>
                  <td>
                    <button
                      type="button"
                      className="linkish"
                      onClick={() =>
                        navigate(`/meeting-intel/${m.investor_id}/${m.meeting_id}/prepare`)
                      }
                    >
                      Open →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!meetings.length && <p className="muted">No Meeting Intelligence records yet for this client.</p>}

          {!meetingId && (
            <div className="mi-create">
              <h3>New meeting</h3>
              <div className="filters" style={{ flexWrap: 'wrap' }}>
                <input
                  placeholder="Title (optional)"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                />
                <select
                  value={form.meeting_type}
                  onChange={(e) => setForm({ ...form, meeting_type: e.target.value })}
                >
                  {MEETING_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                <select
                  value={form.channel}
                  onChange={(e) => setForm({ ...form, channel: e.target.value })}
                >
                  <option value="online">online</option>
                  <option value="phone">phone</option>
                  <option value="in_person">in-person</option>
                </select>
                <input
                  placeholder="Purpose"
                  value={form.purpose}
                  onChange={(e) => setForm({ ...form, purpose: e.target.value })}
                  style={{ minWidth: 220 }}
                />
                <button type="button" className="btn" disabled={busy} onClick={createMeeting}>
                  {busy ? 'Creating…' : 'Prepare Meeting'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {stage === 'prepare' && (
        <div className="mi-prepare">
          {!meetingId && (
            <div className="panel">
              <h2>Prepare a meeting</h2>
              <p className="muted">Create a meeting from History, or use the form below.</p>
              <div className="filters">
                <button type="button" className="btn" disabled={busy} onClick={createMeeting}>
                  Prepare Meeting for {selectedClient}
                </button>
                <button type="button" className="btn ghost" onClick={() => go('history')}>
                  View history
                </button>
              </div>
            </div>
          )}

          {meeting && (
            <>
              <div className="panel">
                <div className="panel-head">
                  <h2>{meeting.title}</h2>
                  <span className="muted">
                    {meeting.meeting_id} · {meeting.status}
                  </span>
                </div>
                <p className="muted">
                  {meeting.display_name} · {meeting.meeting_type} · {meeting.channel}
                </p>
                <div className="filters">
                  <button
                    type="button"
                    className="btn soft"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        setBrief(await api.meetingIntelPrepare(meeting.meeting_id, true));
                      } catch (e) {
                        setErr(String(e));
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Regenerate brief
                  </button>
                  {meeting.consent_status !== 'confirmed' ? (
                    <button type="button" className="btn" disabled={busy} onClick={confirmConsent}>
                      Confirm recording consent
                    </button>
                  ) : (
                    <span className="pill conf Verified">Consent confirmed</span>
                  )}
                  <button
                    type="button"
                    className="btn"
                    disabled={busy || meeting.consent_status !== 'confirmed'}
                    onClick={startLive}
                  >
                    Start Meeting
                  </button>
                </div>
              </div>

              {brief && (
                <div className="ws-overview">
                  <div className="ws-overview-main">
                    <section className="panel">
                      <h2>Client snapshot</h2>
                      <p>
                        <strong>{brief.client_snapshot?.display_name}</strong>{' '}
                        <PriorityPill priority={brief.client_snapshot?.priority} />
                      </p>
                      <div className="grid-kpi">
                        <div className="kpi">
                          <div className="label">Portfolio</div>
                          <div className="value" style={{ fontSize: '1.1rem' }}>
                            {formatInr(brief.client_snapshot?.portfolio_value, { lakhs: true })}
                          </div>
                        </div>
                        <div className="kpi">
                          <div className="label">Goal</div>
                          <div className="value" style={{ fontSize: '1rem' }}>
                            {brief.client_snapshot?.goal || 'N/A'}
                          </div>
                        </div>
                        <div className="kpi">
                          <div className="label">Open commitments</div>
                          <div className="value" style={{ fontSize: '1.1rem' }}>
                            {brief.client_snapshot?.open_commitments_count ?? 0}
                          </div>
                        </div>
                      </div>
                      <EvidenceBadge evidence={brief.evidence} />
                    </section>

                    <section className="panel">
                      <h2>Previous meeting recap</h2>
                      {!brief.previous_meeting_recap ? (
                        <p className="muted">No prior Meeting Intelligence record — nothing invented.</p>
                      ) : (
                        <>
                          <p>
                            <strong>{brief.previous_meeting_recap.title}</strong>{' '}
                            <span className="muted">{brief.previous_meeting_recap.date}</span>
                          </p>
                          <ul>
                            {(brief.previous_meeting_recap.executive_summary || []).map((b: string) => (
                              <li key={b}>{b}</li>
                            ))}
                          </ul>
                        </>
                      )}
                    </section>

                    <section className="panel">
                      <h2>Portfolio & goal changes</h2>
                      {(brief.portfolio_and_goal_changes || []).map((c: any, i: number) => (
                        <div key={i} className="ws-alert-mini">
                          <strong>{c.title}</strong>
                          <div className="muted">{c.detail}</div>
                        </div>
                      ))}
                      {!brief.portfolio_and_goal_changes?.length && (
                        <p className="muted">No material changes flagged.</p>
                      )}
                    </section>

                    <section className="panel">
                      <h2>Priority discussion topics</h2>
                      {(brief.priority_topics || []).map((t: any, i: number) => (
                        <div key={i} className="ws-alert-mini">
                          <strong>{t.title}</strong> · {t.priority}{' '}
                          <ConfidencePill confidence={t.evidence_status} />
                          <div className="muted">{t.why_it_matters}</div>
                          <div>Q: {t.suggested_question}</div>
                        </div>
                      ))}
                    </section>
                  </div>

                  <aside className="ws-overview-side">
                    <section className="panel">
                      <h2>Suggested agenda</h2>
                      <ol>
                        {(meeting.agenda || brief.suggested_agenda || []).map((a: string, i: number) => (
                          <li key={i}>
                            <input
                              value={a}
                              onChange={(e) => {
                                const next = [...(meeting.agenda || brief.suggested_agenda)];
                                next[i] = e.target.value;
                                setMeeting({ ...meeting, agenda: next });
                              }}
                              onBlur={() => saveAgenda(meeting.agenda || [])}
                              style={{ width: '100%' }}
                            />
                          </li>
                        ))}
                      </ol>
                      <button
                        type="button"
                        className="btn ghost"
                        onClick={() => {
                          const next = [...(meeting.agenda || []), 'New agenda item'];
                          setMeeting({ ...meeting, agenda: next });
                          saveAgenda(next);
                        }}
                      >
                        Add item
                      </button>
                    </section>

                    <section className="panel">
                      <h2>Questions to ask</h2>
                      <ul>
                        {(brief.questions_to_ask || []).map((q: string) => (
                          <li key={q}>{q}</li>
                        ))}
                      </ul>
                    </section>

                    <section className="panel">
                      <h2>Pending commitments</h2>
                      {(brief.pending_commitments || []).slice(0, 6).map((c: any) => (
                        <div key={c.id} className="ws-commit-row">
                          <strong>{c.action}</strong>
                          <div className="muted">{c.status}</div>
                        </div>
                      ))}
                      {!brief.pending_commitments?.length && (
                        <p className="muted">None open.</p>
                      )}
                    </section>

                    <section className="panel">
                      <h2>Checklist</h2>
                      {(meeting.checklist || brief.checklist || []).map((c: any) => (
                        <label key={c.id} className="muted" style={{ display: 'flex', gap: 8 }}>
                          <input
                            type="checkbox"
                            checked={!!c.done}
                            onChange={async (e) => {
                              const next = (meeting.checklist || []).map((x: any) =>
                                x.id === c.id ? { ...x, done: e.target.checked } : x,
                              );
                              const m = await api.meetingIntelPatch(meeting.meeting_id, {
                                checklist: next,
                              });
                              setMeeting(m);
                            }}
                          />
                          {c.label}
                        </label>
                      ))}
                    </section>
                  </aside>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {stage === 'live' && meeting && (
        <div className="ws-overview">
          <div className="ws-overview-main">
            <section className="panel">
              <h2>Agenda</h2>
              <ol>
                {(meeting.agenda || []).map((a: string, i: number) => (
                  <li key={i}>{a}</li>
                ))}
              </ol>
            </section>
            <section className="panel">
              <h2>Quick advisor notes</h2>
              <div className="filters">
                <select value={noteCat} onChange={(e) => setNoteCat(e.target.value)}>
                  <option value="client_concern">Client concern</option>
                  <option value="financial_change">Financial change</option>
                  <option value="client_preference">Client preference</option>
                  <option value="advice_discussed">Advice discussed</option>
                  <option value="decision">Decision</option>
                  <option value="follow_up">Follow-up</option>
                  <option value="question">Question</option>
                </select>
                <input
                  style={{ flex: 1 }}
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Timestamped note…"
                />
                <button type="button" className="btn" onClick={addNote}>
                  Add
                </button>
              </div>
              <ul className="timeline">
                {(meeting.live_notes || []).map((n: any) => (
                  <li key={n.note_id}>
                    <span className="muted">{n.category}</span> — {n.text}
                  </li>
                ))}
              </ul>
            </section>
          </div>
          <aside className="ws-overview-side">
            <section className="panel mi-rec-panel">
              <h2>Recording</h2>
              <p>
                Status: <strong>{meeting.recording_status}</strong>
                {meeting.recording_status === 'recording' && (
                  <span className="mi-rec-dot"> ● REC {fmtTime(elapsed)}</span>
                )}
              </p>
              <p className="muted">
                Consent: {meeting.consent_status}. Browser capture uses microphone only — not Zoom/Teams
                audio unless you share that device.
              </p>
              <div className="filters">
                <button type="button" className="btn" disabled={busy} onClick={startBrowserRecording}>
                  Start Recording
                </button>
                <button type="button" className="btn ghost" onClick={pauseRecording}>
                  Pause
                </button>
                <button type="button" className="btn ghost" onClick={resumeRecording}>
                  Resume
                </button>
                <button type="button" className="btn" onClick={stopBrowserRecording}>
                  Stop & upload
                </button>
              </div>
              <label className="btn soft" style={{ marginTop: 8, display: 'inline-block' }}>
                Upload audio
                <input
                  type="file"
                  accept="audio/*,.webm,.wav,.mp3,.m4a"
                  style={{ display: 'none' }}
                  onChange={(e) => onUploadFile(e.target.files?.[0] || null)}
                />
              </label>
              <div className="filters" style={{ marginTop: 12 }}>
                <button type="button" className="btn" disabled={busy} onClick={runTranscribe}>
                  Transcribe with Gemini
                </button>
                <button
                  type="button"
                  className="btn ghost"
                  onClick={async () => {
                    await api.meetingIntelEnd(meeting.meeting_id);
                    go('minutes', meeting.meeting_id);
                  }}
                >
                  End Meeting
                </button>
              </div>
              <h3>Or paste advisor transcript</h3>
              <p className="muted">Use only real notes — never fabricated content.</p>
              <textarea
                rows={5}
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                style={{ width: '100%' }}
                placeholder="Paste actual meeting notes / transcript…"
              />
              <button type="button" className="btn soft" disabled={busy} onClick={pasteTranscript}>
                Save pasted transcript
              </button>
            </section>
          </aside>
        </div>
      )}

      {stage === 'minutes' && meeting && (
        <div className="mi-minutes">
          <div className="panel">
            <div className="panel-head">
              <h2>Transcript & Minutes</h2>
              <span className="muted">
                transcript: {meeting.transcript_status} · minutes: {meeting.minutes_status}
              </span>
            </div>
            {!meeting.transcript?.full_text && (
              <p className="warn">
                No transcript yet. Record/upload + Gemini transcribe, or paste advisor-provided text on
                Live Meeting.
              </p>
            )}
            {(meeting.transcript?.segments || []).length > 0 && (
              <div className="mi-transcript">
                <h3>Segments</h3>
                {(meeting.transcript.segments as any[]).map((s) => (
                  <div key={s.segment_id} className="mi-seg">
                    <span className="muted">
                      [{s.start_time}] {s.speaker_id} · {s.segment_id}
                    </span>
                    <div>{s.text}</div>
                  </div>
                ))}
              </div>
            )}
            <div className="filters">
              <button
                type="button"
                className="btn"
                disabled={busy || meeting.transcript_status !== 'ready'}
                onClick={genMinutes}
              >
                {busy ? 'Generating…' : 'Generate Meeting Minutes (Gemini)'}
              </button>
              {meeting.minutes_status === 'ready_for_review' || meeting.minutes_status === 'draft' ? (
                <button type="button" className="btn" disabled={busy} onClick={approve}>
                  Approve Meeting Minutes
                </button>
              ) : null}
              {meeting.minutes_status === 'approved' && (
                <button type="button" className="btn soft" disabled={busy} onClick={makeCommitments}>
                  Create commitments from agreed actions
                </button>
              )}
            </div>
          </div>

          {meeting.minutes && (
            <div className="ws-overview">
              <div className="ws-overview-main">
                <section className="panel">
                  <h2>Executive summary</h2>
                  <ul>
                    {(meeting.minutes.executive_summary || []).map((b: string, i: number) => (
                      <li key={i}>{b}</li>
                    ))}
                  </ul>
                  <EvidenceBadge evidence={meeting.minutes.evidence} />
                </section>
                <section className="panel">
                  <h2>Advice given</h2>
                  {(meeting.minutes.advice_items || []).map((a: any) => (
                    <div key={a.advice_id} className="ws-drift-card">
                      <div className="ws-drift-body">
                        <strong>{a.summary}</strong>{' '}
                        <ConfidencePill confidence={a.evidence_status} />
                        <div className="muted">
                          Response: {a.client_response} · segments:{' '}
                          {(a.evidence_segment_ids || []).join(', ') || 'none'}
                        </div>
                        <p>{a.rationale}</p>
                      </div>
                    </div>
                  ))}
                </section>
                <section className="panel">
                  <h2>Decisions & preferences</h2>
                  {(meeting.minutes.decisions || []).map((d: any, i: number) => (
                    <div key={i} className="ws-alert-mini">
                      <strong>{d.decision}</strong> — {d.status}{' '}
                      <ConfidencePill confidence={d.evidence_status} />
                    </div>
                  ))}
                </section>
                <section className="panel">
                  <h2>Action items</h2>
                  {(meeting.minutes.action_items || []).map((a: any) => (
                    <div key={a.action_id} className="ws-commit-row">
                      <strong>{a.description}</strong>
                      <div className="muted">
                        {a.owner} · due {a.due_date || 'unassigned'} ·{' '}
                        {a.suggestion_only ? 'suggestion (needs approval)' : 'agreed'}
                        {a.commitment_id ? ` · commitment ${a.commitment_id}` : ''}
                      </div>
                    </div>
                  ))}
                </section>
              </div>
              <aside className="ws-overview-side">
                <section className="panel">
                  <h2>Client concerns</h2>
                  {(meeting.minutes.client_concerns || []).map((c: any, i: number) => (
                    <div key={i} className="ws-alert-mini">
                      <strong>{c.concern}</strong>
                      <div className="muted">{c.supporting_statement}</div>
                    </div>
                  ))}
                </section>
                <section className="panel">
                  <h2>Follow-up draft</h2>
                  <span className="pill hypo">Draft — Not Sent</span>
                  <pre className="draft-msg">{meeting.minutes.follow_up_draft}</pre>
                  <p className="muted">Status: {meeting.minutes.follow_up_draft_status}</p>
                </section>
                <section className="panel">
                  <h2>Proposed client updates</h2>
                  <p className="muted">Require explicit approval — not auto-applied.</p>
                  {(meeting.minutes.proposed_client_updates || []).map((p: any, i: number) => (
                    <div key={i} className="ws-alert-mini">
                      <strong>{p.field_name}</strong>
                      <div className="muted">
                        {String(p.previous_value)} → {String(p.proposed_value)} ({p.status})
                      </div>
                    </div>
                  ))}
                  {!meeting.minutes.proposed_client_updates?.length && (
                    <p className="muted">None proposed.</p>
                  )}
                </section>
              </aside>
            </div>
          )}
        </div>
      )}

      {stage === 'live' && !meeting && (
        <div className="panel">
          <p className="muted">Open or start a meeting from Preparation first.</p>
        </div>
      )}
      {stage === 'minutes' && !meeting && (
        <div className="panel">
          <p className="muted">Select a meeting from History.</p>
        </div>
      )}
    </div>
  );
}
