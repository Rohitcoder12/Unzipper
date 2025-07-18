# bot.py
import logging
import os
import io
import zipfile
import py7zr
import shutil
from telethon.sync import TelegramClient, events
from telethon.sessions import StringSession

# --- Configuration from Heroku Config Vars ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
# IMPORTANT: The BOT_TOKEN is NOT used here. The String Session authenticates you.
SESSION_STRING = os.environ.get("STRING_SESSION")

TEMP_DIR = "temp_downloads" # Used for extraction if in-memory fails

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Initialize the Client with the String Session ---
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond(
        "Hello! I am the advanced Unzipper Bot.\n\n"
        "Send me a ZIP or 7z file. I will process it in memory. "
        "This works for files > 20 MB, but is limited by Heroku's RAM (~512MB)."
    )

@client.on(events.NewMessage(func=lambda e: e.document is not None))
async def document_handler(event):
    doc = event.document
    file_name = doc.attributes[0].file_name
    
    is_zip = doc.mime_type == "application/zip" or file_name.lower().endswith('.zip')
    is_7z = doc.mime_type == "application/x-7z-compressed" or file_name.lower().endswith('.7z')

    if not (is_zip or is_7z):
        return

    status_message = await event.respond(f"Downloading `{file_name}` into memory...")
    
    try:
        # 1. Download the file into an in-memory bytes buffer
        file_buffer = io.BytesIO(await event.download_media(file=bytes))
        await client.edit_message(status_message, "Download complete. Extracting from memory...")

        # 2. Extract from the in-memory buffer
        archive_name = "archive" # Placeholder
        if is_zip:
            archive = zipfile.ZipFile(file_buffer)
            file_list = archive.infolist()
        elif is_7z:
            archive = py7zr.SevenZipFile(file_buffer, mode='r')
            file_list = archive.list()
        
        await client.edit_message(status_message, f"Found {len(file_list)} files. Starting upload...")
        
        file_count = 0
        # 3. Iterate and upload each file
        for item in file_list:
            if not (is_zip and item.is_dir()): # Skip directories for zipfile
                # For zipfile, item is an info object. For py7zr, it has a 'filename' attribute.
                inner_filename = item.filename if is_zip else item.filename

                # Read the inner file's content into another bytes buffer
                if is_zip:
                    inner_file_bytes = archive.read(inner_filename)
                elif is_7z:
                    # py7zr needs a slightly different way to get the file data
                    all_files_dict = archive.readall()
                    inner_file_bytes = all_files_dict[inner_filename].read()

                # Upload the bytes
                await client.send_file(
                    event.chat_id,
                    file=inner_file_bytes,
                    attributes=[types.DocumentAttributeFilename(file_name=inner_filename)]
                )
                file_count += 1
        
        await client.edit_message(status_message, f"Upload complete! Sent {file_count} file(s).")

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        await client.edit_message(status_message, f"An error occurred: {e}\n\nThis might be because the file is too large for Heroku's RAM.")
    finally:
        # No cleanup needed as we didn't use the disk
        pass


print("Bot is starting...")
client.start()
client.run_until_disconnected()