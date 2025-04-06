#!/usr/bin/env python
import os
from typing import List, Dict, Optional
from .crew import LeadScoringCrew
from . import database

def process_leads(user_id: str, batch_size: int = 5) -> List[Dict]:
    """
    Process a batch of leads using the lead scoring crew
    """
    serper_api_key = os.getenv('SERPER_API_KEY')
    if not serper_api_key:
        raise ValueError("SERPER_API_KEY environment variable is required")

    crew = LeadScoringCrew(serper_api_key=serper_api_key)
    return crew.process_leads(user_id=user_id, batch_size=batch_size)

def process_single_lead(lead_id: str, user_id: str) -> Dict:
    """
    Process a single lead using the lead scoring crew
    """
    serper_api_key = os.getenv('SERPER_API_KEY')
    if not serper_api_key:
        raise ValueError("SERPER_API_KEY environment variable is required")

    crew = LeadScoringCrew(serper_api_key=serper_api_key)
    return crew.process_single_lead(lead_id=lead_id, user_id=user_id)

def save_user_preferences(
    user_id: str,
    selected_signals: List[str],
    brand_voice: str,
    target_audience: str,
    core_problem: Optional[str] = None,
    solution_summary: Optional[str] = None,
    differentiators: Optional[List[str]] = None,
    icp_industry: Optional[str] = None,
    icp_company_size: Optional[str] = None,
    icp_region: Optional[str] = None,
    icp_job_title: Optional[str] = None
) -> Dict:
    """
    Save or update user preferences for lead scoring
    """
    return database.save_user_preferences(
        user_id=user_id,
        selected_signals=selected_signals,
        brand_voice=brand_voice,
        target_audience=target_audience,
        core_problem=core_problem,
        solution_summary=solution_summary,
        differentiators=differentiators,
        icp_industry=icp_industry,
        icp_company_size=icp_company_size,
        icp_region=icp_region,
        icp_job_title=icp_job_title
    )

def get_user_preferences(user_id: str) -> Dict:
    """
    Get user preferences for lead scoring
    """
    return database.get_user_preferences(user_id)

def get_lead_scores(user_id: str) -> List[Dict]:
    """
    Get all scored leads for a user
    """
    return database.get_leads_for_user(user_id)
