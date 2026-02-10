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
        self.table.is_pending = True
        try:
            odds = self.executor.find_odds(self.match, self.market)

            if not odds or odds <= 1.0:
                self.logger.error(f"Quote non valide: {odds}")
                self.finished.emit(False)
                return

            stake = self.money_manager.calculate_stake(odds)

            if stake <= 0:
                self.logger.warning("Stake calcolato a 0. Operazione annullata.")
                self.finished.emit(False)
                return

            success = self.executor.place_bet(self.match, self.market, stake)
            self.finished.emit(success)

        except Exception as e:
            self.logger.error(f"Errore BetWorker: {e}")
            self.finished.emit(False)

        finally:
            self.table.is_pending = False
