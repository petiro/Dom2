"""
Vision Learner - Core AI module with OpenRouter integration
Handles vision-based understanding for both Telegram messages and web pages
"""
import requests
import json
import base64
import time
from typing import Dict, List, Optional, Any


class VisionLearner:
    """
    Core AI vision learner using OpenRouter API (free models)
    Handles both text and image understanding
    """
    
    def __init__(self, api_key: str, model: str = "google/gemini-2.0-flash-exp:free", logger=None):
        """
        Initialize Vision Learner
        
        Args:
            api_key: OpenRouter API key
            model: Model to use (default: free Gemini)
            logger: Optional logger instance
        """
        self.api_key = api_key
        self.model = model
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        self.logger = logger
        
        # Rate limiting
        self.last_call = 0
        self.min_interval = 1  # seconds between calls
    
    def _rate_limit(self):
        """Simple rate limiting to avoid hitting API limits"""
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()
    
    def _call_api(self, messages: List[Dict], temperature: float = 0.3, max_tokens: int = 1000) -> Optional[str]:
        """
        Call OpenRouter API
        
        Args:
            messages: List of message dicts with role and content
            temperature: Sampling temperature
            max_tokens: Max tokens in response
            
        Returns:
            API response text or None on error
        """
        self._rate_limit()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/your-repo",  # Optional
            "X-Title": "DomNativeAgent"  # Optional
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(self.url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                return content.strip()
            else:
                if self.logger:
                    self.logger.error(f"Unexpected API response format: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            if self.logger:
                self.logger.error(f"API call failed: {e}")
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error processing API response: {e}")
            return None
    
    def understand_text(self, text: str, context: str = "") -> Optional[Dict]:
        """
        Understand pure text content
        
        Args:
            text: Text to analyze
            context: Optional context about what we're looking for
            
        Returns:
            Structured understanding as dict
        """
        prompt = f"""
Analyze this text and extract structured information.
{f'Context: {context}' if context else ''}

Text:
{text}

Respond ONLY with valid JSON. No markdown, no code blocks, just raw JSON.
Extract all relevant information in a structured format.
"""
        
        messages = [{"role": "user", "content": prompt}]
        response = self._call_api(messages, temperature=0.3)
        
        if not response:
            return None
        
        try:
            # Clean markdown if present
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            return json.loads(response)
        except json.JSONDecodeError as e:
            if self.logger:
                self.logger.error(f"Failed to parse JSON response: {e}")
                self.logger.error(f"Response was: {response}")
            return None
    
    def understand_image(self, image_b64: str, question: str) -> Optional[str]:
        """
        Understand image content with vision AI
        
        Args:
            image_b64: Base64 encoded image
            question: What to look for in the image
            
        Returns:
            AI's answer as text
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                    }
                ]
            }
        ]
        
        return self._call_api(messages, temperature=0.3)
    
    def extract_json_from_image(self, image_b64: str, schema_hint: str = "") -> Optional[Dict]:
        """
        Extract structured JSON data from image (e.g., Telegram message screenshot)
        
        Args:
            image_b64: Base64 encoded image
            schema_hint: Optional hint about expected JSON structure
            
        Returns:
            Extracted data as dict
        """
        prompt = f"""
Analyze this image and extract ALL information as structured JSON.

{f'Expected structure: {schema_hint}' if schema_hint else ''}

Rules:
1. Extract EVERYTHING visible (text, numbers, symbols, emojis)
2. Identify the format/pattern of the message
3. Return ONLY valid JSON, no markdown, no explanations
4. If it's a betting signal, extract: teams, score, market, bet_type, confidence

Respond with raw JSON only.
"""
        
        response = self.understand_image(image_b64, prompt)
        
        if not response:
            return None
        
        try:
            # Clean markdown if present
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            return json.loads(response)
        except json.JSONDecodeError as e:
            if self.logger:
                self.logger.error(f"Failed to parse JSON from vision response: {e}")
                self.logger.error(f"Response was: {response}")
            return None
    
    def find_selector(self, screenshot_b64: str, element_description: str) -> Optional[str]:
        """
        Find CSS selector for an element in a screenshot
        
        Args:
            screenshot_b64: Base64 encoded screenshot
            element_description: What to find (e.g., "bet placement button")
            
        Returns:
            CSS selector as string
        """
        prompt = f"""
Analyze this webpage screenshot and find the CSS selector for: {element_description}

Instructions:
1. Look at the visual layout
2. Identify the target element
3. Generate a robust CSS selector that would work
4. Consider: classes, IDs, text content, attributes
5. Respond with ONLY the CSS selector, nothing else

Examples of good selectors:
- button.bet-place
- .market-odds-button:has-text("Piazza")
- [data-testid="place-bet"]
- .btn-primary.submit-bet

Respond with just the selector string.
"""
        
        response = self.understand_image(screenshot_b64, prompt)
        
        if response:
            # Clean any markdown or extra text
            response = response.strip().strip('`').strip()
            if '\n' in response:
                response = response.split('\n')[0]
        
        return response
    
    def detect_layout_change(self, screenshot_old_b64: str, screenshot_new_b64: str) -> Optional[Dict]:
        """
        Detect if website layout has changed significantly
        
        Args:
            screenshot_old_b64: Old screenshot
            screenshot_new_b64: New screenshot
            
        Returns:
            Dict with changed: bool, description: str, affected_elements: list
        """
        prompt = """
Compare these two screenshots of the same website.

Determine:
1. Has the layout changed significantly? (yes/no)
2. What specific elements moved or changed?
3. Which UI components are affected?

Respond ONLY with valid JSON:
{
  "changed": true/false,
  "confidence": 0.0-1.0,
  "description": "brief description of changes",
  "affected_elements": ["element1", "element2"],
  "recommendations": ["suggestion1", "suggestion2"]
}
"""
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "text", "text": "OLD SCREENSHOT:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_old_b64}"}},
                    {"type": "text", "text": "NEW SCREENSHOT:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_new_b64}"}}
                ]
            }
        ]
        
        response = self._call_api(messages, temperature=0.2)
        
        if not response:
            return None
        
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            return json.loads(response)
        except json.JSONDecodeError:
            return None
    
    def learn_pattern(self, examples: List[str], description: str = "") -> Optional[Dict]:
        """
        Learn a pattern from multiple examples
        
        Args:
            examples: List of example texts
            description: What kind of pattern we're learning
            
        Returns:
            Pattern definition as dict
        """
        examples_text = "\n\n".join([f"Example {i+1}:\n{ex}" for i, ex in enumerate(examples)])
        
        prompt = f"""
Analyze these examples and extract the common pattern/structure.
{f'Context: {description}' if description else ''}

{examples_text}

Create a pattern definition that includes:
1. Structure/format
2. Required fields
3. Optional fields
4. Regex patterns for extraction
5. Validation rules

Respond ONLY with valid JSON defining the pattern.
"""
        
        messages = [{"role": "user", "content": prompt}]
        response = self._call_api(messages, temperature=0.3)
        
        if not response:
            return None
        
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            return json.loads(response)
        except json.JSONDecodeError:
            return None
