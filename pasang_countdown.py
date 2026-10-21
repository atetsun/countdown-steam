"""
Siapkan channel countdown + webhook-nya (opsional, bisa juga buat webhook manual di Discord).
Hasil: channel "⏳・countdown" (hanya baca) dan file countdown_webhook.txt berisi URL webhook.

  python pasang_countdown.py

Setelah itu isi URL di countdown_webhook.txt ke GitHub Secrets dengan nama DISCORD_WEBHOOK_COUNTDOWN.
Jangan upload countdown_webhook.txt ke GitHub.
"""
import os

import discord

BASE = os.path.dirname(os.path.abspath(__file__))
TOKEN = open(os.path.join(BASE, "token.txt")).read().strip()
WEBHOOK_FILE = os.path.join(BASE, "countdown_webhook.txt")

NAMA_CHANNEL = "event"
LABEL_CHANNEL = "🍿・event"
KATEGORI = "🎉 EVENT"
TOPIK = "Countdown sale dan fest Steam. Diperbarui otomatis."
NAMA_WEBHOOK = "Steam Countdown"


def norm(teks):
    return teks.replace("️", "").lower()


client = discord.Client(intents=discord.Intents.default())


@client.event
async def on_ready():
    guild = client.guilds[0] if client.guilds else None
    if guild is None:
        print("Bot belum masuk ke server mana pun. Undang bot dulu.")
        await client.close()
        return

    kategori = next((c for c in guild.categories if norm(c.name) == norm(KATEGORI)), None)
    ch = next((c for c in guild.text_channels if c.name.split("・")[-1] == NAMA_CHANNEL), None)

    if ch is None:
        ow = {guild.default_role: discord.PermissionOverwrite(send_messages=False, add_reactions=True)}
        ch = await guild.create_text_channel(LABEL_CHANNEL, category=kategori, overwrites=ow, topic=TOPIK)
        print(f"Channel dibuat: {LABEL_CHANNEL}")
    else:
        print(f"Channel sudah ada: {ch.name}")

    webhook = next((w for w in await ch.webhooks() if w.name == NAMA_WEBHOOK and w.token), None)
    if webhook is None:
        webhook = await ch.create_webhook(name=NAMA_WEBHOOK)
        print("Webhook dibuat.")
    else:
        print("Webhook sudah ada, dipakai ulang.")

    with open(WEBHOOK_FILE, "w", encoding="utf-8") as f:
        f.write(webhook.url)
    print(f"URL webhook disimpan di: {WEBHOOK_FILE}")
    print("Jaga kerahasiaan file itu (siapa pun yang punya URL-nya bisa mengirim pesan ke channel).")
    await client.close()


client.run(TOKEN)
