import os
import threading

from flask import Flask
import discord
from discord import app_commands

# -------------------------
# Webserver für Render
# -------------------------

web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Black Forest Genetics GrowBot ist online."

def run_webserver():
    port = int(os.getenv("PORT", "10000"))
    web_app.run(host="0.0.0.0", port=port)

# -------------------------
# Discord Bot
# -------------------------
class GrowBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True

        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"✅ GrowBot ist online als {self.user}")

        await self.change_presence(
            activity=discord.Game(
                name="Black Forest Genetics 🌱"
            )
        )
bot = GrowBot()

@bot.tree.command(
    name="hilfe",
    description="Zeigt die verfügbaren GrowBot-Befehle."
)
async def hilfe(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🌲 Black Forest Genetics GrowBot\n"
        "✅ Version 1.0 ist aktiv.\n"
        "🌱 Growlogs und Pflanzenprofile folgen als Nächstes."
    )
@bot.tree.command(
    name="status",
    description="Zeigt den Status des GrowBots."
)
async def status(interaction: discord.Interaction):
    await interaction.response.send_message(
        "✅ Black Forest Genetics GrowBot läuft erfolgreich."
    )
@bot.tree.command(
    name="grow_erstellen",
    description="Erstellt ein Pflanzenprofil mit Growlog-Thread."
)
async def grow_erstellen(
    interaction: discord.Interaction,
    name: str,
    sorte: str
):
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message(
            "❌ Dieser Befehl funktioniert nur in einem Textkanal.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"🌱 Growlog für **{name}** wird erstellt …",
        ephemeral=True
    )
    startnachricht = await interaction.channel.send(
        f"🌱 **Pflanzenprofil: {name}**\n"
        f"🧬 **Sorte:** {sorte}\n"
        f"👤 **Grower:** {interaction.user.mention}"
    )

    thread = await startnachricht.create_thread(
        name=f"🌱 {name} – Growlog",
        auto_archive_duration=1440
    )

    await thread.send(
        f"## 🌲 Black Forest Genetics Growlog\n\n"
        f"**Pflanze:** {name}\n"
        f"**Sorte:** {sorte}\n"
        f"**Grower:** {interaction.user.mention}\n\n"
        f"### 📋 Neuer Eintrag\n"
        f"🌡️ **Temperatur:** —\n"
        f"💧**Luftfeuchtigkeit:** —\n"
        f"🚿 **Gießen:** —\n"
        f"🧪 **Düngung:** —\n"
        f"⚗️ **pH:** —\n"
        f"💡 **PPFD / DLI:** —\n"
        f"📏 **Wuchshöhe:** —\n"
        f"📝 **Notizen:** —\n"
        f"📷 **Fotos:** Als Nachricht im Thread hochladen"
    )

    await interaction.followup.send(
        f"✅ Growlog erstellt: {thread.mention}",
        ephemeral=True
    )
@bot.tree.command(
    name="eintrag",
    description="Fügt einen neuen Eintrag zum Growlog hinzu."
)
@app_commands.describe(
    temperatur="Temperatur, zum Beispiel 24 °C",
    luftfeuchtigkeit="Luftfeuchtigkeit, zum Beispiel 65 %",
    giessen="Gießmenge oder Angabe zum Gießen",
    duengung="Verwendeter Dünger und Dosierung",
    ph="Gemessener pH-Wert",
    ppfd_dli="Gemessener PPFD- oder DLI-Wert",
    wuchshoehe="Aktuelle Wuchshöhe",
    notizen="Weitere Beobachtungen"
)
async def eintrag(
    interaction: discord.Interaction,
    temperatur: str = "—",
    luftfeuchtigkeit: str = "—",
    giessen: str = "—",
    duengung: str = "—",
    ph: str = "—",
    ppfd_dli: str = "—",
    wuchshoehe: str = "—",
    notizen: str = "—"
):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Benutze `/eintrag` innerhalb eines Growlog-Threads.",
            ephemeral=True
        )
        return

    zeitpunkt = int(interaction.created_at.timestamp())

    await interaction.response.send_message(
        f"## 📋 Neuer Growlog-Eintrag\n"
        f"📅 **Zeitpunkt:** <t:{zeitpunkt}:F>\n"
        f"👤 **Grower:** {interaction.user.mention}\n\n"
        f"🌡️ **Temperatur:** {temperatur}\n"
        f"💧 **Luftfeuchtigkeit:** {luftfeuchtigkeit}\n"
        f"🚿 **Gießen:**
    {giessen}\n"
        f"🧪 **Düngung:** {duengung}\n"
        f"⚗️ **pH:** {ph}\n"
        f"💡 **PPFD / DLI:** {ppfd_dli}\n"
        f"📏 **Wuchshöhe:** {wuchshoehe}\n"
        f"📝 **Notizen:** {notizen}\n\n"
        f"📷 **Fotos:** Direkt unter diesem Eintrag hochladen"
    )

# -------------------------
# Bot starten
# -------------------------
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN fehlt in den Render-Umgebungsvariablen."
    )

threading.Thread(
    target=run_webserver,
    daemon=True
).start()

bot.run(TOKEN)
