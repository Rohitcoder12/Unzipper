# generate_session.py
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# --- Get these from my.telegram.org ---
API_ID = int(input("Please enter your API ID: "))
API_HASH = input("Please enter your API HASH: ")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    session_string = client.session.save()
    print("\n--- YOUR SESSION STRING ---")
    print(session_string)
    print("\nCOPY this string and save it. You will need it for the Heroku config.")