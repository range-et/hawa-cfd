"""Catalog every executable upstream example and run bounded verification jobs."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys

from example_inventory import entrypoints

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--match", default="")
    parser.add_argument("--output-root", type=Path, default=ROOT / "results/examples")
    args = parser.parse_args()
    examples = ROOT / "vendor/lettuce/examples"
    if args.reference:
        checkout = ROOT / ".reference/lettuce-upstream"
        if not (checkout / ".git").exists():
            subprocess.run(["git", "clone", "--no-checkout", "https://github.com/lettucecfd/lettuce.git", str(checkout)], check=True)
        commit = json.loads((ROOT / "vendor/lettuce/upstream.json").read_text())["commit"]
        subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", commit], check=True, stdout=subprocess.DEVNULL)
        examples = checkout / "examples"
    paths = entrypoints(examples)
    paths = [p for p in paths if args.match in p.relative_to(examples).as_posix()]
    if not paths:
        parser.error("No executable examples match the requested selection")
    role = "reference" if args.reference else "backport"
    output = args.output_root.resolve() / (role + "-" + args.device.replace(":", "-"))
    python = ROOT / ".venv-reference" / ("Scripts/python.exe" if os.name == "nt" else "bin/python") if args.reference else Path(sys.executable)

    def run(path):
        name = path.relative_to(examples).as_posix()
        directory = output / name.replace("/", "__")
        command = [str(python), str(ROOT / "scripts/example_worker.py"), name,
                   "--device", args.device, "--source-root", str(examples), "--output", str(directory)]
        if args.full:
            command.append("--full")
        report = directory / "report.json"
        report.unlink(missing_ok=True)
        try:
            result = subprocess.run(command, cwd=ROOT, env=dict(os.environ, MPLBACKEND="Agg"),
                                    capture_output=True, text=True, timeout=None if args.full else 180)
            if report.exists():
                record=json.loads(report.read_text())
                if result.returncode and record.get('status') in ('passed','launcher-only'):
                    record.update(status='failed',error='Worker exited with code '+str(result.returncode))
                return record
            return {"source": name, "status": "failed", "error": result.stderr[-2500:]}
        except subprocess.TimeoutExpired:
            return {"source": name, "status": "timeout"}
    records = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = {executor.submit(run, p): p for p in paths}
        for future in as_completed(pending):
            report = future.result()
            records.append(report)
            print(report["source"] + ": " + report["status"] + " " + report.get("error", ""), flush=True)
    output.mkdir(parents=True, exist_ok=True)
    summary_name = "report.json" if not args.match else "report-" + args.match.replace("/", "_") + ".json"
    (output / summary_name).write_text(json.dumps({"role": role, "device": args.device,
        "profile": "full" if args.full else "bounded", "examples": records}, indent=2) + "\n")
    return 1 if any(r["status"] not in ("passed", "launcher-only") for r in records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
