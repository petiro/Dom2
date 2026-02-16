import logging
from PySide6.QtCore import QThread, Signal


class BetWorker(QThread):
    finished = Signal(bool)

    def __init__(self, money_manager, executor, match_data):
        super().__init__()
        self.executor = executor
        self.match = match_data.get('match', match_data.get('teams', ''))
        self.market = match_data.get('market', '')
        self.money_manager = money_manager
        self.logger = logging.getLogger("SuperAgent")

    def run(self):
        try:
            odds = self.executor.find_odds(self.match, self.market)

            if odds is None or odds <= 1.0:
                self.logger.error(f"Invalid odds: {odds}")
                self.finished.emit(False)
                return

            stake = self.money_manager.get_stake(odds)

            if not stake or stake <= 0:
                self.logger.warning("Stake = 0. Operation cancelled.")
                self.finished.emit(False)
                return

            success = self.executor.place_bet(self.match, self.market, stake)
            self.finished.emit(bool(success))

        except Exception as e:
            self.logger.error(f"BetWorker error: {e}")
            self.finished.emit(False)
