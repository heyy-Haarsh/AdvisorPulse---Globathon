# Data schemas

## Layer 1 — Transactions (optional CSV)

| Column | Type | Notes |
|---|---|---|
| transaction_id | string | Unique; duplicates flagged (not auto-deleted) |
| user_id | string | Not linked as true portfolio performance |
| date | string/date | `########` → missing |
| time | string | HH:MM:SS |
| description | string | Normalized whitespace |
| category | string | Empty → UNCATEGORIZED |
| amount | number | Non-numeric dropped |
| currency | string | Default INR |
| type | string | credit/debit normalized |
| payment_mode | string | Optional |
| city | string | Empty → UNKNOWN |

## Layer 2 — Synthetic portfolio (all `is_demo=true`)

### synthetic_investors.csv
`investor_id, display_name, is_demo, tier, risk_profile, age, city, currency, aum_band, last_review_date, data_freshness_days, visibility_rank, notes_summary`

### synthetic_goals.csv
`goal_id, investor_id, is_demo, goal_name, goal_type, target_amount, current_mapped_value, target_date, start_date, expected_annual_return_pct, required_monthly_sip, currency, status_hint, benchmark_id`

### synthetic_holdings.csv
`holding_id, investor_id, is_demo, instrument_id, instrument_name, asset_class, quantity, market_value, currency, as_of_date, weight_pct`

### synthetic_returns.csv
`investor_id, is_demo, period, period_end_date, portfolio_return_pct, benchmark_id, benchmark_return_pct, portfolio_value_eom, methodology_note`

### synthetic_cashflows.csv
`cashflow_id, investor_id, is_demo, date, amount, flow_type, currency, note`

### synthetic_advice.csv
`advice_id, investor_id, is_demo, advice_date, recommendation, intended_outcome, follow_up_status, follow_up_due, advisor_id`

### synthetic_notes.csv
`note_id, investor_id, is_demo, created_at, author, note_text, source, transcript_local`
