import os
import re
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from src.textHandler import TextHandler
# Add import for MessageServiceType
try:
    from pyrogram.enums import MessageServiceType
except ImportError:
    MessageServiceType = None

class MessageExporter:
    def __init__(self, client):
        self.client = client
        self.exported_media = []
        self.total_messages = 0
        self.processed_messages = 0
        
    async def export_message_range(self, start_link: str, end_link: str, downloads_dir: str = "downloads/exports") -> str:
        """Export messages between start_link and end_link and create HTML file with parallel processing"""
        try:
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
            
            self.total_messages = end_msg_id - start_msg_id + 1
            self.processed_messages = 0
            
            print(f"Starting export of {self.total_messages} messages...")
            
            # Get all messages in range with full JSON data using parallel processing
            messages_data = await self._get_messages_with_json_parallel(chat_id, start_msg_id, end_msg_id)
            
            print("Downloading media files...")
            # Download media files in parallel
            media_files = await self._download_range_media_parallel(messages_data, downloads_dir)
            
            print("Generating files...")
            # Create separate CSS and JS files
            self._create_css_file(downloads_dir)
            self._create_js_file(downloads_dir)
            
            # Generate HTML file with external CSS/JS references
            html_filename = self._generate_enhanced_html_export(messages_data, media_files, downloads_dir, start_link, end_link)
            
            # Also save JSON file
            json_filename = self._save_json_export(messages_data, downloads_dir)
            
            return html_filename
        except Exception as e:
            # If everything fails, create a minimal error HTML file
            print(f"Critical export error: {e}")
            return self._create_emergency_html(start_link, end_link, str(e), downloads_dir)

    async def _get_messages_with_json_parallel(self, chat_id: str, start_msg_id: int, end_msg_id: int, batch_size: int = 10) -> List[Dict]:
        """Get messages with complete JSON data and reply information using parallel processing"""
        all_message_ids = list(range(start_msg_id, end_msg_id + 1))
        messages_data = []
        
        # Process messages in batches
        for i in range(0, len(all_message_ids), batch_size):
            batch_ids = all_message_ids[i:i + batch_size]
            
            # Create tasks for parallel processing
            tasks = [self._get_single_message_with_json(chat_id, msg_id) for msg_id in batch_ids]
            
            # Execute batch in parallel
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for msg_id, result in zip(batch_ids, batch_results):
                if isinstance(result, Exception):
                    messages_data.append({
                        'id': msg_id,
                        'error': f"Could not get message {msg_id}: {result}",
                        'log': f"Could not get message {msg_id}: {result}",
                        'date': None
                    })
                else:
                    messages_data.append(result)
                
                self.processed_messages += 1
                self._print_progress("Fetching messages")
        
        # Sort messages by ID to maintain order
        messages_data.sort(key=lambda x: x['id'])
        return messages_data

    async def _get_single_message_with_json(self, chat_id: str, msg_id: int) -> Dict:
        """Get a single message with JSON data"""
        try:
            message = await self.client.get_messages(chat_id=chat_id, message_ids=msg_id)
            if message and not message.empty:
                try:
                    # Convert message to dict and add extra metadata
                    msg_dict = self._message_to_dict(message)
                    # Add reply information
                    reply_info = await self._get_reply_info(message)
                    if reply_info:
                        msg_dict['reply_to'] = reply_info
                    # Try to make it JSON serializable (test only, not for saving)
                    json.dumps(msg_dict, ensure_ascii=False, default=str)
                    return msg_dict
                except Exception as e:
                    # If serialization fails, add error placeholder
                    return {
                        'id': msg_id,
                        'error': f"Could not serialize message {msg_id}: {e}",
                        'log': f"Could not serialize message {msg_id}: {e}",
                        'date': getattr(message, "date", None)
                    }
            else:
                # Message is empty or not found
                return {
                    'id': msg_id,
                    'error': f"Message {msg_id} not found or is empty.",
                    'log': f"Message {msg_id} not found or is empty.",
                    'date': None
                }
        except Exception as e:
            # Log the error for this message and continue
            return {
                'id': msg_id,
                'error': f"Could not get message {msg_id}: {e}",
                'log': f"Could not get message {msg_id}: {e}",
                'date': None
            }

    async def _download_range_media_parallel(self, messages_data: List[Dict], downloads_dir: str, batch_size: int = 5) -> List[Dict]:
        """Download media files for all messages using parallel processing"""
        media_messages = [msg for msg in messages_data if msg.get('media_type') and 'error' not in msg]
        media_files = []
        processed_media = 0
        
        if not media_messages:
            return media_files
        
        print(f"Found {len(media_messages)} messages with media")
        
        # Process media downloads in smaller batches to avoid overwhelming the client
        for i in range(0, len(media_messages), batch_size):
            batch = media_messages[i:i + batch_size]
            
            # Create tasks for parallel media download
            tasks = [self._download_single_media(msg_data, downloads_dir) for msg_data in batch]
            
            # Execute batch in parallel
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for msg_data, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    print(f"Failed to download media for message {msg_data['id']}: {result}")
                elif result:
                    media_files.append(result)
                
                processed_media += 1
                self._print_progress(f"Downloading media ({processed_media}/{len(media_messages)})")
        
        return media_files

    async def _download_single_media(self, msg_data: Dict, downloads_dir: str) -> Optional[Dict]:
        """Download media for a single message"""
        try:
            # Reconstruct message for download
            message = await self.client.get_messages(chat_id=msg_data['chat_id'], message_ids=msg_data['id'])
            if message and not message.empty:
                media_path = await self.client.download_media(message, file_name=f"{downloads_dir}/media/")
                if media_path:
                    return {'message_id': msg_data['id'], 'path': media_path}
        except Exception as e:
            raise Exception(f"Could not download media for message {msg_data['id']}: {e}")
        return None

    def _print_progress(self, operation: str):
        """Print progress bar for current operation"""
        if self.total_messages > 0:
            percentage = (self.processed_messages / self.total_messages) * 100
            bar_length = 30
            filled_length = int(bar_length * percentage // 100)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            print(f"\r{operation}: [{bar}] {percentage:.1f}% ({self.processed_messages}/{self.total_messages})", end='', flush=True)
            if self.processed_messages == self.total_messages:
                print()  # New line when complete

    def _create_css_file(self, downloads_dir: str):
        """Create separate CSS file"""
        css_content = "body {font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5;} h1 {color: #0088cc; text-align: center;} h2 {color: #333; border-bottom: 2px solid #0088cc; padding-bottom: 5px;} .export-info {background: #fff; padding: 15px; margin-bottom: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);} .message {background: #fff; margin-bottom: 15px; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); position: relative; transition: all 0.3s ease;} .service-message {background: #f8f9fa; border-left: 4px solid #6c757d; font-style: italic;} .message-header {font-size: 12px; color: #666; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px;} .message-text {line-height: 1.6; margin-bottom: 10px;} .service-text {color: #6c757d; font-weight: 500; text-align: center; padding: 10px;} .message-media {margin: 10px 0;} img {max-width: 100%; height: auto; border-radius: 5px;} video {max-width: 100%; height: auto; border-radius: 5px;} audio {width: 100%;} .media-file {background: #f9f9f9; padding: 10px; border-radius: 5px; margin: 5px 0;} .caption {font-style: italic; color: #666; margin-top: 10px;} .reply-info {background: #e8f4fd; border-left: 4px solid #0088cc; padding: 10px; margin: 10px 0; border-radius: 0 5px 5px 0; cursor: pointer; transition: background 0.2s ease;} .reply-info:hover {background: #d4edda;} .reply-preview {font-size: 14px; color: #555;} .json-toggle {background: #f0f0f0; border: 1px solid #ccc; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 12px; margin-top: 10px; display: inline-block;} .json-data {display: none; background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 5px; margin-top: 10px; font-family: monospace; font-size: 12px; white-space: pre-wrap; max-height: 300px; overflow-y: auto;} .stats {background: #e8f4fd; padding: 10px; border-radius: 5px; margin-top: 20px;} .media-info {font-size: 12px; color: #888; margin-top: 5px;} .highlight {background: #ffeb3b !important; border: 2px solid #ff9800 !important; transform: scale(1.02);} .reply-link {color: #0088cc; text-decoration: underline;}"
        css_path = os.path.join(downloads_dir, "export_styles.css")
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write(css_content)

    def _create_js_file(self, downloads_dir: str):
        """Create separate JavaScript file"""
        js_content = "function toggleJson(id) {var elem = document.getElementById('json-' + id); elem.style.display = elem.style.display === 'none' ? 'block' : 'none';} function scrollToMessage(messageId) {var targetMsg = document.getElementById('msg-' + messageId); if (targetMsg) {targetMsg.scrollIntoView({behavior: 'smooth', block: 'center'}); targetMsg.classList.add('highlight'); setTimeout(function() {targetMsg.classList.remove('highlight');}, 1000);} else {alert('Replied message not found in this export range');}} window.onload = function() {document.querySelectorAll('.reply-info').forEach(function(elem) {elem.addEventListener('click', function() {var messageId = this.getAttribute('data-reply-to'); if (messageId) scrollToMessage(messageId);});});};"
        js_path = os.path.join(downloads_dir, "export_scripts.js")
        with open(js_path, 'w', encoding='utf-8') as f:
            f.write(js_content)

    def _create_emergency_html(self, start_link: str, end_link: str, error_msg: str, downloads_dir: str) -> str:
        """Create emergency HTML file when export completely fails"""
        try:
            if not os.path.exists(downloads_dir):
                os.makedirs(downloads_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_filename = f"telegram_export_emergency_{timestamp}.html"
            html_path = os.path.join(downloads_dir, html_filename)
            emergency_html = f'<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Telegram Export - Emergency</title><style>body {{font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5;}} .emergency {{background: #fff; padding: 20px; border-radius: 5px; border-left: 4px solid #e74c3c;}} .info {{background: #fff; padding: 15px; margin-top: 20px; border-radius: 5px; border-left: 4px solid #3498db;}}</style></head><body><div class="emergency"><h2>⚠️ Export Emergency Recovery</h2><p><strong>The export process encountered a critical error, but this HTML file was created to preserve your request.</strong></p><p><strong>Start Link:</strong> {start_link}</p><p><strong>End Link:</strong> {end_link}</p><p><strong>Error Details:</strong> {error_msg}</p><p><strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p></div><div class="info"><h3>📋 Troubleshooting</h3><ul><li>Check if the message links are valid and accessible</li><li>Ensure you have access to the chat/channel</li><li>Try exporting a smaller range of messages</li><li>Check your internet connection</li><li>Restart the application and try again</li></ul></div></body></html>'
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(emergency_html)
            return html_filename
        except Exception as e2:
            print(f"Even emergency HTML creation failed: {e2}")
            return None

    async def export_json_only(self, start_link: str, end_link: str, downloads_dir: str = "downloads/exports") -> str:
        """Export only JSON data without downloading media"""
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)
            
        start_info = self._parse_message_link(start_link)
        end_info = self._parse_message_link(end_link)
        
        if not start_info or not end_info or start_info['chat_id'] != end_info['chat_id']:
            raise ValueError("Invalid or mismatched message links")
            
        chat_id = start_info['chat_id']
        start_msg_id = min(start_info['message_id'], end_info['message_id'])
        end_msg_id = max(start_info['message_id'], end_info['message_id'])
        
        messages_data = await self._get_messages_with_json(chat_id, start_msg_id, end_msg_id)
        json_filename = self._save_json_export(messages_data, downloads_dir)
        
        return json_filename

    async def _get_messages_with_json(self, chat_id: str, start_msg_id: int, end_msg_id: int) -> List[Dict]:
        """Get messages with complete JSON data and reply information"""
        messages_data = []
        
        for msg_id in range(start_msg_id, end_msg_id + 1):
            try:
                message = await self.client.get_messages(chat_id=chat_id, message_ids=msg_id)
                if message and not message.empty:
                    try:
                        # Convert message to dict and add extra metadata
                        msg_dict = self._message_to_dict(message)
                        # Add reply information
                        reply_info = await self._get_reply_info(message)
                        if reply_info:
                            msg_dict['reply_to'] = reply_info
                        # Try to make it JSON serializable (test only, not for saving)
                        json.dumps(msg_dict, ensure_ascii=False, default=str)
                        messages_data.append(msg_dict)
                    except Exception as e:
                        # If serialization fails, add error placeholder
                        messages_data.append({
                            'id': msg_id,
                            'error': f"Could not serialize message {msg_id}: {e}",
                            'log': f"Could not serialize message {msg_id}: {e}",
                            'date': getattr(message, "date", None)
                        })
                else:
                    # Message is empty or not found
                    messages_data.append({
                        'id': msg_id,
                        'error': f"Message {msg_id} not found or is empty.",
                        'log': f"Message {msg_id} not found or is empty.",
                        'date': None
                    })
            except Exception as e:
                # Log the error for this message and continue
                messages_data.append({
                    'id': msg_id,
                    'error': f"Could not get message {msg_id}: {e}",
                    'log': f"Could not get message {msg_id}: {e}",
                    'date': None
                })
                continue
        
        return messages_data

    def _message_to_dict(self, message) -> Dict:
        """Convert Pyrogram message object to dictionary with all available data"""
        msg_dict = {
            'id': message.id,
            'date': message.date.isoformat() if message.date else None,
            'chat_id': getattr(message.chat, 'id', None) if message.chat else None,
            'chat_title': getattr(message.chat, 'title', None) if message.chat else None,
            'chat_username': getattr(message.chat, 'username', None) if message.chat else None,
            'from_user': None,
            'text': message.text,
            'caption': message.caption,
            'media_type': None,
            'media_info': {},
            'reply_to_message_id': message.reply_to_message_id,
            'forward_from': None,
            'edit_date': message.edit_date.isoformat() if message.edit_date else None,
            'views': getattr(message, 'views', None),
            'entities': [],
            'caption_entities': [],
            'reactions': [],
            'is_service': False,
            'service_type': None,
            'service_text': None
        }
        
        # Check if this is a service message
        if TextHandler.is_service_message(message):
            msg_dict['is_service'] = True
            # Try to get the enum type if available
            service_type_name = None
            service_type_class = type(message.service).__name__ if message.service else None
            if hasattr(message.service, "type"):
                # If it's a Pyrogram MessageServiceType enum, get its name
                try:
                    service_type_enum = message.service.type
                    if hasattr(service_type_enum, "name"):
                        service_type_name = service_type_enum.name
                    else:
                        service_type_name = str(service_type_enum)
                except Exception:
                    service_type_name = None
            msg_dict['service_type'] = service_type_name or service_type_class
            msg_dict['service_type_class'] = service_type_class
            msg_dict['service_text'] = TextHandler.extract_service_message_text(message)
        
        # Add user information
        if message.from_user:
            msg_dict['from_user'] = {
                'id': message.from_user.id,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name,
                'username': message.from_user.username,
                'is_bot': message.from_user.is_bot
            }

        # Add media information (use sizes for photo)
        if message.photo:
            # Use the largest size available
            if hasattr(message.photo, "sizes") and message.photo.sizes:
                largest = max(message.photo.sizes, key=lambda s: getattr(s, "file_size", 0) or 0)
                msg_dict['media_type'] = 'photo'
                msg_dict['media_info'] = {
                    'file_id': getattr(largest, 'file_id', None),
                    'file_size': getattr(largest, 'file_size', None),
                    'width': getattr(largest, 'width', None),
                    'height': getattr(largest, 'height', None)
                }
            else:
                msg_dict['media_type'] = 'photo'
                msg_dict['media_info'] = {}
        elif message.video:
            msg_dict['media_type'] = 'video'
            msg_dict['media_info'] = {'file_id': message.video.file_id, 'duration': message.video.duration, 'width': message.video.width, 'height': message.video.height, 'file_size': getattr(message.video, 'file_size', None)}
        elif message.audio:
            msg_dict['media_type'] = 'audio'
            msg_dict['media_info'] = {'file_id': message.audio.file_id, 'duration': message.audio.duration, 'title': message.audio.title, 'performer': message.audio.performer, 'file_size': getattr(message.audio, 'file_size', None)}
        elif message.voice:
            msg_dict['media_type'] = 'voice'
            msg_dict['media_info'] = {'file_id': message.voice.file_id, 'duration': message.voice.duration, 'file_size': getattr(message.voice, 'file_size', None)}
        elif message.document:
            msg_dict['media_type'] = 'document'
            msg_dict['media_info'] = {'file_id': message.document.file_id, 'file_name': message.document.file_name, 'mime_type': message.document.mime_type, 'file_size': getattr(message.document, 'file_size', None)}
        elif message.sticker:
            msg_dict['media_type'] = 'sticker'
            msg_dict['media_info'] = {'file_id': message.sticker.file_id, 'emoji': message.sticker.emoji, 'set_name': getattr(message.sticker, 'set_name', None)}

        # Add entities if present
        if message.entities:
            msg_dict['entities'] = [{'type': e.type, 'offset': e.offset, 'length': e.length, 'url': getattr(e, 'url', None)} for e in message.entities]
        
        if message.caption_entities:
            msg_dict['caption_entities'] = [{'type': e.type, 'offset': e.offset, 'length': e.length, 'url': getattr(e, 'url', None)} for e in message.caption_entities]
        
        # Add forward information using forward_origin only
        if hasattr(message, 'forward_origin') and message.forward_origin:
            if hasattr(message.forward_origin, 'sender_user'):
                msg_dict['forward_from'] = {
                    'user_id': message.forward_origin.sender_user.id,
                    'first_name': message.forward_origin.sender_user.first_name,
                    'username': message.forward_origin.sender_user.username
                }
            elif hasattr(message.forward_origin, 'sender_chat'):
                msg_dict['forward_from'] = {
                    'chat_id': message.forward_origin.sender_chat.id,
                    'chat_title': message.forward_origin.sender_chat.title,
                    'chat_username': message.forward_origin.sender_chat.username
                }
        # ...do not use deprecated forward_from or forward_from_chat...

        # Add reactions if present (Pyrogram >=2.0)
        try:
            outgoing_emojis = set()
            if hasattr(message, "outgoing_reaction") and message.outgoing_reaction:
                for r in message.outgoing_reaction:
                    emoji = getattr(r, "emoji", None)
                    if emoji:
                        outgoing_emojis.add(emoji)
            if hasattr(message, "reactions") and message.reactions:
                # Try .results (new Pyrogram)
                if hasattr(message.reactions, "results") and message.reactions.results:
                    for reaction in message.reactions.results:
                        emoji = getattr(reaction.reaction, "emoji", None)
                        if not emoji:
                            custom_emoji_id = getattr(reaction.reaction, "custom_emoji_id", None)
                            if custom_emoji_id:
                                emoji = f"[custom:{custom_emoji_id}]"
                        if not emoji:
                            emoji = "[unknown]"
                        count = getattr(reaction, "count", None)
                        chosen = emoji in outgoing_emojis
                        msg_dict['reactions'].append({
                            'emoji': emoji,
                            'count': count,
                            'chosen': chosen
                        })
                # Try .reactions (fork/older Pyrogram)
                elif hasattr(message.reactions, "reactions") and message.reactions.reactions:
                    for reaction in message.reactions.reactions:
                        # --- FIX: get emoji from reaction.type.emoji ---
                        emoji = None
                        if hasattr(reaction, "type") and hasattr(reaction.type, "emoji"):
                            emoji = getattr(reaction.type, "emoji", None)
                        if not emoji:
                            custom_emoji_id = getattr(getattr(reaction, "type", None), "custom_emoji_id", None)
                            if custom_emoji_id:
                                emoji = f"[custom:{custom_emoji_id}]"
                        if not emoji:
                            emoji = "[unknown]"
                        count = getattr(reaction, "count", None)
                        chosen = emoji in outgoing_emojis
                        msg_dict['reactions'].append({
                            'emoji': emoji,
                            'count': count,
                            'chosen': chosen
                        })
        except Exception:
            pass

        return msg_dict

    async def _get_reply_info(self, message) -> Optional[Dict]:
        """Get information about the message being replied to"""
        if not message.reply_to_message_id:
            return None
        
        try:
            replied_message = await self.client.get_messages(chat_id=message.chat.id, message_ids=message.reply_to_message_id)
            if replied_message and not replied_message.empty:
                return {
                    'message_id': replied_message.id,
                    'date': replied_message.date.isoformat() if replied_message.date else None,
                    'text_preview': (replied_message.text[:100] + '...') if replied_message.text and len(replied_message.text) > 100 else replied_message.text,
                    'from_user': replied_message.from_user.first_name if replied_message.from_user else 'Channel',
                    'media_type': self._get_media_type(replied_message)
                }
        except Exception as e:
            print(f"Could not get reply info for message {message.reply_to_message_id}: {e}")
        
        return None

    def _get_media_type(self, message) -> Optional[str]:
        """Get media type from message"""
        if message.photo: return 'photo'
        elif message.video: return 'video'
        elif message.audio: return 'audio'
        elif message.voice: return 'voice'
        elif message.document: return 'document'
        elif message.sticker: return 'sticker'
        return None

    async def _download_range_media(self, messages_data: List[Dict], downloads_dir: str) -> List[Dict]:
        """Download media files for all messages"""
        media_files = []
        
        for msg_data in messages_data:
            # Skip error messages
            if 'error' in msg_data:
                continue
                
            if msg_data.get('media_type'):
                try:
                    # Reconstruct message for download
                    message = await self.client.get_messages(chat_id=msg_data['chat_id'], message_ids=msg_data['id'])
                    if message and not message.empty:
                        media_path = await self.client.download_media(message, file_name=f"{downloads_dir}/media/")
                        if media_path:
                            media_files.append({'message_id': msg_data['id'], 'path': media_path})
                except Exception as e:
                    print(f"Could not download media for message {msg_data['id']}: {e}")
        
        return media_files

    def _save_json_export(self, messages_data: List[Dict], downloads_dir: str) -> str:
        """Save complete JSON export"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"telegram_export_{timestamp}.json"
        json_path = os.path.join(downloads_dir, json_filename)
        
        export_data = {
            'export_info': {
                'export_date': datetime.now().isoformat(),
                'total_messages': len(messages_data),
                'exported_by': 'Telegram-Restricted-Content-Downloader'
            },
            'messages': messages_data
        }
        
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
            return json_filename
        except Exception as e:
            print(f"Error saving JSON file: {e}")
            return None

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
    
    # --- RTL detection helper ---
    def _is_rtl_text(self, text: str) -> bool:
        """
        Detect if the text is mostly Arabic/Persian and should be rendered RTL.
        """
        if not text:
            return False
        rtl_chars = 0
        total_chars = 0
        for c in text:
            # Arabic and Persian Unicode blocks
            if (
                '\u0600' <= c <= '\u06FF' or  # Arabic
                '\u0750' <= c <= '\u077F' or  # Arabic Supplement
                '\u08A0' <= c <= '\u08FF' or  # Arabic Extended-A
                '\uFB50' <= c <= '\uFDFF' or  # Arabic Presentation Forms-A
                '\uFE70' <= c <= '\uFEFF' or  # Arabic Presentation Forms-B
                '\u200F' == c                 # RTL mark
            ):
                rtl_chars += 1
            if c.isalpha():
                total_chars += 1
        # If first non-space char is RTL, or >40% of letters are RTL, treat as RTL
        first_nonspace = next((ch for ch in text if not ch.isspace()), '')
        first_is_rtl = (
            '\u0600' <= first_nonspace <= '\u06FF' or
            '\u0750' <= first_nonspace <= '\u077F' or
            '\u08A0' <= first_nonspace <= '\u08FF' or
            '\uFB50' <= first_nonspace <= '\uFDFF' or
            '\uFE70' <= first_nonspace <= '\uFEFF' or
            '\u200F' == first_nonspace
        )
        if total_chars == 0:
            return False
        rtl_ratio = rtl_chars / total_chars
        return first_is_rtl or rtl_ratio > 0.4

    def _generate_enhanced_html_export(self, messages_data: List[Dict], media_files: List[Dict], downloads_dir: str, start_link: str, end_link: str) -> str:
        """Generate enhanced HTML file with external CSS and JS references"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_filename = f"telegram_export_{timestamp}.html"
            html_path = os.path.join(downloads_dir, html_filename)
            
            media_lookup = {item['message_id']: item['path'] for item in media_files}
            message_ids = [msg['id'] for msg in messages_data if 'error' not in msg]
            
            # Count failed and successful messages
            failed_messages = [msg for msg in messages_data if 'error' in msg]
            successful_messages = [msg for msg in messages_data if 'error' not in msg]
            service_messages = [msg for msg in successful_messages if msg.get('is_service')]
            
            # HTML header with external CSS and JS references
            html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Telegram Export with JSON Data</title>
    <link rel="stylesheet" href="export_styles.css">
</head>
<body>
    <h1>Telegram Messages Export with JSON Data</h1>
    <div class="export-info">
        <h2>Export Information</h2>
        <p><strong>Export Date:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p><strong>Start Link:</strong> <a href="{start_link}" target="_blank">{start_link}</a></p>
        <p><strong>End Link:</strong> <a href="{end_link}" target="_blank">{end_link}</a></p>
        <p><strong>Total Messages:</strong> {len(messages_data)}</p>
        <p><strong>Successful:</strong> {len(successful_messages)}</p>
        <p><strong>Service Messages:</strong> {len(service_messages)}</p>
        <p><strong>Failed:</strong> {len(failed_messages)}</p>
    </div>
    <h2>Messages</h2>'''
            
            for msg_data in messages_data:
                # If this is an error/log placeholder, render with clickable failed link
                if 'error' in msg_data:
                    html_content += (
                        f'<div class="message" id="msg-{msg_data["id"]}" style="background:#ffeaea;border:1px solid #ff8888;">'
                        f'<div class="message-header" style="color:#b71c1c;">Message ID: {msg_data["id"]} | ERROR</div>'
                        f'<div class="message-text" style="color:#b71c1c;"><b>Error:</b> {msg_data.get("error", "Unknown error")}</div>'
                        f'<div style="margin-top:10px;"><strong>Check manually:</strong> <a href="{self._reconstruct_message_link(msg_data, start_link)}" target="_blank" style="color:#0088cc;">{self._reconstruct_message_link(msg_data, start_link)}</a></div>'
                        f'</div>'
                    )
                    continue

                # Handle service messages with special styling
                if msg_data.get('is_service'):
                    service_text = msg_data.get('service_text', 'Service message')
                    service_type = msg_data.get('service_type', 'Unknown')
                    service_type_class = msg_data.get('service_type_class', '')
                    msg_date = msg_data.get('date', 'Unknown')
                    html_content += f'<div class="message service-message" id="msg-{msg_data["id"]}">'
                    html_content += (
                        f'<div class="message-header">'
                        f'<b>Service Message</b> | ID: {msg_data["id"]} | Date: {msg_date} | '
                        f'<span style="color:#0088cc;">Type: {service_type}'
                    )
                    if service_type_class and service_type_class != service_type:
                        html_content += f' <span style="color:#888;">({service_type_class})</span>'
                    html_content += '</span></div>'

                    # --- Show details for PINNED_MESSAGE and NEW_CHAT_MEMBERS ---
                    # We need to check the original message object for these fields
                    # Find the original message object in messages_data (if available)
                    original_message = None
                    if 'original_message_obj' in msg_data:
                        original_message = msg_data['original_message_obj']
                    # If not present, skip (for future extension)

                    # For PINNED_MESSAGE, show info about the pinned message
                    if service_type == "PINNED_MESSAGE":
                        # Try to get pinned_message info from msg_data if available
                        pinned_info = ""
                        try:
                            # If you want to show the pinned message text, you need to fetch it from the message object
                            # But here, we only have the dict, so we can't fetch it unless you store it in msg_data
                            # So, recommend to add this in _message_to_dict if needed
                            pinned_message_id = None
                            if hasattr(original_message, "pinned_message") and original_message.pinned_message:
                                pinned_message_id = getattr(original_message.pinned_message, "id", None)
                                pinned_text = getattr(original_message.pinned_message, "text", None)
                                pinned_caption = getattr(original_message.pinned_message, "caption", None)
                                pinned_content = pinned_text or pinned_caption or ""
                                pinned_info = f'<div><b>Pinned Message ID:</b> {pinned_message_id}</div>'
                                if pinned_content:
                                    pinned_info += f'<div><b>Pinned Content:</b> {pinned_content}</div>'
                            elif "pinned_message_id" in msg_data:
                                pinned_info = f'<div><b>Pinned Message ID:</b> {msg_data["pinned_message_id"]}</div>'
                        except Exception:
                            pass
                        if pinned_info:
                            html_content += f'<div class="service-text" style="background:#e3f2fd;">{pinned_info}</div>'

                    # For NEW_CHAT_MEMBERS, show info about the new members
                    if service_type == "NEW_CHAT_MEMBERS":
                        members_info = ""
                        try:
                            if hasattr(original_message, "new_chat_members") and original_message.new_chat_members:
                                members = original_message.new_chat_members
                                members_info = "<div><b>New Members Joined:</b> " + ", ".join(
                                    [getattr(u, "first_name", "Unknown") for u in members]
                                ) + "</div>"
                        except Exception:
                            pass
                        if members_info:
                            html_content += f'<div class="service-text" style="background:#e3f2fd;">{members_info}</div>'

                    html_content += f'<div class="service-text">{service_text}</div>'
                    # JSON toggle button and data for service messages
                    try:
                        json_data_str = json.dumps(msg_data, indent=2, ensure_ascii=False, default=str)
                    except Exception as e:
                        json_data_str = f"Could not serialize message: {e}"
                    html_content += f'<div class="json-toggle" onclick="toggleJson({msg_data["id"]})">Show/Hide JSON Data</div><div id="json-{msg_data["id"]}" class="json-data">{json_data_str}</div></div>'
                    continue

                # Compose sender display: Name (id) [@username]
                from_user = msg_data.get('from_user')
                if from_user:
                    sender_name = from_user.get('first_name') or from_user.get('last_name') or from_user.get('username') or "Deleted Account"
                    sender_id = from_user.get('id')
                    sender_username = from_user.get('username')
                else:
                    sender_name = "Deleted Account"
                    sender_id = None
                    sender_username = None

                sender_info = sender_name
                if sender_id is not None:
                    sender_info += f' (id: {sender_id})'
                if sender_username:
                    sender_info += f' [@{sender_username}]'

                msg_date = msg_data.get('date', 'Unknown')
                
                html_content += f'<div class="message" id="msg-{msg_data["id"]}"><div class="message-header">Message ID: {msg_data["id"]} | Date: {msg_date} | From: {sender_info}'
                
                if msg_data.get('media_type'):
                    html_content += f' | Media: {msg_data["media_type"]}'
                
                html_content += '</div>'
                
                # Show reply information with clickable functionality
                if msg_data.get('reply_to'):
                    reply = msg_data['reply_to']
                    reply_msg_id = reply['message_id']
                    is_in_range = reply_msg_id in message_ids
                    
                    if is_in_range:
                        html_content += f'<div class="reply-info" data-reply-to="{reply_msg_id}" title="Click to scroll to replied message"><strong>↳ Replying to message {reply_msg_id}</strong> by {reply["from_user"]}<div class="reply-preview">{reply.get("text_preview", "")}</div></div>'
                    else:
                        html_content += f'<div class="reply-info"><strong>↳ Replying to message {reply_msg_id}</strong> by {reply["from_user"]} <span style="color:#888;">(not in export range)</span><div class="reply-preview">{reply.get("text_preview", "")}</div></div>'
                
                # Message text
                if msg_data.get('text') or msg_data.get('caption'):
                    text_content = msg_data.get('text') or msg_data.get('caption')
                    escaped_text = text_content.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
                    # RTL detection
                    if self._is_rtl_text(text_content):
                        html_content += f'<div class="message-text" dir="rtl" style="text-align:right">{escaped_text}</div>'
                    else:
                        html_content += f'<div class="message-text">{escaped_text}</div>'
                
                # Media content
                if msg_data['id'] in media_lookup:
                    media_path = media_lookup[msg_data['id']]
                    filename = os.path.basename(media_path)
                    file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
                    relative_path = os.path.relpath(media_path, downloads_dir).replace('\\', '/')

                    # --- Sticker and animation/gif support ---
                    # Fixed stickers are webp, animated stickers are webm, GIFs are gif/mp4 (prefer gif if available)
                    if file_ext in ['jpg', 'jpeg', 'png']:
                        html_content += f'<div class="message-media"><img src="{relative_path}" alt="Image"></div>'
                    elif file_ext == 'webp':
                        # Fixed sticker (static)
                        html_content += f'<div class="message-media"><img src="{relative_path}" alt="Sticker" style="max-width:128px;background:#eee;"><div class="media-info">Sticker (.webp)</div></div>'
                    elif file_ext in ['mp4', 'webm']:
                        # mp4/webm can be video, animated sticker, or gif (Telegram GIFs are mp4, but if .gif exists, prefer .gif)
                        # Check if a .gif file exists for this media (same base name)
                        gif_path = os.path.splitext(media_path)[0] + ".gif"
                        gif_rel = os.path.relpath(gif_path, downloads_dir).replace('\\', '/')
                        if os.path.exists(gif_path):
                            html_content += f'<div class="message-media"><img src="{gif_rel}" alt="GIF"></div>'
                        elif msg_data.get('media_type') == 'sticker':
                            html_content += f'<div class="message-media"><video autoplay loop muted playsinline style="background:#eee;max-width:128px;"><source src="{relative_path}" type="video/{file_ext}">Your browser does not support animated stickers.</video><div class="media-info">Animated Sticker (.{file_ext})</div></div>'
                        else:
                            html_content += f'<div class="message-media"><video controls loop autoplay muted playsinline><source src="{relative_path}" type="video/{file_ext}">Your browser does not support video or GIFs. (Telegram GIFs are mp4 files)</video></div>'
                    elif file_ext == 'gif':
                        html_content += f'<div class="message-media"><img src="{relative_path}" alt="GIF"></div>'
                    elif file_ext == 'tgs':
                        # Lottie animation, not viewable in browser
                        html_content += f'<div class="media-file">🗂️ <a href="{relative_path}" target="_blank">{filename}</a> <span class="media-info">(Telegram animated sticker .tgs - not viewable in browser)</span></div>'
                    elif file_ext in ['mp3', 'wav', 'ogg', 'opus', 'oga']:
                        audio_type = "audio/ogg" if file_ext == "oga" else f"audio/{file_ext}"
                        html_content += f'<div class="message-media"><audio controls><source src="{relative_path}" type="{audio_type}">Your browser does not support audio.</audio></div>'
                    else:
                        html_content += f'<div class="media-file">📁 <a href="{relative_path}" target="_blank">{filename}</a></div>'

                    # Add media info
                    if msg_data.get('media_info'):
                        media_info = msg_data['media_info']
                        info_text = f"File size: {media_info.get('file_size', 'Unknown')}"
                        if media_info.get('duration'):
                            info_text += f" | Duration: {media_info['duration']}s"
                        html_content += f'<div class="media-info">{info_text}</div>'
                
                # Show reactions if present and not empty
                if msg_data.get('reactions') and len(msg_data['reactions']) > 0:
                    html_content += '<div class="message-reactions" style="margin-bottom:8px;">'
                    for reaction in msg_data['reactions']:
                        emoji = reaction.get('emoji', '')
                        count = reaction.get('count', 0)
                        chosen = reaction.get('chosen', False)
                        chosen_style = 'border:2px solid #0088cc;border-radius:50%;padding:2px;' if chosen else ''
                        html_content += f'<span style="display:inline-block;margin-right:8px;font-size:18px;{chosen_style}">{emoji} <span style="font-size:13px;color:#555;">{count}</span></span>'
                    html_content += '</div>'

                # JSON toggle button and data
                try:
                    json_data_str = json.dumps(msg_data, indent=2, ensure_ascii=False, default=str)
                except Exception as e:
                    json_data_str = f"Could not serialize message: {e}"
                html_content += f'<div class="json-toggle" onclick="toggleJson({msg_data["id"]})">Show/Hide JSON Data</div><div id="json-{msg_data["id"]}" class="json-data">{json_data_str}</div></div>'
            
            # Add statistics and close HTML with external JS reference
            media_count = len(media_files)
            text_only_count = len([m for m in successful_messages if (m.get('text') or m.get('caption')) and not m.get('media_type') and not m.get('is_service')])
            reply_count = len([m for m in successful_messages if m.get('reply_to')])
            
            html_content += f'''<div class="stats">
    <h2>Export Statistics</h2>
    <p>Total Messages: {len(messages_data)}</p>
    <p>Successfully Exported: {len(successful_messages)}</p>
    <p>Service Messages: {len(service_messages)}</p>
    <p>Failed Messages: {len(failed_messages)}</p>
    <p>Messages with Media: {media_count}</p>
    <p>Text-only Messages: {text_only_count}</p>
    <p>Reply Messages: {reply_count}</p>
</div>
<script src="export_scripts.js"></script>
</body>
</html>'''
            
            # Always try to write the HTML file, even if there were errors
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            return html_filename
        except Exception as e:
            print(f"HTML generation failed: {e}")
            # Create emergency HTML if normal generation fails
            return self._create_emergency_html(start_link, end_link, f"HTML generation error: {e}", downloads_dir)

    def _reconstruct_message_link(self, msg_data: Dict, start_link: str) -> str:
        """Reconstruct message link for failed messages"""
        chat_id = msg_data.get('chat_id') or 'unknown'
        msg_id = msg_data['id']
        
        if start_link.startswith("https://t.me/c/") and str(chat_id).startswith('-100'):
            clean_chat_id = str(chat_id)[4:] if str(chat_id).startswith('-100') else str(chat_id)
            return f"https://t.me/c/{clean_chat_id}/{msg_id}"
        else:
            try:
                username = start_link.split('https://t.me/')[-1].split('/')[0]
                return f"https://t.me/{username}/{msg_id}"
            except:
                return f"Message ID: {msg_id}"
