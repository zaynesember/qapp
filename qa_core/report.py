"""
report.py — Excel report generation (v3.5, concise state_codes syntax + refined highlighting)

Original QA engine by sbaltz.
Refactored and extended by Zayne (2025).
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import pathlib
from typing import Dict, Any
from qa_core import config


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------

def _flatten(value: Any) -> str:
    """Convert listlike/dict/dataframe/scalar to concise string."""
    if isinstance(value, (list, tuple, set, pd.Series, np.ndarray)):
        value = list(value)
        if not value:
            return "<EMPTY>"
        normed = ["<EMPTY>" if (pd.isna(v) or str(v).strip() == "") else str(v).strip() for v in value]
        uniq = list(set(normed))
        if len(uniq) == 1:
            val = uniq[0]
            return val if len(normed) == 1 else f"{val} × {len(normed)}"
        if len(normed) > 10:
            return ", ".join(normed[:10]) + ", ..."
        return ", ".join(normed)
    if isinstance(value, dict):
        if not value:
            return "<EMPTY>"
        return "; ".join(
            f"{k}={('<EMPTY>' if pd.isna(v) or (isinstance(v, str) and not v.strip()) else v)}"
            for k, v in value.items()
        )
    if isinstance(value, pd.DataFrame):
        return "<EMPTY>" if value.empty else f"<DATAFRAME: {value.shape[0]} rows, {value.shape[1]} cols>"
    try:
        if pd.isna(value) or (isinstance(value, str) and not value.strip()):
            return "<EMPTY>"
    except Exception:
        pass
    return str(value)


def _compress_issue_values_row(row):
    """Collapse repeated '<EMPTY>' sequences cleanly."""
    s = str(row["issue_values"]).strip()
    n = int(row.get("issues", 0) or 0)
    if not s or "<EMPTY>" not in s:
        return s
    if "×" in s:
        return s
    tokens = [t for t in s.replace("\n", ",").replace(";", ",").split(",") if t.strip()]
    non_ellipsis = [t.strip() for t in tokens if t.strip() != "..."]
    if non_ellipsis and all(t == "<EMPTY>" for t in non_ellipsis):
        return "<EMPTY>" if n <= 1 else f"<EMPTY> × {n}"
    return s


def _compact_problematic_values(row):
    """Compress repeated identical values into '<VALUE> × n' syntax."""
    s = str(row.get("issue_values", "")).strip()
    if not s or "×" in s:
        return s
    n = int(row.get("issues", 0) or 0)
    if n <= 1:
        return s
    tokens = [t.strip() for t in s.replace("\n", ",").replace(";", ",").split(",") if t.strip()]
    tokens = [t.replace(". . .", "...") for t in tokens if t != "..."]
    if not tokens:
        return s
    uniq = set(tokens)
    if len(uniq) == 1:
        val = next(iter(uniq))
        return f"{val} × {n}"
    return s


def _compress_row_ranges(row_nums, limit=10):
    """Convert list of row numbers to '1, 3-5, 7, ...'."""
    if not row_nums:
        return ""
    row_nums = sorted({int(x) for x in row_nums if str(x).isdigit()})
    if not row_nums:
        return ""
    ranges, start, prev = [], row_nums[0], row_nums[0]
    for n in row_nums[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = n
    ranges.append(f"{start}-{prev}" if start != prev else str(start))
    if len(ranges) > limit:
        ranges = ranges[:limit] + ["..."]
    return ", ".join(ranges)


# ---------------------------------------------------------------------
# Excel report writer
# ---------------------------------------------------------------------

def write_excel_report(results: Dict[str, Any], path: pathlib.Path) -> None:
    """Write human-readable Excel QA report (v3.5)."""
    excluded_sections = {"statewide_totals", "duplicates_summary"}
    detected_state = results.get("detected_state", {})

    # Rename fips_checks → state_codes if present
    if "fips_checks" in results and "state_codes" not in results:
        results["state_codes"] = results.pop("fips_checks")

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        rows = []
        for section, content in results.items():
            if section in excluded_sections or not isinstance(content, dict):
                continue
            for check, v in content.items():
                if not isinstance(v, dict):
                    continue
                issue_values = "" if check in ("exact_duplicates", "all_but_votes_duplicate") else _flatten(v.get("issue_values", ""))
                rows.append({
                    "section": section,
                    "check": check,
                    "issues": int(v.get("issues", 0) or 0),
                    "issue_values": issue_values,
                    "issue_row_numbers": _flatten(v.get("issue_row_numbers", "")),
                })

        # Add duplicates summary rows if not yet included
        if "duplicates" in results:
            dup_df = results["duplicates"]
            if isinstance(dup_df, pd.DataFrame) and not dup_df.empty and "dup_type" in dup_df.columns:
                existing = {(r["section"], r["check"]) for r in rows}
                for dup_type, g in dup_df.groupby("dup_type"):
                    name = "exact_duplicates" if dup_type == "exact_duplicate" else dup_type
                    if ("duplicates", name) not in existing:
                        rows.append({
                            "section": "duplicates",
                            "check": name,
                            "issues": len(g),
                            "issue_values": "",
                            "issue_row_numbers": ",".join(map(str, g.index.to_series().add(1))),
                        })

        # Remove redundant field-level duplicate check
        rows = [r for r in rows if not (r["section"] == "fields" and r["check"] == "exact_duplicates")]

        df = pd.DataFrame(rows, columns=["section", "check", "issues", "issue_values", "issue_row_numbers"])
        df["issues"] = df["issues"].fillna(0).astype(int)
        df["issue_values"] = df["issue_values"].fillna("").replace("<EMPTY>", "")
        df["issue_row_numbers"] = df["issue_row_numbers"].fillna("<EMPTY>").replace("", "<EMPTY>")
        df["issue_values"] = df.apply(_compress_issue_values_row, axis=1)

        # Apply concise value × n syntax across all relevant sections
        df["issue_values"] = df.apply(_compact_problematic_values, axis=1)

        # Compact row numbers
        def _safe_parse_rows(val):
            if not val or val in ("<EMPTY>", ""):
                return []
            return [int(x) for x in str(val).replace("...", "").replace(" ", "").split(",") if x.isdigit()]
        df["issue_row_numbers"] = df["issue_row_numbers"].apply(lambda v: _compress_row_ranges(_safe_parse_rows(v)))

        # Blank out when no issues
        mask = df["issues"] == 0
        df.loc[mask, ["issue_values", "issue_row_numbers"]] = ""

        # Rename headers for readability
        df = df.rename(columns={
            "section": "QA Section",
            "check": "Check Name",
            "issues": "Issues Found",
            "issue_values": "Problematic Values",
            "issue_row_numbers": "Row Numbers"
        })

        failed_checks = (df["Issues Found"] > 0).sum()

        # --- Detected state banner at top ---
        state_banner = pd.DataFrame([
            ["Detected State", detected_state.get("state_po", "Unknown")],
            ["State Name", detected_state.get("state_name", "")],
            ["State FIPS", detected_state.get("state_fips", "")],
            ["State IC", detected_state.get("state_ic", "")],
            ["State CEN", detected_state.get("state_cen", "")]
        ], columns=["Info", "Value"])

        meta_df = pd.DataFrame([
            ["Failed Checks", f"{failed_checks:,}"],
            ["Total Checks", f"{len(df):,}"],
        ], columns=["Info", "Value"])

        # Write top metadata
        state_banner.to_excel(writer, index=False, sheet_name="QA Summary", startrow=0)
        banner_end = len(state_banner) + 2
        meta_df.to_excel(writer, index=False, sheet_name="QA Summary", startrow=banner_end)
        start_row = banner_end + len(meta_df) + 2

        # --- Write main QA summary table ---
        df.to_excel(writer, index=False, sheet_name="QA Summary", startrow=start_row)

        wb = writer.book
        ws = writer.sheets["QA Summary"]

        header_fmt = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "text_wrap": True})
        wrap_fmt = wb.add_format({"text_wrap": True})
        ws.set_column("A:A", 18)
        ws.set_column("B:B", 28)
        ws.set_column("C:C", 12)
        ws.set_column("D:D", 65, wrap_fmt)
        ws.set_column("E:E", 45, wrap_fmt)

        header_row = start_row
        for i, val in enumerate(df.columns):
            ws.write(header_row, i, val, header_fmt)

        # --- Highlight failing checks ---
        fail_fmt = wb.add_format({"font_color": "#9C0006", "bg_color": "#FFC7CE"})
        ws.conditional_format(
            f"C{header_row+2}:C{header_row+len(df)+1}",
            {"type": "cell", "criteria": ">", "value": 0, "format": fail_fmt}
        )

        # --- Special red for state_codes section (only Issues cell) ---
        red_fmt = wb.add_format({"font_color": "#9C0006", "bg_color": "#F4CCCC", "bold": True})
        for idx, row in df.iterrows():
            if row["QA Section"] == "state_codes" and row["Issues Found"] > 0:
                excel_row = start_row + 2 + idx
                ws.write(excel_row - 1, 2, row["Issues Found"], red_fmt)

        ws.freeze_panes(header_row + 1, 0)

        # --- Extra sheets ---
        name_map = {"statewide_totals": "Vote Aggregation", "duplicates": "Duplicates"}
        for section, content in results.items():
            if section in {"duplicates_summary"}:
                continue
            if isinstance(content, pd.DataFrame) and not content.empty:
                name = name_map.get(section, section)[:31]
                content.to_excel(writer, index=False, sheet_name=name)

    print(f"Excel report written to {path}")
