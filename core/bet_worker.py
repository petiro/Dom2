import logging
from PySide6.QtCore import QThread, Signal

class BetWorker(QThread):
    finished = Signal(bool)

    def __init__(self, table, executor, match_data):
        super().__init__()
        self.table = table
        self.executor = executor
        self.match = match_data['match']
        self.market = match_data['market']
        self.money_manager = table
        self.logger = logging.getLogger("BetWorker")

    def run(self):
        try:
            odds, _locator = self.executor.find_odds(self.match, self.market)

            if not odds or odds <= 1.0:
                self.logger.error(f"Quote non valide: {odds}")
                self.table.is_pending = False
                self.finished.emit(False)
                return

            stake = self.money_manager.calculate_stake(odds)

            if not stake or stake <= 0:
                self.logger.warning("Stake = 0. Operazione annullata.")
                self.table.is_pending = False
                self.finished.emit(False)
                return

            success = self.executor.place_bet(self.match, self.market, stake)

            self.table.is_pending = False
            self.finished.emit(bool(success))

        except Exception as e:
            self.logger.error(f"Errore BetWorker: {e}")
            self.table.is_pending = False
            self.finished.emit(False)
