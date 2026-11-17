"""Post-hoc sanity checks on the model's response.

The model occasionally produces a BLUF/executive_summary that's internally
inconsistent with its own extracted_data (observed ~1 in 10 real test images:
e.g. stating "EBITDA of 3,431" in prose when extracted_data correctly shows
EBITDA = 15,299 and a *different* series, FCF, = 3,431). The JSON schema
can't enforce cross-field consistency, so this module catches it after the
fact by checking that when the BLUF names a series and a number together,
that number actually matches that series' value — not just any value
anywhere in extracted_data (a number existing elsewhere doesn't make the
pairing correct, since the bug is mislabeling, not a fabricated number).
"""

import re

_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def _numbers_in_text(text: str) -> list[float]:
    found = []
    for match in _NUMBER_RE.findall(text or ""):
        cleaned = match.replace(",", "")
        try:
            value = float(cleaned)
        except ValueError:
            continue
        if value != 0:
            found.append(value)
    return found


def _series_totals(data: dict) -> dict[str, float]:
    """Sum of each series' values, keyed by series_name (lowercased)."""
    totals: dict[str, float] = {}
    for series in data.get("extracted_data", []):
        name = series.get("series_name", "").strip().lower()
        if not name:
            continue
        total = sum(
            pt["y"] for pt in series.get("data_points", []) if pt.get("y") is not None
        )
        totals[name] = totals.get(name, 0) + total
    return totals


def check_bluf_consistency(data: dict, tolerance: float = 0.05) -> list[str]:
    """Return warnings when the BLUF names a series alongside a number that
    doesn't match that series' actual extracted value.

    Heuristic, not a hard validator: finds a number in the BLUF text, looks
    for the nearest series name mentioned right before it (within ~40 chars),
    and checks the number against that series' total. Flags for human
    attention; does not block or auto-correct the result.
    """
    warnings: list[str] = []

    if data.get("chart_metadata", {}).get("is_diagram"):
        return warnings  # no numeric series to cross-check for diagrams
    if not data.get("data_integrity", {}).get("is_financial_visual", True):
        return warnings  # nothing to check on a non-financial image

    totals = _series_totals(data)
    if not totals:
        return warnings

    bluf_text = data.get("executive_summary", {}).get("bluf", "") or ""

    for match in _NUMBER_RE.finditer(bluf_text):
        cleaned = match.group().replace(",", "")
        try:
            num = float(cleaned)
        except ValueError:
            continue
        # Skip small numbers: too likely to be a year, percentage, ratio, or
        # count rather than the kind of figure a series mismatch matters for.
        if num < 10:
            continue

        # Look at the text just before this number for a series name mention
        window_start = max(0, match.start() - 40)
        preceding_text = bluf_text[window_start:match.start()].lower()

        # Prefer the longest/most specific matching series name (e.g. "free
        # cash flow" over a shorter substring) so overlapping names don't
        # pick an arbitrary one.
        matches = [
            (series_name, total)
            for series_name, total in totals.items()
            if series_name and series_name in preceding_text
        ]
        if not matches:
            continue
        series_name, total = max(matches, key=lambda m: len(m[0]))

        if abs(num - total) > tolerance * max(abs(total), 1):
            warnings.append(
                f"BLUF says '{series_name}' is {num:g}, but extracted_data shows "
                f"{series_name} = {total:g}. Possible mislabeled figure — verify manually."
            )

    return warnings
