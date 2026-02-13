# ------------------------------------------------------------------
    #  Status / Stats / Data Exposure (PER LA UI)
    # ------------------------------------------------------------------
    def get_state(self) -> str:
        return self.state_manager.state.name

    def get_bet_history(self) -> list:
        """Restituisce lo storico completo delle scommesse per la StatsTab"""
        return self._bet_results

    def get_stats(self) -> dict:
        total = len(self._bet_results)
        placed = sum(1 for r in self._bet_results if r.get("placed"))
        wins = sum(1 for r in self._bet_results if r.get("result") == "WIN") # Presuppone che qualcuno aggiorni il risultato
        profit = sum(r.get("profit", 0) for r in self._bet_results)
        
        return {
            "state": self.get_state(),
            "signals_received": self._signal_count,
            "bets_total": total,
            "bets_placed": placed,
            "win_rate": (wins / placed * 100) if placed > 0 else 0.0,
            "total_profit": profit,
            "uptime_s": time.time() - self.monitor.start_time.timestamp() if self.monitor else 0,
        }

    # ------------------------------------------------------------------
    #  Factory Logic (Caricamento Profilo Robot)
    # ------------------------------------------------------------------
    def load_robot_profile(self, robot_data: dict):
        """
        Attiva un robot specifico: cambia canali Telegram e Prompts.
        """
        logger.info(f"🤖 Attivazione Profilo Robot: {robot_data.get('name', 'Unknown')}")
        
        # 1. Aggiorna configurazione Telegram
        tg_channel = robot_data.get("telegram")
        if tg_channel:
            # Aggiorna la config corrente e riavvia il worker
            self.current_config["telegram"]["selected_chats"] = [tg_channel]
            self.connect_telegram(self.current_config["telegram"])
            logger.info(f"📡 Canale Telegram impostato su: {tg_channel}")

        # 2. Aggiorna Prompt AI (se usassi l'AI per decidere)
        # self.trainer.set_system_prompt(...) 
        
        self.safe_emit(self.log_message, f"Agente {robot_data.get('name')} ATTIVO")
