"""Excel & CSV export pipeline for ChartLens AI's analyzed chart JSON."""

import pandas as pd


def _write_audit_sheet(writer, meta: dict, integrity: dict, summary: dict, data: dict) -> None:
    audit_rows = [
        ("Title", meta.get("title")),
        ("Chart Type", meta.get("chart_type")),
        ("Units", meta.get("units")),
        ("Units Multiplier", meta.get("units_multiplier")),
        ("Scale Type", meta.get("scale_type")),
        ("Source", meta.get("data_source")),
        ("Needs Human Review", integrity.get("needs_human_review")),
        ("Confidence Score", integrity.get("confidence_score")),
        ("Missing Elements", ", ".join(integrity.get("missing_elements", [])) or "None"),
        ("BLUF", summary.get("bluf")),
        ("Situation", summary.get("situation")),
        ("Implication", summary.get("implication")),
        ("Anomalies & Risks", " | ".join(data.get("anomalies_and_risks", []))),
    ]
    df_audit = pd.DataFrame(audit_rows, columns=["Field", "Value"])
    df_audit.to_excel(writer, sheet_name="GS_Executive_Brief", index=False)


def export_to_excel_and_csv(data: dict, output_prefix: str = "chartlens_analysis") -> None:
    meta = data["chart_metadata"]
    integrity = data["data_integrity"]
    summary = data["executive_summary"]
    multiplier = meta.get("units_multiplier") or 1
    is_diagram = meta.get("is_diagram", False)

    csv_path = f"{output_prefix}.csv"
    xlsx_path = f"{output_prefix}.xlsx"

    if is_diagram:
        # Non-Cartesian diagram (debt structure, org chart): export entities and
        # directed relationships instead of a numeric pivot, which would be empty.
        rel = data.get("diagram_relationships", {"entities": [], "relationships": []})
        df_entities = pd.DataFrame({"Entity": rel.get("entities", [])})
        df_relationships = pd.DataFrame(rel.get("relationships", []))
        if not df_relationships.empty:
            df_relationships = df_relationships.rename(
                columns={"from": "From", "to": "To", "label": "Label", "amount": "Amount"}
            )

        df_relationships.to_csv(csv_path, index=False)

        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            df_entities.to_excel(writer, sheet_name="Entities", index=False)
            df_relationships.to_excel(writer, sheet_name="Relationships", index=False)
            _write_audit_sheet(writer, meta, integrity, summary, data)
    else:
        # Flatten extracted_data into a long-format DataFrame and a pivoted Excel-ready table
        rows = []
        for series in data["extracted_data"]:
            s_name = series["series_name"]
            for pt in series["data_points"]:
                raw_y = pt["y"]
                normalized_y = (raw_y * multiplier) if raw_y is not None else None
                rows.append(
                    {
                        "x": pt["x"],
                        "series_name": s_name,
                        "raw_y": raw_y,
                        "units": meta.get("units"),
                        "normalized_y": normalized_y,
                    }
                )

        df_long = pd.DataFrame(rows)

        # Create a wide (pivoted) table mirroring how an analyst rebuilds a chart in Excel
        if not df_long.empty:
            df_wide = df_long.pivot_table(
                index="x", columns="series_name", values="raw_y", aggfunc="first", sort=False
            ).reset_index()
            df_wide = df_wide.rename(columns={"x": meta.get("x_axis_label") or "Category / X"})
        else:
            df_wide = pd.DataFrame()

        df_wide.to_csv(csv_path, index=False)

        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            df_wide.to_excel(writer, sheet_name="Extracted_Chart_Data", index=False)
            df_long.to_excel(writer, sheet_name="Normalized_Series", index=False)
            _write_audit_sheet(writer, meta, integrity, summary, data)

    print(f"Saved CSV  -> {csv_path}")
    print(f"Saved XLSX -> {xlsx_path}")
