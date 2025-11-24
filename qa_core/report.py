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

def _flatten(value: Any, show_empty_marker: bool = False) -> str:
    """Convert listlike/dict/dataframe/scalar to concise string.

    By default this returns empty strings for missing/blank inputs so that
    report cells remain blank. Set `show_empty_marker=True` only when a
    literal "<EMPTY>" marker is desired (currently the Unique sheet).
    """
    empty_marker = "<EMPTY>" if show_empty_marker else ""

    if isinstance(value, (list, tuple, set, pd.Series, np.ndarray)):
        value = list(value)
        if not value:
            return empty_marker
        normed = [empty_marker if (pd.isna(v) or str(v).strip() == "") else str(v).strip() for v in value]
        uniq = list(set(normed))
        if len(uniq) == 1:
            val = uniq[0]
            return val if len(normed) == 1 else f"{val} × {len(normed)}"
        if len(normed) > 10:
            return ", ".join(normed[:10]) + ", ..."
        return ", ".join(normed)
    if isinstance(value, dict):
        if not value:
            return empty_marker
        return "; ".join(
            f"{k}={(empty_marker if pd.isna(v) or (isinstance(v, str) and not v.strip()) else v)}"
            for k, v in value.items()
        )
    if isinstance(value, pd.DataFrame):
        return empty_marker if value.empty else f"<DATAFRAME: {value.shape[0]} rows, {value.shape[1]} cols>"
    try:
        if pd.isna(value) or (isinstance(value, str) and not value.strip()):
            return empty_marker
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


def _condense_issue_values_row(row):
    """General-purpose compression: collapse repeated tokens into 'value × n'.

    Takes a row (pandas Series) with keys 'issue_values' (string) and
    optionally 'issues' (int). Parses values using common delimiters and
    returns a concise, ordered summary like 'A × 3, B, C × 2'.
    """
    import re
    from collections import Counter

    s = str(row.get("issue_values", "")).strip()
    if not s:
        return ""
    # If already condensed (contains a multiplier and no commas), leave as-is
    if "×" in s and "," not in s:
        return s

    # Split on common delimiters, keep tokens that are non-empty after strip
    tokens = [t.strip() for t in re.split(r"[,;\n]+", s) if t.strip()]
    if not tokens:
        return ""
    # Remove tokens that are purely ellipses or stray punctuation (e.g., '.' or '...')
    tokens = [t for t in tokens if not re.fullmatch(r"\.*\s*", t)]
    if not tokens:
        return ""
    counter = Counter(tokens)
    # Order by frequency desc, then lexicographically for stability
    parts = []
    for token, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
        if count > 1:
            parts.append(f"{token} × {count}")
        else:
            parts.append(token)

    return ", ".join(parts)

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


def _pretty_check_name(raw: str) -> str:
    """Convert internal check identifiers into concise, human-friendly labels.

    Examples:
      - 'precinct_format::ODD_NUMBER_OF_SINGLE_QUOTES' ->
           'Odd number of single quotes (Precinct)'
      - 'candidate_regex::UNRECOGNIZED CHARACTERS' ->
           'Unrecognized characters (Candidate)'
      - 'zero_vote_rows' -> 'Zero vote rows'
    """
    import re
    s = str(raw or "")
    if not s:
        return ""
    # Split composite keys joined by '::'
    parts = s.split("::")
    # Determine the most specific label (last part) and an optional column/source
    label_part = parts[-1]
    source_part = None
    # Try to detect a column from earlier parts (look for *_format or *_regex)
    for p in parts[:-1]:
        if p.endswith("_format"):
            source_part = p[: -len("_format")]
            break
        if p.endswith("_regex"):
            source_part = p[: -len("_regex")]
            break
        # common section names like 'candidate_running_mates' are useful as source
        if p in ("candidate", "votes", "candidate_running_mates"):
            source_part = p
            break

    # Clean label part: replace underscores with spaces, lower-case, and tidy spacing
    lab = re.sub(r"[_]+", " ", label_part).strip()
    lab = lab.strip()
    # Normalize case: lowercase then capitalize first char
    lab_norm = lab.lower().capitalize()
    # If label contains parentheses or special markers, keep them but clean spacing
    lab_norm = re.sub(r"\s+\(", " (", lab_norm)

    if source_part:
        col = source_part.replace("_", " ").title()
        return f"{lab_norm} ({col})"

    # Fallback: if the original name is snake_case, make it human
    if "_" in s and "::" not in s:
        return s.replace("_", " ").capitalize()
    return lab_norm


def _extract_variables_from_check(raw: str) -> str:
    """Attempt to infer which dataset variables/columns a given check refers to.

    This is a best-effort parser that looks for prefixes like
    '<column>_format', '<column>_missing', or composite keys joined by
    '::'. Returns a human-friendly, comma-separated short list or an
    empty string when nothing obvious can be inferred.
    """
    if not raw:
        return ""
    s = str(raw)
    # Composite keys like 'candidate_format::ODD_...' or 'candidate::SOMETHING'
    if "::" in s:
        first = s.split("::", 1)[0]
    else:
        first = s
    # If something like '<col>_format' or '<col>_missing'
    for suffix in ("_format", "_regex", "_missing", "_invalid", "_rows"):
        if first.endswith(suffix):
            return first[: -len(suffix)].replace("_", " ").title()
    # If underscore-separated, and looks like a single column name, return it
    if "_" in first and len(first.split("_")) <= 3:
        return first.replace("_", " ").title()
    # If camel or plain single token, return title-cased
    return first.replace("_", " ").title()


# ---------------------------------------------------------------------
# Excel report writer
# ---------------------------------------------------------------------

def write_excel_report(results: Dict[str, Any], path: pathlib.Path) -> None:
    """Write human-readable Excel QA report (v3.5)."""
    excluded_sections = {"statewide_totals", "duplicates_summary", "missingness", "dataset_info"}
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
                # Avoid duplicating missingness: if this is a `*_missing` check
                # coming from `field_formats` and we also have a `missingness`
                # section for the same column, skip the `field_formats` missing
                # row to reduce redundancy in the summary.
                if section == "field_formats" and isinstance(check, str) and check.endswith("_missing"):
                    col = check[: -len("_missing")]
                    if "missingness" in results and col in results["missingness"]:
                        continue

                # Use explicit '<EMPTY>' marker for issue values so that
                # repeated empty values can be compressed into '<EMPTY> × n'.
                issue_values = "" if check in ("exact_duplicates", "all_but_votes_duplicate") else _flatten(v.get("issue_values", ""), show_empty_marker=True)
                rows.append({
                    "section": section,
                    "check": check,
                    "issues": int(v.get("issues", 0) or 0),
                    "issue_values": issue_values,
                    "issue_row_numbers": _flatten(v.get("issue_row_numbers", "")),
                    # Best-effort variables/columns this check targets
                    "variables": _extract_variables_from_check(check),
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

        df = pd.DataFrame(rows, columns=["section", "check", "issues", "issue_values", "issue_row_numbers", "variables"])
        df["issues"] = df["issues"].fillna(0).astype(int)
        # Preserve '<EMPTY>' markers here so compression logic can convert
        # repeated empty entries into '<EMPTY> × n'. Do not strip the marker.
        df["issue_values"] = df["issue_values"].fillna("")
        df["issue_row_numbers"] = df["issue_row_numbers"].fillna("<EMPTY>").replace("", "<EMPTY>")
        # Apply general compression: collapse repeated tokens into 'value × n'
        df["issue_values"] = df.apply(_condense_issue_values_row, axis=1)

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
            "check": "Check",
            "issues": "Issues Found",
            "issue_values": "Problematic Values",
            "issue_row_numbers": "Row Numbers",
            "variables": "Variables",
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
        # Dataset-level info (rows/columns/unique counts) if provided
        dataset_info = results.get("dataset_info", {})

        # Gather failed checks names from all dict-based sections
        # Group failed checks by section so we show one line per section
        failed_by_section: dict[str, list[str]] = {}
        merge_sections = {"fields", "field_formats", "field_regex_checks"}
        for section, content in results.items():
            if isinstance(content, dict):
                for check, v in content.items():
                    try:
                        issues = int(v.get("issues", 0) or 0)
                    except Exception:
                        issues = 0
                    if issues > 0:
                        # Map merged field-level sections into a single 'Field Checks' group
                        pretty = _pretty_check_name(check)
                        if section in merge_sections:
                            failed_by_section.setdefault("Field Checks", []).append(pretty)
                        else:
                            failed_by_section.setdefault(section, []).append(pretty)

        # Count total failed checks
        failed_checks = sum(len(v) for v in failed_by_section.values())

        # Build a compact meta table to display in QA Summary
        meta_items = []
        if dataset_info:
            meta_items.extend([
                ["Rows", str(dataset_info.get("rows", ""))],
                ["Columns", str(dataset_info.get("columns", ""))],
                ["Unique Counties", str(dataset_info.get("unique_counties", ""))],
                ["Unique Jurisdictions", str(dataset_info.get("unique_jurisdictions", ""))],
            ])

        meta_items.append(["Failed Checks", str(failed_checks)])

        # Format failed checks grouped by section; insert a blank line between sections
        if failed_by_section:
            lines = []
            for sec, checks in failed_by_section.items():
                lines.append(f"{sec}: {', '.join(checks)}")
            grouped = "\n\n".join(lines)
        else:
            grouped = ""

        # Note: detailed failed-checks list is written separately into the
        # QA Summary sheet (see below) to keep the overview compact.
        meta_df = pd.DataFrame(meta_items, columns=["Info", "Value"])

        # Combine state banner and meta into one concise overview table
        overview_df = pd.concat([state_banner, meta_df], ignore_index=True)

        # Build a vertical list of failed checks (one per row) with separate
        # 'Section' and 'Check' columns for readability. We'll link Section
        # entries to their corresponding sheets below.
        failed_rows = []
        for sec, checks in failed_by_section.items():
            for chk in checks:
                failed_rows.append({"Section": sec, "Check": chk})
        failed_df = pd.DataFrame(failed_rows) if failed_rows else pd.DataFrame({"Section": [], "Check": []})

        # Reserve columns: TOC (left), Overview (middle), Failed Checks (right)
        toc_col = 0
        summary_col = 3
        failed_col = summary_col + 4

        # Write overview and failed-checks into the QA Summary sheet
        overview_df.to_excel(writer, index=False, sheet_name="QA Summary", startrow=0, startcol=summary_col)
        failed_df.to_excel(writer, index=False, sheet_name="QA Summary", startrow=0, startcol=failed_col)

        wb = writer.book
        ws = writer.sheets["QA Summary"]

        header_fmt = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "text_wrap": True})
        wrap_fmt = wb.add_format({"text_wrap": True})
        try:
            ws.set_column(toc_col, toc_col, 28)
            ws.set_column(summary_col, summary_col + 1, 40, wrap_fmt)
            ws.set_column(failed_col, failed_col + 1, 40, wrap_fmt)
        except Exception:
            pass

        # Highlight failed checks count cell inside overview (if present)
        try:
            failed_checks_val = int(failed_checks)
        except Exception:
            failed_checks_val = 0
        if failed_checks_val > 0:
            fail_fmt = wb.add_format({"font_color": "#9C0006", "bg_color": "#FFC7CE", "bold": True})
            try:
                idx_failed = int(overview_df.index[overview_df["Info"] == "Failed Checks"].tolist()[0])
                ws.write(1 + idx_failed, summary_col + 1, str(failed_checks_val), fail_fmt)
            except Exception:
                pass

        # Highlight columns mismatch against expected count from config if available
        from qa_core import config as _config
        try:
            expected_cols = len(_config.REQUIRED_COLUMNS)
            actual_cols = int(dataset_info.get("columns", 0)) if dataset_info else 0
            if actual_cols != expected_cols:
                col_fmt = wb.add_format({"font_color": "#9C0006", "bg_color": "#FFC7CE", "bold": True})
                try:
                    idx_cols = int(overview_df.index[overview_df["Info"] == "Columns"].tolist()[0])
                    ws.write(1 + idx_cols, summary_col + 1, str(actual_cols), col_fmt)
                except Exception:
                    pass
        except Exception:
            pass

        # --- Extra sheets ---
        name_map = {
            "statewide_totals": "Vote Aggregation",
            "duplicates": "Duplicates",
            # Friendly sheet names
            "zero_vote_precincts": "Zero Votes",
            "unique_values": "Unique",
            "magnitude_offices_map": "Mag Offices",
            "offices_multiple_magnitudes": "Multi-Mag Offices",
            "stage_invalid_rows": "Stage Issues",
        }

        def _autosize_sheet(sheet_name: str, df_table: pd.DataFrame):
            """Set reasonable column widths and wrap text for a written sheet.

            Widths are based on the max length of values in each column,
            capped between 12 and 60 characters.
            """
            ws = writer.sheets.get(sheet_name)
            if ws is None:
                return
            wb = writer.book
            wrap_fmt = wb.add_format({"text_wrap": True})
            # sensible min/max bounds (chars)
            min_w, max_w = 8, 80
            for i, col in enumerate(df_table.columns):
                # Compute max length from header and column values, accounting
                # for multi-line cells — measure the longest line.
                try:
                    vals = df_table[col].astype(str).fillna("").tolist()
                except Exception:
                    vals = [str(x) for x in df_table[col].tolist()]
                max_len = len(str(col))
                wrap_needed = False
                for v in vals:
                    if not v:
                        continue
                    # consider multi-line cells
                    parts = str(v).splitlines()
                    for p in parts:
                        l = len(p)
                        if l > max_len:
                            max_len = l
                    if len(parts) > 1:
                        wrap_needed = True

                # Heuristic: shrink numeric-looking columns slightly
                is_numeric = False
                try:
                    series = df_table[col]
                    if pd.api.types.is_numeric_dtype(series):
                        is_numeric = True
                    else:
                        non_empty = [x for x in vals if x.strip()]
                        if non_empty:
                            digit_like = sum(1 for x in non_empty if str(x).replace('.', '', 1).replace('-', '', 1).isdigit())
                            if digit_like / len(non_empty) > 0.9:
                                is_numeric = True
                except Exception:
                    is_numeric = False

                # Add a small cushion and clamp
                cushion = 2 if is_numeric else 4
                width = min(max(max_len + cushion, min_w), max_w)
                # Apply wrap format if any cell contains newlines or the text is long
                fmt = wrap_fmt if wrap_needed or width > 30 else None
                # set column (xlsxwriter set_column takes first_col, last_col, width, cell_format)
                try:
                    if fmt is not None:
                        ws.set_column(i, i, width, fmt)
                    else:
                        ws.set_column(i, i, width)
                except Exception:
                    # fall back to a safe fixed width
                    try:
                        ws.set_column(i, i, min(40, max(width, 12)))
                    except Exception:
                        pass

        # Build list of DataFrame sheets to write (including Missingness as its own sheet)
        df_sheets: list[tuple[str, pd.DataFrame]] = []

        # Merge field-level sections into a single sheet for clarity.
        # Combine `fields`, `field_formats`, and `field_regex_checks` into
        # one compact `Field Checks` sheet containing only checks with
        # issues (>0). When multiple sections report the same `Check Name`,
        # keep the entry with the largest `Issues Found` to avoid redundancy.
        merged_field_rows = []
        for merge_section in ("fields", "field_formats", "field_regex_checks"):
            content = results.get(merge_section, {})
            if not isinstance(content, dict):
                continue
            for check, v in content.items():
                if not isinstance(v, dict):
                    continue
                # Skip missingness rows coming from field_formats (we have a Missingness sheet)
                if merge_section == "field_formats" and isinstance(check, str) and check.endswith("_missing"):
                    continue
                try:
                    issues = int(v.get("issues", 0) or 0)
                except Exception:
                    issues = 0
                # Only include checks that actually found issues
                if issues <= 0:
                    continue
                issue_values = _flatten(v.get("issue_values", ""), show_empty_marker=True)
                merged_field_rows.append({
                    "Section": merge_section,
                    "Check Name": check,
                    "Issues Found": issues,
                    "Problematic Values": issue_values,
                    "Row Numbers": _flatten(v.get("issue_row_numbers", "")),
                    "variables": _extract_variables_from_check(check),
                })

        if merged_field_rows:
            merged_df = pd.DataFrame(merged_field_rows)
            # Convert internal check identifiers to concise human-friendly labels
            try:
                if "Check Name" in merged_df.columns:
                    merged_df["Check"] = merged_df["Check Name"].apply(lambda x: _pretty_check_name(x) if isinstance(x, str) else _pretty_check_name(str(x)))
                    merged_df = merged_df.drop(columns=["Check Name"])
                # Drop the now-redundant Section column to keep the sheet compact
                if "Section" in merged_df.columns:
                    merged_df = merged_df.drop(columns=["Section"])
                # Expose inferred variables column with a friendly header
                if "variables" in merged_df.columns:
                    merged_df = merged_df.rename(columns={"variables": "Variables"})
            except Exception:
                # If anything goes wrong, fall back to the original names
                pass
            # Attempt to collapse highly-overlapping checks (likely duplicates)
            try:
                def _parse_rows(val):
                    if not val or val in ("<EMPTY>", ""):
                        return set()
                    parts = [p.strip() for p in str(val).replace('...', '').split(',') if p.strip()]
                    nums = set()
                    for p in parts:
                        if '-' in p:
                            try:
                                a, b = p.split('-', 1)
                                a = int(a); b = int(b)
                                nums.update(range(a, b+1))
                            except Exception:
                                continue
                        else:
                            try:
                                nums.add(int(p))
                            except Exception:
                                continue
                    return nums

                merged_df = merged_df.sort_values("Issues Found", ascending=False).reset_index(drop=True)
                remove_idx = set()
                row_sets = [ _parse_rows(r) for r in merged_df['Row Numbers'].tolist() ]
                for i in range(len(merged_df)):
                    if i in remove_idx:
                        continue
                    si = row_sets[i]
                    if not si:
                        continue
                    for j in range(i+1, len(merged_df)):
                        if j in remove_idx:
                            continue
                        sj = row_sets[j]
                        if not sj:
                            continue
                        inter = si & sj
                        if not inter:
                            continue
                        # If overlap covers at least half of the smaller set, treat as duplicate
                        if len(inter) >= 0.5 * min(len(si), len(sj)):
                            # remove the one with fewer issues (j will have <= because of sort)
                            remove_idx.add(j)
                if remove_idx:
                    merged_df = merged_df.drop(index=list(remove_idx)).reset_index(drop=True)
                # Final de-dup by check name keep highest-issue version
                merged_df = merged_df.sort_values("Issues Found", ascending=False).drop_duplicates(subset=["Check Name"], keep="first").reset_index(drop=True)
            except Exception:
                # Fall back to simple dedupe
                try:
                    merged_df = merged_df.sort_values("Issues Found", ascending=False).drop_duplicates(subset=["Check Name"], keep="first").reset_index(drop=True)
                except Exception:
                    pass
            # Friendly sheet name
            df_sheets.append(("Field Checks", merged_df))

        # Convert missingness dict into a DataFrame sheet if present
        if "missingness" in results and isinstance(results["missingness"], dict):
            miss = results["missingness"]
            miss_rows = []
            for col_name, v in miss.items():
                if isinstance(v, dict):
                    miss_rows.append({
                        "Column": col_name,
                        "Missing Count": v.get("missing_count", ""),
                        "% Missing": v.get("percent_empty", ""),
                        "Alt Missing Values": v.get("alt_missing_values", ""),
                    })
                else:
                    miss_rows.append({"Column": col_name, "Missing Count": "", "% Missing": "", "Alt Missing Values": ""})
            miss_df = pd.DataFrame(miss_rows)
            df_sheets.append(("Missingness", miss_df))

        # Convert dict-based sections (that are not DataFrames) into sheets
        # Skip sections already merged into the `Field Checks` sheet.
        merge_sections = {"fields", "field_formats", "field_regex_checks"}
        for section, content in results.items():
            if section in merge_sections:
                continue
            if section in {"duplicates_summary", "missingness", "dataset_info"}:
                continue
            if isinstance(content, dict):
                # Special-case office_mappings: render one row per problematic
                # observed office with suggested mapping and score for clarity.
                if section == "office_mappings":
                    rows_sec = []
                    for check, v in content.items():
                        if not isinstance(v, dict):
                            continue
                        mapping_suggestions = v.get("mapping_suggestions", {}) or {}
                        unmatched_counts = v.get("unmatched_counts", {}) or {}
                        # Build one row per observed unmatched office
                        for obs, sug in mapping_suggestions.items():
                            rows_sec.append({
                                "Observed Office": obs,
                                "Count": int(unmatched_counts.get(obs, 0) or 0),
                                "Suggested Mapping": sug.get("suggested", ""),
                            })
                    if rows_sec:
                        sec_name = name_map.get(section, section.replace("_", " ").title())[:31]
                        df_sheets.append((sec_name, pd.DataFrame(rows_sec)))
                    continue
                # Generic handling: Build a DataFrame of checks for this section
                rows_sec = []
                for check, v in content.items():
                    if not isinstance(v, dict):
                        continue
                    # Skip checks with zero issues for the large field_regex_checks
                    if section == "field_regex_checks":
                        try:
                            if int(v.get("issues", 0) or 0) == 0:
                                continue
                        except Exception:
                            pass
                    # For field_formats, skip any missingness rows (we have a
                    # dedicated Missingness sheet)
                    if section == "field_formats" and isinstance(check, str) and check.endswith("_missing"):
                        continue
                    # Preserve explicit '<EMPTY>' markers for problematic values
                    # so they can be compressed into '<EMPTY> × n' in the sheet.
                    issue_values = _flatten(v.get("issue_values", ""), show_empty_marker=True)
                    rows_sec.append({
                        "Check": _pretty_check_name(check),
                        "Variables": _extract_variables_from_check(check),
                        "Issues Found": int(v.get("issues", 0) or 0),
                        "Problematic Values": issue_values,
                        "Row Numbers": _flatten(v.get("issue_row_numbers", "")),
                    })
                if rows_sec:
                    sec_name = name_map.get(section, section.replace("_", " ").title())[:31]
                    df_table = pd.DataFrame(rows_sec)
                    # Show checks with issues at the top to aid triage
                    if "Issues Found" in df_table.columns:
                        try:
                            df_table = df_table.sort_values("Issues Found", ascending=False).reset_index(drop=True)
                        except Exception:
                            pass
                    df_sheets.append((sec_name, df_table))
                continue
            # If the section already contains a DataFrame, write it as-is
            if isinstance(content, pd.DataFrame) and not content.empty:
                name = name_map.get(section, section)[:31]
                df_sheets.append((name, content))

        # Write DataFrame sheets in alphabetical order
        df_sheets.sort(key=lambda x: x[0].lower())

        # --- Table of Contents on QA Summary (left) ---
        toc_col = 0
        try:
            ws.write(0, toc_col, "Table of Contents", header_fmt)
            link_fmt = wb.add_format({"font_color": "#0563C1", "underline": True})
            row_idx = 1
            for name, table in df_sheets:
                sheet_name = name[:31]
                # Do not include the 'Failed Checks' table (it's embedded in QA Summary)
                if sheet_name == "QA Summary":
                    continue
                url = f"internal:'{sheet_name}'!A1"
                ws.write_url(row_idx, toc_col, url, link_fmt, sheet_name)
                row_idx += 1
        except Exception:
            pass
        # After constructing df_sheets, link the QA Summary 'Section' entries
        # in the failed-checks table to their corresponding sheets.
        try:
            # Determine the starting column where we wrote the failed_df
            # (must match the values used above when writing overview/failed_df)
            summary_col = 3
            failed_col = summary_col + 4
            failed_startrow = 0
            # Write hyperlinks into the Section column for each failed-check row
            if not failed_df.empty:
                # map section label to sheet name used in df_sheets/name_map
                sheet_name_map = {}
                for name, _ in df_sheets:
                    sheet_name_map[name] = name
                for r_idx, row in failed_df.iterrows():
                    sec_label = str(row.get("Section", ""))
                    # Map 'Field Checks' directly; otherwise use name_map fallback
                    if sec_label == "Field Checks":
                        target = "Field Checks"
                    else:
                        target = name_map.get(sec_label, sec_label)
                    target = str(target)[:31]
                    try:
                        cell_row = failed_startrow + 1 + int(r_idx)
                        url = f"internal:'{target}'!A1"
                        ws.write_url(cell_row, failed_col, url, link_fmt, target)
                    except Exception:
                        # If hyperlinking fails, leave plain text
                        try:
                            ws.write(cell_row, failed_col, sec_label)
                        except Exception:
                            pass
        except Exception:
            pass

        # Before writing, condense repeated problematic values in each sheet
        for i, (name, table) in enumerate(df_sheets):
            # operate on a copy to avoid side effects
            table = table.copy()
            if 'Problematic Values' in table.columns:
                try:
                    table['Problematic Values'] = table.apply(
                        lambda r: _condense_issue_values_row({
                            'issue_values': r.get('Problematic Values', ''),
                            'issues': int(r.get('Issues Found', 0) or 0)
                        }),
                        axis=1
                    )
                except Exception:
                    pass
                # If a check reports zero issues, leave the problematic-values
                # cell blank (do not show '<EMPTY>' which indicates a real
                # missing value in the dataset).
                try:
                    if 'Issues Found' in table.columns:
                        table.loc[table['Issues Found'] == 0, 'Problematic Values'] = ""
                except Exception:
                    pass
            if 'issue_values' in table.columns:
                try:
                    table['issue_values'] = table.apply(
                        lambda r: _condense_issue_values_row({
                            'issue_values': r.get('issue_values', ''),
                            'issues': int(r.get('issues', 0) or 0)
                        }),
                        axis=1
                    )
                except Exception:
                    pass
                try:
                    if 'issues' in table.columns:
                        table.loc[table['issues'] == 0, 'issue_values'] = ""
                except Exception:
                    pass

            sheet_name = name[:31]
            table.to_excel(writer, index=False, sheet_name=sheet_name)
            _autosize_sheet(sheet_name, table)
            # Freeze header row for the Unique sheet for easier browsing
            try:
                if sheet_name in ("Unique", "Unique Values"):
                    ws_uv = writer.sheets.get(sheet_name)
                    if ws_uv is not None:
                        ws_uv.freeze_panes(1, 0)
            except Exception:
                pass

    print(f"Excel report written to {path}")
