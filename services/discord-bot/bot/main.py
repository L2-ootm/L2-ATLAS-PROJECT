import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
from aiohttp import web
from bot.api import setup_bot_api
from database.database import connect_database, disconnect_database

# Load environment variables from .env file
load_dotenv()

# Get the bot token from environment variables
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")

# Define the bot's intents (moved into L2Bot.__init__)

class L2Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.db_connected = False
        self.rag_system = None
        self.temp_channel_manager = None

    async def setup_hook(self):
        # Initialize Temp Channel Manager
        from bot.managers.temp_channels import TempChannelManager
        self.temp_channel_manager = TempChannelManager(self)
        self.loop.create_task(self.temp_channel_manager.start_monitoring())

        # Connect to local SQLite database
        try:
            await connect_database()
            self.db_connected = True
            print("Database features are enabled.")
        except Exception as e:
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print(f"Database connection failed: {e}")
            print("Running without database features.")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

        for filename in os.listdir("./bot/cogs"):
            if filename.endswith(".py"):
                try:
                    await self.load_extension(f"bot.cogs.{filename[:-3]}")
                    print(f"Loaded cog {filename[:-3]}")
                except Exception as e:
                    print(f"Failed to load cog {filename[:-3]}: {e}")
        
        # Sync commands to a specific guild for faster updates
        if GUILD_ID:
            print(f"Syncing commands to guild: {GUILD_ID}")
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print("Commands synced to guild.")
        else:
            # Sync globally if no guild ID is provided (can take up to an hour)
            print("Syncing commands globally (this may take up to an hour)...")
            await self.tree.sync()
            print("Global sync command sent.")

    async def on_ready(self):
        print(f'Logged in as {self.user.name} ({self.user.id})')
        print('------')

    async def close(self):
        await super().close()
        if self.db_connected:
            await disconnect_database()

bot = L2Bot()

@bot.command()
@commands.is_owner()
async def sync(ctx):
    """Syncs slash commands manually."""
    print("Manual sync initiated...")
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            await ctx.send(f"Commands synced to guild {GUILD_ID}")
        else:
            await bot.tree.sync()
            await ctx.send("Commands synced globally.")
    except Exception as e:
        await ctx.send(f"Sync failed: {e}")

@bot.command()
@commands.is_owner()
async def clear_global(ctx):
    """Clears all global commands to remove duplicates."""
    print("Clearing global commands...")
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    await ctx.send("✅ Global commands cleared. Duplicates should disappear (might take some time to update).")

@bot.command()
@commands.is_owner()
async def clear_guild(ctx):
    """Clears all guild commands."""
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.clear_commands(guild=guild)
        await bot.tree.sync(guild=guild)
        await ctx.send(f"✅ Guild commands cleared for {GUILD_ID}.")
    else:
        await ctx.send("❌ No GUILD_ID found in env.")

async def main():
    if BOT_TOKEN:
        # Start the internal API server
        api_app = setup_bot_api(bot)
        runner = web.AppRunner(api_app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', 8081)
        await site.start()
        print("Internal Bot API is running on http://localhost:8081")

        # Start the bot
        await bot.start(BOT_TOKEN)
    else:
        print("Error: DISCORD_BOT_TOKEN not found in .env file.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shutting down.")
    finally:
        asyncio.run(bot.close())