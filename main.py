import os
import threading

import discord
from discord import app_commands
from flask import Flask

TOKEN = os.getenv("DISCORD_TOKEN")

web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Black Forest Genetics GrowBot ist online."


def run_webserver():
    port = int(os.getenv("PORT", "10000"))
    web_app.run(host="0.0.0.0", port=port)


class GrowBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True 
      

        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        commands = await self.tree.sync()
        print(f"{len(commands)} Slash-Commands synchronisiert.")

    async def on_ready(self):
        print(f"GrowBot ist online als {self.user}")
        await self.change_presence(
            activity=discord.Game(name="Black Forest Genetics 🌱")
        )


bot = @bot.tree.command(
    name="hilfe",
    description="Zeigt die verfügbaren GrowBot-Befehle."
)
async def hilfe(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌲 Black Forest Genetics GrowBot",
        description="Willkommen beim digitalen GrowBot.",
        color=discord.Color.green()
    )

    embed.add_field(
        name="🌱 Growlogs",
        value="Growlogs und Pflanzenprofile folgen in Phase 2.",
        inline=False
    )

    embed.add_field(
        name="🛠 Status",
        value="Grundgerüst Version 1.0 ist aktiv.",
        inline=False
    )

    embed.set_footer(
        text="Black Forest Genetics • GrowBot 1.0"
    )


@bot.tree.command(
    name="status",
    description="Prüft, ob der GrowBot funktioniert."
)
async def status(interaction: discord.Interaction):
    await interaction.response.send_message(
        "✅ Der Black Forest Genetics GrowBot ist online."
    )


if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN fehlt. Hinterlege ihn bei Render."
    )
   await interaction.response.send_message(embed=embed)

threading.Thread(target=run_webserver, daemon=True).start()
bot.run(TOKEN)
