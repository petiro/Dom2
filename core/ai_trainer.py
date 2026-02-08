"""
AITrainerEngine — AI-powered decision engine with conversational memory.

Provides:
  - Conversation memory (last N messages)
  - DOM snapshot analysis
  - Screenshot-based visual analysis
  - Universal system prompt for RPA context
"""
import json
import time
from collections import deque
from typing import Optional


SYSTEM_PROMPT_UNIVERSAL = """Sei SuperAgent, un assistente AI specializzato in:
- Automazione RPA su piattaforme di betting live
- Analisi DOM e selezione CSS/XPath di elementi
- Interpretazione di segnali Telegram (tip, quote, mercati)
- Analisi visiva di screenshot per trovare pulsanti e form
- Auto-healing dei selettori CSS rotti

Regole:
1. Rispondi SOLO in italiano
2. Sii conciso e tecnico
3. Se analizzi un DOM, suggerisci il selettore CSS migliore
4. Se analizzi uno screenshot, descrivi cosa vedi e dove cliccare
5. Non inventare informazioni — se non sei sicuro, dillo
"""


class AITrainerEngine:
    """AI engine with memory for multi-turn conversations and DOM/visual analysis.

    Usage:
        trainer = AITrainerEngine(vision_learner=vision, logger=logger)
        response = trainer.ask("Cosa vedi in questa pagina?", dom_snapshot=html)
        response = trainer.ask("Dove clicco?", screenshot_b64=img_data)
    """

    MAX_MEMORY = 10  # last N conversation turns

    def __init__(self, vision_learner=None, logger=None):
        self.vision = vision_learner
        self.logger = logger
        self._memory: deque = deque(maxlen=self.MAX_MEMORY)
        self._system_prompt = SYSTEM_PROMPT_UNIVERSAL

    @property
    def memory(self) -> list:
        """Return current conversation memory as list."""
        return list(self._memory)

    def clear_memory(self):
        """Reset conversation memory."""
        self._memory.clear()
        if self.logger:
            self.logger.info("[AITrainer] Memory cleared")

    def ask(self, user_message: str,
            dom_snapshot: Optional[str] = None,
            screenshot_b64: Optional[str] = None) -> str:
        """Send a message to the AI with optional DOM/screenshot context.

        Returns the AI response text.
        """
        if not self.vision:
            return "AI non disponibile (VisionLearner non inizializzato)"

        # Build context from memory
        context_parts = [self._system_prompt, ""]

        # Add conversation history
        if self._memory:
            context_parts.append("--- Conversazione precedente ---")
            for turn in self._memory:
                role = turn.get("role", "?")
                content = turn.get("content", "")
                context_parts.append(f"{role}: {content}")
            context_parts.append("--- Fine cronologia ---\n")

        # Add DOM snapshot if provided
        if dom_snapshot:
            # Truncate if too long
            if len(dom_snapshot) > 20000:
                dom_snapshot = dom_snapshot[:20000] + "\n... [TRONCATO]"
            context_parts.append(f"--- DOM Snapshot ---\n{dom_snapshot}\n--- Fine DOM ---\n")

        # Add screenshot description if provided
        if screenshot_b64:
            context_parts.append("[Screenshot allegato per analisi visiva]")

        context_parts.append(f"Utente: {user_message}")
        full_context = "\n".join(context_parts)

        # Store user message in memory
        self._memory.append({"role": "Utente", "content": user_message, "ts": time.time()})

        try:
            # Use vision learner for the query
            if screenshot_b64:
                # Visual analysis with screenshot
                result = self.vision.understand_image(
                    screenshot_b64,
                    prompt=full_context,
                    context="RPA visual analysis"
                )
            else:
                # Text-only analysis
                result = self.vision.understand_text(
                    full_context,
                    context="RPA trainer conversation"
                )

            # Extract response text
            if isinstance(result, dict):
                response_text = result.get("response", result.get("text", json.dumps(result, ensure_ascii=False)))
            elif isinstance(result, str):
                response_text = result
            else:
                response_text = str(result) if result else "Nessuna risposta dall'AI."

            # Store AI response in memory
            self._memory.append({"role": "AI", "content": response_text, "ts": time.time()})

            return response_text

        except Exception as e:
            error_msg = f"Errore AI: {e}"
            if self.logger:
                self.logger.error(f"[AITrainer] {error_msg}")
            self._memory.append({"role": "AI", "content": error_msg, "ts": time.time()})
            return error_msg

    def analyze_dom(self, dom_snapshot: str, question: str = "Analizza il DOM e suggerisci i selettori per gli elementi interattivi.") -> str:
        """Analyze a DOM snapshot and return AI insights."""
        return self.ask(question, dom_snapshot=dom_snapshot)

    def analyze_screenshot(self, screenshot_b64: str, question: str = "Descrivi cosa vedi e dove dovrei cliccare.") -> str:
        """Analyze a screenshot and return AI insights."""
        return self.ask(question, screenshot_b64=screenshot_b64)

    def get_action_suggestion(self, dom_snapshot: Optional[str] = None,
                               screenshot_b64: Optional[str] = None,
                               current_state: str = "") -> str:
        """Ask AI for next action suggestion given current context."""
        prompt = f"Stato attuale: {current_state}\nQual è la prossima azione da eseguire?"
        return self.ask(prompt, dom_snapshot=dom_snapshot, screenshot_b64=screenshot_b64)
