# Claude Log Interpreter

A tool for parsing and displaying Claude JSON logs in a clean, readable format instead of raw JSON.

## Overview

The Claude Log Interpreter (`claude-log-interpreter.sh`) transforms raw Claude JSON messages into human-readable output with color coding, filtering, and real-time following capabilities.

## Features

- **Real-time interpretation**: Parse Claude JSON logs as they're generated
- **Color-coded output**: Different colors for assistant, user, tool use, and tool result messages
- **Compact mode**: One-line summaries for high-density information
- **Filtering**: Filter by message type or session ID
- **Follow mode**: Like `tail -f` for live log monitoring
- **Pipe support**: Works with pipes for real-time processing

## Usage

### Basic Usage

```bash
# Parse a log file
./claude-log-interpreter.sh /tmp/hive-mind-pr-123.log

# Compact format (one line per message)
./claude-log-interpreter.sh --compact /tmp/hive-mind-pr-123.log

# Follow a log file (like tail -f)
./claude-log-interpreter.sh --follow /tmp/hive-mind-pr-123.log

# Filter by message type
./claude-log-interpreter.sh --filter assistant /tmp/hive-mind-pr-123.log

# Filter by session ID
./claude-log-interpreter.sh --session 96ac7824-0618-47e3-9fa0-2d7d000c0a09 /tmp/log.json
```

### Pipe Usage

```bash
# Process logs from stdout
tail -f /tmp/hive-mind-pr-123.log | ./claude-log-interpreter.sh

# Process logs from another command
some-command 2>&1 | ./claude-log-interpreter.sh --compact
```

### Integration with GitHub Scripts

The GitHub automation scripts now use the log interpreter automatically:

```bash
# PR worker with live log interpretation
./.agent/scripts/github-pr-worker.sh

# Issue worker with live log interpretation
./.agent/scripts/github-issue-worker.sh
```

## Message Types & Colors

| Type          | Color   | Icon  | Description                              |
| ------------- | ------- | ----- | ---------------------------------------- |
| `assistant`   | Cyan    | 🔧/💬 | Claude assistant messages and tool usage |
| `user`        | Green   | 👤    | User messages and input                  |
| `tool_use`    | Yellow  | 🔧    | Tool execution requests                  |
| `tool_result` | Magenta | ✅/❌ | Tool execution results (success/error)   |

## Output Formats

### Standard Format

```
┌─ [10:14:07] ASSISTANT
│  Session: 96ac7824-0618-47e3-9fa0-2d7d000c0a09
│  UUID: 058568ae
│  🔧 Using tools: Bash
└─

┌─ [10:14:07] USER
│  Session: 96ac7824-0618-47e3-9fa0-2d7d000c0a09
│  UUID: 23bfe2bb
│  👤 Tool result for git add command
└─
```

### Compact Format

```
[10:14:13] 🔧 Using tools: Bash
[10:14:13] 👤 Tool result for git add command
[10:14:14] 💬 The Docker fixes have been successfully applied!
```

## Integration Details

### GitHub PR Worker Integration

The PR worker script now uses:

```bash
2>&1 | tee "$log_file" | "$SCRIPT_DIR/claude-log-interpreter.sh" --compact
```

This provides:

- **Live interpretation**: See parsed logs in real-time
- **Log preservation**: Raw logs saved to file for debugging
- **Clean output**: No more raw JSON in terminal

### GitHub Issue Worker Integration

Same integration pattern as PR worker, providing consistent user experience across all GitHub automation scripts.

## Command Line Options

| Option          | Short | Description                                                     |
| --------------- | ----- | --------------------------------------------------------------- |
| `--follow`      | `-f`  | Follow log file like `tail -f`                                  |
| `--filter TYPE` |       | Filter by message type (assistant, user, tool_use, tool_result) |
| `--session ID`  |       | Filter by specific session ID                                   |
| `--compact`     |       | Show compact one-line format                                    |
| `--raw`         |       | Show raw JSON for debugging                                     |
| `--help`        | `-h`  | Show help message                                               |

## Examples

### Following Live Logs

```bash
# Follow GitHub PR worker logs
./.agent/scripts/github-pr-worker.sh &
./claude-log-interpreter.sh --follow /tmp/hive-mind-pr-*.log
```

### Debugging Tool Usage

```bash
# Show only tool-related messages
./claude-log-interpreter.sh --filter tool_use /tmp/log.json
./claude-log-interpreter.sh --filter tool_result /tmp/log.json
```

### Session Analysis

```bash
# Analyze specific session
./claude-log-interpreter.sh --session 96ac7824-0618-47e3-9fa0-2d7d000c0a09 /tmp/log.json
```

## Benefits

1. **Improved UX**: No more staring at raw JSON logs
2. **Real-time feedback**: See what's happening as it happens
3. **Better debugging**: Color-coded, structured output makes issues easier to spot
4. **Flexible filtering**: Focus on specific types of messages or sessions
5. **Preserved logs**: Original logs still saved for detailed analysis

## Technical Details

- **Language**: Bash with `jq` for JSON parsing
- **Dependencies**: `jq`, standard UNIX tools (`date`, `tail`, etc.)
- **Performance**: Processes logs line-by-line for real-time operation
- **Compatibility**: Works with any Claude JSON log format
- **Error handling**: Gracefully handles non-JSON lines and malformed input
