"""
SAP Migration Post-Load Validator - Live Dashboard
Run:  python dashboard/app.py
Open: http://localhost:5000
"""

import sys
import threading
import time
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, send_file, request, Response

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.validator import MaterialValidator
from core.reporter import generate_excel_report


app = Flask(__name__)

BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "reports"
CONFIG_FILE = BASE_DIR / "config.json"
LABELS_FILE = BASE_DIR / "custom_labels.csv"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "source_dir": str(BASE_DIR / "data" / "source"),
    "target_dir": str(BASE_DIR / "data" / "target"),
    "pass_threshold": 100.0,
    "selected_fields": [],  # empty = all fields
}

results_store = {}
scan_status = {
    "last_scan": None,
    "scanning": False,
    "error": None,
}
file_states = {}
activity_log = []

SUPPORTED_EXT = {".csv", ".xlsx", ".xls"}

# This prevents multiple scans from running at the same time
scan_lock = threading.Lock()


def load_config():
    if CONFIG_FILE.exists():
        try:
            return {**DEFAULT_CONFIG, **json.loads(CONFIG_FILE.read_text())}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def get_dirs():
    cfg = load_config()

    src = Path(cfg.get("source_dir", DEFAULT_CONFIG["source_dir"]))
    tgt = Path(cfg.get("target_dir", DEFAULT_CONFIG["target_dir"]))

    src.mkdir(parents=True, exist_ok=True)
    tgt.mkdir(parents=True, exist_ok=True)

    return src, tgt


def log_event(message, level="info"):
    entry = {
        "ts": datetime.now().strftime("%H:%M:%S"),
        "message": message,
        "level": level,
    }

    activity_log.append(entry)

    if len(activity_log) > 50:
        activity_log.pop(0)

    print(f"  [{entry['ts']}] {message}")


def discover_pairs():
    SOURCE_DIR, TARGET_DIR = get_dirs()

    src_files = {
        f.stem.upper(): f
        for f in SOURCE_DIR.iterdir()
        if f.suffix.lower() in SUPPORTED_EXT
    }

    tgt_files = {
        f.stem.upper(): f
        for f in TARGET_DIR.iterdir()
        if f.suffix.lower() in SUPPORTED_EXT
    }

    pairs = []

    for name in sorted(set(src_files) | set(tgt_files)):
        sp = str(src_files[name]) if name in src_files else None
        tp = str(tgt_files[name]) if name in tgt_files else None

        has_pair = name in src_files and name in tgt_files

        if has_pair:
            mtime = max(Path(sp).stat().st_mtime, Path(tp).stat().st_mtime)
        else:
            mtime = None

        pairs.append(
            {
                "name": name,
                "source_path": sp,
                "target_path": tp,
                "has_pair": has_pair,
                "mtime": mtime,
                "source_file": Path(sp).name if sp else None,
                "target_file": Path(tp).name if tp else None,
            }
        )

    return pairs


def run_validation(name, source_path, target_path):
    cfg = load_config()

    pass_threshold = float(cfg.get("pass_threshold", 100.0))
    selected_fields = cfg.get("selected_fields", [])
    custom_labels = str(LABELS_FILE) if LABELS_FILE.exists() else None

    validator = MaterialValidator(
        pass_threshold=pass_threshold,
        selected_fields=selected_fields if selected_fields else None,
        custom_labels=custom_labels,
    )

    result = validator.validate(source_path, target_path)
    ss = result.summary_stats

    field_rows = []

    for fr in result.field_results:
        field_rows.append(
            {
                "field": fr.field_source,
                "field_label": fr.field_label,
                "field_target": fr.field_target,
                "type": "numeric" if fr.is_numeric else "string",
                "tolerance": fr.tolerance_used,
                "total": fr.total_records,
                "matched": fr.matched,
                "mismatched": fr.mismatched,
                "miss_source": fr.missing_in_source,
                "miss_target": fr.missing_in_target,
                "match_pct": fr.match_pct,
                "pass_threshold": fr.pass_threshold,
                "status": fr.status,
                "mismatches": fr.mismatch_details[:50],
            }
        )

    mapping = None

    if result.mapping:
        from core.field_labels import get_label, load_custom_labels

        custom = load_custom_labels(str(LABELS_FILE)) if LABELS_FILE.exists() else {}

        mapping = {
            "join_key": result.mapping.join_key,
            "join_key_label": result.mapping.join_key_label,
            "matched_fields": result.mapping.matched_fields,
            "matched_labels": {
                f: get_label(f, custom) for f in result.mapping.matched_fields
            },
            "source_only_fields": result.mapping.source_only_fields,
            "target_only_fields": result.mapping.target_only_fields,
            "numeric_fields": result.mapping.numeric_fields,
            "tolerance_map": result.mapping.tolerance_map,
            "selected_fields": result.mapping.selected_fields,
            "pass_threshold": result.mapping.pass_threshold,
        }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_filename = f"{name}_{ts}.xlsx"
    excel_path = REPORTS_DIR / excel_filename

    result_dict = {
        "name": name,
        "status": result.overall_status,
        "source_file": Path(source_path).name,
        "target_file": Path(target_path).name,
        "total_source_records": result.total_source_records,
        "total_target_records": result.total_target_records,
        "records_matched": result.records_matched,
        "records_only_in_source": result.records_only_in_source,
        "records_only_in_target": result.records_only_in_target,
        "fields_passed": ss["fields_passed"],
        "fields_failed": ss["fields_failed"],
        "total_fields": ss["total_fields_validated"],
        "pass_rate_pct": ss["pass_rate_pct"],
        "pass_threshold": pass_threshold,
        "selected_fields": selected_fields,
        "errors": result.errors,
        "mapping": mapping,
        "field_results": field_rows,
        "run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "excel_file": excel_filename,
    }

    try:
        generate_excel_report(result_dict, str(excel_path))
    except Exception as e:
        result_dict["excel_error"] = str(e)
        log_event(f"Excel failed for {name}: {e}", "error")

    return result_dict


def scan_and_validate_all():
    """
    Scans source and target folders and validates matching file pairs.

    Important:
    scan_lock prevents duplicate scans from running at the same time.
    This is the main fix for the long-running issue.
    """

    if not scan_lock.acquire(blocking=False):
        log_event("Scan already running — skipping duplicate scan", "warn")
        return

    scan_status["scanning"] = True
    scan_status["error"] = None

    try:
        pairs = discover_pairs()

        for pair in pairs:
            name = pair["name"]

            if not pair["has_pair"]:
                prev = file_states.get(name, {})

                if prev.get("state") != "unmatched":
                    side = "source" if pair["source_path"] else "target"
                    other = "target" if side == "source" else "source"

                    log_event(
                        f"{name}: found in {side} only — waiting for {other} file",
                        "warn",
                    )

                    file_states[name] = {
                        "state": "unmatched",
                        "detected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "source_file": pair["source_file"],
                        "target_file": pair["target_file"],
                    }

                continue

            last_mtime = pair["mtime"]
            existing = results_store.get(name)
            prev_state = file_states.get(name, {})

            if not existing:
                log_event(
                    f"{name}: new file pair — {pair['source_file']} + {pair['target_file']}",
                    "info",
                )
            elif prev_state.get("_mtime") != last_mtime:
                log_event(f"{name}: file changed — re-validating", "info")
            else:
                continue

            file_states[name] = {
                "state": "validating",
                "detected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source_file": pair["source_file"],
                "target_file": pair["target_file"],
                "_mtime": last_mtime,
            }

            try:
                result = run_validation(
                    name,
                    pair["source_path"],
                    pair["target_path"],
                )

                result["_mtime"] = last_mtime
                results_store[name] = result

                file_states[name] = {
                    "state": "done",
                    "detected_at": file_states[name]["detected_at"],
                    "validated_at": result["run_at"],
                    "source_file": pair["source_file"],
                    "target_file": pair["target_file"],
                    "_mtime": last_mtime,
                }

                level = "success" if result["status"] == "PASS" else "warn"

                log_event(
                    f"{name}: {result['status']} — "
                    f"{result['fields_passed']}/{result['total_fields']} fields passed "
                    f"(threshold {result['pass_threshold']}%), "
                    f"{result['records_matched']:,} records matched",
                    level,
                )

            except Exception as e:
                file_states[name]["state"] = "error"
                scan_status["error"] = str(e)
                log_event(f"{name}: error — {e}", "error")

        scan_status["last_scan"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    except Exception as e:
        scan_status["error"] = str(e)
        log_event(f"Scan error: {e}", "error")

    finally:
        scan_status["scanning"] = False
        scan_lock.release()


def background_watcher(interval=60):
    """
    Optional automatic watcher.

    Keep this disabled while testing.
    If enabled, it scans every 60 seconds instead of every 5 seconds.
    """

    while True:
        scan_and_validate_all()
        time.sleep(interval)


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/scan", methods=["POST"])
def api_scan():
    threading.Thread(target=scan_and_validate_all, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/status")
def api_status():
    pairs = discover_pairs()
    cfg = load_config()
    source_dir, target_dir = get_dirs()

    return jsonify(
        {
            "last_scan": scan_status["last_scan"],
            "scanning": scan_status["scanning"],
            "error": scan_status["error"],
            "source_dir": str(source_dir),
            "target_dir": str(target_dir),
            "pairs": pairs,
            "file_states": file_states,
            "total_tables": len([p for p in pairs if p["has_pair"]]),
            "unmatched": len([p for p in pairs if not p["has_pair"]]),
            "pass_threshold": cfg.get("pass_threshold", 100.0),
            "selected_fields": cfg.get("selected_fields", []),
        }
    )


@app.route("/api/results")
def api_results():
    return jsonify(list(results_store.values()))


@app.route("/api/results/<name>")
def api_result_detail(name):
    r = results_store.get(name.upper())

    if r:
        return jsonify(r)

    return jsonify({"error": "Not found"}), 404


@app.route("/api/activity")
def api_activity():
    return jsonify(list(reversed(activity_log)))


@app.route("/api/upload/source", methods=["POST"])
def upload_source():
    return _handle_upload(request, get_dirs()[0], "source")


@app.route("/api/upload/target", methods=["POST"])
def upload_target():
    return _handle_upload(request, get_dirs()[1], "target")


@app.route("/api/upload/labels", methods=["POST"])
def upload_labels():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    f = request.files["file"]
    f.save(str(LABELS_FILE))

    log_event(f"Custom labels uploaded: {f.filename}", "info")

    results_store.clear()

    for n in file_states:
        if file_states[n].get("state") == "done":
            file_states[n]["state"] = "changed"

    threading.Thread(target=scan_and_validate_all, daemon=True).start()

    return jsonify({"ok": True, "filename": f.filename})


def _handle_upload(req, dest_dir, side):
    if "file" not in req.files:
        return jsonify({"error": "No file"}), 400

    saved = []

    for f in req.files.getlist("file"):
        if not f.filename:
            continue

        if Path(f.filename).suffix.lower() not in SUPPORTED_EXT:
            return jsonify({"error": f"Unsupported: {f.filename}"}), 400

        f.save(str(dest_dir / f.filename))

        log_event(f"Uploaded to {side}: {f.filename}", "info")
        saved.append(f.filename)

    if saved:
        threading.Thread(target=scan_and_validate_all, daemon=True).start()

    return jsonify({"ok": True, "saved": saved})


@app.route("/api/config", methods=["GET"])
def api_get_config():
    cfg = load_config()

    available = []

    if results_store:
        first = next(iter(results_store.values()))

        available = [
            {
                "field": fr["field"],
                "label": fr.get("field_label", fr["field"]),
            }
            for fr in first.get("field_results", [])
        ]

    return jsonify(
        {
            "source_dir": cfg.get("source_dir", DEFAULT_CONFIG["source_dir"]),
            "target_dir": cfg.get("target_dir", DEFAULT_CONFIG["target_dir"]),
            "pass_threshold": cfg.get("pass_threshold", 100.0),
            "selected_fields": cfg.get("selected_fields", []),
            "available_fields": available,
            "labels_file_exists": LABELS_FILE.exists(),
            "labels_file": str(LABELS_FILE) if LABELS_FILE.exists() else None,
        }
    )


@app.route("/api/config", methods=["POST"])
def api_set_config():
    data = request.get_json(force=True)
    cfg = load_config()
    changed = False

    for key in ("source_dir", "target_dir"):
        if key in data and data[key].strip():
            new_path = str(Path(data[key].strip()))

            if new_path != cfg.get(key):
                cfg[key] = new_path
                changed = True

    if "pass_threshold" in data:
        thr = float(data["pass_threshold"])

        if thr != cfg.get("pass_threshold"):
            cfg["pass_threshold"] = thr
            changed = True
            log_event(f"Pass threshold updated to {thr}%", "info")

    if "selected_fields" in data:
        sel = [f.strip().upper() for f in data["selected_fields"] if f.strip()]

        if sel != cfg.get("selected_fields", []):
            cfg["selected_fields"] = sel
            changed = True

            if sel:
                log_event(f"Field selection updated: {len(sel)} fields", "info")
            else:
                log_event("Field selection: all fields", "info")

    if changed:
        save_config(cfg)
        results_store.clear()

        for n in file_states:
            if file_states[n].get("state") == "done":
                file_states[n]["state"] = "changed"

        threading.Thread(target=scan_and_validate_all, daemon=True).start()

    return jsonify({"ok": True, "config": cfg})


@app.route("/api/labels/sample")
def api_labels_sample():
    from core.field_labels import SAP_FIELD_LABELS

    lines = ["FIELD_NAME,FRIENDLY_LABEL"]

    for k, v in list(SAP_FIELD_LABELS.items())[:20]:
        lines.append(f"{k},{v}")

    return Response(
        "\n".join(lines).encode("utf-8"),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=sample_labels.csv"
        },
    )


@app.route("/api/download/<name>")
def api_download(name):
    r = results_store.get(name.upper())

    if not r:
        return jsonify({"error": "Not found"}), 404

    path = REPORTS_DIR / r.get("excel_file", "")

    if not path.exists():
        return jsonify({"error": "Missing"}), 404

    return send_file(
        str(path),
        as_attachment=True,
        download_name=path.name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/api/download-file/<filename>")
def api_download_file(filename):
    path = REPORTS_DIR / filename

    if not path.exists() or not filename.endswith(".xlsx"):
        return jsonify({"error": "Not found"}), 404

    return send_file(
        str(path),
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/api/reports")
def api_reports():
    files = sorted(
        REPORTS_DIR.glob("*.xlsx"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    return jsonify(
        [
            {
                "filename": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
            for f in files
        ]
    )


@app.route("/api/folders")
def api_folders():
    s, t = get_dirs()

    return jsonify(
        {
            "source_dir": str(s),
            "target_dir": str(t),
            "reports_dir": str(REPORTS_DIR),
        }
    )


if __name__ == "__main__":
    s, t = get_dirs()
    cfg = load_config()

    print("\n  SAP Post-Load Validator - Dashboard")
    print(f"  Source dir      -> {s}")
    print(f"  Target dir      -> {t}")
    print(f"  Reports         -> {REPORTS_DIR}")
    print(f"  Pass threshold  -> {cfg.get('pass_threshold', 100)}%")
    print("  Open            -> http://localhost:5000\n")

    # One scan at startup
    threading.Thread(target=scan_and_validate_all, daemon=True).start()

    # Keep this disabled while testing to avoid repeated long scans.
    # After testing, you can enable it with 60 seconds interval:
    # threading.Thread(target=background_watcher, args=(60,), daemon=True).start()

    app.run(debug=False, port=5000, use_reloader=False)
