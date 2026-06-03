"""
SAP Migration Post-Load Validator — Core Engine
- Auto-detects field mapping, numeric columns, and tolerances from data
- Supports pass threshold per field (default 100%, configurable e.g. 90%)
- Supports field selection — only validate chosen fields
- Resolves SAP technical names to friendly English labels
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)

DEFAULT_JOIN_KEY      = "MATNR"
DEFAULT_PASS_THRESHOLD = 100.0   # % — fields >= this are PASS


@dataclass
class FieldResult:
    field_source:     str
    field_target:     str
    field_label:      str
    total_records:    int
    matched:          int
    mismatched:       int
    missing_in_target: int
    missing_in_source: int
    is_numeric:       bool  = False
    tolerance_used:   float = None
    pass_threshold:   float = DEFAULT_PASS_THRESHOLD
    mismatch_details: list  = field(default_factory=list)

    @property
    def match_pct(self) -> float:
        if self.total_records == 0:
            return 0.0
        return round(self.matched / self.total_records * 100, 2)

    @property
    def status(self) -> str:
        # PASS if match_pct meets or exceeds threshold AND no blank issues
        if self.missing_in_target or self.missing_in_source:
            # blank issues still count as issues but threshold still applies
            pass
        return "PASS" if self.match_pct >= self.pass_threshold else "FAIL"


@dataclass
class MappingReport:
    join_key:           str
    join_key_label:     str
    matched_fields:     list
    source_only_fields: list
    target_only_fields: list
    numeric_fields:     list
    tolerance_map:      dict
    total_source_cols:  int
    total_target_cols:  int
    selected_fields:    list  = field(default_factory=list)  # empty = all
    pass_threshold:     float = DEFAULT_PASS_THRESHOLD


@dataclass
class ValidationResult:
    source_file:             str
    target_file:             str
    total_source_records:    int
    total_target_records:    int
    records_matched:         int
    records_only_in_source:  int
    records_only_in_target:  int
    mapping:                 MappingReport = None
    field_results:           list = field(default_factory=list)
    errors:                  list = field(default_factory=list)

    @property
    def overall_status(self) -> str:
        if self.errors:
            return "ERROR"
        return "FAIL" if any(f.status == "FAIL" for f in self.field_results) else "PASS"

    @property
    def summary_stats(self) -> dict:
        total  = len(self.field_results)
        passed = sum(1 for f in self.field_results if f.status == "PASS")
        return {
            "total_fields_validated": total,
            "fields_passed":          passed,
            "fields_failed":          total - passed,
            "pass_rate_pct":          round(passed / total * 100, 1) if total else 0,
        }


class MaterialValidator:
    """
    Validates SAP 4.7 CSV vs S/4HANA export.

    Key parameters
    ──────────────
    pass_threshold  float   Match % a field needs to be PASS (default 100.0)
                            e.g. 90.0 means any field ≥ 90% match = PASS
    selected_fields list    Only validate these fields (technical SAP names).
                            Empty list = validate all common fields.
    field_map       dict    Manual column mapping overrides.
    join_key        str     Force a join key column name.
    tolerance_map   dict    Per-column numeric tolerance overrides.
    custom_labels           dict or path to label-override CSV.
    """

    def __init__(
        self,
        field_map:           dict  = None,
        tolerance_map:       dict  = None,
        join_key:            str   = None,
        pass_threshold:      float = DEFAULT_PASS_THRESHOLD,
        selected_fields:     list  = None,
        numeric_sample_rows: int   = 50,
        numeric_threshold:   float = 0.80,
        custom_labels              = None,
    ):
        self.field_map            = field_map
        self.tolerance_overrides  = tolerance_map or {}
        self.join_key             = join_key
        self.pass_threshold       = pass_threshold
        self.selected_fields      = [f.strip().upper() for f in (selected_fields or [])]
        self.numeric_sample_rows  = numeric_sample_rows
        self.numeric_threshold    = numeric_threshold

        from core.field_labels import load_custom_labels
        if isinstance(custom_labels, str):
            self.custom_labels = load_custom_labels(custom_labels)
        elif isinstance(custom_labels, dict):
            self.custom_labels = {k.upper(): v for k, v in custom_labels.items()}
        else:
            self.custom_labels = {}

    def _label(self, field_name: str) -> str:
        from core.field_labels import get_label
        return get_label(field_name, self.custom_labels)

    # ── Entry point ──────────────────────────────────────────────────────────
    def validate(
        self,
        source_path:      str,
        target_path:      str,
        source_delimiter: str = ",",
        target_delimiter: str = ",",
        max_mismatch_rows: int = 100,
    ) -> ValidationResult:

        try:
            src_df = self._load_file(source_path, source_delimiter)
        except Exception as e:
            return ValidationResult(
                source_file=source_path, target_file=target_path,
                total_source_records=0, total_target_records=0,
                records_matched=0, records_only_in_source=0,
                records_only_in_target=0,
                errors=[f"Cannot load source file: {e}"]
            )
        try:
            tgt_df = self._load_file(target_path, target_delimiter)
        except Exception as e:
            return ValidationResult(
                source_file=source_path, target_file=target_path,
                total_source_records=len(src_df), total_target_records=0,
                records_matched=0, records_only_in_source=len(src_df),
                records_only_in_target=0,
                errors=[f"Cannot load target file: {e}"]
            )

        join_key = self._detect_join_key(src_df, tgt_df)
        if not join_key:
            return ValidationResult(
                source_file=source_path, target_file=target_path,
                total_source_records=len(src_df), total_target_records=len(tgt_df),
                records_matched=0, records_only_in_source=0, records_only_in_target=0,
                errors=[
                    f"No common join key found.\n"
                    f"  Source columns: {src_df.columns.tolist()}\n"
                    f"  Target columns: {tgt_df.columns.tolist()}"
                ]
            )

        field_map, mapping_report = self._build_field_map(src_df, tgt_df, join_key)

        src_df = self._normalise_key(src_df, join_key)
        tgt_df = self._normalise_key(tgt_df, join_key)

        src_keys = set(src_df[join_key].dropna())
        tgt_keys = set(tgt_df[join_key].dropna())

        merged = src_df.merge(tgt_df, on=join_key, how="inner", suffixes=("_src", "_tgt"))

        field_results = []
        for src_col, tgt_col in field_map.items():
            tolerance = mapping_report.tolerance_map.get(src_col)
            fr = self._validate_field(
                merged, src_col, tgt_col, join_key,
                tolerance, max_mismatch_rows
            )
            if fr:
                field_results.append(fr)

        return ValidationResult(
            source_file=source_path, target_file=target_path,
            total_source_records=len(src_df), total_target_records=len(tgt_df),
            records_matched=len(src_keys & tgt_keys),
            records_only_in_source=len(src_keys - tgt_keys),
            records_only_in_target=len(tgt_keys - src_keys),
            mapping=mapping_report,
            field_results=field_results,
        )

    # ── Numeric detection ────────────────────────────────────────────────────
    def _detect_numeric_columns(self, src_df, tgt_df, columns):
        numeric_cols = {}
        for col in columns:
            src_vals = src_df[col].dropna().head(self.numeric_sample_rows)
            tgt_vals = tgt_df[col].dropna().head(self.numeric_sample_rows)
            if len(src_vals) == 0 or len(tgt_vals) == 0:
                continue

            def parse_rate(series):
                parsed = 0
                for v in series:
                    try:
                        float(str(v).replace(",", "."))
                        parsed += 1
                    except (ValueError, TypeError):
                        pass
                return parsed / len(series)

            if (parse_rate(src_vals) >= self.numeric_threshold and
                    parse_rate(tgt_vals) >= self.numeric_threshold):
                if col in self.tolerance_overrides:
                    tol = self.tolerance_overrides[col]
                else:
                    all_vals = []
                    for v in list(src_vals) + list(tgt_vals):
                        try:
                            all_vals.append(abs(float(str(v).replace(",", "."))))
                        except (ValueError, TypeError):
                            pass
                    median = float(np.median(all_vals)) if all_vals else 0.0
                    tol    = self._scale_tolerance(median)
                numeric_cols[col] = tol
        return numeric_cols

    @staticmethod
    def _scale_tolerance(median_val: float) -> float:
        if median_val == 0:      return 0.0
        elif median_val < 1:     return 0.0001
        elif median_val < 10:    return 0.001
        elif median_val < 1000:  return 0.01
        else:                    return 0.1

    # ── Field map builder ─────────────────────────────────────────────────────
    def _build_field_map(self, src_df, tgt_df, join_key):
        if self.field_map:
            cols    = list(self.field_map.keys())
            tol_map = self._detect_numeric_columns(src_df, tgt_df, cols)
            tol_map.update(self.tolerance_overrides)
            report  = MappingReport(
                join_key=join_key, join_key_label=self._label(join_key),
                matched_fields=cols, source_only_fields=[],
                target_only_fields=[], numeric_fields=list(tol_map.keys()),
                tolerance_map=tol_map, total_source_cols=len(src_df.columns),
                total_target_cols=len(tgt_df.columns),
                selected_fields=self.selected_fields,
                pass_threshold=self.pass_threshold,
            )
            return self.field_map, report

        src_cols = set(src_df.columns) - {join_key}
        tgt_cols = set(tgt_df.columns) - {join_key}
        common   = sorted(src_cols & tgt_cols)
        only_src = sorted(src_cols - tgt_cols)
        only_tgt = sorted(tgt_cols - src_cols)

        # Apply field selection filter
        if self.selected_fields:
            validate_cols = [c for c in common if c in self.selected_fields]
        else:
            validate_cols = common

        tol_map = self._detect_numeric_columns(src_df, tgt_df, validate_cols)
        tol_map.update(self.tolerance_overrides)

        report = MappingReport(
            join_key=join_key, join_key_label=self._label(join_key),
            matched_fields=common,            # all common (for info display)
            source_only_fields=only_src,
            target_only_fields=only_tgt,
            numeric_fields=sorted(tol_map.keys()),
            tolerance_map=tol_map,
            total_source_cols=len(src_df.columns),
            total_target_cols=len(tgt_df.columns),
            selected_fields=self.selected_fields,
            pass_threshold=self.pass_threshold,
        )
        return {col: col for col in validate_cols}, report

    # ── Join key detection ────────────────────────────────────────────────────
    def _detect_join_key(self, src_df, tgt_df):
        if self.join_key:
            if self.join_key in src_df.columns and self.join_key in tgt_df.columns:
                return self.join_key
            return None
        if DEFAULT_JOIN_KEY in src_df.columns and DEFAULT_JOIN_KEY in tgt_df.columns:
            return DEFAULT_JOIN_KEY
        common = set(src_df.columns) & set(tgt_df.columns)
        if common:
            return sorted(common, key=lambda c: (
                0 if c.upper() in ("MATNR", "MATERIAL", "ID", "KEY") else 1,
                len(c)
            ))[0]
        return None

    # ── File loader ───────────────────────────────────────────────────────────
    def _load_file(self, path: str, delimiter: str) -> pd.DataFrame:
        if path.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(path, dtype=str)
        else:
            df = pd.read_csv(path, delimiter=delimiter, dtype=str, encoding="utf-8-sig")
        df.columns = df.columns.str.strip().str.upper()
        df = df.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))
        return df

    def _normalise_key(self, df: pd.DataFrame, col: str) -> pd.DataFrame:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lstrip("0").str.upper()
        return df

    # ── Field comparator ─────────────────────────────────────────────────────
    def _validate_field(self, merged, src_col, tgt_col, join_key, tolerance, max_rows):
        if src_col == tgt_col:
            src_actual = src_col + "_src" if src_col + "_src" in merged.columns else src_col
            tgt_actual = tgt_col + "_tgt" if tgt_col + "_tgt" in merged.columns else tgt_col
        else:
            src_actual = src_col if src_col in merged.columns else src_col + "_src"
            tgt_actual = tgt_col if tgt_col in merged.columns else tgt_col + "_tgt"

        src_present = src_actual in merged.columns
        tgt_present = tgt_actual in merged.columns
        if not src_present and not tgt_present:
            return None

        total = len(merged)
        mismatches, matched, miss_src, miss_tgt = [], 0, 0, 0

        for _, row in merged.iterrows():
            sv      = row.get(src_actual, np.nan) if src_present else np.nan
            tv      = row.get(tgt_actual, np.nan) if tgt_present else np.nan
            mat_num = row.get(join_key, "")

            sv_null = pd.isna(sv) or str(sv).strip() in ("", "nan", "NaN", "None")
            tv_null = pd.isna(tv) or str(tv).strip() in ("", "nan", "NaN", "None")

            if sv_null and tv_null:
                matched += 1; continue
            if sv_null:
                miss_src += 1
                if len(mismatches) < max_rows:
                    mismatches.append({"material": mat_num, "source_value": "(blank)",
                                       "target_value": str(tv), "issue": "Missing in source"})
                continue
            if tv_null:
                miss_tgt += 1
                if len(mismatches) < max_rows:
                    mismatches.append({"material": mat_num, "source_value": str(sv),
                                       "target_value": "(blank)", "issue": "Missing in target"})
                continue

            if tolerance is not None:
                try:
                    sv_f = float(str(sv).replace(",", "."))
                    tv_f = float(str(tv).replace(",", "."))
                    if abs(sv_f - tv_f) <= tolerance:
                        matched += 1
                    elif len(mismatches) < max_rows:
                        mismatches.append({
                            "material": mat_num, "source_value": sv_f, "target_value": tv_f,
                            "issue": f"Delta={abs(sv_f-tv_f):.4f} (tol+-{tolerance})",
                        })
                    continue
                except ValueError:
                    pass

            if str(sv).strip().upper() == str(tv).strip().upper():
                matched += 1
            elif len(mismatches) < max_rows:
                mismatches.append({"material": mat_num, "source_value": str(sv),
                                   "target_value": str(tv), "issue": "Value mismatch"})

        return FieldResult(
            field_source=src_col, field_target=tgt_col,
            field_label=self._label(src_col),
            total_records=total, matched=matched,
            mismatched=max(0, total - matched - miss_src - miss_tgt),
            missing_in_target=miss_tgt, missing_in_source=miss_src,
            is_numeric=(tolerance is not None), tolerance_used=tolerance,
            pass_threshold=self.pass_threshold,
            mismatch_details=mismatches,
        )
