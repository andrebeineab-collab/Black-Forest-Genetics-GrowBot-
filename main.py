import os
import threading
import sqlite3

from flask import Flask
import discord
from discord import app_commands
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

BERLIN_TZ = ZoneInfo("Europe/Berlin")

def berechne_pflanzenalter(keimdatum: str) -> tuple[int | None, int | None]:
    """Berechnet Lebenstag und Lebenswoche aus dem Keimdatum."""

    
    datum = None

    for formatierung in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            datum = datetime.strptime(keimdatum.strip(), formatierung).date()
            break
        except ValueError:
            continue

    if datum is None:
        return None, None

    lebenstage = (date.today() - datum).days + 1

    if lebenstage < 1:
        return None, None

    lebenswoche = ((lebenstage - 1) // 7) + 1

    return lebenstage, lebenswoche
DB_NAME = "growbot.db"


def init_db():
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_channel_id INTEGER,
            discord_thread_id INTEGER,
            name TEXT NOT NULL,
            sorte TEXT,
            breeder TEXT,
            keimdatum TEXT,
            phase TEXT,
            medium TEXT,
            topfgroesse TEXT,
            lampe TEXT,
            grower_id INTEGER,
            erstellt_am TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_thread_id INTEGER NOT NULL,
            grower_id INTEGER NOT NULL,
            zeitpunkt TEXT NOT NULL,
            temperatur TEXT,
            luftfeuchtigkeit TEXT,
            giessen TEXT,
            duengung TEXT,
            ph TEXT,
            ppfd_dli TEXT,
            wuchshoehe TEXT,
            notizen TEXT
        )
    """)
    
    connection.commit()
    connection.close()

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
@app_commands.choices(
    phase=[
        app_commands.Choice(name="🌱 Keimung", value="Keimung"),
        app_commands.Choice(name="🌿 Sämling", value="Sämling"),
        app_commands.Choice(name="🍃 Wachstum", value="Wachstum"),
        app_commands.Choice(name="🌸 Blüte", value="Blüte"),
        app_commands.Choice(name="🌾 Trocknung", value="Trocknung"),
        app_commands.Choice(name="🫙 Curing", value="Curing"),
        app_commands.Choice(name="🧬 Klon", value="Klon"),
    ]
)
async def grow_erstellen(
    interaction: discord.Interaction,
    name: str,
    sorte: str,
    breeder: str = "—",
    keimdatum: str = "—",
    phase: app_commands.Choice[str] = None,
    medium: str = "—",
    topfgroesse: str = "—",
    lampe: str = "—"
):
    phase_text = phase.value if phase else "Wachstum"  
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
    lebenstage, lebenswoche = berechne_pflanzenalter(keimdatum)
    pflanzen_id = interaction.channel.id
    startnachricht = await interaction.channel.send(
        f"## 🌱 Pflanzenprofil: {name}\n"
        f"🆔 **Pflanzen-ID:** `{pflanzen_id}`\n"
        f"🧬 **Sorte:** {sorte}\n"
        f"🏷️ **Breeder:** {breeder}\n"
        f"📅 **Keimdatum:** {keimdatum}\n"
        f"🌱 **Lebenstag:** {lebenstage}\n"
        f"📆 **Lebenswoche:** {lebenswoche}\n"
        f"🌿 **Phase:** {phase_text}\n"
        f"🪴 **Medium:** {medium}\n"
        f"🪣 **Topfgröße:** {topfgroesse}\n"
        f"💡 **Lampe:** {lampe}\n"
        f"👤 **Grower:** {interaction.user.mention}"
    )
    thread = await startnachricht.create_thread(
        name=f"🌱 {name} – Growlog",
        auto_archive_duration=1440
    )
    speichere_pflanze(
        interaction.channel.id,
        thread.id,
        name,
        sorte,
        breeder,
        keimdatum,
        phase_text,
        medium,
        topfgroesse,
        lampe,
        interaction.user.id
    )
    
    await thread.send(
        f"## 🌲 Black Forest Genetics Growlog\n\n"
        f"**Pflanze:** {name}\n"
        f"**Sorte:** {sorte}\n"
        f"**Breeder:** {breeder}\n"
        f"**Keimdatum:** {keimdatum}\n"
        f"**Phase:** {phase_text}\n"
        f"**Medium:** {medium}\n"
        f"**Topfgröße:** {topfgroesse}\n"
        f"**Lampe:** {lampe}\n"
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
    name="pflanze_info",
    description="Zeigt das gespeicherte Pflanzenprofil dieses Growlogs."
)
async def pflanze_info(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Dieser Befehl funktioniert nur innerhalb eines Growlog-Threads.",
            ephemeral=True
        )
        return

    pflanze = lade_pflanze(interaction.channel.id)
    if pflanze is None:
        await interaction.response.send_message(
            "❌ Für diesen Growlog wurde keine Pflanze in der Datenbank gefunden.",
            ephemeral=True
        )
        return

    (
        name,
        sorte,
        breeder,
        keimdatum,
        phase,
        medium,
        topfgroesse,
        lampe,
        grower_id
    ) = pflanze

    lebenstage, lebenswoche = berechne_pflanzenalter(keimdatum)

    alter_text = (
        f"🌱 **Lebenstag:** {lebenstage}\n"
        f"📅 **Lebenswoche:** {lebenswoche}\n"
        if lebenstage is not None
        else "🌱 **Pflanzenalter:** —\n"
    )

    await interaction.response.send_message(
        f"## 🌱 Pflanzenprofil: {name}\n"
        f"🧬 **Sorte:** {sorte}\n"
        f"🏷️ **Breeder:** {breeder}\n"
        f"📅 **Keimdatum:** {keimdatum}\n"
        f"{alter_text}"
        f"🌿 **Phase:** {phase}\n"
        f"🪴 **Medium:** {medium}\n"
        f"🪣 **Topfgröße:** {topfgroesse}\n"
        f"💡 **Lampe:** {lampe}\n"
        f"👤 **Grower:** <@{grower_id}>"
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
    keimdatum: str,
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

    lebenstage, lebenswoche = berechne_pflanzenalter(keimdatum)

    alter_text = (
        f"🌱 **Lebenstag:** {lebenstage}\n"
        f"📆 **Lebenswoche:** {lebenswoche}\n"
        if lebenstage is not None
        else "⚠️ **Pflanzenalter:** Keimdatum ungültig\n"
    )
    zeitpunkt = int(interaction.created_at.timestamp())

    await interaction.response.send_message(
        f"## 📋 Neuer Growlog-Eintrag\n"
        f"📅 **Zeitpunkt:** <t:{zeitpunkt}:F>\n"
        f"👤 **Grower:** {interaction.user.mention}\n\n"
        f"{alter_text}\n"
        f"🌡️ **Temperatur:** {temperatur}\n"
        f"💧 **Luftfeuchtigkeit:** {luftfeuchtigkeit}\n"
        f"🚿 **Gießen:**{giessen}\n"
        f"🧪 **Düngung:** {duengung}\n"
        f"⚗️ **pH:** {ph}\n"
        f"💡 **PPFD / DLI:** {ppfd_dli}\n"
        f"📏 **Wuchshöhe:** {wuchshoehe}\n"
        f"📝 **Notizen:** {notizen}\n\n"
        f"📷 **Fotos:** Direkt unter diesem Eintrag hochladen"
    )
    speichere_eintrag(
        interaction.channel.id,
        interaction.user.id,
        datetime.now(BERLIN_TZ).isoformat(),
        temperatur,
        luftfeuchtigkeit,
        giessen,
        duengung,
        ph,
        ppfd_dli,
        wuchshoehe,
        notizen
    )
@bot.tree.command(
    name="historie",
    description="Zeigt die gespeicherten Growlog-Einträge dieses Threads."
)
async def historie(interaction: discord.Interaction):

    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Benutze `/historie` innerhalb eines Growlog-Threads.",
            ephemeral=True
        )
        return

    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            zeitpunkt,
            temperatur,
            luftfeuchtigkeit,
            giessen,
            duengung,
            ph,
            ppfd_dli,
            wuchshoehe,
            notizen
        FROM entries
        WHERE discord_thread_id = ?
        ORDER BY id DESC
        LIMIT 10
    """, (interaction.channel.id,))

    eintraege = cursor.fetchall()
    
    cursor.execute("""
    SELECT keimdatum
    FROM plants
    WHERE discord_thread_id = ?
    ORDER BY id DESC
    LIMIT 1
""", (interaction.channel.id,))

pflanze = cursor.fetchone()
keimdatum = pflanze[0] if pflanze else None
    
connection.close()

    if not eintraege:
        await interaction.response.send_message(
            "📭 Für diesen Growlog wurden noch keine gespeicherten Einträge gefunden.",
            ephemeral=True
        )
        return

    text = "## 📚 Growlog-Historie\n\n"
    for eintrag in eintraege:
        (
            zeitpunkt,
            temperatur,
            luftfeuchtigkeit,
            giessen,
            duengung,
            ph,
            ppfd_dli,
            wuchshoehe,
            notizen
        ) = eintrag
        zeitpunkt_dt = datetime.fromisoformat(zeitpunkt)

        if zeitpunkt_dt.tzinfo is None:
            zeitpunkt_dt = zeitpunkt_dt.replace(
                tzinfo=timezone.utc
            ).astimezone(BERLIN_TZ)
        else:
            zeitpunkt_dt = zeitpunkt_dt.astimezone(BERLIN_TZ)

        lebenstage = None
        lebenswoche = None

        if keimdatum:
    for formatierung in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            keimdatum_dt = datetime.strptime(
                keimdatum.strip(),
                formatierung
            ).date()

            lebenstage = (
                zeitpunkt_dt.date() - keimdatum_dt
            ).days + 1

            if lebenstage >= 1:
                lebenswoche = ((lebenstage - 1) // 7) + 1
            else:
                lebenstage = None

            break

        except ValueError:
            continue
    zeitpunkt_text = zeitpunkt_dt.strftime(
            "%d.%m.%Y – %H:%M Uhr"
        )
        
        text += (
            f"📅 **Zeitpunkt:** {zeitpunkt_text}\n"
            f"🌡️ **Temperatur:** {temperatur}\n"
            f"💧 **Luftfeuchtigkeit:** {luftfeuchtigkeit}\n"
            f"🚿 **Gießen:** {giessen}\n"
            f"🧪 **Düngung:** {duengung}\n"
            f"⚗️ **pH:** {ph}\n"
            f"💡 **PPFD / DLI:** {ppfd_dli}\n"
            f"📏 **Wuchshöhe:** {wuchshoehe}\n"
            f"📝 **Notizen:** {notizen}\n"
            f"\n──────────────\n\n"
        )
        await interaction.response.send_message(text)


# -------------------------
# Bot starten
# -------------------------
init_db()
def speichere_pflanze(
    discord_channel_id,
    discord_thread_id,
    name,
    sorte,
    breeder,
    keimdatum,
    phase,
    medium,
    topfgroesse,
    lampe,
    grower_id
):
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO plants (
            discord_channel_id,
            discord_thread_id,
            name,
            sorte,
            breeder,
            keimdatum,
            phase,
            medium,
            topfgroesse,
            lampe,
            grower_id,
            erstellt_am
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        discord_channel_id,
        discord_thread_id,
        name,
        sorte,
        breeder,
        keimdatum,
        phase,
        medium,
        topfgroesse,
        lampe,
        grower_id,
        datetime.now().isoformat()
    ))

    connection.commit()
    connection.close()
def lade_pflanze(thread_id):
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            name,
            sorte,
            breeder,
            keimdatum,
            phase,
            medium,
            topfgroesse,
            lampe,
            grower_id
        FROM plants
        WHERE discord_thread_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (thread_id,))

    pflanze = cursor.fetchone()
    connection.close()

    return pflanze
def speichere_eintrag(
    discord_thread_id,
    grower_id,
    zeitpunkt,
    temperatur,
    luftfeuchtigkeit,
    giessen,
    duengung,
    ph,
    ppfd_dli,
    wuchshoehe,
    notizen
):
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO entries (
            discord_thread_id,
            grower_id,
            zeitpunkt,
            temperatur,
            luftfeuchtigkeit,
            giessen,
            duengung,
            ph,
            ppfd_dli,
            wuchshoehe,
            notizen
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        discord_thread_id,
        grower_id,
        zeitpunkt,
        temperatur,
        luftfeuchtigkeit,
        giessen,
        duengung,
        ph,
        ppfd_dli,
        wuchshoehe,
        notizen
    ))

    connection.commit()
    connection.close()    
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
