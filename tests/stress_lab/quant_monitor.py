import json
import os
import matplotlib.pyplot as plt
from datetime import datetime

HISTORY_PATH = ".quant/stability_history.json"

def load_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    with open(HISTORY_PATH, "r") as f:
        return json.load(f)

def save_history(history):
    os.makedirs(".quant", exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=4)

def append_record(score):
    history = load_history()
    history.append({
        "timestamp": datetime.utcnow().isoformat(),
        "score": score
    })
    save_history(history)
    return history

def generate_chart(history):
    scores = [h["score"] for h in history]
    plt.figure()
    plt.plot(scores)
    plt.title("Stability Score Trend")
    plt.xlabel("Run #")
    plt.ylabel("Score")
    plt.ylim(0, 100)
    plt.savefig("stability_trend.png")
