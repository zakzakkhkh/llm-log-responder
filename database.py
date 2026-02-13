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
_quiet = os.environ.get("DEMO") == "1"

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
            template_id INTEGER,
            embedding_vector BLOB,
            FOREIGN KEY (template_id) REFERENCES templates(template_id)
        )
    ''')
    
    # Lexical index table - for keyword-based search (dual-indexing)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lexical_index (
            index_id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            position INTEGER,
            FOREIGN KEY (log_id) REFERENCES logs(log_id)
        )
    ''')
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_template ON logs(template_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lexical_keyword ON lexical_index(keyword)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lexical_log ON lexical_index(log_id)')
    
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
    if not _quiet:
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
    if not _quiet:
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
    if not _quiet:
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
    if not _quiet:
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

def store_log_entry(log_line: str, is_anomaly: bool = False, template_id: Optional[int] = None, 
                    embedding_vector: Optional[bytes] = None):
    """
    Store a log entry in the logs table with dual-indexing
    Also creates lexical index entries for keyword search
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Insert log entry
    cursor.execute('''
        INSERT INTO logs (timestamp, log_line, is_anomaly, template_id, embedding_vector)
        VALUES (?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), log_line, 1 if is_anomaly else 0, template_id, embedding_vector))
    
    log_id = cursor.lastrowid
    
    # Create lexical index entries (extract keywords)
    import re
    # Extract meaningful keywords (words with 3+ characters, excluding common words)
    stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'way', 'use', 'her', 'she', 'him', 'his', 'its', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how'}
    words = re.findall(r'\b[a-zA-Z]{3,}\b', log_line.lower())
    keywords = [w for w in words if w not in stop_words]
    
    # Store keywords in lexical index
    for position, keyword in enumerate(keywords[:20]):  # Limit to 20 keywords per log
        cursor.execute('''
            INSERT INTO lexical_index (log_id, keyword, position)
            VALUES (?, ?, ?)
        ''', (log_id, keyword, position))
    
    conn.commit()
    conn.close()
    return log_id

def search_logs_by_pattern(pattern: str, hours: int = 24) -> List[Dict]:
    """
    Search logs by pattern (regex-like search) within time window
    Uses dual-indexing: lexical index for keywords, time index for temporal queries
    Returns matching log entries
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cutoff_time = datetime.now().timestamp() - (hours * 3600)
    cutoff_iso = datetime.fromtimestamp(cutoff_time).isoformat()
    
    # Use lexical index for keyword search if pattern is a single word
    import re
    if re.match(r'^\w+$', pattern):
        # Keyword-based search using lexical index (faster)
        cursor.execute('''
            SELECT DISTINCT l.* FROM logs l
            INNER JOIN lexical_index li ON l.log_id = li.log_id
            WHERE l.timestamp >= ? AND li.keyword LIKE ?
            ORDER BY l.timestamp DESC
            LIMIT 100
        ''', (cutoff_iso, f'%{pattern.lower()}%'))
    else:
        # Pattern-based search (fallback)
        cursor.execute('''
            SELECT * FROM logs 
            WHERE timestamp >= ? AND log_line LIKE ?
            ORDER BY timestamp DESC
            LIMIT 100
        ''', (cutoff_iso, f'%{pattern}%'))
    
    rows = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in rows]

def get_logs_by_template_id(template_id: int, hours: int = 24) -> List[Dict]:
    """
    Get logs by template ID within time window (template-based correlation)
    Part of dual-indexing: template index for pattern correlation
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cutoff_time = datetime.now().timestamp() - (hours * 3600)
    cutoff_iso = datetime.fromtimestamp(cutoff_time).isoformat()
    
    cursor.execute('''
        SELECT * FROM logs 
        WHERE timestamp >= ? AND template_id = ?
        ORDER BY timestamp DESC
    ''', (cutoff_iso, template_id))
    rows = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in rows]

if __name__ == "__main__":
    # Initialize database if running directly
    init_db()
    print("Database initialized successfully!")

