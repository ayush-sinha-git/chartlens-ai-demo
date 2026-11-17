# ChartLens AI — GS Chart & Pitchbook Analyzer

Turns a screenshot of a financial chart, pitchbook slide, macro chart, or
debt-structure diagram into structured JSON plus an Excel/CSV export, with a
Goldman Sachs house-style executive summary and anomaly flags.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root (gitignored):

```
OPENROUTER_API_KEY=sk-or-...
```

### Corporate network / SSL

If you're behind a TLS-inspecting corporate proxy (e.g. a Cloudflare Zero
Trust Gateway), `requests` will fail with
`SSLCertVerificationError: self-signed certificate in certificate chain`.
Fix by building a combined CA bundle once per machine:

```bash
mkdir -p certs
security find-certificate -a -c "<your corporate gateway CA name>" -p \
  /Library/Keychains/System.keychain > /tmp/corp_ca.pem
cat "$(python3 -c 'import certifi; print(certifi.where())')" /tmp/corp_ca.pem \
  > certs/combined-ca-bundle.pem
```

`chartlens_ai/config.py` picks up `certs/combined-ca-bundle.pem`
automatically if it exists. This directory is gitignored since the bundle is
machine-specific.

## Usage

### Demo UI (Streamlit)

```bash
streamlit run app.py
```

Upload any image (or pick one from `input_data/` in the sidebar), click
**Analyze**, and get:
- A red **NEEDS HUMAN REVIEW** banner when the model flags occlusion/illegible
  data, or an amber **NOT A FINANCIAL VISUAL** banner if the image isn't a
  chart/slide/diagram at all.
- A GS house-style executive summary (BLUF / situation / implication) and
  flagged anomalies.
- The chart rebuilt live as an interactive Plotly chart (or an entity-
  relationship graph for debt-structure/org-chart diagrams).
- A data table, and one-click CSV/Excel/JSON downloads.
- Any auto-detected inconsistency between the BLUF text and the extracted
  numbers, surfaced as a warning (see `validation.py` below).

### CLI

Single image:

```bash
python run.py input_data/exhibit_3.png
# or with a custom output prefix:
python run.py input_data/exhibit_3.png output_data/my_chart
```

Works with a local file path or a public image URL.

Batch (every image in `input_data/`, writing to `output_data/`):

```bash
python batch_run.py
```

## Project layout

```
chartlens_ai/
├── config.py       # env/API key/CA bundle/model selection
├── prompts.py      # GS house-style system prompt
├── schema.py        # strict JSON schema enforced on the model's response
├── extractor.py     # image encoding + OpenRouter vision API call (with retry)
├── exporter.py      # JSON -> Excel/CSV (numeric charts and entity/relationship diagrams)
├── validation.py     # post-hoc BLUF-vs-extracted-data consistency check
└── cli.py           # CLI entrypoint
app.py               # Streamlit demo UI
run.py               # thin CLI wrapper: python run.py <image>
batch_run.py         # process every image in input_data/
input_data/           # sample charts/slides/diagrams for testing
output_data/          # generated JSON/CSV/XLSX (gitignored)
```

## How it works

1. The image is base64-encoded and sent to a vision model on OpenRouter
   (`google/gemini-2.5-flash` by default — chosen for accuracy vs. cost after
   testing against 7+ alternatives on real financial charts; see
   `chartlens_ai/config.py` for rationale and how to override via
   `GS_CHART_MODEL_ID`).
2. The model returns JSON validated against a strict schema
   (`chartlens_ai/schema.py`), covering:
   - `data_integrity`: whether the image is even a financial visual
     (`is_financial_visual` — the scope guardrail), whether anything is
     occluded/illegible (`needs_human_review`, `missing_elements`), and a
     `confidence_score`.
   - `chart_metadata`: title, chart type, axis/unit info, and an `is_diagram`
     flag for non-Cartesian diagrams (debt structures, org charts).
   - `extracted_data`: numeric series for ordinary charts (bar/line/scatter/
     waterfall/histogram), or `diagram_relationships` (entities + directed
     relationships) for structural diagrams. These are two separate,
     mutually-exclusive shapes — not one — because a debt-structure/org-chart
     diagram has no y-axis value to extract; forcing it into the numeric
     series shape produced an empty, useless Excel table (see
     `chartlens_ai/schema.py`'s module docstring).
   - `executive_summary`: a BLUF-style (Bottom Line Up Front) write-up.
   - `anomalies_and_risks`: flagged structural/credit/market risks.
3. `validation.py` runs a lightweight post-hoc check: if the BLUF text names
   a series alongside a number, that number is compared against the series'
   actual extracted total, and a warning is attached (`_validation_warnings`
   in the result) if they don't match — catching cases where the model's
   prose is internally inconsistent with its own structured data.
4. `exporter.py` turns the JSON into an Excel workbook (pivoted chart data
   or an entity/relationship table, plus a one-page executive brief) and a
   matching CSV. `app.py` renders the same JSON as a live chart/graph plus a
   formatted summary with risk banners.

## Known limitations

- Numeric extraction on long/dense time series (e.g. 40+ years of daily data
  condensed into one chart) is a best-effort approximation, not pixel-exact.
- The model's free-text summary fields can occasionally be internally
  inconsistent with the structured `extracted_data` on the same response
  (rare, observed on ~1 in 10 test images). `validation.py` catches the common
  case (a named series paired with the wrong number) but is a heuristic, not
  a guarantee — treat `extracted_data` as the source of truth over prose if
  they ever disagree.
- `needs_human_review` / `is_financial_visual` / `missing_elements` are the
  model's self-assessment; always spot-check a sample before relying on it
  unsupervised.
