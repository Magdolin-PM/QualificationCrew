import logging
from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.middleware.cors import CORSMiddleware  # Add CORS middleware
from fastapi.responses import HTMLResponse  # Add HTMLResponse
from uuid import UUID
import os
import sys
from dotenv import load_dotenv
from pydantic import BaseModel # Import BaseModel
from typing import List, Dict, Any # Import typing helpers

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
from .database import get_unprocessed_lead_ids, get_lead_priority_summary # Relative import
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
    allow_origins=["*"],  # Allows all origins (replace with specific domains in production)
    allow_credentials=True,
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

class BatchProcessSummary(BaseModel):
    total_processed: int
    successful: int
    failed: int
    errors: List[Dict[str, str]] # List of {lead_id: ..., error: ...}

# Endpoints
@app.post("/users/{user_id_str}/leads/process-batch", response_model=BatchProcessSummary)
def trigger_sync_batch_lead_processing(
    user_id_str: str, 
    request_data: ProcessBatchRequest = Body(default=ProcessBatchRequest(contacts_data=[])),
    # Remove BackgroundTasks dependency
    serper_api_key: str = Depends(get_api_key) # Inject API key via dependency
):
    """
    Processes up to 10 unprocessed leads SYNCHRONOUSLY for a given user.
    Returns an aggregated summary of the batch processing results.
    Requires user's contacts data in the request body.
    """
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid user ID format: {user_id_str}")

    logging.info(f"Fetching unprocessed leads for User ID: {user_id}")
    
    try:
        lead_ids_to_process = get_unprocessed_lead_ids(user_id=user_id, limit=10)
    except Exception as e:
        logging.error(f"Database error fetching leads for User ID {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching leads from database.")

    if not lead_ids_to_process:
        logging.info(f"No unprocessed leads found for User ID: {user_id}")
        # Return empty summary if no leads found
        return BatchProcessSummary(total_processed=0, successful=0, failed=0, errors=[])

    contacts_list_of_dicts = []
    if request_data and request_data.contacts_data:
        contacts_list_of_dicts = [contact.model_dump(exclude_unset=True) for contact in request_data.contacts_data]
        logging.info(f"Received {len(contacts_list_of_dicts)} contacts in request body.")
    else:
        logging.warning(f"No contacts data received in request body for user {user_id}. Domain matching will be skipped.")

    # Instantiate the crew ONCE outside the loop
    try:
        crew = LeadScoringCrew(serper_api_key=serper_api_key)
    except Exception as e:
        logging.error(f"Failed to initialize LeadScoringCrew: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initialize scoring crew.")

    # Process leads synchronously
    results = []
    logging.info(f"Starting synchronous processing of {len(lead_ids_to_process)} leads for User ID: {user_id}")
    
    for lead_id in lead_ids_to_process:
        lead_id_str = str(lead_id)
        logging.info(f"Processing lead {lead_id_str}...")
        try:
            # Call process_single_lead directly
            result = crew.process_single_lead(
                lead_id=lead_id_str, 
                user_id=user_id_str,
                contacts_data=contacts_list_of_dicts
            )
            results.append(result)
            if "error" in result:
                logging.warning(f"Processing failed for lead {lead_id_str}: {result['error']}")
            else:
                logging.info(f"Processing succeeded for lead {lead_id_str}. Score: {result.get('score')}")
                
        except Exception as e:
            # Catch unexpected errors during a single lead's processing
            logging.error(f"Unexpected error during processing lead {lead_id_str}: {e}", exc_info=True)
            results.append({"error": f"Unexpected processing error: {str(e)}", "lead_id": lead_id_str})

    # Calculate summary
    successful_count = 0
    failed_count = 0
    error_list = []
    for res in results:
        if "error" in res:
            failed_count += 1
            error_list.append({"lead_id": res.get("lead_id", "Unknown"), "error": res.get("error", "Unknown")})
        else:
            successful_count += 1
            
    total_processed = len(results)
    summary = BatchProcessSummary(
        total_processed=total_processed,
        successful=successful_count,
        failed=failed_count,
        errors=error_list
    )
    
    logging.info(f"Batch processing complete for user {user_id}. Summary: {summary.model_dump()}")
    return summary

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with HTML interface to test the API"""
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
  {{"name": "Test Contact", "email": "test@matchingdomain.com"}},
  {{"name": "No Match Contact", "email": "nomatch@otherdomain.net"}}
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
        summary = get_lead_priority_summary(user_id=user_id)
        return summary
    except Exception as e:
        logging.error(f"Database error fetching lead summary for User ID {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching lead summary from database.")
# --- END NEW Summary Endpoint ---

# --- How to run ---
# You would typically run this using an ASGI server like uvicorn:
# uvicorn that\'s_the_one.crewai_plus_lead_scoring.api:app --reload --port 8000 --app-dir /path/to/crewAI-enterprise-lead-ql-assist
# Ensure you run this from the project root directory (`crewAI-enterprise-lead-ql-assist`) or adjust Python path accordingly. 