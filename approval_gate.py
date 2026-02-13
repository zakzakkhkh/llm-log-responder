"""
Approval Gate module for LLM Log Responder
Implements human-in-the-loop safety checks for high-risk actions
Matches PDF safety requirements
"""

import json
import os
import sys
from typing import Optional, Tuple

CONFIG_FILE = "config.json"
_quiet = os.environ.get("DEMO") == "1"

def load_config() -> dict:
    """Load configuration from config.json"""
    if not os.path.exists(CONFIG_FILE):
        # Default configuration if file doesn't exist
        return {
            "actions": {
                "RESTART_APACHE": {"risk_level": "HIGH", "requires_approval": True},
                "CLEAR_TEMP_CACHE": {"risk_level": "LOW", "requires_approval": False},
                "ESCALATE": {"risk_level": "MEDIUM", "requires_approval": False}
            },
            "dry_run_mode": True
        }
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def requires_approval(action_name: str) -> bool:
    """
    Check if an action requires human approval
    Returns True if approval is needed, False otherwise
    """
    config = load_config()
    action_config = config.get("actions", {}).get(action_name, {})
    return action_config.get("requires_approval", False)

def get_action_risk_level(action_name: str) -> str:
    """Get the risk level of an action"""
    config = load_config()
    action_config = config.get("actions", {}).get(action_name, {})
    return action_config.get("risk_level", "UNKNOWN")

def request_approval(action_name: str, summary: str, incident_context: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Request human approval for an action
    Returns (approved: bool, approved_by: str or None)
    
    In interactive mode, prompts user. In non-interactive mode, defaults to False.
    """
    config = load_config()
    
    # Check if dry_run_mode is enabled - if so, auto-approve for logging purposes but don't execute
    if config.get("dry_run_mode", True):
        if not _quiet:
            print(f"\n⚠️  [APPROVAL GATE] DRY RUN MODE: Action '{action_name}' would require approval")
            print(f"   Summary: {summary}")
        return (False, "dry_run_mode")  # Return False to prevent execution
    
    # Check if approval is required
    if not requires_approval(action_name):
        return (True, "auto_approved")
    
    # Request approval
    risk_level = get_action_risk_level(action_name)
    action_config = config.get("actions", {}).get(action_name, {})
    description = action_config.get("description", "No description available")
    
    print("\n" + "="*60)
    print(f"⚠️  APPROVAL REQUIRED - {risk_level} RISK ACTION")
    print("="*60)
    print(f"Action: {action_name}")
    print(f"Description: {description}")
    print(f"Summary: {summary}")
    if incident_context:
        print(f"Context: {incident_context[:200]}...")  # Truncate long contexts
    print("="*60)
    
    # For non-interactive environments, we'll default to rejecting
    if not sys.stdin.isatty():
        print("[APPROVAL GATE] Non-interactive mode: Action REJECTED (requires manual approval)")
        return (False, None)
    
    # Interactive prompt
    while True:
        response = input("\nApprove this action? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            approved_by = os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))
            print(f"✅ Action APPROVED by {approved_by}")
            return (True, approved_by)
        elif response in ['n', 'no']:
            print("❌ Action REJECTED")
            return (False, None)
        else:
            print("Please enter 'y' for yes or 'n' for no")

def is_dry_run_mode() -> bool:
    """Check if dry run mode is enabled"""
    config = load_config()
    return config.get("dry_run_mode", True)

if __name__ == "__main__":
    # Test approval gate
    test_actions = ["RESTART_APACHE", "CLEAR_TEMP_CACHE", "ESCALATE"]
    for action in test_actions:
        needs_approval = requires_approval(action)
        risk = get_action_risk_level(action)
        print(f"{action}: Risk={risk}, Requires Approval={needs_approval}")

