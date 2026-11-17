"""Streamlit demo UI for ChartLens AI — GS Chart & Pitchbook Analyzer.

Run with: streamlit run app.py
"""

import io
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chartlens_ai.config import PROJECT_ROOT
from chartlens_ai.extractor import analyze_chart


def _build_relationship_figure(entities: list[str], relationships: list[dict]) -> go.Figure:
    """Lay out entities in a simple vertical flow (top-down by first appearance
    as a 'to' target, so parents tend to sit above children) and draw labeled
    directed edges between them."""
    import math

    # Rough layering: entities that never appear as a "to" start at the top.
    targets = {r["to"] for r in relationships}
    sources_only = [e for e in entities if e not in targets]
    ordered = sources_only + [e for e in entities if e not in sources_only]

    n = len(ordered)
    cols = max(1, math.ceil(math.sqrt(n)))  # wrap into a roughly square grid
    positions = {}
    for i, name in enumerate(ordered):
        row, col = divmod(i, cols)
        positions[name] = (col, -row)  # negative row: sources (row 0) plot above targets

    edge_x, edge_y = [], []
    annotations = []
    for rel in relationships:
        if rel["from"] not in positions or rel["to"] not in positions:
            continue
        x0, y0 = positions[rel["from"]]
        x1, y1 = positions[rel["to"]]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        mid_x, mid_y = (x0 + x1) / 2, (y0 + y1) / 2
        label = rel.get("label", "")
        if rel.get("amount") is not None:
            label = f"{label} ({rel['amount']:g})"
        annotations.append(
            dict(x=mid_x, y=mid_y, text=label, showarrow=False, font=dict(size=9, color="#475569"), bgcolor="rgba(255,255,255,0.85)")
        )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines", line=dict(width=1.5, color="#94A3B8"), hoverinfo="none"))
    node_x = [positions[e][0] for e in entities]
    node_y = [positions[e][1] for e in entities]
    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=entities,
            textposition="bottom center",
            marker=dict(size=28, color="#1D4ED8"),
            hoverinfo="text",
        )
    )
    fig.update_layout(
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=480,
        margin=dict(t=30, b=60),
        annotations=annotations,
    )
    return fig


st.set_page_config(
    page_title="ChartLens AI",
    page_icon="📊",
    layout="wide",
)

INPUT_DIR = PROJECT_ROOT / "input_data"


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .gs-banner-review {
        background-color: #B91C1C;
        color: white;
        padding: 14px 18px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 1.05rem;
        margin-bottom: 12px;
    }
    .gs-banner-non-financial {
        background-color: #92400E;
        color: white;
        padding: 14px 18px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 1.05rem;
        margin-bottom: 12px;
    }
    .gs-banner-ok {
        background-color: #166534;
        color: white;
        padding: 10px 18px;
        border-radius: 6px;
        font-weight: 600;
        margin-bottom: 12px;
    }
    .gs-bluf-box {
        background-color: #0F172A;
        color: #F1F5F9;
        padding: 18px 22px;
        border-radius: 8px;
        border-left: 5px solid #1D4ED8;
        font-size: 1.1rem;
        margin-bottom: 16px;
    }
    .gs-risk-item {
        background-color: #FEF2F2;
        border-left: 4px solid #DC2626;
        padding: 10px 14px;
        margin-bottom: 8px;
        border-radius: 4px;
    }
    .gs-warning-item {
        background-color: #FFFBEB;
        border-left: 4px solid #D97706;
        padding: 10px 14px;
        margin-bottom: 8px;
        border-radius: 4px;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Sidebar: input selection
# ---------------------------------------------------------------------------
st.sidebar.title("📊 ChartLens AI")
st.sidebar.caption("Upload any financial chart, pitchbook slide, macro graph, or debt structure diagram.")

sample_images = sorted(
    p for p in INPUT_DIR.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg")
) if INPUT_DIR.exists() else []

source_mode = st.sidebar.radio("Image source", ["Upload", "Sample library"], horizontal=True)

image_bytes = None
image_name = None

if source_mode == "Upload":
    uploaded = st.sidebar.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])
    if uploaded is not None:
        image_bytes = uploaded.read()
        image_name = uploaded.name
else:
    if sample_images:
        choice = st.sidebar.selectbox("Pick a sample", [p.name for p in sample_images])
        chosen_path = next(p for p in sample_images if p.name == choice)
        image_bytes = chosen_path.read_bytes()
        image_name = chosen_path.name
    else:
        st.sidebar.info("No sample images found in input_data/.")

run_clicked = st.sidebar.button("🔍 Analyze", type="primary", disabled=image_bytes is None)

st.sidebar.divider()
st.sidebar.caption(
    "Model: `google/gemini-2.5-flash` via OpenRouter — chosen for accuracy vs. cost "
    "after testing against 7+ alternatives on real financial charts."
)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result = None
if "result_image_name" not in st.session_state:
    st.session_state.result_image_name = None

if run_clicked and image_bytes is not None:
    tmp_path = PROJECT_ROOT / "output_data" / f"_tmp_{image_name}"
    tmp_path.parent.mkdir(exist_ok=True)
    tmp_path.write_bytes(image_bytes)
    with st.spinner(f"Analyzing '{image_name}' with Goldman Sachs house-style review..."):
        try:
            result = analyze_chart(str(tmp_path))
            st.session_state.result = result
            st.session_state.result_image_name = image_name
        except Exception as e:
            st.error(f"Extraction failed: {e}")
        finally:
            tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
st.title("ChartLens AI — Complex Chart & Pitchbook Analyzer")
st.caption("Image in → structured data, risk flags, and a GS house-style executive summary out.")

if image_bytes is None and st.session_state.result is None:
    st.info("Upload an image or pick a sample from the sidebar, then click **Analyze**.")
    st.stop()

col_image, col_results = st.columns([2, 3], gap="large")

with col_image:
    st.subheader("Source image")
    display_bytes = image_bytes if image_bytes is not None else None
    if display_bytes is not None:
        st.image(display_bytes, width="stretch", caption=image_name)
    elif st.session_state.result is not None:
        st.caption(f"(showing results for: {st.session_state.result_image_name})")

with col_results:
    data = st.session_state.result
    if data is None:
        st.subheader("Results")
        st.info("Click **Analyze** to process the image.")
    else:
        integrity = data["data_integrity"]
        meta = data["chart_metadata"]
        summary = data["executive_summary"]
        is_financial = integrity.get("is_financial_visual", True)

        # --- Status banners ---
        # Priority order matters: is_financial_visual=false (amber) takes
        # precedence over needs_human_review=true (red), since a non-financial
        # image is the more fundamental issue — the green/default banner only
        # shows when both are clear.
        if not is_financial:
            st.markdown(
                '<div class="gs-banner-non-financial">⚠️ NOT A FINANCIAL VISUAL — '
                "no chart data was extracted. See summary below.</div>",
                unsafe_allow_html=True,
            )
        elif integrity["needs_human_review"]:
            missing = ", ".join(integrity.get("missing_elements", [])) or "unspecified issues"
            st.markdown(
                f'<div class="gs-banner-review">🚩 NEEDS HUMAN REVIEW — '
                f"confidence {integrity['confidence_score']:.0%}. Missing/illegible: {missing}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="gs-banner-ok">✅ Extraction confidence: {integrity["confidence_score"]:.0%}</div>',
                unsafe_allow_html=True,
            )

        validation_warnings = data.get("_validation_warnings", [])
        if validation_warnings:
            with st.expander(f"⚠️ {len(validation_warnings)} auto-check warning(s) — verify manually", expanded=False):
                for w in validation_warnings:
                    st.markdown(f'<div class="gs-warning-item">{w}</div>', unsafe_allow_html=True)

        st.caption(f"**{meta['title']}**  ·  {meta['chart_type']}")

        tab_summary, tab_chart, tab_data, tab_raw = st.tabs(
            ["📋 Executive Summary", "📈 Rebuilt Chart", "🗂️ Data Table", "🔧 Raw JSON"]
        )

        # --- Tab: Executive Summary ---
        with tab_summary:
            st.markdown(f'<div class="gs-bluf-box"><b>BLUF:</b> {summary["bluf"]}</div>', unsafe_allow_html=True)
            st.markdown("**Situation**")
            st.write(summary["situation"])
            st.markdown("**Implication**")
            st.write(summary["implication"])

            anomalies = data.get("anomalies_and_risks", [])
            if anomalies:
                st.markdown("**🚨 Anomalies & Risks Flagged**")
                for a in anomalies:
                    st.markdown(f'<div class="gs-risk-item">{a}</div>', unsafe_allow_html=True)

        # --- Tab: Rebuilt Chart ---
        with tab_chart:
            if meta.get("is_diagram"):
                rel = data.get("diagram_relationships", {"entities": [], "relationships": []})
                entities = rel.get("entities", [])
                relationships = rel.get("relationships", [])
                if not entities:
                    st.info("No entities extracted for this diagram.")
                else:
                    st.markdown("**Entity relationship map**")
                    fig = _build_relationship_figure(entities, relationships)
                    st.plotly_chart(fig, width="stretch")
            else:
                series_list = data.get("extracted_data", [])
                if not series_list:
                    st.info("No numeric series were extracted from this image.")
                else:
                    fig = go.Figure()
                    chart_type = (meta.get("chart_type") or "").lower()
                    use_bars = any(k in chart_type for k in ["bar", "waterfall", "histogram"])
                    for series in series_list:
                        xs = [p["x"] for p in series["data_points"]]
                        ys = [p["y"] for p in series["data_points"]]
                        if use_bars:
                            fig.add_trace(go.Bar(name=series["series_name"], x=xs, y=ys))
                        else:
                            fig.add_trace(go.Scatter(name=series["series_name"], x=xs, y=ys, mode="lines+markers"))
                    fig.update_layout(
                        barmode="stack" if use_bars else None,
                        xaxis_title=meta.get("x_axis_label") or "",
                        yaxis_title=meta.get("y_axis_label") or meta.get("units") or "",
                        legend_title_text="Series",
                        height=480,
                        margin=dict(t=30),
                    )
                    st.plotly_chart(fig, width="stretch")

        # --- Tab: Data Table ---
        with tab_data:
            if meta.get("is_diagram"):
                rel = data.get("diagram_relationships", {"entities": [], "relationships": []})
                st.markdown("**Entities**")
                st.dataframe(pd.DataFrame({"Entity": rel.get("entities", [])}), width="stretch")
                st.markdown("**Relationships**")
                df_rel = pd.DataFrame(rel.get("relationships", []))
                if not df_rel.empty:
                    df_rel = df_rel.rename(columns={"from": "From", "to": "To", "label": "Label", "amount": "Amount"})
                st.dataframe(df_rel, width="stretch")
            else:
                rows = []
                for series in data.get("extracted_data", []):
                    for pt in series["data_points"]:
                        rows.append({"Series": series["series_name"], "X": pt["x"], "Y": pt["y"]})
                df = pd.DataFrame(rows)
                st.dataframe(df, width="stretch")

            st.divider()
            col_csv, col_xlsx, col_json = st.columns(3)
            from chartlens_ai.exporter import export_to_excel_and_csv

            export_prefix = str(PROJECT_ROOT / "output_data" / "_streamlit_export")
            Path(export_prefix).parent.mkdir(exist_ok=True)
            export_to_excel_and_csv(data, output_prefix=export_prefix)

            with col_csv:
                with open(f"{export_prefix}.csv", "rb") as f:
                    st.download_button("⬇️ Download CSV", f, file_name="chartlens_analysis.csv")
            with col_xlsx:
                with open(f"{export_prefix}.xlsx", "rb") as f:
                    st.download_button("⬇️ Download Excel", f, file_name="chartlens_analysis.xlsx")
            with col_json:
                st.download_button(
                    "⬇️ Download JSON",
                    json.dumps(data, indent=2),
                    file_name="chartlens_analysis.json",
                    mime="application/json",
                )

        # --- Tab: Raw JSON ---
        with tab_raw:
            st.json(data)
