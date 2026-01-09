#!/bin/bash
# Setup script to configure API key for LLM Log Responder
# This sets the API key as an environment variable for the current session

API_KEY="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"

export OPENROUTER_API_KEY="$API_KEY"

echo "✅ API key configured for this terminal session"
echo "⚠️  Note: This key is only set for the current terminal session"
echo "   If you open a new terminal, run this script again or:"
echo "   export OPENROUTER_API_KEY=\"$API_KEY\""
echo ""
echo "To verify, run: echo \$OPENROUTER_API_KEY"

