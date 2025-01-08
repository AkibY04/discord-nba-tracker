import os
import asyncio
import json
from dotenv import load_dotenv
from discord import Intents, Embed, Interaction
from discord.ext import commands, tasks
from nba_api.live.nba.endpoints import scoreboard


#Load bot token
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

#Intents and bot setup
intents = Intents.default()
intents.message_content = True  

bot = commands.Bot(command_prefix="!", intents=intents)

from typing import Literal, Optional

import discord
from discord.ext import commands

@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()

        await ctx.send(
            f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return

    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

tracked_games = {}  
update_channels = {}  

#Team emojis 
team_emojis = {
    "Hawks": "<:hawks:1326239058157895731>",  
    "Celtics": "<:celtics:1326239095047061524>",  
    "Nets": "<:nets:1326238935214719026>",  
    "Hornets": "<:hornets:1326239015271268402>",  
    "Bulls": "<:bulls:1326239097580163173>",  
    "Cavaliers": "<:cavaliers:1326239096326062080>",  
    "Mavericks": "<:mavericks:1326238936087138334>", 
    "Nuggets": "<:nuggets:1326238898011111598>",  
    "Pistons": "<:pistons:1325999283543081050>",  
    "Warriors": "<:warriors:1326238764946686045>",  
    "Rockets": "<:rockets:1326238857976352778>",  
    "Pacers": "<:pacers:1326238897046425661>",  
    "Clippers": "<:clippers:1326239060183748678>",  
    "Lakers": "<:lakers:1326238975219863622>", 
    "Grizzlies": "<:grizzlies:1326239059185635393>", 
    "Heat": "<:heat:1326239016642809866>", 
    "Bucks": "<:bucks:1326239122938920970>",  
    "Timberwolves": "<:timberwolves:1326238801286266922>",  
    "Pelicans": "<:pelicans:1326238895662305373>",  
    "Knicks": "<:knicks:1326238976251789456>", 
    "Thunder": "<:thunder:1326238802192240711>", 
    "Magic": "<:magic:1326238937299157042>",  
    "76ers": "<:76ers:1326239123643826277>",  
    "Suns": "<:suns:1326238803215781959>", 
    "Trail Blazers": "<:trailblazers:1325998001893933117>",  
    "Kings": "<:kings:1326238977673531462>",  
    "Spurs": "<:spurs:1326238856944550021>",  
    "Raptors": "<:raptors:1326238859133976596>",  
    "Jazz": "<:jazz:1326239013719244831>",  
    "Wizards": "<:wizards:1326238764464476250>",  
}

SAVED_CHANNELS = "channels.json"
#Updating channel dict with channels.json data
def load_update_channels():
    global update_channels
    try:
        with open(SAVED_CHANNELS, "r") as file:
            update_channels = json.load(file)
    except FileNotFoundError:
        update_channels = {}
    except json.JSONDecodeError:
        print("Error: channels.json is corrupted. Starting with empty update channels.")
        update_channels = {}

def save_update_channels():
    with open(SAVED_CHANNELS, "w") as file:
        json.dump(update_channels, file, indent=4)

def get_live_games():
    scoreboard_data = scoreboard.ScoreBoard()
    games = scoreboard_data.games.get_dict()

    ongoing_games = []
    for game in games:
        status = game['gameStatusText']

        if "Q" in status or "OT" in status or "Half" in status:
            game_state = "In Progress"
            ongoing_games.append({
                'home_team': game['homeTeam']['teamName'],
                'home_score': game['homeTeam']['score'],
                'away_team': game['awayTeam']['teamName'],
                'away_score': game['awayTeam']['score'],
                'status': status,
                'state': game_state, 
            })
    return ongoing_games

def get_scheduled_games():
    scoreboard_data = scoreboard.ScoreBoard()
    games = scoreboard_data.games.get_dict()

    scheduled_games = []
    for game in games:
        status = game['gameStatusText']
        scheduled_games.append({
                'home_team': game['homeTeam']['teamName'],
                'home_score': game['homeTeam']['score'],
                'away_team': game['awayTeam']['teamName'],
                'away_score': game['awayTeam']['score'],
                'status': status,
        })

    return scheduled_games


def create_embed(game, index, total):
    home_team_emoji = team_emojis.get(game['home_team'], "")
    away_team_emoji = team_emojis.get(game['away_team'], "")
    
    home_team_name = f"{home_team_emoji} {game['home_team']}"
    away_team_name = f"{away_team_emoji} {game['away_team']}"

    embed = Embed(
        title="🏀 Live NBA Game 🏀",
        description=f"{home_team_name} ({game['home_score']}) vs. {away_team_name} ({game['away_score']})",
        color=0x1D428A
    )
    embed.add_field(name="Status", value=game['status'], inline=False)
    embed.set_footer(text=f"Game {index + 1} of {total}")
    return embed

@bot.event
async def on_ready():
    global update_channels, tracked_games
    print("🏀 NBA Tracker Bot is online!")
    
    # Initialize tracked_games with live games
    tracked_games = {}
    ongoing_games = get_live_games()
    for game in ongoing_games:
        game_key = f"{game['home_team']} vs. {game['away_team']}"
        tracked_games[game_key] = game  # Track current games
    
    # Start the loop after initialization
    load_update_channels()
    check_games.start()

@bot.tree.command(name="live", description="Get live NBA games")
async def live(interaction: Interaction):
    ongoing_games = get_live_games()
    if not ongoing_games:
        await interaction.response.send_message("No games are live right now", ephemeral=True)
        return

    current_page = 0
    total_games = len(ongoing_games)

    embed = create_embed(ongoing_games[current_page], current_page, total_games)
    await interaction.response.send_message(embed=embed)

    sent_message = await interaction.original_response()

    if total_games > 1:
        await sent_message.add_reaction("⬅️")
        await sent_message.add_reaction("➡️")

    def check(reaction, user):
        return (
            user == interaction.user
            and reaction.message.id == sent_message.id
            and str(reaction.emoji) in ["⬅️", "➡️"]
        )

    while True:
        try:
            ongoing_games = get_live_games()

            reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)

            if str(reaction.emoji) == "⬅️":
                current_page = (current_page - 1) % total_games
            elif str(reaction.emoji) == "➡️":
                current_page = (current_page + 1) % total_games

            embed = create_embed(ongoing_games[current_page], current_page, total_games)
            await sent_message.edit(embed=embed)

            await sent_message.remove_reaction(reaction.emoji, user)

        except asyncio.TimeoutError:
            break

@bot.tree.command(name="scheduled", description="Get all scheduled NBA games for today")
async def live(interaction: Interaction):
    ongoing_games = get_scheduled_games()
    if not ongoing_games:
        await interaction.response.send_message("No games are live right now", ephemeral=True)
        return

    current_page = 0
    total_games = len(ongoing_games)

    embed = create_embed(ongoing_games[current_page], current_page, total_games)
    await interaction.response.send_message(embed=embed)

    sent_message = await interaction.original_response()

    if total_games > 1:
        await sent_message.add_reaction("⬅️")
        await sent_message.add_reaction("➡️")

    def check(reaction, user):
        return (
            user == interaction.user
            and reaction.message.id == sent_message.id
            and str(reaction.emoji) in ["⬅️", "➡️"]
        )

    while True:
        try:
            ongoing_games = get_scheduled_games()

            reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)

            if str(reaction.emoji) == "⬅️":
                current_page = (current_page - 1) % total_games
            elif str(reaction.emoji) == "➡️":
                current_page = (current_page + 1) % total_games

            embed = create_embed(ongoing_games[current_page], current_page, total_games)
            await sent_message.edit(embed=embed)

            await sent_message.remove_reaction(reaction.emoji, user)

        except asyncio.TimeoutError:
            break

@bot.tree.command(name="set-update-channel", description="Set the channel for automatic game start/end updates.")
async def set_update_channel(interaction: Interaction, channel_id: str):
    guild = interaction.guild
    if any(char.isalpha() for char in channel_id):
        await interaction.response.send_message(
            "The provided channel ID does not exist in this server. Please check and try again.",
            ephemeral=True
        )
        return
    
    channel = guild.get_channel(int(channel_id))

    if channel is None:
        #Return an error if the channel does not exist or is not in the guild
        await interaction.response.send_message(
            "The provided channel ID does not exist in this server. Please check and try again.",
            ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    update_channels[guild_id] = int(channel_id)
    save_update_channels()  # Save changes to the file
    await interaction.response.send_message(
        f"Update channel successfully set to <#{channel_id}>.",
        ephemeral=True
    )

@bot.tree.command(name="view-update-channel", description="View the current channel for automatic game start/end updates.")
async def view_update_channel(interaction: Interaction):
    guild_id = str(interaction.guild.id)
    await interaction.response.send_message(f"Update channel is currently set to <#{update_channels[guild_id]}>", ephemeral=True)

@tasks.loop(minutes=1)
async def check_games():
    global update_channels, tracked_games
    ongoing_games = get_live_games()
    
    print(update_channels)
    
    #Loop through each guild and channel
    for guild_id, channel_id in update_channels.items():
        guild = bot.get_guild(int(guild_id))
        print(f"Processing guild_id: {guild_id}, Guild: {guild}")
        
        if guild:
            channel = guild.get_channel(channel_id)
            print(f"Guild: {guild.name}, Channel ID: {channel_id}, Channel: {channel}")
            
            if not channel:
                print(f"Channel ID {channel_id} not found in {guild.name}")
                continue  #Skip if the channel doesn't exist
            
            #Ensure the guild has its own tracked games dictionary
            if guild_id not in tracked_games:
                tracked_games[guild_id] = {}

            #Only send a message if it's a new game
            for game in ongoing_games:
                game_key = f"{game['home_team']} vs. {game['away_team']}"
                
                #Check if this game is new for this guild
                if game_key not in tracked_games[guild_id]:
                    print(f"New game started in {guild.name}: {game_key}")
                    tracked_games[guild_id][game_key] = game  # Add to tracked games for this guild
                    
                    home_team_score = game['home_score']
                    away_team_score = game['away_score']
                    home_team_emoji = team_emojis.get(game['home_team'], "")
                    away_team_emoji = team_emojis.get(game['away_team'], "")
                
                    await channel.send(f"🏀 **Game In Progress:** {home_team_emoji} {game['home_team']} ({home_team_score}) vs {away_team_emoji} {game['away_team']} ({away_team_score})")

            #Check for games that ended in this guild
            ended_games = [
                game_key for game_key, tracked_game in tracked_games[guild_id].items()
                if game_key not in [f"{game['home_team']} vs. {game['away_team']}" for game in ongoing_games]
                and tracked_game.get('state') != "Halftime"
            ]
            for game_key in ended_games:
                print(f"Game ended in {guild.name}: {game_key}")
                #Retrieve the final score for the game
                final_score = tracked_games[guild_id][game_key]
                home_team_score = final_score['home_score']
                away_team_score = final_score['away_score']
                home_team_emoji = team_emojis.get(final_score['home_team'], "")
                away_team_emoji = team_emojis.get(final_score['away_team'], "")
            
                await channel.send(f"🏀 **Game Ended:** {home_team_emoji} {final_score['home_team']} ({home_team_score}) vs. {away_team_emoji} {final_score['away_team']} ({away_team_score})")
                
                #Remove the game from tracked games
                del tracked_games[guild_id][game_key]
            
            print("\n")

bot.run(TOKEN)
