import os
from typing import List, Dict
from crewai import Agent
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from . import database
from .tools.lead_scoring_tools import (
    # Assuming these might be defined here or remove if not used
    # EnrichmentValidationTool, 
    # SignalValidationTool, 
    # ScoreValidationTool, 
    # DataQualityTool, 
    # WorkflowValidationTool,
    # LeadScoringSchema is likely a Pydantic model defined elsewhere (e.g., tasks or crew) 
    # and not needed for direct import by the agents class itself.
    # LeadScoringSchema, 
    ScoringValidationTool # This one is definitely used
)
from .tools.web_search_tools import SearchAndContentsTool # Combined search/scrape tool
from .tools.network_tool import DomainMatchTool # Our new domain tool

# Initialize only the tools we will assign to agents
# Note: We instantiate SearchAndContentsTool within the class using the API key
# scoring_validation_tool = ScoringValidationTool() # Instantiate if needed globally, or within class
domain_match_tool = DomainMatchTool() # Instantiate globally

class LeadScoringAgents:
    """Collection of agents for lead scoring"""

    def __init__(self, serper_api_key: str):
        # Initialize tools that require API keys or specific config here
        self.search_tool = SearchAndContentsTool(serper_api_key=serper_api_key)
        # Use globally instantiated tools or create instances here
        self.scoring_validation_tool = ScoringValidationTool()
        self.domain_match_tool = domain_match_tool # Use the global instance
        # Add the scrape tool
        self.scrape_tool = ScrapeWebsiteTool()

        # Instantiate other validation tools if the coordinator needs them directly
        # (Currently, validation happens via tasks and delegated agents using their specific tools)
        # self.enrichment_validator = EnrichmentValidationTool()
        # self.signal_validator = SignalValidationTool()

    def lead_analysis_coordinator(self) -> Agent:
        """Agent responsible for orchestrating the workflow and quality control."""
        return Agent(
            name="Lead Analysis Coordinator",
            role="Lead Qualification Workflow Manager and Quality Assurance Expert",
            goal=(
                "Orchestrate the lead qualification process by assigning tasks to specialized agents, "
                "manage the flow of information, validate the outputs of each step for accuracy, relevance, and completeness, "
                "ensure the final output is a consolidated, validated JSON object, and "
                "use the Domain Match Tool to check for potential network connections based on email domains early in the process."
            ),
            backstory=(
                "As the central hub of the lead qualification team, you are meticulous and process-oriented. "
                "You ensure that each agent performs their task effectively and that the quality of data is maintained throughout the workflow. "
                "You have access to validation tools and the domain matching tool to guide the process."
            ),
            # Assign tools needed for coordination and direct actions
            tools=[self.scoring_validation_tool, self.domain_match_tool],
            allow_delegation=True, # Crucial for assigning tasks
            verbose=True,
            # memory=True # Consider if state needs to be maintained across multiple leads in one run
        )

    def lead_enrichment_specialist(self) -> Agent:
        """Agent focused on enriching lead data using web search and targeted scraping."""
        return Agent(
            name="Lead Data Enricher",
            role="Company and Industry Information Specialist",
            goal="""Receive lead details and focus *exclusively* on enriching:
                - Company Industry Classification
                - Contact's Position/Job Title
                - Estimated Company Size
                - Target Customer Profile (SMB, Mid-Market, Enterprise)
                - Recent Industry Challenges (based on the company's industry)
                - Future Industry Projections (based on the company's industry)
                Prioritize scraping the lead's website directly if available, falling back to general web search only if scraping fails or website is unknown.""",
            backstory="""You are an expert researcher specializing in finding specific pieces 
            of company and industry data. You follow instructions precisely to gather only the 
            requested information. You attempt to scrape the primary company website first 
            for the most accurate data, using general web search as a backup.""",
            # Give the agent both tools
            tools=[self.scrape_tool, self.search_tool],
            allow_delegation=False, # This agent executes a specific task
            verbose=True
        )

    def signal_identification_specialist(self) -> Agent:
        """Agent focused on identifying buying signals using web search.

           Also uses SearchAndContentsTool.
        """
        return Agent(
            name="Specific Signal Detector",
            role="Funding, Hiring, and Layoff Signal Specialist",
            goal="""Receive company information and focus *exclusively* on detecting signals related to:
                - Funding Rounds (new investments, amounts)
                - Hiring Sprees (significant increase in job postings, specific roles)
                - Layoffs (significant workforce reductions, restructuring news)
                Use reliable sources like TechCrunch, Crunchbase, reputable financial news sites, and company press releases.""",
            backstory="""You are a specialist in tracking key company growth and change indicators. 
            Your expertise lies in scanning targeted news and financial data sources to identify 
            concrete evidence of funding, hiring surges, or layoffs. You report only these specific signal types.""",
            tools=[self.search_tool],
            allow_delegation=False,
            verbose=True
        )

    def lead_score_calculation_specialist(self) -> Agent:
        """Agent focused on calculating the lead score based on provided data.

           Uses ScoringValidationTool to ensure output format.
           Receives domain match results via context.
        """
        return Agent(
            name="Lead Scoring Analyst",
            role="Lead Score Calculation Specialist",
            goal="""Receive validated lead data (ICP details, engagement info, signals, connection degree) 
                and calculate a lead score *strictly* based on the provided weighting:
                - 50% ICP Match
                - 15% Engagement History
                - 15% Signal Match (Validated Signals: funding, hiring, layoffs)
                - 20% Connection Level
                Provide a clear breakdown of how each component contributes to the final score.""",
            backstory="""You are an analyst focused solely on applying a predefined scoring rubric. 
            Given validated data points and specific weights (50% ICP, 15% Engagement, 15% Signals, 20% Connection), 
            you meticulously calculate the score for each category and the final weighted score. 
            You do not perform validation yourself but rely on the input data being accurate.""",
            tools=[self.scoring_validation_tool],
            allow_delegation=False,
            verbose=True
        )

    def get_agent_chain(self) -> List[Agent]:
        """Get the chain of agents - Coordinator might be the primary one in hierarchical flow"""
        return [
            self.lead_analysis_coordinator(),
            self.lead_enrichment_specialist(),
            self.signal_identification_specialist(),
            self.lead_score_calculation_specialist()
        ] 