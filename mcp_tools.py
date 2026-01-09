"""
MCP Tools module for LLM Log Responder
Defines available tools following Model Context Protocol (MCP) specification
Matches PDF MCP requirements
"""

import json
import os
from typing import Dict, List, Optional, Tuple

SCHEMA_FILE = "mcp_schema.json"

class MCPTool:
    """Represents a single MCP tool definition"""
    def __init__(self, name: str, description: str, input_schema: Dict, 
                 risk_level: str, requires_approval: bool):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.risk_level = risk_level
        self.requires_approval = requires_approval
    
    def to_dict(self) -> Dict:
        """Convert tool to dictionary format"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval
        }

def load_mcp_schema() -> Dict:
    """Load MCP schema from JSON file"""
    if not os.path.exists(SCHEMA_FILE):
        # Return default schema if file doesn't exist
        return {
            "tools": [
                {
                    "name": "RESTART_APACHE",
                    "description": "Restart Apache web server",
                    "inputSchema": {"type": "object", "properties": {}},
                    "risk_level": "HIGH",
                    "requires_approval": True
                },
                {
                    "name": "CLEAR_TEMP_CACHE",
                    "description": "Clear temporary cache",
                    "inputSchema": {"type": "object", "properties": {}},
                    "risk_level": "LOW",
                    "requires_approval": False
                },
                {
                    "name": "ESCALATE",
                    "description": "Escalate to human operator",
                    "inputSchema": {"type": "object", "properties": {}},
                    "risk_level": "MEDIUM",
                    "requires_approval": False
                }
            ]
        }
    
    with open(SCHEMA_FILE, 'r') as f:
        return json.load(f)

def get_tool_registry() -> Dict[str, MCPTool]:
    """
    Get registry of all available MCP tools
    Returns dictionary mapping tool name to MCPTool object
    """
    schema = load_mcp_schema()
    tools = {}
    
    for tool_def in schema.get("tools", []):
        tool = MCPTool(
            name=tool_def["name"],
            description=tool_def["description"],
            input_schema=tool_def.get("inputSchema", {}),
            risk_level=tool_def.get("risk_level", "UNKNOWN"),
            requires_approval=tool_def.get("requires_approval", False)
        )
        tools[tool.name] = tool
    
    return tools

def validate_tool_request(tool_name: str, parameters: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate a tool execution request against its schema
    Returns (is_valid: bool, error_message: str or None)
    """
    registry = get_tool_registry()
    
    if tool_name not in registry:
        return (False, f"Unknown tool: {tool_name}")
    
    tool = registry[tool_name]
    
    # Basic schema validation (simplified - full JSON Schema validation would be more robust)
    if parameters is None:
        parameters = {}
    
    # Check required parameters
    required_params = tool.input_schema.get("required", [])
    for param in required_params:
        if param not in parameters:
            return (False, f"Missing required parameter: {param}")
    
    return (True, None)

def get_tool_description(tool_name: str) -> Optional[str]:
    """Get description of a tool"""
    registry = get_tool_registry()
    tool = registry.get(tool_name)
    return tool.description if tool else None

def list_available_tools() -> List[str]:
    """Get list of all available tool names"""
    registry = get_tool_registry()
    return list(registry.keys())

if __name__ == "__main__":
    # Test tool registry
    registry = get_tool_registry()
    print("Available MCP Tools:")
    for name, tool in registry.items():
        print(f"  - {name}: {tool.description} (Risk: {tool.risk_level}, Approval: {tool.requires_approval})")

