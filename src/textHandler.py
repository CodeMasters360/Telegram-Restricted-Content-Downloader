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
        Extract text content from a Telegram message including service messages
        Returns the text if found, None otherwise
        """
        text_content = ""
        
        # Check for service message first
        service_text = TextHandler.extract_service_message_text(message)
        if service_text:
            text_content = service_text
        
        # Check for regular message text
        elif hasattr(message, 'text') and message.text:
            text_content += message.text
        
        # Check for caption (text attached to media)
        if hasattr(message, 'caption') and message.caption:
            if text_content:
                text_content += "\n\n" + message.caption
            else:
                text_content = message.caption
        
        return text_content.strip() if text_content.strip() else None

    @staticmethod
    def extract_service_message_text(message) -> Optional[str]:
        """
        Extract text from service messages (system notifications)
        """
        if not hasattr(message, 'service'):
            return None
            
        service = message.service
        if not service:
            return None
            
        # Handle different service message types
        service_type = type(service).__name__
        
        try:
            if service_type == "MessageServiceChatAddUser":
                users = service.users if hasattr(service, 'users') else []
                user_names = [TextHandler._get_user_display_name(user) for user in users]
                if user_names:
                    return f"👥 {', '.join(user_names)} joined the group"
                return "👥 Someone joined the group"
                
            elif service_type == "MessageServiceChatDeleteUser":
                user = service.user if hasattr(service, 'user') else None
                user_name = TextHandler._get_user_display_name(user) if user else "Someone"
                return f"👋 {user_name} left the group"
                
            elif service_type == "MessageServicePinMessage":
                return "📌 Message was pinned"
                
            elif service_type == "MessageServiceChatEditTitle":
                title = service.title if hasattr(service, 'title') else "Unknown"
                return f"✏️ Group title changed to: {title}"
                
            elif service_type == "MessageServiceChatEditPhoto":
                return "🖼️ Group photo was changed"
                
            elif service_type == "MessageServiceChatDeletePhoto":
                return "🗑️ Group photo was removed"
                
            elif service_type == "MessageServiceChatCreate":
                title = service.title if hasattr(service, 'title') else "Unknown"
                return f"🎉 Group '{title}' was created"
                
            elif service_type == "MessageServiceChatMigrateTo":
                return "📤 Group was migrated to supergroup"
                
            elif service_type == "MessageServiceChatMigrateFrom":
                return "📥 Group was migrated from basic group"
                
            elif service_type == "MessageServiceChannelCreate":
                title = service.title if hasattr(service, 'title') else "Unknown"
                return f"📢 Channel '{title}' was created"
                
            elif service_type == "MessageServiceChannelMigrateFrom":
                return "📥 Channel was migrated from group"
                
            elif service_type == "MessageServiceWebViewDataSent":
                return "🌐 Web app data was sent"
                
            elif service_type == "MessageServicePaymentSent":
                return "💳 Payment was sent"
                
            elif service_type == "MessageServiceContactRegistered":
                return "📱 Contact joined Telegram"
                
            elif service_type == "MessageServiceGiftedPremium":
                return "🎁 Premium subscription was gifted"
                
            else:
                # Generic service message
                return f"ℹ️ Service message: {service_type}"
                
        except Exception as e:
            return f"ℹ️ Service message (parsing error: {e})"

    @staticmethod
    def _get_user_display_name(user) -> str:
        """
        Get display name for a user object
        """
        if not user:
            return "Unknown User"
            
        name_parts = []
        if hasattr(user, 'first_name') and user.first_name:
            name_parts.append(user.first_name)
        if hasattr(user, 'last_name') and user.last_name:
            name_parts.append(user.last_name)
            
        if name_parts:
            return " ".join(name_parts)
        elif hasattr(user, 'username') and user.username:
            return f"@{user.username}"
        else:
            return "Unknown User"

    @staticmethod
    def is_service_message(message) -> bool:
        """
        Check if message is a service message
        """
        return hasattr(message, 'service') and message.service is not None

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