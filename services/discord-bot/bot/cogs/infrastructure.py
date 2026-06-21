import discord
from discord.ext import commands
from discord import app_commands
import logging
from bot.channel_messages import send_welcome_messages

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Infrastructure(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.layout_config = {
            "protected_categories": [
                {"name_match": "| SYSTEM LOGS", "target_position": 0, "action": "KEEP_AND_PIN_TOP"},
                {"name_match": "🎧 | GERAL", "target_position": "AFTER_NEW_VOICE", "action": "MOVE"}
            ],
            "new_infrastructure": [
                {
                    "name": "[[ 🏛️ L2 // MAINFRAME ]]",
                    "position_index": 1,
                    "channels": [
                        {"name": "📢・announcements", "type": discord.ChannelType.text},
                        {"name": "📜・protocols", "type": discord.ChannelType.text},
                        {"name": "�・utility-hub", "type": discord.ChannelType.text},
                        {"name": "�💼・war-room", "type": discord.ChannelType.text, "private": True},
                        {"name": "💸・revenue-stream", "type": discord.ChannelType.text},
                        {"name": "📡・command-center", "type": discord.ChannelType.text}
                    ]
                },
                {
                    "name": "[[ ⚙️ L2 // FACTORY ]]",
                    "position_index": 2,
                    "channels": [
                        {"name": "🔨・active-builds", "type": discord.ChannelType.text},
                        {"name": "⚡・n8n-workflows", "type": discord.ChannelType.text},
                        {"name": "🐍・code-repository", "type": discord.ChannelType.text},
                        {"name": "🚧・debug-forum", "type": discord.ChannelType.forum}
                    ]
                },
                {
                    "name": "[[ 🧠 L2 // NEURAL ]]",
                    "position_index": 3,
                    "channels": [
                        {"name": "🎨・prompt-engineering", "type": discord.ChannelType.forum},
                        {"name": "🤖・agents-logs", "type": discord.ChannelType.text},
                        {"name": "📚・knowledge-base", "type": discord.ChannelType.text}
                    ]
                },
                {
                    "name": "[[ 🧪 L2 // DOGFOODING ]]",
                    "position_index": 4,
                    "channels": [
                        {"name": "💠・l2-os-feedback", "type": discord.ChannelType.text},
                        {"name": "🐛・internal-tickets", "type": discord.ChannelType.text}
                    ]
                },
                {
                    "name": "[[ 🎨 L2 // IMAGE-LAB ]]",
                    "position_index": 5,
                    "channels": [
                        {"name": "🧪・img-test", "type": discord.ChannelType.text},
                        {"name": "🖼️・img-production", "type": discord.ChannelType.text},
                        {"name": "🎭・img-showcase", "type": discord.ChannelType.text}
                    ]
                },
                {
                    "name": "[[ 🔊 L2 // UPLINK ]]",
                    "position_index": 6,
                    "channels": [
                        {"name": "🔊・Board Meeting", "type": discord.ChannelType.voice},
                        {"name": "🔊・Deep Work", "type": discord.ChannelType.voice}
                    ]
                }
            ]
        }

    @app_commands.command(name="deploy_infrastructure", description="Deploys the L2 Systems infrastructure (Shift Down & Inject)")
    @app_commands.checks.has_permissions(administrator=True)
    async def deploy_infrastructure(self, interaction: discord.Interaction):
        """
        Executes the Shift Down and Inject algorithm to reorganize the Discord server.
        """
        await interaction.response.defer(thinking=True)
        guild = interaction.guild
        
        if not guild:
            await interaction.followup.send("This command can only be used in a server.")
            return

        try:
            status_msg = await interaction.followup.send("🔄 **Phase A: Mapping & Identification started...**")
            
            # --- PHASE A: Mapping ---
            existing_categories = guild.categories
            system_logs_cat = discord.utils.get(existing_categories, name="| SYSTEM LOGS")
            voice_geral_cat = discord.utils.get(existing_categories, name="🎧 | GERAL")
            
            # Identify Legacy Categories (everything else)
            legacy_categories = []
            for cat in existing_categories:
                if cat != system_logs_cat and cat != voice_geral_cat:
                    # Avoid Moving newly created categories if re-running
                    is_new_structure = any(new_cat["name"] == cat.name for new_cat in self.layout_config["new_infrastructure"])
                    if not is_new_structure:
                        legacy_categories.append(cat)
            
            # Sort legacy categories by current position to maintain relative order
            legacy_categories.sort(key=lambda c: c.position)

            await interaction.followup.send("✅ **Mapping Complete.**\n"
                                          f"- Found System Logs: {'✅' if system_logs_cat else '❌'}\n"
                                          f"- Found Voice Geral: {'✅' if voice_geral_cat else '❌'}\n"
                                          f"- Legacy Categories to Shift: {len(legacy_categories)}")

            # --- PHASE B: The Shift & Inject ---
            await interaction.followup.send("🔄 **Phase B: Shift & Inject started...**")

            # 1. System Logs -> Position 0
            if system_logs_cat:
                await system_logs_cat.edit(position=0)
                await interaction.followup.send("➡️ Moved `| SYSTEM LOGS` to Top.")
            
            # 2. Inject New Structure (Positions 1-5)
            created_cats = {}
            for config in self.layout_config["new_infrastructure"]:
                # Check if exists
                existing_new_cat = discord.utils.get(guild.categories, name=config["name"])
                
                if not existing_new_cat:
                    # Create Category
                    new_cat = await guild.create_category(
                        name=config["name"], 
                        position=config["position_index"]
                    )
                    await interaction.followup.send(f"✨ Created Category: `{config['name']}`")
                else:
                    new_cat = existing_new_cat
                    await new_cat.edit(position=config["position_index"])
                    await interaction.followup.send(f"👌 Category `{config['name']}` exists. Correcting position.")
                
                created_cats[config["name"]] = new_cat
                
                # Create Channels inside Category and track created channels for welcome messages
                created_channels = []
                for chan_conf in config["channels"]:
                    # Check if channel exists ANYWHERE in the guild (not just in this category)
                    existing_chan = discord.utils.get(guild.channels, name=chan_conf["name"])
                    new_channel = None
                    
                    if not existing_chan:
                        # Setup overwrites for private channels
                        overwrites = {}
                        if chan_conf.get("private", False):
                            overwrites = {
                                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                                guild.me: discord.PermissionOverwrite(read_messages=True)
                            }

                        if chan_conf["type"] == discord.ChannelType.text:
                            new_channel = await new_cat.create_text_channel(name=chan_conf["name"], overwrites=overwrites)
                        elif chan_conf["type"] == discord.ChannelType.voice:
                            new_channel = await new_cat.create_voice_channel(name=chan_conf["name"], overwrites=overwrites)
                        elif chan_conf["type"] == discord.ChannelType.forum:
                            # Forum channels must be created via guild.create_forum()
                            if overwrites:
                                new_channel = await guild.create_forum(name=chan_conf["name"], category=new_cat, overwrites=overwrites)
                            else:
                                new_channel = await guild.create_forum(name=chan_conf["name"], category=new_cat)
                        
                        if new_channel and chan_conf["type"] == discord.ChannelType.text:
                            created_channels.append((new_channel, chan_conf["name"]))
                    else:
                        # Channel exists - move it to correct category if needed
                        if hasattr(existing_chan, 'category') and existing_chan.category != new_cat:
                            try:
                                await existing_chan.edit(category=new_cat)
                                logger.info(f"Moved {existing_chan.name} to {new_cat.name}")
                            except:
                                pass
                        # Still try to send welcome messages if empty
                        if hasattr(existing_chan, 'send'):  # Only text channels
                            created_channels.append((existing_chan, chan_conf["name"]))
                
                await interaction.followup.send(f"  ↳ Channels verified for `{config['name']}`")
                
                # Send welcome messages to channels
                for channel, channel_name in created_channels:
                    try:
                        sent = await send_welcome_messages(channel, channel_name)
                        if sent:
                            await interaction.followup.send(f"  📝 Sent welcome messages to `{channel_name}`")
                    except Exception as e:
                        logger.error(f"Failed to send welcome message to {channel_name}: {e}")

            # 3. Handle specific category positioning
            # Find specific categories for special placement
            geral_cat = discord.utils.get(guild.categories, name="| GERAL")
            info_cat = discord.utils.get(guild.categories, name="INFO")
            principal_cat = discord.utils.get(guild.categories, name="| PRINCIPAL")
            afiliado_cat = discord.utils.get(guild.categories, name="afiliado")
            
            # Remove special categories from legacy list
            special_cats = [geral_cat, info_cat, principal_cat, afiliado_cat, voice_geral_cat]
            regular_legacy = [cat for cat in legacy_categories if cat not in special_cats]
            
            # Position 6: | GERAL (voice/general chat)
            current_pos = 6
            if geral_cat:
                await geral_cat.edit(position=current_pos)
                await interaction.followup.send(f"➡️ Moved `| GERAL` to position {current_pos}.")
                current_pos += 1
            
            # Position 7: INFO
            if info_cat:
                await info_cat.edit(position=current_pos)
                await interaction.followup.send(f"➡️ Moved `INFO` to position {current_pos}.")
                current_pos += 1
            
            # Shift regular legacy categories (middle section)
            for cat in regular_legacy:
                try:
                    await cat.edit(position=current_pos)
                    current_pos += 1
                except Exception as e:
                    logger.error(f"Failed to move legacy category {cat.name}: {e}")
            
            await interaction.followup.send(f"⬇️ Shifted {len(regular_legacy)} regular legacy categories.")
            
            # Position near bottom: afiliado
            if afiliado_cat:
                await afiliado_cat.edit(position=current_pos)
                await interaction.followup.send(f"➡️ Moved `afiliado` to position {current_pos} (near bottom).")
                current_pos += 1
            
            # Position at very bottom: | PRINCIPAL
            if principal_cat:
                await principal_cat.edit(position=current_pos)
                await interaction.followup.send(f"➡️ Moved `| PRINCIPAL` to position {current_pos} (bottom).")
                current_pos += 1
            
            # Handle old 🎧 | GERAL if it exists (different from | GERAL)
            if voice_geral_cat and voice_geral_cat != geral_cat:
                await voice_geral_cat.edit(position=current_pos)
                await interaction.followup.send(f"➡️ Moved `🎧 | GERAL` to position {current_pos}.")

            await interaction.followup.send("✅ **INFRASTRUCTURE DEPLOYMENT COMPLETE** 🚀")

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            await interaction.followup.send(f"❌ **CRITICAL FAILURE**: {e}")
            raise e

async def setup(bot):
    await bot.add_cog(Infrastructure(bot))
