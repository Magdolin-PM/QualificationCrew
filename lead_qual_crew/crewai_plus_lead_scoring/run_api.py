import os
import sys
import uvicorn
from dotenv import load_dotenv

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
# # Load environment variables
# dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
# if os.path.exists(dotenv_path):
#     load_dotenv(dotenv_path=dotenv_path)
#     print(f"Loaded environment variables from {dotenv_path}")
# else:
#     parent_dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
#     if os.path.exists(parent_dotenv_path):
#         load_dotenv(dotenv_path=parent_dotenv_path)
#         print(f"Loaded environment variables from parent directory: {parent_dotenv_path}")
# ---

# --- Remove Old Path Setup ---
# # Add current directory to path if not already there
# current_dir = os.path.dirname(os.path.abspath(__file__))
# if current_dir not in sys.path:
#     sys.path.insert(0, current_dir)
# ---

# Run the API server
if __name__ == "__main__":
    # Change directory to project root so uvicorn finds the module
    os.chdir(project_root)
    print(f"Changed directory to: {os.getcwd()}")
    print("Starting API server on http://0.0.0.0:8000...")
    
    # Define the correct application module path relative to the project root
    app_module = "lead_qual_crew.crewai_plus_lead_scoring.api:app"
    print(f"Running Uvicorn with app: {app_module}")
    
    try:
        # Run uvicorn, specifying the correct app module
        uvicorn.run(
            app_module, 
            host="0.0.0.0", 
            port=8000, 
            reload=True, 
        )
    except Exception as e:
        print(f"\nError starting server: {e}")
        # Check for the unified DATABASE_URL in the root .env
        if 'DATABASE_URL' not in os.environ:
            print("\nMake sure DATABASE_URL is set in your root .env file or environment variables.") 