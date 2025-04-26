import os
import sys
import uvicorn
from dotenv import load_dotenv
import sqlalchemy
import psycopg2
import socket
from urllib.parse import urlparse

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

# --- Direct Socket Connection Test ---
db_url = os.getenv("DATABASE_URL")
if db_url:
    print("\n--- Attempting direct socket connection test ---")
    try:
        # --- Test Google First ---
        print("Attempting to resolve google.com...")
        google_ip = socket.gethostbyname("google.com")
        print(f"Resolved google.com to IP: {google_ip}")
        # --- End Google Test ---

        parsed = urlparse(db_url)
        hostname = parsed.hostname
        port = parsed.port or 5432 # Default PG port if not specified
        if hostname:
            print(f"Attempting to resolve and connect to {hostname}:{port}...")
            # Attempt DNS resolution
            ip_address = socket.gethostbyname(hostname)
            print(f"Resolved {hostname} to IP: {ip_address}")
            # Attempt connection
            with socket.create_connection((hostname, port), timeout=5) as sock:
                print(f"Direct socket connection test to {hostname}:{port} SUCCEEDED.")
        else:
            print("Could not parse hostname from DATABASE_URL.")
    except socket.gaierror as e: # Specifically catch DNS errors
        print(f"Direct socket connection test FAILED (DNS Resolution Error - socket.gaierror): {e}")
    except socket.error as e:
        print(f"Direct socket connection test FAILED (Socket Connection Error): {e}")
    except Exception as e:
        print(f"Direct socket connection test FAILED (Other Error): {e}")
    print("--- End direct socket connection test ---\n")
else:
    print("DATABASE_URL not found in environment, skipping direct socket test.")
# --- End Test ---

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
            reload=False, # <-- Disable reloader for testing
        )
    except Exception as e:
        print(f"\nError starting server: {e}")
        # Check for the unified DATABASE_URL in the root .env
        if 'DATABASE_URL' not in os.environ:
            print("\nMake sure DATABASE_URL is set in your root .env file or environment variables.") 