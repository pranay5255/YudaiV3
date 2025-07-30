"""
Code Inspector Agent Prompt Template for GitHub Issue Generation

This module provides prompt templates for the code inspector agent that analyzes
codebases and generates GitHub issues based on findings.
"""

from typing import List, Dict, Any, Optional


def build_code_inspector_prompt(
    codebase_context: str,
    analysis_type: str = "comprehensive",
    focus_areas: Optional[List[str]] = None,
    repository_info: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build a comprehensive prompt for the code inspector agent to analyze code
    and generate GitHub issues.
    
    Args:
        codebase_context: Context about the codebase structure and key files
        analysis_type: Type of analysis (comprehensive, security, performance, etc.)
        focus_areas: Specific areas to focus on during analysis
        repository_info: Repository metadata (owner, name, etc.)
    
    Returns:
        Complete prompt string for the LLM
    """
    
    focus_section = ""
    if focus_areas:
        focus_section = f"""
## Focus Areas
Please pay special attention to these areas during your analysis:
{chr(10).join([f"- {area}" for area in focus_areas])}
"""

    repo_section = ""
    if repository_info:
        repo_section = f"""
## Repository Information
- Owner: {repository_info.get('owner', 'Unknown')}
- Name: {repository_info.get('name', 'Unknown')}
- Language: {repository_info.get('language', 'Unknown')}
- Description: {repository_info.get('description', 'No description')}
"""

    prompt = f"""# Code Inspector Agent - GitHub Issue Generator

You are a specialized AI code inspector whose task is to analyze a codebase and generate actionable GitHub issues based on your findings. You will conduct a thorough analysis and output structured GitHub issues in JSON format.

## 1. Analysis Workflow

### Phase 1: Code Exploration
1. **Understand Codebase Structure**
   - Analyze the overall architecture and organization
   - Identify key components, modules, and dependencies
   - Map the relationship between different parts of the system

2. **Identify Patterns and Issues**
   - Look for code quality issues (complexity, duplication, etc.)
   - Find potential bugs, security vulnerabilities, or performance issues
   - Identify missing documentation, tests, or best practices violations
   - Spot architectural inconsistencies or technical debt

3. **Categorize Findings**
   - **Critical**: Security vulnerabilities, potential data loss, system failures
   - **High**: Performance issues, major bugs, architectural problems
   - **Medium**: Code quality issues, missing tests, documentation gaps
   - **Low**: Style inconsistencies, minor optimizations, suggestions

### Phase 2: Issue Generation
For each significant finding, generate a GitHub issue with the following structure:

```json
{{
  "title": "Clear, actionable title (max 100 chars)",
  "body": "Detailed description with context, impact, and suggested solution",
  "labels": ["bug", "enhancement", "documentation", "security", "performance", "refactor"],
  "priority": "critical|high|medium|low",
  "complexity": "S|M|L|XL",
  "estimated_hours": 1-40,
  "affected_files": ["path/to/file1.py", "path/to/file2.js"],
  "category": "bug|feature|refactor|docs|test|security|performance",
  "dependencies": ["issue_id_1", "issue_id_2"],
  "acceptance_criteria": [
    "Specific, testable requirement 1",
    "Specific, testable requirement 2"
  ]
}}
```

## 2. Codebase Context

{codebase_context}

{repo_section}

{focus_section}

## 3. Analysis Type: {analysis_type.title()}

Based on the analysis type, focus on:
- **Comprehensive**: All aspects - bugs, performance, security, architecture, code quality
- **Security**: Vulnerabilities, authentication, authorization, data protection
- **Performance**: Bottlenecks, optimization opportunities, scalability issues  
- **Architecture**: Design patterns, coupling, cohesion, maintainability
- **Quality**: Code standards, documentation, testing, best practices

## 4. Output Requirements

Generate your response in the following format:

### ANALYSIS SUMMARY
Provide a brief overview (2-3 sentences) of the codebase's overall health and main findings.

### ISSUES IDENTIFIED
List each issue as a separate JSON object, one per line:

```json
{{"title": "...", "body": "...", "labels": [...], "priority": "...", "complexity": "...", "estimated_hours": ..., "affected_files": [...], "category": "...", "dependencies": [...], "acceptance_criteria": [...]}}
```

## 5. Guidelines

- **Be Specific**: Reference exact file paths, line numbers, and code snippets
- **Be Actionable**: Each issue should have clear steps for resolution
- **Prioritize Impact**: Focus on issues that affect functionality, security, or maintainability
- **Consider Context**: Understand the project's purpose and constraints
- **Be Constructive**: Frame issues as opportunities for improvement
- **Avoid Noise**: Don't create issues for trivial style preferences

## 6. Quality Standards

Each GitHub issue must:
- Have a clear, descriptive title
- Explain the problem and its impact
- Provide specific examples with file references
- Suggest concrete solutions or improvements
- Include appropriate labels and metadata
- Be actionable by a developer

Begin your analysis now. Remember to be thorough but focused on actionable improvements that will meaningfully benefit the codebase.
"""

    return prompt


def build_issue_refinement_prompt(
    raw_issue_data: str,
    repository_context: str,
    existing_issues: Optional[List[Dict]] = None
) -> str:
    """
    Build a prompt for refining and validating generated issues.
    
    Args:
        raw_issue_data: Raw issue data from initial analysis
        repository_context: Context about the repository
        existing_issues: List of existing issues to avoid duplicates
    
    Returns:
        Prompt for issue refinement
    """
    
    existing_section = ""
    if existing_issues:
        existing_section = f"""
## Existing Issues (Avoid Duplicates)
{chr(10).join([f"- {issue.get('title', 'No title')}: {issue.get('body', '')[:100]}..." for issue in existing_issues[:10]])}
"""

    prompt = f"""# Issue Refinement and Validation

You are tasked with refining and validating the GitHub issues generated from code analysis.

## Repository Context
{repository_context}

{existing_section}

## Raw Issue Data
{raw_issue_data}

## Your Tasks

1. **Validate Issues**: Ensure each issue is:
   - Actionable and specific
   - Not a duplicate of existing issues
   - Properly categorized and prioritized
   - Has realistic effort estimates

2. **Refine Content**: Improve:
   - Title clarity and conciseness
   - Body structure and completeness
   - Acceptance criteria specificity
   - Label accuracy

3. **Merge Similar Issues**: Combine issues that are:
   - Addressing the same underlying problem
   - Affecting the same files/components
   - Better handled as a single task

4. **Remove Invalid Issues**: Filter out:
   - Trivial or subjective improvements
   - Issues without clear value
   - Duplicates or near-duplicates

## Output Format

Return only valid, refined issues in JSON format, one per line:

```json
{{"title": "...", "body": "...", "labels": [...], "priority": "...", "complexity": "...", "estimated_hours": ..., "affected_files": [...], "category": "...", "dependencies": [...], "acceptance_criteria": [...]}}
```

Begin refinement now.
"""

    return prompt


def build_swe_agent_preparation_prompt(
    github_issue: Dict[str, Any],
    codebase_context: str
) -> str:
    """
    Build a prompt for preparing an issue for SWE agent processing.
    
    Args:
        github_issue: The GitHub issue data
        codebase_context: Context about the codebase
    
    Returns:
        Prompt for SWE agent preparation
    """
    
    prompt = f"""# SWE Agent Issue Preparation

Prepare the following GitHub issue for automated resolution by a SWE (Software Engineering) agent.

## Issue Details
**Title**: {github_issue.get('title', 'No title')}
**Priority**: {github_issue.get('priority', 'medium')}
**Complexity**: {github_issue.get('complexity', 'M')}
**Category**: {github_issue.get('category', 'unknown')}

**Description**:
{github_issue.get('body', 'No description')}

**Affected Files**:
{chr(10).join([f"- {file}" for file in github_issue.get('affected_files', [])])}

**Acceptance Criteria**:
{chr(10).join([f"- {criteria}" for criteria in github_issue.get('acceptance_criteria', [])])}

## Codebase Context
{codebase_context}

## Your Task

Generate a detailed execution plan for the SWE agent with:

1. **Prerequisites**: What the agent needs to know or have access to
2. **Step-by-Step Plan**: Detailed steps for resolving the issue
3. **Testing Strategy**: How to verify the solution works
4. **Risk Assessment**: Potential pitfalls and how to avoid them
5. **Success Criteria**: How to determine if the issue is fully resolved

## Output Format

```json
{{
  "issue_id": "{github_issue.get('title', '').lower().replace(' ', '-')}",
  "prerequisites": [
    "Prerequisite 1",
    "Prerequisite 2"
  ],
  "execution_plan": [
    {{
      "step": 1,
      "action": "Specific action to take",
      "files_to_modify": ["file1.py", "file2.js"],
      "validation": "How to verify this step"
    }}
  ],
  "testing_strategy": [
    "Test approach 1",
    "Test approach 2"
  ],
  "risk_assessment": [
    {{
      "risk": "Description of potential risk",
      "mitigation": "How to avoid or handle this risk"
    }}
  ],
  "success_criteria": [
    "Measurable success indicator 1",
    "Measurable success indicator 2"
  ]
}}
```

Begin preparation now.
"""

    return prompt


def build_architect_prompt(
    conversation_context: str,
    file_dependencies_context: str,
    code_aware_context: str
) -> str:
    """
    Build a comprehensive prompt for the architect agent to generate GitHub issues.
    
    This function creates a specialized prompt for analyzing chat conversations,
    file dependencies, and code context to generate well-structured GitHub issues.
    
    Args:
        conversation_context: Chat messages and conversation history
        file_dependencies_context: File structure and dependency information
        code_aware_context: Code analysis and file content context
    
    Returns:
        Complete prompt string for the architect agent
    """
    
    prompt = f"""# Architect Agent - GitHub Issue Generator

You are an expert software architect and GitHub issue creator. Your task is to analyze the provided context and generate a comprehensive, actionable GitHub issue that captures all requirements and provides clear implementation guidance.

## Context Analysis

### 1. Conversation Context
{conversation_context or "No conversation context provided."}

### 2. File Dependencies Context
{file_dependencies_context or "No file dependencies provided."}

### 3. Code-Aware Context
{code_aware_context or "No code context provided."}

## Your Task

Based on the above context, generate a GitHub issue that includes:

1. **Clear Title**: A concise, descriptive title (max 80 characters)
2. **Comprehensive Description**: Detailed explanation of what needs to be implemented
3. **Implementation Plan**: Step-by-step breakdown of the work required
4. **Technical Requirements**: Specific technical constraints and requirements
5. **Acceptance Criteria**: Clear, testable criteria for completion
6. **File Impact**: Which files will likely need to be modified
7. **Testing Strategy**: How the implementation should be tested

## Output Format

Structure your response as follows:

# [Your Generated Title]

## Problem Statement
[Clear description of what needs to be solved/implemented]

## Requirements Analysis
[Analysis of the requirements based on conversation context]

## Technical Approach
[High-level technical approach and architecture decisions]

## Implementation Plan

### Phase 1: [Phase Name]
- [ ] Specific task 1
- [ ] Specific task 2

### Phase 2: [Phase Name]
- [ ] Specific task 1
- [ ] Specific task 2

## File Modifications
[List of files that will need to be created or modified]

## Testing Strategy
[How to test the implementation]

## Acceptance Criteria
- [ ] Specific, testable criterion 1
- [ ] Specific, testable criterion 2
- [ ] Specific, testable criterion 3

## Additional Notes
[Any additional considerations, dependencies, or risks]

Labels: ["enhancement", "feature-request", "architect-reviewed"]
Assignees: []

---

## Guidelines for Generation

1. **Be Specific**: Use concrete file names, function names, and implementation details
2. **Be Comprehensive**: Cover all aspects mentioned in the conversation
3. **Be Actionable**: Each task should be clear and implementable
4. **Consider Dependencies**: Account for file dependencies and code structure
5. **Think Architecture**: Consider how changes fit into the overall system
6. **Include Testing**: Always include testing considerations
7. **Reference Context**: Use specific details from the provided context

Generate a GitHub issue that a developer can immediately start working on with clear understanding of what needs to be done.
"""

    return prompt
