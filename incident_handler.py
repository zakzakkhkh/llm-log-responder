"""
Incident Handler - Main integration script
Coordinates database, MCP, approval gates, and metrics
Called from monitor.sh to handle detected incidents
"""

import sys
import os
from typing import Optional

_quiet = os.environ.get("DEMO") == "1"

from database import init_db, record_incident, update_incident_resolved
from mcp_server import execute_mcp_tool
from metrics import get_metrics_summary
from rag_framework import get_rag_summarizer

def handle_incident(log_line: str, summary: str, action_name: str) -> int:
    """
    Main handler for detected incidents
    Returns exit code (0 = success, 1 = error)
    """
    # Initialize database if needed
    if not os.path.exists("incidents.db"):
        init_db()
    
    # Record the incident
    incident_id = record_incident(log_line, summary)
    
    # Enhance summary using RAG if available
    try:
        rag_summarizer = get_rag_summarizer()
        enhanced_summary = rag_summarizer.summarize_incident(incident_id, hours=1)
        if enhanced_summary and enhanced_summary != summary:
            summary = enhanced_summary
            if not _quiet:
                print(f"[INCIDENT HANDLER] RAG-enhanced summary generated")
    except Exception as e:
        if not _quiet:
            print(f"[INCIDENT HANDLER] RAG summarization unavailable: {e}")
    
    # Execute the proposed action via MCP (with seccomp sandboxing)
    success, message = execute_mcp_tool(action_name, incident_id, summary)
    
    if success:
        # Mark incident as resolved if action executed successfully
        if "DRY RUN" not in message.upper():
            update_incident_resolved(incident_id)
        if not _quiet:
            print(f"[INCIDENT HANDLER] {message}")
        return 0
    else:
        if not _quiet:
            print(f"[INCIDENT HANDLER] Action failed: {message}")
        return 1

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python incident_handler.py <log_line> <summary> <action_name>")
        sys.exit(1)
    
    log_line = sys.argv[1]
    summary = sys.argv[2]
    action_name = sys.argv[3]
    
    exit_code = handle_incident(log_line, summary, action_name)
    sys.exit(exit_code)

