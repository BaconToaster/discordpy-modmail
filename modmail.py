import discord
import asyncio
import os
from discord.ext import commands, tasks

intents = discord.Intents.default()
intents.members = True

client = commands.Bot(command_prefix=None, help_command=None, intents=intents)

class GlobalVars:
    tgGuild = None
    ticketCat = None
    supportRole = None
    ticketSaveChannel = None
    hasOpenTicket = {}
    
    def __init__(self):
        self.tgGuild = client.get_guild(your guild id)

        for category in self.tgGuild.categories:
            if "tickets" in category.name.lower():
                self.ticketCat = category
                break

        for role in self.tgGuild.roles:
            # replace ||tickets|| with the role which should get pinged after creating a modmail ticket
            if "||tickets||" in role.name.lower():
                self.supportRole = role
                break
        
        for channel in self.tgGuild.text_channels:
            # create a ticket-conclusion channel, the bot will send every modmail ticket as a txt file into it
            if "ticket-conclusion" in channel.name.lower():
                self.ticketSaveChannel = channel
                break

globals = None

async def SendMsgAndAddLog(text, channel : discord.TextChannel, user : discord.Member):
    f = open(f"{user.name}#{user.discriminator}.txt", "a")
    f.writelines(text + "\n\n")
    f.flush()
    await channel.send(text)

@client.event
async def on_ready():
    print("logged in!")
    global globals
    globals = GlobalVars()
    activity = discord.Activity(type=discord.ActivityType.listening, name="your PMs")
    await client.change_presence(activity=activity)

@tasks.loop()
async def GetMessages(message : discord.Message, teamChannel : discord.TextChannel):
    def checkUser(m):
        return (m.channel == message.channel or m.channel == teamChannel) and not m.author.bot

    msg = await client.wait_for("message", check=checkUser)
    if msg.channel == teamChannel:
        await SendMsgAndAddLog(f"**[{msg.author.name}]**: {msg.content}", message.channel, message.author)
    elif msg.channel == message.channel:
        await SendMsgAndAddLog(f"**[{msg.author.name}]**: {msg.content}", teamChannel, message.author)

@client.event
async def on_message(message):
    if message.author.bot:
        return
    
    try:
        if globals.hasOpenTicket[f"{message.author.id}"]:
            pass
    except KeyError:
        globals.hasOpenTicket[f"{message.author.id}"] = False

    if message.channel.type == discord.ChannelType.private and not globals.hasOpenTicket[f"{message.author.id}"]:
        msg = await message.channel.send("Do you want to create a ticket?")
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        def reaction_check_user(reaction, user):
            return (str(reaction.emoji) == "✅"  or str(reaction.emoji) == "❌") and user == message.author and reaction.message.id == msg.id

        try:
            reaction, user = await client.wait_for("reaction_add", timeout=60, check=reaction_check_user)
        except asyncio.TimeoutError:
            await message.channel.send("You failed to react in time, if you want to create a ticket send me another message.")
            return
        
        if str(reaction.emoji) == "❌":
            await message.channel.send("Ok, the creation of the ticket was cancelled.")
        elif str(reaction.emoji) == "✅":
            globals.hasOpenTicket[f"{message.author.id}"] = True
            await message.channel.send("Ok, the ticket was created!")
            
            teamChannel = await globals.tgGuild.create_text_channel(f"{message.author.name}#{message.author.discriminator}", category=globals.ticketCat, reason="Hat ein Modmail Ticket erstellt")
            closeMsg = await teamChannel.send(f"{globals.supportRole.mention}, {message.author.mention} created a ticket.")
            await closeMsg.add_reaction("🔒")
            await message.author.send("The supporters will help you soon, please describe your problem.")

            def checkReaction(reaction, user):
                return str(reaction.emoji) == "🔒" and reaction.message.id == closeMsg.id and not user.bot

            GetMessages.start(message, teamChannel)
            await client.wait_for("reaction_add", check=checkReaction)
            GetMessages.cancel()
            
            await globals.ticketSaveChannel.send(file=discord.File(f"{message.author.name}#{message.author.discriminator}.txt"))
            await teamChannel.delete(reason="The ticket was closed")
            globals.hasOpenTicket[f"{message.author.id}"] = False
            os.remove(f"{message.author.name}#{message.author.discriminator}.txt")
            await message.author.send("Your ticket was closed.")

client.run("ur token here")
