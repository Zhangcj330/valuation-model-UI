import json
from pathlib import Path
import datetime
import os
import streamlit as st
import boto3
from dotenv import load_dotenv

class ModelLogger:
    def __init__(self, log_dir="model_run_logs"):
        """Initialize ModelLogger with log directory"""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        load_dotenv()
        self.s3_bucket = os.getenv('S3_LOG_BUCKET')
        self.s3_prefix = os.getenv('S3_LOG_PREFIX', 'model_logs/')
        self.s3_client = boto3.client('s3')
    
    def create_run_log(self, settings, start_time, end_time, status, output_location=None, error_message=None):
        """Create a log entry for the model run"""
        duration = (end_time - start_time).total_seconds()
        
        log_entry = {
            "run_timestamp": start_time.isoformat(),
            "user": os.getenv('USER', 'unknown'),
            "inputs": {
                "assumption_table": settings["assumption_table_url"],
                "model_point_files": settings["model_point_files_url"],
                "valuation_date": settings["valuation_date"].isoformat(),
                "projection_period": settings["projection_period"],
                "product_groups": settings["product_groups"]
            },
            "execution_details": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "status": status
            },
            "output_location": output_location,
            "error_message": error_message
        }
        
        # Save log to local file
        log_file = self.log_dir / f"run_log_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, "w") as f:
            json.dump(log_entry, f, indent=4)
        
        # Upload log to S3
        if self.s3_bucket:
            try:
                s3_key = f"{self.s3_prefix}run_log_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
                self.s3_client.upload_file(
                    str(log_file),
                    self.s3_bucket,
                    s3_key
                )
            except Exception as e:
                print(f"Failed to upload log to S3: {str(e)}")
        
        return log_entry
    
    def get_run_history(self, limit=None):
        """Retrieve run history, optionally limited to recent runs"""
        log_files = sorted(self.log_dir.glob("*.json"), reverse=True)
        if limit:
            log_files = log_files[:limit]
            
        history = []
        for log_file in log_files:
            with open(log_file, "r") as f:
                history.append(json.load(f))
        return history
    
    def display_run_history(self, limit=None):
        """Display run history in Streamlit sidebar"""
        history = self.get_run_history(limit)
        
        with st.sidebar:
            st.subheader("Model Run History")
            
            if not history:
                st.write("No run history available")
                return

            for log_entry in history:
                with st.container():
                    # Use smaller text and more compact layout for sidebar
                    st.markdown(f"**{log_entry['run_timestamp']}**")
                    status_color = "🟢" if log_entry['execution_details']['status'] == 'success' else "🔴"
                    st.write(f"{status_color} {log_entry['execution_details']['status']}")
                    
                    with st.expander("View Details"):
                        st.write("**Settings:**")
                        st.json(log_entry['inputs'])
                        
                        if log_entry.get('output_location'):
                            st.write(f"**Output:** {log_entry['output_location']}")
                        
                        if log_entry.get('error_message'):
                            st.error(f"Error: {log_entry['error_message']}")
                    
                    st.markdown("---")  # Separator between entries
    
    def clear_old_logs(self, days_to_keep=30):
        """Clear logs older than specified days"""
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
        for log_file in self.log_dir.glob("*.json"):
            file_date = datetime.datetime.strptime(
                log_file.stem.split("_")[2], 
                "%Y%m%d"
            )
            if file_date < cutoff_date:
                log_file.unlink()