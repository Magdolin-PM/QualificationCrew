from typing import Dict, List, Optional, Tuple, Any
import json
import logging
import os
from uuid import UUID
from crewai import Crew, Process, Task
from datetime import datetime, timezone
from . import database
from .agents import LeadScoringAgents
from .tasks import LeadScoringTasks, EnrichmentOutput, ScoringOutput, PositiveSignalDetectionOutput, NegativeSignalDetectionOutput, ValidationTaskOutput, PositiveSignalOutput, NegativeSignalOutput
from .database import LeadStatus, LeadStage, Lead, get_lead_by_id, update_lead, get_user_preferences, create_signal
from fastapi import HTTPException
import re
from crewai import Agent
from langchain_openai import ChatOpenAI

# Consider using a default LLM if not specified, or raise an error
default_llm = ChatOpenAI(model="gpt-3.5-turbo") 

class LeadScoringCrew:
    """Crew for orchestrating the lead scoring process"""

    def __init__(self, serper_api_key: str):
        self.agents = LeadScoringAgents(serper_api_key=serper_api_key)
        self.tasks = LeadScoringTasks()

    def _determine_lead_status(self, score: float) -> LeadStatus:
        """Determine lead status based on score"""
        if score >= 85:
            return LeadStatus.money
        elif score >= 60:
            return LeadStatus.hot
        elif score >= 40:
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

    def _update_lead_in_db(self, 
                           lead_id: str, 
                           user_id: str, 
                           enrichment_output: Optional[EnrichmentOutput], 
                           scoring_output: Optional[ScoringOutput], # The model with final score/reasoning/confidence
                           component_scores: Optional[Dict[str, Any]], # The detailed breakdown
                           ai_confidence: Optional[float] # Confidence from validator task output
                           ):
        """Updates the lead with enrichment, final score, confidence, and detailed scoring components."""
        lead_uuid = UUID(lead_id)
        update_payload = {}
        
        # 1. Process Enrichment Data
        if enrichment_output and isinstance(enrichment_output, EnrichmentOutput):
            try:
                update_payload["enrichment_data"] = enrichment_output.model_dump() 
                update_payload["is_enriched"] = True
                logging.info(f"Using validated enrichment data for Lead ID {lead_id}.")
            except Exception as e:
                logging.error(f"Error processing validated enrichment data for Lead ID {lead_id}: {e}", exc_info=True)
                update_payload["is_enriched"] = False
                update_payload["enrichment_data"] = {"error": f"Error processing enrichment model: {str(e)}"}
        else:
            logging.warning(f"No valid enrichment data model provided for Lead ID {lead_id}. Enrichment status set to False.")
            update_payload["is_enriched"] = False

        # 2. Process Scoring Data & Details
        if scoring_output and isinstance(scoring_output, ScoringOutput):
            try:
                # Add score and status from the final scoring output model
                update_payload["score"] = int(scoring_output.score)
                update_payload["lead_status"] = self._determine_lead_status(scoring_output.score) 
                # Add confidence score from the model
                update_payload["ai_confidence"] = scoring_output.ai_confidence
                # We might store the high-level reasoning separately if needed, but focusing on details now.
                # update_payload["reasoning"] = scoring_output.reasoning
                logging.info(f"Using validated scoring data for Lead ID {lead_id}. Score: {scoring_output.score}, Status: {update_payload['lead_status'].name}, Confidence: {scoring_output.ai_confidence}")
            except Exception as e:
                 logging.error(f"Error processing validated scoring data for Lead ID {lead_id}: {e}", exc_info=True)
                 # Clear score/status if processing failed
                 update_payload.pop("score", None)
                 update_payload.pop("lead_status", None)
                 update_payload.pop("ai_confidence", None)
        else:
             logging.warning(f"No valid scoring output model provided for Lead ID {lead_id}.")

        # Add the detailed component scores dictionary as JSON string
        if component_scores and isinstance(component_scores, dict):
             try:
                 update_payload["scoring_details"] = json.dumps(component_scores)
             except TypeError as json_err:
                 logging.error(f"Failed to serialize component_scores to JSON for {lead_id}: {json_err}")
                 update_payload["scoring_details"] = json.dumps({"error": "failed to serialize scoring details", "details": str(component_scores)})
        elif scoring_output: # If we had a scoring output but no component breakdown
            update_payload["scoring_details"] = json.dumps({"error": "component score breakdown missing", "final_score": scoring_output.score})
        else: # No scoring output at all
             update_payload["scoring_details"] = json.dumps({"error": "scoring failed or did not run"})


        # 3. Update Database if there's anything to update
        if update_payload:
            # Ensure ai_confidence is handled (it might be missing if scoring failed)
            if "ai_confidence" not in update_payload: update_payload["ai_confidence"] = None
            
            try:
                # Log payload, handling potential enums correctly
                log_payload = {k: (v.name if isinstance(v, LeadStatus) else v) for k, v in update_payload.items()}
                logging.info(f"Attempting database update for Lead ID {lead_id} with payload: {log_payload}")
                update_lead(lead_id=lead_uuid, **update_payload)
                logging.info(f"Successfully updated database for Lead ID {lead_id}")
            except Exception as e:
                logging.error(f"Database error updating lead {lead_id} (context user {user_id}): {e}", exc_info=True)
        else:
            logging.warning(f"No data to update in database for Lead ID {lead_id}.")
        
    def _trigger_outreach_crew(self, lead_id: str, user_id: str):
        """Trigger the outreach crew for a lead"""
        # API endpoint
        API_URL = "http://localhost:9000/api/run"
        payload = {
            "user_id": user_id,  # Example user ID
            "lead_ids": [lead_id],  # Single lead ID or list of lead IDs
        }
        response = requests.post(API_URL, json=payload)
        print(f"Outreach crew triggered for lead {lead_id}. Response: {response.json()}")

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

    def _process_and_store_signals(self, 
                                   # Accept the whole validation output
                                   validation_output: Optional[ValidationTaskOutput], 
                                   lead_id: str, 
                                   user_id: str):
        """Processes validated signal output and stores detected signals in the database."""
        if not validation_output or not isinstance(validation_output, ValidationTaskOutput):
            logging.info(f"No valid ValidationTaskOutput model provided for Lead ID {lead_id}. Skipping signal storage.")
            return

        lead_uuid = UUID(lead_id)
        user_uuid = UUID(user_id)
        
        # Process validated positive signals
        positive_signals_output = validation_output.validated_positive_signals
        if positive_signals_output:
            logging.info(f"Processing {len(positive_signals_output[0].detected_signals)} validated positive signals for Lead ID {lead_id}.")
            stored_count = 0
            if len(positive_signals_output) > 0:
                for signal_item in positive_signals_output[0].detected_signals:
                    if not isinstance(signal_item, PositiveSignalOutput):
                        logging.warning(f"Skipping invalid item in positive signal list: {signal_item} for Lead ID {lead_id}.")
                        continue
                try:
                    # Access attributes directly
                    source_url_str = str(signal_item.source_url) if signal_item.source_url else None
                    detected_at_val = signal_item.detected_at
                    
                    create_signal(
                        lead_id=lead_uuid, user_id=user_uuid,
                        signal_type=signal_item.signal_type,
                        description=signal_item.description,
                        details=signal_item.details,
                        source=signal_item.source,
                        source_url=source_url_str,
                        detected_at=detected_at_val
                    )
                    stored_count += 1
                except Exception as db_err:
                    logging.error(f"Database error storing positive signal for Lead ID {lead_id}: {db_err}. Signal data: {signal_item.model_dump()}", exc_info=True)
            logging.info(f"Stored {stored_count} validated positive signals for Lead ID {lead_id}.")
        else:
             logging.info(f"No validated positive signals found for Lead ID {lead_id}. Validation output: {validation_output}")

        # Process validated negative signals
        negative_signals_output = validation_output.validated_negative_signals
        if negative_signals_output:
            logging.info(f"Processing {len(negative_signals_output[0].detected_signals)} validated negative signals for Lead ID {lead_id}.")
            stored_count = 0
            if len(negative_signals_output) > 0:
                for signal_item in negative_signals_output[0].detected_signals:
                    if not isinstance(signal_item, NegativeSignalOutput):
                        logging.warning(f"Skipping invalid item in negative signal list: {signal_item} for Lead ID {lead_id}.")
                        continue
                    try:
                       # Access attributes directly
                       source_url_str = str(signal_item.source_url) if signal_item.source_url else None
                       detected_at_val = signal_item.detected_at

                       create_signal(
                           lead_id=lead_uuid, user_id=user_uuid,
                           signal_type=signal_item.signal_type,
                           description=signal_item.description,
                           details=signal_item.details,
                           source=signal_item.source,
                           source_url=source_url_str,
                           detected_at=detected_at_val
                       )
                       stored_count += 1
                    except Exception as db_err:
                       logging.error(f"Database error storing negative signal for Lead ID {lead_id}: {db_err}. Signal data: {signal_item.model_dump()}", exc_info=True)
            logging.info(f"Stored {stored_count} validated negative signals for Lead ID {lead_id}.")
        else:
             logging.info(f"No validated negative signals found for Lead ID {lead_id}.")

    def process_single_lead(self, lead_data: Dict, user_preferences: Dict, contacts_data: List[Dict]) -> Dict:
        """Processes a single lead using provided data: Enriches, Detects/Validates Signals, Scores Deterministically. (DB calls REMOVED for testing)"""
        # Use a placeholder ID for logging if needed, derived from input if possible
        test_lead_id = lead_data.get('id', 'test_lead') 
        logging.info(f"Starting TEST scoring process for Lead ID: {test_lead_id}")
        
        # --- 1. Fetch Lead Data & User Preferences --- (REMOVED - Data provided as arguments)
        # Ensure provided data is not None/empty for critical operations
        if not lead_data or not user_preferences:
            error_msg = "Missing lead_data or user_preferences for testing."
            logging.error(error_msg)
            return {"error": error_msg, "lead_id": test_lead_id}
        
        logging.info(f"Using provided lead_data for {test_lead_id}")
        logging.info(f"Using provided user_preferences for {test_lead_id}")

        # --- 2. Define Agents & Tasks --- 
        try:
            # Agents needed for this flow
            enricher = self.agents.lead_enrichment_specialist()
            pos_detector = self.agents.positive_signal_detector()
            neg_detector = self.agents.negative_signal_detector()
            validator = self.agents.signal_validation_expert() # New validator agent

            # Define Tasks in sequence
            enrich_task = self.tasks.focused_enrich_lead_task(enricher, context_tasks=[]) # Start with enrichment
            pos_detect_task = self.tasks.focused_positive_signal_detection_task(pos_detector, context_tasks=[enrich_task]) # Depends on enrichment context?
            neg_detect_task = self.tasks.focused_negative_signal_detection_task(neg_detector, context_tasks=[enrich_task]) # Depends on enrichment context?
            validate_task = self.tasks.validate_signals_task(validator, context_tasks=[pos_detect_task, neg_detect_task]) # Depends on both detectors
            
            # List of tasks for the crew
            crew_tasks = [enrich_task, pos_detect_task, neg_detect_task, validate_task]
            crew_agents = [enricher, pos_detector, neg_detector, validator]

        except Exception as e:
            logging.error(f"Error defining agents/tasks for Lead ID {test_lead_id}: {e}", exc_info=True)
            return {"error": "Failed to define agents/tasks", "lead_id": test_lead_id}

        # --- 3. Define and Execute the Crew --- 
        crew = Crew(
            agents=crew_agents,
            tasks=crew_tasks,
            process=Process.sequential,
            verbose=True 
        )

        logging.info(f"Executing simplified crew (enrich, detect, validate) for Lead ID: {test_lead_id}")
        enrichment_output: Optional[EnrichmentOutput] = None
        validation_output: Optional[ValidationTaskOutput] = None # This holds validated signals + confidence
        crew_execution_error = None
        crew_result = None # Store raw result if needed
        
        try:
            # Prepare inputs using provided data
            crew_inputs = {
                "lead_data": lead_data,
                "user_preferences": user_preferences, # Use provided preferences
                "contacts_data": contacts_data or [],
                # Add other essential fields if needed by specific task descriptions
                "company": lead_data.get("company", "Unknown Company"),
                "website": lead_data.get("website", ""),
                "email": lead_data.get("email", ""),
                "position": lead_data.get("position", "Unknown Position"),
                "name": lead_data.get("name", "Unknown Lead"),
                # Pass placeholders or derive from lead_data if needed for logging/context within tasks
                "lead_id_str": str(test_lead_id), 
                "user_id_str": str(user_preferences.get('user_id', 'test_user')) # Example: get user_id from prefs if available
            }
            crew_result = crew.kickoff(inputs=crew_inputs)
            
            # Access structured outputs from the final relevant tasks (Safely)
            enrichment_output = None
            if enrich_task.output and hasattr(enrich_task.output, 'structured_output'):
                 enrichment_output = enrich_task.output.structured_output
            elif enrich_task.output and enrich_task.output.raw:
                 # Try parsing raw enrichment output if structured is missing (optional)
                 try:
                    enrichment_output = EnrichmentOutput.model_validate_json(enrich_task.output.raw) # Or model_validate if dict
                    logging.info(f"Successfully parsed raw EnrichmentOutput for {test_lead_id}")
                 except Exception as parse_err:
                    logging.warning(f"Enrich task for {test_lead_id} missing structured_output and raw output failed parsing ({parse_err}). Raw: {enrich_task.output.raw}")
            else:
                 logging.warning(f"Enrich task for {test_lead_id} has no output.")

            # Attempt to parse validator output
            validation_raw_output = validate_task.output.raw if validate_task.output else None
            validation_output: Optional[ValidationTaskOutput] = None # Reset
            
            if validation_raw_output:
                try:
                    print(f"Validation raw output: {validation_raw_output}")
                    # CrewAI raw output might be a string or dict, handle both
                    if isinstance(validation_raw_output, str):
                        print(f"Validation raw output is a string: {validation_raw_output}")
                        validation_output = ValidationTaskOutput.model_validate_json(validation_raw_output)
                    elif isinstance(validation_raw_output, dict):
                        print(f"Validation raw output is a dict: {validation_raw_output}")
                        validation_output = ValidationTaskOutput.model_validate(validation_raw_output)
                    else:
                        print(f"Validation raw output is an unexpected type: {type(validation_raw_output)}")
                        logging.error(f"Validator output for {test_lead_id} is unexpected type: {type(validation_raw_output)}")
                    
                    if validation_output:
                        logging.info(f"Successfully parsed ValidationTaskOutput for {test_lead_id}")
                        
                except Exception as parse_err:
                    print(f"Failed to parse validator output for {test_lead_id}. Error: {parse_err}")
                    logging.error(f"Failed to parse validator output for {test_lead_id}. Error: {parse_err}. Raw: {validation_raw_output}")
                    # Keep validation_output as None
            else:
                 logging.warning(f"Validate task for {test_lead_id} has no raw output.")

            logging.info(f"Crew execution completed for Lead ID: {test_lead_id}. Outputs retrieved (or missing).")
            
            # Validate the crucial ValidationTaskOutput (if it was retrieved and parsed)
            if validation_output is None:
                 logging.error(f"Validation task for {test_lead_id} did not produce a valid structured output model. Cannot score.")
                 if not crew_execution_error: # Don't overwrite previous crew error
                      crew_execution_error = f"Signal validation failed to produce structured output."
            # No need for isinstance check here now, parsing handled above
            # elif not isinstance(validation_output, ValidationTaskOutput):
            #      logging.error(f"Validation task for {test_lead_id} returned unexpected structured output type: {type(validation_output)}. Cannot score.")
            #      if not crew_execution_error:
            #           crew_execution_error = f"Signal validation returned invalid model type."
            else:
                 logging.info(f"Signal validation successful for {test_lead_id}. Confidence: {validation_output.ai_confidence}")

        except Exception as e:
            logging.error(f"Crew execution failed for Lead ID {test_lead_id}: {e}", exc_info=True)
            crew_execution_error = f"Crew execution failed: {str(e)}"
            # Attempt to get enrichment output even if crew failed later (Safely)
            try:
                 if enrich_task.output and hasattr(enrich_task.output, 'structured_output'):
                      enrichment_output = enrich_task.output.structured_output
                 else:
                      # Already logged warning above if output exists but lacks structure
                      pass 
            except Exception as partial_e:
                 logging.error(f"Error retrieving partial enrichment output after crew failure for {test_lead_id}: {partial_e}")

        # --- 4. Deterministic Scoring (if validation succeeded) --- 
        scoring_output_model: Optional[ScoringOutput] = None
        component_scores_dict: Optional[Dict[str, Any]] = None
        ai_confidence_score: Optional[float] = None

        if validation_output and isinstance(validation_output, ValidationTaskOutput):
            ai_confidence_score = validation_output.ai_confidence # Get confidence from validator
            try:
                logging.info(f"Calculating deterministic score for Lead ID {test_lead_id}")
                scoring_output_model, component_scores_dict = self._calculate_deterministic_score(
                    lead_data=lead_data,
                    user_preferences=user_preferences,
                    validated_positive_signals=validation_output.validated_positive_signals,
                    validated_negative_signals=validation_output.validated_negative_signals,
                    ai_confidence=ai_confidence_score 
                )
                logging.info(f"Deterministic score calculated for {test_lead_id}: {scoring_output_model.score}")
            except Exception as score_err:
                logging.error(f"Error during deterministic scoring for {test_lead_id}: {score_err}", exc_info=True)
                if not crew_execution_error: # Don't overwrite crew error
                     crew_execution_error = f"Deterministic scoring failed: {str(score_err)}"
        elif not crew_execution_error: # If validation didn't produce output and no prior error
             crew_execution_error = "Signal validation did not produce valid output for scoring."
        
        # --- 5. Store Results (Signals and Lead Update) --- (REMOVED FOR TESTING)
        try:
            # Store validated signals
            logging.info(f"Storing validated signals for Lead ID {test_lead_id}")
            self._process_and_store_signals(validation_output, test_lead_id, user_preferences.get('user_id', 'test_user')) # Use test IDs
            
            # Update lead record (pass scoring model, components, and confidence)
            logging.info(f"Updating lead details in DB for Lead ID {test_lead_id}")
            self._update_lead_in_db(
                lead_id=test_lead_id, 
                user_id=user_preferences.get('user_id', 'test_user'), 
                enrichment_output=enrichment_output, 
                scoring_output=scoring_output_model, # Pass the model from deterministic calc
                component_scores=component_scores_dict, # Pass the components dict
                ai_confidence=ai_confidence_score # Pass confidence from validation
            )
            self._trigger_outreach_crew(lead_id=test_lead_id, user_id=user_preferences.get('user_id', 'test_user'))
        except Exception as db_e:
             logging.error(f"Error during final database updates for Lead ID {test_lead_id}: {db_e}", exc_info=True)
             if not crew_execution_error:
                  crew_execution_error = f"Database update failed after processing: {str(db_e)}"

        # --- 6. Return Final Result --- 
        if crew_execution_error:
            # Return error if any step failed critically
            return {"error": crew_execution_error, "lead_id": test_lead_id}
        elif scoring_output_model:
            # Return the calculated scoring output as a dictionary on success
            logging.info(f"TEST RUN successful for {test_lead_id}. Returning score model.")
            return scoring_output_model.model_dump()
        elif validation_output: # If scoring failed but validation worked, return validation output
            logging.warning(f"TEST RUN for {test_lead_id}: Scoring failed but validation output exists. Returning validation model.")
            return validation_output.model_dump()
        else:
            # Fallback if crew ran but scoring/validation didn't produce output
            logging.error(f"TEST RUN completed for {test_lead_id} but no score/validation output generated. Returning raw crew result if available.")
            return {"error": "Processing finished with unexpected state (no score/validation output)", "lead_id": test_lead_id, "raw_crew_result": crew_result}
            
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

    def _calculate_deterministic_score(
        self,
        lead_data: Dict,
        user_preferences: Dict,
        validated_positive_signals: Optional[List[PositiveSignalDetectionOutput]],
        validated_negative_signals: Optional[List[NegativeSignalDetectionOutput]],
        ai_confidence: float # Get confidence from validator task
    ) -> Tuple[ScoringOutput, Dict[str, Any]]:
        """
        Calculates the lead score based on deterministic rules and validated inputs.

        Args:
            lead_data: Dictionary containing data for the specific lead.
            user_preferences: Dictionary containing the user's ICP criteria.
            validated_positive_signals: Pydantic model output from the validation task.
            validated_negative_signals: Pydantic model output from the validation task.
            ai_confidence: Confidence score from the validation task.

        Returns:
            A tuple containing:
                - ScoringOutput: Pydantic model instance with final score and reasoning.
                - Dict[str, Any]: Dictionary with detailed component scores.
        """
        total_score = 0.0
        reasoning_parts = []
        component_scores = {} # Dictionary to store details

        # --- Define Strong Signals ---
        STRONG_SIGNALS = {
            "positive": ["series_funding", "cxo_hiring", "gov_contract", "ipo_filing"],
            "negative": ["delisting_notice", "sec_investigation", "pension_freezing"]
        }
        # Point values for signals
        NORMAL_POS_POINTS = 5.0
        STRONG_POS_POINTS = 10.0 # Example: double points for strong positive
        NORMAL_NEG_DEDUCTION = -10.0
        STRONG_NEG_DEDUCTION = -15.0 # Example: higher deduction for strong negative
        MAX_POS_SIGNAL_SCORE = 20.0
        MAX_NEG_SIGNAL_DEDUCTION = -30.0 # Min score contribution from neg signals is 0

        # --- Helper for safe access and comparison ---
        def check_match(lead_value, pref_values_list) -> bool:
            if lead_value is None or not pref_values_list:
                return False
            lead_lower = str(lead_value).lower().strip()
            # Handle cases where pref_values_list might be a list of strings OR a list containing one comma-separated string
            processed_prefs = []
            for item in pref_values_list:
                if isinstance(item, str):
                    processed_prefs.extend([p.strip().lower() for p in item.split(',') if p.strip()])
                else: # Handle potential non-string items if necessary
                    processed_prefs.append(str(item).lower().strip())
            
            # Check if any part of the lead value matches any preference
            # (e.g., "SaaS" in "HR Tech, AI, SaaS" matches pref "saas")
            lead_parts = {part.strip().lower() for part in lead_lower.split(',') if part.strip()}
            return any(part in processed_prefs for part in lead_parts)

        # --- Extract Lead Data (with defaults) ---
        lead_position = lead_data.get('position')
        lead_industry = lead_data.get('industry')
        lead_region = lead_data.get('region')
        lead_company_size = lead_data.get('company_size')
        connection_degree = lead_data.get('connection_degree')
        last_contacted = lead_data.get('last_contacted') 
        
        # --- Extract User Preferences (with defaults) ---
        # Note: These might contain comma-separated strings within the list
        pref_roles = user_preferences.get('icp_role', [])
        pref_industries = user_preferences.get('icp_industry', [])
        pref_regions = user_preferences.get('icp_region', [])
        pref_company_sizes = user_preferences.get('icp_company_size', [])

        # 1. ICP Match (30 points total = 5 + 10 + 5 + 10)
        icp_score = 0.0
        icp_reasons = []
        
        # Role Match (5 points)
        if check_match(lead_position, pref_roles):
            icp_score += 5.0
            icp_reasons.append(f"Role Match ({lead_position})")
        # Industry Match (10 points) - Use the refined check_match
        if check_match(lead_industry, pref_industries):
            icp_score += 10.0
            icp_reasons.append(f"Industry Match ({lead_industry})")
        # Region Match (5 points)
        if check_match(lead_region, pref_regions):
            icp_score += 5.0
            icp_reasons.append(f"Region Match ({lead_region})")
        # Company Size Match (10 points)
        if check_match(lead_company_size, pref_company_sizes):
            icp_score += 10.0
            icp_reasons.append(f"Size Match ({lead_company_size})")

        component_scores["icp_match_score"] = icp_score
        component_scores["icp_match_reasons"] = icp_reasons
        total_score += icp_score
        reasoning_parts.append(f"ICP Match: {icp_score:.1f}/30 ({len(icp_reasons)} matches)")

        # 2. Connection Degree (10 points)
        connection_score = 0.0
        if connection_degree == 1:
            connection_score = 10.0
        elif connection_degree == 2:
            connection_score = 5.0
        component_scores["connection_degree_score"] = connection_score
        component_scores["connection_degree"] = connection_degree
        total_score += connection_score
        reasoning_parts.append(f"Connection: {connection_score:.1f}/10 (Degree: {connection_degree if connection_degree is not None else 'Unknown'})")

        # 3. Negative Signals Impact (Score starts at 30, deduct points, min score contribution 0)
        negative_signals_deduction = 0.0 # Total deduction, capped at 30
        num_neg_signals = 0
        num_strong_neg_signals = 0
        if validated_negative_signals and isinstance(validated_negative_signals, NegativeSignalDetectionOutput):
            num_neg_signals = len(validated_negative_signals.detected_signals)
            for signal in validated_negative_signals.detected_signals:
                if signal.signal_type in STRONG_SIGNALS["negative"]:
                    negative_signals_deduction += abs(STRONG_NEG_DEDUCTION) # Add deduction amount
                    num_strong_neg_signals += 1
                else:
                    negative_signals_deduction += abs(NORMAL_NEG_DEDUCTION)
        
        # Cap the total deduction
        capped_deduction = min(negative_signals_deduction, abs(MAX_NEG_SIGNAL_DEDUCTION))
        neg_signal_score_contribution = 30.0 - capped_deduction # Calculate contribution (30 - deduction)

        component_scores["negative_signals_score"] = neg_signal_score_contribution 
        component_scores["negative_signals_count"] = num_neg_signals
        component_scores["negative_signals_strong_count"] = num_strong_neg_signals
        total_score += neg_signal_score_contribution
        reasoning_parts.append(f"Neg Signals: {neg_signal_score_contribution:.1f}/30 ({num_neg_signals} found, {num_strong_neg_signals} strong)")

        # 4. Positive Signals Impact (Score starts at 0, add points, max score contribution MAX_POS_SIGNAL_SCORE)
        pos_signal_points = 0.0
        num_pos_signals = 0
        num_strong_pos_signals = 0
        if validated_positive_signals and isinstance(validated_positive_signals, PositiveSignalDetectionOutput):
            if len(validated_positive_signals) > 0:
                num_pos_signals = len(validated_positive_signals[0].detected_signals)
                for signal in validated_positive_signals[0].detected_signals:
                    if signal.signal_type in STRONG_SIGNALS["positive"]:
                         pos_signal_points += STRONG_POS_POINTS
                         num_strong_pos_signals += 1
                    else:
                         pos_signal_points += NORMAL_POS_POINTS
        
        # Cap the score contribution
        capped_pos_signal_score = min(pos_signal_points, MAX_POS_SIGNAL_SCORE)

        component_scores["positive_signals_score"] = capped_pos_signal_score
        component_scores["positive_signals_count"] = num_pos_signals
        component_scores["positive_signals_strong_count"] = num_strong_pos_signals
        total_score += capped_pos_signal_score
        reasoning_parts.append(f"Pos Signals: +{capped_pos_signal_score:.1f}/{MAX_POS_SIGNAL_SCORE:.1f} ({num_pos_signals} found, {num_strong_pos_signals} strong)")

        # 5. Engagement History (10 points)
        engagement_score = 0.0
        contacted = bool(last_contacted) 
        if contacted:
            engagement_score = 10.0
        component_scores["engagement_score"] = engagement_score
        component_scores["last_contacted"] = contacted
        total_score += engagement_score
        reasoning_parts.append(f"Engagement: {engagement_score:.1f}/10 ({'Yes' if contacted else 'No'})")

        # Clamp final score
        final_score = max(0.0, min(100.0, total_score))

        # Construct final reasoning string
        final_reasoning = f"Score: {final_score:.1f}. Confidence: {ai_confidence:.2f}. Breakdown: " + " | ".join(reasoning_parts)

        # Create the ScoringOutput object
        scoring_output_model = ScoringOutput(
            score=final_score, 
            reasoning=final_reasoning,
            ai_confidence=ai_confidence 
        )

        return scoring_output_model, component_scores
