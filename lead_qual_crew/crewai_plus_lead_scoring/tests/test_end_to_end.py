import unittest
import os
from tools.signal_detection_tool import SignalDetectionTool
from tools.signal_validation_filter import SignalValidationFilter
from datetime import datetime, timezone

class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.user_id = "73fb447f-61cc-4ae5-bc4c-5f3a1317c2fb"
        self.lead_id = "00a31a99-8d00-40ef-a80a-49719342a091"
        self.detector = SignalDetectionTool()
        
        # Ensure SERPER_API_KEY is set
        if not os.getenv("SERPER_API_KEY"):
            self.skipTest("SERPER_API_KEY environment variable is required for this test")
    
    def test_lead_signal_detection(self):
        """
        End-to-end test of signal detection and validation for a specific lead
        """
        # Test company name - replace with actual company name for the lead
        company = "Test Company"  # You should replace this with actual company name
        
        # Test all available sources
        sources = ['xing', 'techcrunch', 'f6s', 'google_trends', 'startbase']
        
        # Run signal detection
        signals = self.detector._run(company, sources)
        
        # Validate results
        self.assertIsNotNone(signals, "Should return signals list")
        
        # Check that all returned signals have required fields
        for signal in signals:
            self.assertIn('signal_type', signal)
            self.assertIn('description', signal)
            self.assertIn('source', signal)
            self.assertIn('details', signal)
            self.assertIn('confidence', signal['details'])
            
            # Verify no vague language
            validator = SignalValidationFilter()
            self.assertTrue(
                validator._is_valid_signal(signal),
                f"Signal failed validation: {signal}"
            )
            
            # Check confidence score
            self.assertGreater(
                signal['details']['confidence'],
                0.5,
                f"Signal has low confidence: {signal}"
            )
            
    def test_signal_deduplication(self):
        """
        Test that signals are properly deduplicated across sources
        """
        company = "Test Company"  # Replace with actual company name
        
        # Test sources that might have overlapping information
        sources = ['techcrunch', 'google_trends']
        
        signals = self.detector._run(company, sources)
        
        # Check for duplicate descriptions
        descriptions = [s['description'] for s in signals]
        self.assertEqual(
            len(descriptions),
            len(set(descriptions)),
            "Found duplicate signals"
        )
        
    def test_signal_timestamp_validation(self):
        """
        Test that signals are recent and properly timestamped
        """
        company = "Test Company"  # Replace with actual company name
        signals = self.detector._run(company, ['techcrunch'])
        
        for signal in signals:
            if 'timestamp' in signal['details']:
                # Verify timestamp is recent (within last 6 months)
                timestamp = datetime.fromisoformat(
                    signal['details']['timestamp'].replace('Z', '+00:00')
                )
                age = (datetime.now(timezone.utc) - timestamp).days
                self.assertLess(age, 180, f"Signal is too old: {age} days")

if __name__ == '__main__':
    unittest.main() 