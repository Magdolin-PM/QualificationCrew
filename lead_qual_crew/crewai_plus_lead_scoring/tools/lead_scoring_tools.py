from crewai.tools.base_tool import BaseTool
from typing import Dict, List
# Remove unused database import if tools don't interact with DB
# from .. import database


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
        # NOTE: This tool references the removed validation tools internally.
        # Its implementation needs significant refactoring or removal 
        # if it's intended to be used in the future.
        # Keeping the definition for now, but commenting out problematic parts.
        
        validation_result = {
            "workflow_valid": True,
            "stage_validations": {},
            "data_flow_issues": [],
            "overall_confidence": 0.0
        }
        
        # --- Needs Refactoring --- 
        # Cannot call removed tools directly.
        # Need to adapt logic based on available Pydantic outputs or other checks.
        
        # Example: Check if expected Pydantic outputs exist
        if "enrichment_output" not in workflow_data: # Assuming key name
             validation_result["workflow_valid"] = False
             validation_result["data_flow_issues"].append("Missing enrichment output")
        # else: # Check type if needed
        #    if not isinstance(workflow_data["enrichment_output"], EnrichmentOutput): # Need import
        #         validation_result["workflow_valid"] = False
        #         validation_result["data_flow_issues"].append("Invalid enrichment output type")
                 
        if "validation_output" not in workflow_data: # Assuming key name for validator output
             validation_result["workflow_valid"] = False
             validation_result["data_flow_issues"].append("Missing signal validation output")
             
        if "scoring_output" not in workflow_data: # Assuming key name for final score
             validation_result["workflow_valid"] = False
             validation_result["data_flow_issues"].append("Missing scoring output")
        # --- End Needs Refactoring --- 

        # Calculate overall confidence (Placeholder logic)
        # ... needs logic based on actual validation results ...
        
        # Add error impact assessment (Placeholder logic)
        # ... needs logic based on actual issues ...

        return validation_result 