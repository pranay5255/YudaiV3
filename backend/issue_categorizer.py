"""
GitHub Issue Categorization System
Classifies GitHub issues into multiple categories and generates context graphs
for preprocessing and context retrieval.
"""

import re
import json
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pydantic import BaseModel, Field
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IssueCategory(str, Enum):
    """Enumeration of issue categories for classification"""
    BUG_FIX = "bug_fix"
    TEST_INNOVATION = "test_innovation"  # test innovating & for <service>
    TEST_COVERAGE = "test_coverage"      # test-coverage & add tests
    CICD_GITHUB_ACTIONS = "cicd_github_actions"
    CICD_DOCKER = "cicd_docker"          # CICD - Docker containerisation
    REFACTOR = "refactor"
    FEATURE_SCAFFOLDING = "feature_scaffolding"
    DOCS_UPDATE = "docs_update"
    DOCS_CREATE = "docs_create"
    DATA_MODELS_PYDANTIC = "data_models_pydantic"
    DB_MODELS_SQLALCHEMY = "db_models_sqlalchemy"
    POSTGRES_DB = "postgres_db"


@dataclass
class ContextGraph:
    """Context graph definition for each category"""
    category: IssueCategory
    relevant_files: List[str]
    relevant_directories: List[str]
    github_labels: List[str]
    dependencies: List[str]
    system_prompts: List[str]
    preprocessing_steps: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IssueCategorizer:
    """Main categorization engine for GitHub issues"""
    
    def __init__(self):
        self.keywords_map = self._initialize_keywords()
        self.context_graphs = self._initialize_context_graphs()
        
    def _initialize_keywords(self) -> Dict[IssueCategory, Dict[str, List[str]]]:
        """Initialize keyword mappings for each category"""
        return {
            IssueCategory.BUG_FIX: {
                "title_keywords": [
                    "bug", "fix", "error", "issue", "broken", "crash", "fail", 
                    "exception", "incorrect", "wrong", "not working", "problem"
                ],
                "body_keywords": [
                    "traceback", "stack trace", "error message", "reproduce", 
                    "expected", "actual", "steps to reproduce", "console error"
                ],
                "label_keywords": ["bug", "error", "hotfix"]
            },
            
            IssueCategory.TEST_INNOVATION: {
                "title_keywords": [
                    "test innovation", "testing framework", "test automation", 
                    "test architecture", "testing strategy", "test modernization"
                ],
                "body_keywords": [
                    "pytest", "vitest", "test runner", "test framework", 
                    "testing patterns", "test utilities", "test infrastructure"
                ],
                "label_keywords": ["testing", "innovation", "framework"]
            },
            
            IssueCategory.TEST_COVERAGE: {
                "title_keywords": [
                    "test coverage", "add tests", "unit test", "integration test",
                    "test missing", "coverage", "untested"
                ],
                "body_keywords": [
                    "coverage report", "test cases", "assertions", "mock", 
                    "test data", "coverage percentage", "uncovered lines"
                ],
                "label_keywords": ["testing", "coverage", "quality"]
            },
            
            IssueCategory.CICD_GITHUB_ACTIONS: {
                "title_keywords": [
                    "github actions", "workflow", "ci/cd", "pipeline", 
                    "automation", "deploy", "build"
                ],
                "body_keywords": [
                    ".github/workflows", "action", "runner", "workflow file",
                    "continuous integration", "continuous deployment"
                ],
                "label_keywords": ["ci/cd", "github-actions", "automation"]
            },
            
            IssueCategory.CICD_DOCKER: {
                "title_keywords": [
                    "docker", "container", "dockerfile", "docker-compose",
                    "containerization", "image", "registry"
                ],
                "body_keywords": [
                    "docker build", "docker run", "container image", 
                    "docker-compose.yml", "containerize", "port mapping"
                ],
                "label_keywords": ["docker", "container", "devops"]
            },
            
            IssueCategory.REFACTOR: {
                "title_keywords": [
                    "refactor", "refactoring", "cleanup", "optimize", 
                    "restructure", "improve", "modernize"
                ],
                "body_keywords": [
                    "code quality", "technical debt", "clean code", 
                    "performance", "maintainability", "architecture"
                ],
                "label_keywords": ["refactor", "cleanup", "improvement"]
            },
            
            IssueCategory.FEATURE_SCAFFOLDING: {
                "title_keywords": [
                    "scaffold", "scaffolding", "boilerplate", "template", 
                    "generator", "setup", "initialize"
                ],
                "body_keywords": [
                    "project structure", "initial setup", "base template",
                    "code generation", "starter code"
                ],
                "label_keywords": ["scaffolding", "setup", "template"]
            },
            
            IssueCategory.DOCS_UPDATE: {
                "title_keywords": [
                    "docs update", "documentation update", "readme update",
                    "update docs", "fix documentation"
                ],
                "body_keywords": [
                    "outdated documentation", "incorrect docs", "update readme",
                    "documentation fix", "docs improvement"
                ],
                "label_keywords": ["documentation", "docs", "readme"]
            },
            
            IssueCategory.DOCS_CREATE: {
                "title_keywords": [
                    "docs create", "create documentation", "add documentation",
                    "new docs", "documentation needed"
                ],
                "body_keywords": [
                    "missing documentation", "create readme", "add docs",
                    "document feature", "api documentation"
                ],
                "label_keywords": ["documentation", "docs", "new-docs"]
            },
            
            IssueCategory.DATA_MODELS_PYDANTIC: {
                "title_keywords": [
                    "pydantic", "data model", "schema", "validation",
                    "serialization", "model definition"
                ],
                "body_keywords": [
                    "BaseModel", "pydantic model", "field validation",
                    "serialization", "data validation", "schema definition"
                ],
                "label_keywords": ["pydantic", "models", "validation"]
            },
            
            IssueCategory.DB_MODELS_SQLALCHEMY: {
                "title_keywords": [
                    "sqlalchemy", "db model", "database model", "orm",
                    "table definition", "relationship"
                ],
                "body_keywords": [
                    "sqlalchemy model", "database table", "foreign key",
                    "relationship", "orm mapping", "database schema"
                ],
                "label_keywords": ["sqlalchemy", "database", "orm"]
            },
            
            IssueCategory.POSTGRES_DB: {
                "title_keywords": [
                    "postgres", "postgresql", "database", "sql", "query",
                    "migration", "schema"
                ],
                "body_keywords": [
                    "postgresql", "postgres", "database connection", "sql query",
                    "database migration", "psql", "pg_"
                ],
                "label_keywords": ["postgres", "database", "sql"]
            }
        }
    
    def _initialize_context_graphs(self) -> Dict[IssueCategory, ContextGraph]:
        """Initialize context graphs for each category"""
        return {
            IssueCategory.BUG_FIX: ContextGraph(
                category=IssueCategory.BUG_FIX,
                relevant_files=[
                    "backend/models.py", "src/App.tsx", "backend/run_server.py",
                    "requirements.txt", "package.json", "*.log"
                ],
                relevant_directories=[
                    "backend/", "src/", "tests/", "backend/tests/"
                ],
                github_labels=["bug", "hotfix", "critical"],
                dependencies=[
                    "fastapi", "react", "sqlalchemy", "pydantic", "pytest", "vitest"
                ],
                system_prompts=[
                    "debug_mode_prompt", "error_analysis_prompt", "fix_validation_prompt"
                ],
                preprocessing_steps=[
                    "extract_error_logs", "identify_failing_tests", 
                    "gather_reproduction_steps", "check_recent_changes"
                ]
            ),
            
            IssueCategory.TEST_INNOVATION: ContextGraph(
                category=IssueCategory.TEST_INNOVATION,
                relevant_files=[
                    "vitest.config.ts", "pytest.ini", "backend/tests/", "tests/",
                    "pyproject.toml", "package.json"
                ],
                relevant_directories=[
                    "tests/", "backend/tests/", "src/", "backend/"
                ],
                github_labels=["testing", "framework", "innovation"],
                dependencies=[
                    "pytest", "vitest", "pytest-cov", "testing-library"
                ],
                system_prompts=[
                    "testing_expert_prompt", "framework_selection_prompt", 
                    "test_architecture_prompt"
                ],
                preprocessing_steps=[
                    "analyze_current_testing_stack", "identify_testing_gaps",
                    "research_modern_testing_patterns", "evaluate_frameworks"
                ]
            ),
            
            IssueCategory.TEST_COVERAGE: ContextGraph(
                category=IssueCategory.TEST_COVERAGE,
                relevant_files=[
                    "backend/models.py", "src/components/", "backend/db/",
                    "coverage.xml", ".coveragerc", "vitest.config.ts"
                ],
                relevant_directories=[
                    "src/", "backend/", "tests/", "backend/tests/"
                ],
                github_labels=["testing", "coverage", "quality"],
                dependencies=[
                    "pytest-cov", "coverage", "@vitest/coverage"
                ],
                system_prompts=[
                    "test_writing_prompt", "coverage_analysis_prompt",
                    "quality_assurance_prompt"
                ],
                preprocessing_steps=[
                    "generate_coverage_report", "identify_uncovered_code",
                    "prioritize_test_targets", "analyze_critical_paths"
                ]
            ),
            
            IssueCategory.CICD_GITHUB_ACTIONS: ContextGraph(
                category=IssueCategory.CICD_GITHUB_ACTIONS,
                relevant_files=[
                    ".github/workflows/", "package.json", "pyproject.toml",
                    "requirements.txt", "Dockerfile"
                ],
                relevant_directories=[
                    ".github/", ".github/workflows/", "scripts/"
                ],
                github_labels=["ci/cd", "github-actions", "automation"],
                dependencies=[
                    "github-actions", "workflow-tools"
                ],
                system_prompts=[
                    "cicd_expert_prompt", "workflow_design_prompt",
                    "automation_prompt"
                ],
                preprocessing_steps=[
                    "analyze_existing_workflows", "identify_automation_needs",
                    "review_deployment_strategy", "check_security_practices"
                ]
            ),
            
            IssueCategory.CICD_DOCKER: ContextGraph(
                category=IssueCategory.CICD_DOCKER,
                relevant_files=[
                    "Dockerfile", "docker-compose.yml", "backend/Dockerfile",
                    "nginx.conf", ".dockerignore"
                ],
                relevant_directories=[
                    ".", "backend/", "config/"
                ],
                github_labels=["docker", "containerization", "devops"],
                dependencies=[
                    "docker", "docker-compose"
                ],
                system_prompts=[
                    "docker_expert_prompt", "containerization_prompt",
                    "deployment_optimization_prompt"
                ],
                preprocessing_steps=[
                    "analyze_container_structure", "review_multi_stage_builds",
                    "check_security_best_practices", "optimize_image_size"
                ]
            ),
            
            IssueCategory.REFACTOR: ContextGraph(
                category=IssueCategory.REFACTOR,
                relevant_files=[
                    "backend/models.py", "src/App.tsx", "src/components/",
                    "backend/run_server.py", "pyproject.toml"
                ],
                relevant_directories=[
                    "src/", "backend/", "src/components/", "backend/db/"
                ],
                github_labels=["refactor", "improvement", "technical-debt"],
                dependencies=[
                    "ruff", "eslint", "mypy", "typescript"
                ],
                system_prompts=[
                    "refactoring_expert_prompt", "code_quality_prompt",
                    "architecture_improvement_prompt"
                ],
                preprocessing_steps=[
                    "analyze_code_complexity", "identify_patterns",
                    "check_coupling_cohesion", "review_naming_conventions"
                ]
            ),
            
            IssueCategory.FEATURE_SCAFFOLDING: ContextGraph(
                category=IssueCategory.FEATURE_SCAFFOLDING,
                relevant_files=[
                    "backend/models.py", "src/components/", "backend/run_server.py",
                    "pyproject.toml", "package.json"
                ],
                relevant_directories=[
                    "src/", "backend/", "scripts/", "config/"
                ],
                github_labels=["feature", "scaffolding", "setup"],
                dependencies=[
                    "cookiecutter", "yeoman", "plop"
                ],
                system_prompts=[
                    "scaffolding_expert_prompt", "architecture_design_prompt",
                    "boilerplate_generation_prompt"
                ],
                preprocessing_steps=[
                    "analyze_project_structure", "identify_patterns",
                    "review_existing_scaffolds", "design_templates"
                ]
            ),
            
            IssueCategory.DOCS_UPDATE: ContextGraph(
                category=IssueCategory.DOCS_UPDATE,
                relevant_files=[
                    "README.md", "docs/", "*.md", "backend/README.md"
                ],
                relevant_directories=[
                    "docs/", ".", "backend/"
                ],
                github_labels=["documentation", "update", "readme"],
                dependencies=[
                    "mkdocs", "mkdocs-material"
                ],
                system_prompts=[
                    "documentation_writer_prompt", "technical_writer_prompt",
                    "docs_review_prompt"
                ],
                preprocessing_steps=[
                    "audit_existing_docs", "identify_outdated_content",
                    "check_link_validity", "review_accuracy"
                ]
            ),
            
            IssueCategory.DOCS_CREATE: ContextGraph(
                category=IssueCategory.DOCS_CREATE,
                relevant_files=[
                    "backend/models.py", "src/", "pyproject.toml", "package.json"
                ],
                relevant_directories=[
                    "src/", "backend/", "docs/"
                ],
                github_labels=["documentation", "new-docs", "readme"],
                dependencies=[
                    "mkdocs", "mkdocs-material", "sphinx"
                ],
                system_prompts=[
                    "documentation_creator_prompt", "api_docs_prompt",
                    "user_guide_prompt"
                ],
                preprocessing_steps=[
                    "analyze_undocumented_features", "identify_user_journeys",
                    "review_api_endpoints", "gather_examples"
                ]
            ),
            
            IssueCategory.DATA_MODELS_PYDANTIC: ContextGraph(
                category=IssueCategory.DATA_MODELS_PYDANTIC,
                relevant_files=[
                    "backend/models.py", "backend/db/", "src/types.ts"
                ],
                relevant_directories=[
                    "backend/", "backend/db/", "src/"
                ],
                github_labels=["pydantic", "models", "validation"],
                dependencies=[
                    "pydantic", "pydantic-settings"
                ],
                system_prompts=[
                    "pydantic_expert_prompt", "data_modeling_prompt",
                    "validation_design_prompt"
                ],
                preprocessing_steps=[
                    "analyze_data_flow", "review_validation_rules",
                    "check_serialization_patterns", "identify_model_relationships"
                ]
            ),
            
            IssueCategory.DB_MODELS_SQLALCHEMY: ContextGraph(
                category=IssueCategory.DB_MODELS_SQLALCHEMY,
                relevant_files=[
                    "backend/models.py", "backend/db/", "backend/test_db.py"
                ],
                relevant_directories=[
                    "backend/", "backend/db/"
                ],
                github_labels=["sqlalchemy", "database", "orm"],
                dependencies=[
                    "sqlalchemy", "psycopg2-binary", "alembic"
                ],
                system_prompts=[
                    "sqlalchemy_expert_prompt", "database_design_prompt",
                    "orm_optimization_prompt"
                ],
                preprocessing_steps=[
                    "analyze_database_schema", "review_relationships",
                    "check_migration_history", "optimize_queries"
                ]
            ),
            
            IssueCategory.POSTGRES_DB: ContextGraph(
                category=IssueCategory.POSTGRES_DB,
                relevant_files=[
                    "backend/db/", "backend/models.py", "docker-compose.yml",
                    "backend/test_db.py"
                ],
                relevant_directories=[
                    "backend/db/", "config/"
                ],
                github_labels=["postgres", "database", "sql"],
                dependencies=[
                    "psycopg2-binary", "sqlalchemy"
                ],
                system_prompts=[
                    "postgres_expert_prompt", "database_admin_prompt",
                    "performance_tuning_prompt"
                ],
                preprocessing_steps=[
                    "analyze_database_performance", "review_indexes",
                    "check_connection_pooling", "audit_security"
                ]
            )
        }
    
    def classify_issue(self, title: str, body: str, labels: List[str]) -> Tuple[List[IssueCategory], Dict[str, float]]:
        """
        Classify a GitHub issue into categories
        
        Args:
            title: Issue title
            body: Issue description
            labels: Existing GitHub labels
            
        Returns:
            Tuple of (categories, confidence_scores)
        """
        title_lower = title.lower()
        body_lower = body.lower()
        labels_lower = [label.lower() for label in labels]
        
        category_scores = {}
        
        for category, keywords in self.keywords_map.items():
            score = 0.0
            
            # Title keyword matching (higher weight)
            title_matches = sum(1 for keyword in keywords["title_keywords"] 
                              if keyword in title_lower)
            score += title_matches * 3.0
            
            # Body keyword matching
            body_matches = sum(1 for keyword in keywords["body_keywords"] 
                             if keyword in body_lower)
            score += body_matches * 1.5
            
            # Label matching (highest weight)
            label_matches = sum(1 for keyword in keywords["label_keywords"] 
                              for label in labels_lower if keyword in label)
            score += label_matches * 5.0
            
            # Normalize score
            total_keywords = (len(keywords["title_keywords"]) + 
                            len(keywords["body_keywords"]) + 
                            len(keywords["label_keywords"]))
            
            if total_keywords > 0:
                category_scores[category] = score / total_keywords
        
        # Filter categories with minimum confidence threshold
        min_confidence = 0.1
        relevant_categories = [
            category for category, score in category_scores.items() 
            if score >= min_confidence
        ]
        
        # Sort by confidence
        relevant_categories.sort(key=lambda c: category_scores[c], reverse=True)
        
        return relevant_categories, category_scores
    
    def get_context_graph(self, category: IssueCategory) -> ContextGraph:
        """Get the context graph for a specific category"""
        return self.context_graphs.get(category)
    
    def get_system_prompt_template(self, categories: List[IssueCategory]) -> Dict[str, Any]:
        """
        Generate system prompt template based on categories
        
        Args:
            categories: List of issue categories
            
        Returns:
            Dictionary containing combined system prompt information
        """
        combined_context = {
            "categories": [cat.value for cat in categories],
            "relevant_files": set(),
            "relevant_directories": set(),
            "dependencies": set(),
            "system_prompts": [],
            "preprocessing_steps": []
        }
        
        for category in categories:
            context_graph = self.get_context_graph(category)
            if context_graph:
                combined_context["relevant_files"].update(context_graph.relevant_files)
                combined_context["relevant_directories"].update(context_graph.relevant_directories)
                combined_context["dependencies"].update(context_graph.dependencies)
                combined_context["system_prompts"].extend(context_graph.system_prompts)
                combined_context["preprocessing_steps"].extend(context_graph.preprocessing_steps)
        
        # Convert sets back to lists for JSON serialization
        combined_context["relevant_files"] = list(combined_context["relevant_files"])
        combined_context["relevant_directories"] = list(combined_context["relevant_directories"])
        combined_context["dependencies"] = list(combined_context["dependencies"])
        
        return combined_context
    
    def process_github_issue(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete processing pipeline for a GitHub issue
        
        Args:
            issue_data: Dictionary containing issue information
            
        Returns:
            Complete categorization and context information
        """
        title = issue_data.get("title", "")
        body = issue_data.get("body", "")
        labels = [label.get("name", "") for label in issue_data.get("labels", [])]
        
        # Classify the issue
        categories, confidence_scores = self.classify_issue(title, body, labels)
        
        # Get system prompt template
        system_prompt_info = self.get_system_prompt_template(categories)
        
        # Prepare result
        result = {
            "issue_id": issue_data.get("id"),
            "issue_number": issue_data.get("number"),
            "title": title,
            "categories": [cat.value for cat in categories],
            "confidence_scores": {cat.value: score for cat, score in confidence_scores.items()},
            "context_graphs": [self.get_context_graph(cat).to_dict() for cat in categories],
            "system_prompt_template": system_prompt_info,
            "recommended_actions": self._get_recommended_actions(categories)
        }
        
        return result
    
    def _get_recommended_actions(self, categories: List[IssueCategory]) -> List[str]:
        """Generate recommended actions based on categories"""
        actions = []
        
        if IssueCategory.BUG_FIX in categories:
            actions.extend([
                "Gather error logs and reproduction steps",
                "Run existing tests to identify failures",
                "Check recent commits for potential causes"
            ])
        
        if IssueCategory.TEST_COVERAGE in categories:
            actions.extend([
                "Generate coverage report",
                "Identify uncovered critical paths",
                "Write unit and integration tests"
            ])
        
        if IssueCategory.CICD_GITHUB_ACTIONS in categories:
            actions.extend([
                "Review existing workflows",
                "Design automation strategy",
                "Implement CI/CD best practices"
            ])
        
        if IssueCategory.REFACTOR in categories:
            actions.extend([
                "Analyze code complexity metrics",
                "Identify refactoring opportunities",
                "Plan incremental improvements"
            ])
        
        return actions


# Example usage and testing
if __name__ == "__main__":
    categorizer = IssueCategorizer()
    
    # Test with sample issue data
    sample_issue = {
        "id": 12345,
        "number": 42,
        "title": "Bug: FastAPI endpoint returning 500 error for user authentication",
        "body": "When trying to authenticate users, the /auth/login endpoint throws a 500 internal server error. The traceback shows a SQLAlchemy connection issue with PostgreSQL database.",
        "labels": [
            {"name": "bug"},
            {"name": "backend"},
            {"name": "critical"}
        ]
    }
    
    result = categorizer.process_github_issue(sample_issue)
    print(json.dumps(result, indent=2))