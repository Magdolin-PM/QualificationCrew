from typing import Dict, List
from crewai import Task, Agent
# Remove unused database import if tasks no longer interact directly
# from . import database 
from .agents import LeadScoringAgents
from textwrap import dedent
# REMOVE: from .tools.network_tool import DomainMatchTool

# --- Pydantic Models for Task Outputs ---
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime

# Pydantic model for a single detected signal
class PositiveSignalOutput(BaseModel):
    signal_type: str = Field(..., description="Type: funding, hiring, expansion, partnership, etc.")
    description: str = Field(..., description="A concise description of the signal.")
    details: Dict[str, Any] = Field(default={}, description="Supporting details or evidence for the signal, as a JSON object.")
    source: str = Field(..., description="The source where the signal was detected (e.g., 'website', 'news_article', 'series_funding', 'cxo_hiring', 'job_posting').")
    source_url: Optional[HttpUrl | str] = Field(default=None, description="The URL of the source, if available.") # Allow string for flexibility if URL is not standard
    detected_at: Optional[datetime | str] = Field(default=None, description="Timestamp when the signal was detected (ISO 8601 format preferred).") # Allow string for flexibility
    confidence: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="Confidence in signal accuracy based on source and content")

# Pydantic model for the output of signal detection tasks
class PositiveSignalDetectionOutput(BaseModel):
    detected_signals: List[PositiveSignalOutput] = Field(default=[], description="A list of detected positive signals.")

class NegativeSignalOutput(BaseModel):
    signal_type: str = Field(..., description="Type: layoffs, negative_reviews, financial_trouble, etc.")
    description: str = Field(..., description="A concise description of the signal.")
    details: Dict[str, Any] = Field(default={}, description="Supporting details or evidence for the signal, as a JSON object.")
    source: str = Field(..., description="The source where the signal was detected (e.g., 'website', 'news_article', 'job_posting', 'delisting_notice').")
    source_url: Optional[HttpUrl | str] = Field(default=None, description="The URL of the source, if available.")
    detected_at: Optional[datetime | str] = Field(default=None, description="Timestamp when the signal was detected (ISO 8601 format preferred).") # Allow string for flexibility
    confidence: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="Confidence in signal accuracy based on source and content")

class NegativeSignalDetectionOutput(BaseModel):
    detected_signals: List[NegativeSignalOutput] = Field(default=[], description="A list of detected negative signals.")

# Refined Pydantic model for the output of the enrichment task (SEO/Metadata only)
class EnrichmentOutput(BaseModel):
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Extracted website metadata (e.g., title, description tags).")
    seo_keywords: List[str] = Field(default=[], description="Relevant SEO keywords identified from website metadata.")

# NEW Pydantic model for the output of the signal validation task
class ValidationTaskOutput(BaseModel):
    validated_positive_signals: PositiveSignalDetectionOutput = Field(...) # Use the existing detection output model
    validated_negative_signals: NegativeSignalDetectionOutput = Field(...) # Use the existing detection output model
    ai_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0) in the quality and relevance of the validated signals.")

# Updated Pydantic model for the final deterministic scoring output
class ScoringOutput(BaseModel):
    score: float = Field(..., ge=0, le=100, description="The calculated lead score (0-100).")
    reasoning: str = Field(..., description="Detailed explanation of how the score was calculated, referencing signals and ICP match.")
    ai_confidence: float = Field(..., ge=0.0, le=1.0, description="AI's confidence score (0.0-1.0) based on the quality of input signals used for scoring.")
    # Include raw outputs if needed for debugging/storage, otherwise keep it clean
    # enrichment_data_raw: Optional[str] = None
    # positive_signals_raw: Optional[str] = None
    # negative_signals_raw: Optional[str] = None
# --- End Pydantic Models ---

class LeadScoringTasks:
    """Collection of tasks for lead scoring process"""

    # --- Coordinator Task --- 
    def analyze_initial_lead_task(self, agent: Agent, lead_data: Dict):
        """Task: Read `lead_data` input, return string: 'Lead: [ID]. MatchKey: [Website/Email/None]'. NO TOOLS."""
        # Drastically simplified description
        desc_text = dedent("""
        Read the `lead_data` dictionary from input context. 
        Find the best key (website or email) for domain matching. 
        Return a single string in the format specified in expected_output. 
        DO NOT USE ANY TOOLS.
        """)
        # Simplified expected output focusing on format
        expected_output_text = dedent("""
            Output Format: "Lead: [Identifier]. MatchKey: [Website/Email/None]"
            Example 1: "Lead: Some Company. MatchKey: somecompany.com"
            Example 2: "Lead: contact@example.org. MatchKey: contact@example.org"
            Example 3: "Lead: Lead123. MatchKey: None"
            """)
        return Task(
            description=desc_text.replace('{', '{{').replace('}', '}}'),
            expected_output=expected_output_text.replace('{', '{{').replace('}', '}}'),
            agent=agent,
            # Ensure no tools are accidentally associated if agent has multiple
            tools=[] 
        )

    # --- Enricher Task (SEO/Metadata Focused) ---
    def focused_enrich_lead_task(self, agent: Agent, context_tasks: List[Task]):
        """Creates a *focused* task for extracting SEO keywords and metadata from the *root* of a lead's website domain."""
        
        desc_text = dedent("""
        **Goal:** Extract SEO keywords and metadata *only from the home page (root domain)* of the specific lead's website.
        
        **Context:** You will receive input context containing lead details, including a '{website}' key which might contain a full URL with paths (e.g., http://example.com/some/page).
        
        **Tool Available:**
        - `ScrapeWebsiteTool`

        **Instructions:**
        1. Extract the full URL string from the '{website}' variable in the input context.
        2. **Parse this URL to get only the scheme (e.g., 'https') and the base domain/netloc (e.g., 'www.example.com'). Ignore any path, query parameters, or fragments.**
        3. **Construct the root URL** by combining the scheme and the base domain (e.g., 'https://www.example.com').
        4. If a valid root URL was constructed, use `ScrapeWebsiteTool` with this *root URL only* to fetch the home page content. Handle potential scraping errors gracefully.
        5. Analyze the scraped home page content (HTML) to find:
            - Content of `<meta name="keywords">` tags.
            - Content of `<meta name="description">` tag.
            - Content of `<title>` tag.
            - Store other relevant meta tags found in the metadata dictionary.
        6. If the original '{website}' value is missing/invalid, or if a root URL cannot be constructed, or if scraping the root URL fails, return default empty values (empty metadata dict, empty seo_keywords list) without generating an error.
        7. **Crucially: Do NOT include the full scraped HTML in the final output.**
        
        **Output Format:**
        Return *only* a JSON object strictly matching the EnrichmentOutput model structure (metadata dict, seo_keywords list), reflecting data from the website's root/home page.
        """)
        expected_output_text = "A validated JSON object conforming to the EnrichmentOutput model, containing website metadata and SEO keywords scraped *only from the root domain/home page* of the specific lead's website."
        return Task(
            description=desc_text, 
            agent=agent,
            expected_output=expected_output_text,
            output_pydantic=EnrichmentOutput, 
            context=context_tasks,
        )

    # --- Signal Detector Tasks ---
    def focused_negative_signal_detection_task(self, agent: Agent, context_tasks: List[Task]):
        """Creates a *focused* task for detecting specific negative signal types for the target company using targeted sources."""
        desc_text = dedent("""
        **Goal:** Detect specific negative signals *for the company named '{company}'* using targeted sources.
        
        **Context:** You will receive input context containing lead details, including a '{company}' key.
        
        **Instructions:**
        1. Extract the company name from the '{company}' variable in the input context.
        2. Use 'Search and Contents Tool'.
        3. Formulate specific search queries *incorporating the company name '{company}'* to target: Layoffs, Funding Rounds (failures/slowing), Hiring (reductions/restructuring), Product Launches (failures/delays), Negative Customer Feedback.
           *Example Query Format:* `"{company} layoffs" site:glassdoor.com` OR `"{company} funding problems" site:techcrunch.com`
        4. **Prioritize searching these sources:** `site:glassdoor.com`, `site:kununu.com`, `site:techcrunch.com`, `site:news.ycombinator.com`, `site:startbase.com`, `site:f6s.com`, `site:crunchbase.com`, general financial news.
        5. Extract relevant signals that are *specifically about {company}* based only on search results. Ignore generic industry news.
        6. For each relevant signal found, provide: signal_type, description, details (evidence), source, source_url.
        7. **Crucially: Do NOT include raw search snippets/text in final output.**
        8. **Error Handling:** If the 'Search and Contents Tool' fails (e.g., API error, network issue), do not stop. Log the failure internally if possible, and return an empty list `{{"detected_signals": []}}`.

        **Output Format:**
        Return *only* a JSON object strictly matching the NegativeSignalDetectionOutput model structure.
        Return an empty list `{{"detected_signals": []}}` if no specific signals about '{company}' are found or if the search tool fails.
        """)
        expected_output_text = "A validated JSON object conforming to the NegativeSignalDetectionOutput model, containing only negative signals specific to the company '{company}'."
        return Task(
            description=desc_text, # Use context interpolation
            agent=agent,
            expected_output=expected_output_text,
            output_pydantic=NegativeSignalDetectionOutput, 
            context=context_tasks
        )

    def focused_positive_signal_detection_task(self, agent: Agent, context_tasks: List[Task]):
        """Creates a *focused* task for detecting specific positive signal types for the target company using targeted sources."""
        desc_text = dedent("""
        **Goal:** Detect specific positive growth signals *for the company named '{company}'* using targeted sources.

        **Context:** You will receive input context containing lead details, including a '{company}' key.

        **Instructions:**
        1. Extract the company name from the '{company}' variable in the input context.
        2. Use 'Search and Contents Tool'.
        3. Formulate specific search queries *incorporating the company name '{company}'* to target: Funding Rounds (raised capital/amounts), Hiring (sprees/specific roles, check LinkedIn!), Product Launches (success/positive reviews), Positive Customer Feedback (growth/praise), Partnerships, New IP/Patents.
           *Example Query Formats to Try:*
           `"{company} funding round" site:techcrunch.com`
           `"{company} hiring" site:linkedin.com`
           `"{company} hiring" site:greenhouse.io | site:lever.co | site:jobs.ashbyhq.com` (Common ATS)
           `intitle:"{company}" hiring site:linkedin.com/jobs`
           `"{company} product launch"`
           `"{company} partnership"`
        4. **Prioritize searching these sources:** LinkedIn (especially jobs & company pages), TechCrunch, Crunchbase, company website/press releases, major ATS sites (Greenhouse, Lever, Ashby), Glassdoor.
        5. Extract relevant signals that are *specifically about {company}* based *only* on search results. Ignore generic industry trends.
        6. For each relevant signal found, provide: signal_type, description, details (evidence), source, source_url.
        7. **Crucially: Do NOT include raw search snippets/text in final output.**
        8. **Error Handling:** If the 'Search and Contents Tool' fails (e.g., API error, network issue), do not stop. Log the failure internally if possible, and return an empty list `{{"detected_signals": []}}`.

        **Output Format:**
        Return *only* a JSON object strictly matching the PositiveSignalDetectionOutput model structure.
        Return an empty list `{{"detected_signals": []}}` if no specific signals about '{company}' are found or if the search tool fails.
        """)
        expected_output_text = "A validated JSON object conforming to the PositiveSignalDetectionOutput model, containing only positive signals specific to the company '{company}'."
        return Task(
            description=desc_text, # Use context interpolation
            agent=agent,
            expected_output=expected_output_text,
            output_pydantic=PositiveSignalDetectionOutput, 
            context=context_tasks
        )

    # --- NEW Signal Validation Task ---
    def validate_signals_task(self, agent: Agent, context_tasks: List[Task]):
        """Task for the validation expert to review detected signals for relevance and assess confidence."""
        desc_text = dedent("""
        **Goal:** Validate detected signals *for the specific company '{company}'* and assess overall confidence in their quality.

        **Context:** Review the `detected_signals` lists from the outputs of `focused_positive_signal_detection_task` and `focused_negative_signal_detection_task`. You also have access to the original input context containing the target '{company}' name.
        
        **Instructions:**
        1. Access the lists of positive and negative signals from context.
        2. Extract the target company name from the '{company}' variable in the input context.
        3. For each signal in both lists, evaluate its:
            - Plausibility: Does the description make sense?
            - Relevance: Is it a meaningful business signal AND *is it explicitly about or demonstrably linked to the target company '{company}'*? Discard generic industry signals.
            - Uniqueness: Is it distinct from other signals in the list?
            - Source Reliability (Optional Bonus): Briefly assess if the source seems credible.
        4. Create new lists containing *only* the signals that pass validation (especially the relevance check for '{company}').
        5. Based on the number and perceived quality/reliability of the *validated*, *company-specific* signals, determine an overall AI confidence score between 0.0 and 1.0. 
           **Important:** If NO company-specific signals pass validation, assign a minimum confidence score of **0.3** to reflect uncertainty rather than certainty of absence. Otherwise, score between 0.3 and 1.0 based on the strength of validated signals.
        6. Structure the output according to the ValidationTaskOutput model, including the validated signal lists (`validated_positive_signals`, `validated_negative_signals`) and the confidence score (`ai_confidence`).
        
        **Output Format:**
        Return *only* a JSON object strictly matching the ValidationTaskOutput model structure.
        """)
        expected_output_text = "A validated JSON object conforming to the ValidationTaskOutput model, containing validated signal lists specific to '{company}' and an AI confidence score reflecting this specificity (minimum 0.3 if no specific signals found)."
        return Task(
            description=desc_text, # Use context interpolation
            agent=agent,
            expected_output=expected_output_text,
            output_pydantic=ValidationTaskOutput, # Use the new Pydantic model
            context=context_tasks # Depends on both signal detection tasks
        ) 