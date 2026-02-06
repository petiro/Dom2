"""
RPA Self-Healing System
Automatically detects when website changes and updates selectors using AI vision
"""
import json
import os
import yaml
import base64
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from ai.vision_learner import VisionLearner


class RPAHealer:
    """
    Self-healing RPA system that:
    1. Detects when selectors break
    2. Takes screenshots
    3. Uses AI to find new selectors
    4. Auto-updates configuration
    """
    
    def __init__(self, vision_learner: VisionLearner, logger=None,
                 selectors_file: str = "config/selectors.yaml",
                 backup_dir: str = "data/selector_backups",
                 confidence_threshold: float = 0.8):
        """
        Initialize RPA Healer
        
        Args:
            vision_learner: VisionLearner instance
            logger: Logger instance
            selectors_file: Path to selectors YAML
            backup_dir: Directory for selector backups
            confidence_threshold: Minimum confidence for auto-update
        """
        self.vision = vision_learner
        self.logger = logger
        self.selectors_file = selectors_file
        self.backup_dir = backup_dir
        self.confidence_threshold = confidence_threshold
        
        # History of selector changes
        self.healing_history = []
        self.history_file = "data/healing_history.json"
        
        # Load history
        self._load_history()
        
        # Create backup dir
        os.makedirs(backup_dir, exist_ok=True)
    
    def _load_history(self):
        """Load healing history from disk"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.healing_history = json.load(f)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to load healing history: {e}")
                self.healing_history = []
    
    def _save_history(self):
        """Save healing history to disk"""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.healing_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save healing history: {e}")
    
    def _backup_selectors(self) -> str:
        """Create backup of current selectors file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"selectors_{timestamp}.yaml")
        
        try:
            if os.path.exists(self.selectors_file):
                with open(self.selectors_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                if self.logger:
                    self.logger.info(f"📦 Backup created: {backup_path}")
                
                return backup_path
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to create backup: {e}")
        
        return ""
    
    def _load_selectors(self) -> Dict:
        """Load current selectors from YAML"""
        try:
            with open(self.selectors_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load selectors: {e}")
            return {}
    
    def _save_selectors(self, selectors: Dict):
        """Save selectors to YAML"""
        try:
            with open(self.selectors_file, 'w', encoding='utf-8') as f:
                yaml.dump(selectors, f, default_flow_style=False, allow_unicode=True)
            
            if self.logger:
                self.logger.info(f"✅ Selectors saved to {self.selectors_file}")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save selectors: {e}")
    
    def detect_selector_failure(self, page, selector_key: str, selectors: Dict) -> bool:
        """
        Detect if a selector is no longer working
        
        Args:
            page: Playwright page object
            selector_key: Key in selectors dict (e.g., "bet_button")
            selectors: Current selectors dict
            
        Returns:
            True if selector is broken
        """
        selector = selectors.get(selector_key)
        
        if not selector:
            return True
        
        try:
            # Try to find element
            if isinstance(selector, list):
                # Multiple selectors, try all
                for sel in selector:
                    if page.locator(sel).count() > 0:
                        return False
                return True
            else:
                # Single selector
                return page.locator(selector).count() == 0
        except Exception:
            return True
    
    def heal_selector(self, page, selector_key: str, element_description: str, 
                     auto_update: bool = True) -> Optional[str]:
        """
        Heal a broken selector using AI vision
        
        Args:
            page: Playwright page object
            selector_key: Key in selectors dict (e.g., "bet_button")
            element_description: Human description of what to find
            auto_update: Whether to auto-update the config file
            
        Returns:
            New selector string or None if healing failed
        """
        if self.logger:
            self.logger.info(f"🔧 Attempting to heal selector: {selector_key}")
        
        try:
            # Take screenshot
            screenshot = page.screenshot()
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
            
            # Ask AI to find new selector
            new_selector = self.vision.find_selector(screenshot_b64, element_description)
            
            if not new_selector:
                if self.logger:
                    self.logger.error(f"❌ AI could not find selector for: {element_description}")
                return None
            
            # Test new selector
            try:
                count = page.locator(new_selector).count()
                if count == 0:
                    if self.logger:
                        self.logger.warning(f"⚠️ AI suggested selector not found: {new_selector}")
                    return None
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"⚠️ AI suggested invalid selector: {new_selector} - {e}")
                return None
            
            if self.logger:
                self.logger.info(f"✅ Found new selector: {new_selector}")
            
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
            
            # Auto-update if enabled
            if auto_update:
                self._update_selector(selector_key, new_selector)
            
            return new_selector
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error during healing: {e}")
            return None
    
    def _update_selector(self, selector_key: str, new_selector: str):
        """Update selector in config file"""
        # Backup first
        self._backup_selectors()
        
        # Load current selectors
        selectors = self._load_selectors()
        
        # Update
        selectors[selector_key] = new_selector
        
        # Save
        self._save_selectors(selectors)
        
        if self.logger:
            self.logger.info(f"✅ Updated {selector_key} in config")
    
    def detect_layout_change(self, page, reference_screenshot_path: Optional[str] = None) -> bool:
        """
        Detect if website layout has changed significantly
        
        Args:
            page: Playwright page object
            reference_screenshot_path: Path to reference screenshot (or None to use last known)
            
        Returns:
            True if significant changes detected
        """
        try:
            # Take current screenshot
            current = page.screenshot()
            current_b64 = base64.b64encode(current).decode('utf-8')
            
            # Get reference
            if reference_screenshot_path and os.path.exists(reference_screenshot_path):
                with open(reference_screenshot_path, 'rb') as f:
                    reference_b64 = base64.b64encode(f.read()).decode('utf-8')
            else:
                # No reference, save current as reference
                ref_path = "data/reference_screenshot.png"
                os.makedirs(os.path.dirname(ref_path), exist_ok=True)
                with open(ref_path, 'wb') as f:
                    f.write(current)
                if self.logger:
                    self.logger.info(f"📸 Saved reference screenshot: {ref_path}")
                return False
            
            # Compare with AI
            result = self.vision.detect_layout_change(reference_b64, current_b64)
            
            if result and result.get("changed"):
                if self.logger:
                    self.logger.warning(f"⚠️ Layout change detected: {result.get('description')}")
                return True
            
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error detecting layout change: {e}")
            return False
    
    def auto_heal_all(self, page, selector_descriptions: Dict[str, str]) -> Dict[str, str]:
        """
        Attempt to heal all selectors at once
        
        Args:
            page: Playwright page object
            selector_descriptions: Dict mapping selector_key -> description
                Example: {"bet_button": "place bet button", "score": "live score display"}
        
        Returns:
            Dict of successfully healed selectors
        """
        if self.logger:
            self.logger.info(f"🔧 Auto-healing {len(selector_descriptions)} selectors...")
        
        healed = {}
        
        for key, description in selector_descriptions.items():
            new_selector = self.heal_selector(page, key, description, auto_update=True)
            if new_selector:
                healed[key] = new_selector
        
        if self.logger:
            self.logger.info(f"✅ Successfully healed {len(healed)}/{len(selector_descriptions)} selectors")
        
        return healed
    
    def get_healing_statistics(self) -> Dict:
        """Get statistics about healing operations"""
        total = len(self.healing_history)
        auto_updated = sum(1 for h in self.healing_history if h.get("auto_updated"))
        
        # Group by selector key
        by_key = {}
        for record in self.healing_history:
            key = record.get("selector_key", "unknown")
            by_key[key] = by_key.get(key, 0) + 1
        
        return {
            "total_healings": total,
            "auto_updated": auto_updated,
            "manual": total - auto_updated,
            "by_selector": by_key,
            "last_healing": self.healing_history[-1] if self.healing_history else None
        }
    
    def test_all_selectors(self, page, selectors: Dict) -> Dict[str, bool]:
        """
        Test all selectors and report which are broken
        
        Args:
            page: Playwright page object
            selectors: Selectors dict
            
        Returns:
            Dict mapping selector_key -> working (bool)
        """
        results = {}
        
        for key in selectors:
            results[key] = not self.detect_selector_failure(page, key, selectors)
        
        broken = [k for k, v in results.items() if not v]
        
        if broken and self.logger:
            self.logger.warning(f"⚠️ Broken selectors detected: {broken}")
        
        return results
