import unittest
from unittest.mock import MagicMock, patch
from agents import LeadScoringAgents

class TestLeadScoringAgents(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.serper_api_key = "test_key"
        self.agents = LeadScoringAgents(self.serper_api_key)

    def test_agent_initialization(self):
        """Test that all agents are properly initialized with correct tools"""
        # Test Lead Analyzer
        analyzer = self.agents.lead_analyzer_agent()
        self.assertEqual(analyzer.role, "Lead Analysis and Quality Control Expert")
        self.assertEqual(len(analyzer.tools), 7)  # Should have all validation tools + serper + scrape
        
        # Test Enricher
        enricher = self.agents.enricher_agent()
        self.assertEqual(enricher.role, "Lead Data Research and Enrichment Specialist")
        self.assertEqual(len(enricher.tools), 3)  # Should have serper + scrape + data quality
        
        # Test Signal Detector
        detector = self.agents.signal_detector_agent()
        self.assertEqual(detector.role, "Lead Signal and Intent Detection Expert")
        self.assertEqual(len(detector.tools), 3)  # Should have serper + scrape + signal validator
        
        # Test Lead Scorer
        scorer = self.agents.lead_scorer_agent()
        self.assertEqual(scorer.role, "Lead Scoring and Qualification Expert")
        self.assertEqual(len(scorer.tools), 2)  # Should have scoring validator + data quality

    def test_agent_chain(self):
        """Test that the agent chain is in correct order"""
        chain = self.agents.get_agent_chain()
        self.assertEqual(len(chain), 4)
        
        # Verify correct order by roles
        self.assertEqual(chain[0].role, "Lead Analysis and Quality Control Expert")
        self.assertEqual(chain[1].role, "Lead Data Research and Enrichment Specialist")
        self.assertEqual(chain[2].role, "Lead Signal and Intent Detection Expert")
        self.assertEqual(chain[3].role, "Lead Scoring and Qualification Expert")

    @patch('crewai.Agent')
    def test_lead_analyzer_delegation(self, mock_agent):
        """Test that Lead Analyzer can delegate to other agents"""
        analyzer = self.agents.lead_analyzer_agent()
        self.assertTrue(analyzer.allow_delegation)
        
        # Other agents should not have delegation enabled
        enricher = self.agents.enricher_agent()
        detector = self.agents.signal_detector_agent()
        scorer = self.agents.lead_scorer_agent()
        
        self.assertFalse(getattr(enricher, 'allow_delegation', False))
        self.assertFalse(getattr(detector, 'allow_delegation', False))
        self.assertFalse(getattr(scorer, 'allow_delegation', False))

    def test_tool_assignment(self):
        """Test that each agent has the correct tools assigned"""
        analyzer = self.agents.lead_analyzer_agent()
        enricher = self.agents.enricher_agent()
        detector = self.agents.signal_detector_agent()
        scorer = self.agents.lead_scorer_agent()
        
        # Check Lead Analyzer tools
        analyzer_tool_names = [tool.name for tool in analyzer.tools]
        self.assertIn("validate_workflow", analyzer_tool_names)
        self.assertIn("validate_enrichment", analyzer_tool_names)
        self.assertIn("validate_signals", analyzer_tool_names)
        self.assertIn("validate_scoring", analyzer_tool_names)
        self.assertIn("check_data_quality", analyzer_tool_names)
        
        # Check Enricher tools
        enricher_tool_names = [tool.name for tool in enricher.tools]
        self.assertIn("check_data_quality", enricher_tool_names)
        
        # Check Signal Detector tools
        detector_tool_names = [tool.name for tool in detector.tools]
        self.assertIn("validate_signals", detector_tool_names)
        
        # Check Lead Scorer tools
        scorer_tool_names = [tool.name for tool in scorer.tools]
        self.assertIn("validate_scoring", scorer_tool_names)
        self.assertIn("check_data_quality", scorer_tool_names)

    def test_agent_roles_and_goals(self):
        """Test that agents have appropriate roles and goals"""
        analyzer = self.agents.lead_analyzer_agent()
        self.assertIn("quality", analyzer.goal.lower())
        self.assertIn("coordinate", analyzer.goal.lower())
        
        enricher = self.agents.enricher_agent()
        self.assertIn("research", enricher.goal.lower())
        self.assertIn("enrich", enricher.goal.lower())
        
        detector = self.agents.signal_detector_agent()
        self.assertIn("signals", detector.goal.lower())
        self.assertIn("opportunities", detector.goal.lower())
        
        scorer = self.agents.lead_scorer_agent()
        self.assertIn("score", scorer.goal.lower())
        self.assertIn("criteria", scorer.goal.lower())

if __name__ == '__main__':
    unittest.main() 