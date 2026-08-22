#!/usr/bin/env python3
# This runs inside the GitHub Actions workflow to pull approved results from
# Supabase and write them into the results/ folder in this repo.
#
# It only touches rows where approved=true, so anything still under review
# never shows up here. After it runs, git picks up the changes and commits.
#
# Credentials come from GitHub Actions secrets (SUPABASE_URL + SUPABASE_SECRET_KEY).
# Do not run this locally with real secrets unless you know what you're doing.

from __future__ import annotations

import csv
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

REQUEST_TIMEOUT = 30

# Maps internal metric keys to the column names we use in summary.csv.
# Order here is the column order in the CSV.
CSV_METRIC_COLUMNS = [
    ("prompt_response_accuracy", "Accuracy (%)"),
    ("conditional_accuracy", "Conditional Accuracy (%)"),
    ("answer_recovery_rate", "Answer Recovery (%)"),
    ("instruction_compliance_rate", "Instruction Compliance (%)"),
    ("question_majority_accuracy", "Question Majority Accuracy (%)"),
    ("mean_agreement", "Agreement (%)"),
    ("mean_prompt_sensitivity", "Prompt Sensitivity (%)"),
    ("answer_unanimous_rate", "Answer Unanimous Rate (%)"),
    ("prompt_invariant_incorrect_rate", "Prompt-Invariant Incorrect Rate (%)"),
]


def safe_model_filename(model_name: str) -> str:
    # Turns "llama3.2:3b" into "llama3.2_3b", "phi4-mini:latest" into "phi4_mini", etc.
    clean = model_name.replace(":", "_").replace("/", "_").replace("-", "_")
    if clean.endswith("_latest"):
        clean = clean[:-7]
    return clean


def format_percent(value: Any) -> str:
    # Converts a 0.0-1.0 float to a percentage string like "73.1"
    if value is None:
        return ""
    try:
        f = float(value)
        return f"{f * 100:.1f}"
    except (ValueError, TypeError):
        return str(value)


def get_client() -> tuple[str, dict[str, str]]:
    # Read credentials from environment. Two naming conventions are accepted
    # since the variable name changed at some point.
    url = (
        os.environ.get("SUPABASE_URL")
        or os.environ.get("PRISM_SUPABASE_URL", "")
    ).rstrip("/")
    key = (
        os.environ.get("SUPABASE_SECRET_KEY")
        or os.environ.get("PRISM_SUPABASE_SECRET_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("PRISM_SUPABASE_SERVICE_ROLE_KEY", "")
    )

    if not url or not key:
        print(
            "ERROR: SUPABASE_URL and SUPABASE_SECRET_KEY must be set.",
            file=sys.stderr,
        )
        sys.exit(1)

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    return url, headers


def fetch_approved_runs(url: str, headers: dict) -> list[dict]:
    # Pull all approved runs, most recent first.
    resp = requests.get(
        f"{url}/rest/v1/runs",
        headers=headers,
        params={
            "select": "*",
            "approved": "eq.true",
            "order": "created_utc.desc",
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_run_results(url: str, headers: dict, run_id: str) -> list[dict]:
    # Fetch per-dataset metrics for a single run.
    resp = requests.get(
        f"{url}/rest/v1/run_results",
        headers=headers,
        params={
            "select": "*",
            "benchmark_run_id": f"eq.{run_id}",
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def build_model_record(run: dict, results: list[dict]) -> dict:
    # Combine run metadata with per-dataset metrics into one clean dict.
    return {
        "benchmark_run_id": run["benchmark_run_id"],
        "model": run["model"],
        "model_digest": run.get("model_digest"),
        "datasets": sorted(run.get("datasets") or []),
        "protocol_version": run.get("protocol_version", "1.0"),
        "created_utc": run["created_utc"],
        "approved_at": run.get("approved_at"),
        "device_id": run.get("device_id"),
        "results": sorted(results, key=lambda r: r.get("dataset", "")),
    }


def write_results(out_dir: Path, runs: list[dict], all_results: dict[str, list]) -> None:
    models_dir = out_dir / "models"

    # Wipe and rebuild the models/ directory so stale files don't stick around.
    if models_dir.exists():
        shutil.rmtree(models_dir)
    models_dir.mkdir(parents=True)

    index_entries = []
    summary_rows = []

    for run in runs:
        run_id = run["benchmark_run_id"]
        results = all_results.get(run_id, [])

        record = build_model_record(run, results)

        # One JSON file per model
        fname = safe_model_filename(run["model"]) + ".json"
        (models_dir / fname).write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Add a lightweight entry to the index
        index_entries.append({
            "benchmark_run_id": run_id,
            "model": run["model"],
            "model_digest": run.get("model_digest"),
            "datasets": sorted(run.get("datasets") or []),
            "protocol_version": run.get("protocol_version", "1.0"),
            "created_utc": run["created_utc"],
        })

        # One row per dataset in the summary
        for r in results:
            row = {
                "model": run["model"],
                "dataset": r.get("dataset", ""),
                "n_questions": r.get("n_questions", ""),
                "n_prompt_variants": r.get("n_prompt_variants", ""),
            }
            for key, _ in CSV_METRIC_COLUMNS:
                row[key] = format_percent(r.get(key))
            summary_rows.append(row)

    # Write index.json
    (out_dir / "index.json").write_text(
        json.dumps(index_entries, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Write summary.csv
    if summary_rows:
        fieldnames = (
            ["model", "dataset", "n_questions", "n_prompt_variants"]
            + [col for _, col in CSV_METRIC_COLUMNS]
        )
        # Rename internal keys to human-readable headers in the CSV
        display_rows = []
        for row in summary_rows:
            d = {
                "model": row["model"],
                "dataset": row["dataset"],
                "n_questions": row["n_questions"],
                "n_prompt_variants": row["n_prompt_variants"],
            }
            for key, header in CSV_METRIC_COLUMNS:
                d[header] = row[key]
            display_rows.append(d)

        csv_fieldnames = (
            ["model", "dataset", "n_questions", "n_prompt_variants"]
            + [col for _, col in CSV_METRIC_COLUMNS]
        )
        with (out_dir / "summary.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fieldnames)
            writer.writeheader()
            writer.writerows(display_rows)

    # Write summary.json (same data, raw floats instead of strings)
    summary_json = []
    for run in runs:
        run_id = run["benchmark_run_id"]
        for r in all_results.get(run_id, []):
            entry = {
                "model": run["model"],
                "dataset": r.get("dataset", ""),
                "n_questions": r.get("n_questions"),
                "n_prompt_variants": r.get("n_prompt_variants"),
            }
            for key, _ in CSV_METRIC_COLUMNS:
                entry[key] = r.get(key)
            summary_json.append(entry)

    (out_dir / "summary.json").write_text(
        json.dumps(summary_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main() -> int:
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)

    url, headers = get_client()

    print("Fetching approved runs...")
    runs = fetch_approved_runs(url, headers)

    if not runs:
        print("No approved results found. Nothing to write.")
        return 0

    print(f"Found {len(runs)} approved run(s). Fetching per-dataset metrics...")

    all_results: dict[str, list] = {}
    for run in runs:
        rid = run["benchmark_run_id"]
        all_results[rid] = fetch_run_results(url, headers, rid)

    print("Writing results/...")
    write_results(out_dir, runs, all_results)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Done. Snapshot written at {now}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
