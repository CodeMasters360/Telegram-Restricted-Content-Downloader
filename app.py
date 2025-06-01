import threading
import pyperclip  # type: ignore
import time
import os
import asyncio
from typing import List
import os

from src.intro import Intro
from src.console import Console
from src.exceptions import NoContinueException
from src.client import Client
from src.fileManager import FileManager

links = []
running = True
last_text = ""

def monitor_clipboard():
    global running, last_text

    while running:
        try:
            current_text = pyperclip.paste()

            if not current_text.startswith("https://t.me/"): raise NoContinueException()
            if not current_text.strip(): raise NoContinueException()
            if current_text == last_text: raise NoContinueException()
            if current_text in links: raise NoContinueException()

            last_text = current_text
            links.append(current_text)

            if len(links) == 1:
                Console.clear()
                Intro.create()
                print("\n   >> LINKS CATCHED <<\n")

            print(f"{len(links)}) {current_text}")
        
        except NoContinueException: ...
        except Exception as e: print(e)

        time.sleep(0.5)


async def main():
    global running, links, last_text

    # Setup download directories
    FileManager.setup_directories()

    client = Client()
    await client.start()

    Console.clear()
    Intro.create()

    clipboard_thread = threading.Thread(target=monitor_clipboard, daemon=True)
    clipboard_thread.start()

    while running:
        command = input("").strip().lower()

        if command == "":
            if not len(links):
                print("Huh? you didn't copy any telegram media link yet...")
                continue

            print("Starting to download content...")
            print("Note: Text content will be saved as .txt files")

            await client.download_media(links)
            
            # Show download statistics
            stats = FileManager.get_download_stats()
            print(f"\nDownload Summary:")
            print(f"  Media files: {stats['media_files']}")
            print(f"  Text files: {stats['text_files']}")
            print(f"  Caption files: {stats['caption_files']}")
            
            links = []
            pyperclip.copy("")
            last_text = ""

        elif command == "r":
            links = []
            pyperclip.copy("")
            last_text = ""

            Console.clear()
            Intro.create()

        elif command.startswith("export"):
            parts = command.split()
            if len(parts) == 3:
                start_link = parts[1]
                end_link = parts[2]
                
                if start_link.startswith("https://t.me/") and end_link.startswith("https://t.me/"):
                    print("Starting export process...")
                    result = await client.export_message_range(start_link, end_link)
                    if result:
                        print(f"Export saved as: {result}")
                        print("You can open this HTML file in your browser to view the messages.")
                else:
                    print("Please provide valid Telegram links")
            else:
                print("Usage: export <start_link> <end_link>")
                print("Example: export https://t.me/c/123456789/1 https://t.me/c/123456789/10")

        elif command == "stats":
            stats = FileManager.get_download_stats()
            print(f"\nTotal Downloads:")
            print(f"  Total files: {stats['total_files']}")
            print(f"  Media files: {stats['media_files']}")
            print(f"  Text files: {stats['text_files']}")
            print(f"  Caption files: {stats['caption_files']}")
            
            recent = FileManager.list_recent_files(limit=5)
            if recent:
                print(f"\nRecent downloads:")
                for file in recent:
                    print(f"  {file}")

        elif command == "exit":
            print("Exiting...")
            running = False

        else:
            print("Available commands:")
            print("  [Enter] - Download all queued links")
            print("  r - Reset queue")
            print("  export <start_link> <end_link> - Export message range to HTML")
            print("  stats - Show download statistics")
            print("  exit - Exit application")


if __name__ == "__main__":
    asyncio.run(main())