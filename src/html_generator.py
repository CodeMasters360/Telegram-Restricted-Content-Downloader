import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import html
import base64

class HTMLGenerator:
    def __init__(self):
        self.css_styles = """
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background-color: #0f1419;
                color: #ffffff;
                margin: 0;
                padding: 20px;
                line-height: 1.4;
            }
            
            .chat-container {
                max-width: 800px;
                margin: 0 auto;
                background-color: #17212b;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            }
            
            .chat-header {
                background: linear-gradient(135deg, #2481cc, #1c5a96);
                padding: 20px;
                text-align: center;
                color: white;
            }
            
            .chat-header h1 {
                margin: 0;
                font-size: 24px;
                font-weight: 500;
            }
            
            .chat-header .info {
                margin-top: 8px;
                opacity: 0.9;
                font-size: 14px;
            }
            
            .messages-container {
                padding: 20px;
                max-height: 80vh;
                overflow-y: auto;
            }
            
            .message {
                margin-bottom: 16px;
                display: flex;
                flex-direction: column;
            }
            
            .message.deleted {
                opacity: 0.5;
                font-style: italic;
                color: #8a8a8a;
            }
            
            .message-header {
                display: flex;
                align-items: center;
                margin-bottom: 6px;
                font-size: 13px;
            }
            
            .message-id {
                background-color: #2481cc;
                color: white;
                padding: 2px 8px;
                border-radius: 10px;
                font-weight: 500;
                margin-right: 10px;
                font-size: 11px;
            }
            
            .username {
                font-weight: 600;
                color: #64b5f6;
                margin-right: 8px;
            }
            
            .timestamp {
                color: #8a8a8a;
                font-size: 12px;
            }
            
            .message-content {
                background-color: #232e3c;
                padding: 12px 16px;
                border-radius: 12px;
                border-left: 3px solid #2481cc;
                position: relative;
            }
            
            .message-text {
                margin: 0;
                white-space: pre-wrap;
                word-wrap: break-word;
            }
            
            .media-container {
                margin-top: 10px;
                border-radius: 8px;
                overflow: hidden;
            }
            
            .media-item {
                display: block;
                max-width: 100%;
                border-radius: 8px;
            }
            
            .media-placeholder {
                background-color: #1a252f;
                padding: 20px;
                text-align: center;
                border-radius: 8px;
                border: 2px dashed #3a4a5c;
                color: #8a8a8a;
            }
            
            .voice-message {
                background-color: #1a252f;
                padding: 12px;
                border-radius: 20px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .voice-icon {
                width: 24px;
                height: 24px;
                background-color: #2481cc;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 12px;
            }
            
            .file-attachment {
                background-color: #1a252f;
                padding: 12px;
                border-radius: 8px;
                border: 1px solid #3a4a5c;
                display: flex;
                align-items: center;
                gap: 12px;
            }
            
            .file-icon {
                width: 32px;
                height: 32px;
                background-color: #2481cc;
                border-radius: 6px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 14px;
            }
            
            .file-info {
                flex: 1;
            }
            
            .file-name {
                font-weight: 500;
                margin-bottom: 2px;
            }
            
            .file-size {
                font-size: 12px;
                color: #8a8a8a;
            }
            
            .reply-to {
                background-color: #1a252f;
                border-left: 3px solid #64b5f6;
                padding: 8px 12px;
                margin-bottom: 8px;
                border-radius: 6px;
                font-size: 13px;
            }
            
            .reply-to .reply-username {
                color: #64b5f6;
                font-weight: 600;
                margin-bottom: 2px;
            }
            
            .reply-to .reply-text {
                color: #b0b0b0;
                font-style: italic;
            }
            
            .caption {
                margin-top: 8px;
                font-style: italic;
                color: #e0e0e0;
            }
            
            .error-message {
                background-color: #4a1a1a;
                border-left: 3px solid #ff6b6b;
                padding: 12px;
                border-radius: 8px;
                color: #ffb3b3;
            }
            
            .stats {
                background-color: #1a252f;
                padding: 15px;
                margin-top: 20px;
                border-radius: 8px;
                text-align: center;
                font-size: 13px;
                color: #8a8a8a;
            }
            
            .download-info {
                text-align: center;
                padding: 15px;
                background-color: #1a252f;
                margin-bottom: 20px;
                border-radius: 8px;
                font-size: 13px;
                color: #8a8a8a;
            }
        </style>
        """
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def escape_html(self, text: str) -> str:
        """Escape HTML characters"""
        if not text:
            return ""
        return html.escape(text)
    
    def format_timestamp(self, timestamp) -> str:
        """Format timestamp for display"""
        if hasattr(timestamp, 'strftime'):
            return timestamp.strftime("%Y-%m-%d %H:%M:%S")
        return str(timestamp)
    
    def generate_message_html(self, message_data: Dict[str, Any]) -> str:
        """Generate HTML for a single message"""
        if message_data.get('deleted', False):
            return f"""
            <div class="message deleted">
                <div class="message-header">
                    <span class="message-id">#{message_data.get('id', 'Unknown')}</span>
                    <span class="timestamp">Message deleted</span>
                </div>
                <div class="message-content">
                    <p class="message-text">This message was deleted</p>
                </div>
            </div>
            """
        
        # Message header
        username = self.escape_html(message_data.get('username', 'Unknown'))
        timestamp = self.format_timestamp(message_data.get('timestamp', ''))
        message_id = message_data.get('id', 'Unknown')
        
        html_content = f"""
        <div class="message">
            <div class="message-header">
                <span class="message-id">#{message_id}</span>
                <span class="username">{username}</span>
                <span class="timestamp">{timestamp}</span>
            </div>
        """
        
        # Reply information
        if message_data.get('reply_to'):
            reply = message_data['reply_to']
            reply_username = self.escape_html(reply.get('username', 'Unknown'))
            reply_text = self.escape_html(reply.get('text', 'Media message'))[:100]
            if len(reply.get('text', '')) > 100:
                reply_text += "..."
            
            html_content += f"""
            <div class="reply-to">
                <div class="reply-username">Replying to {reply_username}</div>
                <div class="reply-text">{reply_text}</div>
            </div>
            """
        
        html_content += '<div class="message-content">'
        
        # Message text
        if message_data.get('text'):
            text = self.escape_html(message_data['text'])
            html_content += f'<p class="message-text">{text}</p>'
        
        # Media content
        media_html = self.generate_media_html(message_data.get('media', {}))
        if media_html:
            html_content += media_html
        
        # Caption
        if message_data.get('caption'):
            caption = self.escape_html(message_data['caption'])
            html_content += f'<div class="caption">{caption}</div>'
        
        html_content += '</div></div>'
        
        return html_content
    
    def generate_media_html(self, media_data: Dict[str, Any]) -> str:
        """Generate HTML for media content"""
        if not media_data:
            return ""
        
        media_type = media_data.get('type', '')
        media_html = '<div class="media-container">'
        
        if media_type == 'photo':
            if media_data.get('local_path'):
                media_html += f'<img src="{media_data["local_path"]}" alt="Photo" class="media-item">'
            else:
                media_html += f'<div class="media-placeholder">📷 Photo ({self.format_file_size(media_data.get("size", 0))})</div>'
        
        elif media_type == 'video':
            if media_data.get('local_path'):
                media_html += f'<video controls class="media-item"><source src="{media_data["local_path"]}"></video>'
            else:
                duration = media_data.get('duration', 0)
                duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
                media_html += f'<div class="media-placeholder">🎥 Video ({duration_str}, {self.format_file_size(media_data.get("size", 0))})</div>'
        
        elif media_type == 'voice':
            duration = media_data.get('duration', 0)
            duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
            media_html += f'''
            <div class="voice-message">
                <div class="voice-icon">🎤</div>
                <div>Voice message ({duration_str})</div>
            </div>
            '''
        
        elif media_type == 'audio':
            title = media_data.get('title', 'Audio file')
            performer = media_data.get('performer', '')
            duration = media_data.get('duration', 0)
            duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
            
            if media_data.get('local_path'):
                media_html += f'<audio controls class="media-item"><source src="{media_data["local_path"]}"></audio>'
            
            display_title = f"{performer} - {title}" if performer else title
            media_html += f'<div class="caption">🎵 {self.escape_html(display_title)} ({duration_str})</div>'
        
        elif media_type == 'document':
            filename = media_data.get('filename', 'Document')
            size = self.format_file_size(media_data.get('size', 0))
            
            media_html += f'''
            <div class="file-attachment">
                <div class="file-icon">📄</div>
                <div class="file-info">
                    <div class="file-name">{self.escape
