import os
import discord
import requests, requests_cache
from discord.ext import commands
from mojang import API as mAPI
from database import VerificationDatabase
from dotenv import load_dotenv


# настройки
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
mojangAPI = mAPI()
db = VerificationDatabase()
load_dotenv()

hypixel_token = os.getenv("hypixel_token")
guild_id = os.getenv("guild_id")
jr_guild_id = os.getenv("jr_guild_id")

guild_link = f"https://api.hypixel.net/v2/guild?key={hypixel_token}&id={guild_id}"
jr_guild_link = f"https://api.hypixel.net/v2/guild?key={hypixel_token}&id={jr_guild_id}"
player_link = f"https://api.hypixel.net/v2/player?key={hypixel_token}&uuid="

requests_cache.install_cache('hypixel_mojang_cache', expire_after=1800, ignored_headers=['Authorization']) # кэш запросов, время хранения 30 минут

# при запуске
@bot.event
async def on_ready():
    global ROLES
    print(f'{bot.user} подключился!')
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} слэш-команд")
        guild = bot.get_guild(1351978546192580670)
        ROLES = {
            "No Life": guild.get_role(1355634862807060611),
            "Professional": guild.get_role(1355634865902718977),
            "Skilled": guild.get_role(1355634868528087233),
            "guildmate": guild.get_role(1351997307935002807),
            "jrGuildmate": guild.get_role(1358151345260990646),
            "guest": guild.get_role(1351997564345651321),
            "notVerified": guild.get_role(1356293958073979172)
        }
    except Exception as e:
        print(f"Ошибка синхронизации: {e}")


# основная команда верификации
@bot.tree.command(name="verify", description="Пройти верификацию на сервере")
async def verify(interaction: discord.Interaction, nickname: str):
    await interaction.response.defer(ephemeral=True)
    noLife = ROLES["No Life"]
    professional = ROLES["Professional"]
    skilled = ROLES["Skilled"]
    guildmate = ROLES["guildmate"]
    jrGuildmate = ROLES["jrGuildmate"]
    guest = ROLES["guest"]
    notVerified = ROLES["notVerified"]
    try:
        uuid = mojangAPI.get_uuid(username=nickname) # uuid игрока из mojangAPI
        inGameNickname = mojangAPI.get_username(uuid=uuid) # ник игрока из mojangAPI
        player = requests.get(player_link + uuid).json() # массив данных из HypixelAPI
        discord_tag = player.get("player", {}).get("socialMedia", {}).get("links", {}).get("DISCORD") # дискорд-тег игрока из массива данных
        
        if discord_tag == interaction.user.name:
            guild_data = requests.get(guild_link).json()
            jr_data = requests.get(jr_guild_link).json()
            
            main = {m["uuid"]: m["rank"] for m in guild_data.get("guild", {}).get("members", [])} # участники основной гильдии
            jr = {m["uuid"]: m["rank"] for m in jr_data.get("guild", {}).get("members", [])} # участники младшей гильдии
            
            roles_to_add = guest
            roles_to_remove = notVerified
            rank = "guest"

            if uuid in main: # если в основной гильдии
                rank = main[uuid]
                roles_to_add = [guildmate, ROLES[rank]]
                roles_to_remove = [notVerified, jrGuildmate]
                
            elif uuid in jr: # если в младшей
                rank = jr[uuid]
                roles_to_add = [ROLES["jrGuildmate"]]
                roles_to_remove = [notVerified, guildmate, noLife, professional, skilled]
            
            if not db.get(interaction.user.id): # добавление записи
                db.add(interaction.user.id, uuid, inGameNickname, rank)
            else: # обновление записи
                db.update(interaction.user.id, uuid, inGameNickname, rank)

            await interaction.user.add_roles(*roles_to_add)
            await interaction.user.remove_roles(*roles_to_remove)
            await interaction.followup.send(f"Добро пожаловать, {inGameNickname}!", ephemeral=True)
            await interaction.user.edit(nick=inGameNickname)
        else:
            await interaction.followup.send("Discord не привязан или неверен!", ephemeral=True)
    except Exception as e:
        print(e)





bot.run(token=os.getenv('discord_token'))
