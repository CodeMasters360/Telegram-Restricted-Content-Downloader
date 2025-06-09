import asyncio
import re
from telethon.sync import TelegramClient
from telethon.errors import FloodWaitError, PhoneNumberInvalidError, SessionPasswordNeededError, PeerIdInvalidError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, DocumentAttributeFilename
import mimetypes
import os
from dotenv import load_dotenv
from datetime import datetime
import io
import time

# --- Load environment variables ---
load_dotenv()

# --- API Information ---
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")
SESSION_NAME = os.getenv("SESSION_NAME", "telegram_protected_session")

# --- Validate API Credentials ---
def check_api_credentials():
    """
    Validate API credentials configuration.
    """
    if API_ID == 0 or not API_HASH or not PHONE:
        raise ValueError(
            "API credentials are missing or invalid. Please ensure a `.env` file exists with the following keys:\n"
            "API_ID=your_api_id\nAPI_HASH=your_api_hash\nPHONE=your_phone_number\nSESSION_NAME=your_session_name"
        )

def parse_telegram_url(url):
    """
    Parse Telegram URL to extract channel ID and message ID.
    """
    private_pattern = r'https://t\.me/c/(\d+)/(\d+)'
    public_pattern = r'https://t\.me/([^/]+)/(\d+)'
    
    private_match = re.match(private_pattern, url)
    if private_match:
        channel_id = int(private_match.group(1))
        message_id = int(private_match.group(2))
        full_channel_id = int(f"-100{channel_id}")
        return full_channel_id, message_id, 'private'
    
    public_match = re.match(public_pattern, url)
    if public_match:
        channel_name = public_match.group(1)
        message_id = int(public_match.group(2))
        return channel_name, message_id, 'public'
    
    raise ValueError("Invalid Telegram URL format.")

async def login_with_retry(client: TelegramClient, max_retries=3):
    """
    Attempt login with retry logic.
    """
    for attempt in range(max_retries):
        try:
            print(f"🔄 Attempting login ({attempt + 1}/{max_retries})...")
            if not await client.is_user_authorized():
                await client.send_code_request(PHONE)
                code = input("🔑 Enter the verification code: ").strip()
                await client.sign_in(PHONE, code)
            print("✅ Login successful!")
            return True
        except FloodWaitError as e:
            print(f"⏰ Flood wait error: Retry after {e.seconds} seconds.")
            await asyncio.sleep(e.seconds)
        except PhoneNumberInvalidError:
            raise ValueError("❌ Invalid phone number.")
        except SessionPasswordNeededError:
            password = input("🔐 Enter your two-factor authentication password: ").strip()
            await client.sign_in(password=password)
        except Exception as e:
            print(f"❌ Login failed: {e}")
    return False

async def get_entity_safe(client, entity_id):
    """
    Safely get entity with multiple attempts and error handling.
    """
    try:
        entity = await client.get_entity(entity_id)
        return entity
    except (ValueError, PeerIdInvalidError) as e:
        print(f"⚠️ Direct entity resolution failed: {e}")
        
        try:
            print("🔍 Searching in dialogs...")
            async for dialog in client.iter_dialogs():
                if hasattr(dialog.entity, 'id') and dialog.entity.id == entity_id:
                    print(f"✅ Found entity in dialogs: {dialog.title}")
                    return dialog.entity
        except Exception as e:
            print(f"⚠️ Dialog search failed: {e}")
        
        raise ValueError(f"Could not resolve entity {entity_id}.")

def analyze_document(document):
    """
    Analyze document attributes and determine proper filename and MIME type.
    """
    filename = None
    mime_type = getattr(document, 'mime_type', '')
    extension = mimetypes.guess_extension(mime_type)

    for attr in getattr(document, 'attributes', []):
        if isinstance(attr, DocumentAttributeFilename):
            filename = attr.file_name

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds for uniqueness
        filename = f"file_{timestamp}{extension or '.bin'}"

    return filename, mime_type

async def download_protected_media(client, message):
    """
    Download protected media and return file bytes and metadata.
    """
    try:
        if isinstance(message.media, MessageMediaPhoto):
            print("📷 Downloading photo...")
            file = await client.download_media(message.media, file=bytes)
            filename = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}.jpg"
            mime_type = "image/jpeg"
            return file, filename, mime_type
        elif isinstance(message.media, MessageMediaDocument):
            print("📄 Downloading document...")
            filename, mime_type = analyze_document(message.media.document)
            file = await client.download_media(message.media, file=bytes)
            return file, filename, mime_type
        else:
            return None, None, None
    except Exception as e:
        print(f"❌ Error downloading media: {e}")
        return None, None, None

async def send_media_to_group(client, dest_chat_id, file, filename, mime_type, caption):
    """
    Send media file to the destination group with proper filename.
    """
    try:
        attributes = [DocumentAttributeFilename(filename)]
        
        await client.send_file(
            dest_chat_id,
            file,
            caption=caption or "",
            file_name=filename,
            mime_type=mime_type,
            force_document=True,
            attributes=attributes
        )
        return True
    except Exception as e:
        print(f"❌ Error sending file: {e}")
        return False

async def send_text_message(client, dest_chat_id, text):
    """
    Send text message to the destination group.
    """
    try:
        await client.send_message(dest_chat_id, text)
        return True
    except Exception as e:
        print(f"❌ Error sending text message: {e}")
        return False

async def process_messages_batch_ordered(client, source_entity, dest_chat_id, message_ids):
    """
    Process messages in batch but maintain order by downloading first, then sending sequentially.
    """
    print(f"📥 Fetching batch of {len(message_ids)} messages...")
    start_time = time.time()
    
    try:
        # Step 1: Fetch all messages in one go (fast)
        messages = await client.get_messages(source_entity, ids=message_ids)
        fetch_time = time.time() - start_time
        print(f"✅ Fetched {len(messages)} messages in {fetch_time:.2f}s")
        
        # Step 2: Download all media concurrently (preserve order)
        download_start = time.time()
        download_tasks = []
        message_data = []
        
        for i, message in enumerate(messages):
            if message is None:
                print(f"⚠️ Message {message_ids[i]} not found")
                message_data.append((None, None, None, None, message_ids[i]))
                continue
            
            if message.media:
                # Create download task but don't await yet
                task = download_protected_media(client, message)
                download_tasks.append((task, message.message, message_ids[i], i))
                message_data.append(None)  # Placeholder
            else:
                # Text message - no download needed
                message_data.append((None, None, None, message.message, message_ids[i]))
        
        # Download all media concurrently
        if download_tasks:
            print(f"📥 Downloading {len(download_tasks)} media files concurrently...")
            download_results = await asyncio.gather(
                *[task[0] for task in download_tasks], 
                return_exceptions=True
            )
            
            # Map results back to correct positions
            for j, (task, caption, msg_id, original_index) in enumerate(download_tasks):
                result = download_results[j]
                if isinstance(result, Exception):
                    print(f"❌ Download failed for message {msg_id}: {result}")
                    message_data[original_index] = (None, None, None, caption, msg_id)
                else:
                    file, filename, mime_type = result
                    message_data[original_index] = (file, filename, mime_type, caption, msg_id)
        
        download_time = time.time() - download_start
        print(f"✅ Downloaded all media in {download_time:.2f}s")
        
        # Step 3: Send messages in original order (sequential to maintain order)
        send_start = time.time()
        successful = 0
        
        for data in message_data:
            if data is None:
                continue
                
            file, filename, mime_type, caption, msg_id = data
            
            try:
                if file and filename and mime_type:
                    # Media message
                    success = await send_media_to_group(client, dest_chat_id, file, filename, mime_type, caption)
                    if success:
                        print(f"✅ Media message {msg_id} sent: {filename}")
                        successful += 1
                elif caption:
                    # Text message
                    success = await send_text_message(client, dest_chat_id, caption)
                    if success:
                        print(f"✅ Text message {msg_id} sent")
                        successful += 1
                else:
                    print(f"⚠️ Message {msg_id} has no content")
                    
                # Small delay between sends to avoid rate limiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"❌ Error sending message {msg_id}: {e}")
        
        send_time = time.time() - send_start
        total_time = time.time() - start_time
        
        print(f"✅ Batch completed: {successful}/{len(messages)} messages sent in {total_time:.2f}s")
        print(f"📊 Timing: Fetch={fetch_time:.2f}s, Download={download_time:.2f}s, Send={send_time:.2f}s")
        
        return successful, len(messages)
        
    except Exception as e:
        print(f"❌ Error processing batch: {e}")
        return 0, len(message_ids)

async def main():
    """
    Main function with ordered processing.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Forward protected messages from one Telegram group to another (maintaining order).")
    
    # Single message mode
    parser.add_argument("--source_group_id", type=int, help="Source group ID.")
    parser.add_argument("--message_id", type=int, help="Message ID in the source group.")
    parser.add_argument("--dest_group_id", type=int, help="Destination group ID.")
    
    # Bulk mode using URLs
    parser.add_argument("--from_url", type=str, help="Starting message URL")
    parser.add_argument("--to_url", type=str, help="Ending message URL")
    parser.add_argument("--dest_chat_id", type=int, help="Destination chat ID for bulk forwarding")
    parser.add_argument("--batch_size", type=int, default=10, help="Number of messages to process in each batch (default: 10)")
    
    args = parser.parse_args()
    
    check_api_credentials()
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    if not await login_with_retry(client):
        print("❌ Login failed.")
        return

    try:
        # Bulk forwarding mode
        if args.from_url and args.to_url and args.dest_chat_id:
            print("📋 Ordered bulk forwarding mode activated...")
            start_time = time.time()
            
            # Parse URLs
            from_channel_id, from_message_id, from_type = parse_telegram_url(args.from_url)
            to_channel_id, to_message_id, to_type = parse_telegram_url(args.to_url)
            
            if from_channel_id != to_channel_id:
                print("❌ Error: Both URLs must be from the same channel.")
                return
                
            # Get source entity
            try:
                print(f"🔍 Resolving source entity: {from_channel_id}")
                source_entity = await get_entity_safe(client, from_channel_id)
                print(f"✅ Connected to source channel: {getattr(source_entity, 'title', 'Unknown')}")
            except Exception as e:
                print(f"❌ Source channel resolution failed: {e}")
                return
            
            # Prepare message ID ranges
            total_messages = to_message_id - from_message_id + 1
            message_ids = list(range(from_message_id, to_message_id + 1))
            
            print(f"📋 Processing {total_messages} messages in ordered batches of {args.batch_size}...")
            
            total_successful = 0
            total_processed = 0
            
            # Process in batches (maintaining order)
            for i in range(0, len(message_ids), args.batch_size):
                batch = message_ids[i:i + args.batch_size]
                batch_num = (i // args.batch_size) + 1
                total_batches = (len(message_ids) + args.batch_size - 1) // args.batch_size
                
                print(f"\n🔄 Processing batch {batch_num}/{total_batches} (messages {batch[0]}-{batch[-1]})...")
                
                successful, processed = await process_messages_batch_ordered(client, source_entity, args.dest_chat_id, batch)
                total_successful += successful
                total_processed += processed
                
                # Small delay between batches
                if i + args.batch_size < len(message_ids):
                    await asyncio.sleep(0.5)
            
            total_time = time.time() - start_time
            avg_time_per_message = total_time / total_processed if total_processed > 0 else 0
            
            print(f"\n🎉 Ordered bulk forwarding completed!")
            print(f"📊 Results: {total_successful}/{total_processed} messages forwarded successfully")
            print(f"⏱️ Total time: {total_time:.2f}s")
            print(f"📈 Average time per message: {avg_time_per_message:.2f}s")
        
        # Single message mode
        elif args.source_group_id and args.message_id and args.dest_group_id:
            print("🔄 Single message forwarding mode...")
            
            try:
                source_entity = await get_entity_safe(client, args.source_group_id)
                await process_messages_batch_ordered(client, source_entity, args.dest_group_id, [args.message_id])
                print("🎉 Message forwarded successfully!")
            except Exception as e:
                print(f"❌ Error: {e}")
        
        else:
            print("❌ Invalid arguments. Use either:")
            print("   Single message: --source_group_id --message_id --dest_group_id")
            print("   Bulk forwarding: --from_url --to_url --dest_chat_id [--batch_size N]")
            
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())