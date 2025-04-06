import unittest
from datetime import datetime, timedelta
from tools.signal_validation_filter import SignalValidationFilter

class TestSignalValidation(unittest.TestCase):
    def setUp(self):
        self.validator = SignalValidationFilter()
        
    def test_filter_signals_with_vague_language(self):
        signals = [{
            'description': 'Company might be expanding',
            'source_url': 'http://example.com',
            'details': {'snippet': 'Some details'}
        }]
        filtered = self.validator.filter_signals(signals)
        self.assertEqual(len(filtered), 0, "Should filter out signals with vague language")
        
    def test_filter_signals_without_source_url(self):
        signals = [{
            'description': 'Company is expanding',
            'source_url': None,
            'details': {'snippet': 'Some details'}
        }]
        filtered = self.validator.filter_signals(signals)
        self.assertEqual(len(filtered), 0, "Should filter out signals without source URL")
        
    def test_valid_company_growth_signal(self):
        signal = {
            'signal_type': 'company_growth',
            'description': 'Company is expanding operations',
            'source_url': 'http://example.com',
            'details': {
                'full_snippet': 'Company announced 50 new positions in their Berlin office'
            }
        }
        self.assertTrue(
            self.validator._is_valid_signal(signal),
            "Should accept valid growth signal with specific metrics"
        )
        
    def test_valid_funding_signal(self):
        signal = {
            'signal_type': 'funding_news',
            'description': 'Company raises new funding',
            'source_url': 'http://example.com',
            'details': {
                'title': 'Company raises $5M',
                'snippet': 'Series A funding of $5 million'
            }
        }
        self.assertTrue(
            self.validator._is_valid_signal(signal),
            "Should accept valid funding signal with specific amount"
        )
        
    def test_confidence_scoring(self):
        signal = {
            'description': 'Company expands operations',
            'source_url': 'http://example.com',
            'details': {
                'snippet': 'Company hired 100 employees',
                'detected_keywords': ['hiring', 'growth', 'expansion'],
                'timestamp': datetime.now().isoformat()
            }
        }
        confidence = self.validator.get_signal_confidence(signal)
        self.assertGreater(confidence, 0.5, "High-quality signal should have high confidence")
        
    def test_filter_generic_growth_claims(self):
        signal = {
            'signal_type': 'company_growth',
            'description': 'Company is growing',
            'source_url': 'http://example.com',
            'details': {
                'full_snippet': 'The company is showing strong growth potential'
            }
        }
        self.assertFalse(
            self.validator._is_valid_signal(signal),
            "Should reject growth claims without specific metrics"
        )
        
    def test_filter_unverified_funding_claims(self):
        signal = {
            'signal_type': 'funding_news',
            'description': 'Company seeking funding',
            'source_url': 'http://example.com',
            'details': {
                'title': 'Company looking to raise capital',
                'snippet': 'The company is in talks with investors'
            }
        }
        self.assertFalse(
            self.validator._is_valid_signal(signal),
            "Should reject funding claims without specific amounts"
        )

if __name__ == '__main__':
    unittest.main() 