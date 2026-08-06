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
    description="Erstellt ein neues Pflanzenprofil."
)
async def grow_erstellen(
    interaction: discord.Interaction,
    name: str,
    sorte: str
):
    await interaction.response.send_message(
        f"🌱 **Neues Grow-Profil erstellt!**\n\n"
        f"**Pflanze:** {name}\n"
        f"**Sorte:** {sorte}"
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
