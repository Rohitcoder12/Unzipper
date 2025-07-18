# bot.py

import logging
import os
import zipfile
import py7zr  # <-- Import the new library
import shutil
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

# --- Configuration ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TEMP_DIR = "temp_downloads"
# Telegram's max file size for bot downloads is 20 MB
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB in bytes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def cleanup(path):
    """Deletes the specified directory and its contents."""
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
            logger.info(f"Successfully cleaned up directory: {path}")
        except OSError as e:
            logger.error(f"Error during cleanup of {path}: {e.strerror}")

# --- Bot Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the /start command is issued."""
    await update.message.reply_text(
        "Hello! I am the Unzipper Bot.\n\n"
        "Send me a ZIP or 7z file (under 20 MB), and I will extract its contents for you."
    )

async def handle_archive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming ZIP or 7Z files."""
    chat_id = update.message.chat_id
    document = update.message.document

    # --- NEW: Check file size before doing anything else ---
    if document.file_size > MAX_FILE_SIZE:
        await update.message.reply_text(
            f"Sorry, the file is too large ({document.file_size / 1024 / 1024:.2f} MB). "
            "I can only process files up to 20 MB."
        )
        return

    # Create a unique directory for this request
    request_path = os.path.join(TEMP_DIR, str(chat_id) + "_" + str(update.message.message_id))
    download_path = os.path.join(request_path, document.file_name)
    extract_path = os.path.join(request_path, "extracted")
    os.makedirs(extract_path, exist_ok=True)
    
    processing_message = None
    try:
        # 1. Inform the user
        processing_message = await update.message.reply_text("Processing your file...")

        # 2. Download the file
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(download_path)
        logger.info(f"File downloaded to {download_path}")

        # 3. Extract the archive based on its type
        await context.bot.edit_message_text(text="Extracting files...", chat_id=chat_id, message_id=processing_message.message_id)
        
        # --- NEW: Logic to handle both ZIP and 7z ---
        is_zip = document.mime_type == "application/zip" or document.file_name.lower().endswith('.zip')
        is_7z = document.mime_type == "application/x-7z-compressed" or document.file_name.lower().endswith('.7z')

        if is_zip:
            with zipfile.ZipFile(download_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
        elif is_7z:
            with py7zr.SevenZipFile(download_path, mode='r') as z:
                z.extractall(path=extract_path)
        else:
            # This case should ideally not be hit if filters are correct, but it's good practice
            await update.message.reply_text("Unsupported file format. Please send a .zip or .7z file.")
            cleanup(request_path)
            return

        logger.info(f"Files extracted to {extract_path}")

        # 4. Send the extracted files back
        await context.bot.edit_message_text(text="Uploading extracted files...", chat_id=chat_id, message_id=processing_message.message_id)
        
        file_count = 0
        for root, dirs, files in os.walk(extract_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                try:
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        await context.bot.send_photo(chat_id=chat_id, photo=open(file_path, 'rb'))
                    elif filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                        await context.bot.send_video(chat_id=chat_id, video=open(file_path, 'rb'))
                    else:
                        await context.bot.send_document(chat_id=chat_id, document=open(file_path, 'rb'))
                    file_count += 1
                except TelegramError as e:
                    logger.error(f"Failed to send file {file_path}: {e}")
                    # If a single file fails to upload (e.g., too large), inform the user and continue
                    await update.message.reply_text(f"Could not send file: {filename}\nError: {e.message}")

        # 5. Final status update
        await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)
        await update.message.reply_text(f"Extraction complete! Sent {file_count} file(s).")

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        # If a message was sent, edit it with the error. Otherwise, reply.
        error_text = f"An error occurred during processing: {e}"
        if processing_message:
            await context.bot.edit_message_text(text=error_text, chat_id=chat_id, message_id=processing_message.message_id)
        else:
            await update.message.reply_text(error_text)
    finally:
        # 6. Cleanup: Always remove the temp files
        cleanup(request_path)

# --- Main Bot Setup ---
def main():
    """Start the bot."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN environment variable not set!")
        return

    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
        
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # --- NEW: Updated filter to accept both zip and 7z mime types ---
    archive_filter = (filters.Document.ZIP | filters.Document.MimeType("application/x-7z-compressed"))
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(archive_filter, handle_archive))

    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()