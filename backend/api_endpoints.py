"""
FastAPI Endpoints for GitHub Issue Categorization System
Provides REST API endpoints for categorizing GitHub issues and generating context.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
import json
from datetime import datetime

from github_issue_processor import GitHubIssueProcessor, ProcessingResult
from issue_categorizer import IssueCategory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="GitHub Issue Categorization API",
    description="AI-powered system for categorizing GitHub issues and generating appropriate context",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize processor
processor = GitHubIssueProcessor()


# Pydantic Models
class GitHubLabel(BaseModel):
    """GitHub label model"""
    name: str
    color: Optional[str] = None
    description: Optional[str] = None


class GitHubIssue(BaseModel):
    """GitHub issue model"""
    id: int
    number: int
    title: str
    body: str
    labels: List[GitHubLabel] = []
    state: Optional[str] = "open"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BulkProcessRequest(BaseModel):
    """Request model for bulk processing"""
    issues: List[GitHubIssue]
    options: Optional[Dict[str, Any]] = {}


class CategorizationResponse(BaseModel):
    """Response model for issue categorization"""
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


class BulkProcessResponse(BaseModel):
    """Response model for bulk processing"""
    total_processed: int
    successful: int
    failed: int
    results: List[CategorizationResponse]
    statistics: Dict[str, Any]


class CategoryStatsResponse(BaseModel):
    """Response model for category statistics"""
    total_issues: int
    categories: Dict[str, Dict[str, Any]]
    most_common_category: Optional[str]


class PreprocessingPipelineResponse(BaseModel):
    """Response model for preprocessing pipeline"""
    categories: List[str]
    file_retrieval: Dict[str, Any]
    github_api_calls: Dict[str, Any]
    context_analysis: Dict[str, Any]
    preprocessing_steps: List[str]


# API Endpoints

@app.get("/", summary="Health Check")
async def root():
    """Health check endpoint"""
    return {
        "message": "GitHub Issue Categorization API",
        "status": "active",
        "timestamp": datetime.now().isoformat(),
        "available_categories": [category.value for category in IssueCategory]
    }


@app.post("/categorize", response_model=CategorizationResponse, summary="Categorize Single Issue")
async def categorize_issue(issue: GitHubIssue):
    """
    Categorize a single GitHub issue and generate appropriate context
    
    Args:
        issue: GitHub issue data
        
    Returns:
        Complete categorization result with context and system prompts
    """
    try:
        logger.info(f"Categorizing issue #{issue.number}: {issue.title}")
        
        # Convert to dict format expected by processor
        issue_data = {
            "id": issue.id,
            "number": issue.number,
            "title": issue.title,
            "body": issue.body,
            "labels": [{"name": label.name} for label in issue.labels]
        }
        
        # Process the issue
        result = processor.process_issue(issue_data)
        
        # Convert to response model
        response = CategorizationResponse(
            issue_id=result.issue_id,
            issue_number=result.issue_number,
            title=result.title,
            categories=result.categories,
            confidence_scores=result.confidence_scores,
            context_graph=result.context_graph,
            system_prompt=result.system_prompt,
            preprocessing_instructions=result.preprocessing_instructions,
            recommended_actions=result.recommended_actions,
            processing_timestamp=result.processing_timestamp
        )
        
        logger.info(f"Successfully categorized issue #{issue.number}")
        return response
        
    except Exception as e:
        logger.error(f"Error categorizing issue #{issue.number}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing issue: {str(e)}")


@app.post("/categorize/bulk", response_model=BulkProcessResponse, summary="Categorize Multiple Issues")
async def categorize_issues_bulk(request: BulkProcessRequest, background_tasks: BackgroundTasks):
    """
    Categorize multiple GitHub issues in bulk
    
    Args:
        request: Bulk processing request with list of issues
        background_tasks: FastAPI background tasks for async processing
        
    Returns:
        Bulk processing results with statistics
    """
    try:
        logger.info(f"Starting bulk categorization of {len(request.issues)} issues")
        
        # Convert issues to dict format
        issues_data = []
        for issue in request.issues:
            issue_data = {
                "id": issue.id,
                "number": issue.number,
                "title": issue.title,
                "body": issue.body,
                "labels": [{"name": label.name} for label in issue.labels]
            }
            issues_data.append(issue_data)
        
        # Process issues
        results = processor.bulk_process_issues(issues_data)
        
        # Convert results to response format
        response_results = []
        for result in results:
            response_result = CategorizationResponse(
                issue_id=result.issue_id,
                issue_number=result.issue_number,
                title=result.title,
                categories=result.categories,
                confidence_scores=result.confidence_scores,
                context_graph=result.context_graph,
                system_prompt=result.system_prompt,
                preprocessing_instructions=result.preprocessing_instructions,
                recommended_actions=result.recommended_actions,
                processing_timestamp=result.processing_timestamp
            )
            response_results.append(response_result)
        
        # Get statistics
        statistics = processor.get_category_statistics()
        
        response = BulkProcessResponse(
            total_processed=len(request.issues),
            successful=len(results),
            failed=len(request.issues) - len(results),
            results=response_results,
            statistics=statistics
        )
        
        logger.info(f"Bulk categorization completed: {len(results)}/{len(request.issues)} successful")
        return response
        
    except Exception as e:
        logger.error(f"Error in bulk categorization: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing issues: {str(e)}")


@app.get("/categories", summary="Get Available Categories")
async def get_categories():
    """
    Get list of available issue categories
    
    Returns:
        List of available categories with descriptions
    """
    categories = []
    for category in IssueCategory:
        context_graph = processor.categorizer.get_context_graph(category)
        categories.append({
            "name": category.value,
            "description": f"Issues related to {category.value.replace('_', ' ').title()}",
            "relevant_files": context_graph.relevant_files if context_graph else [],
            "dependencies": context_graph.dependencies if context_graph else []
        })
    
    return {
        "categories": categories,
        "total_categories": len(categories)
    }


@app.get("/statistics", response_model=CategoryStatsResponse, summary="Get Processing Statistics")
async def get_statistics():
    """
    Get statistics about processed issues
    
    Returns:
        Statistics about categories and processing history
    """
    try:
        stats = processor.get_category_statistics()
        
        response = CategoryStatsResponse(
            total_issues=stats["total_issues"],
            categories=stats["categories"],
            most_common_category=stats.get("most_common_category")
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving statistics: {str(e)}")


@app.post("/preprocessing-pipeline", response_model=PreprocessingPipelineResponse, summary="Get Preprocessing Pipeline")
async def get_preprocessing_pipeline(categories: List[str]):
    """
    Get preprocessing pipeline configuration for given categories
    
    Args:
        categories: List of category names
        
    Returns:
        Complete preprocessing pipeline configuration
    """
    try:
        logger.info(f"Generating preprocessing pipeline for categories: {categories}")
        
        # Validate categories
        valid_categories = [cat.value for cat in IssueCategory]
        invalid_categories = [cat for cat in categories if cat not in valid_categories]
        
        if invalid_categories:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid categories: {invalid_categories}. Valid categories: {valid_categories}"
            )
        
        # Get pipeline configuration
        pipeline = processor.get_preprocessing_pipeline(categories)
        
        response = PreprocessingPipelineResponse(
            categories=pipeline["categories"],
            file_retrieval=pipeline["file_retrieval"],
            github_api_calls=pipeline["github_api_calls"],
            context_analysis=pipeline["context_analysis"],
            preprocessing_steps=pipeline["preprocessing_steps"]
        )
        
        logger.info("Preprocessing pipeline generated successfully")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating preprocessing pipeline: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating pipeline: {str(e)}")


@app.get("/system-prompt/{category}", summary="Get System Prompt Template")
async def get_system_prompt_template(category: str):
    """
    Get system prompt template for a specific category
    
    Args:
        category: Category name
        
    Returns:
        System prompt template for the category
    """
    try:
        # Validate category
        valid_categories = [cat.value for cat in IssueCategory]
        if category not in valid_categories:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category: {category}. Valid categories: {valid_categories}"
            )
        
        # Get system prompt
        category_enum = IssueCategory(category)
        context_graph = processor.categorizer.get_context_graph(category_enum)
        system_prompt = processor.prompt_generator.get_combined_prompt([category_enum], context_graph.to_dict())
        
        return {
            "category": category,
            "system_prompt": system_prompt,
            "length": len(system_prompt),
            "context_graph": context_graph.to_dict() if context_graph else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting system prompt for category {category}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving system prompt: {str(e)}")


@app.post("/export", summary="Export Processing Results")
async def export_results():
    """
    Export processing results to JSON
    
    Returns:
        Export status and download information
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"issue_processing_results_{timestamp}.json"
        
        success = processor.export_processing_results(filename)
        
        if success:
            return {
                "status": "success",
                "filename": filename,
                "total_issues": len(processor.processing_history),
                "export_timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Export failed")
            
    except Exception as e:
        logger.error(f"Error exporting results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error exporting results: {str(e)}")


@app.delete("/clear", summary="Clear Processing History")
async def clear_processing_history():
    """
    Clear all processing history
    
    Returns:
        Clear operation status
    """
    try:
        total_cleared = len(processor.processing_history)
        processor.processing_history.clear()
        
        return {
            "status": "success",
            "cleared_count": total_cleared,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error clearing history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error clearing history: {str(e)}")


# Error Handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    logger.error(f"ValueError: {str(exc)}")
    return HTTPException(status_code=400, detail=str(exc))


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unexpected error: {str(exc)}")
    return HTTPException(status_code=500, detail="An unexpected error occurred")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api_endpoints:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )