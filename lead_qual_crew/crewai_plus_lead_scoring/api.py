import logging
from fastapi import FastAPI, HTTPException, Body, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware  # Add CORS middleware
from fastapi.responses import HTMLResponse  # Add HTMLResponse
from uuid import UUID
import os
import sys
from dotenv import load_dotenv
from pydantic import BaseModel # Import BaseModel
from typing import List, Dict, Any # Import typing helpers
from sqlalchemy import or_ # Import or_

# --- Define Project Root and Add to Path ---
# Assuming this script is in crewAI-enterprise-lead-ql-assist/that's the one/crewai_plus_lead_scoring/
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"Added project root to sys.path: {project_root}")

# --- Load .env from Project Root ---
dotenv_path = os.path.join(project_root, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
    print(f"Loaded environment variables from root: {dotenv_path}")
else:
    print(f"Warning: Root .env file not found at {dotenv_path}")

# --- Remove Old .env Loading --- 
# # Load environment variables first
# from dotenv import load_dotenv
# dotenv_path = os.path.join(os.path.dirname(__file__), '.env') 
# if os.path.exists(dotenv_path):
#     load_dotenv(dotenv_path=dotenv_path)
#     print(f"Loaded environment variables from {dotenv_path}")
# else:
#     parent_dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
#     if os.path.exists(parent_dotenv_path):
#         load_dotenv(dotenv_path=parent_dotenv_path)
#         print(f"Loaded environment variables from parent directory: {parent_dotenv_path}")
# ---

# --- Remove Old Path Setup ---
# # Setup Python path
# current_dir = os.path.dirname(os.path.abspath(__file__))
# if current_dir not in sys.path:
#     sys.path.insert(0, current_dir)
# ---

# --- Use Relative Imports ---
from .database import get_unprocessed_lead_ids, get_lead_status_summary # Relative import
# Remove the direct import of process_lead
# from .process_lead import process_lead # Relative import
# Import the LeadScoringCrew
from .crew import LeadScoringCrew
import os # Add os import for environment variable access
# ---

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- API Key Dependency --- (Example using environment variable)
# You might want a more robust way to handle API keys in production
def get_api_key():
    key = os.getenv("SERPER_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="SERPER_API_KEY not configured")
    return key

# Create FastAPI app
app = FastAPI(
    title="CrewAI Lead Scoring API",
    description="API for managing and processing leads using CrewAI.",
    version="0.1.0"
)

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=False,  # Set to False since we're using wildcard origins
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- Pydantic Models for Request Body ---
class Contact(BaseModel):
    # Adjust fields based on the actual CSV columns from the frontend
    # Assuming at least 'email' is present for domain matching
    name: str | None = None
    email: str | None = None
    current_company: str | None = None
    # Add other potentially useful fields if available in the CSV
    # Example: position: str | None = None
    # Example: linkedin_url: str | None = None

    class Config:
        extra = 'allow' # Allow extra fields from CSV not explicitly defined

class ProcessBatchRequest(BaseModel):
    contacts_data: List[Contact] = [] # Default to empty list

# New response model for the async endpoint
class BatchStartResponse(BaseModel):
    message: str
    user_id: str
    leads_queued: int


def get_lead_by_id(lead_id: UUID):
    from .database import SessionLocal, Lead # Relative import
    db = SessionLocal()
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    db.close()
    # Return a dict of the lead
    return lead

def get_user_preferences(user_id: UUID):
    from .database import SessionLocal, UserPreferences # Relative import
    db = SessionLocal()
    user_preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    db.close()
    return user_preferences

# --- Background Task Function ---
# This function will run in the background
def run_scoring_batch_background(
    user_id_str: str, 
    lead_ids_to_process: List[UUID], 
    contacts_list_of_dicts: List[Dict],
    serper_api_key: str # API key needs to be passed explicitly
):
    """Instantiates crew and processes leads in the background."""
    logging.info(f"[Background Task] Starting processing for User ID: {user_id_str}")
    
    # Instantiate the crew inside the background task
    try:
        # Note: Consider if LeadScoringCrew instantiation itself is slow or resource-intensive.
        # If so, it might be better shared or pre-initialized, but this is simpler.
        crew = LeadScoringCrew(serper_api_key=serper_api_key)
    except Exception as e:
        logging.error(f"[Background Task] Failed to initialize LeadScoringCrew for User ID {user_id_str}: {e}", exc_info=True)
        # Cannot easily report back to user here, rely on logs.
        return # Stop processing if crew cannot be initialized
    
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        logging.error(f"[Background Task] Invalid user ID format: {user_id_str}")
        return # Stop processing if user ID is invalid

        
    processed_count = 0
    success_count = 0
    failure_count = 0
    
    for lead_id in lead_ids_to_process:
        lead_id_str = str(lead_id)
        logging.info(f"[Background Task] Processing lead {lead_id_str} for User ID {user_id_str}...")
        # Get lead data and user preferences
        lead_data = get_lead_by_id(lead_id=lead_id)
        user_preferences = get_user_preferences(user_id=user_id)
        try:
            result = crew.process_single_lead(
                lead_data=lead_data.to_dict(),
                user_preferences=user_preferences.to_dict(),
                contacts_data=contacts_list_of_dicts
            )
            processed_count += 1
            if "error" in result:
                logging.warning(f"[Background Task] Processing failed for lead {lead_id_str}: {result.get('error', 'Unknown error')}")
                failure_count += 1
            else:
                # Log success details (e.g., score) from the result dictionary
                logging.info(f"[Background Task] Processing succeeded for lead {lead_id_str}. Result keys: {list(result.keys())}, Score: {result.get('score')}")
                success_count += 1
                
        except Exception as e:
            # Catch unexpected errors during a single lead's processing in background
            logging.error(f"[Background Task] Unexpected error during processing lead {lead_id_str} for User ID {user_id_str}: {e}", exc_info=True)
            failure_count += 1 # Count unexpected errors as failures
            processed_count += 1 # It was attempted

    logging.info(f"[Background Task] Batch processing complete for User ID {user_id_str}. Processed: {processed_count}, Successful: {success_count}, Failed: {failure_count}")
    # NOTE: No return value is sent back to the original HTTP request here.
    # Further actions like DB logging of batch status or notifications would go here.

# --- API Endpoints ---
# Update the endpoint to use BackgroundTasks and return BatchStartResponse
@app.post("/users/{user_id_str}/leads/process-batch", response_model=BatchStartResponse)
def trigger_async_batch_lead_processing(
    user_id_str: str, 
    background_tasks: BackgroundTasks, # Inject BackgroundTasks
    request_data: ProcessBatchRequest = Body(default=ProcessBatchRequest(contacts_data=[])),
    serper_api_key: str = Depends(get_api_key) # Resolve API key here
):
    """
    Triggers ASYNCHRONOUS processing for up to 20 unprocessed leads for a given user.
    Immediately returns a confirmation that processing has started.
    Requires user's contacts data in the request body.
    """
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid user ID format: {user_id_str}")

    logging.info(f"Received request to process leads for User ID: {user_id}")
    
    try:
        # Fetch up to 20 leads
        lead_ids_to_process = get_unprocessed_lead_ids(user_id=user_id, limit=20)
    except Exception as e:
        logging.error(f"Database error fetching leads for User ID {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching leads from database.")

    if not lead_ids_to_process:
        logging.info(f"No unprocessed leads found for User ID: {user_id}. Nothing to queue.")
        # Return slightly different message if nothing to do
        return BatchStartResponse(
            message="No unprocessed leads found to queue.", 
            user_id=user_id_str, 
            leads_queued=0
        )

    contacts_list_of_dicts = []
    if request_data and request_data.contacts_data:
        contacts_list_of_dicts = [contact.model_dump(exclude_unset=True) for contact in request_data.contacts_data]
        logging.info(f"Received {len(contacts_list_of_dicts)} contacts in request body.")
    else:
        logging.warning(f"No contacts data received in request body for user {user_id}. Domain matching will be skipped in background task.")

    # Add the processing function to background tasks
    background_tasks.add_task(
        run_scoring_batch_background,
        user_id_str=user_id_str, # Pass needed arguments
        lead_ids_to_process=lead_ids_to_process,
        contacts_list_of_dicts=contacts_list_of_dicts,
        serper_api_key=serper_api_key 
    )

    num_leads = len(lead_ids_to_process)
    logging.info(f"Queued background processing for {num_leads} leads for User ID: {user_id}")

    # Return immediate confirmation
    return BatchStartResponse(
        message=f"Started background processing for {num_leads} leads.",
        user_id=user_id_str,
        leads_queued=num_leads
    )

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with HTML interface to test the API"""
    # Restore the original complex HTML
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CrewAI Lead Scoring API</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #2c3e50; }
            .endpoint { background: #f8f9fa; padding: 15px; margin-bottom: 15px; border-radius: 5px; }
            button { background: #3498db; color: white; border: none; padding: 8px 15px; border-radius: 3px; cursor: pointer; }
            button:hover { background: #2980b9; }
            pre { background: #f1f1f1; padding: 10px; border-radius: 4px; overflow-x: auto; }
            #response { margin-top: 20px; }
            .user-input { margin-bottom: 10px; }
            textarea { width: 90%; min-height: 100px; margin-top: 5px; }
        </style>
    </head>
    <body>
        <h1>CrewAI Lead Scoring API</h1>
        <p>API is running. Use the endpoint below to process leads synchronously.</p>
        
        <div class="endpoint">
            <h3>Process Batch Synchronously</h3>
            <div class="user-input">
                <label for="userId">User ID:</label><br>
                <input type="text" id="userId" placeholder="Enter User UUID" value="73fb447f-61cc-4ae5-bc4c-5f3a1317c2fb"> 
            </div>
            <div class="user-input">
                <label for="contactsData">Contacts Data (JSON list of objects with 'email', 'name', etc.):</label><br>
                <textarea id="contactsData">[
  {"name": "Test Contact", "email": "test@matchingdomain.com"},
  {"name": "No Match Contact", "email": "nomatch@otherdomain.net"}
]</textarea>
            </div>
            <button onclick="callSyncBatchApi()">Process Leads Synchronously</button>
        </div>
                
        <div id="response">
            <h3>Response:</h3>
            <pre id="responseContent">No response yet</pre>
        </div>
        
        <script>
            async function callSyncBatchApi() {
                document.getElementById('responseContent').innerText = 'Processing... (This may take a while)';
                const userId = document.getElementById('userId').value;
                const contactsDataRaw = document.getElementById('contactsData').value;
                let contactsDataParsed;
                
                if (!userId) {
                    document.getElementById('responseContent').innerText = 'Error: User ID is required.';
                    return;
                }
                
                try {
                    contactsDataParsed = JSON.parse(contactsDataRaw);
                } catch (e) {
                    document.getElementById('responseContent').innerText = `Error parsing Contacts Data JSON: ${e.message}`;
                    return;
                }

                const requestBody = {
                    contacts_data: contactsDataParsed
                };
                
                const endpoint = `/users/${userId}/leads/process-batch`;
                
                try {
                    const response = await fetch(endpoint, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(requestBody)
                    });
                    
                    const data = await response.json();
                    
                    if (!response.ok) {
                         document.getElementById('responseContent').innerText = `Error: ${response.status} ${response.statusText}\n${JSON.stringify(data, null, 2)}`;
                    } else {
                        document.getElementById('responseContent').innerText = JSON.stringify(data, null, 2);
                    }
                    
                } catch (error) {
                    document.getElementById('responseContent').innerText = `Network or other error: ${error.message}`;
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
    # return "Hello World!" # Comment out the simplified version

# Add a debugging endpoint
@app.get("/debug/leads")
async def debug_get_all_leads():
    """
    Debugging endpoint to check what leads exist in the database.
    """
    from .database import SessionLocal, Lead # Relative import
    
    db = SessionLocal()
    try:
        # Get all leads and basic info
        leads = db.query(
            Lead.id, 
            Lead.first_name, 
            Lead.last_name, 
            Lead.company, 
            Lead.score, 
            Lead.created_by
        ).limit(20).all()
        
        # Convert to list of dicts
        lead_list = []
        for lead in leads:
            lead_list.append({
                "id": str(lead.id),
                "name": f"{lead.first_name} {lead.last_name}",
                "company": lead.company,
                "score": lead.score,
                "created_by": str(lead.created_by) if lead.created_by else None
            })
        
        return {
            "count": len(lead_list),
            "leads": lead_list
        }
    finally:
        db.close()

# --- NEW Summary Endpoint ---
@app.get("/users/{user_id_str}/leads/summary")
async def get_user_lead_summary(user_id_str: str):
    """Fetches the count of leads grouped by priority status for a specific user."""
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid user ID format: {user_id_str}")

    logging.info(f"Fetching lead summary for User ID: {user_id}")
    
    try:
        summary = get_lead_status_summary(user_id=user_id)
        return summary
    except Exception as e:
        logging.error(f"Database error fetching lead summary for User ID {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching lead summary from database.")
# --- END NEW Summary Endpoint ---

# Expected query params:
# q: str,
# user_id: UUID,
@app.get("/api/leads/search")
async def search_leads(
    q: str,
    user_id: str
):
    
    from .database import SessionLocal, Lead # Relative import
    db = SessionLocal()
    try:
        # Validate query parameter
        if not q:
            raise HTTPException(status_code=400, detail="Query parameter 'q' is required.")
        if not user_id:
            raise HTTPException(status_code=400, detail="Query parameter 'user_id' is required.")
        try:
            user_id = UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid user ID format: {user_id}")
        leads = db.query(Lead) \
            .filter(Lead.user_id == user_id) \
            .filter(
                or_(
                    Lead.first_name.ilike(f"%{q}%"),
                    Lead.last_name.ilike(f"%{q}%"),
                    Lead.company.ilike(f"%{q}%"),
                    Lead.email.ilike(f"%{q}%")
            )
        ).all()
        return leads
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error searching leads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error searching leads.")
    finally:
        db.close()

# --- How to run ---
# You would typically run this using an ASGI server like uvicorn:
# uvicorn that\'s_the_one.crewai_plus_lead_scoring.api:app --reload --port 8000 --app-dir /path/to/crewAI-enterprise-lead-ql-assist
# Ensure you run this from the project root directory (`crewAI-enterprise-lead-ql-assist`) or adjust Python path accordingly. 