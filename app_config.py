import os
from dotenv import load_dotenv

load_dotenv()

# Application (client) ID of app registration
CLIENT_ID = os.getenv("CLIENT_ID")
# Application's generated client secret: never check this into source control!
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
# Make sure these values are correct
AUTHORITY = f"https://login.microsoftonline.com/{os.getenv('TENANT_ID', 'common')}"

TENANT_ID = os.getenv("TENANT_ID")  # Directory (tenant) ID from Azure portal

SCOPE = ["User.Read"]  # Required permissions
REDIRECT_URI = "http://localhost:8501"  # Your Streamlit app URL
