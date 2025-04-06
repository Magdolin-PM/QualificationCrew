from typing import Dict, List
import re
from datetime import datetime, timedelta

# Enhanced regex for vague phrases
VAGUE_PHRASES_REGEX = re.compile(
    r"\b(may be|might be|could be|seems to|appears to|potentially|possibly|rumored|unconfirmed|suggests|likely|expected to)\b", 
    re.IGNORECASE
)
# Regex for specific numbers/metrics often indicating concrete info
SPECIFIC_METRIC_REGEX = re.compile(r"\b(\d+%|\$\d+(?:\.\d+)?[mkb]?|\d+\s+(?:employees?|positions?|offices?|users?|customers?))\b", re.IGNORECASE)

class SignalValidationFilter:
    """
    Validates detected signals to filter out potential hallucinations or low-quality info.
    Focuses on source verifiability, language certainty, and content specificity.
    """
    
    # High-credibility sources (less likely to need strict validation)
    HIGH_CREDIBILITY_SOURCES = {'techcrunch', 'crunchbase', 'sec_filing'} 
    # Sources requiring stricter validation
    LOWER_CREDIBILITY_SOURCES = {'f6s', 'startbase', 'xing', 'wellfound', 'builtin', 'semrush'}

    def filter_signals(self, signals: List[Dict]) -> List[Dict]:
        """
        Filters a list of signals, returning only those deemed valid.
        """
        validated_signals = []
        for signal in signals:
            is_valid, reason = self._is_valid_signal(signal)
            if is_valid:
                signal['validation_status'] = 'passed'
                validated_signals.append(signal)
            else:
                print(f"DEBUG Validation Filter: Signal REJECTED. Reason: {reason}. Signal: {signal.get('description','N/A')[:100]}...")
                # Optionally store rejected signals elsewhere or just discard
        return validated_signals

    def _is_valid_signal(self, signal: Dict) -> tuple[bool, str]:
        """
        Performs validation checks on a single signal.
        Returns (True, "Passed") if valid, or (False, "Reason for rejection") if invalid.
        """
        description = signal.get('description', '')
        details = signal.get('details', {})
        source = signal.get('source', '').lower()
        source_url = signal.get('source_url')
        full_snippet = details.get('full_snippet', '')
        title = details.get('title', '')
        combined_text = f"{title} {description} {full_snippet}".lower()

        # --- Basic Checks --- 
        if not description or not source:
            return False, "Missing description or source"
        
        # --- Source-Specific Checks & Verifiability --- 
        # Require a source URL for most sources to allow verification
        if source in self.LOWER_CREDIBILITY_SOURCES and not source_url:
             return False, f"Missing source_url for lower credibility source: {source}"
             
        # --- Language Certainty Check --- 
        # Apply stricter language checks for lower credibility sources or if no specific metrics found
        has_specific_metric = SPECIFIC_METRIC_REGEX.search(combined_text)
        needs_strict_language_check = (source in self.LOWER_CREDIBILITY_SOURCES or not has_specific_metric)
        
        if needs_strict_language_check:
            if VAGUE_PHRASES_REGEX.search(combined_text):
                 return False, f"Vague/uncertain language detected ('{VAGUE_PHRASES_REGEX.search(combined_text).group(0)}') in text without strong metrics/source."

        # --- Content Specificity Checks --- 
        # Require minimum length for description/snippet unless it's a highly credible source
        min_content_length = 30
        if source not in self.HIGH_CREDIBILITY_SOURCES and len(combined_text.strip()) < min_content_length:
             return False, f"Content too short (< {min_content_length} chars) for validation from source: {source}"
             
        # Check for missing essential details based on signal type (example)
        signal_type = signal.get('signal_type')
        if signal_type == 'funding_round' and source not in self.HIGH_CREDIBILITY_SOURCES:
             # Look for mention of currency symbol or funding stage keywords
             if not re.search(r'\$|€|£|\b(seed|series [a-z]|round|investment|raised)\b', combined_text, re.IGNORECASE):
                 return False, "Funding signal lacks currency symbol or typical funding keywords."
                 
        if signal_type == 'hiring_activity' and source not in self.HIGH_CREDIBILITY_SOURCES:
             if not re.search(r'\b(hiring|jobs?|careers?|\d+ positions?)\b', combined_text, re.IGNORECASE):
                 return False, "Hiring signal lacks specific hiring keywords or numbers."

        # --- Optional: Timestamp Check (Placeholder) --- 
        # detected_at_str = signal.get('detected_at')
        # if detected_at_str:
        #     try: 
        #         # Parse and check if too old, e.g., > 1 year
        #         pass 
        #     except: pass # Ignore parse errors for validation
             
        # If all checks pass
        return True, "Passed"

    def get_signal_confidence(self, signal: Dict) -> float:
        """
        Calculate a confidence score for a signal based on various factors.
        Returns a score between 0 and 1.
        """
        score = 0.0
        
        # Base confidence from having verifiable source
        if signal.get('source_url'):
            score += 0.3
            
        # Additional confidence from specific details
        details = signal.get('details', {})
        if details:
            # Specific numbers or metrics
            text = f"{signal.get('description', '')} {details.get('snippet', '')}".lower()
            if re.search(r'\b\d+%|\$\d+[mk]?\b|\b\d+\s+(?:employees|positions|offices)\b', text):
                score += 0.2
                
            # Multiple keywords in context
            keywords = details.get('detected_keywords', [])
            if len(keywords) >= 3:
                score += 0.2
                
            # Recent timestamp if available
            if details.get('timestamp'):
                try:
                    timestamp = datetime.fromisoformat(details['timestamp'].replace('Z', '+00:00'))
                    if datetime.now() - timestamp <= timedelta(days=30):
                        score += 0.3
                except (ValueError, TypeError):
                    pass
        
        return min(score, 1.0)  # Cap at 1.0 