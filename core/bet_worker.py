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
            self.log.emit("info", f"🕵️ Scouting: {self.match} | {self.market}")
            
            # 1. Trova Quota (Bloccante)
            odds = self.executor.find_odds(self.match, self.market)
            if not odds or odds <= 1.0:
                self.finished.emit({"status": "error", "msg": "Quota non trovata"})
                return

            # 2. Calcola Stake
            stake = self.table.calculate_stake(odds)
            self.log.emit("info", f"💰 Stake Roserpina: €{stake} @ {odds}")

            # 3. Piazza Scommessa
            if self.executor.place_bet(self.match, self.market, stake):
                self.finished.emit({"status": "placed", "stake": stake, "odds": odds})
            else:
                self.finished.emit({"status": "error", "msg": "Piazzamento fallito"})

        except Exception as e:
            self.finished.emit({"status": "error", "msg": str(e)})
