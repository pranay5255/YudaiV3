"""
File Chunking Utility for Embeddings and File Dependencies

This module provides utilities for chunking file content into smaller pieces
suitable for embedding storage and semantic search.
"""

from pathlib import Path
from typing import Dict, List


class FileChunker:
    """
    Utility class for chunking file content into smaller pieces for embeddings.
    
    This class handles different file types and provides intelligent chunking
    strategies based on file content and structure.
    """
    
    def __init__(self, max_chunk_size: int = 1000, overlap: int = 100):
        """
        Initialize the chunker with configuration.
        
        Args:
            max_chunk_size: Maximum number of characters per chunk
            overlap: Number of characters to overlap between chunks
        """
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
    
    def chunk_file(self, file_path: str, content: str) -> List[Dict[str, any]]:
        """
        Chunk a file's content using a simple, unified approach.
        
        Args:
            file_path: Path to the file
            content: File content as string
            
        Returns:
            List of chunks with metadata
        """
        # Use simple chunking for all file types
        chunks = self._chunk_simple(content)
        
        # Add metadata to each chunk
        file_name = Path(file_path).name
        file_ext = Path(file_path).suffix.lower()
        chunks_with_metadata = []
        
        for i, chunk in enumerate(chunks):
            chunk_data = {
                'chunk_index': i,
                'chunk_text': chunk,
                'file_path': file_path,
                'file_name': file_name,
                'file_type': file_ext,
                'tokens': self._estimate_tokens(chunk),
                'chunk_size': len(chunk),
                'is_complete': i == len(chunks) - 1
            }
            chunks_with_metadata.append(chunk_data)
        
        return chunks_with_metadata
    
    def _chunk_simple(self, content: str) -> List[str]:
        """Simple chunking strategy for all file types."""
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + self.max_chunk_size
            
            # Try to break at a word boundary or newline
            if end < len(content):
                # Look for the last space, newline, or punctuation before the end
                last_break = max(
                    content.rfind(' ', start, end),
                    content.rfind('\n', start, end),
                    content.rfind('.', start, end),
                    content.rfind(',', start, end),
                    content.rfind(';', start, end)
                )
                if last_break > start:
                    end = last_break + 1
            
            chunk = content[start:end]
            chunks.append(chunk)
            
            # Move start position with overlap
            start = max(start + 1, end - self.overlap)
        
        return chunks
    

    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a text chunk.
        
        This is a rough estimation - in production you'd use a proper tokenizer.
        """
        # Rough estimation: 1 token ≈ 4 characters for most text
        # Different ratios for different content types
        if any(char in text for char in ['{', '}', '[', ']', '(', ')']):
            # Code-like content
            return max(1, len(text) // 4)
        else:
            # Natural language content
            return max(1, len(text) // 3)


def create_file_chunker(max_chunk_size: int = 1000, overlap: int = 100) -> FileChunker:
    """
    Factory function to create a FileChunker instance.
    
    Args:
        max_chunk_size: Maximum number of characters per chunk
        overlap: Number of characters to overlap between chunks
        
    Returns:
        Configured FileChunker instance
    """
    return FileChunker(max_chunk_size=max_chunk_size, overlap=overlap)
