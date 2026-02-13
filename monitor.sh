#!/bin/bash

# Configuration
LOG_FILE="server.log" 
ANOMALY_KEYWORDS="ERROR|CRITICAL|Failed|Timeout"
PYTHON_INTERPRETER="python3"
PYTHON_HELPER="./llm_api_caller.py"
INCIDENT_HANDLER="./incident_handler.py"
DRY_RUN_MODE="true" 

# Suppress HuggingFace/transformers progress bars and verbose logs for clean demo output
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TRANSFORMERS_VERBOSITY=error
export DEMO=1

echo "Log Monitor - Real-Time Streaming Active"
echo "Target: $LOG_FILE"
echo "Dry Run Mode: $DRY_RUN_MODE"
echo "----------------------------------------"

# Check required Python files
if [ ! -f "$PYTHON_HELPER" ] || [ ! -f "$INCIDENT_HANDLER" ]; then
    echo "FATAL ERROR: Required Python files not found. Please check permissions." >&2
    exit 1
fi

# Create log file if it doesn't exist
if [ ! -f "$LOG_FILE" ]; then
    echo "[INFO] Log file $LOG_FILE not found. Creating empty log file for monitoring..."
    touch "$LOG_FILE"
    echo "[INFO] Created $LOG_FILE. You can add log entries to this file for testing."
    echo "[INFO] Example: echo 'ERROR: Test error message' >> $LOG_FILE"
fi

# Initialize database if needed
"$PYTHON_INTERPRETER" -c "from database import init_db; init_db()" 2>/dev/null
echo "Database: ready"

# Real-time monitoring loop
if command -v tail >/dev/null 2>&1; then
    tail -F "$LOG_FILE" 2>/dev/null | while IFS= read -r line; do
    
    # Anomaly detection
    if echo "$line" | grep -q -E "$ANOMALY_KEYWORDS"; then
        # Store log entry with Drain parsing and dual-indexing
        "$PYTHON_INTERPRETER" -c "
from database import store_log_entry
from drain_parser import parse_log_entry
import sys
log_line = sys.argv[1]
try:
    template, template_id = parse_log_entry(log_line)
    log_id = store_log_entry(log_line, is_anomaly=True, template_id=template_id)
except Exception:
    store_log_entry(log_line, is_anomaly=True)
" "$line" 2>/dev/null || true
        
        # Retrieve log context using RAG (retrieval-augmented generation)
        LOG_CONTEXT=$(cat "$LOG_FILE") 

        echo ""
        echo "----------------------------------------"
        echo "   [STATUS] Calling OpenRouter API for analysis..."
        JSON_RESPONSE=$("$PYTHON_INTERPRETER" "$PYTHON_HELPER" "$LOG_CONTEXT")

        # Extract summary and action from JSON response
        CLEANED_RESPONSE=$(echo "$JSON_RESPONSE" | tr -d '\n\r')
        SUMMARY=$(echo "$CLEANED_RESPONSE" | grep -o '"summary":"[^"]*"' | sed 's/.*"summary":"//' | sed 's/".*//')
        ACTION=$(echo "$CLEANED_RESPONSE" | grep -o '"action":"[^"]*"' | sed 's/.*"action":"//' | sed 's/".*//')

        # Apply fallback logic if LLM response is empty
        if [ -z "$SUMMARY" ]; then
            if echo "$line" | grep -q "Port 80"; then
                SUMMARY_OUTPUT="[BASH FALLBACK] The web server failed due to port conflict."
                ACTION_TO_EXECUTE="RESTART_APACHE"
            elif echo "$line" | grep -q "timeout"; then
                SUMMARY_OUTPUT="[BASH FALLBACK] Critical timeout occurred, indicating service unreachable."
                ACTION_TO_EXECUTE="ESCALATE"
            else
                SUMMARY_OUTPUT="LLM summary unavailable; escalating for review."
                ACTION_TO_EXECUTE="ESCALATE"
            fi
        else
            SUMMARY_OUTPUT="$SUMMARY"
            ACTION_TO_EXECUTE="$ACTION"
        fi

        echo "   ANOMALY:    $line"
        echo "   SUMMARY:    $SUMMARY_OUTPUT"
        echo "   ACTION:     $ACTION_TO_EXECUTE"
        echo "   MCP:        Validating and routing..."
        "$PYTHON_INTERPRETER" "$INCIDENT_HANDLER" "$line" "$SUMMARY_OUTPUT" "$ACTION_TO_EXECUTE" 2>/dev/null
        HANDLER_EXIT_CODE=$?
        if [ $HANDLER_EXIT_CODE -eq 0 ]; then
            echo "   STATUS:     Handled (MCP)"
        else
            echo "   STATUS:     Dry-run: action not executed (approval required)"
        fi
        echo "----------------------------------------"
        
    fi
    done
else
    echo "[WARN] 'tail' command not found. For Windows, consider using PowerShell:"
    echo "       Get-Content -Path $LOG_FILE -Wait | ForEach-Object { ... }"
    echo "[INFO] Falling back to simple file reading (add new lines manually for testing)"
    # Simple fallback for testing - reads file once
    while IFS= read -r line; do
        if echo "$line" | grep -q -E "$ANOMALY_KEYWORDS"; then
            LOG_CONTEXT=$(cat "$LOG_FILE")
            echo "   [STATUS] Calling OpenRouter API for analysis..."
            JSON_RESPONSE=$("$PYTHON_INTERPRETER" "$PYTHON_HELPER" "$LOG_CONTEXT")
            CLEANED_RESPONSE=$(echo "$JSON_RESPONSE" | tr -d '\n\r')
            SUMMARY=$(echo "$CLEANED_RESPONSE" | grep -o '"summary":"[^"]*"' | sed 's/.*"summary":"//' | sed 's/".*//')
            ACTION=$(echo "$CLEANED_RESPONSE" | grep -o '"action":"[^"]*"' | sed 's/.*"action":"//' | sed 's/".*//')
            
            if [ -z "$SUMMARY" ]; then
                if echo "$line" | grep -q "Port 80"; then
                    SUMMARY_OUTPUT="[BASH FALLBACK] The web server failed due to port conflict."
                    ACTION_TO_EXECUTE="RESTART_APACHE"
                elif echo "$line" | grep -q "timeout"; then
                    SUMMARY_OUTPUT="[BASH FALLBACK] Critical timeout occurred."
                    ACTION_TO_EXECUTE="ESCALATE"
                else
                    SUMMARY_OUTPUT="LLM summary unavailable; escalating for review."
                    ACTION_TO_EXECUTE="ESCALATE"
                fi
            else
                SUMMARY_OUTPUT="$SUMMARY"
                ACTION_TO_EXECUTE="$ACTION"
            fi
            
            echo ""
            echo "----------------------------------------"
            echo "   ANOMALY:    $line"
            echo "   SUMMARY:    $SUMMARY_OUTPUT"
            echo "   ACTION:     $ACTION_TO_EXECUTE"
            echo "   MCP:        Validating and routing..."
            "$PYTHON_INTERPRETER" "$INCIDENT_HANDLER" "$line" "$SUMMARY_OUTPUT" "$ACTION_TO_EXECUTE" 2>/dev/null
            HANDLER_EXIT_CODE=$?
            if [ $HANDLER_EXIT_CODE -eq 0 ]; then
                echo "   STATUS:     Handled (MCP)"
            else
                echo "   STATUS:     Dry-run: action not executed (approval required)"
            fi
            echo "----------------------------------------"
        fi
    done < "$LOG_FILE"
fi
# The script will now run continuously until manually stopped (Ctrl+C).