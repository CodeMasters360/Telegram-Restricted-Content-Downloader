import os
import re
from datetime import datetime
from typing import Optional

class TextHandler:
    @staticmethod
    def sanitize_filename(text: str, max_length: int = 50) -> str:
        """
        Sanitize text to create a valid filename
        """
        # Remove or replace invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', text)
        
        # Remove extra whitespace and newlines
        sanitized = ' '.join(sanitized.split())
        
        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip()
        
        # Ensure it's not empty
        if not sanitized.strip():
            sanitized = "telegram_text"
        
        return sanitized
    
    @staticmethod
    def save_text_content(text: str, link: str, downloads_dir: str = "downloads") -> str:
        """
        Save text content to a .txt file
        Returns the filename of the saved file
        """
        if not text or not text.strip():
            return None
        
        # Create downloads directory if it doesn't exist
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)
        
        # Create filename based on content preview and timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        content_preview = TextHandler.sanitize_filename(text)
        filename = f"{timestamp}_{content_preview}.txt"
        
        filepath = os.path.join(downloads_dir, filename)
        
        # Ensure unique filename
        counter = 1
        while os.path.exists(filepath):
            base_name = f"{timestamp}_{content_preview}_{counter}.txt"
            filepath = os.path.join(downloads_dir, base_name)
            counter += 1
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Source: {link}\n")
                f.write(f"Downloaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                f.write("-" * 50 + "\n\n")
                f.write(text)
            
            return os.path.basename(filepath)
        
        except Exception as e:
            print(f"Error saving text file: {e}")
            return None

    @staticmethod
    def extract_text_from_message(message) -> Optional[str]:
        """
        Extract text content from a Telegram message
        Returns the text if found, None otherwise
        """
        text_content = ""
        
        # Check for message text
        if hasattr(message, 'text') and message.text:
            text_content += message.text
        
        # Check for caption (text attached to media)
        if hasattr(message, 'caption') and message.caption:
            if text_content:
                text_content += "\n\n" + message.caption
            else:
                text_content = message.caption
        
        return text_content.strip() if text_content.strip() else None

    @staticmethod
    def has_media_content(message) -> bool:
        """
        Check if message contains media content (photo, video, audio, document, etc.)
        """
        media_attributes = [
            'photo', 'video', 'audio', 'document', 'animation', 
            'voice', 'video_note', 'sticker', 'contact', 'location'
        ]
        
        for attr in media_attributes:
            if hasattr(message, attr) and getattr(message, attr):
                return True
        
        return False