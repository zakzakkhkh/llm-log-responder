#!/bin/bash

# Configuration
LOG_FILE="server.log" 
ANOMALY_KEYWORDS="ERROR|CRITICAL|Failed|Timeout"
PYTHON_INTERPRETER="python3"
PYTHON_HELPER="./llm_api_caller.py"
INCIDENT_HANDLER="./incident_handler.py"
DRY_RUN_MODE="true" 

echo "Log Monitor - Real-Time Streaming Active"
echo "Target: $LOG_FILE"
echo "Dry Run Mode: $DRY_RUN_MODE"
echo "----------------------------------------"

# Check required files
if [ ! -f "$LOG_FILE" ] || [ ! -f "$PYTHON_HELPER" ] || [ ! -f "$INCIDENT_HANDLER" ]; then
    echo "FATAL ERROR: Required files not found. Please check permissions." >&2
    exit 1
fi

# Initialize database if needed
echo "[INIT] Initializing database..."
"$PYTHON_INTERPRETER" -c "from database import init_db; init_db()" 2>/dev/null || echo "[WARN] Database initialization check skipped"

# Real-time monitoring loop
if command -v tail >/dev/null 2>&1; then
    tail -F "$LOG_FILE" 2>/dev/null | while IFS= read -r line; do
    
    # Anomaly detection
    if echo "$line" | grep -q -E "$ANOMALY_KEYWORDS"; then
        # Store log entry for indexing
        "$PYTHON_INTERPRETER" -c "from database import store_log_entry; store_log_entry('$line', True)" 2>/dev/null || true
        
        # Retrieve log context
        LOG_CONTEXT=$(cat "$LOG_FILE") 

        # Call LLM API
        echo "   [STATUS] Calling OpenRouter API for analysis (This may take a few seconds)..."
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
                SUMMARY_OUTPUT="API ERROR: Check terminal for Python errors."
                ACTION_TO_EXECUTE="ESCALATE"
            fi
        else
            SUMMARY_OUTPUT="$SUMMARY"
            ACTION_TO_EXECUTE="$ACTION"
        fi

        echo -e "\n🚨 [ANOMALY DETECTED] $line"
        echo -e "   [LLM SUMMARY] $SUMMARY_OUTPUT"
        echo -e "   [PROPOSED ACTION] \033[1m$ACTION_TO_EXECUTE\033[0m"
        
        # Execute action via MCP server
        echo -e "   [MCP GATEWAY] Routing action through MCP server with validation..."
        "$PYTHON_INTERPRETER" "$INCIDENT_HANDLER" "$line" "$SUMMARY_OUTPUT" "$ACTION_TO_EXECUTE"
        
        HANDLER_EXIT_CODE=$?
        if [ $HANDLER_EXIT_CODE -eq 0 ]; then
            echo -e "   [STATUS] Incident handled successfully via MCP"
        else
            echo -e "   [STATUS] Incident handling completed with warnings/errors"
        fi
        
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
                    SUMMARY_OUTPUT="API ERROR"
                    ACTION_TO_EXECUTE="ESCALATE"
                fi
            else
                SUMMARY_OUTPUT="$SUMMARY"
                ACTION_TO_EXECUTE="$ACTION"
            fi
            
            echo -e "\n🚨 [ANOMALY DETECTED] $line"
            echo -e "   [LLM SUMMARY] $SUMMARY_OUTPUT"
            echo -e "   [PROPOSED ACTION] $ACTION_TO_EXECUTE"
            "$PYTHON_INTERPRETER" "$INCIDENT_HANDLER" "$line" "$SUMMARY_OUTPUT" "$ACTION_TO_EXECUTE"
        fi
    done < "$LOG_FILE"
fi
# The script will now run continuously until manually stopped (Ctrl+C).