import argparse
import json
from pathlib import Path
import platform
import sys

import numpy as np

from .backends import select_backend
from .lbm import VortexConfig, VortexSimulation
from .cases import CASES


def main():
    parser = argparse.ArgumentParser(description="Hawa Python 3.9 Lettuce engine")
    parser.add_argument("--engine", choices=["lettuce", "smoke"], default="lettuce")
    parser.add_argument("--case", choices=sorted(CASES), default="tgv2d-bgk")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--size", type=int, default=None)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--output", type=Path, default=Path("results/headless"))
    args = parser.parse_args()
    if args.engine == "smoke":
        sim = VortexSimulation(select_backend(args.device), VortexConfig(size=args.size or 64))
    else:
        from .engine import LettuceSimulation
        sim = LettuceSimulation(case=args.case, device=args.device, size=args.size)
    sim.advance(args.steps)
    report = sim.diagnostics()
    report.update({"python": sys.version, "architecture": platform.machine(), "host": "headless"})
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    np.savez_compressed(args.output / "fields.npz", **sim.snapshot())
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
