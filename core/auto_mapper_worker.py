import json
import requests
from PySide6.QtCore import QThread, Signal

class AutoMapperWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, url, api_key, executor):
        super().__init__()
        self.url = url
        self.api_key = api_key
        self.executor = executor

    def run(self):
        try:
            # 1. Navigazione
            if self.executor.page.url != self.url:
                self.executor.page.goto(self.url, wait_until="networkidle")

            # 2. Estrazione DOM Leggero
            dom_data = self.executor.page.evaluate("""() => {
                const elements = document.querySelectorAll('button, input, a, select, [role="button"]');
                return Array.from(elements).map(el => ({
                    tag: el.tagName,
                    id: el.id,
                    class: el.className,
                    text: (el.innerText || el.value || '').substring(0, 50),
                    type: el.type
                })).slice(0, 80);
            }""")

            # 3. Chiamata OpenRouter
            self._call_ai(dom_data)

        except Exception as e:
            self.error.emit(str(e))

    def _call_ai(self, dom_data):
        prompt = f"""
        Analizza questi elementi del sito {self.url}:
        {json.dumps(dom_data)}

        Genera YAML puro con chiavi: search_bar, login_button, match_row, price_element, confirm_button.
        """

        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "http://localhost",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "anthropic/claude-3.5-sonnet",
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=45 
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            clean_yaml = content.replace("```yaml", "").replace("```", "").strip()
            self.finished.emit(clean_yaml)
            
        except requests.exceptions.Timeout:
            self.error.emit("Timeout API AI (45s)")
        except Exception as e:
            self.error.emit(f"Errore AI: {e}")
