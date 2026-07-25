"""Tous les textes du bot, en francais, avec emojis et mise en forme HTML."""

START = (
    "🎉 <b>Bienvenue {name} !</b> 🎀\n\n"
    "Je suis ton assistant <b>stickers</b> 📦\n"
    "Avec moi tu peux :\n\n"
    "✏️ <b>Créer</b> un pack (tu choisis le nom <i>et</i> le lien)\n"
    "🖼 Ajouter des <b>photos</b>, <b>vidéos</b>, <b>GIF</b> ou <b>stickers</b>\n"
    "📥 <b>Importer</b> un pack entier d'un seul coup\n"
    "🟢 <b>Exporter</b> tes stickers vers <b>WhatsApp</b>\n"
    "🏆 Grimper dans le <b>classement</b>\n\n"
    "👇 Utilise les boutons ci-dessous pour commencer."
)

HELP = (
    "❓ <b>Aide</b>\n\n"
    "1️⃣ Appuie sur <b>➕ Nouveau pack</b>\n"
    "2️⃣ Envoie le <b>nom</b> du pack (le titre affiché)\n"
    "3️⃣ Envoie le <b>lien</b> du pack (ex : <code>mon_pack</code>)\n"
    "4️⃣ Envoie tout ce que tu veux : 🖼 photo, 🎬 vidéo, 🎞 GIF, 🧩 sticker\n\n"
    "🤖 Pas besoin de choisir <i>statique</i> ou <i>vidéo</i> : je détecte tout seul.\n"
    "🚫 Un même sticker ne peut pas être ajouté deux fois dans un pack.\n"
    "📦 Envoie un sticker d'un pack existant → je peux importer <b>tout le pack</b>.\n\n"
    "<b>Commandes</b>\n"
    "/start — menu principal\n"
    "/new — créer un pack\n"
    "/mypacks — mes packs\n"
    "/top — classement\n"
    "/cancel — annuler l'opération en cours"
)

ASK_TITLE = (
    "✏️ <b>Nom du pack</b>\n\n"
    "Envoie-moi le titre que tu veux afficher (max 64 caractères).\n"
    "Exemple : <code>Dazai Osamu</code>"
)

ASK_LINK = (
    "🔗 <b>Lien du pack</b>\n\n"
    "Envoie maintenant le lien souhaité (lettres, chiffres et <code>_</code> uniquement).\n"
    "Exemple : <code>dazai_osamu</code>\n\n"
    "Le lien final sera : <code>t.me/addstickers/ton_lien_by_{bot}</code>"
)

BAD_LINK = (
    "⚠️ Lien invalide.\n"
    "Il doit commencer par une lettre et ne contenir que des lettres, chiffres et <code>_</code> (max 40)."
)

LINK_TAKEN = "🚫 Ce lien est déjà utilisé. Choisis-en un autre 🔁"

PACK_READY = (
    "✅ <b>Pack prêt !</b>\n\n"
    "📦 <b>{title}</b>\n"
    "🔗 <code>{link}</code>\n\n"
    "📨 Envoie-moi maintenant tes <b>photos</b> 🖼, <b>vidéos</b> 🎬, <b>GIF</b> 🎞 ou <b>stickers</b> 🧩.\n"
    "Quand tu as fini, appuie sur <b>✅ Terminer</b>."
)

ADDED = "✅ Ajouté ! 🔢 <b>{count}</b> sticker(s) dans <b>{title}</b>\n🔗 {link}"
DUPLICATE = "♻️ Ce sticker est <b>déjà</b> dans le pack — je ne l'ajoute pas deux fois."
PACK_FULL = "⚠️ Pack plein ({max} stickers max). Crée un nouveau pack ✏️"
NO_ACTIVE_PACK = (
    "📦 Aucun pack en cours.\n"
    "Appuie sur <b>➕ Nouveau pack</b> ou <b>📦 Mes packs</b> pour en sélectionner un."
)
FINISHED = "🎉 <b>Terminé !</b>\n\n📦 <b>{title}</b>\n🔢 {count} sticker(s)\n🔗 {link}"
WORKING = "⏳ Téléchargement en cours, patiente un moment..."
IMPORT_ASK = (
    "📦 <b>{title}</b>\n"
    "🔢 <b>{count}</b> stickers dans ce pack\n\n"
    "Que veux-tu faire ?"
)
IMPORT_DONE = (
    "✅ <b>Importation terminée</b>\n\n"
    "➕ Ajoutés : <b>{added}</b>\n"
    "♻️ Doublons ignorés : <b>{dupes}</b>\n"
    "⚠️ Échecs : <b>{failed}</b>\n\n"
    "🔗 {link}"
)
CANCELLED = "🚫 Opération annulée."
ERROR = "⚠️ Une erreur est survenue : <code>{error}</code>"
UNSUPPORTED = "🤔 Je ne sais pas quoi faire avec ça. Envoie une photo, une vidéo, un GIF ou un sticker."
BANNED = "🚫 Tu es banni de ce bot."

WA_START = "⏳ Conversion vers WhatsApp en cours, patiente un moment..."
WA_SPLIT = "⚠️ Pack trop grand — divisé en <b>{files} fichiers</b> max {per} stickers."
WA_DONE = "🟢 <b>Prêt pour WhatsApp !</b>\nOuvre les fichiers avec l'application <i>Sticker Maker</i>."

LEADERBOARD_HEADER = "🏆 <b>Classement des créateurs</b> 🎉\n"
LEADERBOARD_ROW = "{medal} <b>{name}</b>\n     📦 {packs} packs • 🔢 {stickers} stickers"
LEADERBOARD_ME = "\n\n👤 Toi : <b>#{rank}</b> — 🔢 {stickers} stickers"
LEADERBOARD_EMPTY = "🏆 Le classement est vide pour l'instant. Sois le premier ! ✏️"

ADMIN_PANEL = (
    "🛡 <b>Panneau administrateur</b>\n\n"
    "👥 Utilisateurs : <b>{users}</b> (🚫 {banned} bannis)\n"
    "📦 Packs : <b>{packs}</b>\n"
    "🔢 Stickers : <b>{stickers}</b>\n\n"
    "<b>Commandes admin</b>\n"
    "/stats — statistiques\n"
    "/broadcast &lt;message&gt; — message à tous\n"
    "/ban &lt;id&gt; — bannir\n"
    "/unban &lt;id&gt; — débannir\n"
    "/top 20 — classement étendu"
)
NOT_ADMIN = "🚫 Réservé à l'administrateur du bot."
BROADCAST_DONE = "📣 Diffusion terminée : ✅ {ok} • ⚠️ {failed}"
