import os
import threading
import psycopg2

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
    await interaction.response.defer(ephemeral=True)

    connection = get_db_connection()
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
    
    connection.close()

    if not eintraege:
        await interaction.followup.send(
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
    await interaction.followup.send(text, ephemeral=True)




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
        grower_id
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
        name="👤 Grower",
        value=interaction.user.mention,
        inline=True
    )

    embed.set_footer(
        text="Black Forest Genetics • GrowBot"
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

bot.run(TOKEN)
