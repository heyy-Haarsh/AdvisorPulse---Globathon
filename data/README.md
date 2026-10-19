# Data Layer — Advisor Pulse

## Important: two data layers

| Layer | Source | Purpose | Label |
|---|---|---|---|
| **1 — Transactions** | Optional CSV matching the supplied schema | Cash-flow / spending signals only | Real or sample transactions — **not** investment returns |
| **2 — Portfolio universe** | Generated synthetic CSVs | Goals, holdings, returns, advice, prioritization demo | Every record marked `is_demo=true` / ID prefix `DEMO-` |

**Never** present synthetic portfolio returns as if they came from Layer 1 transactions. A salary credit is income, not an investment return. Food delivery spend is not evidence of poor investment behavior.

## Layer 1 — Transaction schema

```
transaction_id, user_id, date, time, description, category, amount, currency, type, payment_mode, city
```

### Normalization rules (implemented in `backend/ingestion/transactions.py`)

- Strip whitespace; normalize category/type capitalization.
- Treat dates like `########`, empty, or unparseable as missing.
- Malformed amounts → null / dropped with validation warning.
- Duplicate `transaction_id` → keep first.
- Empty city → `UNKNOWN`.
- Extract only: income/expense trends, recurring patterns (when history sufficient), cash-flow volatility, unusual spikes **with confidence**.

### Sample file

- `sample_transactions.csv` — synthetic spending sample for pipeline testing (not linked to demo portfolio investors as “true” performance).

## Layer 2 — Synthetic portfolio files

| File | Contents |
|---|---|
| `synthetic_investors.csv` | Profiles, risk, AUM band, visibility tier, last review |
| `synthetic_goals.csv` | Goals, targets, dates, expected path |
| `synthetic_holdings.csv` | Holdings, asset class, market value |
| `synthetic_returns.csv` | Periodic portfolio & benchmark returns |
| `synthetic_advice.csv` | Historical advice + follow-ups |
| `synthetic_notes.csv` | Advisor notes |
| `synthetic_cashflows.csv` | Contribution/withdrawal events for return calcs |

Generate with:

```bash
python data/generate_synthetic.py
```

Validate with:

```bash
python data/validate_data.py
python -m pytest backend/tests -q
```

## Demo narrative investors

| Investor ID | Role in story |
|---|---|
| `DEMO-INV-001` | **Priya Sharma** — long-term retirement goal, measurable deviation, needs review (primary walkthrough) |
| `DEMO-INV-002` | **Arjun Mehta** — appears down vs absolute return, but gap explained by planned withdrawal + still On Track |
| `DEMO-INV-H01`…`H20` | High-visibility book (known top clients) |
| `DEMO-INV-L001`… | Long-tail population for prioritization |

All amounts are **fictional INR demo data**.
