import os
from typing import List, Dict
from crewai import Agent
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from .tools.web_search_tools import SearchAndContentsTool # Combined search/scrape tool

# Initialize only the tools we will assign to agents
# Note: We instantiate SearchAndContentsTool within the class using the API key
# scoring_validation_tool = ScoringValidationTool() # Instantiate if needed globally, or within class

class LeadScoringAgents:
    """Collection of agents for lead scoring"""

    def __init__(self, serper_api_key: str):
        # Initialize only the tools required by the remaining agents
        self.search_tool = SearchAndContentsTool(serper_api_key=serper_api_key)
        self.scrape_tool = ScrapeWebsiteTool(serper_api_key=serper_api_key)
        # Remove unused tool initialization
        # self.scoring_validation_tool = ScoringValidationTool()
        # self.domain_match_tool = DomainMatchTool() # Example if it was instantiated here

    def lead_enrichment_specialist(self) -> Agent:
        """Agent focused on enriching lead data using web scraping for SEO/Metadata."""
        return Agent(
            name="Lead Data Enricher",
            role="Website Metadata and SEO Specialist",
            goal="Receive lead details (especially website URL) and focus *exclusively* on scraping the website to extract metadata (title, description) and SEO keywords.",
            backstory="You are an expert web scraper specializing in extracting specific HTML meta tags and title. You follow instructions precisely to gather only the requested information.",
            # Assign only the scrape tool
            tools=[self.scrape_tool],
            allow_delegation=False, 
            verbose=True
        )

    def negative_signal_detector(self) -> Agent:
        """Agent focused on identifying buying signals using web search.

           Also uses SearchAndContentsTool.
        """
        return Agent(
            name="Negative Signal Detector",
            role="Negative Signal Specialist",
            goal="Receive company information and focus *exclusively* on detecting negative signals by searching targeted sources (Glassdoor, Kununu, TechCrunch, etc.) for layoffs, funding issues, negative feedback.",
            backstory="You are a specialist in tracking key company pains, needs and change indicators. Your expertise lies in scanning targeted news and financial data sources to identify concrete evidence of funding, layoffs, and negative customer feedback. You report only these specific signal types. You utilize targeted search queries on specific news and review sites.",
            tools=[self.search_tool],
            allow_delegation=False,
            verbose=True
        )

    def positive_signal_detector(self) -> Agent:
        """Agent focused on identifying positive signals using web search.

           Also uses SearchAndContentsTool.
        """
        return Agent(
            name="Positive Signal Detector",
            role="Positive Signal Specialist",
            goal="Receive company information and focus *exclusively* on detecting positive signals by searching targeted sources (TechCrunch, Crunchbase, etc.) for funding, hiring sprees, successful launches.",
            backstory="You are a specialist in tracking key company growth, opportunities and change indicators. Your expertise lies in scanning targeted news and financial data sources to identify concrete evidence of funding, layoffs, and negative customer feedback. You report only these specific signal types. You utilize targeted search queries on specific news and business databases.",
            tools=[self.search_tool],
            allow_delegation=False,
            verbose=True
        )

    def signal_validation_expert(self) -> Agent:
        """Agent responsible for validating detected signals and assessing confidence."""
        return Agent(
            name="Signal Validation Expert",
            role="Signal Accuracy and Relevance Analyst",
            goal=(
                "Receive lists of detected positive and negative signals from context. "
                "Review each signal for plausibility, relevance, and potential duplication based on its description, source, and details. "
                "Filter out any signals deemed inaccurate, irrelevant, or redundant. "
                "Assess the overall confidence (0.0-1.0) in the quality and reliability of the *remaining* signals. "
                "Output the validated lists of positive and negative signals, along with the confidence score, conforming to the ValidationTaskOutput model."
            ),
            backstory=(
                "You are a meticulous analyst with a keen eye for detail and a strong understanding of business signals. "
                "Your role is crucial in ensuring that only high-quality, verified signals influence the lead scoring process. "
                "You critically evaluate the inputs from the signal detection agents and provide a confidence score reflecting your assessment."
            ),
            tools=[], # This agent likely performs analysis based on context, may not need tools
            allow_delegation=False, # Performs its own analysis
            verbose=True
        )

    # --- REMOVED lead_score_calculation_specialist --- 

    # --- REMOVED get_agent_chain --- 