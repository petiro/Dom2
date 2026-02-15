import requests
import logging
import json
import time
from PySide6.QtCore import QObject, Signal

class AutoMapperWorker(QObject):
    """
    Worker che gestisce l'analisi del DOM tramite AI con sistema di fallback.
    """
    finished = Signal(dict)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, api_key, dom_data):
        super().__init__()
        self.api_key = api_key
        self.dom_data = dom_data
        self.logger = logging.getLogger("AutoMapper")

        # LISTA MODELLI AGGIORNATA FEBBRAIO 2026 (Resilienza Totale)
        self.AI_MODELS = [
            "anthropic/claude-3.5-sonnet",               # Primo tentativo (Alta precisione)
            "openai/gpt-oss-120b:free",                 # Fallback 1 (Potente e gratuito)
            "qwen/qwen-3-coder-480b-a35b-instruct:free", # Fallback 2 (Ottimo per il codice)
            "google/gemini-2.0-flash-lite-preview-02-05:free", # Fallback 3
            "arcee-ai/trinity-large-preview:free"        # Fallback finale
        ]

    def run(self):
        """Avvia il processo di analisi."""
        try:
            self.status.emit("Inviando dati all'AI per il mapping...")
            result = self._call_openrouter_with_fallback()
            
            if result:
                self.finished.emit(result)
            else:
                self.error.emit("Tutti i modelli AI hanno fallito la risposta.")
        except Exception as e:
            self.error.emit(f"Errore critico nel worker: {str(e)}")

    def _call_openrouter_with_fallback(self):
        """
        Cicla attraverso i modelli finché non riceve una risposta valida (200 OK).
        """
        prompt = f"Analizza questo dump HTML e mappa i selettori per gli elementi interattivi:\n\n{self.dom_data}"

        for model in self.AI_MODELS:
            self.logger.info(f"🔄 Tentativo di mapping con: {model}")
            
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "https://github.com/petiro/Dom2", # Obbligatorio per modelli free
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1
                    },
                    timeout=45
                )

                # Se il modello risponde correttamente
                if response.status_code == 200:
                    data = response.json()
                    choices = data.get('choices', [])
                    if not choices:
                        self.logger.warning(f"⚠️ Risposta vuota da {model}")
                        continue
                    content = choices[0].get('message', {}).get('content', '')
                    if not content:
                        self.logger.warning(f"⚠️ Contenuto vuoto da {model}")
                        continue
                    self.logger.info(f"✅ Mapping completato con successo usando {model}")
                    return self._parse_ai_response(content)

                # Se il modello è saturo (429) o in errore (5xx)
                elif response.status_code in [429, 500, 502, 503]:
                    self.logger.warning(f"⚠️ Modello {model} non disponibile ({response.status_code}). Provo il prossimo...")
                    time.sleep(1) # Breve pausa prima del fallback
                    continue
                
                else:
                    self.logger.error(f"❌ Errore imprevisto {response.status_code} con {model}: {response.text}")
                    continue

            except Exception as e:
                self.logger.error(f"⚠️ Eccezione con il modello {model}: {str(e)}")
                continue

        return None

    def _parse_ai_response(self, content):
        """Pulisce e converte la risposta dell'AI in un dizionario JSON."""
        try:
            # Rimuove eventuali blocchi markdown ```json ... ```
            clean_content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_content)
        except Exception as e:
            self.logger.error(f"Errore nel parsing della risposta AI: {e}")
            return {"raw_response": content}
