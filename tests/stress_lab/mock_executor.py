import random
import time

class MockExecutor:

    def __init__(self):
        self.bet_count = 0
        self.login_fails = 0
        self.balance = 100.0
        self.start_time = time.time()

    def check_open_bet(self):
        return random.random() < 0.05

    def navigate_to_match(self, teams):
        return random.random() > 0.02

    def find_odds(self, teams, market):
        if random.random() < 0.03:
            return None
        return round(random.uniform(1.4, 2.5), 2)

    def place_bet(self, teams, market, stake):
        if random.random() < 0.05:
            return False
        self.bet_count += 1
        self.balance -= stake
        return True

    def get_balance(self):
        return self.balance

    def recycle_browser(self):
        pass

    def check_settled_bets(self):
        if random.random() < 0.1:
            return {"status": random.choice(["WIN", "LOSS", "VOID"]), "payout": random.uniform(0, 10)}
        return None
