"""
RPA Self-Healing System
Two-tier healing: DOM text analysis (fast) → Screenshot AI vision (fallback)
Auto-detects when website changes and updates selectors.
"""
import json
import os
import yaml
import base64
from typing import Dict, List, Optional
from datetime import datetime
from ai.vision_learner import VisionLearner


class RPAHealer:
    """
    Self-healing RPA system:
    1. Detects when selectors break
    2. Tier 1: Scans DOM text → AI analyzes elements → generates selector
    3. Tier 2 (fallback): Takes screenshot → AI vision finds selector
    4. Auto-updates selectors.yaml with backup
    5. Saves healing history for learning
    """

    def __init__(self, vision_learner: VisionLearner, logger=None,
                 selectors_file: str = "config/selectors.yaml",
                 backup_dir: str = "data/selector_backups",
                 confidence_threshold: float = 0.8):
        self.vision = vision_learner
        self.logger = logger
        self.selectors_file = selectors_file
        self.backup_dir = backup_dir
        self.confidence_threshold = confidence_threshold

        self.healing_history = []
        self.history_file = "data/healing_history.json"

        self._load_history()
        os.makedirs(backup_dir, exist_ok=True)

    def _load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.healing_history = json.load(f)
            except Exception:
                self.healing_history = []

    def _save_history(self):
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.healing_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save healing history: {e}")

    def _backup_selectors(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"selectors_{timestamp}.yaml")
        try:
            if os.path.exists(self.selectors_file):
                with open(self.selectors_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return backup_path
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to create backup: {e}")
        return ""

    def _load_selectors(self) -> Dict:
        try:
            with open(self.selectors_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _save_selectors(self, selectors: Dict):
        try:
            with open(self.selectors_file, 'w', encoding='utf-8') as f:
                yaml.dump(selectors, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save selectors: {e}")

    def detect_selector_failure(self, page, selector_key: str, selectors: Dict) -> bool:
        """Returns True if selector is broken."""
        selector = selectors.get(selector_key)
        if not selector:
            return True

        try:
            if isinstance(selector, list):
                for sel in selector:
                    if page.locator(sel).count() > 0:
                        return False
                return True
            else:
                return page.locator(selector).count() == 0
        except Exception:
            return True

    def test_all_selectors(self, page, selectors: Dict) -> Dict[str, bool]:
        """Test all selectors, return dict of selector_key -> working (bool)."""
        results = {}
        for key in selectors:
            results[key] = not self.detect_selector_failure(page, key, selectors)

        broken = [k for k, v in results.items() if not v]
        if broken and self.logger:
            self.logger.warning(f"Broken selectors: {broken}")

        return results

    # ── TIER 1: DOM Text Analysis (fast, no screenshot) ──────────────

    def _heal_via_dom_scan(self, page, selector_key: str, element_description: str) -> Optional[str]:
        """
        Tier 1 healing: scan DOM as text, ask AI to find the right selector.
        Faster and more precise than screenshot-based approach.
        """
        if self.logger:
            self.logger.info(f"Tier 1 (DOM scan) healing: {selector_key}")

        try:
            from core.dom_scanner import scan_dom

            dom_data = scan_dom(page)
            if not dom_data:
                if self.logger:
                    self.logger.warning("DOM scan returned no elements")
                return None

            # Trim to fit API context
            dom_text = json.dumps(dom_data[:200], ensure_ascii=False)
            if len(dom_text) > 8000:
                dom_text = dom_text[:8000]

            prompt = f"""Analyze this DOM data from a betting website.
Find the CSS selector for: {element_description}

DOM elements:
{dom_text}

Rules:
1. Return ONLY the CSS selector string, nothing else
2. Prefer: [data-testid], #id, .specific-class, tag:has-text("text")
3. The selector must be specific enough to match exactly one element
4. Do NOT return explanations, just the raw selector

Selector:"""

            messages = [{"role": "user", "content": prompt}]
            response = self.vision._call_api(messages, temperature=0.1, max_tokens=100)

            if not response:
                return None

            # Clean response
            selector = response.strip().strip('`').strip('"').strip("'")
            if '\n' in selector:
                selector = selector.split('\n')[0].strip()

            # Validate: does it actually find the element?
            try:
                count = page.locator(selector).count()
                if count > 0:
                    if self.logger:
                        self.logger.info(f"Tier 1 found selector: {selector} ({count} matches)")
                    return selector
                else:
                    if self.logger:
                        self.logger.warning(f"Tier 1 selector not found on page: {selector}")
            except Exception:
                if self.logger:
                    self.logger.warning(f"Tier 1 invalid selector: {selector}")

            return None

        except ImportError:
            if self.logger:
                self.logger.warning("dom_scanner not available, skipping Tier 1")
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Tier 1 healing error: {e}")
            return None

    # ── TIER 2: Screenshot + AI Vision (fallback) ────────────────────

    def _heal_via_screenshot(self, page, selector_key: str, element_description: str) -> Optional[str]:
        """
        Tier 2 healing: take screenshot, use AI vision to find new selector.
        Used as fallback when DOM text analysis fails.
        """
        if self.logger:
            self.logger.info(f"Tier 2 (screenshot) healing: {selector_key}")

        try:
            screenshot = page.screenshot()
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

            new_selector = self.vision.find_selector(screenshot_b64, element_description)

            if not new_selector:
                return None

            # Validate
            try:
                count = page.locator(new_selector).count()
                if count > 0:
                    if self.logger:
                        self.logger.info(f"Tier 2 found selector: {new_selector}")
                    return new_selector
            except Exception:
                pass

            return None

        except Exception as e:
            if self.logger:
                self.logger.error(f"Tier 2 healing error: {e}")
            return None

    # ── Combined Healing ─────────────────────────────────────────────

    def heal_selector(self, page, selector_key: str, element_description: str,
                      auto_update: bool = True) -> Optional[str]:
        """
        Heal a broken selector using two-tier approach:
        1. DOM text scan + AI analysis (fast)
        2. Screenshot + AI vision (fallback)
        """
        if self.logger:
            self.logger.info(f"Healing selector: {selector_key}")

        # Tier 1: DOM text analysis
        new_selector = self._heal_via_dom_scan(page, selector_key, element_description)

        # Tier 2: Screenshot fallback
        if not new_selector:
            new_selector = self._heal_via_screenshot(page, selector_key, element_description)

        if not new_selector:
            if self.logger:
                self.logger.error(f"All healing tiers failed for: {selector_key}")
            return None

        # Record healing
        healing_record = {
            "timestamp": datetime.now().isoformat(),
            "selector_key": selector_key,
            "element_description": element_description,
            "new_selector": new_selector,
            "auto_updated": auto_update
        }
        self.healing_history.append(healing_record)
        self._save_history()

        # Auto-update config
        if auto_update:
            self._backup_selectors()
            selectors = self._load_selectors()
            selectors[selector_key] = new_selector
            self._save_selectors(selectors)
            if self.logger:
                self.logger.info(f"Updated {selector_key} in config")

        return new_selector

    def auto_heal_all(self, page, selector_descriptions: Dict[str, str]) -> Dict[str, str]:
        """Heal all broken selectors."""
        if self.logger:
            self.logger.info(f"Auto-healing {len(selector_descriptions)} selectors...")

        healed = {}
        for key, description in selector_descriptions.items():
            new_selector = self.heal_selector(page, key, description, auto_update=True)
            if new_selector:
                healed[key] = new_selector

        if self.logger:
            self.logger.info(f"Healed {len(healed)}/{len(selector_descriptions)} selectors")

        return healed

    def full_site_relearn(self, page) -> Dict[str, str]:
        """
        Full site re-learning: scan entire DOM, ask AI to identify all key elements,
        and rebuild selectors.yaml from scratch.
        Used when the site has changed significantly.
        """
        if self.logger:
            self.logger.info("FULL SITE RELEARN: scanning entire page...")

        try:
            from core.dom_scanner import scan_dom

            dom_data = scan_dom(page, max_elements=400)
            dom_text = json.dumps(dom_data[:300], ensure_ascii=False)
            if len(dom_text) > 8000:
                dom_text = dom_text[:8000]

            prompt = f"""Analyze this DOM from a betting website (bet365).
Identify CSS selectors for these key elements:
- login_button: the login button
- search_button: search/find match button
- search_input: search text input
- bet_button: place bet / "Piazza" button
- stake_input: stake amount input field
- score: live score display
- odds_value: odds number display
- event_name: match/team names display

DOM:
{dom_text}

Respond ONLY with valid JSON mapping element names to CSS selectors:
{{"login_button": "selector", "search_button": "selector", ...}}
Only include elements you can confidently identify. Skip uncertain ones."""

            messages = [{"role": "user", "content": prompt}]
            response = self.vision._call_api(messages, temperature=0.2, max_tokens=500)

            if not response:
                if self.logger:
                    self.logger.error("AI returned no response for full relearn")
                return {}

            # Parse JSON response
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            new_selectors = json.loads(response)

            # Validate each selector on the live page
            validated = {}
            for key, selector in new_selectors.items():
                try:
                    if page.locator(selector).count() > 0:
                        validated[key] = selector
                    else:
                        if self.logger:
                            self.logger.warning(f"Relearn: {key} selector not found on page: {selector}")
                except Exception:
                    continue

            if validated:
                # Backup and save
                self._backup_selectors()
                current = self._load_selectors()
                current.update(validated)
                self._save_selectors(current)

                if self.logger:
                    self.logger.info(f"Full relearn complete: {len(validated)} selectors updated")

                # Record in history
                self.healing_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "type": "full_relearn",
                    "selectors_updated": list(validated.keys()),
                    "auto_updated": True
                })
                self._save_history()

            return validated

        except Exception as e:
            if self.logger:
                self.logger.error(f"Full relearn failed: {e}")
            return {}

    def get_healing_statistics(self) -> Dict:
        total = len(self.healing_history)
        auto_updated = sum(1 for h in self.healing_history if h.get("auto_updated"))

        by_key = {}
        for record in self.healing_history:
            key = record.get("selector_key", record.get("type", "unknown"))
            by_key[key] = by_key.get(key, 0) + 1

        return {
            "total_healings": total,
            "auto_updated": auto_updated,
            "manual": total - auto_updated,
            "by_selector": by_key,
            "last_healing": self.healing_history[-1] if self.healing_history else None
        }
