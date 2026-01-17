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
ROLES = {}
MOD_ROLE_ID = 1355020383350296596


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
            
            # Обновление ника
            api_username = mojangAPI.get_username(uuid)
            if api_username != data['ign']:
                db.update(discord_id, ign=api_username)
                updated_db += 1
            
            guild_rank_raw = {
                'main': main.get(uuid, 'guest'),
                'jr': jr.get(uuid, 'guest')
            }.get(data['guild_type'], 'guest')
            
            if str(guild_rank_raw).lower() in ['Guild Master', 'STAFF', 'Member']:
                guild_rank = 'guildmate' if data['guild_type'] == 'main' else 'jrGuildmate'
            else:
                guild_rank = guild_rank_raw
            
            if guild_rank != data['rank']:
                db.update(discord_id, rank=guild_rank)
                updated_db += 1
            

            user = members_cache.get(discord_id)
            if user:
                jrRanks = ["jrGuildmate", "Newbie"]
                current_rank = guild_rank if guild_rank != data['rank'] else data['rank']
                
                if current_rank == "No Life":
                    roles_to_add = [ROLES["No Life"], ROLES["guildmate"]]
                    roles_to_remove = [ROLES["Skilled"], ROLES["Professional"], ROLES["guest"], ROLES["jrGuildmate"]]
                elif current_rank == "Professional":
                    roles_to_add = [ROLES["Professional"], ROLES["guildmate"]]
                    roles_to_remove = [ROLES["Skilled"], ROLES["No Life"], ROLES["guest"], ROLES["jrGuildmate"]]
                elif current_rank == "Skilled":
                    roles_to_add = [ROLES["Skilled"], ROLES["guildmate"]]
                    roles_to_remove = [ROLES["No Life"], ROLES["Professional"], ROLES["guest"], ROLES["jrGuildmate"]]
                elif current_rank == "guildmate":
                    roles_to_add = [ROLES["guildmate"]]
                    roles_to_remove = [ROLES["No Life"], ROLES["Professional"], ROLES["Skilled"], 
                                     ROLES["guest"], ROLES["jrGuildmate"]]
                elif current_rank in jrRanks:
                    roles_to_add = [ROLES["jrGuildmate"]]
                    roles_to_remove = [ROLES["No Life"], ROLES["Professional"], ROLES["Skilled"], 
                                     ROLES["guildmate"], ROLES["guest"]]
                else:
                    roles_to_add = [ROLES["guest"]]
                    roles_to_remove = [ROLES["No Life"], ROLES["Professional"], ROLES["Skilled"], 
                                     ROLES["guildmate"], ROLES["jrGuildmate"]]
                
                # Применяем роли
                for role in roles_to_remove:
                    if role and role in user.roles:
                        await user.remove_roles(role)
                for role in roles_to_add:
                    if role and role not in user.roles:
                        await user.add_roles(role)
                
                roles_updated += 1

        return f"Обновлено: БД={updated_db}, Роли={roles_updated}"
    except Exception as e:
        print(f"Ошибка update_logic: {e}")
        return f"Ошибка: {e}"


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
    
    try:
        uuid = mojangAPI.get_uuid(username=nickname)
        inGameNickname = mojangAPI.get_username(uuid=uuid)
        player = requests.get(player_link + uuid).json()
        discord_tag = player.get("player", {}).get("socialMedia", {}).get("links", {}).get("DISCORD")
        
        if discord_tag == interaction.user.name:
            guild_data = requests.get(guild_link).json()
            jr_data = requests.get(jr_guild_link).json()
            main = {m["uuid"]: m["rank"] for m in guild_data.get("guild", {}).get("members", [])}
            jr = {m["uuid"]: m["rank"] for m in jr_data.get("guild", {}).get("members", [])}
            

            guild_type = "guest"
            rank = "guest"
            roles_to_add = [ROLES["guest"]]
            roles_to_remove = [ROLES["notVerified"]]
            
            if uuid in main:
                guild_type = "main"
                guild_rank_raw = main[uuid]
                if guild_rank_raw in ['Guild Master', 'STAFF', 'Member']:
                    rank = 'guildmate'
                else:
                    rank = guild_rank_raw
                roles_to_add = [ROLES["guildmate"], ROLES[rank]]
                roles_to_remove = [ROLES["notVerified"], ROLES["jrGuildmate"]]
                
            elif uuid in jr:
                guild_type = "jr"
                guild_rank_raw = jr[uuid]
                if guild_rank_raw in ['Guild Master', 'STAFF', 'Member']:
                    rank = 'jrGuildmate'
                else:
                    rank = guild_rank_raw
                roles_to_add = [ROLES["jrGuildmate"]]
                roles_to_remove = [ROLES["notVerified"], ROLES["guildmate"], ROLES["No Life"], ROLES["Professional"], ROLES["Skilled"],]

            
            if not db.get(interaction.user.id):
                db.add(discord_id=interaction.user.id, uuid=uuid, ign=inGameNickname, 
                      rank=rank, guild_type=guild_type)
            else:
                db.update(discord_id=interaction.user.id, uuid=uuid, ign=inGameNickname, 
                         rank=rank, guild_type=guild_type)
            
            # Применяем роли
            await interaction.user.remove_roles(*roles_to_remove)
            await interaction.user.add_roles(*roles_to_add)
            
            await interaction.followup.send(f"Добро пожаловать, **{inGameNickname}**!\nРанг: `{rank}`", 
                                         ephemeral=True)
            await interaction.user.edit(nick=inGameNickname)
        else:
            await interaction.followup.send("Discord не привязан или неверный ник!", ephemeral=True)
            
    except Exception as e:
        print(f"Ошибка verify: {e}")



@bot.tree.command(name="update", description="Обновить всех привязанных участников")
async def update(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    mod_role = interaction.guild.get_role(MOD_ROLE_ID)
    if mod_role not in interaction.user.roles:
        await interaction.followup.send("Нет прав!", ephemeral=True)
        return
    
    try:
        updated = await update_logic()  # Обновляет ВСЕХ пользователей
        await interaction.followup.send(f"Все пользователи обновлены!\n{updated}", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"Ошибка: {e}", ephemeral=True)
        print(f"Ошибка команды update: {e}")


@bot.tree.command(name="stats", description="Показать статистику верифицированных игроков")
async def stats(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    mod_role = interaction.guild.get_role(MOD_ROLE_ID)
    if mod_role not in interaction.user.roles:
       await interaction.followup.send("Нет прав!", ephemeral=False)
       return
    
    verified = db.get_all()
    stats = {}
    
    for data in verified.values():
        rank = data['rank']
        if data['guild_type'] == 'jr':    
            if rank in ["jrGuildmate", "Newbie"]:
                rank = "jrGuildmate"
        if data['guild_type'] == 'main':  
            if rank not in ["No Life", "Professional", "Skilled"]:
                rank = "guildmate"
        stats[rank] = stats.get(rank, 0) + 1
    
    embed = discord.Embed(
        title="📊 Статистика гильдии",
        description=f"**Всего верифицировано: {len(verified)} игроков**",
        color=0x00ff88  # Зеленый
    )
    
    embed.add_field(
        name="👑 No Life", 
        value=f"{stats.get('No Life', 0)}", 
        inline=True
    )
    embed.add_field(
        name="⭐ Professional", 
        value=f"{stats.get('Professional', 0)}", 
        inline=True
    )
    embed.add_field(
        name="⚡ Skilled", 
        value=f"{stats.get('Skilled', 0)}", 
        inline=True
    )
    embed.add_field(
        name="🛡️ Guildmate", 
        value=f"{stats.get('guildmate', 0)}", 
        inline=True
    )
    embed.add_field(
        name="👶 Jr Guildmate", 
        value=f"{stats.get('jrGuildmate', 0)}", 
        inline=True
    )
    embed.add_field(
        name="🧑 Guest", 
        value=f"{stats.get('guest', 0)}", 
        inline=True
    )
    
    embed.set_footer(
        text=f"Последнее обновление: {discord.utils.utcnow().strftime('%d.%m.%Y %H:%M')}",
        icon_url=interaction.user.display_avatar.url
    )
    
    # Миниатюра сервера
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    
    await interaction.followup.send(embed=embed, ephemeral=False)



bot.run(token=os.getenv('discord_token'))
