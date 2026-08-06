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

bot = GrowBot()# -------------------------
# /hilfe
# -------------------------

@bot.tree.command(
    name="hilfe",
    description="Zeigt die verfügbaren GrowBot-Befehle."
)
async def hilfe(interaction: discord.Interaction):

    embed = discord.Embed(
        title="🌲 Black Forest Genetics GrowBot",
        description="Willkommen beim digitalen GrowBot!",
        color=discord.Color.green()
    )

    embed.add_field(
        name="🌱 Growlogs",
        value="Digitale Growlogs und Pflanzenprofile folgen in den nächsten Versionen.",
        inline=False
    )  
    embed.add_field(
        name="🛠 Status",
        value="Version 1.0 • Bot wird erfolgreich eingerichtet.",
        inline=False
    )

    embed.set_footer(
        text="Black Forest Genetics • GrowBot"
    )

       await interaction.response.send_message(embed=embed)


# -------------------------
# /status
# -------------------------

@bot.tree.command(
    name="status",
    description="Zeigt den Status des GrowBots."
)
async def status(interaction: discord.Interaction):
    await interaction.response.send_message(
        "✅ Black Forest Genetics GrowBot läuft erfolgreich."
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
