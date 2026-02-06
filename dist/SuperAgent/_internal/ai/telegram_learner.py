"""
Telegram Auto-Learning Parser
Learns to understand new message formats automatically using AI vision
"""
import json
import os
import re
import hashlib
from typing import Dict, List, Optional
from datetime import datetime
from ai.vision_learner import VisionLearner


class TelegramLearner:
    """
    Auto-learning Telegram message parser
    Uses AI to understand new formats and saves patterns for future use
    """
    
    def __init__(self, vision_learner: VisionLearner, logger=None, 
                 memory_file: str = "data/telegram_patterns.json",
                 min_confidence: float = 0.75,
                 min_examples_to_learn: int = 3):
        """
        Initialize Telegram Learner
        
        Args:
            vision_learner: VisionLearner instance
            logger: Logger instance
            memory_file: Path to pattern memory file
            min_confidence: Minimum confidence to use a pattern
            min_examples_to_learn: Number of examples before creating a pattern
        """
        self.vision = vision_learner
        self.logger = logger
        self.memory_file = memory_file
        self.min_confidence = min_confidence
        self.min_examples_to_learn = min_examples_to_learn
        
        # Load existing patterns
        self.patterns = self._load_patterns()
        
        # Temporary storage for unknown messages (for learning)
        self.unknown_messages = []
    
    def _load_patterns(self) -> Dict:
        """Load saved patterns from disk"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to load patterns: {e}")
        
        return {
            "patterns": [],
            "statistics": {
                "total_messages": 0,
                "learned_patterns": 0,
                "successful_parses": 0,
                "failed_parses": 0
            }
        }
    
    def _save_patterns(self):
        """Save patterns to disk"""
        try:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.patterns, f, indent=2, ensure_ascii=False)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save patterns: {e}")
    
    def _compute_hash(self, text: str) -> str:
        """Compute hash of message for deduplication"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _match_pattern(self, text: str) -> Optional[Dict]:
        """
        Try to match text against known patterns using regex
        
        Args:
            text: Message text
            
        Returns:
            Extracted data or None
        """
        for pattern in self.patterns.get("patterns", []):
            if not pattern.get("active", True):
                continue
            
            # Try each regex in the pattern
            for regex_def in pattern.get("regexes", []):
                try:
                    regex = regex_def.get("pattern")
                    matches = re.search(regex, text, re.MULTILINE | re.IGNORECASE)
                    
                    if matches:
                        # Extract named groups
                        extracted = matches.groupdict()
                        
                        # Apply any transformations
                        result = self._apply_transformations(extracted, pattern.get("transformations", {}))
                        
                        if self.logger:
                            self.logger.info(f"✅ Matched pattern: {pattern.get('name', 'unknown')}")
                        
                        return result
                        
                except re.error as e:
                    if self.logger:
                        self.logger.warning(f"Invalid regex in pattern: {e}")
                    continue
        
        return None
    
    def _apply_transformations(self, data: Dict, transformations: Dict) -> Dict:
        """Apply transformations to extracted data"""
        result = data.copy()
        
        for field, transform in transformations.items():
            if field in result and transform:
                value = result[field]
                
                # Clean whitespace
                if transform.get("strip"):
                    value = value.strip()
                
                # Convert to uppercase
                if transform.get("uppercase"):
                    value = value.upper()
                
                # Extract numbers only
                if transform.get("numbers_only"):
                    value = re.sub(r'[^\d.]', '', value)
                
                result[field] = value
        
        return result
    
    def parse_message(self, text: str, screenshot_b64: Optional[str] = None) -> Optional[Dict]:
        """
        Parse Telegram message with auto-learning
        
        Args:
            text: Message text
            screenshot_b64: Optional screenshot of the message (for vision AI)
            
        Returns:
            Parsed betting signal or None
        """
        self.patterns["statistics"]["total_messages"] += 1
        
        # Try known patterns first (fast)
        result = self._match_pattern(text)
        
        if result:
            self.patterns["statistics"]["successful_parses"] += 1
            self._save_patterns()
            return result
        
        # Unknown format - use AI
        if self.logger:
            self.logger.info("🤔 Unknown message format, using AI...")
        
        # Try vision AI if screenshot available
        if screenshot_b64:
            result = self._parse_with_vision(text, screenshot_b64)
        else:
            result = self._parse_with_text_ai(text)
        
        if result:
            self.patterns["statistics"]["successful_parses"] += 1
            
            # Store for learning
            self._store_for_learning(text, result)
            
            self._save_patterns()
            return result
        else:
            self.patterns["statistics"]["failed_parses"] += 1
            self._save_patterns()
            return None
    
    def _parse_with_vision(self, text: str, screenshot_b64: str) -> Optional[Dict]:
        """Parse using vision AI on screenshot"""
        schema_hint = """
        {
            "teams": "Team1 vs Team2",
            "score": "X-X",
            "market": "Over/Under X.X",
            "bet_type": "specific bet",
            "confidence": 0.0-1.0,
            "timestamp": "time if present",
            "additional_info": {}
        }
        """
        
        result = self.vision.extract_json_from_image(screenshot_b64, schema_hint)
        
        if result and self._validate_signal(result):
            if self.logger:
                self.logger.info(f"✅ Vision AI extracted: {result}")
            return result
        
        return None
    
    def _parse_with_text_ai(self, text: str) -> Optional[Dict]:
        """Parse using text AI"""
        context = """
        This is a betting signal message. Extract:
        - teams: team names
        - score: current score if present
        - market: betting market (Over/Under, etc.)
        - bet_type: specific bet recommendation
        - confidence: confidence level if mentioned
        """
        
        result = self.vision.understand_text(text, context)
        
        if result and self._validate_signal(result):
            if self.logger:
                self.logger.info(f"✅ Text AI extracted: {result}")
            return result
        
        return None
    
    def _validate_signal(self, signal: Dict) -> bool:
        """Validate that extracted signal has minimum required fields"""
        required = ["teams", "market"]
        return all(field in signal and signal[field] for field in required)
    
    def _store_for_learning(self, text: str, extracted: Dict):
        """Store message for pattern learning"""
        message_hash = self._compute_hash(text)
        
        # Check if already stored
        for msg in self.unknown_messages:
            if msg.get("hash") == message_hash:
                return
        
        self.unknown_messages.append({
            "hash": message_hash,
            "text": text,
            "extracted": extracted,
            "timestamp": datetime.now().isoformat()
        })
        
        if self.logger:
            self.logger.info(f"📚 Stored message for learning ({len(self.unknown_messages)} total)")
        
        # Check if we have enough examples to learn a pattern
        if len(self.unknown_messages) >= self.min_examples_to_learn:
            self._learn_new_pattern()
    
    def _learn_new_pattern(self):
        """Learn a new pattern from stored examples"""
        if len(self.unknown_messages) < self.min_examples_to_learn:
            return
        
        if self.logger:
            self.logger.info(f"🧠 Learning new pattern from {len(self.unknown_messages)} examples...")
        
        # Get texts for learning
        examples = [msg["text"] for msg in self.unknown_messages]
        
        # Ask AI to extract pattern
        pattern_def = self.vision.learn_pattern(
            examples,
            description="Telegram betting signal messages"
        )
        
        if pattern_def:
            # Add metadata
            pattern_def["name"] = f"learned_pattern_{len(self.patterns['patterns']) + 1}"
            pattern_def["learned_at"] = datetime.now().isoformat()
            pattern_def["examples_count"] = len(examples)
            pattern_def["active"] = True
            
            # Add to patterns
            self.patterns["patterns"].append(pattern_def)
            self.patterns["statistics"]["learned_patterns"] += 1
            
            if self.logger:
                self.logger.info(f"✅ Learned new pattern: {pattern_def['name']}")
            
            # Clear examples
            self.unknown_messages = []
            
            self._save_patterns()
        else:
            if self.logger:
                self.logger.warning("❌ Failed to learn pattern from examples")
    
    def get_statistics(self) -> Dict:
        """Get learning statistics"""
        stats = self.patterns.get("statistics", {}).copy()
        stats["active_patterns"] = len([p for p in self.patterns.get("patterns", []) if p.get("active")])
        stats["pending_examples"] = len(self.unknown_messages)
        
        if stats["total_messages"] > 0:
            stats["success_rate"] = stats["successful_parses"] / stats["total_messages"]
        else:
            stats["success_rate"] = 0.0
        
        return stats
    
    def force_learn_now(self):
        """Force learning from current examples (even if less than minimum)"""
        if len(self.unknown_messages) > 0:
            self._learn_new_pattern()
    
    def reset_learning(self):
        """Reset all learned patterns (use with caution!)"""
        if self.logger:
            self.logger.warning("⚠️ Resetting all learned patterns!")
        
        self.patterns = {
            "patterns": [],
            "statistics": {
                "total_messages": 0,
                "learned_patterns": 0,
                "successful_parses": 0,
                "failed_parses": 0
            }
        }
        self.unknown_messages = []
        self._save_patterns()
