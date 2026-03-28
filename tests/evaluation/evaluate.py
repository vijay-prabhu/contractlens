"""Classification evaluation script (ADR-011).

Runs the gold standard test set through the classifier and reports
accuracy, F1, confusion matrix, and score calibration.

Usage:
    cd backend
    poetry run python -m tests.evaluation.evaluate
    poetry run python -m tests.evaluation.evaluate --save  # Save results to file
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.services.classification_service import ClassificationService


GOLD_STANDARD_PATH = Path(__file__).parent / "gold_standard.json"
RESULTS_DIR = Path(__file__).parent / "results"


def load_gold_standard() -> list:
    with open(GOLD_STANDARD_PATH) as f:
        return json.load(f)


def evaluate(save: bool = False):
    gold = load_gold_standard()
    service = ClassificationService()

    print(f"Evaluating {len(gold)} clauses...")
    print()

    results = []
    start = time.monotonic()

    for entry in gold:
        result = service.classify_clause(entry["text"])
        results.append({
            "id": entry["id"],
            "expected_type": entry["expected_clause_type"],
            "predicted_type": result.clause_type,
            "type_correct": result.clause_type == entry["expected_clause_type"],
            "expected_level": entry["expected_risk_level"],
            "predicted_level": result.risk_level,
            "level_correct": result.risk_level == entry["expected_risk_level"],
            "predicted_score": result.risk_score,
            "score_in_range": (
                entry["expected_risk_score_range"][0]
                <= result.risk_score
                <= entry["expected_risk_score_range"][1]
            ),
            "confidence": result.confidence,
            "failed": result.classification_failed,
        })

    elapsed = time.monotonic() - start

    # --- Metrics ---
    total = len(results)
    type_correct = sum(1 for r in results if r["type_correct"])
    level_correct = sum(1 for r in results if r["level_correct"])
    score_in_range = sum(1 for r in results if r["score_in_range"])
    failed = sum(1 for r in results if r["failed"])
    low_confidence = sum(1 for r in results if r["confidence"] < 0.6)

    type_accuracy = type_correct / total if total else 0
    level_accuracy = level_correct / total if total else 0
    score_accuracy = score_in_range / total if total else 0

    # F1 per clause type
    type_tp = defaultdict(int)
    type_fp = defaultdict(int)
    type_fn = defaultdict(int)
    for r in results:
        if r["type_correct"]:
            type_tp[r["expected_type"]] += 1
        else:
            type_fp[r["predicted_type"]] += 1
            type_fn[r["expected_type"]] += 1

    all_types = sorted(set(r["expected_type"] for r in results) | set(r["predicted_type"] for r in results))

    # Confusion matrix for risk levels
    level_order = ["low", "medium", "high", "critical"]
    confusion = defaultdict(lambda: defaultdict(int))
    for r in results:
        confusion[r["expected_level"]][r["predicted_level"]] += 1

    # --- Print Report ---
    print("=" * 60)
    print("CLASSIFICATION EVALUATION REPORT")
    print("=" * 60)
    print(f"Date:           {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Test set:       {total} clauses")
    print(f"Time:           {elapsed:.1f}s ({elapsed/total:.2f}s per clause)")
    print(f"Failures:       {failed}/{total} ({failed/total:.0%})")
    print(f"Low confidence: {low_confidence}/{total} ({low_confidence/total:.0%})")
    print()

    print("--- Accuracy ---")
    print(f"Clause type:    {type_correct}/{total} ({type_accuracy:.1%})")
    print(f"Risk level:     {level_correct}/{total} ({level_accuracy:.1%})")
    print(f"Score in range: {score_in_range}/{total} ({score_accuracy:.1%})")
    print()

    print("--- F1 per Clause Type ---")
    print(f"{'Type':<28} {'Prec':>6} {'Rec':>6} {'F1':>6} {'N':>4}")
    print("-" * 52)
    for t in all_types:
        tp = type_tp[t]
        fp = type_fp[t]
        fn = type_fn[t]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        n = tp + fn
        print(f"{t:<28} {precision:>6.2f} {recall:>6.2f} {f1:>6.2f} {n:>4}")
    print()

    print("--- Risk Level Confusion Matrix ---")
    header = "Actual \\ Pred"
    print(f"{header:<12}", end="")
    for p in level_order:
        print(f"{p:>10}", end="")
    print()
    for a in level_order:
        print(f"{a:<12}", end="")
        for p in level_order:
            count = confusion[a][p]
            print(f"{count:>10}", end="")
        print()
    print()

    # Misclassifications
    misses = [r for r in results if not r["type_correct"]]
    if misses:
        print("--- Misclassified Clauses ---")
        for r in misses:
            print(f"  {r['id']}: expected={r['expected_type']}, got={r['predicted_type']}")
        print()

    # Score outliers
    outliers = [r for r in results if not r["score_in_range"]]
    if outliers:
        print("--- Score Out of Range ---")
        for r in outliers:
            print(f"  {r['id']}: predicted={r['predicted_score']:.2f}, type={r['predicted_type']}")
        print()

    # Save results
    if save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report = {
            "timestamp": timestamp,
            "total": total,
            "type_accuracy": round(type_accuracy, 4),
            "level_accuracy": round(level_accuracy, 4),
            "score_in_range_rate": round(score_accuracy, 4),
            "failure_rate": round(failed / total, 4) if total else 0,
            "low_confidence_rate": round(low_confidence / total, 4) if total else 0,
            "elapsed_seconds": round(elapsed, 2),
            "results": results,
        }
        outpath = RESULTS_DIR / f"eval_{timestamp}.json"
        with open(outpath, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Results saved to: {outpath}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run classification evaluation")
    parser.add_argument("--save", action="store_true", help="Save results to file")
    args = parser.parse_args()
    evaluate(save=args.save)
