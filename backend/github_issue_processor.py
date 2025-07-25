"""
GitHub Issue Processing Orchestrator
Main entry point for categorizing GitHub issues and generating appropriate context.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from issue_categorizer import IssueCategorizer, IssueCategory
from system_prompt_templates import SystemPromptTemplateGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a GitHub issue"""
    issue_id: str
    issue_number: int
    title: str
    categories: List[str]
    confidence_scores: Dict[str, float]
    context_graph: Dict[str, Any]
    system_prompt: str
    preprocessing_instructions: List[str]
    recommended_actions: List[str]
    processing_timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "issue_number": self.issue_number,
            "title": self.title,
            "categories": self.categories,
            "confidence_scores": self.confidence_scores,
            "context_graph": self.context_graph,
            "system_prompt": self.system_prompt,
            "preprocessing_instructions": self.preprocessing_instructions,
            "recommended_actions": self.recommended_actions,
            "processing_timestamp": self.processing_timestamp
        }


class GitHubIssueProcessor:
    """Main orchestrator for GitHub issue processing and categorization"""
    
    def __init__(self):
        self.categorizer = IssueCategorizer()
        self.prompt_generator = SystemPromptTemplateGenerator()
        self.processing_history: List[ProcessingResult] = []
    
    def process_issue(self, issue_data: Dict[str, Any]) -> ProcessingResult:
        """
        Complete processing pipeline for a GitHub issue
        
        Args:
            issue_data: GitHub issue data from API
            
        Returns:
            ProcessingResult with complete categorization and context
        """
        logger.info(f"Processing GitHub issue: {issue_data.get('title', 'Unknown')}")
        
        # Extract issue information
        title = issue_data.get("title", "")
        body = issue_data.get("body", "")
        labels = [label.get("name", "") for label in issue_data.get("labels", [])]
        issue_id = str(issue_data.get("id", ""))
        issue_number = issue_data.get("number", 0)
        
        # Step 1: Categorize the issue
        logger.info("Step 1: Categorizing issue...")
        categories, confidence_scores = self.categorizer.classify_issue(title, body, labels)
        
        if not categories:
            logger.warning("No categories identified for this issue")
            categories = [IssueCategory.REFACTOR]  # Default fallback
        
        logger.info(f"Identified categories: {[cat.value for cat in categories]}")
        
        # Step 2: Generate context graph
        logger.info("Step 2: Generating context graph...")
        context_graph = self.categorizer.get_system_prompt_template(categories)
        
        # Step 3: Generate specialized system prompt
        logger.info("Step 3: Generating system prompt...")
        system_prompt = self.prompt_generator.get_combined_prompt(categories, context_graph)
        
        # Step 4: Get preprocessing instructions
        logger.info("Step 4: Generating preprocessing instructions...")
        preprocessing_instructions = self.prompt_generator.get_preprocessing_instructions(categories)
        
        # Step 5: Get recommended actions
        logger.info("Step 5: Generating recommended actions...")
        recommended_actions = self.categorizer._get_recommended_actions(categories)
        
        # Create processing result
        result = ProcessingResult(
            issue_id=issue_id,
            issue_number=issue_number,
            title=title,
            categories=[cat.value for cat in categories],
            confidence_scores={cat.value: confidence_scores.get(cat, 0.0) for cat in categories},
            context_graph=context_graph,
            system_prompt=system_prompt,
            preprocessing_instructions=preprocessing_instructions,
            recommended_actions=recommended_actions,
            processing_timestamp=datetime.now().isoformat()
        )
        
        # Store in processing history
        self.processing_history.append(result)
        
        logger.info(f"Successfully processed issue #{issue_number}")
        return result
    
    def bulk_process_issues(self, issues_data: List[Dict[str, Any]]) -> List[ProcessingResult]:
        """
        Process multiple GitHub issues in bulk
        
        Args:
            issues_data: List of GitHub issue data from API
            
        Returns:
            List of ProcessingResults
        """
        logger.info(f"Starting bulk processing of {len(issues_data)} issues")
        
        results = []
        for i, issue_data in enumerate(issues_data):
            try:
                logger.info(f"Processing issue {i+1}/{len(issues_data)}")
                result = self.process_issue(issue_data)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing issue {issue_data.get('number', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"Bulk processing completed. {len(results)} issues processed successfully")
        return results
    
    def get_category_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about processed issues by category
        
        Returns:
            Dictionary with category statistics
        """
        if not self.processing_history:
            return {"total_issues": 0, "categories": {}}
        
        category_counts = {}
        total_issues = len(self.processing_history)
        
        for result in self.processing_history:
            for category in result.categories:
                category_counts[category] = category_counts.get(category, 0) + 1
        
        # Calculate percentages
        category_stats = {}
        for category, count in category_counts.items():
            category_stats[category] = {
                "count": count,
                "percentage": round((count / total_issues) * 100, 2)
            }
        
        return {
            "total_issues": total_issues,
            "categories": category_stats,
            "most_common_category": max(category_counts.items(), key=lambda x: x[1])[0] if category_counts else None
        }
    
    def get_preprocessing_pipeline(self, categories: List[str]) -> Dict[str, Any]:
        """
        Get a complete preprocessing pipeline for given categories
        
        Args:
            categories: List of category strings
            
        Returns:
            Complete preprocessing pipeline configuration
        """
        category_enums = [IssueCategory(cat) for cat in categories if cat in IssueCategory.__members__.values()]
        
        pipeline = {
            "categories": categories,
            "file_retrieval": {
                "priority_files": [],
                "relevant_directories": [],
                "file_patterns": []
            },
            "github_api_calls": {
                "recent_commits": True,
                "pull_requests": True,
                "related_issues": True,
                "workflow_runs": False
            },
            "context_analysis": {
                "dependency_analysis": False,
                "code_complexity_metrics": False,
                "test_coverage_analysis": False
            },
            "preprocessing_steps": []
        }
        
        # Configure based on categories
        for category in category_enums:
            context_graph = self.categorizer.get_context_graph(category)
            if context_graph:
                pipeline["file_retrieval"]["priority_files"].extend(context_graph.relevant_files)
                pipeline["file_retrieval"]["relevant_directories"].extend(context_graph.relevant_directories)
                pipeline["preprocessing_steps"].extend(context_graph.preprocessing_steps)
        
        # Category-specific configurations
        if IssueCategory.BUG_FIX in category_enums:
            pipeline["github_api_calls"]["recent_commits"] = True
            pipeline["context_analysis"]["dependency_analysis"] = True
            pipeline["file_retrieval"]["file_patterns"].extend(["*.log", "*.error"])
        
        if IssueCategory.TEST_COVERAGE in category_enums:
            pipeline["context_analysis"]["test_coverage_analysis"] = True
            pipeline["file_retrieval"]["file_patterns"].extend(["*test*.py", "*test*.ts", "coverage.*"])
        
        if IssueCategory.CICD_GITHUB_ACTIONS in category_enums:
            pipeline["github_api_calls"]["workflow_runs"] = True
            pipeline["file_retrieval"]["file_patterns"].extend([".github/workflows/*"])
        
        # Remove duplicates
        pipeline["file_retrieval"]["priority_files"] = list(set(pipeline["file_retrieval"]["priority_files"]))
        pipeline["file_retrieval"]["relevant_directories"] = list(set(pipeline["file_retrieval"]["relevant_directories"]))
        pipeline["preprocessing_steps"] = list(set(pipeline["preprocessing_steps"]))
        
        return pipeline
    
    def export_processing_results(self, filepath: str) -> bool:
        """
        Export processing results to JSON file
        
        Args:
            filepath: Path to export file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "total_issues": len(self.processing_history),
                "statistics": self.get_category_statistics(),
                "results": [result.to_dict() for result in self.processing_history]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Processing results exported to {filepath}")
            return True
        
        except Exception as e:
            logger.error(f"Error exporting results: {str(e)}")
            return False
    
    def load_processing_results(self, filepath: str) -> bool:
        """
        Load processing results from JSON file
        
        Args:
            filepath: Path to import file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            # Convert back to ProcessingResult objects
            self.processing_history = []
            for result_data in import_data.get("results", []):
                result = ProcessingResult(
                    issue_id=result_data["issue_id"],
                    issue_number=result_data["issue_number"],
                    title=result_data["title"],
                    categories=result_data["categories"],
                    confidence_scores=result_data["confidence_scores"],
                    context_graph=result_data["context_graph"],
                    system_prompt=result_data["system_prompt"],
                    preprocessing_instructions=result_data["preprocessing_instructions"],
                    recommended_actions=result_data["recommended_actions"],
                    processing_timestamp=result_data["processing_timestamp"]
                )
                self.processing_history.append(result)
            
            logger.info(f"Processing results loaded from {filepath}")
            return True
        
        except Exception as e:
            logger.error(f"Error loading results: {str(e)}")
            return False


def main():
    """Example usage of the GitHub Issue Processor"""
    
    # Initialize processor
    processor = GitHubIssueProcessor()
    
    # Example issue data (would typically come from GitHub API)
    sample_issues = [
        {
            "id": 12345,
            "number": 42,
            "title": "Bug: FastAPI endpoint returning 500 error for user authentication",
            "body": "When trying to authenticate users, the /auth/login endpoint throws a 500 internal server error. The traceback shows a SQLAlchemy connection issue with PostgreSQL database.",
            "labels": [
                {"name": "bug"},
                {"name": "backend"},
                {"name": "critical"}
            ]
        },
        {
            "id": 12346,
            "number": 43,
            "title": "Add test coverage for user management endpoints",
            "body": "We need to improve test coverage for the user management module. Currently missing unit tests for CRUD operations and integration tests for authentication flows.",
            "labels": [
                {"name": "testing"},
                {"name": "coverage"},
                {"name": "enhancement"}
            ]
        },
        {
            "id": 12347,
            "number": 44,
            "title": "Optimize Docker build process for faster CI/CD",
            "body": "The current Docker build takes too long in CI. We should implement multi-stage builds and better caching strategies to improve build times.",
            "labels": [
                {"name": "docker"},
                {"name": "ci/cd"},
                {"name": "performance"}
            ]
        }
    ]
    
    # Process issues
    print("Processing sample GitHub issues...")
    results = processor.bulk_process_issues(sample_issues)
    
    # Display results
    for result in results:
        print(f"\n--- Issue #{result.issue_number}: {result.title} ---")
        print(f"Categories: {', '.join(result.categories)}")
        print(f"Top actions: {result.recommended_actions[:3]}")
        print(f"System prompt length: {len(result.system_prompt)} characters")
    
    # Show statistics
    print(f"\n--- Processing Statistics ---")
    stats = processor.get_category_statistics()
    print(json.dumps(stats, indent=2))
    
    # Export results
    processor.export_processing_results("issue_processing_results.json")
    
    print("\nProcessing completed successfully!")


if __name__ == "__main__":
    main()