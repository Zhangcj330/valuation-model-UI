# Enterprise Valuation Model

[![CI Pipeline](https://github.com/yourusername/enterprise-valuation-model/actions/workflows/ci.yml/badge.svg)]
[![codecov](https://codecov.io/gh/yourusername/enterprise-valuation-model/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/enterprise-valuation-model)

A Streamlit-based web application for running enterprise valuation models. This application allows users to configure model settings, process multiple products, and view results through an interactive interface.

## Features

- Microsoft authentication
- Supports both SharePoint and S3 storage backends
- Single and batch model execution
- MPF data validation
- Run history tracking

## Setup Instructions

- Python 3.8 or higher
- AWS account with S3 access
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Zhangcj330/valuation-model-UI.git
cd valuation-model-UI
```
2. Create and activate a virtual environment:

Windows
```
python -m venv venv
.\venv\Scripts\activate
```

Linux/Mac
```
python3 -m venv venv
source venv/bin/activate
```
3. Install required packages:
```
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the root directory with the following credentials:

```
# Microsoft Authentication
CLIENT_ID=your_microsoft_app_client_id
CLIENT_SECRET=your_microsoft_app_client_secret
TENANT_ID=your_tenant_id

# AWS S3 Configuration (if using S3 storage)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=your_aws_region
```

#### Configuration Reference

- `CLIENT_ID`: Microsoft Azure application client ID
- `CLIENT_SECRET`: Microsoft Azure application client secret
- `TENANT_ID`: Microsoft tenant ID for your organization


- `AWS_ACCESS_KEY_ID`: AWS access key with permissions to S3
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key
- `AWS_REGION`: AWS region (e.g., us-east-1)

### 4. Run the application

```bash
streamlit run app.py
```

2. Access the application:
   - Open your web browser
   - Navigate to `http://localhost:8501`

## Usage Guide

1. Configure Settings:
   - Enter valuation date
   - Provide S3 URLs for:
     - Assumption table
     - Model files
     - Model point files
     - Output location
   - Select product groups
   - Set projection period

2. Run the Model:
   - Click "Run Valuation Model"
   - Monitor progress in real-time
   - View results in the interface
   - Access output files in S3

3. Manage Settings:
   - Save current settings for future use
   - Load previously saved settings
