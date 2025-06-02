from pyrogram import Client as PyrogramClient
from dotenv import load_dotenv
import os
from typing import List

from src.console import Console
from src.intro import Intro
from src.barProgress import BarProgress
from src.textHandler import TextHandler
from src.messageExporter import MessageExporter

load_dotenv()

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")

class Client():
    def __init__(self):
        self.client = PyrogramClient(name="mysession", api_id=api_id, api_hash=api_hash)
        self.exporter = MessageExporter(self.client)
    
    async def start(self):
        await self.client.start()
    
    async def export_message_range(self, start_link: str, end_link: str) -> str:
        """Export messages between two links and create HTML file"""
        try:
            Console.clear()
            Intro.create()
            print("🚀 Starting message export...")
            print(f"📤 From: {start_link}")
            print(f"📥 To: {end_link}")
            print()
            
            html_filename = await self.exporter.export_message_range(start_link, end_link)
            
            if html_filename:
                print(f"\n✅ Export completed successfully!")
                print(f"📄 HTML file: {html_filename}")
                print(f"🎨 CSS file: export_styles.css")
                print(f"⚡ JS file: export_scripts.js")
                print("\n💡 Open the HTML file in your browser to view the exported messages.")
                return html_filename
            else:
                print("\n❌ Export failed!")
                return None
                
        except Exception as e:
            print(f"\n💥 Export error: {e}")
            return None
    
    async def export_json_only(self, start_link: str, end_link: str) -> str:
        """Export messages as JSON only without downloading media"""
        try:
            Console.clear()
            Intro.create()
            print("📊 Starting JSON export...")
            print(f"📤 From: {start_link}")
            print(f"📥 To: {end_link}")
            print()
            
            json_filename = await self.exporter.export_json_only(start_link, end_link)
            
            if json_filename:
                print(f"\n✅ JSON export completed!")
                print(f"📋 File created: {json_filename}")
                return json_filename
            else:
                print("\n❌ JSON export failed!")
                return None
                
        except Exception as e:
            print(f"\n💥 JSON export error: {e}")
            return None
    
    async def download_media(self, links: List[str]):
        try:
            media_count = 0
            text_count = 0
            service_count = 0
            
            for i, link in enumerate(links):
                message = await self._get_media_by_link(link)
                if not message: 
                    continue

                # Check if this is a service message
                if TextHandler.is_service_message(message):
                    service_text = TextHandler.extract_service_message_text(message)
                    if service_text:
                        filename = TextHandler.save_text_content(
                            service_text, link, "downloads/service_messages"
                        )
                        if filename:
                            service_count += 1
                            Console.clear()
                            Intro.create()
                            print(f"Service message saved as: {filename}")
                            print(f"Service messages saved: {service_count}")
                    continue

                # Check if message has text content
                text_content = TextHandler.extract_text_from_message(message)
                has_media = TextHandler.has_media_content(message)
                
                # Handle media download
                if has_media:
                    def get_progress(current, total):
                        Console.clear()
                        Intro.create()
                        print(f"Downloading media {media_count + 1}/{self._count_media_links(links)}:")
                        print(BarProgress.create(current, total))

                    await self.client.download_media(message, progress=get_progress)
                    media_count += 1
                    
                    # Also save caption if present
                    if text_content and hasattr(message, 'caption') and message.caption:
                        filename = TextHandler.save_text_content(
                            text_content, link, "downloads/captions"
                        )
                        if filename:
                            print(f"Caption saved as: {filename}")
                
                # Handle text-only messages or messages with only text content
                elif text_content:
                    filename = TextHandler.save_text_content(text_content, link)
                    if filename:
                        text_count += 1
                        Console.clear()
                        Intro.create()
                        print(f"Text content saved as: {filename}")
                        print(f"Text files saved: {text_count}")
                
                # If message has both media and caption, save caption separately
                elif has_media and text_content:
                    filename = TextHandler.save_text_content(
                        text_content, link, "downloads/captions"
                    )
                    if filename:
                        print(f"Caption saved as: {filename}")
            
            print(f"     ** Completed **")
            if media_count > 0:
                print(f"Media files downloaded: {media_count}")
            if text_count > 0:
                print(f"Text files saved: {text_count}")
            if service_count > 0:
                print(f"Service messages saved: {service_count}")
        
        except Exception as e:
            print(f"Download process error: {e}")

    def _count_media_links(self, links: List[str]) -> int:
        """Count how many links are likely to contain media for progress tracking"""
        # This is a simple estimation - in a real implementation you might want to
        # pre-check all messages to get an accurate count
        return len(links)

    async def _get_media_by_link(self, link: str):
        if "/s/" in link: 
            return await self._get_story_by_link(link)
        else:
            return await self._get_message_by_link(link)

    async def _get_story_by_link(self, link: str):
        try:
            base = link.split("https://t.me/")[-1]
            parts = base.split("/s/")
            username = parts[0]
            story_id = parts[1]

            return await self.client.get_stories(
                story_sender_chat_id=username,
                story_ids=int(story_id)
            )

        except Exception as e:
            print(f"Something went wrong while trying to get the story: {e}")

    
    async def _get_message_by_link(self, link: str):
        try:
            group_id: str | int
            message_id: str | int

            if link.startswith("https://t.me/c/"):
                base = link.split("https://t.me/c/")[-1]
                parts = base.split("/")

                if len(parts) == 3:
                    topic_id = parts[1]
                    message_id = parts[2]
                else:
                    message_id = parts[1]

                group_id = int(f"-100{parts[0]}")
            
            else:
                base = link.split("https://t.me/")[-1]
                parts = base.split("/")

                group_id = parts[0]
                message_id = parts[1]

            message_id = int(message_id) if not "?" in message_id else int(message_id.split("?")[0])

            return await self.client.get_messages(
                chat_id=group_id, 
                message_ids=message_id
            )

        except Exception as e:
            print(f'Something went wrong while trying to get the message: {e}')