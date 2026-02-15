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
        self.logger = logging.getLogger("BetWorker")

    def run(self):
        try:
            # FIX BUG-03: Usa find_odds (ora esiste sull'executor)
            odds = self.executor.find_odds(self.match, self.market)

            if not odds or odds <= 1.0:
                self.logger.error(f"Quote non valide: {odds}")
                self.finished.emit(False)
                return

            # FIX BUG-03: Usa get_stake (nome corretto su MoneyManager)
            stake = self.money_manager.get_stake(odds)

            if not stake or stake <= 0:
                self.logger.warning("Stake = 0. Operazione annullata.")
                self.finished.emit(False)
                return

            success = self.executor.place_bet(self.match, self.market, stake)
            self.finished.emit(bool(success))

        except Exception as e:
            self.logger.error(f"Errore BetWorker: {e}")
            self.finished.emit(False)
