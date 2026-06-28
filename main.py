import discord
from discord.ext import commands
import asyncio
import os
from config import DISCORD_TOKEN, GUILD_ID
from database.db import init_database

# Initialize intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Create bot instance
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """Bot ready event"""
    print(f"✓ Bot logged in as {bot.user}")
    print(f"✓ Bot ID: {bot.user.id}")
    
    # Initialize database
    init_database()
    print("✓ Database initialized")
    
    # Sync commands to guild only (not globally)
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            synced = await bot.tree.sync(guild=guild)
            print(f"✓ Synced {len(synced)} command(s) to guild")
        else:
            synced = await bot.tree.sync()
            print(f"✓ Synced {len(synced)} command(s) globally")
    except Exception as e:
        print(f"✗ Failed to sync commands: {e}")

async def load_cogs():
    """Load all cogs from the cogs folder"""
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and filename != "__init__.py":
            await bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"✓ Loaded cog: {filename[:-3]}")

async def main():
    """Main function to start the bot"""
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
