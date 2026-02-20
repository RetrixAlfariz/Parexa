from __future__ import annotations

import argparse
import importlib
import json
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT_DIR / "src" / "code"
for path in (str(ROOT_DIR), str(CODE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Parexa Flask app endpoints")
    parser.add_argument("--root-runs", type=int, default=20)
    parser.add_argument("--conv-runs", type=int, default=20)
    parser.add_argument("--chat-runs", type=int, default=3)
    parser.add_argument("--upload-runs", type=int, default=3)
    parser.add_argument(
        "--baseline",
        default="storage/test/outputs/benchmark_baseline_2026-02-09.json",
        help="Baseline JSON path for comparison (optional)",
    )
    parser.add_argument(
        "--output-id",
        default="",
        help="Identifier suffix for output filename (default: UTC timestamp)",
    )
    return parser.parse_args()


def _percentile(values: List[float], ratio: float) -> float:
    if not values:
        return 0.0
    items = sorted(values)
    index = max(0, min(len(items) - 1, int((len(items) - 1) * ratio)))
    return items[index]


def _summarize(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"p50_ms": 0.0, "p95_ms": 0.0, "avg_ms": 0.0}
    return {
        "p50_ms": round(statistics.median(values), 2),
        "p95_ms": round(_percentile(values, 0.95), 2),
        "avg_ms": round(sum(values) / len(values), 2),
    }


def _measure_cold_import_ms() -> float:
    code = (
        "import importlib,time,sys,os;"
        "sys.path.insert(0, os.path.join(os.getcwd(), 'src', 'code'));"
        "import importlib,time;"
        "t=time.perf_counter();"
        "importlib.import_module('parexa_interface.app');"
        "print(round((time.perf_counter()-t)*1000, 4))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT_DIR),
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip().splitlines()[-1])


def _measure_http_metrics(
    *,
    root_runs: int,
    conv_runs: int,
    chat_runs: int,
    upload_runs: int,
) -> Dict[str, Dict[str, float]]:
    mod = importlib.import_module("parexa_interface.app")
    client = mod.app.test_client()

    root_lat: List[float] = []
    conv_lat: List[float] = []
    chat_lat: List[float] = []
    upload_lat: List[float] = []

    for _ in range(max(1, root_runs)):
        start = time.perf_counter()
        response = client.get("/")
        _ = response.status_code
        root_lat.append((time.perf_counter() - start) * 1000)

    for _ in range(max(1, conv_runs)):
        start = time.perf_counter()
        response = client.get("/api/conversations?limit=10")
        _ = response.status_code
        conv_lat.append((time.perf_counter() - start) * 1000)

    for _ in range(max(1, chat_runs)):
        start = time.perf_counter()
        response = client.post("/api/chat", json={"message": "ping", "history": []})
        _ = response.status_code
        chat_lat.append((time.perf_counter() - start) * 1000)

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write("parexa benchmark upload text")
        temp_path = Path(fh.name)

    try:
        for _ in range(max(1, upload_runs)):
            with temp_path.open("rb") as file_obj:
                start = time.perf_counter()
                response = client.post(
                    "/api/upload",
                    data={"file": (file_obj, temp_path.name)},
                    content_type="multipart/form-data",
                )
                _ = response.status_code
                upload_lat.append((time.perf_counter() - start) * 1000)
    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "get_root": _summarize(root_lat),
        "get_conversations": _summarize(conv_lat),
        "post_chat": _summarize(chat_lat),
        "post_upload_text": _summarize(upload_lat),
    }


def _load_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _compare(
    baseline: Dict[str, Any], current: Dict[str, Any]
) -> Dict[str, Dict[str, float]]:
    comparison: Dict[str, Dict[str, float]] = {}
    if not baseline:
        return comparison

    baseline_cold = float(baseline.get("cold_import_ms", 0.0) or 0.0)
    if baseline_cold > 0:
        current_cold = float(current.get("cold_import_ms", 0.0) or 0.0)
        comparison["cold_import_ms"] = {
            "baseline": round(baseline_cold, 2),
            "current": round(current_cold, 2),
            "delta_ms": round(current_cold - baseline_cold, 2),
            "delta_pct": round(((current_cold - baseline_cold) / baseline_cold) * 100, 2),
        }

    baseline_http = baseline.get("http", {})
    current_http = current.get("http", {})
    for key in ("get_root", "get_conversations", "post_chat", "post_upload_text"):
        base_metric = baseline_http.get(key, {})
        curr_metric = current_http.get(key, {})
        base_p95 = float(base_metric.get("p95_ms", 0.0) or 0.0)
        curr_p95 = float(curr_metric.get("p95_ms", 0.0) or 0.0)
        if base_p95 <= 0:
            continue
        comparison[key] = {
            "baseline_p95_ms": round(base_p95, 2),
            "current_p95_ms": round(curr_p95, 2),
            "delta_ms": round(curr_p95 - base_p95, 2),
            "delta_pct": round(((curr_p95 - base_p95) / base_p95) * 100, 2),
        }
    return comparison


def _to_markdown(result: Dict[str, Any]) -> str:
    lines = [
        "# Parexa Benchmark",
        "",
        f"- Timestamp: {result.get('timestamp_utc', '-')}",
        f"- Cold import: {result.get('cold_import_ms', 0.0):.2f} ms",
        "",
        "| Metric | p50 (ms) | p95 (ms) | avg (ms) |",
        "|---|---:|---:|---:|",
    ]
    http = result.get("http", {})
    for key in ("get_root", "get_conversations", "post_chat", "post_upload_text"):
        metric = http.get(key, {})
        lines.append(
            f"| {key} | {metric.get('p50_ms', 0):.2f} | {metric.get('p95_ms', 0):.2f} | {metric.get('avg_ms', 0):.2f} |"
        )
    comparison = result.get("comparison", {})
    if comparison:
        lines.extend(
            [
                "",
                "## Baseline Comparison",
                "",
                "```json",
                json.dumps(comparison, indent=2, ensure_ascii=True),
                "```",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    args = _parse_args()
    output_id = args.output_id.strip() or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    baseline_path = (ROOT_DIR / args.baseline).resolve()
    baseline = _load_json_file(baseline_path)

    result: Dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "cold_import_ms": round(_measure_cold_import_ms(), 2),
        "http": _measure_http_metrics(
            root_runs=args.root_runs,
            conv_runs=args.conv_runs,
            chat_runs=args.chat_runs,
            upload_runs=args.upload_runs,
        ),
    }
    result["comparison"] = _compare(baseline, result)

    output_dir = ROOT_DIR / "storage" / "test" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"benchmark_app_{output_id}.json"
    md_path = output_dir / f"benchmark_app_{output_id}.md"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8")
    md_path.write_text(_to_markdown(result), encoding="utf-8")

    print(json.dumps(result, indent=2, ensure_ascii=True))
    print(f"Saved benchmark JSON to {json_path}")
    print(f"Saved benchmark markdown to {md_path}")


if __name__ == "__main__":
    main()
