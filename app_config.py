import os
from dotenv import load_dotenv

load_dotenv()

# Application (client) ID of app registration
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")

# Authority and endpoints
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

# Required permissions for SharePoint access
SCOPE = ["User.Read", "Files.Read.All", "Sites.Read.All", "Sites.ReadWrite.All"]

# SharePoint site configuration
SHAREPOINT_SITE_NAME = os.getenv("SHAREPOINT_SITE_NAME", "").strip("/")
SHAREPOINT_SITE_ID = os.getenv("SHAREPOINT_SITE_ID")

REDIRECT_URI = "http://localhost:8501"
