import json
import requests
import logging
import re

# CONFIGURA QUI LA TUA CHIAVE OPENROUTER
OPENROUTER_API_KEY = "INSERISCI_QUI_LA_TUA_CHIAVE_SK_OR_..." 

class AISignalParser:
    def __init__(self, api_key=None):
        self.logger = logging.getLogger("SuperAgent")
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = "google/gemini-2.0-flash-001" 

    def parse(self, telegram_text):
        """Analizza il testo Telegram e restituisce dati strutturati."""
        if not telegram_text or len(telegram_text) < 5: return {}
        
        if "INSERISCI_QUI" in self.api_key or not self.api_key:
            self.logger.error("❌ ERRORE: Manca API KEY in core/ai_parser.py")
            return {}

        system_instructions = """
        Sei un parser di scommesse algoritmico.
        
        TUE REGOLE DI ESTRAZIONE E CALCOLO:
        1. SQUADRE: Cerca la riga con icone '🆚' o 'v'. Estrai le squadre come "Squadra A - Squadra B".
        2. PUNTEGGIO: Cerca il risultato attuale (es. "⚽ 6 - 0").
        3. CALCOLO MERCATO (CRUCIALE):
           - Prendi i due numeri del punteggio (X e Y).
           - Fai la somma: X + Y.
           - Aggiungi 0.5 alla somma.
           - Il mercato è: "Over [Somma+0.5]".
           
           Esempio: "⚽ 6 - 0" -> 6+0=6 -> Mercato "Over 6.5".

        OUTPUT: Restituisci SOLO un JSON valido:
        {
            "teams": "SquadraCasa - SquadraOspite",
            "market": "Over X.5",
            "score_detected": "X-Y"
        }
        """

        try:
            self.logger.info("🧠 AI: Analisi messaggio in corso...")
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
