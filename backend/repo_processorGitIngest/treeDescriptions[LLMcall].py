#!/usr/bin/env python3
"""
Tree pruning functionality for GitIngest output.

This module provides functions to:
1. Parse and prune directory trees based on file patterns
2. Generate LLM descriptions for files and directories
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import openai



def generate_llm_descriptions(pruned_items: List[Dict[str, Any]], api_key: Optional[str] = None) -> Dict[str, str]:
    """
    Generate LLM descriptions for files and directories.
    
    Args:
        pruned_items: List of file/directory items from parse_and_prune_tree
        api_key: OpenAI API key (optional, will try to use environment variable)
    
    Returns:
        Dictionary mapping file/directory paths to their descriptions
        Files get 3-5 word descriptions, directories get up to 15 word descriptions
    """
    if not pruned_items:
        return {}
        
    descriptions = {}
    
    # Group items by type for batch processing
    files = [item for item in pruned_items if item['type'] == 'file']
    directories = [item for item in pruned_items if item['type'] == 'directory']
    
    # Initialize OpenAI client
    try:
        if api_key:
            client = openai.OpenAI(api_key=api_key)
        else:
            client = openai.OpenAI()  # Will use OPENAI_API_KEY env var
    except Exception as e:
        print(f"Warning: Could not initialize OpenAI client: {e}")
        # Fallback to simple heuristic descriptions
      
    
    # Generate descriptions for files (3-5 words each)
    if files:
        file_names = [item['name'] for item in files]
        file_prompt = f"""
        Generate very brief 3-5 word descriptions for these files based on their names and extensions.
        Return only the descriptions separated by newlines, one per file, in the same order.
        
        Files:
        {chr(10).join(file_names)}
        
        Example format:
        Python main script
        Configuration YAML file
        README documentation
        """
        
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates brief file descriptions."},
                    {"role": "user", "content": file_prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            file_descriptions = response.choices[0].message.content.strip().split('\n')
            for i, item in enumerate(files):
                if i < len(file_descriptions):
                    descriptions[item['path']] = file_descriptions[i].strip()
                    
        except Exception as e:
            print(f"Warning: Failed to generate file descriptions via LLM: {e}")
            # Fallback for files
            for item in files:
                descriptions[item['path']] = _get_fallback_file_description(item['name'])
    
    # Generate descriptions for directories (up to 15 words each)
    if directories:
        dir_names = [item['name'] for item in directories]
        dir_prompt = f"""
        Generate brief descriptions (maximum 15 words) for these directories based on their names.
        Return only the descriptions separated by newlines, one per directory, in the same order.
        
        Directories:
        {chr(10).join(dir_names)}
        
        Example format:
        Source code and main application logic
        Configuration files and settings
        Documentation and help files
        """
        
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates brief directory descriptions."},
                    {"role": "user", "content": dir_prompt}
                ],
                max_tokens=800,
                temperature=0.3
            )
            
            dir_descriptions = response.choices[0].message.content.strip().split('\n')
            for i, item in enumerate(directories):
                if i < len(dir_descriptions):
                    descriptions[item['path']] = dir_descriptions[i].strip()
                    
        except Exception as e:
            print(f"Warning: Failed to generate directory descriptions via LLM: {e}")
            # Fallback for directories
            for item in directories:
                descriptions[item['path']] = _get_fallback_directory_description(item['name'])
    
    return descriptions





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
# Example usage and testing
if __name__ == "__main__":
    # Example tree string (simplified)
    sample_tree = """Directory structure:
└── example-repo/
    ├── README.md
    ├── LICENSE
    ├── setup.py
    ├── src/
    │   ├── __init__.py
    │   ├── main.py
    │   └── utils.py
    ├── tests/
    │   ├── __init__.py
    │   └── test_main.py
    └── docs/
        └── index.md"""
    
    # Default patterns (simplified example)
    include_patterns = ['*.py', '*.md', '*.json', '*.yaml', '*.yml']
    exclude_patterns = ['*.pyc', '__pycache__/*', '*.log']
    
    # Parse and prune
    pruned = parse_and_prune_tree(sample_tree, include_patterns, exclude_patterns)
    
    print("Pruned tree items:")
    for item in pruned:
        print(f"  {item['type']}: {item['name']} (level {item['level']})")
    
 
