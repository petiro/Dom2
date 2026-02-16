"""
AITrainerEngine V4 — AI-powered decision engine with conversational memory.

Features:
  - Conversation memory (last N messages)
  - DOM snapshot analysis
  - Screenshot-based visual analysis
  - Universal system prompt for RPA context
  - V4: train_step() full pipeline (Snapshot→Vision→LLM→Memory)
  - V4: heal_selector() self-healing protocol
  - V4: set_executor() for direct executor reference
"""
import json
import time
from collections import deque
from typing import Optional


SYSTEM_PROMPT_UNIVERSAL = """You are SuperAgent, an AI assistant specialized in:
- RPA automation on live betting platforms
- DOM analysis and CSS/XPath element selection
- Telegram signal interpretation (tips, odds, markets)
- Visual screenshot analysis to find buttons and forms
- Auto-healing of broken CSS selectors

Rules:
1. Be concise and technical
2. When analyzing DOM, suggest the best CSS selector
3. When analyzing a screenshot, describe what you see and where to click
4. Do not invent information — if unsure, say so
"""

# Maximum screenshot payload size (500KB base64)
MAX_SCREENSHOT_B64_SIZE = 500_000


class AITrainerEngine:
    """AI engine with memory for multi-turn conversations and DOM/visual analysis.

    V4 enhancements:
      - train_step() for full Snapshot→Vision→LLM pipeline
      - heal_selector() for broken selector repair via AI
      - set_executor() for direct executor reference

    Usage:
        trainer = AITrainerEngine(vision_learner=vision, logger=logger)
        trainer.set_executor(executor)
        response = trainer.ask("Cosa vedi in questa pagina?", dom_snapshot=html)
        new_css = trainer.heal_selector("button.old-class", "Pulsante Piazza Scommessa")
    """

    MAX_MEMORY = 10  # last N conversation turns
    DOM_MAX_LENGTH = 20000  # max chars for DOM snapshot truncation

    def __init__(self, vision_learner=None, logger=None):
        self.vision = vision_learner
        self.logger = logger
        self._memory: deque = deque(maxlen=self.MAX_MEMORY)
        self._system_prompt = SYSTEM_PROMPT_UNIVERSAL
        self._executor = None  # V4: direct executor reference

    # ------------------------------------------------------------------
    #  V4: Dependency injection
    # ------------------------------------------------------------------
    def set_executor(self, executor):
        """Set executor reference for direct DOM/screenshot access."""
        self._executor = executor
        if self.logger:
            self.logger.info("[AITrainer] Executor connected")

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
            return "AI not available (VisionLearner not initialized)"

        # Build context from memory
        context_parts = [self._system_prompt, ""]

        # Add conversation history
        if self._memory:
            context_parts.append("--- Previous conversation ---")
            for turn in self._memory:
                role = turn.get("role", "?")
                content = turn.get("content", "")
                context_parts.append(f"{role}: {content}")
            context_parts.append("--- End history ---\n")

        # Add DOM snapshot if provided
        if dom_snapshot:
            # Truncate if too long
            if len(dom_snapshot) > self.DOM_MAX_LENGTH:
                dom_snapshot = dom_snapshot[:self.DOM_MAX_LENGTH] + "\n... [TRUNCATED]"
            context_parts.append(f"--- DOM Snapshot ---\n{dom_snapshot}\n--- End DOM ---\n")

        # Add screenshot description if provided (with size cap)
        if screenshot_b64:
            if len(screenshot_b64) > MAX_SCREENSHOT_B64_SIZE:
                screenshot_b64 = screenshot_b64[:MAX_SCREENSHOT_B64_SIZE]
                if self.logger:
                    self.logger.warning(f"[AITrainer] Screenshot truncated to {MAX_SCREENSHOT_B64_SIZE} chars")
            context_parts.append("[Screenshot attached for visual analysis]")

        context_parts.append(f"User: {user_message}")
        full_context = "\n".join(context_parts)

        # Store user message in memory
        self._memory.append({"role": "User", "content": user_message, "ts": time.time()})

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
                response_text = str(result) if result else "No response from AI."

            # Store AI response in memory
            self._memory.append({"role": "AI", "content": response_text, "ts": time.time()})

            return response_text

        except Exception as e:
            error_msg = f"AI Error: {e}"
            if self.logger:
                self.logger.error(f"[AITrainer] {error_msg}")
            self._memory.append({"role": "AI", "content": error_msg, "ts": time.time()})
            return error_msg

    def analyze_dom(self, dom_snapshot: str, question: str = "Analyze the DOM and suggest selectors for interactive elements.") -> str:
        """Analyze a DOM snapshot and return AI insights."""
        return self.ask(question, dom_snapshot=dom_snapshot)

    def analyze_screenshot(self, screenshot_b64: str, question: str = "Describe what you see and where I should click.") -> str:
        """Analyze a screenshot and return AI insights."""
        return self.ask(question, screenshot_b64=screenshot_b64)

    def get_action_suggestion(self, dom_snapshot: Optional[str] = None,
                               screenshot_b64: Optional[str] = None,
                               current_state: str = "") -> str:
        """Ask AI for next action suggestion given current context."""
        prompt = f"Current state: {current_state}\nWhat is the next action to execute?"
        return self.ask(prompt, dom_snapshot=dom_snapshot, screenshot_b64=screenshot_b64)

    # ------------------------------------------------------------------
    #  V4: Full Training Pipeline
    # ------------------------------------------------------------------
    def train_step(self) -> str:
        """Full training pipeline: Snapshot → Vision → LLM → Memory.

        Captures current page state (DOM + screenshot), asks AI to analyze it,
        stores the result in memory. Returns the AI analysis text.
        """
        if not self._executor:
            return "Executor not connected to trainer."
        if not self.vision:
            return "VisionLearner not available."

        if self.logger:
            self.logger.info("[AITrainer] train_step() — starting pipeline")

        # 1. Capture DOM snapshot
        dom = ""
        try:
            dom = self._executor.get_dom_snapshot()
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[AITrainer] DOM snapshot failed: {e}")

        # 2. Capture screenshot
        screenshot = ""
        try:
            screenshot = self._executor.take_screenshot_b64()
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[AITrainer] Screenshot failed: {e}")

        # 3. Ask AI to analyze the current state
        prompt = (
            "Analyze the current page state. "
            "Identify: 1) Where I am (page/section) "
            "2) Visible interactive elements (buttons, forms, links) "
            "3) Recommended CSS selectors for key elements "
            "4) Any anomalies or issues on the page"
        )

        result = self.ask(prompt, dom_snapshot=dom, screenshot_b64=screenshot)

        if self.logger:
            self.logger.info(f"[AITrainer] train_step() completed — {len(result)} chars")

        return result

    # ------------------------------------------------------------------
    #  V4: Self-Healing Selector
    # ------------------------------------------------------------------
    def heal_selector(self, broken_selector: str, element_description: str) -> Optional[str]:
        """AI-powered selector healing: given a broken CSS selector and
        a description of what it should match, analyze the current DOM
        and return a new working selector.

        Returns the new CSS selector string, or None if healing failed.
        """
        if not self._executor:
            if self.logger:
                self.logger.warning("[AITrainer] heal_selector: no executor")
            return None
        if not self.vision:
            if self.logger:
                self.logger.warning("[AITrainer] heal_selector: no vision")
            return None

        if self.logger:
            self.logger.info(f"[AITrainer] Healing selector: {broken_selector}")

        # 1. Get current DOM
        dom = ""
        try:
            dom = self._executor.get_dom_snapshot()
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[AITrainer] heal DOM snapshot failed: {e}")

        # 2. Get screenshot for visual context
        screenshot = ""
        try:
            screenshot = self._executor.take_screenshot_b64()
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[AITrainer] heal screenshot failed: {e}")

        # 3. Ask AI for a new selector
        prompt = (
            f"The CSS selector '{broken_selector}' no longer works.\n"
            f"The element it was looking for: {element_description}\n\n"
            f"Analyze the DOM and screenshot. Find the correct element and "
            f"suggest a NEW working CSS selector.\n"
            f"Respond ONLY with the new CSS selector, no explanations.\n"
            f"Example response: button.submit-bet"
        )

        try:
            # Try with screenshot first
            if screenshot:
                result = self.vision.understand_image(
                    screenshot,
                    prompt=f"{self._system_prompt}\n\nDOM:\n{dom[:self.DOM_MAX_LENGTH // 2]}\n\n{prompt}",
                    context="selector-healing"
                )
            else:
                result = self.vision.understand_text(
                    f"{self._system_prompt}\n\nDOM:\n{dom[:self.DOM_MAX_LENGTH]}\n\n{prompt}",
                    context="selector-healing"
                )

            # Extract selector from response
            if isinstance(result, dict):
                selector = result.get("response", result.get("text", ""))
            elif isinstance(result, str):
                selector = result
            else:
                selector = str(result) if result else ""

            # Clean up: take first line, strip whitespace
            selector = selector.strip().split("\n")[0].strip()

            # Basic validation: must look like a CSS selector
            if selector and not selector.startswith("Errore") and len(selector) < 200:
                if self.logger:
                    self.logger.info(f"[AITrainer] Healed selector: {broken_selector} -> {selector}")
                return selector

        except Exception as e:
            if self.logger:
                self.logger.error(f"[AITrainer] heal_selector failed: {e}")

        return None
