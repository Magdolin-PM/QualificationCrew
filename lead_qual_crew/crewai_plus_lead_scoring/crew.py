from typing import Dict, List, Optional
import json
import logging
import os
from uuid import UUID
from crewai import Crew, Process, Task
from datetime import datetime, timezone
from . import database
from .agents import LeadScoringAgents
from .tasks import LeadScoringTasks
from .database import LeadStatus, LeadStage, Lead, get_lead_by_id, update_lead
from fastapi import HTTPException
import re

class LeadScoringCrew:
    """Crew for orchestrating the lead scoring process"""

    def __init__(self, serper_api_key: str):
        self.agents = LeadScoringAgents(serper_api_key=serper_api_key)
        self.tasks = LeadScoringTasks()

    def _determine_lead_status(self, score: float) -> LeadStatus:
        """Determine lead status based on score"""
        if score >= 85:
            return LeadStatus.MONEY
        elif score >= 60:
            return LeadStatus.HOT
        elif score >= 45:
            return LeadStatus.WARM
        else:
            return LeadStatus.COLD

    def _determine_lead_priority(self, score: int) -> LeadStatus:
        """Determine lead priority enum based on score."""
        if score >= 85:
            return LeadStatus.money
        elif score >= 70:
            return LeadStatus.hot
        elif score >= 50:
            return LeadStatus.warm
        else:
            return LeadStatus.cold

    def _get_lead_data(self, lead_id: str, user_id: str) -> Dict:
        """Fetches lead data from the database.
        
        Note: user_id is passed for logging/context but not used to fetch the lead by its ID.
        """
        try:
            lead = get_lead_by_id(lead_id=UUID(lead_id)) 
            if not lead:
                logging.error(f"Lead not found: ID {lead_id}")
                raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
            
            full_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()
            if not full_name: full_name = None 

            lead_data = {
                "id": str(lead.id),
                "name": full_name, 
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "email": lead.email,
                "company": lead.company,
                "website": lead.website,
                "notes": lead.notes,
                "priority": lead.priority.name if lead.priority else None,
                "stage": lead.stage.name if lead.stage else None, 
                "created_at": str(lead.created_at) if lead.created_at else None,
                "score": lead.score, 
                "user_id": str(lead.created_by) if lead.created_by else None,
                "industry": lead.industry or "Unknown",
                "company_size": lead.company_size or "Unknown",
                "region": lead.region or "Unknown",
                "position": lead.position or "Unknown",
                "connection_degree": lead.connection_degree, 
                "last_contacted": str(lead.last_contacted) if lead.last_contacted else None
            }
            logging.info(f"Successfully fetched lead data for ID: {lead_id}")
            return lead_data
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            logging.error(f"Database error fetching lead {lead_id} (context user {user_id}): {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database error fetching lead {lead_id}")

    def _update_lead_in_db(self, lead_id: str, user_id: str, score_data: Dict):
        """Updates the lead score, priority, and scoring details in the database.
        
        IMPORTANT:
        - This method should ONLY update score, priority, and scoring_details
        - It should NEVER update the lead stage - that's the user's decision
        - Only numerical data and JSON details should be stored here
        """
        try:
            final_score = score_data.get("score")
            lead_uuid = UUID(lead_id)
            
            if final_score is not None and isinstance(final_score, (int, float)):
                int_score = int(final_score)
                priority_enum = self._determine_lead_priority(int_score)
                
                update_data = {
                    "score": int_score, 
                    "priority": priority_enum, # Set priority based on score
                    "scoring_details": json.dumps(score_data) 
                }
                # Remove automatic stage update
                logging.info(f"Updating Lead ID {lead_id} with final data: Score={update_data['score']}, Priority={update_data['priority'].name}")
                update_lead(lead_id=lead_uuid, **update_data)
                logging.info(f"Successfully updated data for Lead ID {lead_id}")
            else:
                logging.warning(f"Final score not found or invalid in result for Lead ID {lead_id}: {score_data}.")
                # Don't update stage to Closed Lost on scoring failure
        except Exception as e:
            logging.error(f"Database error updating lead {lead_id} (context user {user_id}): {e}", exc_info=True)
            # Don't attempt to set stage to Closed Lost on update failure

    def _clean_json_output(self, text: str) -> str:
        """Clean up LLM output to extract valid JSON from markdown or text."""
        # Handle markdown code blocks
        if '```json' in text or '```' in text:
            # Extract content between markdown code delimiters
            import re
            json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
            match = re.search(json_pattern, text)
            if match:
                return match.group(1).strip()
        
        # If no markdown code blocks, try to find JSON content using braces
        if '{' in text and '}' in text:
            # Find the first opening brace and last closing brace
            start_index = text.find('{')
            end_index = text.rfind('}') + 1  # +1 to include the closing brace
            if start_index < end_index:
                return text[start_index:end_index]
        
        # Fallback: Return the original text if no JSON-like content found
        return text
        
    def process_single_lead(self, lead_id: str, user_id: str, contacts_data: List[Dict]) -> Dict:
        """Processes a single lead through the sequential workflow, including domain matching."""
        logging.info(f"Starting processing for Lead ID: {lead_id}, User ID: {user_id}")
        
        lead_data = None
        lead_uuid = UUID(lead_id) # Convert once

        try:
            # 1. Fetch Lead Data
            lead_data = self._get_lead_data(lead_id, user_id)
        except HTTPException as http_exc:
            logging.error(f"Failed to fetch for lead {lead_id}: {http_exc.detail}")
            return {"error": f"Failed to fetch lead data: {http_exc.detail}", "lead_id": lead_id}
        except Exception as e:
            logging.error(f"Unexpected error during lead fetch/stage update for {lead_id}: {e}", exc_info=True)
            return {"error": "Unexpected error during lead fetch", "lead_id": lead_id}

        # 2. Define Agents
        coordinator = self.agents.lead_analysis_coordinator()
        enricher = self.agents.lead_enrichment_specialist()
        signaler = self.agents.signal_identification_specialist()
        scorer = self.agents.lead_score_calculation_specialist()
        
        # 3. Define Tasks
        try:
            analyze_task = self.tasks.analyze_initial_lead_task(coordinator, lead_data)
            domain_match_task = self.tasks.run_domain_match_task(coordinator, context_tasks=[analyze_task])
            enrich_task = self.tasks.focused_enrich_lead_task(enricher, context_tasks=[analyze_task])
            signal_task = self.tasks.focused_signal_detection_task(signaler, context_tasks=[analyze_task])
            score_task = self.tasks.focused_score_lead_task(scorer, context_tasks=[enrich_task, signal_task, domain_match_task])
            final_validation_task = self.tasks.final_validation_and_compilation_task(coordinator, context_tasks=[score_task])
        except Exception as e:
            logging.error(f"Error defining tasks for Lead ID {lead_id}: {e}", exc_info=True)
            return {"error": "Failed to define tasks", "lead_id": lead_id}

        # 4. Define the Crew
        crew = Crew(
            agents=[coordinator, enricher, signaler, scorer],
            tasks=[analyze_task, domain_match_task, enrich_task, signal_task, score_task, final_validation_task],
            process=Process.sequential,
            verbose=True
        )

        # 5. Execute the Crew
        logging.info(f"Executing crew for Lead ID: {lead_id}")
        # Construct the inputs dictionary for crew kickoff
        # Ensure top-level keys exist for potential interpolation in ANY task description
        inputs = {
            "lead_data": lead_data,  # Keep the full dict for context
            "contacts_data": contacts_data or [],
            # Add essential fields as top-level keys for interpolation safety
            "company": lead_data.get("company", "Unknown Company"),
            "website": lead_data.get("website", ""),
            "email": lead_data.get("email", ""),
            "position": lead_data.get("position", "Unknown Position"),
            "name": lead_data.get("name", "Unknown Lead"),
            "lead_id_str": lead_id, # Add lead_id as well if needed
            "user_id_str": user_id, # Add user_id if needed
        }
        final_result = None
        try:
            crew_output = crew.kickoff(inputs=inputs)
            final_result = final_validation_task.output.raw if final_validation_task.output else None
            logging.info(f"Crew execution completed for Lead ID: {lead_id}. Raw output received.")

            if final_result:
                # Check if result looks like a structured error message from validation
                if isinstance(final_result, str) and ("Validation failed" in final_result or "Error:" in final_result):
                    logging.error(f"Final validation task reported failure for Lead ID {lead_id}: {final_result}")
                    cleaned_error = self._clean_error_message(final_result)
                    return {"error": cleaned_error, "lead_id": lead_id}
                
                try:
                    # Attempt to clean and parse the result as JSON
                    cleaned_result = self._clean_json_output(final_result)
                    parsed_result = json.loads(cleaned_result)
                    logging.info(f"Successfully parsed final JSON result for Lead ID: {lead_id}")
                    
                    # Minimal validation for required fields
                    if not isinstance(parsed_result, dict) or "score" not in parsed_result or not isinstance(parsed_result.get("score"), (int, float)):
                        logging.error(f"Invalid or incomplete JSON structure in final result for Lead ID {lead_id}: {parsed_result}")
                        return {"error": "Invalid or incomplete final JSON structure from crew", "lead_id": lead_id}
                    
                    # If valid JSON structure, update the database and return
                    self._update_lead_in_db(lead_id, user_id, parsed_result) 
                    return parsed_result # Return the successful result dictionary
                    
                except json.JSONDecodeError as json_err:
                    logging.error(f"Failed to parse final crew output as JSON for Lead ID {lead_id}: {json_err}")
                    logging.error(f"Raw output was: {final_result}")
                    return {"error": "Failed to parse final crew output as JSON", "lead_id": lead_id, "raw_output": final_result}
                except Exception as e:
                    # Catch any other unexpected errors during result processing
                    logging.error(f"Unexpected error processing final result for Lead ID {lead_id}: {e}", exc_info=True)
                    return {"error": f"Unexpected error processing final result: {str(e)}", "lead_id": lead_id}
            else:
                logging.warning(f"Crew finished for Lead ID {lead_id}, but final task output was empty.")
                return {"error": "Crew finished with no final output", "lead_id": lead_id}

        except Exception as e:
            logging.error(f"Crew execution failed for Lead ID {lead_id}: {e}", exc_info=True)
            return {"error": "Crew execution failed", "lead_id": lead_id, "exception": str(e)}
            
    def _clean_error_message(self, text: str) -> str:
        """Clean up error messages from markdown or formatting."""
        # Remove markdown code blocks
        if '```' in text:
            text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        
        # Remove other markdown formatting
        text = re.sub(r'[\*_#`]', '', text)
        
        # Clean up extra whitespace
        text = ' '.join(text.split())
        
        # Extract the main error message
        if "Validation failed:" in text:
            return text[text.index("Validation failed:"):]
        elif "Error:" in text:
            return text[text.index("Error:"):]
        
        return text.strip()
