# """
# Architecture Agent Package

# This package contains the Code Inspector Agent that analyzes codebases
# and generates GitHub issues for automated resolution.

# Main Components:
# - CodeInspectorAgent: Core agent for codebase analysis
# - CodeInspectorService: Service layer for agent operations
# - Prompt templates for LLM interactions
# """

# from .code_inspector_service import CodeInspectorAgent, CodeInspectorService
# from .promptTemplate import (
#     build_code_inspector_prompt,
#     build_issue_refinement_prompt,
#     build_swe_agent_preparation_prompt
# )

# __all__ = [
#     "CodeInspectorAgent",
#     "CodeInspectorService", 
#     "build_code_inspector_prompt",
#     "build_issue_refinement_prompt",
#     "build_swe_agent_preparation_prompt"
# ]

# __version__ = "1.0.0" 