# GitHub Automation with Claude Flow

This document describes the comprehensive GitHub automation workflow using Claude Flow hive-mind intelligence for issue management and PR processing.

## Overview

The Aperim Template includes three powerful scripts that work together to provide complete GitHub repository automation:

1. **Issue Selector** - Intelligently prioritizes and selects the most important issue to work on
2. **Issue Worker** - Comprehensively implements issue requirements with testing and creates PRs
3. **PR Worker** - Systematically resolves PR issues and gets them to mergeable state

## Scripts Overview

### 🎯 Issue Selector (`github-issue-selector.sh`)

**Purpose**: Analyzes all open issues using AI to select the highest priority work

**Key Features**:

- Epic identification and dependency mapping
- Priority analysis (P0, P1, critical, high, etc.)
- Business impact assessment
- Technical complexity evaluation
- Age and staleness consideration
- Milestone and sprint alignment
- Best practice selection criteria

**Usage**:

```bash
# Analyze and select best issue
./.agent/scripts/github-issue-selector.sh --repo owner/repository

# Dry run to see analysis without starting work
./.agent/scripts/github-issue-selector.sh --repo owner/repo --dry-run

# Select but don't auto-start work
./.agent/scripts/github-issue-selector.sh --repo owner/repo --no-auto-work
```

### 🔧 Issue Worker (`github-issue-worker.sh`)

**Purpose**: Completely implements issue requirements with comprehensive testing and PR creation

**Key Features**:

- Thorough requirement analysis
- Complete implementation of all issue requirements
- **Mandatory test creation** (even if not explicitly requested)
- Code quality assurance
- Progress updates on the issue
- Automatic PR creation and linking
- Best practice testing implementation

**Usage**:

```bash
# Work on specific issue
./.agent/scripts/github-issue-worker.sh --issue 123 --repo owner/repository

# Work without creating tests (not recommended)
./.agent/scripts/github-issue-worker.sh --issue 123 --repo owner/repo --no-tests

# Work without auto-creating PR
./.agent/scripts/github-issue-worker.sh --issue 123 --repo owner/repo --no-pr
```

### 🔄 PR Worker (`github-pr-worker.sh`)

**Purpose**: Systematically resolves ALL PR issues to get them to mergeable state

**Key Features**:

- Comprehensive PR analysis
- CI/CD failure resolution (ALL failures, no matter how minor)
- Code review comment addressing
- Code quality improvements
- Merge readiness verification
- Optional auto-merge capability

**Usage**:

```bash
# Work on specific PR
./.agent/scripts/github-pr-worker.sh --pr 456 --repo owner/repository

# Work on all open PRs
./.agent/scripts/github-pr-worker.sh --repo owner/repository

# Auto-merge when ready
./.agent/scripts/github-pr-worker.sh --pr 456 --repo owner/repo --auto-merge
```

## Complete Workflow Examples

### 🚀 Full Automation Workflow

```bash
# Step 1: Let AI select the most important issue and work on it
./.agent/scripts/github-issue-selector.sh --repo myorg/project

# This will automatically:
# 1. Analyze all issues for priority and epic relationships
# 2. Select the highest priority issue
# 3. Hand off to issue worker
# 4. Implement all requirements
# 5. Create comprehensive tests
# 6. Create and link PR

# Step 2: Process any existing PRs to get them mergeable
./.agent/scripts/github-pr-worker.sh --repo myorg/project --auto-merge
```

### 🎯 Targeted Issue Work

```bash
# Work on a specific high-priority issue
./.agent/scripts/github-issue-worker.sh --issue 789 --repo myorg/project

# Then ensure the resulting PR gets merged
./.agent/scripts/github-pr-worker.sh --pr [NEW_PR_NUMBER] --repo myorg/project --auto-merge
```

### 🔍 Analysis and Planning

```bash
# Analyze issues without starting work
./.agent/scripts/github-issue-selector.sh --repo myorg/project --dry-run

# See what would be done for a PR without changes
./.agent/scripts/github-pr-worker.sh --pr 123 --repo myorg/project --dry-run
```

## Hive-Mind Architecture

### Multi-Agent Coordination

Each script uses Claude Flow's hive-mind intelligence with specialized agents:

**Issue Selector Agents**:

- `researcher` - Repository and issue analysis
- `analyst` - Data analysis and pattern recognition
- `project-manager` - Priority and milestone evaluation
- `business-analyst` - Business impact assessment
- `technical-architect` - Technical complexity analysis

**Issue Worker Agents**:

- `system-architect` - Implementation planning
- `coder` - Code implementation
- `tester` - Test creation and validation
- `code-reviewer` - Quality assurance
- `technical-writer` - Documentation and PR creation

**PR Worker Agents**:

- `github-workflow-specialist` - CI/CD expertise
- `cicd-engineer` - Build and deployment issues
- `security-analyst` - Security vulnerability fixes
- `code-quality-checker` - Code standards compliance
- `performance-optimizer` - Performance improvements

### Memory and State Management

Each script maintains context through Claude Flow's memory system:

- Issue analysis and requirements
- Implementation progress and decisions
- Code changes and testing strategies
- PR status and merge readiness

## Key Requirements and Guarantees

### ✅ Comprehensive Testing

**CRITICAL**: The issue worker **MUST** create comprehensive tests for any code changes, even if testing isn't explicitly mentioned in the issue. This includes:

- Unit tests for all new functions/methods
- Integration tests for component interactions
- End-to-end tests for user-facing features
- Error condition and edge case testing
- Performance testing where appropriate

### ✅ Complete Issue Implementation

The issue worker ensures **ALL** requirements listed in the issue are fully implemented:

- Every feature request is implemented
- Every bug is fixed
- Every enhancement is completed
- All acceptance criteria are met
- Additional best-practice improvements are included

### ✅ Zero-Defect PR Processing

The PR worker resolves **ALL** issues preventing merge:

- Every CI failure (build, test, lint, security)
- Every code review comment
- Every quality issue
- Every performance concern
- Every documentation gap

## Configuration Options

### Environment Variables

```bash
# Global settings
export CLAUDE_FLOW_DEBUG=true
export CLAUDE_FLOW_MAX_AGENTS=15
export GITHUB_TOKEN=your_github_token

# Performance tuning
export CLAUDE_FLOW_MEMORY_LIMIT=2048
export CLAUDE_FLOW_TIMEOUT=600000
```

### Script Parameters

All scripts support:

- `--dry-run` - Analysis without changes
- `--namespace` - Custom hive-mind namespace
- `--agents` - Maximum agent count
- `--help` - Comprehensive help

## Best Practices

### 🎯 Issue Selection Strategy

1. **Priority First**: Critical issues take precedence
2. **Epic Awareness**: Consider epic relationships and dependencies
3. **Age Balance**: Don't ignore older issues indefinitely
4. **Impact Focus**: Prioritize user-facing and business-critical work
5. **Technical Debt**: Balance feature work with maintenance

### 🔧 Implementation Standards

1. **Test Everything**: Comprehensive testing is mandatory
2. **Document Changes**: Clear commit messages and PR descriptions
3. **Follow Conventions**: Adhere to project coding standards
4. **Security First**: Address security implications
5. **Performance Conscious**: Consider performance impact

### 🔄 PR Management

1. **Address Everything**: No issue is too minor to fix
2. **Quality Gates**: Ensure all quality checks pass
3. **Review Feedback**: Thoroughly address all comments
4. **Merge Readiness**: Verify complete readiness before merge

## Troubleshooting

### Common Issues

**Hive-mind initialization fails**:

```bash
# Check Claude Flow installation
npx --yes claude-flow@alpha --version

# Verify Claude Code integration
claude --version
```

**Memory or namespace conflicts**:

```bash
# List active hives
npx --yes claude-flow@alpha hive-mind sessions

# Clear specific namespace
npx --yes claude-flow@alpha memory usage --action clear --namespace problematic-namespace
```

**API rate limiting**:

```bash
# Check API status
npx --yes claude-flow@alpha health --api

# Configure rate limiting
npx --yes claude-flow@alpha config set providers.github.rateLimit 100
```

### Debug Mode

Enable detailed logging:

```bash
export CLAUDE_FLOW_DEBUG=true
export CLAUDE_FLOW_LOG_LEVEL=debug

# Run scripts with verbose output
./.agent/scripts/github-issue-selector.sh --repo owner/repo --verbose
```

## Integration with CI/CD

### GitHub Actions Integration

Add to your workflow:

```yaml
name: Automated Issue Processing
on:
  schedule:
    - cron: '0 9 * * MON' # Weekly on Monday
  workflow_dispatch:

jobs:
  process-issues:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install Claude Code
        run: npm install -g @anthropic-ai/claude-code

      - name: Process High Priority Issues
        run: ./.agent/scripts/github-issue-selector.sh --repo ${{ github.repository }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
```

### Webhook Integration

Set up webhooks to trigger automation:

```bash
# Trigger on new issues
./.agent/scripts/github-issue-selector.sh --repo owner/repo

# Trigger on PR creation
./.agent/scripts/github-pr-worker.sh --pr $PR_NUMBER --repo owner/repo
```

## Security Considerations

### Access Control

- Scripts require appropriate GitHub token permissions
- Hive-mind memory is isolated per namespace
- All code changes go through PR review process

### API Key Management

- Store API keys securely (environment variables, secrets)
- Use least-privilege access tokens
- Regular key rotation recommended

### Code Security

- All generated code includes security best practices
- Security scanning is part of PR processing
- Vulnerability fixes are prioritized

## Performance Optimization

### Resource Management

- Configure appropriate agent limits for your system
- Use namespaces to isolate hive-mind instances
- Monitor memory usage and cleanup old sessions

### Parallel Processing

- Scripts can run concurrently on different repositories
- Use separate namespaces for parallel operations
- Consider system resource limits

## Future Enhancements

### Planned Features

- Cross-repository epic management
- Advanced priority learning from user feedback
- Integration with project management tools
- Automated performance benchmarking
- Custom agent specialization

### Community Contributions

- Submit feature requests via GitHub issues
- Contribute improvements via pull requests
- Share configuration examples and best practices

---

## Quick Reference

### Essential Commands

```bash
# Complete automation
./.agent/scripts/github-issue-selector.sh --repo owner/repo

# Specific issue work
./.agent/scripts/github-issue-worker.sh --issue 123 --repo owner/repo

# PR cleanup
./.agent/scripts/github-pr-worker.sh --repo owner/repo --auto-merge

# Analysis only
./.agent/scripts/github-issue-selector.sh --repo owner/repo --dry-run
```

### Key Files

- `github-issue-selector.sh` - Issue prioritization and selection
- `github-issue-worker.sh` - Complete issue implementation
- `github-pr-worker.sh` - PR issue resolution and merge preparation

### Support

- Check script help: `script.sh --help`
- Review hive-mind status: `npx --yes claude-flow@alpha hive-mind status`
- Debug with: `export CLAUDE_FLOW_DEBUG=true`

---

**Built with Claude Flow v2.0.0 Alpha - Intelligent AI Agent Orchestration**

_These automation scripts represent the future of AI-powered development workflow management._
