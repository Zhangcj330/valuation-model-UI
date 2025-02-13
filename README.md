# Enterprise Valuation Model Server

[![CI Pipeline](https://github.com/yourusername/enterprise-valuation-model/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/enterprise-valuation-model/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/yourusername/enterprise-valuation-model/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/enterprise-valuation-model)

A Streamlit-based web application for running enterprise valuation models. This application allows users to configure model settings, process multiple products, and view results through an interactive interface.

## Features

- Interactive web interface for model configuration
- Support for multiple product groups
- S3 integration for input/output files
- Real-time progress tracking
- Result visualization
- Run history logging
- Settings management

## Prerequisites

- Python 3.8 or higher
- AWS account with S3 access
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/enterprise-valuation-model.git
cd enterprise-valuation-model
```
2. Create and activate a virtual environment:

Windows
python -m venv venv
.\venv\Scripts\activate


Linux/Mac
python3 -m venv venv
source venv/bin/activate

3. Install required packages:
```
pip install -r requirements.txt
```

## Configuration

1. Set up AWS credentials:
   - Create a `.env` file in the project root:
   ```
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   AWS_DEFAULT_REGION=your_region
   ```

   Or configure AWS CLI:
   ```bash
   aws configure
   ```

2. Prepare your S3 buckets:
   - Create buckets for:
     - Assumption tables
     - Model point files
     - Model files
     - Output results

## File Structure Requirements

1. Assumption Table Excel file should contain the following sheets:
   - lapse
   - CPI
   - prem expenses
   - fixed expenses
   - commissions
   - discount curve
   - mortality
   - trauma
   - TPD
   - prem_rate_level
   - prem_rate_stepped
   - RA
   - RI_prem_rate_level
   - RI_prem_rate_stepped

2. Model point files should be Excel files named according to product groups

## Running the Application

1. Start the Streamlit server:
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


### Project Structure
```
enterprise-valuation-model/
├── app.py                 # Main Streamlit application
├── model_utils.py         # Model processing utilities
├── settings_utils.py      # Settings management
├── s3_utils.py           # S3 interaction utilities
├── log.py                # Logging functionality
├── tests/                # Test files
├── requirements.txt      # Package dependencies
└── README.md            # This file
```
