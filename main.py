import os
import threading
import psycopg2
import io
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

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
def get_db_connection():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL wurde nicht gefunden.")

    return psycopg2.connect(database_url)


def init_db():
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plants (
            id BIGSERIAL PRIMARY KEY,
            discord_channel_id BIGINT,
            discord_thread_id BIGINT,
            name TEXT NOT NULL,
            sorte TEXT,
            breeder TEXT,
            keimdatum TEXT,
            phase TEXT,
            medium TEXT,
            topfgroesse TEXT,
            lampe TEXT,
            grower_id BIGINT,
            erstellt_am TEXT
        )
    """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id BIGSERIAL PRIMARY KEY,
                discord_thread_id BIGINT NOT NULL,
                grower_id BIGINT NOT NULL,
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS phase_history (
            id BIGSERIAL PRIMARY KEY,
            discord_thread_id BIGINT NOT NULL,
            grower_id BIGINT,
            alte_phase TEXT,
            neue_phase TEXT NOT NULL,
            geaendert_am TEXT NOT NULL
        )
    """)

    # Breeder-Projekte
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS breeder_projects (
            id BIGSERIAL PRIMARY KEY,
            discord_channel_id BIGINT,
            discord_thread_id BIGINT,
            grower_id BIGINT NOT NULL,
            projektname TEXT NOT NULL,
            mutterpflanze TEXT,
            vaterpflanze TEXT,
            kreuzung TEXT,
            generation TEXT,
            samenanzahl INTEGER,
            keimrate TEXT,
            phaenotypen TEXT,
            selektion TEXT,
            besonderheiten TEXT,
            erstellt_am TEXT
        )
    """)
    
    # Pflanzenprofil erweitern
    cursor.execute("""
        ALTER TABLE plants
        ADD COLUMN IF NOT EXISTS genetik_typ TEXT
    """)

    cursor.execute("""
        ALTER TABLE plants
        ADD COLUMN IF NOT EXISTS anbaumethode TEXT
    """)

    cursor.execute("""
        ALTER TABLE plants
        ADD COLUMN IF NOT EXISTS lichtzyklus TEXT
    """)

    cursor.execute("""
        ALTER TABLE plants
        ADD COLUMN IF NOT EXISTS status TEXT
    """)

    connection.commit()
    cursor.close()
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
    temp_system="Einheitensystem für Temperatur auswählen",
    giessen_menge="Gießmenge – nur die Zahl eingeben",
    giessen_einheit="Einheit der Gießmenge auswählen",
    duenger_name="Name des verwendeten Düngers",
    duengung_menge="Dosierung - nur die Zahl eingeben",
    duengung_einheit="Einheit der Dosierung auswählen",
    ph="Gemessener pH-Wert",
    ppfd_dli="Gemessener PPFD- oder DLI-Wert",
    wuchshoehe="Aktuelle Wuchshöhe - nur die Zahl eingeben",
    wuchshoehe_einheit="Einheit der Wuchshöhe auswählen",
    notizen="Weitere Beobachtungen"
)
@app_commands.choices(
    temp_system=[
        app_commands.Choice(name="🇩🇪 Deutsch – °C / %", value="DE"),
        app_commands.Choice(name="🇺🇸 US – °F / %", value="US")
    ],
    giessen_einheit=[
        app_commands.Choice(name="ml", value="ml"),
        app_commands.Choice(name="L", value="L")
    ],
    duengung_einheit=[
        app_commands.Choice(name="ml/L", value="ml/L"),
        app_commands.Choice(name="g/L", value="g/L")
    ],
    wuchshoehe_einheit=[
    app_commands.Choice(name="cm", value="cm"),
    app_commands.Choice(name="m", value="m"),
    app_commands.Choice(name="in", value="in"),
    app_commands.Choice(name="ft", value="ft")
    ]
)
async def eintrag(
    interaction: discord.Interaction,
    keimdatum: str = "_",
    temperatur: str = "—",
    luftfeuchtigkeit: str = "—",
    temp_system: app_commands.Choice[str] | None = None,
    giessen_menge: str = "—",
    giessen_einheit: app_commands.Choice[str] = None,
    duenger_name: str = "_",
    duengung_menge: str = "_",
    duengung_einheit: app_commands.Choice[str] = None,
    ph: float | None = None,
    ppfd_dli: str = "—",
    wuchshoehe: str = "—",
    wuchshoehe_einheit: app_commands.Choice[str] | None = None,
    notizen: str = "—"
):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Benutze `/eintrag` innerhalb eines Growlog-Threads.",
            ephemeral=True
        )
        return
    await interaction.response.defer()
    if keimdatum in ("_", "—", "", None):
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT keimdatum
                FROM plants
                WHERE discord_thread_id = %s
                ORDER BY id DESC
                LIMIT 1
            """, (interaction.channel.id,))
            pflanze = cursor.fetchone()
            connection.close()

            if pflanze:
                keimdatum = pflanze[0]

    lebenstage, lebenswoche = berechne_pflanzenalter(keimdatum)


    alter_text = (
        f"🌱 **Lebenstag:** {lebenstage}\n"
        f"📆 **Lebenswoche:** {lebenswoche}\n"
        if lebenstage is not None
        else "⚠️ **Pflanzenalter:** Keimdatum ungültig\n"
    )
    zeitpunkt = int(interaction.created_at.timestamp())

    system = temp_system.value if temp_system else "DE"

    if temperatur not in ("—", "-", ""):
        temperatur_text = (
            f"{temperatur} °F"
            if system == "US"
            else f"{temperatur} °C"
        )
    else:
        temperatur_text = "—"

    if luftfeuchtigkeit not in ("—", "-", ""):
        luftfeuchtigkeit_text = f"{luftfeuchtigkeit} %"
    else:
        luftfeuchtigkeit_text = "—"
    
    await interaction.followup.send(
        f"## 📋 Neuer Growlog-Eintrag\n"
        f"📅 **Zeitpunkt:** <t:{zeitpunkt}:F>\n"
        f"👤 **Grower:** {interaction.user.mention}\n\n"
        f"{alter_text}\n"
        f"🌡️ **Temperatur:** {temperatur_text}\n"
        f"💧 **Luftfeuchtigkeit:** {luftfeuchtigkeit_text}\n"
        f"🚿 **Gießen:** {giessen_menge} {giessen_einheit.value if giessen_einheit else ''}\n"
        f"🧪 **Düngung:** {duenger_name} – {duengung_menge} {duengung_einheit.value if duengung_einheit else ''}\n"
        f"⚗️ **pH:** {ph if ph is not None else '—'}\n"
        f"💡 **PPFD / DLI:** {ppfd_dli}\n"
        f"📏 **Wuchshöhe:** {wuchshoehe} {wuchshoehe_einheit.value if wuchshoehe_einheit else ''}\n"
        f"📝 **Notizen:** {notizen}\n\n"
        f"📷 **Fotos:** Direkt unter diesem Eintrag hochladen"
    )
    speichere_eintrag(
        interaction.channel.id,
        interaction.user.id,
        datetime.now(BERLIN_TZ).isoformat(),
        temperatur_text,
        luftfeuchtigkeit_text,
        f"{giessen_menge} {giessen_einheit.value if giessen_einheit else ''}",
        f"{duenger_name} – {duengung_menge} {duengung_einheit.value if duengung_einheit else ''}",
        ph,
        ppfd_dli,
        f"{wuchshoehe} {wuchshoehe_einheit.value if wuchshoehe_einheit else ''}".strip(),
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
    await interaction.response.defer(ephemeral=True)

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
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
        WHERE discord_thread_id = %s
        ORDER BY id DESC
        LIMIT 10
    """, (interaction.channel.id,))

    eintraege = cursor.fetchall()
    
    cursor.execute("""
    SELECT keimdatum
    FROM plants
    WHERE discord_thread_id = %s
    ORDER BY id DESC
    LIMIT 1
""", (interaction.channel.id,))

    pflanze = cursor.fetchone()
    keimdatum = pflanze[0] if pflanze else None
    cursor.execute(
    """
    SELECT
        alte_phase,
        neue_phase,
        geaendert_am
    FROM phase_history
    WHERE discord_thread_id = %s
    ORDER BY id ASC
    """,
    (interaction.channel.id,)
)

    phasen_eintraege = cursor.fetchall()
    
    connection.close()

    if not eintraege:
        await interaction.followup.send(
            "📭 Für diesen Growlog wurden noch keine gespeicherten Einträge gefunden.",
            ephemeral=True
        )
        return

    def anzeige_wert(wert):
        if wert is None or wert == "":
            return "—"
        return wert

    foto_embeds = []

    text = "## 📚 Growlog-Historie\n\n"
    for eintrag in eintraege:
        (
            entry_id,
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

        photo_connection = get_db_connection()
        photo_cursor = photo_connection.cursor()

        photo_cursor.execute(
            """
            SELECT image_url
            FROM photos
            WHERE discord_thread_id = %s
              AND entry_id = %s
            ORDER BY id ASC
            """,
            (interaction.channel.id, entry_id)
        )

        foto_urls = [row[0] for row in photo_cursor.fetchall()]
        photo_connection.close()

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
                f"🌡️ **Temperatur:** {anzeige_wert(temperatur)}\n"
                f"💧 **Luftfeuchtigkeit:** {anzeige_wert(luftfeuchtigkeit)}\n"
                f"🚿 **Gießen:** {anzeige_wert(giessen)}\n"
                f"🧪 **Düngung:** {anzeige_wert(duengung)}\n"
                f"🚿 **pH:** {anzeige_wert(ph)}\n"
                f"💡 **PPFD / DLI:** {anzeige_wert(ppfd_dli)}\n"
                f"📏 **Wuchshöhe:** {anzeige_wert(wuchshoehe)}\n"
                f"📝 **Notizen:** {anzeige_wert(notizen)}\n"
                f"📷 **Fotos:** {len(foto_urls)}\n"
                f"\n────────────────\n\n"
        )
        for foto_url in foto_urls:
            foto_embed = discord.Embed(
                title="📷 Growlog-Foto",
                description=f"📋 **Growlog-Eintrag:** {entry_id}",
                color=discord.Color.green()
            )

            foto_embed.set_image(url=foto_url)

            foto_embed.set_footer(
                text="Black Forest Genetics • GrowBot"
            )

            foto_embeds.append(foto_embed)
    for i in range(0, len(text), 1900):
        await interaction.followup.send(
            text[i:i + 1900], ephemeral=True
        )

    for foto_embed in foto_embeds:
        await interaction.followup.send(
            embed=foto_embed,
            ephemeral=True
        )

@bot.tree.command(
    name="diagramm",
    description="Zeigt Temperatur und Luftfeuchtigkeit als Growlog-Diagramm."
)
@app_commands.describe(
    temp_system="Temperaturanzeige für das Diagramm auswählen"
)
@app_commands.choices(
    temp_system=[
        app_commands.Choice(name="🇩🇪 Deutsch – °C", value="DE"),
        app_commands.Choice(name="🇺🇸 US – °F", value="US")
    ]
)
async def diagramm(
    interaction: discord.Interaction,
    temp_system: app_commands.Choice[str] | None = None
):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
     "❌ Benutze `/diagramm` innerhalb eines Growlog-Threads.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            zeitpunkt,
            temperatur,
            luftfeuchtigkeit,
            giessen,
            wuchshoehe,
            ppfd_dli
        FROM entries
        WHERE discord_thread_id = %s
        ORDER BY id ASC
        """,
        (interaction.channel.id,)
    )

    eintraege = cursor.fetchall()

    cursor.close()
    connection.close()

    if not eintraege:
        await interaction.followup.send(
            "📭 Für diesen Growlog sind noch keine Daten vorhanden.",
            ephemeral=True
        )
        return

    import io
    import re
    from datetime import datetime
    from matplotlib.figure import Figure

    system = temp_system.value if temp_system else "DE"

    zeitpunkte = []
    temperaturen = []
    luftwerte = []
    giesswerte = []
    hoehenwerte = []
    ppfd_werte = []

    def zahl_lesen(wert):
        if wert is None:
            return None

        text = str(wert).strip()

        if text in ("", "-", "—", "_"):
            return None

        treffer = re.search(r"-?\d+(?:[.,]\d+)?", text)
        if not treffer:
            return None

        return float(
            treffer.group(0).replace(",", ".")
        )

    for zeitpunkt, temperatur, luftfeuchtigkeit, giessen, wuchshoehe, ppfd_dli in eintraege:

        temp = zahl_lesen(temperatur)
        luft = zahl_lesen(luftfeuchtigkeit)
        giessen_wert = zahl_lesen(giessen)
        hoehe_wert = zahl_lesen(wuchshoehe)
        ppfd_wert = zahl_lesen(ppfd_dli)

        if all(wert is None for wert in (temp, luft, giessen_wert, hoehe_wert, ppfd_wert)):
            continue
        # Gießmenge einheitlich in ml umrechnen
        if giessen_wert is not None:
            giessen_text = str(giessen).lower()

            if "ml" not in giessen_text and "l" in giessen_text:
                giessen_wert *= 1000

        # Wuchshöhe einheitlich in cm umrechnen
        if hoehe_wert is not None:
            hoehe_text = str(wuchshoehe).lower()

            if "ft" in hoehe_text:
                hoehe_wert *= 30.48
            elif "in" in hoehe_text:
                hoehe_wert *= 2.54
            elif "cm" in hoehe_text:
                pass
            elif "m" in hoehe_text:
                hoehe_wert *= 100
        # Gespeicherte Fahrenheit-Werte zuerst in Celsius umrechnen
        if temp is not None:
            temperatur_string = str(temperatur).upper()

        if "°F" in temperatur_string or " F" in temperatur_string:
            temp = (temp - 32) * 5 / 9
            # Für US-Diagramm wieder in Fahrenheit umrechnen
        if system == "US":
            temp = (temp * 9 / 5) + 32

        try:
            datum = datetime.fromisoformat(str(zeitpunkt))
            datum_text = datum.strftime("%d.%m.")
        except (ValueError, TypeError):
            datum_text = str(zeitpunkt)[:10]

        zeitpunkte.append(datum_text)
        temperaturen.append(temp)
        luftwerte.append(luft)
        giesswerte.append(giessen_wert)
        hoehenwerte.append(hoehe_wert)
        ppfd_werte.append(ppfd_wert)

    if not zeitpunkte:
        await interaction.followup.send(
            "📊 Noch keine auswertbaren Temperatur- oder Luftfeuchtigkeitswerte vorhanden.",
            ephemeral=True
        )
        return
    fig = Figure(figsize=(9, 5))
    ax1 = fig.subplots()

    x = list(range(len(zeitpunkte)))

    temp_einheit = "°F" if system == "US" else "°C"

    temp_x = [
        x[i]
        for i, wert in enumerate(temperaturen)
        if wert is not None
    ]

    temp_y = [
        wert
        for wert in temperaturen
        if wert is not None
    ]

    luft_x = [
        x[i]
        for i, wert in enumerate(luftwerte)
        if wert is not None
    ]

    luft_y = [
        wert
        for wert in luftwerte
        if wert is not None
    ]
    giess_x = [
        x[i]
        for i, wert in enumerate(giesswerte)
        if wert is not None
    ]

    giess_y = [
        wert
        for wert in giesswerte
        if wert is not None
    ]

    hoehe_x = [
        x[i]
        for i, wert in enumerate(hoehenwerte)
        if wert is not None
    ]

    hoehe_y = [
        wert
        for wert in hoehenwerte
        if wert is not None
    ]

    ppfd_x = [
        x[i]
        for i, wert in enumerate(ppfd_werte)
        if wert is not None
    ]

    ppfd_y = [
        wert
        for wert in ppfd_werte
        if wert is not None
    ]
    if temp_y:
        ax1.plot(
            temp_x,
            temp_y,
            marker="o",
            label=f"Temperatur ({temp_einheit})"
        )

    ax1.set_xlabel("Growlog")
    ax1.set_ylabel(f"Temperatur ({temp_einheit})")
    ax1.set_xticks(x)
    ax1.set_xticklabels(
        zeitpunkte,
        rotation=45,
        ha="right"
    )
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()

    if luft_y:
        ax2.plot(
            luft_x,
            luft_y,
            marker="s",
            linestyle="--",
            label="Luftfeuchtigkeit (%)"
        )
        ax2.set_ylabel("Luftfeuchtigkeit (%)")

    fig.suptitle(
        f"🌱 Black Forest Genetics – {interaction.channel.name}"
    )

    fig.tight_layout()

    bild = io.BytesIO()
    fig.savefig(
        bild,
        format="png",
        dpi=150,
        bbox_inches="tight"
    )
    bild.seek(0)

    datei = discord.File(
        bild,
        filename="growlog_diagramm.png"
    )

    await interaction.followup.send(
        "📊 **Growlog-Diagramm**\n"
        f"🌡️ Temperatur: **{temp_einheit}**\n"
        "💧 Luftfeuchtigkeit: **%**",
        file=datei,
        ephemeral=True
    )

    #Zweites Diagramm: Gießen, Wuchshöhe und PPFD
    if giess_y or hoehe_y or ppfd_y:
        fig2 = Figure(figsize=(9, 8))
        ax_giessen, ax_hoehe, ax_ppfd = fig2.subplots(
            3,
            1,
            sharex=True
        )

        # Gießen
        if giess_y:
            ax_giessen.plot(
                giess_x,
                giess_y,
                marker="o"
            )

        ax_giessen.set_ylabel("Gießen (ml)")
        ax_giessen.grid(True, alpha=0.3)

        # Wuchshöhe
        if hoehe_y:
            ax_hoehe.plot(
                hoehe_x,
                hoehe_y,
                marker="o"
            )

        ax_hoehe.set_ylabel("Wuchshöhe (cm)")
        ax_hoehe.grid(True, alpha=0.3)

        # PPFD / DLI
        if ppfd_y:
            ax_ppfd.plot(
                ppfd_x,
                ppfd_y,
                marker="o"
            )

        ax_ppfd.set_ylabel("PPFD / DLI")
        ax_ppfd.set_xlabel("Growlog")
        ax_ppfd.grid(True, alpha=0.3)

        ax_ppfd.set_xticks(x)
        ax_ppfd.set_xticklabels(
            zeitpunkte,
            rotation=45,
            ha="right"
        )

        fig2.suptitle(
            f"🌱 Black Forest Genetics – {interaction.channel.name}"
        )
        fig2.tight_layout()

        bild2 = io.BytesIO()
        fig2.savefig(
            bild2,
            format="png",
            dpi=150,
            bbox_inches="tight"
        )
        bild2.seek(0)

        datei2 = discord.File(
            bild2,
            filename="growlog_werte_diagramm.png"
        )

        await interaction.followup.send(
            "📊 **Gießen · Wuchshöhe · PPFD / DLI**",
            file=datei2,
            ephemeral=True
        )

@bot.tree.command(
    name="phasen-historie",
    description="Zeigt die gespeicherten Phasenänderungen dieser Pflanze."
)
async def phasen_historie(interaction: discord.Interaction):

    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Benutze `/phasen-historie` innerhalb eines Growlog-Threads.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
  alte_phase,
            neue_phase,
            geaendert_am
        FROM phase_history
        WHERE discord_thread_id = %s
        ORDER BY id ASC
        """,
        (interaction.channel.id,)
    )

    eintraege = cursor.fetchall()
    connection.close()

    if not eintraege:
        await interaction.followup.send(
            "🌱 Für diese Pflanze wurden noch keine Phasenänderungen gespeichert.",
            ephemeral=True
        )
        return

    text = "## 🌱 Phasen-Historie\n\n"

    for alte_phase, neue_phase, geaendert_am in eintraege:

        try:
            zeitpunkt = datetime.fromisoformat(str(geaendert_am))

            if zeitpunkt.tzinfo is None:
                zeitpunkt = zeitpunkt.replace(
                    tzinfo=timezone.utc
                ).astimezone(BERLIN_TZ)
            else:
                zeitpunkt = zeitpunkt.astimezone(BERLIN_TZ)

            zeit_text = zeitpunkt.strftime(
                "%d.%m.%Y – %H:%M Uhr"
            )

        except (ValueError, TypeError):
            zeit_text = str(geaendert_am)

        text += (
            f"📅 **{zeit_text}**\n"
            f"🌿 **{alte_phase or '-'} → {neue_phase or '-'}**\n"
            f"──────────────\n\n"
        )

    for i in range(0, len(text), 1900):
        await interaction.followup.send(
            text[i:i + 1900],
            ephemeral=True
    )

@bot.tree.command(
    name="foto",
    description="Speichert ein Foto im aktuellen Growlog."
)
async def foto(
    interaction: discord.Interaction,
    bild: discord.Attachment
):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Dieser Befehl funktioniert nur in einem Growlog-Thread.",
            ephemeral=True
        )
        return

    if not bild.content_type or not bild.content_type.startswith("image/"):
        await interaction.response.send_message(
            "❌ Bitte lade eine Bilddatei hoch.",
            ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True)

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(   
        """
            SELECT id
            FROM entries
            WHERE discord_thread_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (interaction.channel.id,)
        )

    letzter_eintrag = cursor.fetchone()
    entry_id = letzter_eintrag[0] if letzter_eintrag else None

    cursor.execute(
        """
        INSERT INTO photos (
        discord_thread_id,
            grower_id,
            entry_id,
            image_url,
            message_id,
            erstellt_am
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            interaction.channel.id,
            interaction.user.id,
            entry_id,
            bild.url,
            None,
            datetime.now(BERLIN_TZ).isoformat()
        )
    )

    connection.commit()
    connection.close()
    embed = discord.Embed(
        title="📸 Growlog-Foto",
        description=f"👤 **Grower:** {interaction.user.mention}",
        color=discord.Color.green()
    )

    embed.set_image(url=bild.url)

    embed.set_footer(
        text="Black Forest Genetics • GrowBot"
    )

    await interaction.channel.send(embed=embed)

    await interaction.followup.send(
        "✅ Foto wurde im Growlog gespeichert.",
        ephemeral=True
    )

@bot.tree.command(
    name="foto-historie",
    description="Zeigt die gespeicherten Fotos dieses Growlogs."
)
async def foto_historie(interaction: discord.Interaction):

    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Benutze `/foto-historie` innerhalb eines Growlog-Threads.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
   image_url,
            grower_id,
            entry_id,
            erstellt_am
        FROM photos
        WHERE discord_thread_id = %s
        ORDER BY id DESC
        LIMIT 10
        """,
        (interaction.channel.id,)
    )

    fotos = cursor.fetchall()
    connection.close()

    if not fotos:
        await interaction.followup.send(
            "📭 Für diesen Growlog wurden noch keine Fotos gespeichert.",
            ephemeral=True
        )
        return

    await interaction.followup.send(
        f"📸 **Foto-Historie**\n"
        f"Gespeicherte Fotos: **{len(fotos)}**",
        ephemeral=True
    )
    for image_url, grower_id, entry_id, erstellt_am in fotos:

        try:
            zeitpunkt = datetime.fromisoformat(str(erstellt_am))

            if zeitpunkt.tzinfo is None:
                zeitpunkt = zeitpunkt.replace(
                    tzinfo=timezone.utc
                ).astimezone(BERLIN_TZ)
            else:
                zeitpunkt = zeitpunkt.astimezone(BERLIN_TZ)

            zeit_text = zeitpunkt.strftime(
                "%d.%m.%Y – %H:%M Uhr"
            )

        except (ValueError, TypeError):
            zeit_text = str(erstellt_am)

        embed = discord.Embed(
            title="📸 Growlog-Foto",
            description=(
                f"👤 **Grower:** <@{grower_id}>\n"
                f"📋 **Growlog-Eintrag:** {entry_id or '-'}\n"
                f"🕒 **Zeitpunkt:** {zeit_text}"
            ),
            color=discord.Color.green()
        )

        embed.set_image(url=image_url)

        embed.set_footer(
            text="Black Forest Genetics • GrowBot"
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not isinstance(message.channel, discord.Thread):
        return

    if not message.attachments:
        return

    bilder = [
        attachment
        for attachment in message.attachments
        if attachment.content_type
        and attachment.content_type.startswith("image/")
    ]

    if not bilder:
        return

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM entries
        WHERE discord_thread_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (message.channel.id,)
    )

    letzter_eintrag = cursor.fetchone()

    if not letzter_eintrag:
        connection.close()
        return

    entry_id = letzter_eintrag[0]

    for bild in bilder:
        cursor.execute(
            """
            INSERT INTO photos (
                discord_thread_id,
                grower_id,
                entry_id,
                image_url,
                message_id,
                erstellt_am
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                message.channel.id,
                message.author.id,
                entry_id,
                bild.url,
                message.id,
                datetime.now(BERLIN_TZ).isoformat()
            )
        )

    connection.commit()
    connection.close()

    try:
        await message.add_reaction("✅")
    except discord.Forbidden:
        pass


# -------------------------
# Bot starten
# -------------------------
def init_phase_history():
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS phase_history (
            id SERIAL PRIMARY KEY,
            discord_thread_id BIGINT NOT NULL,
            grower_id BIGINT,
            alte_phase TEXT,
            neue_phase TEXT,
            geaendert_am TEXT
        )
    """)

    connection.commit()
    connection.close()
    
def init_photos():
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id SERIAL PRIMARY KEY,
            discord_thread_id BIGINT NOT NULL,
            grower_id BIGINT,
            entry_id BIGINT,
            image_url TEXT NOT NULL,
            message_id BIGINT,
            erstellt_am TEXT
        )
    """)

    connection.commit()
    connection.close()

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
    grower_id,
    genetik_typ,
    anbaumethode,
    lichtzyklus,
    status
):
    connection =get_db_connection()
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
            genetik_typ,
            anbaumethode,
            lichtzyklus,
            status,
            erstellt_am
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        genetik_typ,
        anbaumethode,
        lichtzyklus,
        status,
        datetime.now().isoformat()
    ))

    connection.commit()
    connection.close()

def erstelle_breeder_projekt(
    discord_channel_id,
    discord_thread_id,
    grower_id,
    projektname,
    mutterpflanze,
    vaterpflanze,
    kreuzung,
    generation,
    samenanzahl,
    keimrate,
    phaenotypen,
    selektion,
    besonderheiten
):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO breeder_projects (
            discord_channel_id,
            discord_thread_id,
            grower_id,
            projektname,
            mutterpflanze,
            vaterpflanze,
            kreuzung,
            generation,
            samenanzahl,
            keimrate,
            phaenotypen,
            selektion,
            besonderheiten,
            erstellt_am
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        discord_channel_id,
        discord_thread_id,
        grower_id,
        projektname,
        mutterpflanze,
        vaterpflanze,
        kreuzung,
        generation,
        samenanzahl,
        keimrate,
        phaenotypen,
        selektion,
        besonderheiten,
        datetime.now().isoformat()
    ))

    projekt_id = cursor.fetchone()[0]

    connection.commit()
    connection.close()

    return projekt_id

def lade_pflanze(thread_id):
    connection = get_db_connection()
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
    grower_id,
    genetik_typ,
    anbaumethode,
    lichtzyklus,
    status
        FROM plants
        WHERE discord_thread_id = %s
        ORDER BY id DESC
        LIMIT 1
    """, (thread_id,))

    pflanze = cursor.fetchone()
    connection.close()

    return pflanze

def aktualisiere_pflanze(
    thread_id,
    phase,
    medium,
    topfgroesse,
    lampe,
    genetik_typ,
    anbaumethode,
    lichtzyklus,
    status
):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE plants
        SET
            phase = %s,
            medium = %s,
            topfgroesse = %s,
            lampe = %s,
            genetik_typ = %s,
            anbaumethode = %s,
            lichtzyklus = %s,
            status = %s
        WHERE discord_thread_id = %s
        """, (
        phase,
        medium,
        topfgroesse,
        lampe,
        genetik_typ,
        anbaumethode,
        lichtzyklus,
        status,
        thread_id
    ))
    

    connection.commit()
    connection.close()


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
    connection = get_db_connection()
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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

@bot.tree.command(
    name="profil",
    description="Zeigt das Pflanzenprofil dieses Growlogs an."
)
async def profil(interaction: discord.Interaction):

    # Der Command muss in einem Thread ausgeführt werden
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Dieser Befehl funktioniert nur in einem Growlog-Thread.",
            ephemeral=True
        )
        return

    # Pflanzenprofil anhand der Thread-ID laden
    pflanze = lade_pflanze(interaction.channel.id)

    if not pflanze:
        await interaction.response.send_message(
            "❌ Für diesen Growlog wurde noch kein Pflanzenprofil gespeichert.",
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
        grower_id,
        genetik_typ,
        anbaumethode,
        lichtzyklus,
        status
    ) = pflanze

    # Leere Werte sauber darstellen
    def wert(value):
        if value is None or str(value).strip() == "":
            return "–"
        return str(value)

    embed = discord.Embed(
        title=f"🌱 Pflanzenprofil – {wert(name)}",
        description="Black Forest Genetics • Digitales Pflanzenprofil"
    )

    embed.add_field(
        name="🧬 Sorte",
        value=wert(sorte),
        inline=True
    )

    embed.add_field(
        name="🏷️ Breeder",
        value=wert(breeder),
        inline=True
    )

    embed.add_field(
        name="📅 Keimdatum",
        value=wert(keimdatum),
        inline=True
    )

    lebenstag, lebenswoche = berechne_pflanzenalter(keimdatum)

    embed.add_field(
        name="🌱 Lebenstag",
        value=str(lebenstag) if lebenstag is not None else "–",
        inline=True
    )

    embed.add_field(
        name="📅 Lebenswoche",
        value=str(lebenswoche) if lebenswoche is not None else "–",
        inline=True
    )

    embed.add_field(
        name="🌿 Phase",
        value=wert(phase),
        inline=True
    )

    embed.add_field(
        name="🪴 Medium",
        value=wert(medium),
        inline=True
    )

    embed.add_field(
        name="🪣 Topfgröße",
        value=wert(topfgroesse),
        inline=True
    )

    embed.add_field(
        name="💡 Lampe",
        value=wert(lampe),
        inline=True
    )

    embed.add_field(
        name="🧬 Genetik-Typ",
        value=wert(genetik_typ),
        inline=True
    )

    embed.add_field(
        name="🌱 Anbaumethode",
        value=wert(anbaumethode),
        inline=True
    )

    embed.add_field(
        name="☀️ Lichtzyklus",
        value=wert(lichtzyklus),
        inline=True
    )

    embed.add_field(
        name="📊 Status",
        value=wert(status),
        inline=True
    )

    embed.add_field(
        name="👤 Grower",
        value=f"<@{grower_id}>",
        inline=True
    )

    embed.set_footer(
        text="Black Forest Genetics • GrowBot"
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(
    name="phase",
    description="Ändert die aktuelle Phase der Pflanze."
)
@app_commands.describe(
    phase="Neue Pflanzenphase"
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
async def phase(
    interaction: discord.Interaction,
    phase: app_commands.Choice[str]
):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
             "❌ Dieser Befehl funktioniert nur in einem Growlog-Thread.",
            ephemeral=True
        )
        return
   
    await interaction.response.defer(ephemeral=True)

    print("PHASE 1: defer abgeschlossen", flush=True)

    print("PHASE 2: verbinde Datenbank", flush=True)
    connection = get_db_connection()

    print("PHASE 3: Datenbank verbunden", flush=True)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT phase
        FROM plants
        WHERE discord_thread_id = %s
        """,
        (interaction.channel.id,)
    )

    plant = cursor.fetchone()
    alte_phase = plant[0] if plant else None

    print("PHASE 4: starte UPDATE", flush=True)
    cursor.execute(
        """
        UPDATE plants
        SET phase = %s
        WHERE discord_thread_id = %s
        """,
        (phase.value, interaction.channel.id)
    )

    print("PHASE 5: UPDATE fertig", flush=True)

    geaendert = cursor.rowcount
    if geaendert > 0 and alte_phase != phase.value:
        cursor.execute(
            """
            INSERT INTO phase_history (
                discord_thread_id,
                grower_id,
                alte_phase,
                neue_phase,
                geaendert_am
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                interaction.channel.id,
                interaction.user.id,
                alte_phase,
                phase.value,
                datetime.now(BERLIN_TZ).isoformat()
            )
        )

    print("PHASE 6: commit", flush=True)
    connection.commit()

    print("PHASE 7: commit fertig", flush=True)
    connection.close()
    
    

    if geaendert == 0:
            await interaction.followup.send(
                "❌ Für diesen Growlog wurde kein Pflanzenprofil gefunden.",
                ephemeral=True
            )
            return
    await interaction.followup.send(
    f"🌿 **Pflanzenphase aktualisiert**\n\n"
    f"Neue Phase: **{phase.value}**",
    ephemeral=True
    )

@bot.tree.command(
    name="phasenhistorie",
    description="Zeigt die gespeicherten Phasenwechsel dieses Growlogs."
)
async def phasenhistorie(interaction: discord.Interaction):

    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Dieser Befehl funktioniert nur in einem Growlog-Thread.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT alte_phase, neue_phase, geaendert_am
        FROM phase_history
        WHERE discord_thread_id = %s
        ORDER BY id ASC
        """,
        (interaction.channel.id,)
    )

    eintraege = cursor.fetchall()

    cursor.close()
    connection.close()

    if not eintraege:
        await interaction.followup.send(
            "📭 Für diesen Growlog gibt es noch keine gespeicherten Phasenwechsel.",
            ephemeral=True
        )
        return

    text = "## 🌿 Phasenhistorie\n\n"
    for alte_phase, neue_phase, geaendert_am in eintraege:

        try:
            zeitpunkt = datetime.fromisoformat(geaendert_am)

            if zeitpunkt.tzinfo is None:
                zeitpunkt = zeitpunkt.replace(tzinfo=timezone.utc)

            zeitpunkt = zeitpunkt.astimezone(BERLIN_TZ)
            zeit_text = zeitpunkt.strftime("%d.%m.%Y – %H:%M Uhr")

        except (ValueError, TypeError):
            zeit_text = geaendert_am

        text += (
            f"🌱 **{alte_phase or '-'} → {neue_phase}**\n"
            f"🕒 {zeit_text}\n\n"
        )
        await interaction.followup.send(
        text,
        ephemeral=True
    )

@bot.tree.command(
    name="phasendauer",
    description="Zeigt die Dauer der gespeicherten Pflanzenphasen."
)
async def phasendauer(interaction: discord.Interaction):

    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Dieser Befehl funktioniert nur in einem Growlog-Thread.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT alte_phase, neue_phase, geaendert_am
        FROM phase_history
        WHERE discord_thread_id = %s
        ORDER BY id ASC
        """,
        (interaction.channel.id,)
    )

    eintraege = cursor.fetchall()

    cursor.execute(
        """
        SELECT phase
        FROM plants
        WHERE discord_thread_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (interaction.channel.id,)
    )

    aktuelle_pflanze = cursor.fetchone()

    cursor.close()
    connection.close()
    if not eintraege:
        await interaction.followup.send(
            "📭 Noch keine Phasendaten vorhanden.",
            ephemeral=True
        )
        return

    text = "## ⏱️ Phasendauer\n\n"

    for index, eintrag in enumerate(eintraege):
        alte_phase, neue_phase, geaendert_am = eintrag

        try:
            start = datetime.fromisoformat(geaendert_am)

            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)

            start = start.astimezone(BERLIN_TZ)

            if index + 1 < len(eintraege):
                ende = datetime.fromisoformat(eintraege[index + 1][2])

                if ende.tzinfo is None:
                    ende = ende.replace(tzinfo=timezone.utc)

                ende = ende.astimezone(BERLIN_TZ)
            else:
                ende = datetime.now(BERLIN_TZ)

            dauer = ende - start
            tage = dauer.days
            stunden = dauer.seconds // 3600

            text += (
                f"🌱 **{neue_phase}**\n"
                f"⏱️ {tage} Tage, {stunden} Stunden\n\n"
            )

        except (ValueError, TypeError):
            continue

    await interaction.followup.send(
        text,
        ephemeral=True
    )

@bot.tree.command(
    name="pflanze-erstellen",
    description="Erstellt ein Pflanzenprofil für diesen Growlog."
)
@app_commands.describe(
    name="Name der Pflanze",
    sorte="Sorte / Strain",
    breeder="Breeder",
    keimdatum="Keimdatum, z.B. 11.08.2026",
    phase="Aktuelle Phase",
    medium="Medium, z.B. Erde oder Coco",
    topfgroesse="Topfgröße, z.B. 11 L",
    lampe="Verwendete Lampe",
    genetik_typ="Genetik-Typ, z.B. feminisiert oder regulär",
    anbaumethode="Anbaumethode, z.B. Indoor oder Outdoor",
    lichtzyklus="Lichtzyklus, z.B. 18/6 oder 12/12",
    status="Status der Pflanze, z.B. Aktiv"
)
async def pflanze_erstellen(
    interaction: discord.Interaction,
    name: str,
    sorte: str,
    breeder: str,
    keimdatum: str,
    phase: str,
    medium: str,
    topfgroesse: str,
    lampe: str,
    genetik_typ: str,
    anbaumethode: str,
    lichtzyklus: str,
    status: str
):
    # Nur innerhalb eines Growlog-Threads
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Dieser Befehl funktioniert nur in einem Growlog-Thread.",
            ephemeral=True
        )
        return

    # Prüfen, ob bereits ein Profil existiert
    vorhandene_pflanze = lade_pflanze(interaction.channel.id)

    if vorhandene_pflanze:
        await interaction.response.send_message(
            "⚠️ Für diesen Growlog existiert bereits ein Pflanzenprofil.",
            ephemeral=True
        )
        return

    # Profil in der Datenbank speichern
    speichere_pflanze(
        interaction.channel.parent_id,
        interaction.channel.id,
        name,
        sorte,
        breeder,
        keimdatum,
        phase,
        medium,
        topfgroesse,
        lampe,
        interaction.user.id,
        genetik_typ,
        anbaumethode,
        lichtzyklus,
        status
    )

    embed = discord.Embed(
        title=f"🌱 Pflanzenprofil – {name}",
        description="Pflanzenprofil erfolgreich erstellt."
    )

    embed.add_field(
        name="🧬 Sorte",
        value=sorte,
        inline=True
    )

    embed.add_field(
        name="🏷️ Breeder",
        value=breeder,
        inline=True
    )

    embed.add_field(
        name="📅 Keimdatum",
        value=keimdatum,
        inline=True
    )

    embed.add_field(
        name="🌿 Phase",
        value=phase,
        inline=True
    )

    embed.add_field(
        name="🪴 Medium",
        value=medium,
        inline=True
    )

    embed.add_field(
        name="🪣 Topfgröße",
        value=topfgroesse,
        inline=True
    )

    embed.add_field(
        name="💡 Lampe",
        value=lampe,
        inline=True
    )

    embed.add_field(
        name="🧬 Genetik-Typ",
        value=genetik_typ,
        inline=True
    )

    embed.add_field(
        name="🌱 Anbaumethode",
        value=anbaumethode,
        inline=True
    )

    embed.add_field(
        name="☀️ Lichtzyklus",
        value=lichtzyklus,
        inline=True
    )

    embed.add_field(
        name="📊 Status",
        value=status,
        inline=True
    )

    embed.add_field(
        name="👤 Grower",
        value=interaction.user.mention,
        inline=True
    )

    embed.set_footer(
        text="Black Forest Genetics • GrowBot"
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(
    name="breeder-erstellen",
    description="Erstellt ein neues Black Forest Genetics Breeder-Projekt."
)
@app_commands.describe(
    projektname="Name des Zuchtprojekts",
    mutterpflanze="Mutterpflanze",
    vaterpflanze="Vaterpflanze",
    kreuzung="Kreuzung",
    generation="Generation, z.B. F1, F2 oder BX1",
    samenanzahl="Anzahl der Samen",
    keimrate="Keimrate, z.B. 95 %",
    phaenotypen="Beobachtete Phänotypen",
    selektion="Ausgewählte Pflanzen / Selektion",
    besonderheiten="Besonderheiten oder Notizen"
)
async def breeder_erstellen(
    interaction: discord.Interaction,
    projektname: str,
    mutterpflanze: str,
    vaterpflanze: str,
    kreuzung: str,
    generation: str,
    samenanzahl: int,
    keimrate: str,
    phaenotypen: str,
    selektion: str,
    besonderheiten: str
):
    # Breeder-Projekte werden in einem Thread angelegt
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Dieser Befehl funktioniert nur innerhalb eines Threads.",
            ephemeral=True
        )
        return

    projekt_id = erstelle_breeder_projekt(
        interaction.channel.parent_id,
        interaction.channel.id,
        interaction.user.id,
        projektname,
        mutterpflanze,
        vaterpflanze,
        kreuzung,
        generation,
        samenanzahl,
        keimrate,
        phaenotypen,
        selektion,
        besonderheiten
        )

    embed = discord.Embed(
        title=f"🧬 Breeder-Projekt – {projektname}",
        description=f"Projekt-ID: **{projekt_id}**"
    )

    embed.add_field(
        name="🌱 Mutterpflanze",
        value=mutterpflanze,
        inline=True
    )

    embed.add_field(
        name="🌿 Vaterpflanze",
        value=vaterpflanze,
        inline=True
    )

    embed.add_field(
        name="🧬 Kreuzung",
        value=kreuzung,
        inline=False
    )

    embed.add_field(
        name="🔬 Generation",
        value=generation,
        inline=True
    )

    embed.add_field(
        name="🌰 Samenanzahl",
        value=str(samenanzahl),
        inline=True
    )

    embed.add_field(
        name="📈 Keimrate",
        value=keimrate,
        inline=True
    )

    embed.add_field(
        name="🌱 Phänotypen",
        value=phaenotypen,
        inline=False
    )

    embed.add_field(
        name="🏆 Selektion",
        value=selektion,
        inline=False
    )

    embed.add_field(
        name="📝 Besonderheiten",
        value=besonderheiten,
        inline=False
    )

    embed.add_field(
        name="👤 Breeder",
        value=interaction.user.mention,
        inline=True
    )

    embed.set_footer(
        text="Black Forest Genetics • Breeder Database"
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(
    name="profil-bearbeiten",
    description="Bearbeitet das Pflanzenprofil dieses Growlogs."
)
@app_commands.describe(
    phase="Neue Phase",
    medium="Neues Medium",
    topfgroesse="Neue Topfgröße",
    lampe="Neue Lampe",
    genetik_typ="Neuer Genetik-Typ",
    anbaumethode="Neue Anbaumethode",
    lichtzyklus="Neuer Lichtzyklus",
    status="Neuer Status"
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
    ],
    medium=[
        app_commands.Choice(name="🌱 Erde", value="Erde"),
        app_commands.Choice(name="🥥 Coco", value="Coco"),
        app_commands.Choice(name="💧 Hydro", value="Hydro"),
        app_commands.Choice(name="🧱 Steinwolle", value="Steinwolle"),
        app_commands.Choice(name="🌿 Living Soil", value="Living Soil"),
    ],
    topfgroesse=[
        app_commands.Choice(name="🪣 1 Liter", value="1 Liter"),
        app_commands.Choice(name="🪣 3 Liter", value="3 Liter"),
        app_commands.Choice(name="🪣 5 Liter", value="5 Liter"),
        app_commands.Choice(name="🪣 7 Liter", value="7 Liter"),
        app_commands.Choice(name="🪣 9 Liter", value="9 Liter"),
        app_commands.Choice(name="🪣 11 Liter", value="11 Liter"),
        app_commands.Choice(name="🪣 15 Liter", value="15 Liter"),
        app_commands.Choice(name="🪣 20 Liter", value="20 Liter"),
        app_commands.Choice(name="🪣 25 Liter", value="25 Liter"),
        app_commands.Choice(name="🪣 30 Liter", value="30 Liter"),
        app_commands.Choice(name="🪣 1 US Gallone", value="1 US Gallone"),
        app_commands.Choice(name="🪣 2 US Gallonen", value="2 US Gallonen"),
        app_commands.Choice(name="🪣 3 US Gallonen", value="3 US Gallonen"),
        app_commands.Choice(name="🪣 5 US Gallonen", value="5 US Gallonen"),
        app_commands.Choice(name="🪣 7 US Gallonen", value="7 US Gallonen"),
        app_commands.Choice(name="🪣 10 US Gallonen", value="10 US Gallonen"),
        app_commands.Choice(name="🪣 15 US Gallonen", value="15 US Gallonen"),
        app_commands.Choice(name="🪣 20 US Gallonen", value="20 US Gallonen"),
    ],
    lampe=[
        app_commands.Choice(name="💡 LED 50 W", value="LED 50 W"),
        app_commands.Choice(name="💡 LED 100 W", value="LED 100 W"),
        app_commands.Choice(name="💡 LED 150 W", value="LED 150 W"),
        app_commands.Choice(name="💡 LED 200 W", value="LED 200 W"),
        app_commands.Choice(name="💡 LED 240 W", value="LED 240 W"),
        app_commands.Choice(name="💡 LED 300 W", value="LED 300 W"),
        app_commands.Choice(name="💡 LED 400 W", value="LED 400 W"),
        app_commands.Choice(name="💡 LED 480 W", value="LED 480 W"),
        app_commands.Choice(name="💡 LED 600 W", value="LED 600 W"),
        app_commands.Choice(name="💡 LED 720 W", value="LED 720 W"),
    ],
    anbaumethode=[
        app_commands.Choice(name="🏠 Indoor", value="Indoor"),
        app_commands.Choice(name="🌳 Outdoor", value="Outdoor"),
        app_commands.Choice(name="🏡 Gewächshaus", value="Gewächshaus"),
    ],
    genetik_typ=[
        app_commands.Choice(name="🧬 Regulär", value="Regulär"),
        app_commands.Choice(name="♀️ Feminisiert", value="Feminisiert"),
        app_commands.Choice(name="⚡ Autoflower", value="Autoflower"),
    ],
    lichtzyklus=[
        app_commands.Choice(name="☀️ 18/6", value="18/6"),
        app_commands.Choice(name="🌤️ 20/4", value="20/4"),
        app_commands.Choice(name="💡 24/0", value="24/0"),
        app_commands.Choice(name="🌙 12/12", value="12/12"),
    ],
    status=[
        app_commands.Choice(name="Aktiv", value="Aktiv"),
        app_commands.Choice(name="Pausiert", value="Pausiert"),
        app_commands.Choice(name="Abgeschlossen", value="Abgeschlossen")
    ]
)
async def profil_bearbeiten(
    interaction: discord.Interaction,
    phase: str = None,
    medium: str = None,
    topfgroesse: str = None,
    lampe: str = None,
    genetik_typ: str = None,
    anbaumethode: str = None,
    lichtzyklus: str = None,
    status: str = None
):
    # Nur innerhalb eines Growlog-Threads
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "❌ Dieser Befehl funktioniert nur in einem Growlog-Thread.",
            ephemeral=True
        )
        return
    # Vorhandenes Pflanzenprofil laden
    pflanze = lade_pflanze(interaction.channel.id)

    if not pflanze:
        await interaction.response.send_message(
            "❌ Für diesen Growlog wurde noch kein Pflanzenprofil gespeichert.",
            ephemeral=True
        )
        return

    (
    name,
    sorte,
    breeder,
    keimdatum,
    alte_phase,
    altes_medium,
    alte_topfgroesse,
    alte_lampe,
    grower_id,
    alter_genetik_typ,
    alte_anbaumethode,
    alter_lichtzyklus,
    alter_status
) = pflanze

    # Nicht angegebene Werte bleiben unverändert
    neue_phase = phase if phase is not None else alte_phase
    neues_medium = medium if medium is not None else altes_medium
    neue_topfgroesse = (
        topfgroesse if topfgroesse is not None else alte_topfgroesse
    )
    neue_lampe = lampe if lampe is not None else alte_lampe

    neuer_genetik_typ = (
        genetik_typ if genetik_typ is not None else alter_genetik_typ
    )
    neue_anbaumethode = (
        anbaumethode if anbaumethode is not None else alte_anbaumethode
    )
    neuer_lichtzyklus = (
        lichtzyklus if lichtzyklus is not None else alter_lichtzyklus
    )
    neuer_status = (
        status if status is not None else alter_status
    )
    #Phasenänderung zusätzlich in der Phasenhistorie speichern
    if phase is not None and phase != alte_phase:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO phase_history (
                discord_thread_id,
                grower_id,
                alte_phase,
                neue_phase,
                geaendert_am
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                interaction.channel.id,
                interaction.user.id,
                alte_phase,
                phase,
                datetime.now(BERLIN_TZ).isoformat()
            )
        )

        connection.commit()
        connection.close()
    # Änderungen speichern
    aktualisiere_pflanze(
        interaction.channel.id,
        neue_phase,
        neues_medium,
        neue_topfgroesse,
        neue_lampe,
        neuer_genetik_typ,
        neue_anbaumethode,
        neuer_lichtzyklus,
        neuer_status
    )

    embed = discord.Embed(
        title=f"✅ Pflanzenprofil aktualisiert – {name}",
        description="Die Änderungen wurden erfolgreich gespeichert."
    )

    embed.add_field(
        name="🌿 Phase",
        value=neue_phase or "–",
        inline=True
    )

    embed.add_field(
        name="🪴 Medium",
        value=neues_medium or "–",
        inline=True
    )

    embed.add_field(
        name="🪣 Topfgröße",
        value=neue_topfgroesse or "–",
        inline=True
    )

    embed.add_field(
        name="💡 Lampe",
        value=neue_lampe or "–",
        inline=True
    )

    embed.add_field(
        name="🧬 Genetik-Typ",
        value=neuer_genetik_typ or "-",
        inline=True
    )

    embed.add_field(
        name="🌱 Anbaumethode",
        value=neue_anbaumethode or "-",
        inline=True
    )

    embed.add_field(
        name="☀️ Lichtzyklus",
        value=neuer_lichtzyklus or "-",
        inline=True
    )

    embed.add_field(
        name="📊 Status",
        value=neuer_status or "-",
        inline=True
    )

    embed.set_footer(
        text="Black Forest Genetics • GrowBot"
    )

    await interaction.response.send_message(embed=embed)
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN fehlt in den Render-Umgebungsvariablen."
    )

threading.Thread(
    target=run_webserver,
    daemon=True
).start()

#init_phase_history()


init_db()
init_photos()

bot.run(TOKEN)
