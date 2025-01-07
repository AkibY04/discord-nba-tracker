import os
import asyncio
from dotenv import load_dotenv
from discord import Intents, Embed, Interaction
from discord.ext import commands, tasks
from nba_api.live.nba.endpoints import scoreboard

#Load bot token
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

#Intents and bot setup
intents = Intents.default()
intents.message_content = True  # Enable message content intent

bot = commands.Bot(command_prefix="!", intents=intents)

tracked_games = {}  
update_channels = {}  
#Team emojis with proper emoji format
team_emojis = {
    "Hawks": "🦅",  
    "Celtics": "☘️",  
    "Nets": "🏀",  
    "Hornets": "🐝",  
    "Bulls": "🐂",  
    "Cavaliers": "🦸",  
    "Mavericks": "🤠", 
    "Nuggets": "⛏️",  
    "Pistons": "<:pistons:1325999283543081050>",  
    "Warriors": "⚔️",  
    "Rockets": "🚀",  
    "Pacers": "🏁",  
    "Clippers": "✂️",  
    "Lakers": "🦄", 
    "Grizzlies": "🐻", 
    "Heat": "🔥", 
    "Bucks": "🦌",  
    "Timberwolves": "🐺",  
    "Pelicans": "🦩",  
    "Knicks": "🗽", 
    "Thunder": "⚡", 
    "Magic": "✨",  
    "76ers": "🔴",  
    "Suns": "🌞", 
    "Trail Blazers": "<:trailblazers:1325998001893933117>",  
    "Kings": "👑",  
    "Spurs": "⚽",  
    "Raptors": "🦖",  
    "Jazz": "🎷",  
    "Wizards": "🧙‍♂️",  
}

def get_live_games():
    scoreboard_data = scoreboard.ScoreBoard()
    games = scoreboard_data.games.get_dict()  

    ongoing_games = []
    for game in games:
        status = game['gameStatusText']
        if "Q" in status or "OT" in status: 
            ongoing_games.append({
                'home_team': game['homeTeam']['teamName'],
                'home_score': game['homeTeam']['score'],
                'away_team': game['awayTeam']['teamName'],
                'away_score': game['awayTeam']['score'],
                'status': status
            })
    return ongoing_games

def create_embed(game, index, total):
    home_team_emoji = team_emojis.get(game['home_team'], "")
    away_team_emoji = team_emojis.get(game['away_team'], "")
    
    home_team_name = f"{home_team_emoji} {game['home_team']}"
    away_team_name = f"{away_team_emoji} {game['away_team']}"

    embed = Embed(
        title="🏀 Live NBA Game 🏀",
        description=f"{home_team_name} ({game['home_score']}) vs {away_team_name} ({game['away_score']})",
        color=0x1D428A
    )
    embed.add_field(name="Status", value=game['status'], inline=False)
    embed.set_footer(text=f"Game {index + 1} of {total}")
    return embed

@bot.event
async def on_ready():
    print(f"🏀 NBA Tracker Bot is online as {bot.user}! 🎉")
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()  #Register all commands globally

    #Start the periodic game check task when the bot is ready
    check_games.start()

@bot.tree.command(name="live", description="Get live NBA games")
async def live(interaction: Interaction):
    """
    Slash command to fetch live NBA games.
    """
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

@bot.tree.command(name="setupdatechannel", description="Set the channel for automatic game start/end updates.")
async def set_update_channel(interaction: Interaction, channel_id: str):
    guild_id = str(interaction.guild.id)
    update_channels[guild_id] = int(channel_id)
    await interaction.response.send_message(f"Update channel set to <#{channel_id}>", ephemeral=True)

@tasks.loop(minutes=1)
async def check_games():
    global update_channels, tracked_games
    ongoing_games = get_live_games()

    for guild_id, channel_id in update_channels.items():
        guild = bot.get_guild(int(guild_id))
        if guild:
            channel = guild.get_channel(channel_id)
            if not channel:
                continue  #Skip if channel doesn't exist

            for game in ongoing_games:
                game_key = f"{game['home_team']} vs {game['away_team']}"
                
                #Check if this game has not been tracked yet (start message)
                if game_key not in tracked_games:
                    tracked_games[game_key] = game
                    await channel.send(f"🏀 **Game Started:** {game['home_team']} vs {game['away_team']} ({game['status']})")
                
            ended_games = [game_key for game_key in tracked_games if game_key not in [f"{game['home_team']} vs {game['away_team']}" for game in ongoing_games]]
            for game_key in ended_games:
                #Send the game ended message only once
                await channel.send(f"🏀 **Game Ended:** {game_key}")
                del tracked_games[game_key] 


# Run the bot
bot.run(TOKEN)
