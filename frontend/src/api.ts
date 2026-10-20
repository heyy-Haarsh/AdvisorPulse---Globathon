const BASE = '';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path}: ${res.status} ${text}`);
  }
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
  return res.json();
}

export type Priority = 'Critical' | 'High' | 'Monitor' | 'On Track';
export type Confidence = 'Verified' | 'Limited' | 'Insufficient';

export interface ClientPriority {
  investor_id: string;
  display_name: string;
  tier: string;
  risk_profile: string;
  priority: Priority;
  score: number;
  confidence?: Confidence;
  severity?: string;
  priority_reason: string;
  factors: { name: string; points: number; detail: string; is_data_quality?: boolean }[];
  goal_status: {
    deviation_pct_vs_expected: number;
    progress_to_target_pct: number;
    goal_name: string;
  };
  last_review_date: string;
  data_freshness_days: string | number;
  data_quality_issue: boolean;
  marked_reviewed?: boolean;
  decision_action?: string;
  decision?: { action?: string; note?: string };
  evidence?: EvidenceEnvelope;
  resolved?: boolean;
}

export interface EvidenceEnvelope {
  confidence: Confidence;
  severity: string;
  claim: string;
  evidence: { source: string; record_ids?: string[]; as_of?: string; detail?: string }[];
  missing_data?: string[];
  limitations?: string[];
  next_steps?: string[];
  is_hypothetical?: boolean;
}

export interface Overview {
  total_clients: number;
  clients_requiring_review: number;
  priority_distribution: Record<string, number>;
  high_visibility_count: number;
  long_tail_count: number;
  recently_changed_long_tail: ClientPriority[];
  action_queue: ClientPriority[];
  follow_ups?: ClientPriority[];
  resolved_suppressed?: number;
  illustrative_note: string;
  is_demo: boolean;
}

export const api = {
  overview: () => get<Overview>('/api/overview'),
  attention: (params: Record<string, string> = {}) => {
    const q = new URLSearchParams(params).toString();
    return get<{ count: number; clients: ClientPriority[] }>(`/api/attention${q ? `?${q}` : ''}`);
  },
  attentionEngine: () => get<any>('/api/attention-engine'),
  clients: (params: Record<string, string> = {}) => {
    const q = new URLSearchParams(params).toString();
    return get<{ count: number; clients: ClientPriority[] }>(`/api/clients${q ? `?${q}` : ''}`);
  },
  investor: (id: string) => get<any>(`/api/investors/${id}`),
  structuredSummary: (id: string) => get<any>(`/api/investors/${id}/summary`),
  adviceOutcomes: (id: string) => get<any>(`/api/investors/${id}/advice-outcomes`),
  drift: (id: string) => get<any>(`/api/investors/${id}/drift`),
  setDriftStatus: (alertId: string, status: string, note = '') =>
    post<any>(`/api/drift/${encodeURIComponent(alertId)}/status`, { status, note }),
  whatif: (
    id: string,
    body: {
      scenario_type?: string;
      sip_delta?: number;
      return_delta_pp?: number;
      years_override?: number;
      lump_sum?: number;
      proposed_weights?: Record<string, number>;
      market_shocks?: Record<string, number>;
    },
  ) => post<any>(`/api/investors/${id}/whatif`, body),
  marketShockAssumptions: () => get<any>('/api/market-shock/assumptions'),
  marketShockInstruments: (kind?: string) =>
    get<any>(`/api/market-shock/instruments${kind ? `?kind=${encodeURIComponent(kind)}` : ''}`),
  marketShockRun: (body: {
    scenario_name?: string;
    scenario_type?: string;
    instrument_id?: string | null;
    price_change_pct?: number;
    equity_market_shock_pct?: number;
    include_indirect_exposure?: boolean;
    assumptions_version?: string;
    preset_id?: string | null;
    include_goal_impact?: boolean;
  }) => post<any>('/api/market-shock/run', body),
  marketShockMarkReviewed: (body: {
    investor_id: string;
    scenario_equity_shock_pct?: number;
    note?: string;
  }) => post<any>('/api/market-shock/mark-reviewed', body),
  agents: (id: string) => get<any>(`/api/investors/${id}/agents`),
  timeline: (id: string) => get<any>(`/api/investors/${id}/timeline`),
  brief: (id: string) => get<any>(`/api/investors/${id}/meeting-brief`),
  meetingPrep: (id: string) => get<any>(`/api/investors/${id}/meeting-prep`),
  meetingFollowup: (id: string, notes_text: string) =>
    post<any>(`/api/investors/${id}/meeting-followup`, { notes_text }),
  notes: (investorId?: string) =>
    get<{ notes: any[]; extractions: any[]; transcription_disclaimer?: string }>(
      `/api/notes${investorId ? `?investor_id=${investorId}` : ''}`,
    ),
  addNote: (investor_id: string, note_text: string) =>
    post<any>('/api/notes', { investor_id, note_text }),
  updateNote: (note_id: string, note_text: string) =>
    put<any>(`/api/notes/${note_id}`, { note_text }),
  markReviewed: (investor_id: string, reviewed = true) =>
    post<any>('/api/attention/reviewed', { investor_id, reviewed }),
  attentionDecision: (investor_id: string, action: string, note?: string) =>
    post<any>('/api/attention/decision', { investor_id, action, note }),
  mockTranscript: (investor_id: string, mock_transcript?: string) =>
    post<any>('/api/transcription/mock-local', { investor_id, mock_transcript }),
  confirmExtraction: (extraction_id: string, create_followup = true) =>
    post<any>(`/api/memory/extractions/${extraction_id}/confirm`, { create_followup }),
  dismissExtraction: (extraction_id: string) =>
    post<any>(`/api/memory/extractions/${extraction_id}/dismiss`, {}),
  commitments: (investorId?: string) =>
    get<{ commitments: any[] }>(
      `/api/commitments${investorId ? `?investor_id=${investorId}` : ''}`,
    ),
  addCommitment: (body: {
    investor_id: string;
    action: string;
    due?: string;
    status?: string;
    commitment_id?: string;
  }) => post<any>('/api/commitments', body),
  copilot: (
    query: string,
    context_investor_id?: string,
    conversation_context?: Record<string, unknown>,
  ) =>
    post<any>('/api/copilot', {
      query,
      context_investor_id,
      conversation_context,
    }),
  copilotDemoCatalog: () => get<any>('/api/copilot/demo-catalog'),
  patterns: () => get<any>('/api/patterns'),
  pattern: (id: string) => get<any>(`/api/patterns/${id}`),
  feedback: (body: {
    investor_id: string;
    insight_ref: string;
    action: string;
    correction?: string;
    note?: string;
  }) => post<any>('/api/feedback', body),
  settings: () => get<any>('/api/settings'),
  saveSettings: (body: Record<string, unknown>) => put<any>('/api/settings', body),
  audit: () => get<{ entries: any[] }>('/api/audit'),
  scenario: () => get<any>('/api/demo/scenario'),
  txnSignals: () => get<any>('/api/transactions/signals'),
  blindSpot: (segment = 'less_observed') =>
    get<any>(`/api/blind-spot?segment=${encodeURIComponent(segment)}`),
  alertQuality: () => get<any>('/api/eval/alert-quality'),
  nextReviewAction: (id: string) => get<any>(`/api/investors/${id}/next-review-action`),
  decideNextReviewAction: (
    id: string,
    body: {
      decision: 'accept' | 'edit' | 'reject';
      action_key?: string;
      action_label?: string;
      note?: string;
      approve_client_message?: boolean;
    },
  ) => post<any>(`/api/investors/${id}/next-review-action/decision`, body),
  performanceCrosscheck: (id: string) =>
    get<any>(`/api/investors/${id}/performance-crosscheck`),
  validateTxnDemoDirty: () => post<any>('/api/transactions/validate-demo-dirty', {}),
  validateTxnUpload: async (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/transactions/validate', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`API validate: ${res.status}`);
    return res.json();
  },
  txnExceptions: () => get<{ exceptions: any[]; is_demo: boolean }>('/api/transactions/exceptions'),
  resolveTxnException: (exceptionId: string, resolution: string, note = '') =>
    post<any>(`/api/transactions/exceptions/${encodeURIComponent(exceptionId)}/resolve`, {
      resolution,
      note,
    }),
  importTransactions: () => post<any>('/api/transactions/import', {}),

  // Meeting Intelligence (Gemini)
  meetingIntelStatus: () => get<any>('/api/meeting-intel/status'),
  meetingIntelList: (investorId?: string) =>
    get<any>(
      `/api/meeting-intel/meetings${investorId ? `?investor_id=${encodeURIComponent(investorId)}` : ''}`,
    ),
  meetingIntelGet: (meetingId: string) => get<any>(`/api/meeting-intel/meetings/${meetingId}`),
  meetingIntelCreate: (body: Record<string, unknown>) =>
    post<any>('/api/meeting-intel/meetings', body),
  meetingIntelPatch: async (meetingId: string, body: Record<string, unknown>) => {
    const res = await fetch(`/api/meeting-intel/meetings/${meetingId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`API patch meeting: ${res.status} ${await res.text()}`);
    return res.json();
  },
  meetingIntelPrepare: (meetingId: string, regenerate = false) =>
    post<any>(
      `/api/meeting-intel/meetings/${meetingId}/prepare?regenerate=${regenerate}`,
      {},
    ),
  meetingIntelConsent: (meetingId: string, note = '') =>
    post<any>(`/api/meeting-intel/meetings/${meetingId}/consent`, { note }),
  meetingIntelStart: (meetingId: string) =>
    post<any>(`/api/meeting-intel/meetings/${meetingId}/start`, {}),
  meetingIntelRecordingState: (meetingId: string, state: string) =>
    post<any>(
      `/api/meeting-intel/meetings/${meetingId}/recording-state?state=${encodeURIComponent(state)}`,
      {},
    ),
  meetingIntelNote: (meetingId: string, body: Record<string, unknown>) =>
    post<any>(`/api/meeting-intel/meetings/${meetingId}/notes`, body),
  meetingIntelUploadAudio: async (meetingId: string, file: Blob, filename: string) => {
    const fd = new FormData();
    fd.append('file', file, filename);
    const res = await fetch(`/api/meeting-intel/meetings/${meetingId}/upload-audio`, {
      method: 'POST',
      body: fd,
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.status} ${await res.text()}`);
    return res.json();
  },
  meetingIntelTranscribe: (meetingId: string) =>
    post<any>(`/api/meeting-intel/meetings/${meetingId}/transcribe`, {}),
  meetingIntelPasteTranscript: (meetingId: string, text: string) =>
    post<any>(`/api/meeting-intel/meetings/${meetingId}/transcript/paste`, { text }),
  meetingIntelUpdateTranscript: async (meetingId: string, body: Record<string, unknown>) => {
    const res = await fetch(`/api/meeting-intel/meetings/${meetingId}/transcript`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Transcript update: ${res.status}`);
    return res.json();
  },
  meetingIntelGenerateMinutes: (meetingId: string) =>
    post<any>(`/api/meeting-intel/meetings/${meetingId}/minutes/generate`, {}),
  meetingIntelPatchMinutes: async (meetingId: string, body: Record<string, unknown>) => {
    const res = await fetch(`/api/meeting-intel/meetings/${meetingId}/minutes`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Minutes patch: ${res.status}`);
    return res.json();
  },
  meetingIntelApproveMinutes: (meetingId: string) =>
    post<any>(`/api/meeting-intel/meetings/${meetingId}/minutes/approve`, {}),
  meetingIntelCommitments: (meetingId: string, action_ids?: string[]) =>
    post<any>(`/api/meeting-intel/meetings/${meetingId}/commitments`, { action_ids }),
  meetingIntelEnd: (meetingId: string) =>
    post<any>(`/api/meeting-intel/meetings/${meetingId}/end`, {}),
  meetingIntelScheduleMeet: (meetingId: string, preferGoogle = true) =>
    post<any>(
      `/api/meeting-intel/meetings/${meetingId}/schedule-meet?prefer_google=${preferGoogle}`,
      {},
    ),
  meetingIntelLoadDemoTranscript: (meetingId: string) =>
    post<any>(`/api/meeting-intel/meetings/${meetingId}/load-demo-transcript`, {}),
  meetingIntelSeedDemo: () => post<any>('/api/meeting-intel/seed-demo', {}),
  meetingIntelGoogleStatus: () => get<any>('/api/meeting-intel/google/status'),
  meetingIntelGoogleAuthUrl: () => get<any>('/api/meeting-intel/google/auth-url'),
};
