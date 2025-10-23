import os
import yt_dlp
import asyncio
import tempfile # Added for secure cookie file handling
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# Assuming these are defined in config.py and helpers.py
from config import API_ID, API_HASH, BOT_TOKEN, BOT_NAME, FORCE_JOIN_CHANNEL, OWNER_ID
from database import add_user
from helpers import check_size_okay, delete_message_safe

# --- COOKIE HANDLING SETUP ---

# This global variable will store the path to the temporary cookie file
GLOBAL_COOKIES_PATH = None

def setup_cookies_file():
    """Reads the cookie string from environment variable and writes to a temp file."""
    cookies_string = os.environ.get("YOUTUBE_COOKIES")
    if not cookies_string:
        print("WARNING: YOUTUBE_COOKIES env var is not set. Restricted videos may fail.")
        return None
    
    try:
        # Create a temporary file to store the cookie string. delete=False to keep it until cleanup.
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
        temp_file.write(cookies_string)
        temp_file.close()
        print(f"SUCCESS: Cookies loaded to temporary file: {temp_file.name}")
        return temp_file.name
    except Exception as e:
        print(f"ERROR: Failed to create temporary cookie file: {e}")
        return None

def cleanup_cookies_file(path):
    """Deletes the temporary cookie file."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
            print(f"CLEANUP: Removed temporary cookie file: {path}")
        except Exception as e:
            print(f"CLEANUP ERROR: Could not remove {path}: {e}")


# --- BOT INITIALIZATION ---

app = Client('moxi', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_sessions = {}

# --- HELPER FUNCTIONS ---

async def user_must_join(user_id: int) -> bool:
    if not FORCE_JOIN_CHANNEL:
        return True
    try:
        member = await app.get_chat_member(FORCE_JOIN_CHANNEL, user_id)
        return member.status not in ('kicked', 'left')
    except Exception:
        return False

# --- HANDLERS ---

@app.on_message(filters.command('start'))
async def start_cmd(client, message):
    await add_user(message.from_user.id, message.from_user.username)
    txt = f"👋 Welcome to {BOT_NAME}\nSend a YouTube link and choose audio/video."
    await message.reply_text(txt)

@app.on_message(filters.private & filters.regex(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/"))
async def on_link(client, message):
    if FORCE_JOIN_CHANNEL and not await user_must_join(message.from_user.id):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Join Channel", url=f"https://t.me/{FORCE_JOIN_CHANNEL.strip('@')}")],
            [InlineKeyboardButton("✅ I Joined, Continue", callback_data="check_join")]
        ])
        await message.reply_text(f"⛔ You must join {FORCE_JOIN_CHANNEL} to use this bot.", reply_markup=kb)
        return
    await add_user(message.from_user.id, message.from_user.username)
    url = message.text.strip()
    user_sessions[message.from_user.id] = {'url': url}
    kb = InlineKeyboardMarkup([[InlineKeyboardButton('🎵 Audio', callback_data='type_audio'), InlineKeyboardButton('🎥 Video', callback_data='type_video')]])
    await message.reply_text('Select type:', reply_markup=kb)

@app.on_callback_query(filters.regex('^check_join$'))
async def check_join_cb(client, callback):
    uid = callback.from_user.id
    if await user_must_join(uid):
        await callback.message.edit_text("🎉 You are now a member! Send your YouTube link again.")
    else:
        await callback.answer("You still need to join the channel.", show_alert=True)

@app.on_callback_query(filters.regex('^type_'))
async def choose_type(client, callback):
    uid = callback.from_user.id
    session = user_sessions.get(uid)
    if not session:
        await callback.answer('Session expired. Send the link again.', show_alert=True)
        return
    mode = callback.data.split('_', 1)[1]
    session['mode'] = mode
    await callback.message.edit_text('Fetching qualities, please wait...')
    
    # --- FIX 1: Add cookiefile to ydl_opts for information fetch ---
    ydl_opts = {'quiet': True, 'skip_download': True}
    if GLOBAL_COOKIES_PATH:
        ydl_opts['cookiefile'] = GLOBAL_COOKIES_PATH
    # -----------------------------------------------------------------

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(session['url'], download=False)
    except Exception as e:
        error_message = str(e)
        if "confirm you’re not a bot" in error_message or "Sign in" in error_message:
             error_message = "Video restricted! Ensure your YOUTUBE_COOKIES are valid."
        await callback.message.edit_text('❌ Failed to fetch info: ' + error_message)
        return
    
    kb = []
    if mode == 'audio':
        kb = [[InlineKeyboardButton('128 kbps', callback_data='q_128'), InlineKeyboardButton('320 kbps', callback_data='q_320')]]
    else:
        # Check available formats/qualities and filter if necessary (yt-dlp handles most of this)
        kb = [[InlineKeyboardButton('360p', callback_data='q_360'), InlineKeyboardButton('720p', callback_data='q_720')], [InlineKeyboardButton('1080p', callback_data='q_1080')]]
    await callback.message.edit_text('Choose quality:', reply_markup=InlineKeyboardMarkup(kb))

@app.on_callback_query(filters.regex('^q_'))
async def chosen_quality(client, callback):
    uid = callback.from_user.id
    session = user_sessions.get(uid)
    if not session:
        await callback.answer('Session expired. Send the link again.', show_alert=True)
        return
    quality = callback.data.split('_', 1)[1]
    mode = session.get('mode')
    url = session.get('url')
    progress_msg = await callback.message.edit_text('⬇️ Download starting...')

    # Set up download options
    if mode == 'video':
        qmap = {'360': 'bestvideo[height<=360]+bestaudio/best[height<=360]', '720': 'bestvideo[height<=720]+bestaudio/best[height<=720]', '1080': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'}
        ydl_opts = {'format': qmap.get(quality, 'best'), 'outtmpl': f'{uid}_%(title)s.%(ext)s'}
    else:
        abr = '128' if quality == '128' else '320'
        ydl_opts = {'format': 'bestaudio/best', 'outtmpl': f'{uid}_%(title)s.%(ext)s', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': abr}]}
    
    # --- FIX 2: Add cookiefile to ydl_opts for download ---
    if GLOBAL_COOKIES_PATH:
        ydl_opts['cookiefile'] = GLOBAL_COOKIES_PATH
    # ------------------------------------------------------
        
    filename = None
    try:
        # Progress hook needs a way to update the Telegram message asynchronously
        async def edit_message_progress(d):
             if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                percent = (downloaded / total * 100) if total else 0
                # Use progress_msg (from outer scope)
                try:
                    await progress_msg.edit_text(f"⬇️ Downloading... {percent:.1f}%")
                except Exception:
                    # Ignore exceptions during rapid progress updates
                    pass

        ydl_opts['progress_hooks'] = [edit_message_progress]
        ydl_opts['logger'] = yt_dlp.utils.StdLogger() # Added logger to catch errors more clearly

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # Check size and upload logic (rest of your original logic)
        if not await check_size_okay(os.path.getsize(filename)):
            await progress_msg.edit_text('❌ File too large, aborted.')
            if filename and os.path.exists(filename): os.remove(filename)
            return

        # Handle file extension for upload (yt-dlp output format might differ from expected)
        final_file_to_send = filename
        if mode == 'audio':
            # yt-dlp might keep the original extension until the end of post-processing
            # We assume the MP3 postprocessor renamed the file correctly
            # Check the final file output name from info if possible, or rely on original logic
            mp3file = os.path.splitext(filename)[0]+'.mp3'
            final_file_to_send = mp3file if os.path.exists(mp3file) else filename
            sent_msg = await callback.message.reply_audio(audio=final_file_to_send, caption=f"🎵 {info.get('title')}")
        else:
            sent_msg = await callback.message.reply_video(video=final_file_to_send, caption=f"🎬 {info.get('title')}")

        await delete_message_safe(progress_msg)
        
        # Cleanup the downloaded file immediately
        if os.path.exists(final_file_to_send):
            os.remove(final_file_to_send)
        if os.path.exists(filename) and filename != final_file_to_send:
            os.remove(filename)

        # The asyncio.sleep(1800) and delete is redundant if you clean up locally, 
        # but I will keep it to match your original logic for message deletion.
        asyncio.create_task(asyncio.sleep(1800));
        await sent_msg.delete()
        
    except Exception as e:
        error_message = str(e)
        if "confirm you’re not a bot" in error_message or "Sign in" in error_message:
             error_message = "Video restricted! Ensure your YOUTUBE_COOKIES are valid."
        await progress_msg.edit_text('❌ Download Error: ' + error_message)
        # Final cleanup in case the download failed mid-way and left files
        if filename and os.path.exists(filename):
            os.remove(filename)


# --- RUN APPLICATION WITH COOKIE SETUP/CLEANUP ---

# 1. Setup cookies before running the bot
GLOBAL_COOKIES_PATH = setup_cookies_file()

try:
    # 2. Run the bot
    app.run()
    
finally:
    # 3. Cleanup the temporary cookie file after the bot stops
    cleanup_cookies_file(GLOBAL_COOKIES_PATH)
