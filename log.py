import json
from pathlib import Path
import datetime
import os
import streamlit as st

class ModelLogger:
    def __init__(self, log_dir="model_run_logs"):
        """Initialize ModelLogger with log directory"""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
    
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
        
        # Save log to file
        log_file = self.log_dir / f"run_log_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, "w") as f:
            json.dump(log_entry, f, indent=4)
        
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
    
    def display_run_history(self, limit=10):
        """Display run history in Streamlit"""
        log_files = sorted(self.log_dir.glob("*.json"), reverse=True)
        if not log_files:
            st.info("No previous runs found")
            return
        
        st.subheader("Run History")
        for log_file in list(log_files)[:limit]:
            with open(log_file, "r") as f:
                log_entry = json.load(f)
                
            with st.expander(f"Run at {log_entry['run_timestamp']}"):
                # Display summary information
                col1, col2 = st.columns(2)
                with col1:
                    st.write("Status:", log_entry["execution_details"]["status"])
                    st.write("Duration:", f"{log_entry['execution_details']['duration_seconds']:.1f} seconds")
                with col2:
                    st.write("Products:", ", ".join(log_entry["inputs"]["product_groups"]))
                    st.write("User:", log_entry["user"])
                
                # Show full details in expandable section
                if st.checkbox("Show full details", key=f"details_{log_entry['run_timestamp']}"):
                    st.json(log_entry)
    
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