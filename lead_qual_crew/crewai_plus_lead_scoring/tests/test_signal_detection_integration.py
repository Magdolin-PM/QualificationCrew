import unittest
from unittest.mock import patch, MagicMock
from tools.signal_detection_tool import SignalDetectionTool
from datetime import datetime

class TestSignalDetectionIntegration(unittest.TestCase):
    def setUp(self):
        self.detector = SignalDetectionTool()
        
    @patch('requests.post')
    def test_signal_detection_with_validation(self, mock_post):
        # Mock Serper API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'organic': [
                {
                    'title': 'Test Company raises $10M Series A',
                    'snippet': 'Test Company announced a $10 million Series A funding round',
                    'link': 'http://techcrunch.com/article'
                },
                {
                    'title': 'Test Company might be expanding',
                    'snippet': 'Rumors suggest Test Company could be looking at expansion',
                    'link': 'http://techcrunch.com/article2'
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # Test signal detection with validation
        signals = self.detector._run('Test Company', ['techcrunch'])
        
        # Should only return the funding signal, not the speculative expansion
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]['signal_type'], 'funding_news')
        self.assertIn('$10M', signals[0]['description'])
        self.assertTrue('confidence' in signals[0]['details'])
        
    @patch('requests.post')
    def test_multiple_source_validation(self, mock_post):
        # Mock different responses for different sources
        def mock_serper_response(*args, **kwargs):
            if 'site:techcrunch.com' in kwargs['json']['q']:
                return MagicMock(json=lambda: {
                    'organic': [{
                        'title': 'Test Company raises $10M',
                        'snippet': 'Funding announcement',
                        'link': 'http://techcrunch.com/article'
                    }]
                })
            elif 'site:f6s.com' in kwargs['json']['q']:
                return MagicMock(json=lambda: {
                    'organic': [{
                        'title': 'Test Company Profile',
                        'snippet': 'Company is hiring 20 new positions',
                        'link': 'http://f6s.com/company'
                    }]
                })
            return MagicMock(json=lambda: {'organic': []})
            
        mock_post.side_effect = mock_serper_response
        
        # Test multiple sources
        signals = self.detector._run('Test Company', ['techcrunch', 'f6s'])
        
        # Should return both valid signals
        self.assertEqual(len(signals), 2)
        signal_types = {s['signal_type'] for s in signals}
        self.assertEqual(signal_types, {'funding_news', 'company_growth'})
        
    @patch('requests.post')
    def test_confidence_scoring_integration(self, mock_post):
        # Mock response with varying quality signals
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'organic': [
                {
                    'title': 'Test Company raises $10M Series A',
                    'snippet': 'Major funding announcement with specific details',
                    'link': 'http://techcrunch.com/article',
                    'date': datetime.now().isoformat()
                },
                {
                    'title': 'Test Company News',
                    'snippet': 'The company is doing well',
                    'link': 'http://techcrunch.com/article2'
                }
            ]
        }
        mock_post.return_value = mock_response
        
        signals = self.detector._run('Test Company', ['techcrunch'])
        
        # Should only return the high-confidence signal
        self.assertEqual(len(signals), 1)
        self.assertGreater(signals[0]['details']['confidence'], 0.5)

if __name__ == '__main__':
    unittest.main() 