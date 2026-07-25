from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

import config

BTN_NEW = '✏️ Nouveau pack'
BTN_MY_PACKS = '📦 Mes packs'
BTN_TOP = '🏆 Classement'
BTN_HELP = '❓ Aide'
BTN_DONE = '✅ Terminer'
BTN_CANCEL = '🚫 Annuler'
BTN_WA = '🟢 Vers WhatsApp'
BTN_ADMIN = '🛡 Admin'


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(BTN_NEW), KeyboardButton(BTN_MY_PACKS)],
        [KeyboardButton(BTN_TOP), KeyboardButton(BTN_HELP)],
    ]
    if is_admin:
        rows.append([KeyboardButton(BTN_ADMIN)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, input_field_placeholder='Choisis une option 👇')


def pack_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_DONE), KeyboardButton(BTN_WA)],
            [KeyboardButton(BTN_MY_PACKS), KeyboardButton(BTN_CANCEL)],
        ],
        resize_keyboard=True,
        input_field_placeholder='Envoie une photo, vidéo, GIF ou sticker 📨',
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_CANCEL)]],
        resize_keyboard=True,
        input_field_placeholder='En attente de ta réponse ✍️',
    )


def remove() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def start_links() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('👤 Contacter le créateur', url=config.CREATOR_URL)],
            [
                InlineKeyboardButton('📢 La chaîne', url=config.CHANNEL_URL),
                InlineKeyboardButton('💬 Le groupe', url=config.GROUP_URL),
            ],
        ]
    )


def import_choice(set_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('✅ Importer tout le pack', callback_data=f'imp:{set_name}')],
            [InlineKeyboardButton('🧩 Ce sticker seulement', callback_data='imp_one')],
            [InlineKeyboardButton('🚫 Annuler', callback_data='imp_no')],
        ]
    )


def pack_actions(pack_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('📨 Continuer ce pack', callback_data=f'use:{pack_name}')],
            [
                InlineKeyboardButton('🟢 WhatsApp', callback_data=f'wa:{pack_name}'),
                InlineKeyboardButton('🗑 Oublier', callback_data=f'del:{pack_name}'),
            ],
            [InlineKeyboardButton('🔗 Voir le pack', url=f'https://t.me/addstickers/{pack_name}')],
        ]
    )
