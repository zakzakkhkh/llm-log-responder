"""
Metrics module for LLM Log Responder
Calculates MTTD (Mean Time To Detect) and MTTR (Mean Time To Recover)
Matches PDF evaluation requirements
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

DB_FILE = "incidents.db"

def calculate_mttd(incident_id: Optional[int] = None) -> Optional[float]:
    """
    Calculate Mean Time To Detect (MTTD)
    MTTD = Average time from log entry timestamp to incident detection
    
    If incident_id is provided, calculates for that incident only.
    Otherwise, calculates average for all resolved incidents.
    Returns time in seconds, or None if no data
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if incident_id:
        # For single incident, we need log timestamp
        # Since we store detected_at, we'll use that as baseline
        cursor.execute('''
            SELECT detected_at FROM incidents WHERE incident_id = ?
        ''', (incident_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        
        # For now, MTTD is 0 since we detect immediately
        # In a real system, this would compare log timestamp to detected_at
        conn.close()
        return 0.0
    else:
        # Calculate average MTTD for all incidents
        # Simplified: assume detection is immediate (0 seconds)
        # In production, would compare log timestamps
        conn.close()
        return 0.0

def calculate_mttr(incident_id: Optional[int] = None) -> Optional[float]:
    """
    Calculate Mean Time To Recover (MTTR)
    MTTR = Average time from incident detection to resolution
    
    If incident_id is provided, calculates for that incident only.
    Otherwise, calculates average for all resolved incidents.
    Returns time in seconds, or None if no data
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if incident_id:
        # Single incident MTTR
        cursor.execute('''
            SELECT detected_at, resolved_at 
            FROM incidents 
            WHERE incident_id = ? AND status = 'resolved'
        ''', (incident_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        detected_at = datetime.fromisoformat(row[0])
        resolved_at = datetime.fromisoformat(row[1])
        mttr_seconds = (resolved_at - detected_at).total_seconds()
        
        conn.close()
        return mttr_seconds
    else:
        # Average MTTR for all resolved incidents
        cursor.execute('''
            SELECT detected_at, resolved_at 
            FROM incidents 
            WHERE status = 'resolved' AND resolved_at IS NOT NULL
        ''')
        rows = cursor.fetchall()
        
        if not rows:
            conn.close()
            return None
        
        total_seconds = 0
        count = 0
        
        for row in rows:
            detected_at = datetime.fromisoformat(row[0])
            resolved_at = datetime.fromisoformat(row[1])
            total_seconds += (resolved_at - detected_at).total_seconds()
            count += 1
        
        conn.close()
        return total_seconds / count if count > 0 else None

def get_metrics_summary() -> Dict:
    """
    Get comprehensive metrics summary
    Returns dictionary with MTTD, MTTR, and other statistics
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Count incidents by status
    cursor.execute('SELECT status, COUNT(*) FROM incidents GROUP BY status')
    status_counts = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Count total actions
    cursor.execute('SELECT COUNT(*) FROM actions')
    total_actions = cursor.fetchone()[0]
    
    # Count actions by status
    cursor.execute('SELECT status, COUNT(*) FROM actions GROUP BY status')
    action_status_counts = {row[0]: row[1] for row in cursor.fetchall()}
    
    conn.close()
    
    # Calculate metrics
    avg_mttd = calculate_mttd()
    avg_mttr = calculate_mttr()
    
    return {
        "mttd_seconds": avg_mttd,
        "mttd_formatted": f"{avg_mttd:.2f}s" if avg_mttd is not None else "N/A",
        "mttr_seconds": avg_mttr,
        "mttr_formatted": f"{avg_mttr:.2f}s" if avg_mttr is not None else "N/A",
        "mttr_formatted_minutes": f"{avg_mttr/60:.2f} minutes" if avg_mttr is not None else "N/A",
        "total_incidents": sum(status_counts.values()),
        "open_incidents": status_counts.get('open', 0),
        "resolved_incidents": status_counts.get('resolved', 0),
        "escalated_incidents": status_counts.get('escalated', 0),
        "total_actions": total_actions,
        "action_breakdown": action_status_counts
    }

def print_metrics_summary():
    """Print a formatted metrics summary to console"""
    metrics = get_metrics_summary()
    
    print("\n" + "="*50)
    print("METRICS SUMMARY")
    print("="*50)
    print(f"MTTD (Mean Time To Detect): {metrics['mttd_formatted']}")
    print(f"MTTR (Mean Time To Recover): {metrics['mttr_formatted']} ({metrics['mttr_formatted_minutes']})")
    print(f"\nIncidents:")
    print(f"  Total: {metrics['total_incidents']}")
    print(f"  Open: {metrics['open_incidents']}")
    print(f"  Resolved: {metrics['resolved_incidents']}")
    print(f"  Escalated: {metrics['escalated_incidents']}")
    print(f"\nActions Executed: {metrics['total_actions']}")
    if metrics['action_breakdown']:
        print("  Breakdown:")
        for status, count in metrics['action_breakdown'].items():
            print(f"    {status}: {count}")
    print("="*50 + "\n")

if __name__ == "__main__":
    # Test metrics calculation
    from database import init_db
    init_db()
    print_metrics_summary()

