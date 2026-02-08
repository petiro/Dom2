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
            # Naviga se necessario (opzionale se già sulla pagina)
            if self.executor.page.url != self.url:
                self.executor.page.goto(self.url, wait_until="networkidle")

            # Estrai DOM leggero
            dom_data = self.executor.page.evaluate("""() => {
                const elements = document.querySelectorAll('button, input, a, select, [role="button"]');
                return Array.from(elements).map(el => ({
                    tag: el.tagName,
                    id: el.id,
                    class: el.className,
                    text: el.innerText || el.placeholder || el.value,
                    type: el.type
                })).slice(0, 100);
            }""")

            # Chiama AI
            yaml_code = self._call_openrouter(dom_data)
            self.finished.emit(yaml_code)

        except Exception as e:
            self.error.emit(str(e))

    def _call_openrouter(self, dom_data):
        prompt = f"""
        Analizza questi elementi del sito {self.url}:
        {json.dumps(dom_data)}

        Genera YAML puro con chiavi: search_bar, login_button, match_row, price_element, confirm_button.
        Nessun testo introduttivo, solo codice YAML.
        """

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )
        
        if response.status_code != 200:
            raise Exception(f"OpenRouter Error: {response.text}")

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        # Pulisci eventuali markdown ```yaml
        return content.replace("```yaml", "").replace("```", "").strip()
