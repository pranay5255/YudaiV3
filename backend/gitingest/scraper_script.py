#!/usr/bin/env python3
"""
GitIngest Repository Data Extractor

This script uses GitIngest to extract comprehensive repository data and save it
in a structured JSON format for visualization and analysis.

Usage:
    python scraper_script.py <github_repo_url> [output_file.json]
    
Example:
    python scraper_script.py https://github.com/octocat/Hello-World repo_data.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import time

from gitingest import ingest


def parse_summary(summary: str) -> Dict[str, Any]:
    """Parse the repository summary section from GitIngest output."""
    metadata = {}
    
    # Extract repository name
    repo_match = re.search(r'Repository:\s*(.+)', summary)
    if repo_match:
        metadata['repository'] = repo_match.group(1).strip()
    
    # Extract file count
    files_match = re.search(r'Files analyzed:\s*(\d+)', summary)
    if files_match:
        metadata['files_analyzed'] = int(files_match.group(1))
    
    # Extract estimated tokens
    tokens_match = re.search(r'Estimated tokens:\s*([\d.]+k?)', summary)
    if tokens_match:
        token_str = tokens_match.group(1)
        if token_str.endswith('k'):
            metadata['estimated_tokens'] = int(float(token_str[:-1]) * 1000)
        else:
            metadata['estimated_tokens'] = int(float(token_str))
    
    return metadata


def parse_directory_structure(tree: str) -> Dict[str, Any]:
    """Parse the directory structure section from GitIngest output."""
    structure = {
        'root_directory': '',
        'total_directories': 0,
        'total_files': 0,
        'file_types': {},
        'structure_tree': tree.strip()
    }
    
    lines = tree.strip().split('\n')
    if not lines:
        return structure
    
    # Extract root directory name
    root_match = re.search(r'└── (.+)/', lines[0])
    if root_match:
        structure['root_directory'] = root_match.group(1)
    
    # Count files and directories
    file_count = 0
    dir_count = 0
    file_extensions = {}
    
    for line in lines[1:]:  # Skip the root directory line
        line = line.strip()
        if not line:
            continue
            
        # Count directories (lines ending with /)
        if line.endswith('/'):
            dir_count += 1
        # Count files (lines not ending with / and not just whitespace/connectors)
        elif not line.startswith('├──') and not line.startswith('└──') and not line.startswith('│'):
            if '/' in line or '.' in line.split()[-1]:
                file_count += 1
                # Extract file extension
                parts = line.split()
                if parts:
                    filename = parts[-1]
                    if '.' in filename:
                        ext = filename.split('.')[-1]
                        file_extensions[ext] = file_extensions.get(ext, 0) + 1
    
    structure['total_directories'] = dir_count
    structure['total_files'] = file_count
    structure['file_types'] = file_extensions
    
    return structure


def get_default_patterns() -> Tuple[List[str], List[str]]:
    """
    Get default include and exclude patterns for repository analysis.
    
    Returns:
        Tuple of (include_patterns, exclude_patterns)
    """
    # Default include patterns - focus on common source code files
    default_include = [
        '*.py',      # Python files
        '*.js',      # JavaScript files  
        '*.ts',      # TypeScript files
        '*.jsx',     # React JSX files
        '*.tsx',     # React TypeScript files
        '*.md',      # Markdown documentation
        '*.json',    # Configuration files
        '*.yaml',    # YAML configuration
        '*.yml',     # YAML configuration
        '*.toml',    # TOML configuration
        '*.ini',     # INI configuration
        '*.cfg',     # Configuration files
        '*.conf',    # Configuration files
        '*.txt',     # Text files
        '*.rst',     # ReStructuredText
        '*.html',    # HTML files
        '*.css',     # CSS files
        '*.scss',    # SCSS files
        '*.sass',    # Sass files
        '*.sh',      # Shell scripts
        '*.bash',    # Bash scripts
        '*.zsh',     # Zsh scripts
        '*.sql',     # SQL files
        '*.xml',     # XML files
        '*.csv',     # CSV files
        '*.lock',    # Lock files (package-lock.json, etc.)
        'requirements.txt',  # Python dependencies
        'package.json',      # Node.js dependencies
        'Cargo.toml',        # Rust dependencies
        'go.mod',           # Go dependencies
        'Gemfile',          # Ruby dependencies
        'composer.json',    # PHP dependencies
        'pom.xml',          # Maven dependencies
        'build.gradle',     # Gradle dependencies
        'Makefile',         # Makefiles
        'Dockerfile',       # Docker files
        'docker-compose.yml', # Docker compose
        '.gitignore',       # Git ignore files
        'README*',          # README files
        'LICENSE*',         # License files
        'CHANGELOG*',       # Changelog files
        'CONTRIBUTING*',    # Contributing files
        'CODE_OF_CONDUCT*'  # Code of conduct files
    ]
    
    # Default exclude patterns - exclude common non-source files
    default_exclude = [
        '*.log',           # Log files
        '*.tmp',           # Temporary files
        '*.temp',          # Temporary files
        '*.cache',         # Cache files
        '*.pyc',           # Python compiled files
        '*.pyo',           # Python optimized files
        '__pycache__/*',   # Python cache directories
        '*.so',            # Shared object files
        '*.dll',           # Windows DLL files
        '*.exe',           # Executable files
        '*.bin',           # Binary files
        '*.obj',           # Object files
        '*.o',             # Object files
        '*.a',             # Static library files
        '*.lib',           # Library files
        '*.jar',           # Java JAR files
        '*.war',           # Java WAR files
        '*.ear',           # Java EAR files
        '*.class',         # Java class files
        '*.min.js',        # Minified JavaScript
        '*.min.css',       # Minified CSS
        '*.map',           # Source map files
        '*.woff',          # Web fonts
        '*.woff2',         # Web fonts
        '*.ttf',           # TrueType fonts
        '*.eot',           # Embedded OpenType fonts
        '*.svg',           # SVG files (usually images)
        '*.png',           # Image files
        '*.jpg',           # Image files
        '*.jpeg',          # Image files
        '*.gif',           # Image files
        '*.bmp',           # Image files
        '*.ico',           # Icon files
        '*.pdf',           # PDF files
        '*.zip',           # Archive files
        '*.tar',           # Archive files
        '*.gz',            # Compressed files
        '*.rar',           # Archive files
        '*.7z',            # Archive files
        'node_modules/*',  # Node.js dependencies
        'vendor/*',        # PHP dependencies
        'target/*',        # Maven build output
        'build/*',         # Build output
        'dist/*',          # Distribution output
        'out/*',           # Output directories
        '.git/*',          # Git repository data
        '.svn/*',          # SVN repository data
        '.hg/*',           # Mercurial repository data
        '.DS_Store',       # macOS system files
        'Thumbs.db',       # Windows system files
        '*.swp',           # Vim swap files
        '*.swo',           # Vim swap files
        '*~',              # Backup files
        '.#*',             # Emacs backup files
        '.#*#',            # Emacs backup files
        '*.orig',          # Git merge conflict files
        '*.rej',           # Git reject files
        '.coverage',       # Coverage files
        'htmlcov/*',       # Coverage HTML output
        '.pytest_cache/*', # pytest cache
        '.tox/*',          # tox environments
        '.venv/*',         # Python virtual environments
        'venv/*',          # Python virtual environments
        'env/*',           # Python virtual environments
        '.env',            # Environment files
        '.env.*',          # Environment files
        '*.key',           # Key files
        '*.pem',           # Certificate files
        '*.crt',           # Certificate files
        '*.p12',           # Certificate files
        '*.pfx',           # Certificate files
        'secrets.json',    # Secret files
        'config.json',     # Config files (often contain secrets)
        'credentials.json', # Credential files
        '*.db',            # Database files
        '*.sqlite',        # SQLite database files
        '*.sqlite3',       # SQLite database files
        '*.mdb',           # Access database files
        '*.accdb',         # Access database files
        '*.bak',           # Backup files
        '*.backup',        # Backup files
        '*.old',           # Old files
        '*.prev',          # Previous files
        '*.save',          # Save files
        '*.sav',           # Save files
        '*.dat',           # Data files
        '*.data',          # Data files
        '*.bin',           # Binary data files
        '*.dat',           # Data files
        '*.idx',           # Index files
        '*.index',         # Index files
        '*.lock',          # Lock files (except package-lock.json)
        '*.pid',           # Process ID files
        '*.sock',          # Socket files
        '*.fifo',          # Named pipe files
        '*.lck',           # Lock files
        '*.lck.*',         # Lock files
        '*.tmp.*',         # Temporary files
        '*.temp.*',        # Temporary files
        '*.cache.*',       # Cache files
        '*.bak.*',         # Backup files
        '*.old.*',         # Old files
        '*.prev.*',        # Previous files
        '*.save.*',        # Save files
        '*.sav.*',         # Save files
        '*.dat.*',         # Data files
        '*.data.*',        # Data files
        '*.bin.*',         # Binary data files
        '*.idx.*',         # Index files
        '*.index.*',       # Index files
        '*.lock.*',        # Lock files
        '*.pid.*',         # Process ID files
        '*.sock.*',        # Socket files
        '*.fifo.*',        # Named pipe files
        '*.lck.*',         # Lock files
        '*.tmp.*.*',       # Temporary files
        '*.temp.*.*',      # Temporary files
        '*.cache.*.*',     # Cache files
        '*.bak.*.*',       # Backup files
        '*.old.*.*',       # Old files
        '*.prev.*.*',      # Previous files
        '*.save.*.*',      # Save files
        '*.sav.*.*',       # Save files
        '*.dat.*.*',       # Data files
        '*.data.*.*',      # Data files
        '*.bin.*.*',       # Binary data files
        '*.idx.*.*',       # Index files
        '*.index.*.*',     # Index files
        '*.lock.*.*',      # Lock files
        '*.pid.*.*',       # Process ID files
        '*.sock.*.*',      # Socket files
        '*.fifo.*.*',      # Named pipe files
        '*.lck.*.*'        # Lock files
    ]
    
    return default_include, default_exclude


def parse_file_contents(content: str) -> Dict[str, Any]:
    """Parse the file contents section from GitIngest output."""
    files_data = {
        'files': [],
        'total_files_parsed': 0,
        'total_content_size': len(content),
        'file_sizes': {},
        'language_distribution': {}
    }
    
    # Split content by file delimiters
    file_sections = re.split(r'=+\s*\nFILE:\s*(.+?)\s*\n=+\s*\n', content)
    
    if len(file_sections) < 2:
        return files_data
    
    # Process file sections (skip first empty section if exists)
    for i in range(1, len(file_sections), 2):
        if i + 1 < len(file_sections):
            file_path = file_sections[i].strip()
            file_content = file_sections[i + 1].strip()
            
            # Extract file information
            file_info = {
                'path': file_path,
                'name': Path(file_path).name,
                'extension': Path(file_path).suffix,
                'content_size': len(file_content),
                'lines': len(file_content.split('\n')),
                'content_preview': file_content[:500] + '...' if len(file_content) > 500 else file_content
            }
            
            # Determine language based on extension
            language_map = {
                '.py': 'Python',
                '.js': 'JavaScript',
                '.ts': 'TypeScript',
                '.java': 'Java',
                '.cpp': 'C++',
                '.c': 'C',
                '.go': 'Go',
                '.rs': 'Rust',
                '.php': 'PHP',
                '.rb': 'Ruby',
                '.swift': 'Swift',
                '.kt': 'Kotlin',
                '.scala': 'Scala',
                '.html': 'HTML',
                '.css': 'CSS',
                '.scss': 'SCSS',
                '.sass': 'Sass',
                '.md': 'Markdown',
                '.txt': 'Text',
                '.json': 'JSON',
                '.xml': 'XML',
                '.yaml': 'YAML',
                '.yml': 'YAML',
                '.toml': 'TOML',
                '.ini': 'INI',
                '.sh': 'Shell',
                '.bat': 'Batch',
                '.ps1': 'PowerShell',
                '.sql': 'SQL',
                '.r': 'R',
                '.m': 'MATLAB',
                '.ipynb': 'Jupyter Notebook'
            }
            
            file_info['language'] = language_map.get(file_info['extension'], 'Unknown')
            
            files_data['files'].append(file_info)
            files_data['total_files_parsed'] += 1
            
            # Update statistics
            ext = file_info['extension']
            files_data['file_sizes'][ext] = files_data['file_sizes'].get(ext, 0) + file_info['content_size']
            
            lang = file_info['language']
            files_data['language_distribution'][lang] = files_data['language_distribution'].get(lang, 0) + 1
    
    return files_data


def extract_repository_data(repo_url: str, 
                          max_file_size: Optional[int] = None,
                          include_patterns: Optional[List[str]] = None,
                          exclude_patterns: Optional[List[str]] = None,
                          token: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract comprehensive repository data using GitIngest.
    
    Args:
        repo_url: GitHub repository URL
        max_file_size: Maximum file size in bytes to process
        include_patterns: List of file patterns to include (uses defaults if None)
        exclude_patterns: List of file patterns to exclude (uses defaults if None)
        token: GitHub personal access token for private repositories
    
    Returns:
        Dictionary containing structured repository data
    """
    print(f"Extracting data from: {repo_url}")
    
    # Get default patterns if none provided
    if include_patterns is None and exclude_patterns is None:
        default_include, default_exclude = get_default_patterns()
        include_patterns = default_include
        exclude_patterns = default_exclude
        print(f"Using default patterns:")
        print(f"  Include: {len(include_patterns)} patterns (focusing on source code files)")
        print(f"  Exclude: {len(exclude_patterns)} patterns (excluding binaries, logs, etc.)")
    elif include_patterns is None:
        default_include, _ = get_default_patterns()
        include_patterns = default_include
        print(f"Using default include patterns: {len(include_patterns)} patterns")
    elif exclude_patterns is None:
        _, default_exclude = get_default_patterns()
        exclude_patterns = default_exclude
        print(f"Using default exclude patterns: {len(exclude_patterns)} patterns")
    
    # Prepare ingest parameters
    ingest_params = {}
    if max_file_size:
        ingest_params['max_file_size'] = max_file_size
    if include_patterns:
        ingest_params['include_patterns'] = include_patterns
    if exclude_patterns:
        ingest_params['exclude_patterns'] = exclude_patterns
    if token:
        ingest_params['token'] = token
    
    try:
        # Extract data using GitIngest
        summary, tree, content = ingest(repo_url, **ingest_params)
        
        # Parse all sections
        metadata = parse_summary(summary)
        structure = parse_directory_structure(tree)
        files_data = parse_file_contents(content)
        
        # Compile comprehensive repository data
        repo_data = {
            'extraction_info': {
                'timestamp': datetime.now().isoformat(),
                'source_url': repo_url,
                'extraction_method': 'GitIngest',
                'ingest_parameters': ingest_params
            },
            'repository_metadata': metadata,
            'directory_structure': structure,
            'file_contents': files_data,
            'statistics': {
                'total_files': metadata.get('files_analyzed', 0),
                'estimated_tokens': metadata.get('estimated_tokens', 0),
                'total_content_size': files_data['total_content_size'],
                'languages_found': len(files_data['language_distribution']),
                'file_types_found': len(files_data['file_sizes'])
            }
        }
        
        print(f"Successfully extracted data for {metadata.get('repository', 'unknown')}")
        print(f"Files analyzed: {metadata.get('files_analyzed', 0)}")
        print(f"Estimated tokens: {metadata.get('estimated_tokens', 0)}")
        
        return repo_data
        
    except Exception as e:
        print(f"GitIngest error: {e}")
        return {
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'source_url': repo_url
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
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


def main():
    """Main function to handle command line arguments and execute the script."""
    parser = argparse.ArgumentParser(
        description="Extract repository data using GitIngest and save as JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scraper_script.py https://github.com/octocat/Hello-World
  python scraper_script.py https://github.com/user/repo repo_data.json
  python scraper_script.py https://github.com/user/repo --max-size 51200 --include "*.py" --include "*.md"
  python scraper_script.py --show-defaults  # Show default include/exclude patterns
        """
    )
    
    parser.add_argument(
        'repo_url',
        nargs='?',
        help='GitHub repository URL to analyze (not required with --show-defaults)'
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
    
    parser.add_argument(
        '--include',
        action='append',
        dest='include_patterns',
        help='File patterns to include (can be specified multiple times). If not specified, uses comprehensive defaults focusing on source code files.'
    )
    
    parser.add_argument(
        '--exclude',
        action='append',
        dest='exclude_patterns',
        help='File patterns to exclude (can be specified multiple times). If not specified, uses comprehensive defaults excluding binaries, logs, and system files.'
    )
    
    parser.add_argument(
        '--token',
        help='GitHub personal access token for private repositories'
    )
    
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Save with pretty formatting (default: True)'
    )
    
    parser.add_argument(
        '--show-defaults',
        action='store_true',
        help='Show default include and exclude patterns and exit'
    )
    
    args = parser.parse_args()
    
    # Handle show-defaults option
    if args.show_defaults:
        print("Default Include Patterns (focusing on source code and important files):")
        print("=" * 60)
        default_include, default_exclude = get_default_patterns()
        
        # Group include patterns by category
        categories = {
            'Source Code': [p for p in default_include if p in ['*.py', '*.js', '*.ts', '*.jsx', '*.tsx', '*.java', '*.cpp', '*.c', '*.go', '*.rs', '*.php', '*.rb', '*.swift', '*.kt', '*.scala']],
            'Web Files': [p for p in default_include if p in ['*.html', '*.css', '*.scss', '*.sass']],
            'Documentation': [p for p in default_include if p in ['*.md', '*.rst', '*.txt']],
            'Configuration': [p for p in default_include if p in ['*.json', '*.yaml', '*.yml', '*.toml', '*.ini', '*.cfg', '*.conf']],
            'Scripts': [p for p in default_include if p in ['*.sh', '*.bash', '*.zsh']],
            'Data Files': [p for p in default_include if p in ['*.sql', '*.xml', '*.csv']],
            'Dependency Files': [p for p in default_include if p in ['requirements.txt', 'package.json', 'Cargo.toml', 'go.mod', 'Gemfile', 'composer.json', 'pom.xml', 'build.gradle']],
            'Build Files': [p for p in default_include if p in ['Makefile', 'Dockerfile', 'docker-compose.yml']],
            'Git Files': [p for p in default_include if p in ['.gitignore']],
            'Project Files': [p for p in default_include if p in ['README*', 'LICENSE*', 'CHANGELOG*', 'CONTRIBUTING*', 'CODE_OF_CONDUCT*']],
            'Lock Files': [p for p in default_include if p in ['*.lock']]
        }
        
        for category, patterns in categories.items():
            if patterns:
                print(f"\n{category}:")
                for pattern in sorted(patterns):
                    print(f"  {pattern}")
        
        print("\n" + "=" * 60)
        print("Default Exclude Patterns (excluding non-source files):")
        print("=" * 60)
        
        exclude_categories = {
            'Logs & Temp': [p for p in default_exclude if any(x in p for x in ['*.log', '*.tmp', '*.temp', '*.cache'])],
            'Compiled Files': [p for p in default_exclude if any(x in p for x in ['*.pyc', '*.pyo', '__pycache__', '*.so', '*.dll', '*.exe', '*.bin', '*.obj', '*.o', '*.a', '*.lib', '*.jar', '*.war', '*.ear', '*.class'])],
            'Minified Files': [p for p in default_exclude if any(x in p for x in ['*.min.js', '*.min.css', '*.map'])],
            'Media Files': [p for p in default_exclude if any(x in p for x in ['*.woff', '*.woff2', '*.ttf', '*.eot', '*.svg', '*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp', '*.ico', '*.pdf'])],
            'Archives': [p for p in default_exclude if any(x in p for x in ['*.zip', '*.tar', '*.gz', '*.rar', '*.7z'])],
            'Dependencies': [p for p in default_exclude if any(x in p for x in ['node_modules', 'vendor', 'target', 'build', 'dist', 'out'])],
            'Version Control': [p for p in default_exclude if any(x in p for x in ['.git', '.svn', '.hg'])],
            'System Files': [p for p in default_exclude if any(x in p for x in ['.DS_Store', 'Thumbs.db', '*.swp', '*.swo', '*~', '.#*'])],
            'Environment & Secrets': [p for p in default_exclude if any(x in p for x in ['.env', '*.key', '*.pem', '*.crt', '*.p12', '*.pfx', 'secrets.json', 'credentials.json'])],
            'Databases': [p for p in default_exclude if any(x in p for x in ['*.db', '*.sqlite', '*.sqlite3', '*.mdb', '*.accdb'])],
            'Backup Files': [p for p in default_exclude if any(x in p for x in ['*.bak', '*.backup', '*.old', '*.prev', '*.save', '*.sav'])],
            'Data Files': [p for p in default_exclude if any(x in p for x in ['*.dat', '*.data', '*.bin', '*.idx', '*.index'])],
            'Process Files': [p for p in default_exclude if any(x in p for x in ['*.lock', '*.pid', '*.sock', '*.fifo', '*.lck'])]
        }
        
        for category, patterns in exclude_categories.items():
            if patterns:
                print(f"\n{category}:")
                for pattern in sorted(patterns):
                    print(f"  {pattern}")
        
        print(f"\nTotal: {len(default_include)} include patterns, {len(default_exclude)} exclude patterns")
        sys.exit(0)
    
    # Validate repository URL (unless showing defaults)
    if not args.show_defaults:
        if not args.repo_url:
            print("Error: Please provide a GitHub repository URL")
            sys.exit(1)
        if not args.repo_url.startswith('https://github.com/'):
            print("Error: Please provide a valid GitHub repository URL")
            sys.exit(1)
    
    # Extract repository data
    repo_data = extract_repository_data(
        repo_url=args.repo_url,
        max_file_size=args.max_size,
        include_patterns=args.include_patterns,
        exclude_patterns=args.exclude_patterns,
        token=args.token
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
    print(f"Repository: {repo_data['repository_metadata'].get('repository', 'Unknown')}")
    print(f"Files analyzed: {repo_data['statistics']['total_files']}")
    print(f"Estimated tokens: {repo_data['statistics']['estimated_tokens']}")
    print(f"Languages found: {repo_data['statistics']['languages_found']}")
    print(f"File types found: {repo_data['statistics']['file_types_found']}")
    print(f"Total content size: {repo_data['statistics']['total_content_size']} bytes")
    
    # Show language distribution
    if repo_data['file_contents']['language_distribution']:
        print("\nLanguage Distribution:")
        for lang, count in sorted(repo_data['file_contents']['language_distribution'].items(), 
                                key=lambda x: x[1], reverse=True):
            print(f"  {lang}: {count} files")


if __name__ == "__main__":
    main()
