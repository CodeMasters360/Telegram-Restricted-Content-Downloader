import os
import re
from datetime import datetime
from typing import List, Dict, Any
from src.textHandler import TextHandler

class MessageExporter:
    def __init__(self, client):
        self.client = client
        self.exported_media = []
        
    async def export_message_range(self, start_link: str, end_link: str, downloads_dir: str = "downloads/exports") -> str:
        """Export messages between start_link and end_link and create HTML file"""
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)
            
        # Parse links to get message IDs and chat info
        start_info = self._parse_message_link(start_link)
        end_info = self._parse_message_link(end_link)
        
        if not start_info or not end_info or start_info['chat_id'] != end_info['chat_id']:
            raise ValueError("Invalid or mismatched message links")
            
        chat_id = start_info['chat_id']
        start_msg_id = min(start_info['message_id'], end_info['message_id'])
        end_msg_id = max(start_info['message_id'], end_info['message_id'])
        
        # Get all messages in range
        messages = []
        media_files = []
        
        for msg_id in range(start_msg_id, end_msg_id + 1):
            try:
                message = await self.client.get_messages(chat_id=chat_id, message_ids=msg_id)
                if message and not message.empty:
                    messages.append(message)
                    
                    # Download media if present
                    if TextHandler.has_media_content(message):
                        media_path = await self.client.download_media(message, file_name=f"{downloads_dir}/media/")
                        if media_path:
                            media_files.append({'message_id': msg_id, 'path': media_path})
                            
            except Exception as e:
                print(f"Could not get message {msg_id}: {e}")
                continue
        
        # Generate HTML file
        html_filename = self._generate_html_export(messages, media_files, downloads_dir, start_link, end_link)
        return html_filename
    
    def _parse_message_link(self, link: str) -> Dict[str, Any]:
        """Parse Telegram message link to extract chat_id and message_id"""
        try:
            if link.startswith("https://t.me/c/"):
                base = link.split("https://t.me/c/")[-1]
                parts = base.split("/")
                chat_id = int(f"-100{parts[0]}")
                message_id = int(parts[1].split("?")[0] if "?" in parts[1] else parts[1])
            else:
                base = link.split("https://t.me/")[-1]
                parts = base.split("/")
                chat_id = parts[0]
                message_id = int(parts[1].split("?")[0] if "?" in parts[1] else parts[1])
            
            return {'chat_id': chat_id, 'message_id': message_id}
        except:
            return None
    
    def _generate_html_export(self, messages: List, media_files: List[Dict], downloads_dir: str, start_link: str, end_link: str) -> str:
        """Generate HTML file with all messages and media"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_filename = f"telegram_export_{timestamp}.html"
        html_path = os.path.join(downloads_dir, html_filename)
        
        # Create media lookup dict
        media_lookup = {item['message_id']: item['path'] for item in media_files}
        
        # Generate HTML content
        html_content = f'<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Telegram Export</title><style>body{{font-family:Arial,sans-serif;margin:20px;background:#f5f5f5}}h1{{color:#0088cc;text-align:center}}h2{{color:#333;border-bottom:2px solid #0088cc;padding-bottom:5px}}.export-info{{background:#fff;padding:15px;margin-bottom:20px;border-radius:5px;box-shadow:0 2px 5px rgba(0,0,0,0.1)}}.message{{background:#fff;margin-bottom:15px;padding:15px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1)}}.message-header{{font-size:12px;color:#666;margin-bottom:10px;border-bottom:1px solid #eee;padding-bottom:5px}}.message-text{{line-height:1.6;margin-bottom:10px}}.message-media{{margin:10px 0}}img{{max-width:100%;height:auto;border-radius:5px}}video{{max-width:100%;height:auto;border-radius:5px}}audio{{width:100%}}.media-file{{background:#f9f9f9;padding:10px;border-radius:5px;margin:5px 0}}.caption{{font-style:italic;color:#666;margin-top:10px}}.stats{{background:#e8f4fd;padding:10px;border-radius:5px;margin-top:20px}}</style></head><body><h1>Telegram Messages Export</h1><div class="export-info"><h2>Export Information</h2><p><strong>Export Date:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p><p><strong>Start Link:</strong> <a href="{start_link}" target="_blank">{start_link}</a></p><p><strong>End Link:</strong> <a href="{end_link}" target="_blank">{end_link}</a></p><p><strong>Total Messages:</strong> {len(messages)}</p></div><h2>Messages</h2>'
        
        for message in messages:
            # Message header
            msg_date = message.date.strftime("%Y-%m-%d %H:%M:%S") if message.date else "Unknown"
            sender = getattr(message.from_user, 'first_name', 'Unknown') if message.from_user else 'Channel'
            
            html_content += f'<div class="message"><div class="message-header">Message ID: {message.id} | Date: {msg_date} | From: {sender}</div>'
            
            # Message text
            text_content = TextHandler.extract_text_from_message(message)
            if text_content:
                escaped_text = text_content.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
                html_content += f'<div class="message-text">{escaped_text}</div>'
            
            # Media content
            if message.id in media_lookup:
                media_path = media_lookup[message.id]
                filename = os.path.basename(media_path)
                file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
                
                relative_path = os.path.relpath(media_path, downloads_dir).replace('\\', '/')
                
                if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                    html_content += f'<div class="message-media"><img src="{relative_path}" alt="Image"></div>'
                elif file_ext in ['mp4', 'avi', 'mov', 'webm']:
                    html_content += f'<div class="message-media"><video controls><source src="{relative_path}" type="video/{file_ext}">Your browser does not support video.</video></div>'
                elif file_ext in ['mp3', 'wav', 'ogg', 'opus']:
                    html_content += f'<div class="message-media"><audio controls><source src="{relative_path}" type="audio/{file_ext}">Your browser does not support audio.</audio></div>'
                else:
                    html_content += f'<div class="media-file">📁 <a href="{relative_path}" target="_blank">{filename}</a></div>'
            
            html_content += '</div>'
        
        # Add statistics
        media_count = len(media_files)
        text_only_count = len([m for m in messages if TextHandler.extract_text_from_message(m) and not TextHandler.has_media_content(m)])
        
        html_content += f'<div class="stats"><h2>Export Statistics</h2><p>Total Messages: {len(messages)}</p><p>Messages with Media: {media_count}</p><p>Text-only Messages: {text_only_count}</p></div></body></html>'
        
        # Write HTML file
        try:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            return html_filename
        except Exception as e:
            print(f"Error creating HTML file: {e}")
            return None
