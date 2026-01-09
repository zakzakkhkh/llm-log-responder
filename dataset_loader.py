"""
Dataset Loader for Evaluation
Loads public log datasets in CSV/JSON format for evaluation
"""

import csv
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

def load_dataset_csv(file_path: str) -> List[Dict]:
    """
    Load dataset from CSV file
    Expected format: log_line,is_anomaly,timestamp (optional columns)
    Returns list of dictionaries with log_line, is_anomaly, timestamp
    """
    logs = []
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            log_entry = {
                'log_line': row.get('log_line', '').strip(),
                'is_anomaly': int(row.get('is_anomaly', 0)) if row.get('is_anomaly', '0').isdigit() else 0,
                'timestamp': row.get('timestamp', datetime.now().isoformat())
            }
            
            if log_entry['log_line']:  # Skip empty lines
                logs.append(log_entry)
    
    return logs

def load_dataset_json(file_path: str) -> List[Dict]:
    """
    Load dataset from JSON file
    Expected format: list of objects with log_line, is_anomaly, timestamp
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle both list of dicts and dict with 'logs' key
    if isinstance(data, list):
        logs = data
    elif isinstance(data, dict) and 'logs' in data:
        logs = data['logs']
    else:
        raise ValueError("JSON format not recognized. Expected list or dict with 'logs' key.")
    
    # Normalize format
    normalized_logs = []
    for entry in logs:
        if isinstance(entry, str):
            # If it's just a string, treat as normal log
            normalized_logs.append({
                'log_line': entry,
                'is_anomaly': 0,
                'timestamp': datetime.now().isoformat()
            })
        elif isinstance(entry, dict):
            normalized_logs.append({
                'log_line': entry.get('log_line', entry.get('log', '')),
                'is_anomaly': int(entry.get('is_anomaly', entry.get('anomaly', 0))),
                'timestamp': entry.get('timestamp', datetime.now().isoformat())
            })
    
    return normalized_logs

def load_dataset(file_path: str) -> List[Dict]:
    """
    Load dataset from file (auto-detect format)
    Supports CSV and JSON formats
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found: {file_path}")
    
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.csv':
        return load_dataset_csv(file_path)
    elif file_ext == '.json':
        return load_dataset_json(file_path)
    else:
        # Try CSV first, then JSON
        try:
            return load_dataset_csv(file_path)
        except:
            return load_dataset_json(file_path)

def generate_sample_dataset(output_file: str = "test_datasets/sample_logs.csv", num_logs: int = 80):
    """
    Generate synthetic test dataset with known anomalies
    Creates CSV file with log entries and ground truth labels
    """
    import random
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    
    # Sample log templates
    normal_logs = [
        "2025-01-15 10:30:00 INFO: Request processed successfully",
        "2025-01-15 10:30:05 INFO: User authentication successful",
        "2025-01-15 10:30:10 INFO: Database query completed in 45ms",
        "2025-01-15 10:30:15 INFO: Cache hit for key user_12345",
        "2025-01-15 10:30:20 INFO: API endpoint /api/health responded with 200",
        "2025-01-15 10:30:25 INFO: Session created for user admin",
        "2025-01-15 10:30:30 INFO: File uploaded successfully: document.pdf",
        "2025-01-15 10:30:35 INFO: Background job completed: backup_20250115",
    ]
    
    anomaly_logs = [
        "2025-01-15 10:35:00 ERROR: Apache failed to start. Port 80 is in use.",
        "2025-01-15 10:35:05 CRITICAL: Database connection timeout after 30 seconds",
        "2025-01-15 10:35:10 ERROR: Failed to connect to Redis server at 127.0.0.1:6379",
        "2025-01-15 10:35:15 ERROR: Permission denied: cannot write to /var/log/app.log",
        "2025-01-15 10:35:20 CRITICAL: Disk space below 5% threshold on /var",
        "2025-01-15 10:35:25 ERROR: Service nginx failed to restart",
        "2025-01-15 10:35:30 ERROR: Connection refused: unable to reach database server",
        "2025-01-15 10:35:35 CRITICAL: Memory usage exceeded 95% threshold",
        "2025-01-15 10:35:40 ERROR: SSL certificate expired for domain example.com",
        "2025-01-15 10:35:45 ERROR: Failed to authenticate user: invalid credentials",
    ]
    
    logs = []
    base_time = datetime(2025, 1, 15, 10, 30, 0)
    
    # Generate mix of normal and anomalous logs
    anomaly_ratio = 0.3  # 30% anomalies
    num_anomalies = int(num_logs * anomaly_ratio)
    num_normal = num_logs - num_anomalies
    
    # Add normal logs
    for i in range(num_normal):
        log_template = random.choice(normal_logs)
        timestamp = base_time.replace(second=base_time.second + i * 5)
        logs.append({
            'log_line': log_template,
            'is_anomaly': 0,
            'timestamp': timestamp.isoformat()
        })
    
    # Add anomaly logs
    for i in range(num_anomalies):
        log_template = random.choice(anomaly_logs)
        timestamp = base_time.replace(second=base_time.second + (num_normal + i) * 5)
        logs.append({
            'log_line': log_template,
            'is_anomaly': 1,
            'timestamp': timestamp.isoformat()
        })
    
    # Shuffle to mix normal and anomalies
    random.shuffle(logs)
    
    # Write to CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['log_line', 'is_anomaly', 'timestamp'])
        writer.writeheader()
        writer.writerows(logs)
    
    print(f"Generated sample dataset: {output_file}")
    print(f"  Total logs: {num_logs}")
    print(f"  Normal logs: {num_normal}")
    print(f"  Anomaly logs: {num_anomalies}")
    
    return output_file

if __name__ == "__main__":
    # Generate sample dataset for testing
    generate_sample_dataset()
