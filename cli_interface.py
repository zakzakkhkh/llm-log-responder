#!/usr/bin/env python3
"""
Command-Line Interface for LLM Log Responder
Interactive query interface matching assignment requirements
"""

import sys
from query_interface import interactive_query, summarize_errors_by_time_window, query_suspicious_events, should_restart_service
from alert_rule_generator import suggest_alert_rules, generate_alert_rules_file
from evaluation import print_evaluation_report
from run_evaluation import run_comprehensive_evaluation

def print_help():
    """Print help message"""
    print("""
LLM Log Responder - Command Interface
=====================================

Available Commands:

QUERIES:
  query "summarize last hour errors"
  query "what suspicious auth events occurred"
  query "should I restart apache"
  query "show open incidents"

ALERT RULES:
  suggest-rules              - Suggest alert rules based on recent patterns
  generate-rules             - Generate Bash script with alert rules

EVALUATION:
  evaluate                   - Run evaluation report
  evaluate-dataset <file>    - Run evaluation on dataset file

METRICS:
  metrics                    - Show system metrics

EXAMPLES:
  python3 cli_interface.py query "summarize last hour errors"
  python3 cli_interface.py suggest-rules
  python3 cli_interface.py evaluate
    """)

def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == "query":
        if len(sys.argv) < 3:
            print("Error: Query required")
            print("Usage: python3 cli_interface.py query '<your query>'")
            sys.exit(1)
        
        query = " ".join(sys.argv[2:])
        result = interactive_query(query)
        print(result)
    
    elif command == "suggest-rules":
        print("Analyzing log patterns and suggesting alert rules...\n")
        suggestions = suggest_alert_rules(hours=24)
        
        print(f"Suggested {len(suggestions)} alert rules:\n")
        for i, rule in enumerate(suggestions, 1):
            print(f"Rule {i}: {rule['pattern']}")
            print(f"  Regex: {rule['regex']}")
            print(f"  Threshold: {rule['threshold']} occurrences")
            print(f"  Suggested Action: {rule['action']}")
            print(f"  Frequency (last 24h): {rule['frequency']}\n")
    
    elif command == "generate-rules":
        output_file = sys.argv[2] if len(sys.argv) > 2 else "generated_alert_rules.sh"
        generate_alert_rules_file(output_file)
        print(f"Alert rules generated in {output_file}")
    
    elif command == "evaluate":
        print_evaluation_report()
    
    elif command == "evaluate-dataset":
        if len(sys.argv) < 3:
            print("Error: Dataset file required")
            print("Usage: python3 cli_interface.py evaluate-dataset <dataset_file> [limit]")
            sys.exit(1)
        
        dataset_file = sys.argv[2]
        limit = None
        if len(sys.argv) > 3:
            try:
                limit = int(sys.argv[3])
            except ValueError:
                print(f"Warning: Invalid limit value, ignoring...")
        
        run_comprehensive_evaluation(dataset_file, limit=limit)
    
    elif command == "metrics":
        from metrics import print_metrics_summary
        print_metrics_summary()
    
    elif command == "help" or command == "--help" or command == "-h":
        print_help()
    
    else:
        print(f"Unknown command: {command}")
        print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()

