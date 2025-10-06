#!/bin/bash

# Aperim Template - Claude Log Interpreter Script
# Parses Claude JSON logs and presents them in a clean, readable format

set -euo pipefail

# Colours for output (Australian spelling)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Colour

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [LOG_FILE]"
    echo ""
    echo "Interprets Claude JSON logs and presents them in a clean, readable format"
    echo ""
    echo "Options:"
    echo "  --follow, -f           Follow log file (like tail -f)"
    echo "  --filter TYPE          Filter by message type (assistant, user, tool_use, tool_result)"
    echo "  --session ID           Filter by specific session ID"
    echo "  --compact             Show compact format (one line per message)"
    echo "  --raw                 Show raw JSON (for debugging)"
    echo "  --help, -h             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 /tmp/hive-mind-pr-123.log         # Parse log file"
    echo "  $0 --follow /tmp/hive-mind-pr-123.log   # Follow log file"
    echo "  $0 --filter assistant --compact log.json  # Show only assistant messages"
    echo "  tail -f log.json | $0               # Pipe from tail"
}

# Default values
FOLLOW=false
FILTER=""
SESSION_FILTER=""
COMPACT=false
RAW=false
LOG_FILE=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --follow|-f)
            FOLLOW=true
            shift
            ;;
        --filter)
            FILTER="$2"
            shift 2
            ;;
        --session)
            SESSION_FILTER="$2"
            shift 2
            ;;
        --compact)
            COMPACT=true
            shift
            ;;
        --raw)
            RAW=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        -*)
            echo -e "${RED}Unknown option: $1${NC}" >&2
            show_usage >&2
            exit 1
            ;;
        *)
            LOG_FILE="$1"
            shift
            ;;
    esac
done

# Format timestamp
format_timestamp() {
    local timestamp="$1"
    if [[ "$timestamp" =~ ^[0-9]+$ ]]; then
        # Unix timestamp (milliseconds)
        date -d "@$(echo "$timestamp" | sed 's/...$//')" '+%H:%M:%S' 2>/dev/null || echo "??:??:??"
    else
        # Already formatted or invalid
        echo "$timestamp"
    fi
}

# Extract tool name from tool_use
extract_tool_name() {
    local content="$1"
    echo "$content" | jq -r '.name // .tool_name // "unknown_tool"' 2>/dev/null || echo "unknown_tool"
}

# Truncate text to specified length
truncate_text() {
    local text="$1"
    local max_length="${2:-100}"
    
    if [ ${#text} -gt $max_length ]; then
        echo "${text:0:$max_length}..."
    else
        echo "$text"
    fi
}

# Extract meaningful content from message
extract_content() {
    local json_line="$1"
    local message_type="$2"
    
    case "$message_type" in
        "assistant")
            # Extract tool use or text content
            local tool_uses=$(echo "$json_line" | jq -r '.message.content[]? | select(.type == "tool_use") | .name' 2>/dev/null | tr '\n' ',' | sed 's/,$//')
            local text_content=$(echo "$json_line" | jq -r '.message.content[]? | select(.type == "text") | .text' 2>/dev/null)
            
            if [ -n "$tool_uses" ]; then
                echo "🔧 Using tools: $tool_uses"
            elif [ -n "$text_content" ]; then
                echo "💬 $(truncate_text "$text_content" 80)"
            else
                echo "📝 Assistant message"
            fi
            ;;
        "user")
            # Check if it's a tool result
            local tool_use_id=$(echo "$json_line" | jq -r '.message.content[0].tool_use_id // ""' 2>/dev/null)
            local is_error=$(echo "$json_line" | jq -r '.message.content[0].is_error // false' 2>/dev/null)
            
            if [ -n "$tool_use_id" ] && [ "$tool_use_id" != "null" ]; then
                if [ "$is_error" = "true" ]; then
                    echo "❌ Tool error: $(echo "$tool_use_id" | cut -c1-12)..."
                else
                    echo "✅ Tool completed: $(echo "$tool_use_id" | cut -c1-12)..."
                fi
            else
                local content=$(echo "$json_line" | jq -r '.message.content // .content // ""' 2>/dev/null)
                if [ -n "$content" ] && [ "$content" != "null" ]; then
                    echo "👤 $(truncate_text "$content" 80)"
                else
                    echo "👤 User input"
                fi
            fi
            ;;
        "tool_use")
            local tool_name=$(extract_tool_name "$json_line")
            echo "🔧 $tool_name"
            ;;
        "tool_result")
            local tool_name=$(echo "$json_line" | jq -r '.tool_use_id // .parent_tool_use_id // "unknown"' 2>/dev/null)
            local is_error=$(echo "$json_line" | jq -r '.is_error // false' 2>/dev/null)
            if [ "$is_error" = "true" ]; then
                echo "❌ Tool error: $tool_name"
            else
                echo "✅ Tool result: $tool_name"
            fi
            ;;
        *)
            echo "📄 $message_type"
            ;;
    esac
}

# Process a single JSON line
process_json_line() {
    local line="$1"
    
    # Skip empty lines
    [ -z "$line" ] && return
    
    # Check if it's valid JSON
    if ! echo "$line" | jq empty >/dev/null 2>&1; then
        if [ "$RAW" = true ]; then
            echo -e "${YELLOW}[NON-JSON] $line${NC}"
        fi
        return
    fi
    
    # Extract basic info
    local message_type=$(echo "$line" | jq -r '.type // "unknown"' 2>/dev/null)
    local session_id=$(echo "$line" | jq -r '.session_id // "unknown"' 2>/dev/null)
    local uuid=$(echo "$line" | jq -r '.uuid // ""' 2>/dev/null | cut -c1-8)
    
    # Debug output (temporary)
    [ "$RAW" = true ] && echo "DEBUG: type=$message_type, session=$session_id" >&2
    
    # Apply session filter
    if [ -n "$SESSION_FILTER" ] && [ "$session_id" != "$SESSION_FILTER" ]; then
        return
    fi
    
    # Apply message type filter
    if [ -n "$FILTER" ] && [ "$message_type" != "$FILTER" ]; then
        return
    fi
    
    # Show raw JSON if requested
    if [ "$RAW" = true ]; then
        echo "$line" | jq .
        return
    fi
    
    # Get current timestamp
    local timestamp=$(date '+%H:%M:%S')
    
    # Extract role for assistant/user messages
    local role=""
    if [ "$message_type" = "assistant" ] || [ "$message_type" = "user" ]; then
        role=$(echo "$line" | jq -r '.message.role // ""' 2>/dev/null)
    fi
    
    # Choose color based on message type
    local color=""
    case "$message_type" in
        "assistant") color="$CYAN" ;;
        "user") color="$GREEN" ;;
        "tool_use") color="$YELLOW" ;;
        "tool_result") color="$MAGENTA" ;;
        *) color="$BLUE" ;;
    esac
    
    # Extract meaningful content
    local content=$(extract_content "$line" "$message_type")
    
    # Format output
    if [ "$COMPACT" = true ]; then
        echo -e "${color}[$timestamp] $content${NC}"
    else
        echo -e "${color}┌─ [$timestamp] $(echo "$message_type" | tr '[:lower:]' '[:upper:]')${NC}"
        echo -e "${color}│  Session: $session_id${NC}"
        [ -n "$uuid" ] && echo -e "${color}│  UUID: $uuid${NC}"
        echo -e "${color}│  $content${NC}"
        echo -e "${color}└─${NC}"
        echo ""
    fi
}

# Main processing function
process_logs() {
    if [ "$FOLLOW" = true ] && [ -n "$LOG_FILE" ]; then
        # Follow mode - tail the file
        echo -e "${BLUE}📺 Following log file: $LOG_FILE${NC}"
        echo -e "${BLUE}Press Ctrl+C to stop${NC}"
        echo ""
        
        tail -f "$LOG_FILE" | while IFS= read -r line; do
            process_json_line "$line"
        done
    elif [ -n "$LOG_FILE" ]; then
        # File mode - process entire file
        echo -e "${BLUE}📄 Processing log file: $LOG_FILE${NC}"
        echo ""
        
        while IFS= read -r line; do
            process_json_line "$line"
        done < "$LOG_FILE"
    else
        # Stdin mode - process piped input
        echo -e "${BLUE}📥 Processing logs from stdin...${NC}"
        echo ""
        
        while IFS= read -r line; do
            process_json_line "$line"
        done
    fi
}

# Validate inputs
if [ -n "$LOG_FILE" ] && [ ! -f "$LOG_FILE" ]; then
    echo -e "${RED}❌ Log file not found: $LOG_FILE${NC}" >&2
    exit 1
fi

# Validate filter
if [ -n "$FILTER" ] && [[ ! "$FILTER" =~ ^(assistant|user|tool_use|tool_result)$ ]]; then
    echo -e "${RED}❌ Invalid filter type: $FILTER${NC}" >&2
    echo -e "${YELLOW}Valid types: assistant, user, tool_use, tool_result${NC}" >&2
    exit 1
fi

# Check if running in pipe mode
if [ -z "$LOG_FILE" ] && [ -t 0 ]; then
    echo -e "${RED}❌ No log file specified and no input piped${NC}" >&2
    show_usage >&2
    exit 1
fi

# Start processing
echo -e "${BLUE}🎯 Claude Log Interpreter v1.0${NC}"
[ -n "$FILTER" ] && echo -e "${BLUE}🔍 Filtering: $FILTER messages${NC}"
[ -n "$SESSION_FILTER" ] && echo -e "${BLUE}🎯 Session: $SESSION_FILTER${NC}"
[ "$COMPACT" = true ] && echo -e "${BLUE}📦 Compact mode enabled${NC}"
echo ""

process_logs