import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import asyncio
from bot.utils.log_embeds import LogEmbedBuilder

CONFIG_FILE = "bot/logging_config.json"

class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self.load_config()
        self.auto_fetch_logs.start()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Failed to load logging config: {e}")
        return {"guild_id": None, "channels": {}, "last_processed_id": 0}

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Failed to save logging config: {e}")

    def cog_unload(self):
        self.auto_fetch_logs.cancel()

    @app_commands.command(name="setup_logs", description="[ADMIN] Setup auto-logging channels.")
    async def setup_logs(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🔒 **ACCESS DENIED.** Admin permissions required.", ephemeral=True)
            return

        await interaction.response.defer()
        guild = interaction.guild
        self.config["guild_id"] = guild.id

        # Create Category
        category_name = "| SYSTEM LOGS"
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)
        
        # Define Channels
        channels_map = {
            "info": "🔵・info",
            "success": "🟢・success",
            "warning": "⚠️・warning",
            "error": "🔴・error",
            "critical": "🚨・critical"
        }

        created_channels = {}

        for key, name in channels_map.items():
            channel = discord.utils.get(guild.text_channels, name=name, category=category)
            if not channel:
                channel = await guild.create_text_channel(name, category=category)
            created_channels[key] = channel.id

        self.config["channels"] = created_channels
        self.save_config()

        await interaction.followup.send(f"✅ **Logging System Setup Complete!**\nChannels created in `{category_name}`.")

    @tasks.loop(seconds=10)
    async def auto_fetch_logs(self):
        if not self.config.get("guild_id") or not self.config.get("channels"):
            return

        last_id = self.config.get("last_processed_id", 0)
        
        # Fetch new logs
        try:
            new_logs = self.bot.supabase_manager.get_new_logs(last_id=last_id)
        except Exception as e:
            print(f"Error fetching new logs: {e}")
            return

        if not new_logs:
            return

        # Sort by ID ascending to process in order
        new_logs.sort(key=lambda x: x['id'])

        guild = self.bot.get_guild(self.config["guild_id"])
        if not guild:
            return

        for log in new_logs:
            event_type = log.get("event_type", "UNKNOWN")
            channel_key = self.get_channel_key(event_type)
            channel_id = self.config["channels"].get(channel_key)

            if channel_id:
                channel = guild.get_channel(channel_id)
                if channel:
                    embed = LogEmbedBuilder.create_log_embed(log)
                    try:
                        await channel.send(embed=embed)
                    except Exception as e:
                        print(f"Failed to send log to channel {channel.name}: {e}")

            # Update last processed ID
            if log['id'] > self.config["last_processed_id"]:
                self.config["last_processed_id"] = log['id']
        
        self.save_config()

    def get_channel_key(self, event_type):
        """Map event types to channel keys."""
        # Critical
        if event_type in ['HONEYPOT_TRIGGER', 'TAMPER_ATTEMPT', 'SYSTEM_SHUTDOWN_ATTEMPT']:
            return "critical"
        # Error
        if event_type in ['PAYMENT_FAILED', 'API_ERROR', 'UNAUTHORIZED_ACCESS', 'RECORD_DELETED']:
            return "error"
        # Warning
        if event_type in ['CORRELATED_SUSPICION_TZ', 'MASS_ATTACK_MITIGATION', 'API_LATENCY_HIGH', 'SUBSCRIPTION_CANCELLED']:
            return "warning"
        # Success
        if event_type in ['PAYMENT_SUCCESS', 'SYNC_COMPLETE', 'FILE_UPLOAD', 'USER_CREATED', 'SUBSCRIPTION_CREATED', 'RECORD_CREATED']:
            return "success"
        # Default Info
        return "info"

    @auto_fetch_logs.before_loop
    async def before_auto_fetch(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Logger(bot))
