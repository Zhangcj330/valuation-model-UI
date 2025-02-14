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
        self.s3_bucket = os.getenv("S3_LOG_BUCKET")
        self.s3_prefix = os.getenv("S3_LOG_PREFIX", "model_logs/")
        self.s3_client = boto3.client("s3")
        self.run_history = []  # Initialize empty run history
        self.load_history()  # Load existing history on initialization

    def create_run_log(
        self,
        settings,
        start_time,
        end_time,
        status,
        output_location=None,
        error_message=None,
    ):
        """Create a log entry for the model run"""
        duration = (end_time - start_time).total_seconds()

        log_entry = {
            "run_timestamp": start_time.isoformat(),
            "user": os.getenv("USER", "unknown"),
            "inputs": {
                "assumption_table": settings.get("assumption_table_url", ""),
                "model_point_files": settings.get("model_point_files_url", ""),
                "valuation_date": settings["valuation_date"].isoformat(),
                "projection_period": settings["projection_period"],
                "product_groups": settings["product_groups"],
            },
            "execution_details": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "status": status,
            },
        }

        if output_location:
            log_entry["output_location"] = output_location
        if error_message:
            log_entry["error_message"] = error_message

        self.add_log_entry(log_entry)
        return log_entry

    def add_log_entry(self, log_entry):
        """Add a log entry to run history and save to file"""
        self.run_history.append(log_entry)

        # Save log to local file
        timestamp = datetime.datetime.fromisoformat(
            log_entry["run_timestamp"].split("+")[0]
        )
        log_file = self.log_dir / f"run_log_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, "w") as f:
            json.dump(log_entry, f, indent=4)

        # Upload log to S3 if configured
        if self.s3_bucket:
            try:
                s3_key = f"{self.s3_prefix}run_log_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
                self.s3_client.upload_file(str(log_file), self.s3_bucket, s3_key)
            except Exception as e:
                print(f"Failed to upload log to S3: {str(e)}")

    def load_history(self):
        """Load run history from log files"""
        self.run_history = []
        log_files = sorted(self.log_dir.glob("*.json"), reverse=True)
        for log_file in log_files:
            try:
                with open(log_file, "r") as f:
                    self.run_history.append(json.load(f))
            except Exception as e:
                print(f"Error loading log file {log_file}: {str(e)}")

    def get_run_history(self, page=1, items_per_page=10):
        """Retrieve run history, optionally limited to recent runs"""
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page

        total_items = len(self.run_history)
        total_pages = (total_items + items_per_page - 1) // items_per_page

        return {
            "items": self.run_history[start_idx:end_idx],
            "total_pages": total_pages,
            "current_page": page,
            "total_items": total_items,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        }

    def format_duration(self, seconds):
        """Format duration in seconds to a readable string"""
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = int(seconds % 60)
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = int(seconds // 3600)
            remaining = seconds % 3600
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            return f"{hours}h {minutes}m {seconds}s"

    def display_run_history(self, page=1, items_per_page=10):
        """Display run history in Streamlit sidebar with pagination"""
        history_data = self.get_run_history(page, items_per_page)

        with st.sidebar:
            st.subheader("Model Run History")

            if not self.run_history:
                st.write("No run history available")
                return

            # Display history items
            for log_entry in history_data["items"]:
                try:
                    # Parse ISO format timestamp
                    timestamp = datetime.datetime.fromisoformat(
                        log_entry["run_timestamp"].replace("Z", "+00:00")
                    )
                    date_str = timestamp.strftime("%b %d, %Y")
                    time_str = timestamp.strftime("%I:%M %p")
                except (ValueError, KeyError) as e:
                    print(f"Error parsing timestamp: {e}")
                    date_str = "Unknown Date"
                    time_str = "Unknown Time"

                # Status emoji
                status_color = (
                    "🟢"
                    if log_entry["execution_details"]["status"] == "success"
                    else "🔴"
                )

                # Display header with date and status
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"🕒 {date_str} {time_str}")
                    st.write(f"👤 {log_entry.get('user', 'unknown_user')}")
                with col2:
                    st.write(
                        f"{status_color} {log_entry['execution_details']['status']}"
                    )

                with st.expander("View Details"):
                    # Format duration from seconds
                    duration_seconds = log_entry["execution_details"].get(
                        "duration_seconds"
                    )
                    duration_str = (
                        self.format_duration(duration_seconds)
                        if duration_seconds is not None
                        else "N/A"
                    )
                    st.write("**Duration:** ⏱️ " + duration_str)

                    st.write("**Settings:**")
                    st.json(log_entry["inputs"])

                    if log_entry.get("output_location"):
                        st.write(f"**Output:** 📁 {log_entry['output_location']}")

                    if log_entry.get("error_message"):
                        st.error(f"Error: {log_entry['error_message']}")

                st.markdown("<hr style='margin: 10px 0px'>", unsafe_allow_html=True)

            # Display pagination controls
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if history_data["has_previous"]:
                    st.markdown(
                        "<div style='text-align: center; padding-top: 5px'>",
                        unsafe_allow_html=True,
                    )
                    if st.button("←"):
                        st.session_state["history_page"] = page - 1
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
            with col2:
                st.markdown(
                    "<div style='text-align: center; margin-top: 24px'>Page "
                    f"{page} of {history_data['total_pages']}</div>",
                    unsafe_allow_html=True,
                )
            with col3:
                if history_data["has_next"]:
                    st.markdown(
                        "<div style='text-align: center; padding-top: 5px'>",
                        unsafe_allow_html=True,
                    )
                    if st.button("→"):
                        st.session_state["history_page"] = page + 1
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    def clear_old_logs(self, days_to_keep=30):
        """Clear logs older than specified days"""
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
        for log_file in self.log_dir.glob("*.json"):
            file_date = datetime.datetime.strptime(
                log_file.stem.split("_")[2], "%Y%m%d"
            )
            if file_date < cutoff_date:
                log_file.unlink()

    def _load_logs(self):
        """Load existing logs from directory"""
        self.run_history = []
        for log_file in sorted(self.log_dir.glob("*.json")):
            try:
                with open(log_file, "r") as f:
                    self.run_history.append(json.load(f))
            except Exception as e:
                print(f"Error loading log file {log_file}: {str(e)}")
