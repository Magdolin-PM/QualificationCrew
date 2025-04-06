import unittest
from datetime import datetime, timezone, timedelta
from tools.lead_scoring_tools import (
    EnrichmentValidationTool,
    SignalValidationTool,
    ScoringValidationTool,
    DataQualityTool,
    WorkflowValidationTool
)

class TestLeadScoringTools(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.enrichment_validator = EnrichmentValidationTool()
        self.signal_validator = SignalValidationTool()
        self.scoring_validator = ScoringValidationTool()
        self.data_quality_tool = DataQualityTool()
        self.workflow_validator = WorkflowValidationTool()

    def test_enrichment_validation(self):
        """Test enrichment validation tool"""
        # Test complete data
        complete_data = {
            "company_description": "A tech company",
            "industry": "Software",
            "company_challenges": ["Growth", "Competition"],
            "recent_developments": ["New Product Launch"],
            "growth_indicators": ["Market Expansion"],
            "last_enrichment": datetime.now(timezone.utc).isoformat(),
            "data_sources": {
                "company_website": {
                    "url": "https://example.com",
                    "last_updated": "2024-03-01",
                    "content": "Valid content"
                },
                "linkedin": {
                    "url": "https://linkedin.com/company/example",
                    "last_updated": "2024-03-01",
                    "profile_data": "Complete profile"
                }
            }
        }
        
        result = self.enrichment_validator._run(complete_data)
        self.assertTrue(result["is_valid"])
        self.assertGreater(result["confidence_score"], 80)
        
        # Test incomplete data
        incomplete_data = {
            "company_description": "A tech company",
            "industry": "Software"
        }
        
        result = self.enrichment_validator._run(incomplete_data)
        self.assertFalse(result["is_valid"])
        self.assertLess(result["confidence_score"], 50)

    def test_signal_validation(self):
        """Test signal validation tool"""
        # Test valid signals
        valid_signals = {
            "detected_signals": [
                {
                    "type": "growth_signal",
                    "description": "Company is expanding rapidly",
                    "details": {
                        "evidence": "Multiple job postings for senior roles, new office locations announced, and recent press releases about market expansion",
                        "impact": "High growth potential indicating strong market position and buying power"
                    },
                    "source": "linkedin",
                    "source_url": "https://linkedin.com/company/example",
                    "verification_sources": [
                        "https://example.com/press/expansion",
                        "https://news.example.com/growth"
                    ]
                }
            ]
        }
        
        result = self.signal_validator._run(valid_signals)
        self.assertTrue(result["is_valid"])
        self.assertGreater(result["overall_confidence"], 0.7)
        self.assertEqual(len(result["invalid_signals"]), 0)
        
        # Test invalid signals
        invalid_signals = {
            "detected_signals": [
                {
                    "type": "growth_signal",
                    "description": "Company is expanding"
                    # Missing details and source
                }
            ]
        }
        
        result = self.signal_validator._run(invalid_signals)
        self.assertFalse(result["is_valid"])

    def test_scoring_validation(self):
        """Test scoring validation tool"""
        # Test valid scoring
        valid_scoring = {
            "scoring": {
                "icp_match_score": 85,
                "signal_match_score": 70,
                "engagement_score": 60,
                "connection_score": 75
            },
            "scoring_details": {
                "ai_confidence": 0.85,
                "highest_impact_matches": ["Industry match", "Size match"],
                "confidence_reasoning": "Strong evidence from multiple sources"
            }
        }
        
        result = self.scoring_validator._run(valid_scoring)
        self.assertTrue(result["is_valid"])
        self.assertGreater(result["confidence_score"], 80)
        
        # Test invalid scoring
        invalid_scoring = {
            "scoring": {
                "icp_match_score": 85
                # Missing required components
            }
        }
        
        result = self.scoring_validator._run(invalid_scoring)
        self.assertFalse(result["is_valid"])

    def test_data_quality(self):
        """Test data quality tool"""
        # Test high quality data
        good_data = {
            "company": "Example Corp",
            "industry": "Software",
            "company_size": "100-500",
            "region": "North America",
            "website": "https://example.com",
            "linkedin": "https://linkedin.com/company/example",
            "enrichment_data": {
                "industry": "Software",
                "description": "Leading software company"
            },
            "scoring": {"total": 85},
            "scoring_details": {"confidence": 0.9}
        }
        
        result = self.data_quality_tool._run(good_data)
        self.assertGreater(result["overall_quality"], 80)
        
        # Test low quality data with inconsistencies and missing fields
        poor_data = {
            "enrichment_data": {
                "industry": "Technology",
                "description": "Tech company"
            }
        }
        
        result = self.data_quality_tool._run(poor_data)
        # Check individual scores
        self.assertLess(result["completeness_score"], 20, "Data missing most required fields")
        self.assertEqual(result["consistency_score"], 60, "Should have consistency deduction for industry mismatch")
        self.assertLess(result["accuracy_score"], 40, "Missing verification sources")
        # Check overall quality
        self.assertLess(result["overall_quality"], 50, "Overall quality should be poor")

    def test_workflow_validation(self):
        """Test workflow validation tool"""
        # Test complete workflow
        complete_workflow = {
            "enrichment_stage": {
                "company_description": "Tech company",
                "industry": "Software",
                "company_challenges": ["Growth"],
                "recent_developments": ["Expansion"],
                "growth_indicators": ["Hiring"],
                "last_enrichment": datetime.now(timezone.utc).isoformat(),
                "data_sources": {
                    "company_website": {"url": "https://example.com"}
                }
            },
            "signals_stage": {
                "detected_signals": [
                    {
                        "type": "challenge_signal",
                        "description": "Growth challenges",
                        "details": {
                            "evidence": "Detailed evidence",
                            "impact": "High"
                        },
                        "source": "website"
                    }
                ]
            },
            "scoring_stage": {
                "scoring": {
                    "icp_match_score": 85,
                    "signal_match_score": 70,
                    "engagement_score": 60,
                    "connection_score": 75
                },
                "scoring_details": {
                    "ai_confidence": 0.85,
                    "highest_impact_matches": ["Industry match"],
                    "confidence_reasoning": "Strong evidence"
                }
            }
        }
        
        result = self.workflow_validator._run(complete_workflow)
        self.assertTrue(result["workflow_valid"])
        self.assertGreater(result["overall_confidence"], 70)
        
        # Test incomplete workflow
        incomplete_workflow = {
            "enrichment_stage": {
                "company_description": "Tech company"
            }
            # Missing signals and scoring stages
        }
        
        result = self.workflow_validator._run(incomplete_workflow)
        self.assertFalse(result["workflow_valid"])
        self.assertTrue(len(result["data_flow_issues"]) > 0)

    def test_data_freshness(self):
        """Test data freshness validation"""
        old_data = {
            "company_description": "Tech company",
            "industry": "Software",
            "company_challenges": ["Growth"],
            "recent_developments": ["Expansion"],
            "growth_indicators": ["Hiring"],
            "last_enrichment": (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        }
        
        result = self.enrichment_validator._run(old_data)
        self.assertIn("days old", result["quality_issues"][0])
        self.assertLess(result["confidence_score"], 80)

if __name__ == '__main__':
    unittest.main() 