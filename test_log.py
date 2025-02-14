import pytest
from datetime import datetime, timedelta
from log import ModelLogger
import json
import shutil
import streamlit as st
import pandas as pd
import numpy as np


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary directory for log files"""
    log_dir = tmp_path / "test_logs"
    log_dir.mkdir()
    yield log_dir
    shutil.rmtree(log_dir)


@pytest.fixture
def logger(tmp_path):
    """Create a logger instance with temporary directory"""
    return ModelLogger(log_dir=tmp_path)


@pytest.fixture
def sample_settings():
    """Create sample settings for testing"""
    return {
        "valuation_date": datetime(2024, 1, 1),
        "product_groups": ["test_product"],
        "projection_period": 10,
        "assumption_table_url": "s3://test/assumptions.xlsx",
        "model_point_files_url": "s3://test/model_points/",
    }


@pytest.fixture
def sample_log_entry():
    """Create a sample log entry for testing"""
    return {
        "run_timestamp": "2024-01-01T12:00:00",
        "user": "test_user",
        "inputs": {
            "assumption_table": "s3://test/assumptions.xlsx",
            "model_point_files": "s3://test/model_points/",
            "valuation_date": "2024-01-01T00:00:00",
            "projection_period": 10,
            "product_groups": ["test_product"],
        },
        "execution_details": {
            "start_time": "2024-01-01T12:00:00",
            "end_time": "2024-01-01T12:01:00",
            "duration_seconds": 60,
            "status": "success",
        },
    }


class TestModelLogger:
    """Test ModelLogger class"""

    def test_init(self, tmp_path):
        """Test logger initialization"""
        logger = ModelLogger(log_dir=tmp_path)
        assert logger.log_dir == tmp_path
        assert logger.log_dir.exists()
        assert isinstance(logger.run_history, list)

    def test_create_run_log(self, logger, sample_settings):
        """Test creating a run log entry"""
        start_time = datetime(2024, 1, 1, 12, 0)
        end_time = start_time + timedelta(minutes=1)

        log_entry = logger.create_run_log(
            settings=sample_settings,
            start_time=start_time,
            end_time=end_time,
            status="success",
            output_location="s3://test/output.xlsx",
        )

        assert log_entry["run_timestamp"] == start_time.isoformat()
        assert log_entry["execution_details"]["duration_seconds"] == 60
        assert log_entry["execution_details"]["status"] == "success"
        assert log_entry["output_location"] == "s3://test/output.xlsx"
        assert log_entry["inputs"]["product_groups"] == ["test_product"]

    def test_add_log_entry(self, logger, sample_log_entry):
        """Test adding a log entry"""
        logger.add_log_entry(sample_log_entry)

        assert len(logger.run_history) == 1
        assert logger.run_history[0] == sample_log_entry

        # Verify file was created
        log_files = list(logger.log_dir.glob("*.json"))
        assert len(log_files) == 1

        # Verify file contents
        with open(log_files[0], "r") as f:
            saved_entry = json.load(f)
            assert saved_entry == sample_log_entry

    def test_load_history(self, tmp_path):
        """Test loading history from files"""
        # Create test log files
        test_entries = [
            {
                "run_timestamp": "2024-01-01T12:00:00",
                "execution_details": {"status": "success"},
            },
            {
                "run_timestamp": "2024-01-01T13:00:00",
                "execution_details": {"status": "error"},
            },
        ]

        for entry in test_entries:
            timestamp = datetime.fromisoformat(entry["run_timestamp"])
            with open(
                tmp_path / f"run_log_{timestamp.strftime('%Y%m%d_%H%M%S')}.json",
                "w",
            ) as f:
                json.dump(entry, f)

        logger = ModelLogger(log_dir=tmp_path)
        assert len(logger.run_history) == 2
        assert all(entry in logger.run_history for entry in test_entries)

    def test_get_run_history(self, logger, sample_log_entry):
        """Test retrieving run history"""
        # Add multiple entries
        for i in range(5):
            entry = sample_log_entry.copy()
            entry["run_timestamp"] = f"2024-01-01T{12+i}:00:00"
            logger.add_log_entry(entry)

        # Test without limit
        history = logger.get_run_history()
        assert len(history) == 5

        # Test with limit
        limited_history = logger.get_run_history(limit=3)
        assert len(limited_history) == 3

    def test_format_duration(self, logger):
        """Test duration formatting"""
        test_cases = [
            (30, "30.0 seconds"),
            (90, "1m 30s"),
            (3600, "1h 0m 0s"),
            (3661, "1h 1m 1s"),
            (0, "0.0 seconds"),
        ]

        for seconds, expected in test_cases:
            assert logger.format_duration(seconds) == expected

    def test_display_run_history(self, logger, sample_log_entry, monkeypatch):
        """Test displaying run history"""
        # Mock streamlit components
        mock_expander = type(
            "MockExpander",
            (),
            {"__enter__": lambda x: None, "__exit__": lambda x, y, z, w: None},
        )

        mock_column = type(
            "MockColumn",
            (),
            {"__enter__": lambda x: None, "__exit__": lambda x, y, z, w: None},
        )

        monkeypatch.setattr(st, "sidebar", mock_expander())
        monkeypatch.setattr(st, "subheader", lambda x: None)
        monkeypatch.setattr(st, "write", lambda x: None)
        monkeypatch.setattr(st, "columns", lambda x: [mock_column(), mock_column()])
        monkeypatch.setattr(st, "expander", lambda x: mock_expander())

        # Add some entries and test display
        logger.add_log_entry(sample_log_entry)
        logger.display_run_history()
        logger.display_run_history(limit=1)

    def test_error_handling(self, logger, sample_settings):
        """Test error handling in log creation"""
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=10)

        log_entry = logger.create_run_log(
            settings=sample_settings,
            start_time=start_time,
            end_time=end_time,
            status="error",
            error_message="Test error message",
        )

        assert log_entry["execution_details"]["status"] == "error"
        assert log_entry["error_message"] == "Test error message"


def test_create_run_log(logger):
    """Test basic log creation"""
    settings = {
        "valuation_date": "2024-01-01",
        "product_groups": ["test_product"],
        "projection_period": 10,
    }

    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=1)

    log = logger.create_run_log(settings, start_time, end_time, "success")

    assert log["execution_details"]["status"] == "success"
    assert log["execution_details"]["duration_seconds"] == 60.0
    assert len(logger.run_history) == 1

    # Verify file was created
    log_files = list(logger.log_dir.glob("*.json"))
    assert len(log_files) == 1


def test_format_duration(logger):
    """Test duration formatting"""
    assert logger.format_duration(30) == "30.0 seconds"
    assert logger.format_duration(90) == "1m 30s"
    assert logger.format_duration(3600) == "1h 0m 0s"


def test_load_existing_logs(tmp_path):
    """Test loading existing log files"""
    # Create some test logs with correct structure
    test_logs = [
        {
            "run_timestamp": "2024-01-01T12:00:00",
            "execution_details": {"status": "success", "duration_seconds": 60},
            "settings": {"product_groups": ["test"]},
        },
        {
            "run_timestamp": "2024-01-01T13:00:00",
            "execution_details": {"status": "error", "duration_seconds": 30},
            "settings": {"product_groups": ["test"]},
        },
    ]

    # Save test logs to files with correct naming
    for entry in test_logs:
        timestamp = datetime.fromisoformat(entry["run_timestamp"])
        with open(
            tmp_path / f"run_log_{timestamp.strftime('%Y%m%d_%H%M%S')}.json",
            "w",
        ) as f:
            json.dump(entry, f)

    # Create new logger instance to load existing logs
    logger = ModelLogger(log_dir=tmp_path)
    assert len(logger.run_history) == 2


def test_create_run_log_duration_formatting(logger):
    settings = {
        "valuation_date": "2024-01-01",
        "product_groups": ["test"],
        "projection_period": 10,
        "assumption_table_url": "s3://test/assumptions.xlsx",
        "model_point_files_url": "s3://test/model_points/",
    }

    # Test seconds
    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=45)
    log_entry = logger.create_run_log(settings, start_time, end_time, "success")
    assert log_entry["execution_details"]["duration_seconds"] == 45.0

    # Test minutes and seconds
    end_time = start_time + timedelta(minutes=2, seconds=30)
    log_entry = logger.create_run_log(settings, start_time, end_time, "success")
    assert log_entry["execution_details"]["duration_seconds"] == 150.0

    # Test hours, minutes, and seconds
    end_time = start_time + timedelta(hours=1, minutes=30, seconds=15)
    log_entry = logger.create_run_log(settings, start_time, end_time, "success")
    assert log_entry["execution_details"]["duration_seconds"] == 5415.0


def test_add_log_entry(logger):
    """Test adding log entries to run history"""
    log_entry = {
        "run_timestamp": "2024-01-01T12:00:00",
        "execution_details": {"status": "success", "duration_seconds": 10.0},
    }

    logger.add_log_entry(log_entry)
    assert len(logger.run_history) == 1
    assert logger.run_history[0] == log_entry

    # Verify file was created
    log_files = list(logger.log_dir.glob("*.json"))
    assert len(log_files) == 1

    # Verify file contents
    with open(log_files[0], "r") as f:
        saved_entry = json.load(f)
        assert saved_entry == log_entry


def test_load_history(logger, temp_log_dir):
    """Test loading history from files"""
    # Create test log files with correct structure
    test_entries = [
        {
            "run_timestamp": "2024-01-01T12:00:00",
            "execution_details": {
                "status": "success",
                "duration_seconds": 10.0,
            },
        },
        {
            "run_timestamp": "2024-01-01T13:00:00",
            "execution_details": {"status": "error", "duration_seconds": 5.0},
        },
    ]

    # Save files with correct naming
    for entry in test_entries:
        timestamp = datetime.fromisoformat(entry["run_timestamp"])
        with open(
            temp_log_dir / f"run_log_{timestamp.strftime('%Y%m%d_%H%M%S')}.json",
            "w",
        ) as f:
            json.dump(entry, f)

    # Create new logger and load history
    logger = ModelLogger(log_dir=temp_log_dir)
    assert len(logger.run_history) == 2
    assert all(entry in logger.run_history for entry in test_entries)


def test_create_run_log_with_duration(logger):
    """Test creating run log with duration calculation"""
    settings = {
        "valuation_date": datetime.now(),
        "product_groups": ["test"],
        "projection_period": 10,
        "assumption_table": "s3://test/assumptions.xlsx",
        "model_point_files": "s3://test/model_points/",
    }

    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=2, seconds=30)

    log_entry = logger.create_run_log(settings, start_time, end_time, "success")

    assert "execution_details" in log_entry
    assert "duration_seconds" in log_entry["execution_details"]
    assert log_entry["execution_details"]["duration_seconds"] == 150.0  # 2m30s = 150 seconds


def test_create_run_log_with_non_serializable(logger):
    """Test creating run log with non-serializable objects"""
    settings = {
        "valuation_date": datetime.now(),
        "product_groups": ["test"],
        "projection_period": 10,
        "dataframe": pd.DataFrame({"test": [1, 2, 3]}),
        "numpy_array": np.array([1, 2, 3]),
    }

    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=1)

    # This should not raise any JSON serialization errors
    log_entry = logger.create_run_log(settings, start_time, end_time, "success")

    # Verify the log was created and can be serialized
    assert log_entry["execution_details"]["status"] == "success"

    # Test that we can serialize the log entry
    json_str = json.dumps(log_entry)
    assert isinstance(json_str, str)

    # Verify the log file was created and can be read
    log_files = list(logger.log_dir.glob("*.json"))
    assert len(log_files) == 1

    with open(log_files[0], "r") as f:
        loaded_log = json.load(f)
        assert loaded_log["execution_details"]["status"] == "success"
