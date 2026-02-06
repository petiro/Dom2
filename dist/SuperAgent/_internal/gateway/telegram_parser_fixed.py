import re
import json
from ai_bridge import AIBridge  # Fixed import
from gateway.pattern_memory import PatternMemory

class TelegramParser:
    def __init__(self, logger, api_key=None):
        self.logger = logger
        self.ai = AIBridge(api_key) if api_key else None
        self.memory = PatternMemory()

    def parse_signal(self, text):
        """
        Parse betting signal from Telegram message
        
        Returns dict with keys: teams, market, score
        or None if not a valid signal
        """
        # 1. Check if format is already known (Local Memory)
        cached_result = self.memory.get_pattern(text)
        if cached_result:
            self.logger.info("Pattern recognized from memory.")
            return cached_result

        # 2. If unknown, use AI
        if self.ai:
            prompt = f"""
            Analizza questo messaggio di scommesse sportive e scarta se non è un segnale operativo.
            Estrai: squadre, mercato specifico (es. Over 1.5), e punteggio attuale.
            Se il segnale indica 'Over successivo', calcola l'over basandoti sul punteggio attuale.
            Rispondi SOLO in formato JSON: {{"teams": "...", "market": "...", "score": "..."}}
            Messaggio: {text}
            """
            try:
                import requests
                headers = {
                    "Authorization": f"Bearer {self.ai.api_key}",
                    "Content-Type": "application/json"
                }
                data = {
                    "model": self.ai.model,
                    "messages": [{"role": "user", "content": prompt}]
                }
                r = requests.post(self.ai.url, headers=headers, json=data, timeout=10)
                r.raise_for_status()
                res = r.json()['choices'][0]['message']['content'].strip()
                
                # Clean markdown if AI adds it
                if "```json" in res:
                    res = res.split("```json")[1].split("```")[0].strip()
                
                result = json.loads(res)
                
                # 3. Save new pattern to memory
                self.memory.save_pattern(text, result)
                return result
            except Exception as e:
                self.logger.error(f"AI Parsing failed, falling back to regex: {e}")

        # Fallback Regex (previous logic)
        try:
            teams_match = re.search(r'🆚(.*?)\n', text)
            teams = teams_match.group(1).strip() if teams_match else None
            
            score_match = re.search(r'⚽\s*(\d+\s*-\s*\d+)|⌚.*?,.*?(\d+\s*-\s*\d+)', text)
            current_score = score_match.group(1) or score_match.group(2) if score_match else None
            
            market = "Over 0.5" if "OVER" in text.upper() else None
            
            if teams:
                return {
                    "teams": teams,
                    "market": market,
                    "score": current_score
                }
        except Exception as e:
            self.logger.error(f"Regex parsing failed: {e}")
        
        return None
