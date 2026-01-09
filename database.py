"""
Database module for LLM Log Responder
Handles SQLite database operations for incidents, actions, and logs
Simplified schema matching PDF architecture
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, List

DB_FILE = "incidents.db"

def init_db():
    """Initialize the SQLite database with required tables"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Incidents table - stores detected anomalies
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at TIMESTAMP NOT NULL,
            resolved_at TIMESTAMP,
            log_line TEXT NOT NULL,
            summary TEXT,
            status TEXT DEFAULT 'open' CHECK(status IN ('open', 'resolved', 'escalated'))
        )
    ''')
    
    # Actions table - stores executed remediation actions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS actions (
            action_id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER,
            action_name TEXT NOT NULL,
            executed_at TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'executed', 'approved', 'rejected', 'failed')),
            approved_by TEXT,
            result_message TEXT,
            FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
        )
    ''')
    
    # Logs table - stores log entries (optional, for template mining)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL,
            log_line TEXT NOT NULL,
            is_anomaly INTEGER DEFAULT 0,
            template_id INTEGER
        )
    ''')
    
    # Templates table - stores log templates (for Phase 4)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_pattern TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            frequency INTEGER DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"[DATABASE] Initialized database: {DB_FILE}")

def record_incident(log_line: str, summary: Optional[str] = None) -> int:
    """
    Record a detected incident/anomaly
    Returns the incident_id
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO incidents (detected_at, log_line, summary, status)
        VALUES (?, ?, ?, 'open')
    ''', (datetime.now().isoformat(), log_line, summary))
    
    incident_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    print(f"[DATABASE] Recorded incident ID: {incident_id}")
    return incident_id

def record_action(incident_id: int, action_name: str, status: str = 'executed', 
                  approved_by: Optional[str] = None, result_message: Optional[str] = None) -> int:
    """
    Record an executed action
    Returns the action_id
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO actions (incident_id, action_name, executed_at, status, approved_by, result_message)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (incident_id, action_name, datetime.now().isoformat(), status, approved_by, result_message))
    
    action_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    print(f"[DATABASE] Recorded action ID: {action_id} - {action_name}")
    return action_id

def update_incident_resolved(incident_id: int):
    """Mark an incident as resolved"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE incidents 
        SET resolved_at = ?, status = 'resolved'
        WHERE incident_id = ?
    ''', (datetime.now().isoformat(), incident_id))
    
    conn.commit()
    conn.close()
    print(f"[DATABASE] Marked incident {incident_id} as resolved")

def get_open_incidents() -> List[Dict]:
    """Get all open incidents"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM incidents WHERE status = "open" ORDER BY detected_at DESC')
    rows = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in rows]

def get_incident_by_id(incident_id: int) -> Optional[Dict]:
    """Get a specific incident by ID"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM incidents WHERE incident_id = ?', (incident_id,))
    row = cursor.fetchone()
    
    conn.close()
    return dict(row) if row else None

def get_recent_actions(limit: int = 10) -> List[Dict]:
    """Get recent actions"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM actions 
        ORDER BY executed_at DESC 
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in rows]

def get_incidents_by_time_window(hours: int = 1) -> List[Dict]:
    """
    Get incidents within a time window (last N hours)
    Returns list of incidents detected in the specified time range
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cutoff_time = datetime.now().timestamp() - (hours * 3600)
    cutoff_iso = datetime.fromtimestamp(cutoff_time).isoformat()
    
    cursor.execute('''
        SELECT * FROM incidents 
        WHERE detected_at >= ? 
        ORDER BY detected_at DESC
    ''', (cutoff_iso,))
    rows = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in rows]

def get_errors_by_time_window(hours: int = 1) -> List[Dict]:
    """
    Get error incidents within a time window
    Filters for incidents containing ERROR/CRITICAL/Failed keywords
    """
    incidents = get_incidents_by_time_window(hours)
    error_keywords = ['ERROR', 'CRITICAL', 'Failed', 'Timeout']
    
    error_incidents = []
    for incident in incidents:
        log_line = incident.get('log_line', '')
        if any(keyword in log_line.upper() for keyword in error_keywords):
            error_incidents.append(incident)
    
    return error_incidents

def store_log_entry(log_line: str, is_anomaly: bool = False):
    """
    Store a log entry in the logs table for indexing and querying
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO logs (timestamp, log_line, is_anomaly)
        VALUES (?, ?, ?)
    ''', (datetime.now().isoformat(), log_line, 1 if is_anomaly else 0))
    
    conn.commit()
    conn.close()

def search_logs_by_pattern(pattern: str, hours: int = 24) -> List[Dict]:
    """
    Search logs by pattern (regex-like search) within time window
    Returns matching log entries
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cutoff_time = datetime.now().timestamp() - (hours * 3600)
    cutoff_iso = datetime.fromtimestamp(cutoff_time).isoformat()
    
    cursor.execute('''
        SELECT * FROM logs 
        WHERE timestamp >= ? AND log_line LIKE ?
        ORDER BY timestamp DESC
    ''', (cutoff_iso, f'%{pattern}%'))
    rows = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in rows]

if __name__ == "__main__":
    # Initialize database if running directly
    init_db()
    print("Database initialized successfully!")

