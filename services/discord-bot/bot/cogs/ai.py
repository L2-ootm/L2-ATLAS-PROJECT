import discord
from discord.ext import commands
from discord import app_commands
from bot.rag import RAGSystem, KeyManager
from bot.agent import L2Agent
from bot.chat_session import (
    ChatSessionManager, 
    is_farewell, 
    is_directed_at_bot,
    format_session_start_message,
    format_session_end_message
)
from bot.utils.log_embeds import LogEmbedBuilder
from datetime import datetime


class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.key_manager = KeyManager()
        self.rag_system = RAGSystem(supabase_client=bot.supabase_manager)
        self.agent = L2Agent(
            bot=bot,
            key_manager=self.key_manager,
            supabase_client=bot.supabase_manager
        )
        self.session_manager = ChatSessionManager()

    async def send_split_message(self, destination, content, reference=None):
        """
        Sends a message to a destination, splitting it if it exceeds 2000 characters.
        Supports replying to a specific message.
        """
        if not content:
            content = "Request processed."
            
        if len(content) <= 2000:
            if isinstance(destination, discord.Interaction):
                await destination.followup.send(content)
            elif reference:
                await destination.send(content, reference=reference)
            else:
                await destination.send(content)
            return

        # Split logic
        chunks = []
        while content:
            if len(content) <= 2000:
                chunks.append(content)
                break
            
            split_index = content.rfind('\n', 0, 1950)
            if split_index == -1:
                split_index = content.rfind(' ', 0, 1950)
            
            if split_index == -1:
                split_index = 1950
            
            chunks.append(content[:split_index])
            content = content[split_index:].lstrip()

        for i, chunk in enumerate(chunks):
            if isinstance(destination, discord.Interaction):
                await destination.followup.send(chunk)
            elif reference and i == 0:
                await destination.send(chunk, reference=reference)
            else:
                await destination.send(chunk)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLASH COMMANDS
    # ═══════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="logs", description="[ADMIN] View recent system logs.")
    async def logs(self, interaction: discord.Interaction, limit: int = 5):
        await interaction.response.defer()
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("🔒 **ACCESS DENIED.** L2_SYS_ADMIN clearance required.")
            return

        try:
            logs = self.bot.supabase_manager.get_recent_logs(limit=limit)
            
            if isinstance(logs, dict) and "error" in logs:
                await interaction.followup.send(f"⚠️ Error fetching logs: {logs['error']}")
                return

            if not logs:
                await interaction.followup.send("ℹ️ No recent logs found in `sys_trace_stream`.")
                return

            await interaction.followup.send(f"### 📡 SYSTEM AUDIT STREAM // LAST {limit} EVENTS")
            
            for log in logs:
                embed = LogEmbedBuilder.create_log_embed(log)
                await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"Error in /logs command: {e}")
            await interaction.followup.send(f"An error occurred: {e}")

    @app_commands.command(name="ask", description="Ask a question to the AI assistant (with tool access).")
    async def ask(self, interaction: discord.Interaction, question: str):
        """AI Assistant with Agent Tools."""
        await interaction.response.defer()
        
        try:
            print(f"Processing /ask command (agent mode): {question}")
            
            if interaction.guild:
                answer = await self.agent.run(
                    query=question,
                    guild=interaction.guild,
                    user=interaction.user,
                    channel=interaction.channel
                )
            else:
                answer = await self.rag_system.query(question)
            
            await self.send_split_message(interaction, answer)
            
        except Exception as e:
            print(f"Error in /ask command: {e}")
            await interaction.followup.send(f"⚠️ An error occurred: {e}")

    @app_commands.command(name="ask_simple", description="Ask a question (without tools, faster).")
    async def ask_simple(self, interaction: discord.Interaction, question: str):
        """Simple Q&A without agent tools - faster for basic questions."""
        await interaction.response.defer()
        try:
            print(f"Processing /ask_simple command: {question}")
            answer = await self.rag_system.query(question)
            full_response = f"**Q:** {question}\n\n{answer}"
            await self.send_split_message(interaction, full_response)
        except Exception as e:
            print(f"Error in /ask_simple command: {e}")
            await interaction.followup.send(f"An error occurred: {e}")

    @app_commands.command(name="chat", description="Start a seamless chat session with the AI.")
    async def chat(self, interaction: discord.Interaction):
        """
        Start a continuous chat session.
        The bot will automatically respond to your messages until you say goodbye.
        """
        await interaction.response.defer()
        
        try:
            # Start session
            session = self.session_manager.start_session(
                user_id=interaction.user.id,
                channel_id=interaction.channel.id,
                guild_id=interaction.guild.id if interaction.guild else 0
            )
            
            # Send welcome message
            await interaction.followup.send(format_session_start_message())
            
        except Exception as e:
            print(f"Error starting chat session: {e}")
            await interaction.followup.send(f"⚠️ Failed to start chat session: {e}")

    @app_commands.command(name="stop", description="Stop the current chat session.")
    async def stop_chat(self, interaction: discord.Interaction):
        """Stop an active chat session."""
        await interaction.response.defer()
        
        session = self.session_manager.get_session(
            interaction.user.id, 
            interaction.channel.id
        )
        
        if session:
            duration = int((datetime.utcnow() - session.started_at).total_seconds() / 60)
            self.session_manager.end_session(interaction.user.id, interaction.channel.id)
            await interaction.followup.send(
                format_session_end_message(session.message_count, duration)
            )
        else:
            await interaction.followup.send("ℹ️ No active chat session to stop.")

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE LISTENER
    # ═══════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle incoming messages for chat sessions and L2 prefix."""
        if message.author.bot:
            return
        
        # Check for active chat session first
        session = self.session_manager.get_session(
            message.author.id, 
            message.channel.id
        )
        
        if session:
            await self._handle_chat_session(message, session)
            return
        
        # Fallback to L2 prefix for non-session messages
        if message.content.lower().startswith("l2 "):
            query = message.content[3:].strip()
            if query:
                # Implicit Session Start
                # If query is substantial, treat it as start of session but DONT confirm.
                # Just process it as a session message.
                session = self.session_manager.start_session(
                    user_id=message.author.id,
                    channel_id=message.channel.id,
                    guild_id=message.guild.id if message.guild else 0
                )
                # No welcome message designated here.
                await self._handle_chat_session(message, session)

    async def _handle_chat_session(self, message: discord.Message, session):
        """Handle a message within an active chat session."""
        content = message.content.strip()
        
        # Check for farewell
        if is_farewell(content):
            self.session_manager.end_session(message.author.id, message.channel.id)
            # Silent stop -> Just react
            try:
                await message.add_reaction("👋")
            except:
                pass
            return
        
        # Check if message is directed at bot (in session mode, respond to everything)
        bot_mentioned = self.bot.user in message.mentions
        if not is_directed_at_bot(content, bot_mentioned, in_active_session=True):
            # Not directed at bot, skip but don't end session
            return
        
        # Add user message to history
        session.add_message("user", content)
        
        # Process with agent
        async with message.channel.typing():
            try:
                # Build context from session history
                history_context = ""
                if session.conversation_history:
                    recent = session.conversation_history[-10:]  # Last 10 messages
                    history_context = "\n\n[CONVERSATION HISTORY]\n"
                    for msg in recent[:-1]:  # Exclude current message
                        history_context += f"{msg['role'].upper()}: {msg['content']}\n"
                
                # Extract image attachments from the message
                attachment_info = ""
                image_urls = []
                document_contents = []
                
                # Define readable text file extensions
                READABLE_EXTENSIONS = {'.txt', '.md', '.json', '.csv', '.py', '.js', '.html', '.css', '.xml', '.yaml', '.yml', '.log', '.ini', '.cfg', '.toml'}
                
                for attachment in message.attachments:
                    # Handle images
                    if attachment.content_type and attachment.content_type.startswith("image/"):
                        image_urls.append(attachment.url)
                    # Handle text documents
                    elif any(attachment.filename.lower().endswith(ext) for ext in READABLE_EXTENSIONS):
                        try:
                            # Download and decode the attachment
                            file_bytes = await attachment.read()
                            file_content = file_bytes.decode('utf-8', errors='replace')
                            
                            # Limit content size to prevent context overflow
                            if len(file_content) > 15000:
                                file_content = file_content[:15000] + "\n\n... [TRUNCATED - File too large]"
                            
                            document_contents.append({
                                "filename": attachment.filename,
                                "content": file_content
                            })
                        except Exception as e:
                            logger.warning(f"Failed to read attachment {attachment.filename}: {e}")
                
                if image_urls:
                    attachment_info = f"\n\n[ATTACHED IMAGES]\nThe user attached {len(image_urls)} image(s) to this message. URLs:\n"
                    for i, url in enumerate(image_urls, 1):
                        attachment_info += f"{i}. {url}\n"
                    attachment_info += "Use these URLs with edit_image tool if the user wants to edit/transform them.\n"
                
                if document_contents:
                    attachment_info += f"\n\n[ATTACHED DOCUMENTS]\nThe user attached {len(document_contents)} document(s). Contents:\n"
                    for doc in document_contents:
                        attachment_info += f"\n--- FILE: {doc['filename']} ---\n"
                        attachment_info += doc['content']
                        attachment_info += f"\n--- END OF {doc['filename']} ---\n"
                
                # Run agent with history and attachments
                full_query = content
                if history_context:
                    full_query = f"{history_context}\nCurrent message: {content}"
                if attachment_info:
                    full_query += attachment_info
                
                answer = await self.agent.run(
                    query=full_query,
                    guild=message.guild,
                    user=message.author,
                    channel=message.channel
                )
                
                # Add response to history
                session.add_message("assistant", answer)
                
                # Reply to the message
                await self.send_split_message(
                    message.channel, 
                    answer, 
                    reference=message
                )
                
            except Exception as e:
                print(f"Error in chat session response: {e}")
                await message.reply(f"⚠️ Error: {e}")

    async def _handle_single_query(self, message: discord.Message, query: str):
        """Handle a single L2-prefixed query (not in a session)."""
        async with message.channel.typing():
            try:
                print(f"Processing L2 prefix query: {query}")
                
                if message.guild:
                    answer = await self.agent.run(
                        query=query,
                        guild=message.guild,
                        user=message.author,
                        channel=message.channel
                    )
                else:
                    answer = await self.rag_system.query(query)
                
                await self.send_split_message(message.channel, answer)
                
            except Exception as e:
                print(f"Error in L2 query: {e}")
                await message.reply(f"⚠️ Error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # IMAGE GENERATION COMMANDS
    # ═══════════════════════════════════════════════════════════════════════════
    
    @app_commands.command(name="image", description="Generate an image using AI")
    @app_commands.describe(
        model="Select the AI model to use",
        prompt="Describe the image you want to generate",
        width="Image width (default: 1024)",
        height="Image height (default: 1024)"
    )
    @app_commands.choices(model=[
        app_commands.Choice(name="🚀 Flux Schnell (Fast, 5K/pollen)", value="flux"),
        app_commands.Choice(name="⚡ Z-Image Turbo (Fast, 5K/pollen)", value="zimage"),
        app_commands.Choice(name="🎨 SDXL Turbo (3.3K/pollen)", value="turbo"),
        app_commands.Choice(name="🌟 GPT Image Mini (Premium, 70/pollen)", value="gptimage"),
        app_commands.Choice(name="💎 GPT Image 1.5 (Highest Quality, 15/pollen)", value="gptimage-large"),
        app_commands.Choice(name="🌸 Seedream 4.0 (35/pollen)", value="seedream"),
        app_commands.Choice(name="🌺 Seedream 4.5 Pro (Premium, 25/pollen)", value="seedream-pro"),
        app_commands.Choice(name="✏️ FLUX Kontext (Image Editing, 25/pollen)", value="kontext"),
        app_commands.Choice(name="🍌 NanoBanana (25/pollen)", value="nanobanana"),
        app_commands.Choice(name="🍌 NanoBanana Pro (Premium, 6/pollen)", value="nanobanana-pro"),
    ])
    async def image_command(
        self, 
        interaction: discord.Interaction,
        model: str,
        prompt: str,
        width: int = 1024,
        height: int = 1024
    ):
        """Generate an image with selected model."""
        await interaction.response.defer(thinking=True)
        
        from bot.image_gen import get_image_generator
        from bot.pollen_manager import get_pollen_manager
        
        generator = get_image_generator()
        pollen_mgr = get_pollen_manager()
        
        # Override the model temporarily
        original_model = generator.model
        generator.model = model
        
        try:
            # Check if user attached an image for kontext/editing
            reference_url = None
            
            # Generate and send
            success, message = await generator.generate_and_send(
                channel=interaction.channel,
                prompt=prompt,
                width=width,
                height=height,
                reference_url=reference_url
            )
            
            # Get updated status
            status = pollen_mgr.get_status()
            
            if success:
                await interaction.followup.send(
                    f"✅ Image generated with **{model}**!\n"
                    f"📊 Pollen today: `{status['total_used_today']:.4f}` / `{status['total_remaining_today'] + status['total_used_today']:.1f}`"
                )
            else:
                await interaction.followup.send(f"❌ Failed: {message}")
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")
        finally:
            # Restore original model
            generator.model = original_model
    
    @app_commands.command(name="image_edit", description="Edit an image using AI - Interactive flow")
    @app_commands.describe(
        model="Select the AI model for editing"
    )
    @app_commands.choices(model=[
        app_commands.Choice(name="✏️ FLUX Kontext (Best for editing, 25/pollen)", value="kontext"),
        app_commands.Choice(name="🌟 GPT Image Mini (70/pollen)", value="gptimage"),
        app_commands.Choice(name="💎 GPT Image 1.5 (Highest Quality, 15/pollen)", value="gptimage-large"),
        app_commands.Choice(name="🌺 Seedream 4.5 Pro (25/pollen)", value="seedream-pro"),
        app_commands.Choice(name="🍌 NanoBanana Pro (6/pollen)", value="nanobanana-pro"),
    ])
    async def image_edit_command(
        self,
        interaction: discord.Interaction,
        model: str = "kontext"
    ):
        """Interactive image editing flow."""
        # Step 1: Acknowledge and ask for image
        await interaction.response.send_message(
            f"🎨 **Image Edit Session Started**\n"
            f"**Model:** `{model}`\n\n"
            f"📎 **Step 1:** Please send the image you want to edit.\n"
            f"*You have 60 seconds to upload an image...*",
            ephemeral=False
        )
        
        # Step 2: Wait for image
        def check_image(m):
            return (
                m.author.id == interaction.user.id and 
                m.channel.id == interaction.channel.id and
                len(m.attachments) > 0 and
                any(a.content_type and a.content_type.startswith("image/") for a in m.attachments)
            )
        
        try:
            image_msg = await self.bot.wait_for("message", check=check_image, timeout=60.0)
            
            # Get image URL
            image_attachment = next(
                a for a in image_msg.attachments 
                if a.content_type and a.content_type.startswith("image/")
            )
            reference_url = image_attachment.url
            
            # React to confirm receipt
            await image_msg.add_reaction("✅")
            
        except Exception as e:
            await interaction.followup.send(
                "⏰ **Timed out!** No image received within 60 seconds.\n"
                "Run `/image_edit` again to start over."
            )
            return
        
        # Step 3: Ask for prompt
        prompt_ask = await interaction.channel.send(
            f"✅ **Image received!**\n\n"
            f"✍️ **Step 2:** Now describe what changes you want.\n"
            f"*Example: \"make it cyberpunk style\" or \"add neon lights\"*\n\n"
            f"*You have 120 seconds to type your prompt...*"
        )
        
        def check_prompt(m):
            return (
                m.author.id == interaction.user.id and 
                m.channel.id == interaction.channel.id and
                len(m.content) > 0 and
                not m.content.startswith("/")
            )
        
        try:
            prompt_msg = await self.bot.wait_for("message", check=check_prompt, timeout=120.0)
            prompt = prompt_msg.content
            
            await prompt_msg.add_reaction("🎨")
            
        except Exception:
            await interaction.channel.send(
                "⏰ **Timed out!** No prompt received.\n"
                "Run `/image_edit` again to start over."
            )
            return
        
        # Step 4: Process
        processing_msg = await interaction.channel.send(
            f"⏳ **Downloading image...**"
        )
        
        from bot.image_gen import get_image_generator, download_image_as_base64
        from bot.pollen_manager import get_pollen_manager
        
        # Convert Discord URL to base64
        base64_image = await download_image_as_base64(reference_url)
        if not base64_image:
            await processing_msg.edit(content="❌ **Failed to download image.** Please try again.")
            return
        
        await processing_msg.edit(
            content=f"⏳ **Processing with {model}...**\n"
            f"This may take up to 2 minutes for high-quality models."
        )
        
        generator = get_image_generator()
        pollen_mgr = get_pollen_manager()
        
        original_model = generator.model
        generator.model = model
        
        try:
            async with interaction.channel.typing():
                success, message = await generator.generate_and_send(
                    channel=interaction.channel,
                    prompt=prompt,
                    width=1024,
                    height=1024,
                    reference_url=base64_image  # Use base64 instead of Discord URL
                )
            
            # Delete processing message
            await processing_msg.delete()
            
            status = pollen_mgr.get_status()
            
            if success:
                await interaction.channel.send(
                    f"✅ **Image edited successfully!**\n"
                    f"**Model:** `{model}` | **Prompt:** {prompt[:50]}...\n"
                    f"📊 Pollen today: `{status['total_used_today']:.4f}`"
                )
            else:
                await interaction.channel.send(f"❌ **Failed:** {message}")
                
        except Exception as e:
            await processing_msg.delete()
            await interaction.channel.send(f"❌ **Error:** {e}")
        finally:
            generator.model = original_model
    
    @app_commands.command(name="pollen_status", description="Check Pollinations.ai API usage and remaining budget")
    async def pollen_status_command(self, interaction: discord.Interaction):
        """Show pollen usage status."""
        await interaction.response.defer(thinking=True)
        
        from bot.pollen_manager import get_pollen_manager
        pollen_mgr = get_pollen_manager()
        report = pollen_mgr.get_usage_report()
        await interaction.followup.send(report)

    @app_commands.command(name="pollen_set", description="Manually set pollen usage (supports 0.08 or 0,08)")
    @app_commands.describe(amount="Amount of pollen used today (e.g. 0.08)", key_name="Key name (default: Primary)")
    async def pollen_set_command(self, interaction: discord.Interaction, amount: str, key_name: str = "Primary"):
        """Manually set pollen usage."""
        # Check permissions (only owner or specific role)
        if interaction.user.id != 354332306733563914 and interaction.user.id != 1332768567540256860:
             # Just a basic check for now
             pass 

        try:
            # Handle both dot and comma
            amount_val = float(amount.replace(',', '.'))
        except ValueError:
            await interaction.response.send_message(
                f"❌ **Invalid format:** Please enter a number like `0.08` or `0,08`.", ephemeral=True
            )
            return

        from bot.pollen_manager import get_pollen_manager
        pollen_mgr = get_pollen_manager()
        
        if pollen_mgr.set_key_usage(key_name, amount_val):
            await interaction.response.send_message(
                f"✅ **Usage Updated:** `{key_name}` set to `{amount_val:.4f}` pollen used today."
            )
        else:
            await interaction.response.send_message(
                f"❌ **Failed:** Key `{key_name}` not found.", ephemeral=True
            )



async def setup(bot):
    await bot.add_cog(AI(bot))