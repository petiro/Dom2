import psutil
import os

class StabilityMetrics:

    def __init__(self):
        self.errors = 0
        self.events = 0
        self.memory_peak = 0
        self.cpu_peak = 0

    def monitor(self):
        process = psutil.Process(os.getpid())
        mem = process.memory_info().rss / 1024 / 1024
        cpu = process.cpu_percent(interval=0.1)

        self.memory_peak = max(self.memory_peak, mem)
        self.cpu_peak = max(self.cpu_peak, cpu)

    def score(self):
        score = 100

        if self.errors > 50:
            score -= 30
        if self.memory_peak > 800:
            score -= 20
        if self.cpu_peak > 95:
            score -= 20

        return max(score, 0)
