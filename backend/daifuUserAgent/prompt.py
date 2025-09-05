# DAifu Prompt Template
"""Utility to build prompts for the DAifu agent."""
from textwrap import dedent
from typing import Any, Dict, List, Tuple

SYSTEM_HEADER = dedent(
    """
    You are **DAifu**, an AI assistant specialized in GitHub repository management and issue creation.
    Your primary role is to help users create clear, actionable GitHub issues from their conversations
    and repository context.

    **Core Responsibilities:**
    1. Analyze user requests and repository context to create well-structured GitHub issues
    2. Provide direct, professional responses based on available context
    3. Suggest next steps and improvements when appropriate
    4. Maintain focus on actionable outcomes

    **Response Guidelines:**
    - Be direct and professional in all communications
    - Use repository context to provide informed responses
    - Focus on creating clear, actionable GitHub issues when requested
    - Ask for clarification only when essential information is missing
    - Provide specific recommendations based on repository data

    **Output Format:**
    When creating issues, structure them with:
    - Clear, descriptive titles
    - Detailed descriptions including context and requirements
    - Appropriate labels and metadata
    """
).strip()


def build_daifu_prompt(
    repo_details: Dict[str, Any],
    commits: List[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    pulls: List[Dict[str, Any]],
    conversation: List[Tuple[str, str]],
    file_contexts: List[str] = None
) -> str:
    """Return the complete prompt string for DAifu."""
    # Format repository details
    details_str = (
        f"Repository: {repo_details['full_name']}\n"
        f"Description: {repo_details.get('description','')}\n"
        f"Default branch: {repo_details.get('default_branch','')}\n"
        f"Languages: {', '.join(repo_details.get('languages', {}).keys())}\n"
        f"Topics: {', '.join(repo_details.get('topics', []))}\n"
        f"License: {repo_details.get('license', {}).get('name') if repo_details.get('license') else 'None'}\n"
        f"Stars: {repo_details.get('stargazers_count',0)}, Forks: {repo_details.get('forks_count',0)}\n"
        f"Open issues: {repo_details.get('open_issues_count',0)}\n"
        f"URL: {repo_details.get('html_url','')}\n"
    )

    # Format recent commits (limit to 5 for brevity)
    commits_str = "Recent Commits:\n"
    for c in commits[:5]:
        commits_str += (
            f"- {c['sha'][:7]}: {c['message'].splitlines()[0]} "
            f"(by {c['author'].get('name','?')} at {c['author'].get('date','')})\n"
        )

    # Format open issues (limit to 5)
    issues_str = "Open Issues:\n"
    open_issues = [i for i in issues if i['state'] == 'open'][:5]
    for i in open_issues:
        issues_str += (
            f"- #{i['number']}: {i['title']} (by {i['user'].get('login','?')})\n"
        )

    # Format open pull requests (limit to 5)
    pulls_str = "Open Pull Requests:\n"
    open_pulls = [p for p in pulls if p['state'] == 'open'][:5]
    for p in open_pulls:
        pulls_str += (
            f"- #{p['number']}: {p['title']} (by {p['user'].get('login','?')})\n"
        )

    # Format file contexts if provided
    file_contexts_str = ""
    if file_contexts:
        file_contexts_str = "Relevant File Contexts:\n" + "\n".join(file_contexts)

    # Format conversation
    convo_formatted = "\n".join(f"{speaker}: {utterance}" for speaker, utterance in conversation)

    # Combine all into final prompt
    prompt = dedent(
        f"""
        {SYSTEM_HEADER}

        <GITHUB_CONTEXT_BEGIN>
        {details_str}
        {commits_str}
        {issues_str}
        {pulls_str}
        </GITHUB_CONTEXT_END>

        <FILE_CONTEXTS_BEGIN>
        {file_contexts_str}
        </FILE_CONTEXTS_END>

        <CONVERSATION_BEGIN>
        {convo_formatted}
        </CONVERSATION_END>

        (Respond now as **DAifu** following the guidelines above. Focus on providing direct, actionable responses based on the available context.)
        """
    ).strip()
    return prompt

# Note: GitHub context fetching is now handled by ChatOps class using GitHubOps
# This ensures consistent data fetching and error handling across the application