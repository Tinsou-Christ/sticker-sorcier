"""Bot Telegram de création de stickers — 100% en français."""

import asyncio
import logging
import re

from telegram import InputSticker, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import converter
import db
import keyboards as kb
import strings as S
import wastickers

logger = logging.getLogger(__name__)

LINK_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{2,39}$')

# etats de conversation (stockes dans user_data['step'])
STEP_TITLE = 'title'
STEP_LINK = 'link'


# --------------------------------------------------------------------------
# utilitaires
# --------------------------------------------------------------------------

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMINS


def pack_link(name: str) -> str:
    return f'https://t.me/addstickers/{name}'


async def reply(update: Update, text: str, **kwargs):
    return await update.effective_message.reply_html(text, **kwargs)


def extract_media(message):
    """renvoie (kind, file_id, file_unique_id, suffix, emoji, set_name) ou None.

    kind ∈ static | video | animated (format Telegram du sticker a creer)
    """
    if message.sticker:
        st = message.sticker
        if st.is_animated:
            kind, suffix = 'animated', '.tgs'
        elif st.is_video:
            kind, suffix = 'video', '.webm'
        else:
            kind, suffix = 'static', '.webp'
        return kind, st.file_id, st.file_unique_id, suffix, st.emoji or '🙂', st.set_name

    if message.photo:
        ph = message.photo[-1]
        return 'photo', ph.file_id, ph.file_unique_id, '.jpg', '🙂', None

    if message.animation:
        an = message.animation
        return 'anim', an.file_id, an.file_unique_id, '.mp4', '🙂', None

    if message.video:
        vi = message.video
        return 'anim', vi.file_id, vi.file_unique_id, '.mp4', '🙂', None

    if message.document:
        doc = message.document
        mime = doc.mime_type or ''
        if mime.startswith('image/'):
            return 'photo', doc.file_id, doc.file_unique_id, '.png', '🙂', None
        if mime.startswith('video/'):
            return 'anim', doc.file_id, doc.file_unique_id, '.mp4', '🙂', None

    return None


async def build_input_sticker(context, kind, file_id, suffix, emoji) -> InputSticker:
    """prepare un InputSticker : les stickers existants passent par leur file_id,
    les photos/videos sont converties au bon format"""
    if kind in ('static', 'video', 'animated'):
        return InputSticker(sticker=file_id, emoji_list=[emoji], format=kind)

    tg_file = await context.bot.get_file(file_id)
    raw = bytes(await tg_file.download_as_bytearray())

    if kind == 'photo':
        data = await asyncio.to_thread(converter.image_to_webp, raw)
        return InputSticker(sticker=data, emoji_list=[emoji], format='static')

    data = await asyncio.to_thread(converter.video_to_webm, raw, suffix)
    return InputSticker(sticker=data, emoji_list=[emoji], format='video')


async def push_sticker(context, active, input_sticker, user_id) -> None:
    """cree le pack s'il n'existe pas encore, sinon ajoute le sticker"""
    if not active['created']:
        await context.bot.create_new_sticker_set(
            user_id=user_id,
            name=active['name'],
            title=active['title'],
            stickers=[input_sticker],
        )
        active['created'] = True
        active['id'] = db.add_pack(user_id, active['name'], active['title'])
    else:
        await context.bot.add_sticker_to_set(
            user_id=user_id,
            name=active['name'],
            sticker=input_sticker,
        )


# --------------------------------------------------------------------------
# commandes de base
# --------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.save_user(user)
    if db.is_banned(user.id):
        return await reply(update, S.BANNED, reply_markup=kb.remove())

    context.user_data.clear()
    await reply(
        update,
        S.START.format(name=user.first_name or 'toi'),
        reply_markup=kb.main_menu(is_admin(user.id)),
    )
    await update.effective_message.reply_html(
        '🔗 <b>Rejoins-nous :</b>', reply_markup=kb.start_links()
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update, S.HELP, reply_markup=kb.main_menu(is_admin(update.effective_user.id)))


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await reply(update, S.CANCELLED, reply_markup=kb.main_menu(is_admin(update.effective_user.id)))


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.save_user(update.effective_user)
    context.user_data.clear()
    context.user_data['step'] = STEP_TITLE
    await reply(update, S.ASK_TITLE, reply_markup=kb.cancel_menu())


async def cmd_mypacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    packs = db.user_packs(update.effective_user.id)
    if not packs:
        return await reply(update, S.NO_ACTIVE_PACK, reply_markup=kb.main_menu(is_admin(update.effective_user.id)))

    await reply(update, f'📦 <b>Tes packs</b> — {len(packs)} au total')
    for row in packs[:20]:
        text = (
            f'📦 <b>{row["title"]}</b>\n'
            f'🔢 {row["count"]} sticker(s)\n'
            f'🔗 <code>{pack_link(row["name"])}</code>'
        )
        await update.effective_message.reply_html(text, reply_markup=kb.pack_actions(row['name']))


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        limit = int(context.args[0]) if context.args else 10
    except (ValueError, IndexError):
        limit = 10
    limit = max(3, min(limit, 50))

    rows = db.leaderboard(limit)
    if not rows:
        return await reply(update, S.LEADERBOARD_EMPTY)

    medals = ['🥇', '🥈', '🥉']
    lines = [S.LEADERBOARD_HEADER]
    for i, row in enumerate(rows):
        medal = medals[i] if i < 3 else f'{i + 1}.'
        name = row['first_name'] or (f'@{row["username"]}' if row['username'] else 'Anonyme')
        lines.append(S.LEADERBOARD_ROW.format(medal=medal, name=name, packs=row['packs'], stickers=row['stickers']))

    text = '\n'.join(lines)
    rank, me = db.user_rank(update.effective_user.id)
    if rank:
        text += S.LEADERBOARD_ME.format(rank=rank, stickers=me['stickers'])

    await reply(update, text, reply_markup=kb.main_menu(is_admin(update.effective_user.id)))


# --------------------------------------------------------------------------
# creation de pack (texte)
# --------------------------------------------------------------------------

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.save_user(user)
    if db.is_banned(user.id):
        return await reply(update, S.BANNED, reply_markup=kb.remove())

    text = (update.effective_message.text or '').strip()

    if text == kb.BTN_NEW:
        return await cmd_new(update, context)
    if text == kb.BTN_MY_PACKS:
        return await cmd_mypacks(update, context)
    if text == kb.BTN_TOP:
        return await cmd_top(update, context)
    if text == kb.BTN_HELP:
        return await cmd_help(update, context)
    if text == kb.BTN_CANCEL:
        return await cmd_cancel(update, context)
    if text == kb.BTN_ADMIN:
        return await cmd_admin(update, context)
    if text == kb.BTN_DONE:
        return await finish_pack(update, context)
    if text == kb.BTN_WA:
        active = context.user_data.get('active')
        if not active:
            return await reply(update, S.NO_ACTIVE_PACK)
        return await export_whatsapp(update, context, active['name'])

    step = context.user_data.get('step')

    if step == STEP_TITLE:
        title = text[:64]
        context.user_data['title'] = title
        context.user_data['step'] = STEP_LINK
        return await reply(
            update,
            S.ASK_LINK.format(bot=context.bot.username),
            reply_markup=kb.cancel_menu(),
        )

    if step == STEP_LINK:
        link = text.lstrip('@').strip()
        if not LINK_RE.match(link):
            return await reply(update, S.BAD_LINK)

        name = f'{link}_by_{context.bot.username}'
        if db.get_pack_by_name(name):
            return await reply(update, S.LINK_TAKEN)
        try:
            await context.bot.get_sticker_set(name)
            return await reply(update, S.LINK_TAKEN)
        except TelegramError:
            pass

        context.user_data['step'] = None
        context.user_data['active'] = {
            'name': name,
            'title': context.user_data.get('title', 'Mon pack'),
            'created': False,
            'id': None,
        }
        return await reply(
            update,
            S.PACK_READY.format(title=context.user_data['active']['title'], link=pack_link(name)),
            reply_markup=kb.pack_menu(),
        )

    await reply(update, S.NO_ACTIVE_PACK, reply_markup=kb.main_menu(is_admin(user.id)))


async def finish_pack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active = context.user_data.get('active')
    if not active or not active.get('created'):
        return await reply(update, S.NO_ACTIVE_PACK, reply_markup=kb.main_menu(is_admin(update.effective_user.id)))

    count = db.pack_count(active['id'])
    context.user_data.pop('active', None)
    await reply(
        update,
        S.FINISHED.format(title=active['title'], count=count, link=pack_link(active['name'])),
        reply_markup=kb.main_menu(is_admin(update.effective_user.id)),
    )


# --------------------------------------------------------------------------
# medias
# --------------------------------------------------------------------------

async def on_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.save_user(user)
    if db.is_banned(user.id):
        return await reply(update, S.BANNED, reply_markup=kb.remove())

    media = extract_media(update.effective_message)
    if not media:
        return await reply(update, S.UNSUPPORTED)

    active = context.user_data.get('active')
    if not active:
        return await reply(update, S.NO_ACTIVE_PACK, reply_markup=kb.main_menu(is_admin(user.id)))

    kind, file_id, unique_id, suffix, emoji, set_name = media

    # sticker appartenant a un pack existant -> on propose d'importer tout le pack
    if set_name and set_name != active['name']:
        try:
            source = await context.bot.get_sticker_set(set_name)
        except TelegramError:
            source = None
        if source:
            context.user_data['pending'] = media
            return await reply(
                update,
                S.IMPORT_ASK.format(title=source.title, count=len(source.stickers)),
                reply_markup=kb.import_choice(set_name),
            )

    await add_one(update, context, media)


async def add_one(update: Update, context: ContextTypes.DEFAULT_TYPE, media):
    user = update.effective_user
    active = context.user_data['active']
    kind, file_id, unique_id, suffix, emoji, _ = media

    if active['id'] and db.pack_count(active['id']) >= config.MAX_STICKERS_PER_PACK:
        return await reply(update, S.PACK_FULL.format(max=config.MAX_STICKERS_PER_PACK))

    if active['id'] and db.has_sticker(active['id'], unique_id):
        return await reply(update, S.DUPLICATE)

    waiting = await reply(update, S.WORKING)
    try:
        input_sticker = await build_input_sticker(context, kind, file_id, suffix, emoji)
        await push_sticker(context, active, input_sticker, user.id)
        db.add_sticker(active['id'], unique_id)
    except (BadRequest, TelegramError, RuntimeError, OSError) as exc:
        logger.exception('ajout impossible')
        return await waiting.edit_text(S.ERROR.format(error=str(exc)[:200]), parse_mode=ParseMode.HTML)

    await waiting.edit_text(
        S.ADDED.format(count=db.pack_count(active['id']), title=active['title'], link=pack_link(active['name'])),
        parse_mode=ParseMode.HTML,
    )


async def import_full_pack(update: Update, context: ContextTypes.DEFAULT_TYPE, set_name: str):
    query = update.callback_query
    user = update.effective_user
    active = context.user_data.get('active')
    if not active:
        return await query.edit_message_text(S.NO_ACTIVE_PACK, parse_mode=ParseMode.HTML)

    try:
        source = await context.bot.get_sticker_set(set_name)
    except TelegramError as exc:
        return await query.edit_message_text(S.ERROR.format(error=str(exc)[:200]), parse_mode=ParseMode.HTML)

    await query.edit_message_text(S.WORKING, parse_mode=ParseMode.HTML)

    added = dupes = failed = 0
    for st in source.stickers:
        if active['id'] and db.pack_count(active['id']) >= config.MAX_STICKERS_PER_PACK:
            break
        if active['id'] and db.has_sticker(active['id'], st.file_unique_id):
            dupes += 1
            continue

        if st.is_animated:
            kind = 'animated'
        elif st.is_video:
            kind = 'video'
        else:
            kind = 'static'

        try:
            input_sticker = InputSticker(
                sticker=st.file_id, emoji_list=[st.emoji or '🙂'], format=kind
            )
            await push_sticker(context, active, input_sticker, user.id)
            db.add_sticker(active['id'], st.file_unique_id)
            added += 1
        except TelegramError as exc:
            logger.warning('import sticker echoue: %s', exc)
            failed += 1
        await asyncio.sleep(0.6)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=S.IMPORT_DONE.format(added=added, dupes=dupes, failed=failed, link=pack_link(active['name'])),
        parse_mode=ParseMode.HTML,
        reply_markup=kb.pack_menu(),
    )


# --------------------------------------------------------------------------
# WhatsApp
# --------------------------------------------------------------------------

async def export_whatsapp(update: Update, context: ContextTypes.DEFAULT_TYPE, set_name: str):
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id, S.WA_START, parse_mode=ParseMode.HTML)

    try:
        source = await context.bot.get_sticker_set(set_name)
    except TelegramError as exc:
        return await context.bot.send_message(
            chat_id, S.ERROR.format(error=str(exc)[:200]), parse_mode=ParseMode.HTML
        )

    webps = []
    for st in source.stickers[:config.MAX_STICKERS_PER_PACK]:
        if st.is_animated:
            continue  # les stickers .tgs ne sont pas supportes par WhatsApp
        suffix = '.webm' if st.is_video else '.webp'
        try:
            tg_file = await context.bot.get_file(st.file_id)
            raw = bytes(await tg_file.download_as_bytearray())
            webps.append(await asyncio.to_thread(converter.to_wa_webp, raw, suffix))
        except Exception as exc:  # noqa: BLE001
            logger.warning('conversion whatsapp echouee: %s', exc)

    if not webps:
        return await context.bot.send_message(
            chat_id, S.ERROR.format(error='aucun sticker convertible'), parse_mode=ParseMode.HTML
        )

    total_files = wastickers.files_count_for(len(webps), config.WA_STICKERS_PER_FILE)
    if total_files > 1:
        await context.bot.send_message(
            chat_id,
            S.WA_SPLIT.format(files=total_files, per=config.WA_STICKERS_PER_FILE),
            parse_mode=ParseMode.HTML,
        )

    tray = await asyncio.to_thread(wastickers.build_tray_icon_png, webps[0])
    files = await asyncio.to_thread(
        wastickers.build_wastickers_files,
        source.title,
        f'@{context.bot.username}',
        webps,
        tray,
        config.WA_STICKERS_PER_FILE,
    )

    for filename, buf in files:
        await context.bot.send_document(chat_id, document=buf, filename=filename)

    await context.bot.send_message(chat_id, S.WA_DONE, parse_mode=ParseMode.HTML)


# --------------------------------------------------------------------------
# callbacks
# --------------------------------------------------------------------------

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ''

    if data.startswith('imp:'):
        return await import_full_pack(update, context, data[4:])

    if data == 'imp_one':
        media = context.user_data.pop('pending', None)
        if not media:
            return await query.edit_message_text(S.CANCELLED, parse_mode=ParseMode.HTML)
        await query.edit_message_text('🧩 Ajout du sticker...', parse_mode=ParseMode.HTML)
        return await add_one(update, context, media)

    if data == 'imp_no':
        context.user_data.pop('pending', None)
        return await query.edit_message_text(S.CANCELLED, parse_mode=ParseMode.HTML)

    if data.startswith('use:'):
        name = data[4:]
        row = db.get_pack(update.effective_user.id, name)
        if not row:
            return await query.edit_message_text(S.NO_ACTIVE_PACK, parse_mode=ParseMode.HTML)
        context.user_data['active'] = {
            'name': row['name'], 'title': row['title'], 'created': True, 'id': row['id']
        }
        await query.edit_message_text(
            S.PACK_READY.format(title=row['title'], link=pack_link(row['name'])),
            parse_mode=ParseMode.HTML,
        )
        return await context.bot.send_message(
            update.effective_chat.id, '📨 En attente de tes médias...', reply_markup=kb.pack_menu()
        )

    if data.startswith('wa:'):
        return await export_whatsapp(update, context, data[3:])

    if data.startswith('del:'):
        name = data[4:]
        row = db.get_pack(update.effective_user.id, name)
        if row:
            db.delete_pack(row['id'])
        return await query.edit_message_text('🗑 Pack oublié (il reste sur Telegram).', parse_mode=ParseMode.HTML)


# --------------------------------------------------------------------------
# admin
# --------------------------------------------------------------------------

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await reply(update, S.NOT_ADMIN)
    stats = db.global_stats()
    await reply(update, S.ADMIN_PANEL.format(**stats), reply_markup=kb.main_menu(True))


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_admin(update, context)


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await reply(update, S.NOT_ADMIN)
    if not context.args:
        return await reply(update, '📣 Utilisation : <code>/broadcast ton message</code>')

    message = update.effective_message.text.split(' ', 1)[1]
    ok = failed = 0
    for user_id in db.all_user_ids():
        try:
            await context.bot.send_message(user_id, message, parse_mode=ParseMode.HTML)
            ok += 1
        except TelegramError:
            failed += 1
        await asyncio.sleep(0.05)
    await reply(update, S.BROADCAST_DONE.format(ok=ok, failed=failed))


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await reply(update, S.NOT_ADMIN)
    if not context.args or not context.args[0].isdigit():
        return await reply(update, '🚫 Utilisation : <code>/ban 123456789</code>')
    db.set_banned(int(context.args[0]), True)
    await reply(update, f'🚫 Utilisateur <code>{context.args[0]}</code> banni.')


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await reply(update, S.NOT_ADMIN)
    if not context.args or not context.args[0].isdigit():
        return await reply(update, '✅ Utilisation : <code>/unban 123456789</code>')
    db.set_banned(int(context.args[0]), False)
    await reply(update, f'✅ Utilisateur <code>{context.args[0]}</code> débanni.')


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception('erreur non gerée', exc_info=context.error)


# --------------------------------------------------------------------------
# app
# --------------------------------------------------------------------------

async def post_init(app: Application):
    from telegram import BotCommand

    await app.bot.set_my_commands([
        BotCommand('start', '🏠 Menu principal'),
        BotCommand('new', '✏️ Créer un pack'),
        BotCommand('mypacks', '📦 Mes packs'),
        BotCommand('top', '🏆 Classement'),
        BotCommand('help', '❓ Aide'),
        BotCommand('cancel', '🚫 Annuler'),
    ])


def build_application() -> Application:
    db.init()

    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('help', cmd_help))
    app.add_handler(CommandHandler('new', cmd_new))
    app.add_handler(CommandHandler('mypacks', cmd_mypacks))
    app.add_handler(CommandHandler('top', cmd_top))
    app.add_handler(CommandHandler('cancel', cmd_cancel))
    app.add_handler(CommandHandler('admin', cmd_admin))
    app.add_handler(CommandHandler('stats', cmd_stats))
    app.add_handler(CommandHandler('broadcast', cmd_broadcast))
    app.add_handler(CommandHandler('ban', cmd_ban))
    app.add_handler(CommandHandler('unban', cmd_unban))

    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Sticker.ALL | filters.Document.ALL,
        on_media,
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)

    return app
