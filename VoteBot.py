import os
import discord
from discord.ext import commands
from discord.ui import Button, View
from datetime import datetime
from dotenv import load_dotenv
import sqlite3

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

conn = sqlite3.connect('polls.db')
c = conn.cursor()

ephemeral_messages = {}

c.execute('''CREATE TABLE IF NOT EXISTS Polls (
                id INTEGER PRIMARY KEY,
                question TEXT,
                end_date TEXT,
                poll_type TEXT
             )''')

c.execute('''CREATE TABLE IF NOT EXISTS Options (
                id INTEGER PRIMARY KEY,
                poll_id INTEGER,
                option_text TEXT,
                FOREIGN KEY(poll_id) REFERENCES Polls(id)
             )''')

c.execute('''CREATE TABLE IF NOT EXISTS Votes (
                vote_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                poll_id INTEGER,
                option_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES Users(id),
                FOREIGN KEY(poll_id) REFERENCES Polls(id),
                FOREIGN KEY(option_id) REFERENCES Options(id)
             )''')

c.execute('''CREATE TABLE IF NOT EXISTS EphemeralResultMessages (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                poll_id INTEGER,
                message_id INTEGER,
                FOREIGN KEY(poll_id) REFERENCES Polls(id)
             )''')

conn.commit()

def create_poll(question, end_date, options, poll_type):
    c.execute("INSERT INTO Polls (question, end_date, poll_type) VALUES (?, ?, ?)", (question, end_date, poll_type))
    poll_id = c.lastrowid
    for option in options:
        c.execute("INSERT INTO Options (poll_id, option_text) VALUES (?, ?)", (poll_id, option))
    conn.commit()
    return poll_id

def get_poll(poll_id):
    c.execute("SELECT * FROM Polls WHERE id=?", (poll_id,))
    poll = c.fetchone()
    if poll:
        c.execute("SELECT * FROM Options WHERE poll_id=?", (poll_id,))
        options = c.fetchall()
        return poll, options
    else:
        return None, []

def save_vote(user_id, poll_id, option_id):
    c.execute("INSERT OR REPLACE INTO Votes (user_id, poll_id, option_id) VALUES (?, ?, ?)", (user_id, poll_id, option_id))
    conn.commit()

def get_poll_results(poll_id):
    c.execute("SELECT option_text, COUNT(Votes.user_id) FROM Options LEFT JOIN Votes ON Options.id = Votes.option_id WHERE Options.poll_id=? GROUP BY Options.option_text", (poll_id,))
    results = c.fetchall()
    return results

def save_ephemeral_result_message(user_id, poll_id, message_id):
    c.execute("INSERT INTO EphemeralResultMessages (user_id, poll_id, message_id) VALUES (?, ?, ?)", (user_id, poll_id, message_id))
    conn.commit()

def get_ephemeral_result_message(user_id, poll_id, message_id):
    c.execute("SELECT message_id FROM EphemeralResultMessages WHERE user_id=? AND poll_id=? AND message_id=?", (user_id, poll_id, message_id))
    return c.fetchone()

def get_results(poll_id):
    poll, options = get_poll(poll_id)
    if not poll:
        return "Poll not found."
    
    question = poll[1]
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    end_time_str = poll[2] 
    end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M") 
    if datetime.now() < end_time:
       results = f"**{question}**\n*Results as of {current_time}:*\n"
    else:
        results = f"**{question}**\n*Results as of {end_time}:*\n"
    poll_results = get_poll_results(poll_id)
    sorted_results = sorted(poll_results, key=lambda x: x[1], reverse=True)
    
    for option, count in sorted_results:
        results += f"**{option}:** {count}\n"
        
    if datetime.now() < end_time:
        results += f"*The poll ends at {end_time}*\n"
    else:
        results += f"*The poll ended at {end_time}*\n"
    return results

class ResultMessage(discord.ui.View):
    def __init__(self, initial_content, poll_id, message_id, end_date):  
        super().__init__()
        self.initial_content = initial_content
        self.poll_id = poll_id
        self.message_id = message_id
        self.end_date = end_date  

        refresh_button = Button(label="Refresh results", style=discord.ButtonStyle.success, custom_id=f"refresh_button_{poll_id}")
        self.add_item(refresh_button)
        refresh_button.callback = self.refresh_results

    async def refresh_results(self, interaction: discord.Interaction):
        try:
            results = get_results(self.poll_id)
            await interaction.response.edit_message(content=results, view=self)
            if datetime.now() > self.end_date:
                # Disable the button after the last refresh
                for item in self.children:
                    if isinstance(item, Button) and item.label == "Refresh results":
                        item.disabled = True
                        break
        except discord.NotFound:
            print("Result message not found")
            # If the result message is not found, retrieve it from the database
            message_id = get_ephemeral_result_message(interaction.user.id, self.poll_id, self.message_id)
            if message_id:
                try:
                    # Check if the current time is past the end date
                    if datetime.now() > self.end_date:
                        # Disable the button after the last refresh
                        for item in self.children:
                            if isinstance(item, Button) and item.label == "Refresh results":
                                item.disabled = True
                                await interaction.response.edit_message(content=results, view=self)
                                break
                    else:
                        result_message = await interaction.followup.fetch_message(message_id)
                        await result_message.edit(content=results, view=self)
                except discord.NotFound:
                    print("Ephemeral result message not found")
                except Exception as e:
                    print(f"Unexpected error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

class PollView(View):
    def __init__(self, question, options, message, end_date, poll_id, multi_choice=False):
        super().__init__()
        self.question = question
        self.options = options
        self.message = message
        self.end_date = end_date
        self.poll_id = poll_id
        self.multi_choice = multi_choice

        vote_button = Button(label="I want to vote", style=discord.ButtonStyle.primary, custom_id="vote_button")
        self.add_item(vote_button)
        vote_button.callback = self.vote_button

        result_button = Button(label="Show results", style=discord.ButtonStyle.blurple, custom_id="result_button")
        self.add_item(result_button)
        result_button.callback = self.result_button

    async def result_button(self, interaction: discord.Interaction):
        try:
            results = get_results(self.poll_id)
            result_message = ResultMessage(results, self.poll_id, interaction.message.id, self.end_date)
            await interaction.response.send_message(results, ephemeral=True, view=result_message)
            save_ephemeral_result_message(interaction.user.id, self.poll_id, interaction.message.id)
        except discord.HTTPException as e:
            print(f"Error sending result message: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    async def vote_button(self, interaction: discord.Interaction):
        if datetime.now() > self.end_date:
            await interaction.response.send_message("The poll has ended. Voting is no longer possible.", ephemeral=True)
            return

        view = SinglePollView(interaction.user.id, self.poll_id, self.options, self.end_date) if not self.multi_choice else MultiPollView(interaction.user.id, self.poll_id, self.options, self.end_date)
        if self.multi_choice:
            ephemeral_message = await interaction.response.send_message(f"**{self.question}**\n*Please select your vote(s) below.*", ephemeral=True, view=view)
        else:
            ephemeral_message = await interaction.response.send_message(f"**{self.question}**\n*Please select your vote below.*", ephemeral=True, view=view)

        if interaction.user.id not in ephemeral_messages:
            ephemeral_messages[interaction.user.id] = []
        ephemeral_messages[interaction.user.id].append(ephemeral_message)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if datetime.now() > self.end_date:
            results = get_results(self.poll_id)
            for item in self.children:
                if isinstance(item, Button):
                    item.disabled = True
            await interaction.response.edit_message(content=results, view=self)
            return False
        return True

class SinglePollView(View):
    def __init__(self, user_id, poll_id, options, end_date):
        super().__init__()
        self.user_id = user_id
        self.poll_id = poll_id
        self.options = options
        self.selected_option = None
        self.end_date = end_date 

        if user_id:
            self.fetch_user_votes()

        for option in options:
            style = discord.ButtonStyle.success if option == self.selected_option else discord.ButtonStyle.secondary
            vote_button = Button(label=option, style=style, custom_id=option)
            self.add_item(vote_button)
            vote_button.callback = self.on_button_click

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Check if the poll has ended
        if datetime.now() > self.end_date:
            for item in self.children:
                if isinstance(item, Button):
                    item.disabled = True
            await interaction.response.edit_message(view=self)
            return False
        return interaction.user.id == self.user_id


    async def on_button_click(self, interaction: discord.Interaction):
        # Check if the poll has ended
        if datetime.now() > self.end_date:
            await interaction.response.send_message("The poll has ended. Your vote cannot be accepted.", ephemeral=True)
            return

        option = interaction.data['custom_id']
        if option in self.options:
            if self.selected_option == option:
                self.selected_option = None
                self.remove_vote_from_database(option)
            else:
                prev_option = self.selected_option
                self.selected_option = option
                self.remove_vote_from_database(prev_option)
                self.save_vote_to_database(option)

        for item in self.children:
            if isinstance(item, Button):
                item.style = discord.ButtonStyle.success if item.custom_id == self.selected_option else discord.ButtonStyle.secondary

        await interaction.response.edit_message(view=self)

    def fetch_user_votes(self):
        c.execute("SELECT option_text FROM Votes INNER JOIN Options ON Votes.option_id = Options.id WHERE Votes.user_id=? AND Votes.poll_id=?", (self.user_id, self.poll_id))
        self.selected_option = c.fetchone()

    def save_vote_to_database(self, option):
        c.execute("DELETE FROM Votes WHERE user_id=? AND poll_id=?", (self.user_id, self.poll_id))
        c.execute("INSERT INTO Votes (user_id, poll_id, option_id) VALUES (?, ?, (SELECT id FROM Options WHERE option_text=? AND poll_id=?))", (self.user_id, self.poll_id, option, self.poll_id))
        conn.commit()

    def remove_vote_from_database(self, option):
        if option is not None:
            c.execute("DELETE FROM Votes WHERE user_id=? AND poll_id=? AND option_id=(SELECT id FROM Options WHERE option_text=? AND poll_id=?)", (self.user_id, self.poll_id, option, self.poll_id))
            conn.commit()

class MultiPollView(View):
    def __init__(self, user_id, poll_id, options, end_date):
        super().__init__()
        self.user_id = user_id
        self.poll_id = poll_id
        self.options = options
        self.selected_options = set()
        self.end_date = end_date

        if user_id:
            self.fetch_user_votes()

        for option in options:
            style = discord.ButtonStyle.success if option in self.selected_options else discord.ButtonStyle.secondary
            vote_button = Button(label=option, style=style, custom_id=option)
            self.add_item(vote_button)
            vote_button.callback = self.on_button_click

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Check if the poll has ended
        if datetime.now() > self.end_date:
            for item in self.children:
                if isinstance(item, Button):
                    item.disabled = True
            await interaction.response.edit_message(view=self)
            return False
        return interaction.user.id == self.user_id

    async def on_button_click(self, interaction: discord.Interaction):
        # Check if the poll has ended
        if datetime.now() > self.end_date:
            await interaction.response.send_message("The poll has ended. Your vote cannot be accepted.", ephemeral=True)
            return

        option = interaction.data['custom_id']
        if option in self.options:
            if option in self.selected_options:
                self.selected_options.remove(option)
                self.remove_vote_from_database(option)
            else:
                self.selected_options.add(option)
                self.save_vote_to_database(option)

        for item in self.children:
            if isinstance(item, Button):
                item.style = discord.ButtonStyle.success if item.custom_id in self.selected_options else discord.ButtonStyle.secondary

        await interaction.response.edit_message(view=self)

    def fetch_user_votes(self):
        c.execute("SELECT option_text FROM Votes INNER JOIN Options ON Votes.option_id = Options.id WHERE Votes.user_id=? AND Votes.poll_id=?", (self.user_id, self.poll_id))
        self.selected_options = set(option[0] for option in c.fetchall())

    def save_vote_to_database(self, option):
        c.execute("INSERT INTO Votes (user_id, poll_id, option_id) VALUES (?, ?, (SELECT id FROM Options WHERE option_text=? AND poll_id=?))", (self.user_id, self.poll_id, option, self.poll_id))
        conn.commit()

    def remove_vote_from_database(self, option):
        c.execute("DELETE FROM Votes WHERE user_id=? AND poll_id=? AND option_id=(SELECT id FROM Options WHERE option_text=? AND poll_id=?)", (self.user_id, self.poll_id, option, self.poll_id))
        conn.commit()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command(name='single_poll')
async def create_single_poll(ctx, question: str, end_date_str: str, *options: str):
    options = list(set(opt for opt in options if opt.strip()))  
    if len(options) < 2:
        await ctx.send("You must provide at least two non-empty and unique options for the poll.")
        return
    
    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        await ctx.send("Invalid date format. Please use the format YYYY-MM-DD HH:MM.")
        return

    if end_date < datetime.now():
        await ctx.send("End date cannot be in the past.")
        return

    options_text = "\n".join(options)
    message = await ctx.send(f"**{question}**\n{options_text}\n*The poll ends at {end_date.strftime('%Y-%m-%d %H:%M')}*")

    poll_id = create_poll(question, end_date_str, options, 'single_poll')
    view = PollView(question, options, message, end_date, poll_id)
    await message.edit(view=view)
    
@bot.command(name='multi_poll')
async def create_multi_poll(ctx, question: str, end_date_str: str, *options: str):
    options = list(set(opt for opt in options if opt.strip()))  
    if len(options) < 2:
        await ctx.send("You must provide at least two non-empty and unique options for the poll.")
        return
    
    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        await ctx.send("Invalid date format. Please use the format YYYY-MM-DD HH:MM.")
        return

    if end_date < datetime.now():
        await ctx.send("End date cannot be in the past.")
        return

    options_text = "\n".join(options)
    message = await ctx.send(f"**{question}**\n{options_text}\n*The poll ends at {end_date.strftime('%Y-%m-%d %H:%M')}*")

    poll_id = create_poll(question, end_date_str, options, 'multi_poll')
    view = PollView(question, options, message, end_date, poll_id, multi_choice=True)
    await message.edit(view=view)

@bot.command(name='poll_help')
async def poll_help(ctx):
    help_message = (
        "To create a single-choice poll, use the command:\n"
        "`!single_poll \"<question>\" \"<end_date>\" \"<option1>\" \"<option2>\" ...`\n\n"
        "To create a multiple-choice poll, use the command:\n"
        "`!multi_poll \"<question>\" \"<end_date>\" \"<option1>\" \"<option2>\" ...`\n\n"
        "The date and time format for <end_date> is YYYY-MM-DD HH:MM.\n\n"
        "Example for a single-choice poll:\n"
        "`!single_poll \"What's your favorite color?\" \"2024-06-04 23:59\" \"Red\" \"Blue\" \"Green\"`\n\n"
        "Example for a multiple-choice poll:\n"
        "`!multi_poll \"Which programming languages do you know?\" \"2024-06-04 23:59\" \"Python\" \"JavaScript\" \"Java\" \"C++\"`\n"
    )
    await ctx.send(help_message)

bot.run(TOKEN)