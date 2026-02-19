import sys
import os

# 🔴 FIX PATH ASSOLUTO PER GITHUB ACTIONS
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, ROOT)

import json
import time

# ✅ Import locali (NO tests.stress_lab)
from mock_executor import MockExecutor
from stability_metrics import StabilityMetrics
from quant_monitor import append_record, generate_chart

TEST_SECONDS = 180  # 3 minuti CI


def run_stress():

    executor = MockExecutor()
    metrics = StabilityMetrics()

    start = time.time()

    while time.time() - start < TEST_SECONDS:

        try:
            if executor.check_open_bet():
                pass

            odds = executor.find_odds("Milan-Inter", "OVER")

            if odds:
                executor.place_bet("Milan-Inter", "OVER", 1)

            metrics.events += 1

        except Exception:
            metrics.errors += 1

        if executor.login_fails > 5:
            metrics.errors += 5

        metrics.monitor()
        time.sleep(0.01)

    score = metrics.score()

    report = {
        "events": metrics.events,
        "errors": metrics.errors,
        "memory_peak": metrics.memory_peak,
        "cpu_peak": metrics.cpu_peak,
        "stability_score": score
    }

    os.makedirs("quant_reports", exist_ok=True)

    with open("quant_reports/stress_report.json", "w") as f:
        json.dump(report, f, indent=4)

    history = append_record(score)
    generate_chart(history)

    print("STRESS COMPLETED")
    print(report)

    return report


if __name__ == "__main__":
    run_stress()
