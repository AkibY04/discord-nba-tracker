import asyncio
import os
from dotenv import load_dotenv
from discord import Intents, Client
from discord.ext import tasks
from nba_api.live.nba.endpoints import scoreboard

# Loading bot token
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID')) 
PREFIX = os.getenv('PREFIX')

intents = Intents.default()
intents.message_content = True
client = Client(intents=intents)

tracked_games = {}

def get_live_games():
    scoreboard_data = scoreboard.ScoreBoard()
    games_dict = scoreboard_data.get_dict()  
    games = games_dict['scoreboard']['games'] 

    ongoing_games = []
    for game in games:
        status = game['gameStatusText']
        if "Q" in status or "OT" in status: 
            ongoing_games.append({
                'home_team': game['homeTeam']['teamName'],
                'away_team': game['awayTeam']['teamName'],
                'status': status
            })
    return ongoing_games

@tasks.loop(minutes=1)
async def check_games():
    global tracked_games
    current_games = {game['home_team'] + " vs " + game['away_team']: game for game in get_live_games()}

    channel = client.get_channel(CHANNEL_ID) 

    # Check for new games starting
    for game_key, game in current_games.items():
        if game_key not in tracked_games:
            tracked_games[game_key] = game
            await channel.send(f"🏀 **Game Started:** {game['home_team']} vs {game['away_team']} ({game['status']})")

    # Check for games that ended
    ended_games = [game_key for game_key in tracked_games if game_key not in current_games]
    for game_key in ended_games:
        await channel.send(f"🏀 **Game Ended:** {game_key}")
        del tracked_games[game_key]

#Bot is ready
@client.event
async def on_ready():
    await asyncio.sleep(3)

    channel = client.get_channel(CHANNEL_ID) 

    if channel:
        await channel.send("NBA Tracker Bot is now online!")

    check_games.start() 
# Event: Respond to messages
@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.content.lower() == "hello":
        await message.channel.send("Hello!")

    if message.content.lower() == PREFIX + "live":
        ongoing_games = get_live_games()
        if not ongoing_games:
            await message.channel.send("No games are live right now. 🏀")
        else:
            response = "🏀 **Live Games:**\n"
            for game in ongoing_games:
                response += f"- {game['home_team']} vs {game['away_team']} ({game['status']})\n"
            await message.channel.send(response)

# Run the bot
client.run(TOKEN)
