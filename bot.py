# bot.py (Disk-based version for Heroku)

import logging
import os
import io
import zipfile
import py7zr
import shutil
from telethon.sync import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl import types

# --- Configuration from Heroku Config Vars ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("STRING_SESSION")

# A temporary directory on Heroku's ephemeral disk
TEMP_DIR = "temp_downloads"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Initialize the Client with the String Session ---
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# --- Helper function to clean up files ---
def cleanup(path):
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
            logger.info(f"Successfully cleaned up directory: {path}")
        except OSError as e:
            logger.error(f"Error during cleanup of {path}: {e.strerror}")

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    # Ignore messages from other bots
    if event.sender.bot:
        return

    await event.respond(
        "Hello! I am the advanced Unzipper Bot.\n\n"
        "Send me a ZIP or 7z file. I will use the server disk to process it. "
        "This is slower but handles larger files."
    )

@client.on(events.NewMessage(func=lambda e: e.document is not None))
async def document_handler(event):
    # Ignore files sent by other bots
    if event.sender.bot:
        return

    doc = event.document
    file_name = doc.attributes[0].file_name
    
    is_zip = doc.mime_type == "application/zip" or file_name.lower().endswith('.zip')
    is_7z = doc.mime_type == "application/x-7z-compressed" or file_name.lower().endswith('.7z')

    if not (is_zip or is_7z):
        return

    # Create a unique directory for this request on the disk
    request_path = os.path.join(TEMP_DIR, str(event.chat_id) + "_" + str(event.message.id))
    download_path = os.path.join(request_path, file_name)
    extract_path = os.path.join(request_path, "extracted")
    os.makedirs(extract_path, exist_ok=True)
    
    status_message = await event.respond(f"Downloading `{file_name}` to server disk...")

    try:
        # 1. Download the file TO DISK (not to memory)
        await client.download_media(
            message=event.message,
            file=download_path
        )
        await client.edit_message(status_message, "Download complete. Extracting files from disk...")

        # 2. Extract the archive from the file on disk
        if is_zip:
            with zipfile.ZipFile(download_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
        elif is_7z:
            with py7zr.SevenZipFile(download_path, mode='r') as z:
                z.extractall(path=extract_path)
        
        await client.edit_message(status_message, "Extraction complete. Now uploading...")
        
        # 3. Iterate and upload each file from the disk
        file_count = 0
        for root, dirs, files in os.walk(extract_path):
            for inner_filename in files:
                file_path = os.path.join(root, inner_filename)
                # We can use the caption parameter to set the filename for the user
                await client.send_file(event.chat_id, file=file_path, caption=inner_filename)
                file_count += 1
        
        await client.edit_message(status_message, f"Upload complete! Sent {file_count} file(s).")

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        await client.edit_message(status_message, f"An error occurred: {e}")
    finally:
        # 4. CRITICAL: Clean up the files from the disk to save space
        cleanup(request_path)

# --- Main Function to Run the Bot ---
def main():
    # Create the temp directory if it doesn't exist
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
        
    print("Bot is starting...")
    client.start()
    client.run_until_disconnected()

if __name__ == '__main__':
    main()