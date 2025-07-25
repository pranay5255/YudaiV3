"""
Example usage of the Code Inspector Agent

This file demonstrates how to use the CodeInspectorAgent to analyze
a repository and generate GitHub issues.
"""

import os
import sys
from typing import List

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from sqlalchemy.orm import Session
from db.database import get_db, SessionLocal
from models import Repository, UserIssue
from daifuUserAgent.architectAgent import CodeInspectorService


def example_repository_analysis():
    """
    Example: Analyze a repository and create issues
    """
    print("=== Code Inspector Agent Example ===\n")
    
    # Get database session
    db: Session = SessionLocal()
    
    try:
        # Example parameters (replace with actual values)
        repository_id = 1  # Replace with actual repository ID
        user_id = 1       # Replace with actual user ID
        
        print(f"Analyzing repository ID: {repository_id}")
        print(f"User ID: {user_id}")
        
        # Check if repository exists
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            print(f"❌ Repository with ID {repository_id} not found")
            return
        
        print(f"📁 Repository: {repository.full_name}")
        print(f"🏷️  Language: {repository.language}")
        print(f"📝 Description: {repository.description}\n")
        
        # Analyze repository and create issues
        print("🔍 Starting codebase analysis...")
        
        issues = CodeInspectorService.analyze_repository_and_create_issues(
            db=db,
            repository_id=repository_id,
            user_id=user_id,
            analysis_type="comprehensive",
            focus_areas=["security", "performance", "code_quality"],
            refine_issues=True
        )
        
        print(f"✅ Analysis complete! Generated {len(issues)} issues:\n")
        
        # Display generated issues
        for i, issue in enumerate(issues, 1):
            print(f"Issue {i}:")
            print(f"  🏷️  Title: {issue.title}")
            print(f"  🔥 Priority: {issue.priority}")
            print(f"  📊 Status: {issue.status}")
            print(f"  📝 Description: {issue.description[:100]}...")
            print()
        
        # Example: Prepare an issue for SWE agent
        if issues:
            first_issue = issues[0]
            print(f"🤖 Preparing issue '{first_issue.title}' for SWE agent...")
            
            try:
                execution_plan = CodeInspectorService.prepare_issue_for_swe_agent(
                    db=db,
                    issue_id=first_issue.issue_id
                )
                
                print("✅ SWE agent preparation complete!")
                print(f"📋 Execution plan contains {len(execution_plan.get('execution_plan', []))} steps")
                print(f"⚠️  Risk factors: {len(execution_plan.get('risk_assessment', []))}")
                
            except Exception as e:
                print(f"❌ SWE agent preparation failed: {e}")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        
    finally:
        db.close()


def example_list_ready_issues():
    """
    Example: List issues ready for SWE agent processing
    """
    print("\n=== Issues Ready for SWE Agent ===\n")
    
    db: Session = SessionLocal()
    
    try:
        repository_id = 1  # Replace with actual repository ID
        
        ready_issues = CodeInspectorService.get_issues_ready_for_swe(
            db=db,
            repository_id=repository_id
        )
        
        if not ready_issues:
            print("📭 No issues ready for SWE agent processing")
            return
        
        print(f"🚀 Found {len(ready_issues)} issues ready for SWE agent:\n")
        
        for issue in ready_issues:
            print(f"🎯 {issue.title}")
            print(f"   Status: {issue.status}")
            print(f"   SWE Status: {issue.swe_agent_status or 'not_started'}")
            print(f"   Priority: {issue.priority}")
            print(f"   Complexity: {issue.complexity_score or 'Unknown'}")
            if issue.estimated_hours:
                print(f"   Estimated: {issue.estimated_hours} hours")
            print()
        
    except Exception as e:
        print(f"❌ Failed to list ready issues: {e}")
        
    finally:
        db.close()


def example_custom_analysis():
    """
    Example: Custom analysis with specific focus areas
    """
    print("\n=== Custom Security Analysis ===\n")
    
    db: Session = SessionLocal()
    
    try:
        repository_id = 1
        user_id = 1
        
        print("🔒 Running security-focused analysis...")
        
        issues = CodeInspectorService.analyze_repository_and_create_issues(
            db=db,
            repository_id=repository_id,
            user_id=user_id,
            analysis_type="security",
            focus_areas=[
                "Authentication and authorization",
                "Input validation and sanitization", 
                "SQL injection vulnerabilities",
                "Cross-site scripting (XSS)",
                "API security",
                "Secrets and credential management"
            ],
            refine_issues=True
        )
        
        security_issues = [issue for issue in issues if "security" in issue.issue_text_raw.lower()]
        
        print(f"🛡️  Found {len(security_issues)} security-related issues:")
        
        for issue in security_issues:
            print(f"  ⚠️  {issue.title} (Priority: {issue.priority})")
        
    except Exception as e:
        print(f"❌ Security analysis failed: {e}")
        
    finally:
        db.close()


if __name__ == "__main__":
    # Check if OPENROUTER_API_KEY is set
    if not os.getenv("OPENROUTER_API_KEY"):
        print("❌ OPENROUTER_API_KEY environment variable is required")
        print("   Please set it before running this example")
        sys.exit(1)
    
    print("🤖 Code Inspector Agent Examples")
    print("================================\n")
    
    # Run examples
    try:
        example_repository_analysis()
        example_list_ready_issues()
        example_custom_analysis()
        
    except KeyboardInterrupt:
        print("\n⏹️  Examples interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    
    print("\n✅ Examples completed!") 