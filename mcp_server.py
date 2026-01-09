"""
MCP Server module for LLM Log Responder
Implements Model Context Protocol (MCP) server with validation and audit logging
Matches PDF MCP requirements for safe tool invocation
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, Optional, Tuple

from mcp_tools import validate_tool_request, get_tool_registry, get_tool_description
from database import record_action
from approval_gate import request_approval, requires_approval, is_dry_run_mode

AUDIT_LOG_FILE = "mcp_audit.log"

def log_audit_event(tool_name: str, incident_id: Optional[int], status: str, 
                    approved_by: Optional[str] = None, error: Optional[str] = None):
    """
    Log all MCP tool invocations for audit trail
    Matches PDF requirement for audit logging
    """
    audit_entry = {
        "timestamp": datetime.now().isoformat(),
        "tool_name": tool_name,
        "incident_id": incident_id,
        "status": status,
        "approved_by": approved_by,
        "error": error
    }
    
    # Write to audit log file
    with open(AUDIT_LOG_FILE, 'a') as f:
        f.write(json.dumps(audit_entry) + "\n")
    
    print(f"[MCP AUDIT] {tool_name} - Status: {status} - Incident: {incident_id}")

def execute_mcp_tool(tool_name: str, incident_id: Optional[int] = None, 
                     summary: Optional[str] = None, parameters: Optional[Dict] = None) -> Tuple[bool, str]:
    """
    Execute an MCP tool with validation and approval checks
    Returns (success: bool, message: str)
    """
    # Step 1: Validate tool exists and parameters match schema
    is_valid, error_msg = validate_tool_request(tool_name, parameters)
    if not is_valid:
        log_audit_event(tool_name, incident_id, "validation_failed", error=error_msg)
        return (False, f"Validation failed: {error_msg}")
    
    log_audit_event(tool_name, incident_id, "validated")
    
    # Step 2: Check if approval is required
    if requires_approval(tool_name):
        approved, approved_by = request_approval(tool_name, summary or "No summary provided")
        if not approved:
            log_audit_event(tool_name, incident_id, "rejected", approved_by=approved_by)
            return (False, "Action rejected by approval gate")
        log_audit_event(tool_name, incident_id, "approved", approved_by=approved_by)
    else:
        approved_by = "auto_approved"
    
    # Step 3: Check dry run mode
    if is_dry_run_mode():
        log_audit_event(tool_name, incident_id, "dry_run", approved_by=approved_by)
        return (True, f"[DRY RUN] Tool '{tool_name}' would be executed (approved by {approved_by})")
    
    # Step 4: Execute the actual tool via actions.sh
    import subprocess
    try:
        # Call actions.sh with the tool name
        result = subprocess.run(
            ["./actions.sh", tool_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Record action in database
            if incident_id:
                record_action(incident_id, tool_name, status='executed', 
                            approved_by=approved_by, result_message=result.stdout)
            
            log_audit_event(tool_name, incident_id, "executed", approved_by=approved_by)
            return (True, f"Tool '{tool_name}' executed successfully")
        else:
            error_msg = result.stderr or "Unknown error"
            log_audit_event(tool_name, incident_id, "failed", error=error_msg)
            return (False, f"Tool execution failed: {error_msg}")
            
    except subprocess.TimeoutExpired:
        error_msg = "Tool execution timed out"
        log_audit_event(tool_name, incident_id, "timeout", error=error_msg)
        return (False, error_msg)
    except Exception as e:
        error_msg = str(e)
        log_audit_event(tool_name, incident_id, "error", error=error_msg)
        return (False, f"Tool execution error: {error_msg}")

def get_available_tools_info() -> Dict:
    """Get information about all available MCP tools"""
    registry = get_tool_registry()
    tools_info = {}
    
    for name, tool in registry.items():
        tools_info[name] = {
            "description": tool.description,
            "risk_level": tool.risk_level,
            "requires_approval": tool.requires_approval,
            "input_schema": tool.input_schema
        }
    
    return tools_info

if __name__ == "__main__":
    # Test MCP server
    print("MCP Server Test")
    print("="*50)
    
    # List available tools
    registry = get_tool_registry()
    print("\nAvailable Tools:")
    for name, tool in registry.items():
        print(f"  - {name}: {tool.description}")
    
    # Test validation
    print("\nTesting validation:")
    is_valid, msg = validate_tool_request("RESTART_APACHE")
    print(f"  RESTART_APACHE: {is_valid} ({msg})")
    
    is_valid, msg = validate_tool_request("UNKNOWN_TOOL")
    print(f"  UNKNOWN_TOOL: {is_valid} ({msg})")

