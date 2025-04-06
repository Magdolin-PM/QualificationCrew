import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from tools.signal_detection_tool import SignalDetectionTool
from tools.lead_scoring_tools import SignalValidationTool

class TestSignalDetection(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.signal_detector = SignalDetectionTool()
        self.signal_validator = SignalValidationTool()
        
    def test_signal_source_verification(self):
        """Test that all signals have verifiable sources"""
        test_signals = self.signal_detector._run(
            company="Test Company",
            sources=['xing', 'techcrunch', 'google_trends', 'startbase']
        )
        
        for signal in test_signals:
            # Every signal must have a source
            self.assertIn('source', signal, "Signal missing source attribution")
            self.assertIsNotNone(signal['source'], "Signal has None source")
            self.assertNotEqual(signal['source'], "", "Signal has empty source")
            
            # Every signal should have either a source_url or detailed evidence
            has_url = 'source_url' in signal and signal['source_url']
            has_evidence = ('details' in signal and 
                          'evidence' in signal['details'] and 
                          signal['details']['evidence'])
            
            self.assertTrue(has_url or has_evidence, 
                          f"Signal lacks both URL and evidence: {signal}")

    def test_signal_content_validation(self):
        """Test that signal content is specific and not generic"""
        test_signals = self.signal_detector._run(
            company="Test Company",
            sources=['xing', 'techcrunch', 'google_trends', 'startbase']
        )
        
        for signal in test_signals:
            # Description should be specific
            self.assertIn(signal['description'].lower(), 
                         signal['details']['evidence'].lower(),
                         "Signal description not supported by evidence")
            
            # Check for generic phrases that might indicate hallucination
            generic_phrases = [
                "showing growth",
                "expanding rapidly",
                "potential opportunity",
                "might be interested",
                "could be looking for",
                "seems to be"
            ]
            
            for phrase in generic_phrases:
                self.assertNotIn(
                    phrase.lower(), 
                    signal['description'].lower(),
                    f"Signal contains generic phrase: {phrase}"
                )

    def test_signal_timestamp_validation(self):
        """Test that signals have recent timestamps and are not future-dated"""
        test_signals = self.signal_detector._run(
            company="Test Company",
            sources=['xing', 'techcrunch', 'google_trends', 'startbase']
        )
        
        now = datetime.now(timezone.utc)
        
        for signal in test_signals:
            if 'timestamp' in signal:
                signal_time = datetime.fromisoformat(signal['timestamp'].replace('Z', '+00:00'))
                
                # Signal should not be from the future
                self.assertLess(signal_time, now, 
                              f"Signal has future timestamp: {signal['timestamp']}")
                
                # Signal should not be too old (e.g., more than 6 months)
                age = (now - signal_time).days
                self.assertLess(age, 180, 
                              f"Signal is too old: {age} days")

    def test_signal_deduplication(self):
        """Test that duplicate signals are properly handled"""
        test_signals = self.signal_detector._run(
            company="Test Company",
            sources=['xing', 'techcrunch', 'google_trends', 'startbase']
        )
        
        # Check for duplicate descriptions
        descriptions = [s['description'] for s in test_signals]
        self.assertEqual(
            len(descriptions),
            len(set(descriptions)),
            "Duplicate signal descriptions found"
        )
        
        # Check for similar evidence from different sources
        evidences = [s['details']['evidence'] for s in test_signals]
        for i, ev1 in enumerate(evidences):
            for j, ev2 in enumerate(evidences):
                if i != j:
                    # If evidence is similar, sources should be different
                    if self._similarity_score(ev1, ev2) > 0.8:
                        self.assertNotEqual(
                            test_signals[i]['source'],
                            test_signals[j]['source'],
                            "Similar evidence from same source"
                        )

    def test_signal_confidence_scoring(self):
        """Test that signal confidence scores are properly justified"""
        test_signals = self.signal_detector._run(
            company="Test Company",
            sources=['xing', 'techcrunch', 'google_trends', 'startbase']
        )
        
        for signal in test_signals:
            confidence = signal['details'].get('confidence', 0)
            
            # Higher confidence should require more evidence
            if confidence > 80:
                self.assertTrue('source_url' in signal and signal['source_url'],
                              "High confidence signal missing source URL")
                self.assertGreater(len(signal['details']['evidence']), 100,
                                 "High confidence signal has insufficient evidence")
            
            # Very high confidence should require multiple sources
            if confidence > 90:
                self.assertTrue(
                    isinstance(signal.get('verification_sources', []), list) and
                    len(signal.get('verification_sources', [])) >= 2,
                    "Very high confidence signal lacks multiple verification sources"
                )

    def _similarity_score(self, text1: str, text2: str) -> float:
        """Simple similarity score between two texts"""
        # This is a basic implementation - in practice, you might want to use
        # more sophisticated text similarity measures
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)

if __name__ == '__main__':
    unittest.main() 