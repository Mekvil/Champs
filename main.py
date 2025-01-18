import os
import json
import discord
import asyncio
from datetime import datetime, timedelta
from discord import app_commands
from dotenv import load_dotenv
from discord.ext import tasks, commands

# Load environment variables
load_dotenv()

# Configure intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Constants
LEADERBOARD_CHANNEL_ID = change this
QUEUE_CHANNEL_ID = change this
RULES_CHANNEL_ID = change this
RESULTS_CHANNEL_ID = change this
ADMIN_IDS = [setup admins]

def get_rules_message(rules_channel):
    channel_mention = rules_channel.mention if rules_channel else "#правила"
    return f"You must accept the rules in {channel_mention} first!"

# Helper functions
def load_rules_accepted():
    try:
        with open('rules_accepted.json', 'r') as f:
            content = f.read()
            return set(json.loads(content) if content else [])
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_rules_accepted(accepted_users):
    with open('rules_accepted.json', 'w') as f:
        json.dump(list(accepted_users), f)

def load_players():
    try:
        with open('players.json', 'r') as f:
            content = f.read()
            return json.loads(content) if content else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_players(players):
    with open('players.json', 'w') as f:
        json.dump(players, f, indent=4)

def load_match_limits():
    try:
        with open('match_limits.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_reset": datetime.now().strftime("%Y-%m-%d"), "matches": {}, "dodges": {}, "weekly_matches": {}}

def save_match_limits(data):
    with open('match_limits.json', 'w') as f:
        json.dump(data, f, indent=4)

def load_queue_bans():
    try:
        with open('queue_bans.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        bans = {'bans': {}}
        save_queue_bans(bans)
        return bans

def save_queue_bans(data):
    with open('queue_bans.json', 'w') as f:
        json.dump(data, f, indent=4)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def check_weekly_reset():
    limits = load_match_limits()
    
    if not limits.get('last_reset'):
        limits['last_reset'] = datetime.now().strftime("%Y-%m-%d")
        limits['matches'] = {}
        limits['weekly_matches'] = {}
        save_match_limits(limits)
        return
        
    last_reset = datetime.strptime(limits['last_reset'], "%Y-%m-%d")
    current_date = datetime.now()
    
    days_since_reset = (current_date - last_reset).days
    if days_since_reset >= 7:
        limits['matches'] = {}
        limits['weekly_matches'] = {}
        limits['last_reset'] = current_date.strftime("%Y-%m-%d")
        save_match_limits(limits)
        print(f"Weekly match limits reset on {current_date.strftime('%Y-%m-%d')} after {days_since_reset} days")

def reset_match_limits():
    """Force reset all match limits"""
    limits = load_match_limits()
    limits['matches'] = {}
    limits['weekly_matches'] = {}
    limits['last_reset'] = datetime.now().strftime("%Y-%m-%d")
    save_match_limits(limits)
    print("Match limits have been force reset")

def can_players_match(player1_id: str, player2_id: str) -> bool:
    check_weekly_reset()
    limits = load_match_limits()
    
    if 'matches' not in limits:
        limits['matches'] = {}
        save_match_limits(limits)
        return True
        
    players = sorted([str(player1_id), str(player2_id)])
    match_pair = f"{players[0]}-{players[1]}"
    
    matches = limits['matches'].get(match_pair, 0)
    last_reset = limits.get('last_reset', 'Never')
    
    return matches < 2

def record_match_played(player1_id: str, player2_id: str):
    limits = load_match_limits()
    match_pair = f"{sorted([str(player1_id), str(player2_id)])[0]}-{sorted([str(player1_id), str(player2_id)])[1]}"
    limits['matches'][match_pair] = limits['matches'].get(match_pair, 0) + 1
    save_match_limits(limits)

async def record_dodge(interaction, player_id: str):
    limits = load_match_limits()
    
    if 'dodges' not in limits:
        limits['dodges'] = {}
    
    limits['dodges'][player_id] = limits['dodges'].get(player_id, 0) + 1
    save_match_limits(limits)
    
    players = load_players()
    player_name = players[player_id]['name']
    
    results_channel = interaction.guild.get_channel(RESULTS_CHANNEL_ID)
    if results_channel:
        embed = discord.Embed(
            title="Match Dodged",
            description=f"**{player_name}** has dodged a match\nDodges remaining this week: {2 - limits['dodges'].get(player_id, 0)}",
            color=discord.Color.red()
        )
        await results_channel.send(embed=embed)

def get_weekly_matches(player_id: str) -> int:
    limits = load_match_limits()
    
    if not limits.get('last_reset'):
        limits['last_reset'] = datetime.now().strftime("%Y-%m-%d")
        limits['weekly_matches'] = {}
        save_match_limits(limits)
        return 0
    
    last_reset = datetime.strptime(limits['last_reset'], "%Y-%m-%d")
    current_time = datetime.now()
    days_since_reset = (current_time - last_reset).days
    
    if days_since_reset >= 7:
        limits['weekly_matches'] = {}
        limits['last_reset'] = current_time.strftime("%Y-%m-%d")
        save_match_limits(limits)
        return 0
    
    return limits.get('weekly_matches', {}).get(str(player_id), 0)

def increment_weekly_matches(player_id: str):
    limits = load_match_limits()
    if 'weekly_matches' not in limits:
        limits['weekly_matches'] = {}
    
    player_id = str(player_id)
    limits['weekly_matches'][player_id] = limits['weekly_matches'].get(player_id, 0) + 1
    save_match_limits(limits)

def can_player_duel(player_id: str) -> bool:
    weekly_matches = get_weekly_matches(player_id)
    return weekly_matches < 5

def is_player_banned(player_id: str):
    bans = load_queue_bans()
    if not bans or 'bans' not in bans:
        return False
        
    if str(player_id) in bans['bans']:
        ban_end = datetime.strptime(bans['bans'][str(player_id)], "%Y-%m-%d %H:%M:%S")
        if ban_end > datetime.now():
            return True
        else:
            del bans['bans'][str(player_id)]
            save_queue_bans(bans)
    return False

def ban_player(player_id: str):
    bans = load_queue_bans()
    ban_end = datetime.now() + timedelta(days=1)
    bans['bans'][str(player_id)] = ban_end.strftime("%Y-%m-%d %H:%M:%S")
    save_queue_bans(bans)

def apply_dodge_penalty(player_id: str):
    players = load_players()
    player_data = players[str(player_id)]
    
    old_rating = player_data['rating']
    
    player_data['rating'] = max(0, player_data['rating'] - 20)
    
    save_players(players)
    
    history = []
    history.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "dodge_penalty",
        "player": {
            "id": str(player_id),
            "name": player_data['name'],
            "old_rating": old_rating,
            "new_rating": player_data['rating']
        }
    })
    
    if leaderboard_message:
        asyncio.create_task(update_leaderboard())

def load_match_history():
    try:
        with open('match_history.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        default_history = {}
        save_match_history(default_history)
        return default_history

def save_match_history(data):
    with open('match_history.json', 'w') as f:
        json.dump(data, f, indent=4)

def record_match_history(winner_id: str, loser_id: str, winner_rating: int, loser_rating: int):
    try:
        history = load_match_history()
        if not isinstance(history, dict):
            history = {}  # Reset if not a dictionary
            
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        match_entry = {
            "winner_rating": winner_rating,
            "loser_rating": loser_rating,
            "timestamp": current_time
        }
        
        if winner_id not in history:
            history[winner_id] = {"wins": [], "losses": []}
        history[winner_id]["wins"].append({
            "opponent_id": loser_id,
            **match_entry
        })
        
        if loser_id not in history:
            history[loser_id] = {"wins": [], "losses": []}
        history[loser_id]["losses"].append({
            "opponent_id": winner_id,
            **match_entry
        })
        
        save_match_history(history)
    except Exception as e:
        print(f"Error recording match history: {e}")

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        self.add_view(QueueAndDuelView())
        await self.tree.sync()

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')

        leaderboard_channel = self.get_channel(LEADERBOARD_CHANNEL_ID)
        if leaderboard_channel:
            async for message in leaderboard_channel.history(limit=100):
                await message.delete()
            
            embed = create_leaderboard_embed()
            global leaderboard_message
            leaderboard_message = await leaderboard_channel.send(embed=embed)
            print("Leaderboard initialized")

        queue_channel = self.get_channel(QUEUE_CHANNEL_ID)
        if queue_channel:
            async for message in queue_channel.history(limit=100):
                await message.delete()
            
            view = QueueAndDuelView()
            await queue_channel.send("Click the button below to look for a fight!", view=view)
            print("Queue and Duel buttons initialized")

        self.match_queued_players.start()
        print(f"{self.user} has connected to Discord!")

    @tasks.loop(seconds=5.0)
    async def match_queued_players(self):
        await self.wait_until_ready()
        while not self.is_closed():
            current_time = datetime.now()
            to_remove = []
            
            queue_list = list(queue_players.items())
            
            for i, (player_id, player_data) in enumerate(queue_list):
                for other_id, other_data in queue_list[i+1:]:
                    rating_diff = abs(player_data['rating'] - other_data['rating'])
                    if rating_diff <= 100:
                        if not can_players_match(player_id, other_id):
                            continue

                        queue_channel = self.get_channel(QUEUE_CHANNEL_ID)
                        if queue_channel:
                            player = await self.fetch_user(int(player_id))
                            other_player = await self.fetch_user(int(other_id))
                            
                            if player and other_player:
                                to_remove.extend([player_id, other_id])
                                
                                await queue_channel.send(
                                    f"🎮 Match Found!\n"
                                    f"{player.mention} ({player_data['rating']} ELO) vs "
                                    f"{other_player.mention} ({other_data['rating']} ELO)\n"
                                    f"Rating difference: {rating_diff}",
                                    view=EndMatchView(player, other_player)
                                )
            
            for player_id in to_remove:
                if player_id in queue_players:
                    del queue_players[player_id]
            
            for player_id, data in queue_players.items():
                time_in_queue = current_time - data['timestamp']
                if time_in_queue.total_seconds() > 3600:  # 1 hour
                    to_remove.append(player_id)
            
            await asyncio.sleep(5)  # Check every 5 seconds

class QueueAndDuelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Join Queue", style=discord.ButtonStyle.primary, custom_id="queue:join")
    async def join_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        
        if user_id not in rules_accepted:
            rules_channel = interaction.guild.get_channel(RULES_CHANNEL_ID)
            await interaction.response.send_message(
                get_rules_message(rules_channel),
                ephemeral=True,
                view=AcceptRulesView()
            )
            return
        
        players_data = load_players()
        if user_id not in players_data:
            await interaction.response.send_message(
                "You are not registered! Ask an admin to register you.",
                ephemeral=True
            )
            return
        
        if is_player_banned(user_id):
            bans = load_queue_bans()
            ban_end = datetime.strptime(bans['bans'][user_id], "%Y-%m-%d %H:%M:%S")
            time_left = ban_end - datetime.now()
            hours = int(time_left.total_seconds() / 3600)
            minutes = int((time_left.total_seconds() % 3600) / 60)
            
            await interaction.response.send_message(
                f"You are banned from queue for {hours}h {minutes}m!",
                ephemeral=True
            )
            return

        if user_id in queue_players:
            await interaction.response.send_message(
                "You are already in queue!",
                ephemeral=True
            )
            return

        view = ConfirmQueueView()
        await interaction.response.send_message(
            f"Are you sure you want to join the queue? Current rating: {players_data[user_id]['rating']} ELO (±100 ELO range)",
            view=view,
            ephemeral=True
        )
        view.message = await interaction.original_response()
        
        await view.wait()
        
        if view.value:
            queue_players[user_id] = {
                "rating": players_data[user_id]["rating"],
                "timestamp": datetime.now()
            }
            await interaction.followup.send("Added to queue!", ephemeral=True)

    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.danger, custom_id="queue:leave")
    async def leave_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        
        if user_id not in queue_players:
            await interaction.response.send_message(
                "You are not in the queue!",
                ephemeral=True
            )
            return

        del queue_players[user_id]
        await interaction.response.send_message("Removed from queue!", ephemeral=True)

    @discord.ui.button(label="Duel", style=discord.ButtonStyle.success, custom_id="duel:start")
    async def start_duel(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        
        if user_id not in rules_accepted:
            rules_channel = interaction.guild.get_channel(RULES_CHANNEL_ID)
            await interaction.response.send_message(
                get_rules_message(rules_channel),
                ephemeral=True,
                view=AcceptRulesView()
            )
            return

        players_data = load_players()
        
        if user_id not in players_data:
            await interaction.response.send_message(
                "You are not registered! Ask an admin to register you.",
                ephemeral=True
            )
            return
        
        if is_player_banned(user_id):
            bans = load_queue_bans()
            ban_end = datetime.strptime(bans['bans'][user_id], "%Y-%m-%d %H:%M:%S")
            time_left = ban_end - datetime.now()
            hours = int(time_left.total_seconds() / 3600)
            minutes = int((time_left.total_seconds() % 3600) / 60)
            
            await interaction.response.send_message(
                f"You are banned from duels for {hours}h {minutes}m!",
                ephemeral=True
            )
            return

        available_players = []
        
        for member in interaction.guild.members:
            member_id = str(member.id)
            if member_id in players_data and member_id != user_id:
                rating_diff = abs(players_data[user_id]["rating"] - players_data[member_id]["rating"])
                if rating_diff <= 100:  
                    available_players.append(member)

        if not available_players:
            await interaction.response.send_message(
                "No players available within 100 ELO of your rating!",  
                ephemeral=True
            )
            return

        view = PlayerSelectView(interaction.user, available_players)
        await interaction.response.send_message(
            f"Select a player to duel! Your rating: {players_data[user_id]['rating']} ELO (±100 ELO range)",  
            view=view,
            ephemeral=True
        )

class PlayerSelectView(discord.ui.View):
    def __init__(self, challenger, available_players):
        super().__init__()
        self.add_item(PlayerSelectDropdown(challenger, available_players))

class PlayerSelectDropdown(discord.ui.Select):
    def __init__(self, challenger, available_players):
        self.challenger = challenger
        options = []
        
        players_data = load_players()
        challenger_rating = players_data[str(challenger.id)]["rating"]
        
        for player in available_players:
            player_id = str(player.id)
            if player_id not in players_data:
                continue
                
            rating_diff = abs(challenger_rating - players_data[player_id]["rating"])
            if rating_diff > 100:
                continue
                
            if not can_players_match(str(challenger.id), player_id):
                continue
                
            options.append(
                discord.SelectOption(
                    label=player.name,
                    value=player_id,
                    description=f"Rating: {players_data[player_id]['rating']} (±{rating_diff})"
                )
            )
        
        if not options:
            options = [discord.SelectOption(
                label="No players available",
                value="none",
                description="No players within 100 ELO or match limit reached"
            )]
        
        super().__init__(
            placeholder="Select a player to duel",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(self.challenger.id):
            await interaction.response.send_message("This is not your duel menu!", ephemeral=True)
            return

        if self.values[0] == "none":
            await interaction.response.send_message("No players available to duel!", ephemeral=True)
            return

        opponent = interaction.guild.get_member(int(self.values[0]))
        if not opponent:
            await interaction.response.send_message("Selected player not found!", ephemeral=True)
            return

        players = load_players()
        challenger_id = str(self.challenger.id)
        opponent_id = str(opponent.id)
        
        if not can_players_match(challenger_id, opponent_id):
            await interaction.response.send_message("Match limit reached with this player!", ephemeral=True)
            return
            
        challenger_rating = players[challenger_id]["rating"]
        opponent_rating = players[opponent_id]["rating"]
        rating_diff = abs(challenger_rating - opponent_rating)

        view = DuelAcceptDeclineView(self.challenger, opponent)
        match_message = await interaction.channel.send(
            f"{opponent.mention}, {self.challenger.mention} ({challenger_rating} ELO) challenges you to a duel!\n"
            f"Your rating: {opponent_rating} ELO\n"
            f"Rating difference: {rating_diff} ELO",
            view=view
        )
        view.message = match_message
        await interaction.response.defer()

class DuelAcceptDeclineView(discord.ui.View):
    def __init__(self, challenger, opponent):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.message = None
        self.response_message = None
        self.duel_accepted = False

    async def on_timeout(self):
        if self.duel_accepted:  
            return
            
        if self.message:
            try:
                await self.message.delete()
            except:
                pass
            
        if self.challenger and hasattr(self.message, 'channel'):
            try:
                timeout_msg = await self.message.channel.send(
                    f"Duel request from {self.challenger.mention} has timed out.",
                    delete_after=5
                )
            except:
                pass

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("This is not your duel to accept!", ephemeral=True)
            return

        self.duel_accepted = True

        if self.message:
            try:
                await self.message.delete()
            except:
                pass

        players = load_players()
        challenger_id = str(self.challenger.id)
        opponent_id = str(self.opponent.id)
        challenger_rating = players[challenger_id]["rating"]
        opponent_rating = players[opponent_id]["rating"]
        rating_diff = abs(challenger_rating - opponent_rating)

        match_view = EndMatchView(self.challenger, self.opponent)
        match_message = await interaction.channel.send(
            f"🎮 Match started!\n"
            f"{self.challenger.mention} ({challenger_rating} ELO) vs "
            f"{self.opponent.mention} ({opponent_rating} ELO)\n"
            f"Rating difference: {rating_diff}\n",
            view=match_view
        )
        await interaction.response.defer()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("This is not your duel to decline!", ephemeral=True)
            return

        if self.message:
            try:
                await self.message.delete()
            except:
                pass

        await interaction.response.send_message(
            f"{self.opponent.mention} declined the duel!",
            delete_after=5
        )

class EndMatchView(discord.ui.View):
    def __init__(self, player1, player2):
        super().__init__(timeout=None)
        self.add_item(SelectWinnerDropdown(player1, player2))
        self.player1 = player1
        self.player2 = player2

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in [self.player1.id, self.player2.id] and interaction.user.id not in ADMIN_IDS:
            await interaction.response.send_message("This is not your match!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Dodge", style=discord.ButtonStyle.danger)
    async def dodge(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        
        if interaction.user.id not in [self.player1.id, self.player2.id]:
            await interaction.response.send_message("This is not your match to dodge!", ephemeral=True)
            return
        
        limits = load_match_limits()
        dodges_used = limits.get('dodges', {}).get(user_id, 0)
        if dodges_used >= 2:
            await interaction.response.send_message("You have no dodges remaining this week!", ephemeral=True)
            return
        
        await record_dodge(interaction, user_id)
        
        await interaction.message.delete()
        
        await interaction.response.send_message("Match dodged!", ephemeral=True)

class SelectWinnerDropdown(discord.ui.Select):
    def __init__(self, player1, player2):
        self.player1 = player1  
        self.player2 = player2
        options = [
            discord.SelectOption(
                label=f"{player1.name}",
                value=str(player1.id)
            ),
            discord.SelectOption(
                label=f"{player2.name}",
                value=str(player2.id)
            )
        ]
        super().__init__(
            placeholder="Select the winner",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in ADMIN_IDS:
            await interaction.response.send_message("Only admins can use this!", ephemeral=True)
            return

        winner_id = self.values[0]
        winner = self.player1 if str(self.player1.id) == winner_id else self.player2
        loser = self.player2 if str(self.player1.id) == winner_id else self.player1

        limits = load_match_limits()
        match_pair = f"{sorted([str(winner.id), str(loser.id)])[0]}-{sorted([str(winner.id), str(loser.id)])[1]}"
        if 'matches' not in limits:
            limits['matches'] = {}
        limits['matches'][match_pair] = limits['matches'].get(match_pair, 0) + 1
        save_match_limits(limits)

        await interaction.response.defer(ephemeral=True)
        
        await process_match_result(interaction, winner, loser)
        await interaction.message.delete()

class ConfirmQueueView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=10)
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.send_message("Cancelled!", ephemeral=True)

    async def on_timeout(self):
        if self.value is None:
            await self.message.edit(content="Confirmation timed out", view=None)

class AcceptRulesView(discord.ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="Accept Rules", style=discord.ButtonStyle.success)
    async def accept_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if user_id in rules_accepted:
            await interaction.response.send_message("You have already accepted the rules!", ephemeral=True)
            return

        rules_accepted.add(user_id)
        save_rules_accepted(rules_accepted)
        await interaction.response.send_message("You have accepted the rules!", ephemeral=True)

async def update_leaderboard():
    global leaderboard_message
    if not leaderboard_message:
        return
        
    embed = create_leaderboard_embed()
    try:
        await leaderboard_message.edit(embed=embed)
    except discord.NotFound:
        channel = leaderboard_message.channel
        leaderboard_message = await channel.send(embed=embed)

async def initialize_leaderboard(self):
    global leaderboard_message
    leaderboard_channel = self.get_channel(LEADERBOARD_CHANNEL_ID)
    if leaderboard_channel:
        async for message in leaderboard_channel.history():
            await message.delete()
        
        embed = create_leaderboard_embed()
        leaderboard_message = await leaderboard_channel.send(embed=embed)
        print("Leaderboard initialized")

async def process_match_result(interaction, winner, loser):
    winner_id = str(winner.id)
    loser_id = str(loser.id)
    
    increment_weekly_matches(winner_id)
    increment_weekly_matches(loser_id)
    
    players = load_players()
    winner_rating = players[winner_id]["rating"]
    loser_rating = players[loser_id]["rating"]
    
    record_match_history(winner_id, loser_id, winner_rating, loser_rating)
    
    k_factor = 32
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 - expected_winner
    
    new_winner_rating = int(winner_rating + k_factor * (1 - expected_winner))
    new_loser_rating = int(loser_rating + k_factor * (0 - expected_loser))
    
    players[winner_id]["rating"] = new_winner_rating
    players[winner_id]["wins"] = players[winner_id].get("wins", 0) + 1
    
    players[loser_id]["rating"] = new_loser_rating
    players[loser_id]["losses"] = players[loser_id].get("losses", 0) + 1
    
    save_players(players)
    
    rating_change_winner = new_winner_rating - winner_rating
    rating_change_loser = new_loser_rating - loser_rating
    
    increment_match_count(winner_id, loser_id)
    increment_weekly_matches(winner_id)
    increment_weekly_matches(loser_id)
    
    results_channel = interaction.guild.get_channel(RESULTS_CHANNEL_ID)
    if results_channel:
        embed = discord.Embed(title="Match Results", color=discord.Color.gold())
        
        embed.add_field(
            name="Winner",
            value=f"**{players[winner_id]['name']}** ({winner.mention})\n"
                  f"{winner_rating} → {new_winner_rating} "
                  f"({'+' if rating_change_winner >= 0 else ''}{rating_change_winner})",
            inline=False
        )
        
        embed.add_field(
            name="Loser",
            value=f"**{players[loser_id]['name']}** ({loser.mention})\n"
                  f"{loser_rating} → {new_loser_rating} ({rating_change_loser})",
            inline=False
        )
        
        embed.set_footer(text="Author: Mekvil • github.com/Mekvil/Champs")
        
        await results_channel.send(embed=embed)
    
    await interaction.followup.send("Match results recorded!", ephemeral=True)
    
    await update_leaderboard()

def create_leaderboard_embed():
    players = load_players()
    if not players:
        embed = discord.Embed(title="No players registered yet!")
        embed.set_footer(text="Author: Mekvil • github.com/Mekvil/Champs")
        return embed
        
    sorted_players = sorted(
        [(id, data) for id, data in players.items() if data.get('wins', 0) + data.get('losses', 0) > 0],
        key=lambda x: x[1]["rating"],
        reverse=True
    )
    
    embed = discord.Embed(title=" Champs Leaderboard", color=discord.Color.gold())
    
    if not sorted_players:
        embed.description = "No players have played any games yet!"
        embed.set_footer(text="Author: Mekvil • github.com/Mekvil/Champs")
        return embed
    
    leaderboard_text = ""
    for i, (player_id, data) in enumerate(sorted_players, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        leaderboard_text += f"{medal} **{data['name']}** - {data['rating']} ELO "
        leaderboard_text += f"(W: {data.get('wins', 0)} L: {data.get('losses', 0)}) [{data['discord_name']}]\n"
    
    embed.description = leaderboard_text
    embed.set_footer(text="Author: Mekvil • github.com/Mekvil/Champs")
    return embed

def increment_match_count(player1_id: str, player2_id: str):
    limits = load_match_limits()
    
    match_key = f"{player1_id}-{player2_id}"
    if match_key not in limits['matches']:
        limits['matches'][match_key] = 0
    
    limits['matches'][match_key] += 1
    save_match_limits(limits)

bot = Bot()

@bot.tree.command(name="rating", description="Check your or another player's rating")
@app_commands.describe(
    player="The player to check rating for (optional)"
)
async def rating(interaction: discord.Interaction, player: discord.Member = None):
    target = player or interaction.user
    target_id = str(target.id)
    
    players = load_players()
    if target_id not in players:
        await interaction.response.send_message(f"{target.name} is not registered!", ephemeral=True)
        return
    
    player_data = players[target_id]
    history = load_match_history()
    player_history = history.get(target_id, {"wins": [], "losses": []})
    
    embed = discord.Embed(
        title=f"Rating for {player_data['name']}",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Stats",
        value=f"Rating: {player_data['rating']} ELO\n"
              f"Wins: {player_data['wins']}\n"
              f"Losses: {player_data['losses']}",
        inline=False
    )
    
    recent_matches = []
    all_matches = []
    
    for win in player_history['wins']:
        all_matches.append(("W", win))
    for loss in player_history['losses']:
        all_matches.append(("L", loss))
    
    all_matches.sort(key=lambda x: datetime.strptime(x[1]['timestamp'], "%Y-%m-%d %H:%M:%S"), reverse=True)
    
    for result, match in all_matches[:5]:
        opponent_id = match['opponent_id']
        opponent_name = players[opponent_id]['name']
        rating_diff = match['winner_rating'] - match['loser_rating']
        match_time = datetime.strptime(match['timestamp'], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        
        if result == "W":
            recent_matches.append(f"✅ vs {opponent_name} (±{abs(rating_diff)}) - {match_time}")
        else:
            recent_matches.append(f"❌ vs {opponent_name} (±{abs(rating_diff)}) - {match_time}")
    
    if recent_matches:
        embed.add_field(
            name="Recent Matches",
            value="\n".join(recent_matches),
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="setup_lfg", description="Setup the Looking For Fight button")
@discord.app_commands.checks.has_permissions(administrator=True)
async def setup_lfg(interaction: discord.Interaction):
    view = LookingForFightButton()
    await interaction.channel.send("Click the button below to look for a fight!", view=view)
    await interaction.response.send_message("Looking For Fight button has been set up!", ephemeral=True)

@bot.tree.command(name="setup_rules", description="Setup the rules acceptance button (Admin only)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def setup_rules(interaction: discord.Interaction):
    view = AcceptRulesButton()
    rules_channel = interaction.guild.get_channel(RULES_CHANNEL_ID)
    await rules_channel.send(f"You must accept the rules in #правила first!", view=view)
    await interaction.response.send_message("Rules acceptance button has been set up!", ephemeral=True)

@bot.tree.command(name="register", description="Register a player in the rating system (Admin only)")
@app_commands.describe(
    user="The user to register",
    name="The player's name"
)
async def register(interaction: discord.Interaction, user: discord.Member, name: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("Only admins can register players!", ephemeral=True)
        return

    players = load_players()
    player_id = str(user.id)
        
    players[player_id] = {
        "rating": 1000,
        "wins": 0,
        "losses": 0,
        "name": name,
        "discord_name": user.name
    }
    save_players(players)
    await update_leaderboard()
    await interaction.response.send_message(f"Successfully registered **{name}** ({user.mention})! Starting rating is 1000")

@bot.tree.command(name="match", description="Record a match result (Admin only)")
@app_commands.describe(
    winner="The winner of the match",
    loser="The loser of the match"
)
async def match(interaction: discord.Interaction, winner: discord.Member, loser: discord.Member):
    await interaction.response.defer(ephemeral=True)

    if interaction.user.id not in ADMIN_IDS:
        await interaction.followup.send("Only admins can use this command!", ephemeral=True)
        return

    players = load_players()
    if str(winner.id) not in players or str(loser.id) not in players:
        await interaction.followup.send("Both players must be registered!", ephemeral=True)
        return

    winner_id = str(winner.id)
    loser_id = str(loser.id)
    
    winner_rating = players[winner_id]["rating"]
    loser_rating = players[loser_id]["rating"]
    
    record_match_history(winner_id, loser_id, winner_rating, loser_rating)
    
    k_factor = 32
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 - expected_winner
    
    new_winner_rating = int(winner_rating + k_factor * (1 - expected_winner))
    new_loser_rating = int(loser_rating + k_factor * (0 - expected_loser))
    
    players[winner_id]["rating"] = new_winner_rating
    players[winner_id]["wins"] = players[winner_id].get("wins", 0) + 1
    
    players[loser_id]["rating"] = new_loser_rating
    players[loser_id]["losses"] = players[loser_id].get("losses", 0) + 1
    
    save_players(players)
    
    rating_change_winner = new_winner_rating - winner_rating
    rating_change_loser = new_loser_rating - loser_rating
    
    increment_match_count(winner_id, loser_id)
    increment_weekly_matches(winner_id)
    increment_weekly_matches(loser_id)
    
    results_channel = interaction.guild.get_channel(RESULTS_CHANNEL_ID)
    if results_channel:
        embed = discord.Embed(title="Match Results", color=discord.Color.gold())
        
        embed.add_field(
            name="Winner",
            value=f"**{players[winner_id]['name']}** ({winner.mention})\n"
                  f"{winner_rating} → {new_winner_rating} "
                  f"({'+' if rating_change_winner >= 0 else ''}{rating_change_winner})",
            inline=False
        )
        
        embed.add_field(
            name="Loser",
            value=f"**{players[loser_id]['name']}** ({loser.mention})\n"
                  f"{loser_rating} → {new_loser_rating} ({rating_change_loser})",
            inline=False
        )
        
        embed.set_footer(text="Author: Mekvil • github.com/Mekvil/Champs")
        
        await results_channel.send(embed=embed)
    
    await interaction.followup.send("Match results recorded!", ephemeral=True)
    
    await update_leaderboard()

@bot.tree.command(name="reset_limits", description="Reset all match limits (Admin only)")
@app_commands.default_permissions(administrator=True)
async def reset_limits(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
        
    reset_match_limits()
    await interaction.response.send_message("All match limits have been reset!", ephemeral=True)

leaderboard_message = None
active_matches = {}  
rules_accepted = load_rules_accepted()  
queue_players = {}  
active_duels = {}  

bot.run(os.getenv('DISCORD_TOKEN'))