# bot.py

import logging
import os
import zipfile
import shutil
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Configuration ---
# Get your token from @BotFather
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
# A temporary directory to store downloaded and extracted files
TEMP_DIR = "temp_downloads"

# Enable logging to see errors
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
        "Send me any ZIP file, and I will extract its contents and send them back to you."
    )

async def handle_zip_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming ZIP files."""
    chat_id = update.message.chat_id
    document = update.message.document

    # Check if the sent file is a ZIP file
    if document.mime_type != "application/zip":
        await update.message.reply_text("Please send a valid ZIP file.")
        return

    # Create a unique directory for this request to handle concurrent users
    request_path = os.path.join(TEMP_DIR, str(chat_id) + "_" + str(update.message.message_id))
    download_path = os.path.join(request_path, document.file_name)
    extract_path = os.path.join(request_path, "extracted")

    os.makedirs(extract_path, exist_ok=True)

    try:
        # 1. Inform the user
        processing_message = await update.message.reply_text("Processing your ZIP file...")

        # 2. Download the file
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(download_path)
        logger.info(f"File downloaded to {download_path}")

        # 3. Extract the ZIP file
        await context.bot.edit_message_text(text="Extracting files...", chat_id=chat_id, message_id=processing_message.message_id)
        with zipfile.ZipFile(download_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        logger.info(f"Files extracted to {extract_path}")

        # 4. Send the extracted files back
        await context.bot.edit_message_text(text="Uploading extracted files...", chat_id=chat_id, message_id=processing_message.message_id)
        
        file_count = 0
        for root, dirs, files in os.walk(extract_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                try:
                    # Determine file type and send accordingly
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        await context.bot.send_photo(chat_id=chat_id, photo=open(file_path, 'rb'))
                    elif filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                        await context.bot.send_video(chat_id=chat_id, video=open(file_path, 'rb'))
                    else:
                        await context.bot.send_document(chat_id=chat_id, document=open(file_path, 'rb'))
                    file_count += 1
                except Exception as e:
                    logger.error(f"Failed to send file {file_path}: {e}")
                    await update.message.reply_text(f"Could not send file: {filename}\nError: {e}")

        # 5. Final status update
        await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)
        await update.message.reply_text(f"Extraction complete! Sent {file_count} file(s).")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        await update.message.reply_text(f"An error occurred during processing: {e}")
    finally:
        # 6. Cleanup: Always remove the temp files
        cleanup(request_path)

# --- Main Bot Setup ---
def main():
    """Start the bot."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN environment variable not set!")
        return

    # Create the temporary directory if it doesn't exist
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
        
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.Document.ZIP, handle_zip_file))

    # Run the bot until you press Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
