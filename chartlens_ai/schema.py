"""Strict JSON schema the model must return, enforced via OpenRouter's json_schema response_format.

extracted_data and diagram_relationships are two separate, mutually-exclusive
extraction paths rather than one shape, because forcing a debt structure/org
chart's entities and arrows into the numeric x/y series shape produced an
empty, useless table in exporter.py (there's no y-axis value to extract from
a box-and-arrow diagram). chart_metadata.is_diagram tells the model (and
exporter.py/app.py downstream) which of the two paths applies.
"""

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "data_integrity": {
            "type": "object",
            "description": "Visual audit of legibility and completeness performed BEFORE extracting numbers",
            "properties": {
                "is_financial_visual": {
                    "type": "boolean",
                    "description": "False if the image is not a financial chart, pitchbook slide, macro graph, or corporate/debt structure diagram (e.g. it's a photo, a meme, an unrelated document, a person, etc.) — when false, extracted_data/diagram_relationships should be empty and the executive_summary should simply state the image isn't a financial visual",
                },
                "needs_human_review": {
                    "type": "boolean",
                    "description": "True if any part of the chart is occluded, watermarked, illegible, or missing critical axis labels",
                },
                "missing_elements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of unreadable or missing components (e.g., 'Y-axis scale occluded', 'Legend cut off')",
                },
                "confidence_score": {
                    "type": "number",
                    "description": "0.0 to 1.0 scale of overall extraction accuracy",
                },
            },
            "required": ["is_financial_visual", "needs_human_review", "missing_elements", "confidence_score"],
            "additionalProperties": False,
        },
        "chart_metadata": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The main title or headline of the slide/chart",
                },
                "chart_type": {
                    "type": "string",
                    "description": "e.g., Stacked Bar Chart, Line Graph, Yield Curve, Debt Waterfall, Scatter Plot, Debt Structure Diagram, Org Chart",
                },
                "is_diagram": {
                    "type": "boolean",
                    "description": "True for non-Cartesian entity/relationship diagrams (debt structures, org charts) where data belongs in `diagram_relationships` instead of `extracted_data`",
                },
                "x_axis_label": {
                    "type": ["string", "null"],
                    "description": "Label of the X-axis, or null for non-Cartesian diagrams",
                },
                "y_axis_label": {
                    "type": ["string", "null"],
                    "description": "Label of the Y-axis, or null for non-Cartesian diagrams",
                },
                "units": {
                    "type": ["string", "null"],
                    "description": "Explicit unit of measurement shown on the chart (e.g., '$M', '$B', '%', 'bps', 'x')",
                },
                "units_multiplier": {
                    "type": ["number", "null"],
                    "description": "Numeric multiplier to normalize raw values (e.g., 1000000 for $M, 1000000000 for $B, 0.01 for %, 1 for raw units)",
                },
                "scale_type": {
                    "type": ["string", "null"],
                    "enum": ["linear", "logarithmic", "unknown", None],
                    "description": "Axis scale type; null for non-Cartesian diagrams",
                },
                "data_source": {
                    "type": ["string", "null"],
                    "description": "Any footnoted sources, e.g., Bloomberg, Capital IQ, Company Filings",
                },
            },
            "required": [
                "title",
                "chart_type",
                "is_diagram",
                "x_axis_label",
                "y_axis_label",
                "units",
                "units_multiplier",
                "scale_type",
                "data_source",
            ],
            "additionalProperties": False,
        },
        "extracted_data": {
            "type": "array",
            "description": "The extracted numeric data series to rebuild the chart in Excel. Leave empty for non-Cartesian diagrams (use diagram_relationships instead).",
            "items": {
                "type": "object",
                "properties": {
                    "series_name": {
                        "type": "string",
                        "description": "Name of the line, bar category, or debt tranche",
                    },
                    "data_points": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "x": {
                                    "type": ["string", "number"],
                                    "description": "X-axis coordinate, date, or entity name",
                                },
                                "y": {
                                    "type": ["number", "null"],
                                    "description": "Exact or reliably interpolated Y value, or null if occluded/illegible",
                                },
                            },
                            "required": ["x", "y"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["series_name", "data_points"],
                "additionalProperties": False,
            },
        },
        "diagram_relationships": {
            "type": "object",
            "description": "For non-Cartesian diagrams only (debt structures, org charts). Leave entities/relationships as empty arrays for ordinary charts.",
            "properties": {
                "entities": {
                    "type": "array",
                    "description": "Every box/node in the diagram (e.g., 'HoldCo (Parent Issuer)', 'Subsidiary I')",
                    "items": {"type": "string"},
                },
                "relationships": {
                    "type": "array",
                    "description": "Every directed connection/arrow between entities",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string", "description": "Source entity"},
                            "to": {"type": "string", "description": "Target entity"},
                            "label": {
                                "type": "string",
                                "description": "The connection's label, e.g. 'Debt financing', 'Cash upstream to repay HoldCo debt'",
                            },
                            "amount": {
                                "type": ["number", "null"],
                                "description": "Dollar amount or leverage multiple shown on this connection, or null if not quantified",
                            },
                        },
                        "required": ["from", "to", "label", "amount"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["entities", "relationships"],
            "additionalProperties": False,
        },
        "executive_summary": {
            "type": "object",
            "properties": {
                "bluf": {
                    "type": "string",
                    "description": "Bottom Line Up Front - 1-sentence core takeaway with key numbers",
                },
                "situation": {
                    "type": "string",
                    "description": "Objective summary of what the visible data directly demonstrates",
                },
                "implication": {
                    "type": "string",
                    "description": "Strategic, credit, or market impact grounded in the slide (label any external macro assumptions explicitly)",
                },
            },
            "required": ["bluf", "situation", "implication"],
            "additionalProperties": False,
        },
        "anomalies_and_risks": {
            "type": "array",
            "description": "Flagged financial risks, margin compression, correlation breaks, or structural subordination red flags",
            "items": {"type": "string"},
        },
    },
    "required": [
        "data_integrity",
        "chart_metadata",
        "extracted_data",
        "diagram_relationships",
        "executive_summary",
        "anomalies_and_risks",
    ],
    "additionalProperties": False,
}
