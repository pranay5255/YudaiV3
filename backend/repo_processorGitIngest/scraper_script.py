#!/usr/bin/env python3
"""
GitIngest Repository Data Extractor

This script uses GitIngest to extract repository data and return raw response
without any preprocessing.

Usage:
    python scraper_script.py <github_repo_url> [output_file.json]
    
Example:
    python scraper_script.py https://github.com/octocat/Hello-World repo_data.json
"""

import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from gitingest import ingest_async as ingest

from utils import utc_now

include_categories = {
    'Source Code': ['*.py', '*.js', '*.ts', '*.jsx', '*.tsx', '*.java', '*.cpp', '*.c', '*.go', '*.rs', '*.php', '*.rb', '*.swift', '*.kt', '*.scala', '*.cs', '*.vb', '*.hs', '*.lua', '*.jl'],
    'Web Files': ['*.html', '*.css', '*.scss', '*.sass', '*.less', '*.styl', '*.pug', '*.hbs'],
    'Documentation': ['*.md', '*.rst', '*.txt', '*.tex', '*.adoc'],
    'Configuration': ['*.json', '*.yaml', '*.yml', '*.toml', '*.ini', '*.cfg', '*.conf', '*.properties'],
    'Scripts': ['*.sh', '*.bash', '*.zsh', '*.ps1', '*.bat'],
    'Data Files': ['*.sql', '*.xml', '*.csv', '*.jsonl', '*.tsv'],
    'Dependency Files': ['requirements.txt', 'package.json', 'Cargo.toml', 'go.mod', 'Gemfile', 'composer.json', 'pom.xml', 'build.gradle', 'Pipfile'],
    'Build Files': ['Makefile', 'Dockerfile', 'docker-compose.yml', 'Jenkinsfile'],
    'Git Files': ['.gitignore', '.gitattributes'],
    'Project Files': ['README*', 'LICENSE*', 'CHANGELOG*', 'CONTRIBUTING*', 'CODE_OF_CONDUCT*'],
    'Lock Files': ['*.lock', 'Pipfile.lock']
}

# Exclude categories with additional file types
exclude_categories = {
    'Logs & Temp': ['*.log', '*.tmp', '*.temp', '*.cache'],
    'Compiled Files': ['*.pyc', '*.pyo', '__pycache__', '*.so', '*.dll', '*.exe', '*.bin', '*.obj', '*.o', '*.a', '*.lib', '*.jar', '*.war', '*.ear', '*.class', '*.beam'],
    'Minified Files': ['*.min.js', '*.min.css', '*.map'],
    'Media Files': ['*.woff', '*.woff2', '*.ttf', '*.eot', '*.svg', '*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp', '*.ico', '*.pdf', '*.psd', '*.mp4', '*.mp3'],
    'Archives': ['*.zip', '*.tar', '*.gz', '*.rar', '*.7z', '*.bz2'],
    'Dependencies': ['node_modules', 'vendor', 'target', 'build', 'dist', 'out'],
    'Version Control': ['.git', '.svn', '.hg'],
    'System Files': ['.DS_Store', 'Thumbs.db', '*.swp', '*.swo', '*~', '.#*'],
    'Environment & Secrets': ['.env', '*.key', '*.pem', '*.crt', '*.p12', '*.pfx', 'secrets.json', 'credentials.json'],
    'Databases': ['*.db', '*.sqlite', '*.sqlite3', '*.mdb', '*.accdb'],
    'Backup Files': ['*.bak', '*.backup', '*.old', '*.prev', '*.save', '*.sav'],
    'Data Files': ['*.dat', '*.data', '*.bin', '*.idx', '*.index'],
    'Process Files': ['*.lock', '*.pid', '*.sock', '*.fifo', '*.lck']
}

def categorize_file(file_path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Categorize a file based on its path into include or exclude categories.
    
    Args:
        file_path (str): The path of the file to categorize.
    
    Returns:
        tuple: (category, type) where type is 'include' or 'exclude', or (None, None) if no match.
    """
    dirs = os.path.dirname(file_path).split(os.sep)
    file_name = os.path.basename(file_path)
    
    # Check exclude categories first (exclusions typically take precedence)
    for category, patterns in exclude_categories.items():
        for pattern in patterns:
            if '*' not in pattern:
                # Directory pattern or exact file name
                if pattern in dirs or file_name == pattern:
                    return (category, 'exclude')
            else:
                # File pattern
                if fnmatch.fnmatch(file_name, pattern):
                    return (category, 'exclude')
    
    # Then check include categories
    for category, patterns in include_categories.items():
        for pattern in patterns:
            if '*' not in pattern:
                # Exact file name
                if file_name == pattern:
                    return (category, 'include')
            else:
                # File pattern
                if fnmatch.fnmatch(file_name, pattern):
                    return (category, 'include')
    
    # No match found
    return (None, None)

async def extract_repository_data(
    repo_url: str,
    max_file_size: Optional[int] = None
) -> Dict[str, Any]:
    """Extract repository data using GitIngest and return raw response."""
    print(f"Extracting data from: {repo_url}")

    try:
        # Extract data using GitIngest (await the async function)
        summary, tree, content = await ingest(
            repo_url,
            max_file_size=max_file_size
        )

        # Parse tree structure to get files and directories
        file_categories = {}
        directories = []
        files = []

        if tree:
            lines = tree.strip().split('\n')
            for line in lines:
                if line.strip() and not line.startswith('Directory structure:'):
                    # Extract path from tree line
                    path = line.strip().lstrip('├── └── │   ')
                    if path:
                        if path.endswith('/'):
                            # This is a directory
                            directories.append(path.rstrip('/'))
                        else:
                            # This is a file - categorize with full path
                            category, cat_type = categorize_file(path)
                            if category and cat_type == 'include':
                                file_categories[path] = {'category': category, 'type': cat_type}

        # Extract individual file contents from GitIngest content
        # GitIngest returns content as a string with file separators
        file_contents = {}
        if content:
            # Split content by file separator markers
            content_sections = content.split('=' * 50)
            current_file = None
            current_content = []

            for section in content_sections:
                lines = section.strip().split('\n')
                if lines and lines[0].startswith('File: '):
                    # Save previous file if exists
                    if current_file and current_content:
                        file_contents[current_file] = '\n'.join(current_content)

                    # Start new file
                    current_file = lines[0][6:].strip()  # Remove 'File: ' prefix
                    current_content = lines[1:]  # Skip the file header
                elif current_file:
                    current_content.extend(lines)

            # Save last file
            if current_file and current_content:
                file_contents[current_file] = '\n'.join(current_content)

        # Build files array with content
        for file_path in file_categories.keys():
            if file_path in file_contents:
                file_content = file_contents[file_path]
                files.append({
                    'path': file_path,
                    'content': file_content,
                    'size': len(file_content),
                    'content_size': len(file_content),
                    'type': file_categories[file_path]['category']
                })

        return {
            'extraction_info': {
                'timestamp': utc_now().isoformat(),
                'source_url': repo_url,
                'parameters': {
                    'max_file_size': max_file_size,
                    'file_categories': file_categories,
                    'directories': directories
                }
            },
            'files': files,
            'raw_response': {
                'summary': summary,
                'tree': tree,
                'content': content
            }
        }

    except Exception as e:
        return {
            'error': str(e),
            'timestamp': utc_now().isoformat(),
            'source_url': repo_url
        }

def save_json_data(data: Dict[str, Any], output_file: str) -> None:
    """Save data to JSON file with proper formatting."""
    output_path = Path(output_file)
    
    # Create output directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data saved to: {output_path.absolute()}")
    except Exception as e:
        print(f"Error saving file: {e}")


async def main() -> None:
    """Main function to handle command line arguments and execute the script."""
    parser = argparse.ArgumentParser(
        description="Extract repository data using GitIngest and save raw response as JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scraper_script.py https://github.com/octocat/Hello-World
  python scraper_script.py https://github.com/user/repo repo_data.json
  python scraper_script.py https://github.com/user/repo --max-size 51200
        """
    )
    
    parser.add_argument(
        'repo_url',
        help='GitHub repository URL to analyze'
    )
    
    parser.add_argument(
        'output_file',
        nargs='?',
        default='repository_data.json',
        help='Output JSON file path (default: repository_data.json)'
    )
    
    parser.add_argument(
        '--max-size',
        type=int,
        help='Maximum file size in bytes to process'
    )
    
    args = parser.parse_args()
    
    # Validate required arguments
    if not args.repo_url:
        print("Error: Repository URL is required")
        parser.print_help()
        sys.exit(1)
    
    # Extract repository data (await the async function)
    repo_data = await extract_repository_data(
        repo_url=args.repo_url,
        max_file_size=args.max_size
    )
    
    # Check for errors
    if 'error' in repo_data:
        print(f"Failed to extract data: {repo_data['error']}")
        sys.exit(1)
    
    # Save data to JSON file
    save_json_data(repo_data, args.output_file)
    
    # Print summary
    print("\n" + "="*50)
    print("EXTRACTION SUMMARY")
    print("="*50)
    print(f"Repository: {args.repo_url}")
    print("Raw response saved with summary, tree, and content sections")
    print(f"Output file: {args.output_file}")


async def test_extract_repository_data():
    """Test function to verify repository data extraction works correctly."""
    # Test with a simple public repository
    test_repo_url = "https://github.com/octocat/Hello-World"
    print(f"Testing repository extraction for: {test_repo_url}")

    try:
        result = await extract_repository_data(test_repo_url, max_file_size=50000)
        if "error" in result:
            print(f"Error during extraction: {result['error']}")
            return False

        files = result.get("files", [])
        print(f"Successfully extracted {len(files)} files:")
        for file in files[:5]:  # Show first 5 files
            print(f"  - {file['path']} ({file['content_size']} chars, type: {file['type']})")

        if files:
            print(f"Sample content from first file ({files[0]['path']}):")
            content_preview = files[0]['content'][:200] + "..." if len(files[0]['content']) > 200 else files[0]['content']
            print(f"    {content_preview}")

        return True
    except Exception as e:
        print(f"Test failed with error: {e}")
        return False

if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Run test function
        success = asyncio.run(test_extract_repository_data())
        sys.exit(0 if success else 1)
    else:
        # Run main function
        asyncio.run(main())
