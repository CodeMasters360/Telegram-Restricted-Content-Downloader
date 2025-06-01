import os
import re
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
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
        
        # Get all messages in range with full JSON data
        messages_data = await self._get_messages_with_json(chat_id, start_msg_id, end_msg_id)
        
        # Download media files
        media_files = await self._download_range_media(messages_data, downloads_dir)
        
        # Generate HTML file with JSON data and reply info
        html_filename = self._generate_enhanced_html_export(messages_data, media_files, downloads_dir, start_link, end_link)
        
        # Also save JSON file
        json_filename = self._save_json_export(messages_data, downloads_dir)
        
        return html_filename

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
                    # Convert message to dict and add extra metadata
                    msg_dict = self._message_to_dict(message)
                    
                    # Add reply information
                    reply_info = await self._get_reply_info(message)
                    if reply_info:
                        msg_dict['reply_to'] = reply_info
                    
                    messages_data.append(msg_dict)
                    
            except Exception as e:
                print(f"Could not get message {msg_id}: {e}")
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
            'reactions': []
        }
        
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
            if msg_data['media_type']:
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
                json.dump(export_data, f, indent=2, ensure_ascii=False)
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
    
    def _generate_enhanced_html_export(self, messages_data: List[Dict], media_files: List[Dict], downloads_dir: str, start_link: str, end_link: str) -> str:
        """Generate enhanced HTML file with JSON data and reply information"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_filename = f"telegram_export_{timestamp}.html"
        html_path = os.path.join(downloads_dir, html_filename)
        
        media_lookup = {item['message_id']: item['path'] for item in media_files}
        
        # Create message ID lookup for scroll-to functionality
        message_ids = [msg['id'] for msg in messages_data]
        
        html_content = f'<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Telegram Export with JSON Data</title><style>body{{font-family:Arial,sans-serif;margin:20px;background:#f5f5f5}}h1{{color:#0088cc;text-align:center}}h2{{color:#333;border-bottom:2px solid #0088cc;padding-bottom:5px}}.export-info{{background:#fff;padding:15px;margin-bottom:20px;border-radius:5px;box-shadow:0 2px 5px rgba(0,0,0,0.1)}}.message{{background:#fff;margin-bottom:15px;padding:15px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1);position:relative;transition:all 0.3s ease}}.message-header{{font-size:12px;color:#666;margin-bottom:10px;border-bottom:1px solid #eee;padding-bottom:5px}}.message-text{{line-height:1.6;margin-bottom:10px}}.message-media{{margin:10px 0}}img{{max-width:100%;height:auto;border-radius:5px}}video{{max-width:100%;height:auto;border-radius:5px}}audio{{width:100%}}.media-file{{background:#f9f9f9;padding:10px;border-radius:5px;margin:5px 0}}.caption{{font-style:italic;color:#666;margin-top:10px}}.reply-info{{background:#e8f4fd;border-left:4px solid #0088cc;padding:10px;margin:10px 0;border-radius:0 5px 5px 0;cursor:pointer;transition:background 0.2s ease}}.reply-info:hover{{background:#d4edda}}.reply-preview{{font-size:14px;color:#555}}.json-toggle{{background:#f0f0f0;border:1px solid #ccc;padding:5px 10px;border-radius:3px;cursor:pointer;font-size:12px;margin-top:10px;display:inline-block}}.json-data{{display:none;background:#2d2d2d;color:#f8f8f2;padding:15px;border-radius:5px;margin-top:10px;font-family:monospace;font-size:12px;white-space:pre-wrap;max-height:300px;overflow-y:auto}}.stats{{background:#e8f4fd;padding:10px;border-radius:5px;margin-top:20px}}.media-info{{font-size:12px;color:#888;margin-top:5px}}.highlight{{background:#ffeb3b!important;border:2px solid #ff9800!important;transform:scale(1.02)}}.reply-link{{color:#0088cc;text-decoration:underline}}</style><script>function toggleJson(id){{var elem=document.getElementById("json-"+id);elem.style.display=elem.style.display==="none"?"block":"none"}}function scrollToMessage(messageId){{var targetMsg=document.getElementById("msg-"+messageId);if(targetMsg){{targetMsg.scrollIntoView({{behavior:"smooth",block:"center"}});targetMsg.classList.add("highlight");setTimeout(function(){{targetMsg.classList.remove("highlight")}},1000)}}else{{alert("Replied message not found in this export range")}}}}window.onload=function(){{document.querySelectorAll(".reply-info").forEach(function(elem){{elem.addEventListener("click",function(){{var messageId=this.getAttribute("data-reply-to");if(messageId)scrollToMessage(messageId)}})}})}};</script></head><body><h1>Telegram Messages Export with JSON Data</h1><div class="export-info"><h2>Export Information</h2><p><strong>Export Date:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p><p><strong>Start Link:</strong> <a href="{start_link}" target="_blank">{start_link}</a></p><p><strong>End Link:</strong> <a href="{end_link}" target="_blank">{end_link}</a></p><p><strong>Total Messages:</strong> {len(messages_data)}</p></div><h2>Messages</h2>'
        
        for msg_data in messages_data:
            sender = msg_data.get('from_user', {}).get('first_name', 'Channel') if msg_data.get('from_user') else 'Channel'
            msg_date = msg_data.get('date', 'Unknown')
            
            html_content += f'<div class="message" id="msg-{msg_data["id"]}"><div class="message-header">Message ID: {msg_data["id"]} | Date: {msg_date} | From: {sender}'
            
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
                html_content += f'<div class="message-text">{escaped_text}</div>'
            
            # Media content
            if msg_data['id'] in media_lookup:
                media_path = media_lookup[msg_data['id']]
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
            html_content += f'<div class="json-toggle" onclick="toggleJson({msg_data["id"]})">Show/Hide JSON Data</div><div id="json-{msg_data["id"]}" class="json-data">{json.dumps(msg_data, indent=2, ensure_ascii=False)}</div></div>'
        
        # Add statistics
        media_count = len(media_files)
        text_only_count = len([m for m in messages_data if (m.get('text') or m.get('caption')) and not m.get('media_type')])
        reply_count = len([m for m in messages_data if m.get('reply_to')])
        
        html_content += f'<div class="stats"><h2>Export Statistics</h2><p>Total Messages: {len(messages_data)}</p><p>Messages with Media: {media_count}</p><p>Text-only Messages: {text_only_count}</p><p>Reply Messages: {reply_count}</p></div></body></html>'
        
        try:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            return html_filename
        except Exception as e:
            print(f"Error creating HTML file: {e}")
            return None
