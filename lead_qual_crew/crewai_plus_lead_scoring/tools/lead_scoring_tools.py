from crewai.tools.base_tool import BaseTool
from typing import Dict, List
from .. import database

class EnrichmentValidationTool(BaseTool):
    name: str = "validate_enrichment"
    description: str = """Validates the quality and completeness of enriched lead data.
    Checks for required fields, data accuracy, and source reliability."""
    
    def _run(self, enriched_data: Dict) -> Dict:
        validation_result = {
            "is_valid": True,
            "missing_fields": [],
            "quality_issues": [],
            "source_validation": {},
            "confidence_score": 0.0
        }
        
        required_fields = [
            "company_description",
            "industry",
            "company_challenges",
            "recent_developments",
            "growth_indicators"
        ]
        
        # Check for missing fields
        for field in required_fields:
            if field not in enriched_data or not enriched_data[field]:
                validation_result["is_valid"] = False
                validation_result["missing_fields"].append(field)
        
        # Validate data sources
        sources = enriched_data.get("data_sources", {})
        source_weights = {
            "company_website": 1.0,
            "linkedin": 0.9,
            "crunchbase": 0.8,
            "news_articles": 0.7,
            "other": 0.5
        }
        
        total_source_score = 0
        source_count = 0
        
        for source, weight in source_weights.items():
            if source in sources:
                source_data = sources[source]
                source_validation = {
                    "present": True,
                    "last_updated": source_data.get("last_updated", "unknown"),
                    "completeness": 0.0
                }
                
                # Check source data completeness
                if isinstance(source_data, dict):
                    fields_present = len([v for v in source_data.values() if v])
                    total_fields = len(source_data)
                    source_validation["completeness"] = (fields_present / total_fields) * 100 if total_fields > 0 else 0
                    
                    total_source_score += source_validation["completeness"] * weight
                    source_count += 1
                
                validation_result["source_validation"][source] = source_validation
        
        # Calculate source confidence score
        source_confidence = (total_source_score / source_count) if source_count > 0 else 0
        
        # Check data freshness
        if "last_enrichment" in enriched_data:
            from datetime import datetime, timezone
            try:
                enrichment_date = datetime.fromisoformat(enriched_data["last_enrichment"].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                days_old = (now - enrichment_date).days
                
                if days_old > 30:
                    validation_result["quality_issues"].append(f"Data is {days_old} days old")
                    source_confidence *= 0.8  # Reduce confidence for old data
            except (ValueError, AttributeError):
                validation_result["quality_issues"].append("Invalid enrichment date format")
        
        # Calculate overall confidence score
        completeness_score = ((len(required_fields) - len(validation_result["missing_fields"])) / len(required_fields)) * 100
        validation_result["confidence_score"] = (completeness_score * 0.6) + (source_confidence * 0.4)
        
        # Add quality metrics
        validation_result["quality_metrics"] = {
            "completeness_score": completeness_score,
            "source_confidence": source_confidence,
            "data_freshness": "good" if not any("days old" in issue for issue in validation_result["quality_issues"]) else "needs_update"
        }
        
        return validation_result

class SignalValidationTool(BaseTool):
    name: str = "validate_signals"
    description: str = """Validates detected signals for accuracy, relevance, and evidence quality.
    Ensures signals are properly supported and prioritized."""
    
    def _run(self, signals_data: Dict) -> Dict:
        validation_result = {
            "is_valid": True,
            "invalid_signals": [],
            "confidence_scores": {},
            "overall_confidence": 0.0
        }
        
        if "detected_signals" not in signals_data:
            validation_result["is_valid"] = False
            return validation_result
        
        total_confidence = 0
        for signal in signals_data["detected_signals"]:
            signal_confidence = 0
            issues = []
            
            # Check required fields
            if not all(k in signal for k in ["type", "description", "details", "source"]):
                issues.append("Missing required fields")
            
            # Check evidence quality
            if "details" in signal and "evidence" in signal["details"]:
                if len(signal["details"]["evidence"]) > 50:
                    signal_confidence += 40
                if "source_url" in signal and signal["source_url"]:
                    signal_confidence += 30
                if "impact" in signal["details"] and signal["details"]["impact"]:
                    signal_confidence += 30
            
            if issues:
                validation_result["invalid_signals"].append({
                    "signal": signal["type"],
                    "issues": issues
                })
                validation_result["is_valid"] = False
            
            validation_result["confidence_scores"][signal["type"]] = signal_confidence
            total_confidence += signal_confidence
        
        num_signals = len(signals_data["detected_signals"])
        validation_result["overall_confidence"] = total_confidence / (num_signals * 100) if num_signals > 0 else 0
        
        return validation_result

class ScoringValidationTool(BaseTool):
    name: str = "validate_scoring"
    description: str = """Validates lead scoring results and structure.
    Ensures the JSON format is correct and all required fields are present."""
    
    def _run(self, scoring_data: Dict) -> Dict:
        validation_result = {
            "is_valid": True,
            "issues": [],
            "fixed_data": None,
            "message": "",
            "confidence_score": 0.0
        }
        
        # Make a copy of scoring data to fix
        fixed_data = scoring_data.copy() if isinstance(scoring_data, dict) else {}
        validation_result["fixed_data"] = fixed_data
        
        # Basic structure validation
        if not isinstance(scoring_data, dict):
            validation_result["is_valid"] = False
            validation_result["issues"].append("Input is not a dictionary")
            validation_result["message"] = "Input must be a JSON object"
            # Create a minimal valid structure 
            validation_result["fixed_data"] = {
                "score": 50,
                "reasoning": "Auto-generated due to invalid input format",
                "scoring_details": {
                    "icp_score": 25,
                    "icp_reasoning": "Auto-generated",
                    "engagement_score": 8,
                    "engagement_reasoning": "Auto-generated",
                    "signals_score": 7,
                    "signals_reasoning": "Auto-generated",
                    "connection_score": 10,
                    "connection_reasoning": "Auto-generated",
                    "ai_confidence": 30,
                    "confidence_reasoning": "Low confidence due to invalid input format"
                }
            }
            return validation_result
        
        # Check for required top-level fields
        required_fields = ["score", "reasoning"]
        missing_fields = [field for field in required_fields if field not in scoring_data]
        
        if missing_fields:
            validation_result["is_valid"] = False
            validation_result["issues"].append(f"Missing required fields: {', '.join(missing_fields)}")
            validation_result["message"] = "The scoring object must contain 'score' and 'reasoning' fields"
            
            # Add missing fields with default values
            if "score" not in fixed_data:
                fixed_data["score"] = 50  # Default mid-range score
            if "reasoning" not in fixed_data:
                fixed_data["reasoning"] = "Auto-generated reasoning due to missing field"
        
        # Validate score is a number
        if "score" in scoring_data:
            score = scoring_data["score"]
            if not isinstance(score, (int, float)):
                validation_result["is_valid"] = False
                validation_result["issues"].append(f"Score is not a number: {score}")
                validation_result["message"] = "Score must be a number between 0 and 100"
                # Try to convert string to number if possible
                try:
                    fixed_data["score"] = int(score)
                except (ValueError, TypeError):
                    fixed_data["score"] = 50  # Default value
            elif not (0 <= score <= 100):
                validation_result["is_valid"] = False
                validation_result["issues"].append(f"Score is out of range: {score}")
                validation_result["message"] = "Score must be between 0 and 100"
                # Fix the score to be within range
                fixed_data["score"] = min(max(0, score), 100)
        
        # Ensure scoring_details exists
        if "scoring_details" not in fixed_data:
            fixed_data["scoring_details"] = {}
            validation_result["issues"].append("scoring_details object is missing, created empty one")
            
        # Validate scoring_details if present in original data
        if "scoring_details" in scoring_data:
            details = scoring_data["scoring_details"]
            
            # Handle non-dict scoring_details
            if not isinstance(details, dict):
                validation_result["is_valid"] = False
                validation_result["issues"].append("scoring_details is not an object")
                validation_result["message"] = "scoring_details must be a JSON object"
                fixed_data["scoring_details"] = {}  # Reset to empty dict for fixes
            else:
                # Copy the valid dict
                fixed_data["scoring_details"] = details.copy()
            
            # Check for component scores
            component_scores = [
                "icp_score", "engagement_score", "signals_score", "connection_score"
            ]
            
            # Add missing component scores
            for comp in component_scores:
                if comp not in fixed_data["scoring_details"]:
                    # Default values for missing scores
                    if comp == "icp_score":
                        fixed_data["scoring_details"][comp] = 25  # 50% of 50
                    else:
                        fixed_data["scoring_details"][comp] = 10  # Default for other components
                    
                    # Add reasoning for the component
                    reasoning_field = f"{comp}_reasoning"
                    if reasoning_field not in fixed_data["scoring_details"]:
                        fixed_data["scoring_details"][reasoning_field] = f"Auto-generated for missing {comp}"
                    
                    validation_result["issues"].append(f"Added missing score component: {comp}")
            
            # Check for component reasonings
            for comp in component_scores:
                reasoning_field = f"{comp}_reasoning"
                if comp in fixed_data["scoring_details"] and reasoning_field not in fixed_data["scoring_details"]:
                    fixed_data["scoring_details"][reasoning_field] = f"Auto-generated reasoning for {comp}"
                    validation_result["issues"].append(f"Added missing reasoning for: {comp}")
            
            # Ensure ai_confidence exists
            if "ai_confidence" not in fixed_data["scoring_details"]:
                fixed_data["scoring_details"]["ai_confidence"] = 70
                fixed_data["scoring_details"]["confidence_reasoning"] = "Auto-assigned confidence score as it was missing"
                validation_result["issues"].append("Added missing ai_confidence")
            elif "confidence_reasoning" not in fixed_data["scoring_details"]:
                fixed_data["scoring_details"]["confidence_reasoning"] = "Auto-assigned confidence reasoning"
                validation_result["issues"].append("Added missing confidence_reasoning")
        
        # Handle the case where scoring_details wasn't in original data but we created it
        else:
            # Create complete scoring details structure
            component_scores = [
                "icp_score", "engagement_score", "signals_score", "connection_score"
            ]
            
            for comp in component_scores:
                if comp not in fixed_data["scoring_details"]:
                    # Default values
                    if comp == "icp_score":
                        fixed_data["scoring_details"][comp] = 25  # 50% of 50
                    else:
                        fixed_data["scoring_details"][comp] = 10  # Default for others
                
                # Add reasoning for each component
                reasoning_field = f"{comp}_reasoning"
                if reasoning_field not in fixed_data["scoring_details"]:
                    fixed_data["scoring_details"][reasoning_field] = f"Auto-generated for missing {comp}"
            
            # Ensure ai_confidence exists
            if "ai_confidence" not in fixed_data["scoring_details"]:
                fixed_data["scoring_details"]["ai_confidence"] = 60
                fixed_data["scoring_details"]["confidence_reasoning"] = "Auto-assigned low confidence due to missing details"
        
        # Calculate confidence score based on issues
        issue_count = len(validation_result["issues"])
        validation_result["confidence_score"] = max(0, 100 - (issue_count * 10))
        
        # If valid but with warnings
        if validation_result["is_valid"] and validation_result["issues"]:
            validation_result["message"] = "Valid with warnings: " + validation_result["message"]
        elif validation_result["is_valid"]:
            validation_result["message"] = "Validation passed"
        else:
            validation_result["message"] = "Validation failed, but data has been fixed: " + validation_result["message"]
        
        # Always return the fixed data, even if validation passed
        return validation_result

class DataQualityTool(BaseTool):
    name: str = "check_data_quality"
    description: str = """Comprehensive data quality assessment tool.
    Checks for completeness, accuracy, and consistency across all lead data."""
    
    def _run(self, lead_data: Dict) -> Dict:
        quality_result = {
            "completeness_score": 0.0,
            "consistency_score": 0.0,
            "accuracy_score": 0.0,
            "overall_quality": 0.0,
            "issues": []
        }
        
        # Check data completeness
        required_fields = [
            "company", "industry", "company_size", "region",
            "enrichment_data", "scoring", "scoring_details"
        ]
        
        present_fields = sum(1 for field in required_fields if field in lead_data and lead_data[field])
        quality_result["completeness_score"] = (present_fields / len(required_fields)) * 100
        
        # Check data consistency
        consistency_issues = []
        base_consistency = 100
        deduction_per_issue = 40
        
        # Check industry consistency
        if "enrichment_data" in lead_data:
            if "industry" in lead_data:
                if lead_data["industry"] != lead_data["enrichment_data"].get("industry"):
                    consistency_issues.append("Industry mismatch between lead and enrichment data")
            else:
                consistency_issues.append("Industry data only in enrichment, missing in base data")
        
        # Calculate consistency score
        quality_result["consistency_score"] = max(0, base_consistency - (len(consistency_issues) * deduction_per_issue))
        quality_result["issues"].extend(consistency_issues)
        
        # Calculate accuracy score based on data source presence
        has_website = bool(lead_data.get("website"))
        has_linkedin = bool(lead_data.get("linkedin"))
        has_enrichment = bool(lead_data.get("enrichment_data"))
        
        quality_result["accuracy_score"] = ((has_website + has_linkedin + has_enrichment) / 3) * 100
        
        # Calculate overall quality
        quality_result["overall_quality"] = (
            quality_result["completeness_score"] * 0.4 +
            quality_result["consistency_score"] * 0.3 +
            quality_result["accuracy_score"] * 0.3
        )
        
        return quality_result

class WorkflowValidationTool(BaseTool):
    name: str = "validate_workflow"
    description: str = """End-to-end workflow validation tool.
    Ensures proper execution and data flow between all stages of lead scoring."""
    
    def _run(self, workflow_data: Dict) -> Dict:
        validation_result = {
            "workflow_valid": True,
            "stage_validations": {},
            "data_flow_issues": [],
            "overall_confidence": 0.0
        }
        
        # Validate enrichment stage
        if "enrichment_stage" in workflow_data:
            enrichment_validator = EnrichmentValidationTool()
            enrichment_result = enrichment_validator._run(workflow_data["enrichment_stage"])
            validation_result["stage_validations"]["enrichment"] = enrichment_result
            if not enrichment_result["is_valid"]:
                validation_result["workflow_valid"] = False
                validation_result["data_flow_issues"].append(
                    "Enrichment stage validation failed"
                )
        else:
            validation_result["workflow_valid"] = False
            validation_result["data_flow_issues"].append("Missing enrichment stage data")
        
        # Validate signal detection stage
        if "signals_stage" in workflow_data:
            signal_validator = SignalValidationTool()
            signals_result = signal_validator._run(workflow_data["signals_stage"])
            validation_result["stage_validations"]["signals"] = signals_result
            if not signals_result["is_valid"]:
                validation_result["workflow_valid"] = False
                validation_result["data_flow_issues"].append(
                    "Signal detection stage validation failed"
                )
        else:
            validation_result["workflow_valid"] = False
            validation_result["data_flow_issues"].append("Missing signals stage data")
        
        # Validate scoring stage
        if "scoring_stage" in workflow_data:
            scoring_validator = ScoringValidationTool()
            scoring_result = scoring_validator._run(workflow_data["scoring_stage"])
            validation_result["stage_validations"]["scoring"] = scoring_result
            if not scoring_result["is_valid"]:
                validation_result["workflow_valid"] = False
                validation_result["data_flow_issues"].append(
                    "Scoring stage validation failed"
                )
        else:
            validation_result["workflow_valid"] = False
            validation_result["data_flow_issues"].append("Missing scoring stage data")
        
        # Validate data consistency across stages
        if all(stage in workflow_data for stage in ["enrichment_stage", "signals_stage", "scoring_stage"]):
            # Check if enrichment data is properly used in signal detection
            if "company_challenges" in workflow_data["enrichment_stage"]:
                challenges = workflow_data["enrichment_stage"]["company_challenges"]
                signals = workflow_data["signals_stage"].get("detected_signals", [])
                if not any(s.get("type") == "challenge_signal" for s in signals):
                    validation_result["data_flow_issues"].append(
                        "Company challenges not reflected in signals"
                    )
            
            # Check if signals are properly reflected in scoring
            if "detected_signals" in workflow_data["signals_stage"]:
                signal_count = len(workflow_data["signals_stage"]["detected_signals"])
                if "signal_match_score" in workflow_data["scoring_stage"].get("scoring", {}):
                    if signal_count == 0 and workflow_data["scoring_stage"]["scoring"]["signal_match_score"] > 0:
                        validation_result["data_flow_issues"].append(
                            "Signal match score > 0 with no detected signals"
                        )
        
        # Calculate overall confidence
        stage_confidences = []
        if "enrichment" in validation_result["stage_validations"]:
            stage_confidences.append(
                validation_result["stage_validations"]["enrichment"]["confidence_score"]
            )
        if "signals" in validation_result["stage_validations"]:
            stage_confidences.append(
                validation_result["stage_validations"]["signals"]["overall_confidence"] * 100
            )
        if "scoring" in validation_result["stage_validations"]:
            stage_confidences.append(
                validation_result["stage_validations"]["scoring"]["confidence_score"]
            )
        
        if stage_confidences:
            validation_result["overall_confidence"] = sum(stage_confidences) / len(stage_confidences)
        
        # Add error impact assessment
        if validation_result["data_flow_issues"]:
            validation_result["error_impact"] = {
                "severity": "high" if len(validation_result["data_flow_issues"]) > 2 else "medium",
                "affected_stages": [issue.split()[0].lower() for issue in validation_result["data_flow_issues"]],
                "recommended_actions": [
                    f"Fix {issue.lower()}" for issue in validation_result["data_flow_issues"]
                ]
            }
        
        return validation_result 