
import json
import sys
import os

REPORT_PATH = "quant_reports/stress_report.json"

def fail(msg):
    print(f"CI FAILURE: {msg}")
    sys.exit(1)

def success(msg):
    print(f"CI OK: {msg}")
    sys.exit(0)

if not os.path.exists(REPORT_PATH):
    fail("stress_report.json non trovato")

with open(REPORT_PATH, encoding="utf-8") as f:
    data = json.load(f)

score = data.get("stability_score", 0)
errors = data.get("errors", 0)
mem = data.get("memory_peak", 0)

print("\nQUANT REPORT")
print(f"Stability score: {score}")
print(f"Errors: {errors}")
print(f"Memory peak: {mem}")

if errors > 0:
    fail(f"Errori runtime rilevati: {errors}")

if score < 80:
    fail(f"Stability score troppo basso: {score}")

if mem > 1500:
    fail(f"Memory leak sospetto: {mem} MB")

success("Sistema stabile")
