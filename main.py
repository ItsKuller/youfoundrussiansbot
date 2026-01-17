import os
import asyncio
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
members_cache = {}
guild = discord.Guild
ROLES = {}


async def update_logic():
    try:
        guild_data = requests.get(guild_link).json()
        jr_data = requests.get(jr_guild_link).json()
        main = {m["uuid"]: m["rank"] for m in guild_data.get("guild", {}).get("members", [])}
        jr = {m["uuid"]: m["rank"] for m in jr_data.get("guild", {}).get("members", [])}

        updated_db = 0
        roles_updated = 0

        for discord_id, data in db.get_all().items():
            uuid = data['uuid']
            
            api_username = mojangAPI.get_username(uuid)
            if api_username != data['ign']:
                db.update(discord_id, ign=api_username)
                updated_db += 1
            
            guild_rank = {
                'main': main.get(uuid, 'guest'),
                'jr': jr.get(uuid, 'guest')
            }.get(data['guild_type'], 'guest')
            
            if guild_rank != data['rank']:
                db.update(discord_id, rank=guild_rank)
                updated_db += 1
            
            user = members_cache.get(discord_id)
            if user:
                current_rank = guild_rank if guild_rank != data['rank'] else data['rank']
                
                # Логика ролей
                if current_rank == "No Life":
                    roles_to_add = [ROLES["No Life"], ROLES["guildmate"]]
                    roles_to_remove = [ROLES["Skilled"], ROLES["Professional"], ROLES["guest"]]
                elif current_rank == "Professional":
                    roles_to_add = [ROLES["Professional"], ROLES["guildmate"]]
                    roles_to_remove = [ROLES["Skilled"], ROLES["No Life"], ROLES["guest"]]
                elif current_rank == "Skilled":
                    roles_to_add = [ROLES["Skilled"], ROLES["guildmate"]]
                    roles_to_remove = [ROLES["No Life"], ROLES["Professional"], ROLES["guest"]]
                else:
                    roles_to_add = [ROLES["guest"]]
                    roles_to_remove = [ROLES["No Life"], ROLES["Professional"], ROLES["Skilled"], 
                                     ROLES["guildmate"], ROLES["jrGuildmate"]]
                
                for role in roles_to_remove:
                    if role in user.roles:
                        await user.remove_roles(role)
                
                for role in roles_to_add:
                    if role not in user.roles:
                        await user.add_roles(role)
                
                roles_updated += 1

        updated = (f"Обновлено: БД={updated_db}, Роли: {roles_updated}")

        return updated

    except Exception as e:
        print(f"❌ Ошибка update_logic: {e}")


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
        for member in guild.members:
            members_cache[member.id] = member
        bot.loop.create_task(auto_role_sync())
    except Exception as e:
        print(f"Ошибка синхронизации: {e}")

async def auto_role_sync():
    while True:
        await update_logic()
        await asyncio.sleep(86400)  # 30 минут

@bot.event 
async def on_member_join(member):
    members_cache[member.id] = member

@bot.event 
async def on_member_remove(member):
    members_cache.pop(member.id, None)


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
            
            guild_type = "guest"
            roles_to_add = guest
            roles_to_remove = notVerified
            rank = "guest"

            if uuid in main: # если в основной гильдии
                guild_type = "main"
                rank = main[uuid]
                roles_to_add = [guildmate, ROLES[rank]]
                roles_to_remove = [notVerified, jrGuildmate]
                
            elif uuid in jr: # если в младшей
                guild_type = "jr"
                rank = jr[uuid]
                roles_to_add = [ROLES["jrGuildmate"]]
                roles_to_remove = [notVerified, guildmate, noLife, professional, skilled]
            
            if not db.get(interaction.user.id): # добавление записи
                db.add(discord_id=interaction.user.id, uuid=uuid, ign=inGameNickname, rank=rank, guild_type=guild_type)
            else: # обновление записи
                db.update(discord_id=interaction.user.id, uuid=uuid, ign=inGameNickname, rank=rank, guild_type=guild_type)

            await interaction.user.add_roles(*roles_to_add)
            await interaction.user.remove_roles(*roles_to_remove)
            await interaction.followup.send(f"Добро пожаловать, {inGameNickname}!", ephemeral=True)
            await interaction.user.edit(nick=inGameNickname)
        else:
            await interaction.followup.send("Discord не привязан или неверен!", ephemeral=True)
    except Exception as e:
        print(e)


@bot.tree.command(name="update", description="Обновить всех привязанных участников")
async def update(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        updated = await update_logic()  # Обновляет ВСЕХ пользователей
        await interaction.followup.send(f"Все пользователи обновлены!\n{updated}", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"Ошибка: {e}", ephemeral=True)
        print(f"Ошибка команды update: {e}")


bot.run(token=os.getenv('discord_token'))
