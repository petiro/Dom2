from PySide6.QtCore import QThread, Signal

class BetWorker(QThread):
    finished = Signal(dict) # Output: {status, stake, odds}
    log = Signal(str, str)  # Output: level, message

    def __init__(self, table, executor, match_data):
        super().__init__()
        self.table = table
        self.executor = executor
        self.match = match_data['match']
        self.market = match_data['market']

    def run(self):
        try:
            self.log.emit("info", f"Scouting: {self.match} | {self.market}")

            # 1. Navigate to match and select market
            selectors = self.executor._load_selectors()

            if not self.executor.navigate_to_match(self.match, selectors):
                self.finished.emit({"status": "error", "msg": "Match non trovato"})
                return

            if not self.executor.select_market(self.market, selectors):
                self.finished.emit({"status": "error", "msg": "Mercato non trovato"})
                return

            # 2. Find odds on page
            odds = self.executor.find_odds(self.match, self.market)
            if not odds or odds <= 1.0:
                self.finished.emit({"status": "error", "msg": "Quota non trovata o <= 1.0"})
                return

            # 3. Calculate stake via Roserpina
            stake = self.table.calculate_stake(odds)
            if stake <= 0:
                self.finished.emit({"status": "error", "msg": "Stake calcolato a 0"})
                return
            self.log.emit("info", f"Stake Roserpina: EUR {stake} @ {odds}")

            # 4. Place bet (takes selectors dict)
            if self.executor.place_bet(selectors):
                self.finished.emit({"status": "placed", "stake": stake, "odds": odds})
            else:
                self.finished.emit({"status": "error", "msg": "Piazzamento fallito"})

        except Exception as e:
            self.finished.emit({"status": "error", "msg": str(e)})
