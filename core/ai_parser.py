import json
import requests
import logging

class AISignalParser:
    def __init__(self, api_key=None):
        self.logger = logging.getLogger("SuperAgent")
        self.api_key = api_key
        self.model = "google/gemini-2.0-flash-001" 

    def parse(self, telegram_text):
        if not telegram_text or len(telegram_text) < 5: return {}
        
        if not self.api_key:
            self.logger.warning("⚠️ AI PARSER: API Key mancante! Vai in 'IMPOSTAZIONI' e salva la chiave.")
            return {}

        system_instructions = """
        Sei un parser di scommesse algoritmico.
        REGOLE:
        1. Estrai squadre (es. "Squadra A - Squadra B").
        2. Estrai punteggio (es. "6 - 0").
        3. Calcola Mercato: Somma punteggio + 0.5 (es. 6+0=6 -> "Over 6.5").
        
        OUTPUT JSON:
        {"teams": "...", "market": "Over X.5", "score_detected": "X-Y"}
        """

        try:
            # self.logger.info("🧠 AI: Invio richiesta...")
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "SuperAgentBot"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_instructions},
                        {"role": "user", "content": telegram_text}
                    ],
                    "temperature": 0.1
                },
                timeout=15
            )
            
            if response.status_code == 200:
                raw = response.json()['choices'][0]['message']['content']
                clean = raw.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean)
                self.logger.info(f"✅ AI OUTPUT: {data}")
                return data
            else:
                self.logger.error(f"❌ Errore AI: {response.status_code}")
                return {}
        except Exception as e:
            self.logger.error(f"❌ Eccezione AI: {e}")
            return {}
