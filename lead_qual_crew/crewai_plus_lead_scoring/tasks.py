from typing import Dict, List
from crewai import Task, Agent
from . import database
from .agents import LeadScoringAgents
from textwrap import dedent
from .tools.network_tool import DomainMatchTool

class LeadScoringTasks:
    """Collection of tasks for lead scoring process"""

    # Removed __init__ as agents are passed directly to tasks now
    # def __init__(self, agents: LeadScoringAgents):
    #     self.agents = agents

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

    def run_domain_match_task(self, agent: Agent, context_tasks: List[Task]):
        """Task for the coordinator to run the DomainMatchTool."""
        desc_text = dedent("""
        1. Access the user's contacts data provided in the initial crew kickoff context (key 'contacts_data').
        2. Access the lead's identifier (website or email) determined by the previous task's context.
        3. Use the 'Domain Match Tool' with the contacts data and the lead's identifier.
        4. Record the exact output string from the tool.
        """)
        expected_output_text = dedent("""
            The string result from the Domain Match Tool, indicating matches or no matches found.
            Example: 'Found 2 contact(s)...' or 'No contacts found...'
            """)
        return Task(
            description=desc_text.replace('{', '{{').replace('}', '}}'),
            expected_output=expected_output_text.replace('{', '{{').replace('}', '}}'),
            agent=agent,
            context=context_tasks
        )

    # --- Enricher Task (Delegated by Coordinator) ---
    def focused_enrich_lead_task(self, agent: Agent, context_tasks: List[Task]):
        """Creates a *focused* task for enriching specific lead data points, prioritizing website scraping."""
        desc_text = dedent("""
        **Goal:** Enrich the lead by finding specific B2B information, prioritizing direct website data.
        
        **Context:** Get the lead identifier (company name, website) from the 'analyze_initial_lead_task' context.
        
        **Tools Available:**
        - `ScrapeWebsiteTool`
        - `SearchAndContentsTool` (fallback)

        **Instructions:**
        1. Extract lead identifiers from context.
        2. Prioritize Website Scraping:
           - If a website URL is available: Try `ScrapeWebsiteTool`.
           - On Success: Analyze text for required B2B details (Industry, Role, Size, Target Audience, Challenges, Trends).
           - On Failure or No URL: Proceed to Step 3.
        3. Web Search Fallback (If needed):
           - Use `SearchAndContentsTool` based on company name.
           - Search for the required B2B details.
           - Prioritize reliable sources.
        4. Synthesize Findings (prefer scraped data).
        5. **Crucially: Do NOT include raw scraped text/snippets in final output.**
        
        **Output Format:**
        Return *only* a JSON object strictly containing the required fields (industry, position, company_size, target_customer_profile, industry_challenges, industry_projections). Use "Not Found" if needed.
        Example structure in expected_output.
        """)
        # Note: Example JSON in expected_output needs braces escaped too.
        expected_output_text = """A JSON object with fields: industry, position, company_size, target_customer_profile, industry_challenges, industry_projections. Use 'Not Found' if needed. No raw text/snippets. Example: {{"industry": "SaaS", "position": "CEO", "company_size": "10-50", "target_customer_profile": "Enterprise", "industry_challenges": [], "industry_projections": []}}"""
        return Task(
            description=desc_text.replace('{', '{{').replace('}', '}}'),
            agent=agent,
            expected_output=expected_output_text.replace('{', '{{').replace('}', '}}'), # Escape braces here too
            context=context_tasks
        )

    # --- Coordinator Validation Task --- 
    # def validate_enrichment_task(self) -> Task: ... (Keep commented out for now)

    # --- Signal Detector Task (Delegated by Coordinator) ---
    def focused_signal_detection_task(self, agent: Agent, context_tasks: List[Task]):
        """Creates a *focused* task for detecting specific signal types."""
        desc_text = dedent("""
        **Goal:** Detect specific buying signals for the lead company.
        
        **Context:** Get lead identifiers (company name, website) from 'analyze_initial_lead_task' context.
        
        **Instructions:**
        1. Extract identifiers from context.
        2. Use 'Search and Contents Tool' to find recent signals.
        3. Search *specifically* for news/releases/postings on: Funding, Hiring, Layoffs.
        4. Prioritize reliable sources.
        5. For each signal, provide: description, source URL, priority (1-10).
        6. **Crucially: Do NOT include raw search snippets/text in final output.**

        **Output Format:**
        Return *only* JSON `{{"detected_signals": [ ...signals... ]}}`.
        Signal format structure specified in expected_output.
        Return `{{"detected_signals": []}}` if no signals found.
        """)
        # Note: Example JSON in expected_output needs braces escaped too.
        expected_output_text = """JSON `{{"detected_signals": [...]}}`. Signal format: {{"type": "<type>", "description": "...", "details": {{"evidence": "..."}}, "source": "...", "source_url": "...", "priority": <1-10>}}. Empty list if none."""
        return Task(
            description=desc_text.replace('{', '{{').replace('}', '}}'),
            agent=agent,
            expected_output=expected_output_text.replace('{', '{{').replace('}', '}}'), # Escape braces here too
            context=context_tasks
        )
        
    # --- Coordinator Validation Task --- 
    # def validate_signals_task(self) -> Task: ... (Keep commented out for now)

    # --- Scorer Task (Delegated by Coordinator) ---
    def focused_score_lead_task(self, agent: Agent, context_tasks: List[Task]):
        """Creates a *focused* task for calculating a robust, dynamic B2B lead score."""
        desc_text = dedent("""
        **Goal:** Calculate dynamic lead score using context and B2B logic.
        
        **Context Provided:**
        - Initial Lead Data (via `lead_data` input key): Contains connection degree etc.
        - Enriched Data (from enrichment task): JSON with relevant B2B details.
        - Signals List (from signal task): JSON list.
        - Domain Match Results (from domain match task): String.
            
        **Scoring Framework (100 points total):**
        1.  **ICP - Firmographics (40 pts):** Assess fit based on industry, region, size (1-50 good), target customer profile (Enterprise focus = high points). Use enriched data.
        2.  **ICP - Persona (15 pts):** Assess role/position match. Use enriched data.
        3.  **Buying Signals (20 pts):** Assess detected signals. Emphasize enterprise-focus signals.
        4.  **Connection Strength (15 pts):** Use connection degree (1st=high) or domain match result (match=medium) as fallback. Use initial lead data.
        5.  **Engagement (10 pts):** Default 5 pts.
            
        **Dynamic Adjustments (Apply ONE, prioritize 1):**
        - **Cond 1 (Strong Connect & Fit):** Trigger: (Strong connection) AND (Firmographics score high). Action: Halve Persona pts contribution, add deducted pts to Connection.
        - **Cond 2 (High Intent & Fit):** Trigger: (Signals score high) AND (Firmographics score high). Action: Add 5 pts to Signals (max 25), remove 5 pts from Engagement (min 0).
            
        **Instructions:**
        1. Extract all necessary data from context and initial inputs.
        2. Calculate baseline points per category.
        3. Evaluate & Apply Dynamic Adjustments (if triggered).
        4. Sum final points (0-100).
        5. Write detailed `reasoning` (baseline + adjustments).
        6. Populate `scoring_details` (component scores/reasoning, confidence, `dynamic_adjustment_applied`).
        7. Validate output JSON with 'Scoring Validation Tool'.
        """)
        # Note: Example JSON in expected_output needs braces escaped too.
        expected_output_text = dedent("""
            Validated JSON object (LeadScoringSchema) with score, reasoning, scoring_details reflecting dynamic logic.
            Example Structure: {{"score": 88, "reasoning": "...", "scoring_details": {{"icp_firmographics_score": ..., "dynamic_adjustment_applied": "..."}}}}
            """)
        return Task(
            description=desc_text.replace('{', '{{').replace('}', '}}'),
            expected_output=expected_output_text.replace('{', '{{').replace('}', '}}'), # Escape braces here too
            agent=agent,
            context=context_tasks
        )

    # --- Coordinator Final Validation & Compilation Task --- 
    def final_validation_and_compilation_task(self, agent: Agent, context_tasks: List[Task]):
        """Task for the Coordinator to perform final validation and compile the report."""
        desc_text = dedent("""
        **Goal:** Validate final scoring output and compile report.
        
        **Context:** Get scoring JSON output from previous task.
        
        **Instructions:**
        1. Access scoring JSON from context.
        2. Use 'Scoring Validation Tool' to check structure/types.
        3. If validation fails critically, report failure honestly.
        4. If validation tool provides `fixed_data`, use that.
        5. Do not fabricate data on critical failure.
        6. Return validated JSON or clear error message.
        """)
        # Note: Example JSON in expected_output needs braces escaped too.
        expected_output_text = dedent("""
            Either:
            1. Valid JSON object `{{ "score": ..., "reasoning": ... }}`.
            OR
            2. Error message: `Validation failed: ...`.
            """)
        return Task(
            description=desc_text.replace('{', '{{').replace('}', '}}'),
            expected_output=expected_output_text.replace('{', '{{').replace('}', '}}'), # Escape braces here too
            agent=agent,
            context=context_tasks
        ) 