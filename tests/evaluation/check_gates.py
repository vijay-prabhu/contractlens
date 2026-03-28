"""Check quality gates against evaluation results (ADR-015).

Reads the latest evaluation results and exits with code 1 if any
threshold is breached. Used by GitHub Actions CI/CD pipeline.

Usage:
    python tests/evaluation/check_gates.py results.json
"""
import json
import sys
from pathlib import Path

# Quality gate thresholds
THRESHOLDS = {
    "type_accuracy": 0.90,     # Clause type accuracy >= 90%
    "level_accuracy": 0.75,    # Risk level accuracy >= 75%
    "failure_rate_max": 0.05,  # Failure rate < 5%
}


def check_gates(results_path: str) -> bool:
    with open(results_path) as f:
        results = json.load(f)

    passed = True

    print("=" * 50)
    print("QUALITY GATE CHECK")
    print("=" * 50)

    checks = [
        ("Type accuracy", results["type_accuracy"], THRESHOLDS["type_accuracy"], ">="),
        ("Level accuracy", results["level_accuracy"], THRESHOLDS["level_accuracy"], ">="),
        ("Failure rate", results["failure_rate"], THRESHOLDS["failure_rate_max"], "<="),
    ]

    for name, value, threshold, op in checks:
        if op == ">=" and value >= threshold:
            status = "PASS"
        elif op == "<=" and value <= threshold:
            status = "PASS"
        else:
            status = "FAIL"
            passed = False

        print(f"  {name}: {value:.1%} (threshold: {op}{threshold:.0%}) — {status}")

    print()
    if passed:
        print("All quality gates PASSED")
    else:
        print("QUALITY GATES FAILED — blocking merge")

    return passed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Find the latest results file
        results_dir = Path(__file__).parent / "results"
        results_files = sorted(results_dir.glob("eval_*.json"))
        if not results_files:
            print("No evaluation results found. Run evaluate.py first.")
            sys.exit(1)
        results_path = str(results_files[-1])
    else:
        results_path = sys.argv[1]

    if not check_gates(results_path):
        sys.exit(1)
