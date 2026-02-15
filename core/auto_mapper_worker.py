import requests
import logging
import json
import os
import time
import yaml
from PySide6.QtCore import QObject, Signal
from core.config_loader import load_secure_config
from core.utils import get_project_root


class AutoMapperWorker(QObject):
    """
    V7.2 Auto-Discovery Worker.

    Pipeline:
    1. SCAN: Use executor.scan_page_elements() to extract interactive DOM elements
    2. AI PREDICT: Send element list to AI to identify selectors
    3. VERIFY: Physically test each selector on the live page
    4. SAVE: Write validated selectors to config/selectors.yaml
    """
    finished = Signal(dict)
    error = Signal(str)
    status = Signal(str)

    # Resilient model list (Feb 2026)
    AI_MODELS = [
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-oss-120b:free",
        "qwen/qwen-3-coder-480b-a35b-instruct:free",
        "google/gemini-2.0-flash-lite-preview-02-05:free",
        "arcee-ai/trinity-large-preview:free",
    ]

    def __init__(self, executor, url):
        super().__init__()
        self.executor = executor
        self.url = url
        self.logger = logging.getLogger("AutoMapper")
        self.secrets = load_secure_config()
        self.api_key = self.secrets.get("openrouter_api_key")

    def run(self):
        """Execute the full auto-discovery pipeline."""
        try:
            # 1. SCAN
            self.status.emit(f"Scanning DOM structure: {self.url}...")
            elements = self.executor.scan_page_elements(self.url)

            if not elements:
                self.error.emit("Scanner failed: could not read page elements.")
                self.finished.emit({})
                return

            self.status.emit(f"AI analyzing {len(elements)} interactive elements...")

            # 2. AI PREDICT
            found_selectors = self._ask_ai_for_selectors(elements)

            if not found_selectors:
                self.error.emit("AI could not find valid selector matches.")
                self.finished.emit({})
                return

            # 3. VERIFY
            self.status.emit("Physically verifying selectors on page...")
            validated = {}
            for key, selector in found_selectors.items():
                if selector == "NOT_FOUND":
                    continue

                self.status.emit(f"Testing {key}: {selector}...")
                if self.executor.verify_selector_validity(selector):
                    self.logger.info(f"✅ {key} CONFIRMED: {selector}")
                    validated[key] = selector
                else:
                    self.logger.warning(f"⚠️ {key} discarded (element not responsive): {selector}")

            # 4. SAVE
            if validated:
                self._save_selectors(validated)
                self.status.emit(f"Saved {len(validated)} validated selectors.")
            else:
                self.status.emit("No selectors passed physical verification.")

            self.finished.emit(validated)

        except Exception as e:
            self.logger.error(f"AutoMapper critical error: {e}", exc_info=True)
            self.error.emit(f"Critical error: {str(e)}")

    def _ask_ai_for_selectors(self, elements):
        """Send element list to AI with model fallback chain."""
        if not self.api_key:
            self.error.emit("OpenRouter API key missing.")
            return {}

        prompt = (
            "You are an expert in Web Scraping and Browser Automation.\n"
            "Here is a JSON list of interactive elements extracted from a bookmaker page:\n\n"
            f"{json.dumps(elements[:150])}\n\n"
            "Identify the correct CSS selectors for these functions:\n"
            '1. "login_button": Button to log in (text: Accedi, Login, Entra)\n'
            '2. "balance_selector": Element showing account balance\n'
            '3. "search_button": Button to open search\n'
            '4. "search_input": Input field for searching events\n'
            '5. "stake_input": Input where bet amount is typed\n'
            '6. "place_button": Final bet placement button (Scommetti, Piazza)\n'
            '7. "bet_confirm_msg": Confirmation message after bet\n\n'
            'Respond ONLY with JSON: { "login_button": "...", ... }\n'
            'Use "NOT_FOUND" if uncertain.'
        )

        for model in self.AI_MODELS:
            self.logger.info(f"Trying model: {model}")
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "https://github.com/petiro/Dom2",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                    },
                    timeout=45,
                )

                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    content = choices[0].get("message", {}).get("content", "")
                    if not content:
                        continue

                    self.logger.info(f"✅ Mapping completed with {model}")
                    return self._parse_ai_response(content)

                elif response.status_code in [429, 500, 502, 503]:
                    self.logger.warning(
                        f"Model {model} unavailable ({response.status_code}). Trying next..."
                    )
                    time.sleep(1)
                    continue
                else:
                    self.logger.error(
                        f"Unexpected {response.status_code} from {model}: {response.text}"
                    )
                    continue

            except Exception as e:
                self.logger.error(f"Exception with model {model}: {e}")
                continue

        return {}

    def _parse_ai_response(self, content):
        """Parse AI JSON response, stripping markdown fences."""
        try:
            clean = content.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except Exception as e:
            self.logger.error(f"AI response parse error: {e}")
            return {"raw_response": content}

    def _save_selectors(self, new_data):
        """Merge validated selectors into existing config/selectors.yaml."""
        path = os.path.join(get_project_root(), "config", "selectors.yaml")
        current = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    current = yaml.safe_load(f) or {}
            except Exception:
                pass

        current.update(new_data)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(current, f, default_flow_style=False)
