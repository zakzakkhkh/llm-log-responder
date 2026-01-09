"""
Alert Rule Generator for LLM Log Responder
Generates Bash scripts for alert rules (regex, thresholds)
Matches assignment requirement for suggesting alert rules
"""

import re
from datetime import datetime
from typing import List, Dict, Optional
from database import get_incidents_by_time_window, search_logs_by_pattern

def analyze_error_patterns(hours: int = 24) -> List[Dict]:
    """
    Analyze error patterns from recent incidents
    Returns common patterns that could be used for alert rules
    """
    incidents = get_incidents_by_time_window(hours)
    
    patterns = {}
    for incident in incidents:
        log_line = incident.get('log_line', '')
        
        # Extract common error patterns
        if 'ERROR' in log_line:
            # Extract error type
            if 'Port' in log_line and ('80' in log_line or '443' in log_line):
                pattern = 'port.*conflict'
                patterns[pattern] = patterns.get(pattern, 0) + 1
            elif 'timeout' in log_line.lower():
                pattern = 'timeout'
                patterns[pattern] = patterns.get(pattern, 0) + 1
            elif 'connection' in log_line.lower() and 'failed' in log_line.lower():
                pattern = 'connection.*failed'
                patterns[pattern] = patterns.get(pattern, 0) + 1
            elif 'permission denied' in log_line.lower():
                pattern = 'permission.*denied'
                patterns[pattern] = patterns.get(pattern, 0) + 1
            else:
                # Generic ERROR pattern
                pattern = 'ERROR'
                patterns[pattern] = patterns.get(pattern, 0) + 1
        
        if 'CRITICAL' in log_line:
            pattern = 'CRITICAL'
            patterns[pattern] = patterns.get(pattern, 0) + 1
    
    # Sort by frequency
    sorted_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)
    
    return [{"pattern": p, "frequency": f, "regex": pattern_to_regex(p)} 
            for p, f in sorted_patterns]

def pattern_to_regex(pattern: str) -> str:
    """Convert pattern description to regex"""
    pattern_map = {
        'port.*conflict': r'ERROR.*[Pp]ort\s+\d+.*in use',
        'timeout': r'(?i)(timeout|timed out)',
        'connection.*failed': r'(?i)(connection.*failed|failed to connect)',
        'permission.*denied': r'(?i)(permission denied)',
        'ERROR': r'ERROR',
        'CRITICAL': r'CRITICAL'
    }
    
    return pattern_map.get(pattern, f'({pattern})')

def generate_alert_rule_bash(pattern: str, threshold: int = 1, action: str = "ESCALATE") -> str:
    """
    Generate a Bash script for an alert rule
    Matches assignment requirement for generating Bash responder scripts
    """
    regex = pattern_to_regex(pattern)
    
    bash_script = f"""#!/bin/bash
# Auto-generated alert rule
# Pattern: {pattern}
# Threshold: {threshold} occurrence(s)
# Action: {action}

LOG_FILE="${{LOG_FILE:-server.log}}"
PATTERN="{regex}"
THRESHOLD={threshold}
ACTION="{action}"

# Count occurrences in last hour
COUNT=$(tail -n 1000 "$LOG_FILE" | grep -c -E "$PATTERN" || echo "0")

if [ "$COUNT" -ge "$THRESHOLD" ]; then
    echo "[ALERT] Pattern detected $COUNT times (threshold: $THRESHOLD)"
    echo "[ALERT] Pattern: $PATTERN"
    echo "[ALERT] Triggering action: $ACTION"
    
    # Trigger action
    ./actions.sh "$ACTION"
    
    exit 0
else
    exit 1
fi
"""
    return bash_script

def suggest_alert_rules(hours: int = 24) -> List[Dict]:
    """
    Suggest alert rules based on recent error patterns
    Returns list of suggested rules with patterns, thresholds, and actions
    """
    patterns = analyze_error_patterns(hours)
    
    suggestions = []
    for pattern_info in patterns[:5]:  # Top 5 patterns
        pattern = pattern_info['pattern']
        frequency = pattern_info['frequency']
        regex = pattern_info['regex']
        
        # Suggest threshold based on frequency
        threshold = max(1, frequency // 3)  # Alert if 1/3 of occurrences happen
        
        # Suggest action based on pattern
        if 'port' in pattern.lower() or 'timeout' in pattern.lower():
            action = "RESTART_APACHE"
        elif 'critical' in pattern.upper():
            action = "ESCALATE"
        else:
            action = "ESCALATE"
        
        suggestions.append({
            "pattern": pattern,
            "regex": regex,
            "threshold": threshold,
            "action": action,
            "frequency": frequency,
            "bash_script": generate_alert_rule_bash(pattern, threshold, action)
        })
    
    return suggestions

def generate_alert_rules_file(output_file: str = "generated_alert_rules.sh", hours: int = 24):
    """
    Generate a Bash file with multiple alert rules
    """
    suggestions = suggest_alert_rules(hours)
    
    with open(output_file, 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Auto-generated alert rules based on log analysis\n")
        f.write("# Generated: " + str(datetime.now()) + "\n\n")
        
        for i, suggestion in enumerate(suggestions, 1):
            f.write(f"# Rule {i}: {suggestion['pattern']} (frequency: {suggestion['frequency']})\n")
            f.write(suggestion['bash_script'])
            f.write("\n" + "="*60 + "\n\n")
    
    print(f"Generated {len(suggestions)} alert rules in {output_file}")

if __name__ == "__main__":
    import sys
    
    print("Alert Rule Generator")
    print("="*50)
    print("\nAnalyzing recent error patterns...")
    
    suggestions = suggest_alert_rules(hours=24)
    
    print(f"\nSuggested {len(suggestions)} alert rules:\n")
    for i, rule in enumerate(suggestions, 1):
        print(f"Rule {i}: {rule['pattern']}")
        print(f"  Regex: {rule['regex']}")
        print(f"  Threshold: {rule['threshold']} occurrences")
        print(f"  Suggested Action: {rule['action']}")
        print(f"  Frequency (last 24h): {rule['frequency']}")
        print()
    
    # Generate bash file
    generate_alert_rules_file("generated_alert_rules.sh")
    print("Alert rules saved to generated_alert_rules.sh")

