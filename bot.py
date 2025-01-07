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
