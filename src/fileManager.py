import os
from typing import List

class FileManager:
    @staticmethod
    def setup_directories():
        """
        Create necessary directories for organizing downloads
        """
        directories = [
            "downloads",
            "downloads/media", 
            "downloads/text",
            "downloads/captions"
        ]
        
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"Created directory: {directory}")
    
    @staticmethod
    def get_download_stats(base_dir: str = "downloads") -> dict:
        """
        Get statistics about downloaded files
        """
        stats = {
            "total_files": 0,
            "text_files": 0,
            "media_files": 0,
            "caption_files": 0
        }
        
        if not os.path.exists(base_dir):
            return stats
        
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                stats["total_files"] += 1
                
                if file.endswith('.txt'):
                    if 'captions' in root:
                        stats["caption_files"] += 1
                    else:
                        stats["text_files"] += 1
                else:
                    stats["media_files"] += 1
        
        return stats
    
    @staticmethod
    def list_recent_files(base_dir: str = "downloads", limit: int = 10) -> List[str]:
        """
        List recently downloaded files
        """
        files = []
        
        if not os.path.exists(base_dir):
            return files
        
        for root, dirs, filenames in os.walk(base_dir):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                mtime = os.path.getmtime(filepath)
                files.append((mtime, filepath))
        
        # Sort by modification time (newest first) and return filenames
        files.sort(reverse=True)
        return [filepath for _, filepath in files[:limit]]