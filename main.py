import os
import yt_dlp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN, BOT_NAME, FORCE_JOIN_CHANNEL, OWNER_ID
from database import add_user
from helpers import check_size_okay, delete_message_safe

app = Client('moxi', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_sessions = {}

async def user_must_join(user_id: int) -> bool:
    if not FORCE_JOIN_CHANNEL:
        return True
    try:
        member = await app.get_chat_member(FORCE_JOIN_CHANNEL, user_id)
        return member.status not in ('kicked', 'left')
    except Exception:
        return False

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

Monish▪️🥷, [23-10-2025 09:09]
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
    ydl_opts = {'quiet': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(session['url'], download=False)
    except Exception as e:
        await callback.message.edit_text('Failed to fetch info: ' + str(e))
        return
    kb = []
    if mode == 'audio':
        kb = [[InlineKeyboardButton('128 kbps', callback_data='q_128'), InlineKeyboardButton('320 kbps', callback_data='q_320')]]
    else:
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
    if mode == 'video':
        qmap = {'360': 'bestvideo[height<=360]+bestaudio/best[height<=360]', '720': 'bestvideo[height<=720]+bestaudio/best[height<=720]', '1080': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'}
        ydl_opts = {'format': qmap.get(quality, 'best'), 'outtmpl': f'{uid}_%(title)s.%(ext)s'}
    else:
        abr = '128' if quality == '128' else '320'
        ydl_opts = {'format': 'bestaudio/best', 'outtmpl': f'{uid}_%(title)s.%(ext)s', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': abr}]}
    filename = None
    try:
        def progress_hook(d):
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                percent = (downloaded / total * 100) if total else 0
                asyncio.create_task(progress_msg.edit_text(f"⬇️ Downloading... {percent:.1f}%"))
        ydl_opts['progress_hooks'] = [progress_hook]
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        if not await check_size_okay(os.path.getsize(filename)):
            await progress_msg.edit_text('❌ File too large, aborted.')
            os.remove(filename)
            return
        if mode == 'video':
            sent_msg = await callback.message.reply_video(video=filename, caption=f"🎬 {info.get('title')}")
        else:
            mp3file = os.path.splitext(filename)[0]+'.mp3'
            sent_msg = await callback.message.reply_audio(audio=mp3file, caption=f"🎵 {info.get('title')}")
        await delete_message_safe(progress_msg)
        os.remove(filename)
        # auto-delete uploaded file after 30 minutes
        asyncio.create_task(asyncio.sleep(1800));
        await sent_msg.delete()
    except Exception as e:
        await progress_msg.edit_text('❌ Error: '+str(e))

app.run()


Done ✅ — this is the full, corrected repo with:
