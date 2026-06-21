"""
L2 SYSTEMS // Tool Executor
Executes tools called by the AI agent with Discord API integration.
"""

import discord
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import json
import logging

logger = logging.getLogger(__name__)

class ToolExecutor:
    """Executes AI tool calls against Discord API."""
    
    def __init__(self, bot, guild: discord.Guild, user: discord.Member, current_channel: discord.TextChannel = None):
        self.bot = bot
        self.guild = guild
        self.user = user
        self.current_channel = current_channel  # Channel where command was issued
        self.config_store = {}  # Simple in-memory config, can be replaced with DB
    
    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool and return the result.
        
        Returns:
            Dict with 'success', 'result' or 'error' keys
        """
        # Get the executor method
        executor_method = getattr(self, f"_execute_{tool_name}", None)
        
        if not executor_method:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
        
        try:
            result = await executor_method(arguments)
            return {
                "success": True,
                "result": result
            }
        except discord.Forbidden as e:
            return {
                "success": False,
                "error": f"Permission denied: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Tool execution error [{tool_name}]: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _find_channel(self, channel_name: str) -> Optional[discord.abc.GuildChannel]:
        """Find a channel by name (partial match, case-insensitive)."""
        channel_name = channel_name.lower().strip().lstrip('#')
        
        # Search all channels (Text, Forum, Voice, etc.)
        for channel in self.guild.channels:
            # Exact match
            if channel.name.lower() == channel_name:
                return channel
            # Partial match (for emoji prefixes like "📢・announcements")
            if channel_name in channel.name.lower():
                return channel
        
        return None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TOOL IMPLEMENTATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _execute_send_message(self, args: Dict) -> str:
        """Send a message to a channel."""
        channel_name = args.get("channel_name")
        content = args.get("content")
        
        channel = self._find_channel(channel_name)
        if not channel:
            raise ValueError(f"Channel '{channel_name}' not found")
        
        # Check permissions
        if not channel.permissions_for(self.guild.me).send_messages:
            raise discord.Forbidden("Bot cannot send messages to this channel")
        
        message = await channel.send(content)
        return f"Message sent to #{channel.name} (ID: {message.id})"
    
    async def _execute_read_channel(self, args: Dict) -> str:
        """Read recent messages from a channel."""
        channel_name = args.get("channel_name")
        limit = min(args.get("limit", 20), 100)
        
        channel = self._find_channel(channel_name)
        if not channel:
            raise ValueError(f"Channel '{channel_name}' not found")
        
        messages = []
        async for msg in channel.history(limit=limit):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
            author = msg.author.display_name
            content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            messages.append(f"[{timestamp}] {author}: {content}")
        
        messages.reverse()  # Chronological order
        return "\n".join(messages) if messages else "No messages found"
    
    async def _execute_summarize_channel(self, args: Dict) -> str:
        """
        Read messages and return them for summarization.
        Supports large context (up to 1000 messages) for Devstral 2's 256K context.
        """
        channel_name = args.get("channel_name")
        limit = min(args.get("limit", 200), 1000)  # Allow up to 1000 messages
        time_filter = args.get("time_filter", "all")
        
        channel = self._find_channel(channel_name)
        if not channel:
            raise ValueError(f"Channel '{channel_name}' not found")
        
        # Calculate time boundary based on filter
        now = datetime.utcnow()
        if time_filter == "today":
            after = now.replace(hour=0, minute=0, second=0, microsecond=0)
            time_desc = "today"
        elif time_filter == "yesterday":
            after = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            time_desc = "yesterday"
        elif time_filter == "3days":
            after = now - timedelta(days=3)
            time_desc = "last 3 days"
        elif time_filter == "week":
            after = now - timedelta(days=7)
            time_desc = "last 7 days"
        elif time_filter == "2weeks":
            after = now - timedelta(days=14)
            time_desc = "last 14 days"
        elif time_filter == "month":
            after = now - timedelta(days=30)
            time_desc = "last 30 days"
        elif time_filter == "3months":
            after = now - timedelta(days=90)
            time_desc = "last 3 months"
        else:  # "all" or unknown
            after = None
            time_desc = "all time"
        
        # Fetch messages with optional time filter
        messages = []
        message_count = 0
        async for msg in channel.history(limit=limit, after=after):
            message_count += 1
            if msg.author.bot:
                continue
            
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
            author = msg.author.display_name
            content = msg.content
            
            # Include attachments info
            if msg.attachments:
                attachment_info = f" [+{len(msg.attachments)} attachment(s)]"
            else:
                attachment_info = ""
            
            # Include embed info
            if msg.embeds:
                embed_info = f" [+{len(msg.embeds)} embed(s)]"
            else:
                embed_info = ""
            
            if content:
                messages.append(f"[{timestamp}] {author}: {content}{attachment_info}{embed_info}")
            elif attachment_info or embed_info:
                messages.append(f"[{timestamp}] {author}: {attachment_info}{embed_info}")
        
        messages.reverse()  # Chronological order
        
        if not messages:
            return f"📭 No messages found in #{channel.name} for {time_desc}. The channel is empty or only contains bot messages."
        
        # Build comprehensive summary context
        header = f"""📊 **CHANNEL SUMMARY CONTEXT**
**Channel:** #{channel.name}
**Time Range:** {time_desc}
**Messages Analyzed:** {len(messages)} human messages (from {message_count} total)
**Period:** {messages[0].split(']')[0][1:]} to {messages[-1].split(']')[0][1:]}

---
**CONVERSATION LOG:**

"""
        
        return header + "\n".join(messages)
    
    async def _execute_pin_message(self, args: Dict) -> str:
        """Pin a message."""
        channel_name = args.get("channel_name")
        message_id = args.get("message_id")
        
        channel = self._find_channel(channel_name)
        if not channel:
            raise ValueError(f"Channel '{channel_name}' not found")
        
        try:
            message = await channel.fetch_message(int(message_id))
            await message.pin()
            return f"Message {message_id} pinned in #{channel.name}"
        except discord.NotFound:
            raise ValueError(f"Message {message_id} not found")
    
    async def _execute_create_thread(self, args: Dict) -> str:
        """Create a thread."""
        channel_name = args.get("channel_name")
        thread_name = args.get("thread_name")
        message_id = args.get("message_id")
        
        channel = self._find_channel(channel_name)
        if not channel:
            raise ValueError(f"Channel '{channel_name}' not found")
        
        if message_id:
            message = await channel.fetch_message(int(message_id))
            thread = await message.create_thread(name=thread_name)
        else:
            thread = await channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.public_thread
            )
        
        return f"Thread '{thread_name}' created (ID: {thread.id})"
    
    async def _execute_create_forum_post(self, args: Dict) -> str:
        """Create a post in a Forum Channel."""
        channel_name = args.get("channel_name")
        title = args.get("title")
        content = args.get("content")
        tag_names = args.get("tag_names", [])
        
        channel = self._find_channel(channel_name)
        if not channel:
            raise ValueError(f"Channel '{channel_name}' not found")
        
        if not isinstance(channel, discord.ForumChannel):
            raise ValueError(f"Channel '#{channel.name}' is not a Forum Channel. Use 'create_thread' for text channels.")
            
        # Resolve tags
        applied_tags = []
        if tag_names and channel.available_tags:
            for tag_name in tag_names:
                tag = discord.utils.find(lambda t: t.name.lower() == tag_name.lower(), channel.available_tags)
                if tag:
                    applied_tags.append(tag)
        
        thread_with_message = await channel.create_thread(
            name=title,
            content=content,
            applied_tags=applied_tags
        )
        
        # discord.py create_thread on Forum returns a thread (with starter_message)
        # or a tuple depending on version. In recent dpy, it returns a thread object.
        thread = thread_with_message
        
        return f"✅ Forum Post **'{title}'** created in <#{channel.id}> (ID: {thread.id})"
    
    async def _execute_search_messages(self, args: Dict) -> str:
        """Search for messages containing keywords."""
        channel_name = args.get("channel_name")
        query = args.get("query", "").lower()
        limit = min(args.get("limit", 10), 50)
        
        channel = self._find_channel(channel_name)
        if not channel:
            raise ValueError(f"Channel '{channel_name}' not found")
        
        results = []
        async for msg in channel.history(limit=500):  # Search last 500
            if query in msg.content.lower():
                timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
                author = msg.author.display_name
                snippet = msg.content[:150] + "..." if len(msg.content) > 150 else msg.content
                results.append(f"[{timestamp}] {author}: {snippet}")
                
                if len(results) >= limit:
                    break
        
        if not results:
            return f"No messages containing '{query}' found in #{channel.name}"
        
        return f"Found {len(results)} messages:\n" + "\n".join(results)
    
    async def _execute_get_config(self, args: Dict) -> str:
        """Get a configuration value."""
        key = args.get("key")
        
        # Check bot's config attribute or use in-memory store
        if hasattr(self.bot, 'config') and key in self.bot.config:
            value = self.bot.config[key]
        elif key in self.config_store:
            value = self.config_store[key]
        else:
            return f"Config '{key}' not found"
        
        return f"{key} = {value}"
    
    async def _execute_set_config(self, args: Dict) -> str:
        """Set a configuration value."""
        key = args.get("key")
        value = args.get("value")
        
        # Store in bot config or in-memory
        if hasattr(self.bot, 'config'):
            self.bot.config[key] = value
        else:
            self.config_store[key] = value
        
        return f"Config '{key}' set to '{value}'"
    
    async def _execute_list_channels(self, args: Dict) -> str:
        """List all channels."""
        category_filter = args.get("category", "").lower()
        
        result = []
        for category in self.guild.categories:
            if category_filter and category_filter not in category.name.lower():
                continue
            
            channels = [f"  • {ch.name}" for ch in category.channels if isinstance(ch, discord.TextChannel)]
            if channels:
                result.append(f"**{category.name}**")
                result.extend(channels)
        
        # Uncategorized
        uncategorized = [ch for ch in self.guild.text_channels if ch.category is None]
        if uncategorized and not category_filter:
            result.append("**Uncategorized**")
            result.extend([f"  • {ch.name}" for ch in uncategorized])
        
        return "\n".join(result) if result else "No channels found"
    
    async def _execute_get_channel_info(self, args: Dict) -> str:
        """Get channel information."""
        channel_name = args.get("channel_name")
        
        channel = self._find_channel(channel_name)
        if not channel:
            raise ValueError(f"Channel '{channel_name}' not found")
        
        info = [
            f"**Channel:** #{channel.name}",
            f"**ID:** {channel.id}",
            f"**Category:** {channel.category.name if channel.category else 'None'}",
            f"**Topic:** {channel.topic or 'No topic'}",
            f"**Created:** {channel.created_at.strftime('%Y-%m-%d')}",
            f"**Position:** {channel.position}"
        ]
        
        if isinstance(channel, discord.ForumChannel):
            info.append("**Type:** Forum Channel")
            if channel.available_tags:
                tags = [f"`{t.name}`" for t in channel.available_tags]
                info.append(f"**Available Tags:** {', '.join(tags)}")
            else:
                info.append("**Available Tags:** None")
        
        return "\n".join(info)

    async def _execute_create_forum_post(self, args: Dict) -> str:
        """Create a post in a Forum Channel."""
        channel_name = args.get("channel_name")
        title = args.get("title")
        content = args.get("content")
        tag_names = args.get("tag_names", [])
        
        channel = self._find_channel(channel_name)
        if not channel:
            raise ValueError(f"Channel '{channel_name}' not found")
        
        if not isinstance(channel, discord.ForumChannel):
            raise ValueError(f"Channel '#{channel.name}' is not a Forum Channel. Use 'create_thread' for text channels.")
            
        # Resolve tags with feedback
        applied_tags = []
        invalid_tags = []
        
        if tag_names:
            if channel.available_tags:
                for tag_name in tag_names:
                    tag = discord.utils.find(lambda t: t.name.lower() == tag_name.lower(), channel.available_tags)
                    if tag:
                        applied_tags.append(tag)
                    else:
                        invalid_tags.append(tag_name)
            else:
                invalid_tags = tag_names  # No tags available in channel
        
        thread_with_message = await channel.create_thread(
            name=title,
            content=content,
            applied_tags=applied_tags
        )
        
        # discord.py create_thread on Forum returns a thread (with starter_message)
        thread = thread_with_message
        
        result = f"✅ Forum Post **'{title}'** created in <#{channel.id}> (ID: {thread.id})"
        
        if applied_tags:
            tag_list = ", ".join([t.name for t in applied_tags])
            result += f"\n🏷️ **Tags applied:** {tag_list}"
            
        if invalid_tags:
            bad_tags = ", ".join(invalid_tags)
            result += f"\n⚠️ **Ignored tags (not found):** {bad_tags}\n*Tip: Use `get_channel_info` to see available tags.*"
            
        return result
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MEMORY TOOLS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _execute_remember(self, args: Dict) -> str:
        """Save information to permanent memory."""
        from bot.memory import get_memory_manager
        
        content = args.get("content")
        category = args.get("category", "general")
        
        if not content:
            raise ValueError("No content provided to remember")
        
        memory_manager = get_memory_manager()
        memory_id = memory_manager.save_memory(
            content=content,
            category=category,
            user_id=self.user.id,
            guild_id=self.guild.id
        )
        
        return f"🧠 Memory saved (ID: `{memory_id}`, category: `{category}`)\n\n*\"{content[:100]}{'...' if len(content) > 100 else ''}\"*"
    
    async def _execute_recall(self, args: Dict) -> str:
        """Search and retrieve from permanent memory."""
        from bot.memory import get_memory_manager
        
        query = args.get("query")
        category = args.get("category")
        
        if not query:
            raise ValueError("No query provided for recall")
        
        memory_manager = get_memory_manager()
        memories = memory_manager.recall(query, n_results=5, category=category)
        
        if not memories:
            return f"🔍 No memories found matching: *{query}*"
        
        result = f"🧠 **Found {len(memories)} memories matching: *{query}***\n\n"
        for i, mem in enumerate(memories, 1):
            timestamp = mem['metadata'].get('timestamp', 'unknown')[:10]
            cat = mem['metadata'].get('category', 'general')
            relevance = int(mem.get('relevance', 0) * 100)
            result += f"**{i}.** [{cat}] ({timestamp}) - {relevance}% match\n"
            result += f"   {mem['content'][:200]}{'...' if len(mem['content']) > 200 else ''}\n\n"
        
        return result
    
    async def _execute_forget(self, args: Dict) -> str:
        """Delete a memory by ID."""
        from bot.memory import get_memory_manager
        
        memory_id = args.get("memory_id")
        
        if not memory_id:
            raise ValueError("No memory ID provided")
        
        memory_manager = get_memory_manager()
        success = memory_manager.forget(memory_id)
        
        if success:
            return f"🗑️ Memory `{memory_id}` deleted successfully."
        else:
            return f"⚠️ Failed to delete memory `{memory_id}`. It may not exist."
    
    async def _execute_list_memories(self, args: Dict) -> str:
        """List recent memories."""
        from bot.memory import get_memory_manager
        
        limit = args.get("limit", 10)
        
        memory_manager = get_memory_manager()
        memories = memory_manager.get_recent_memories(limit=limit)
        
        if not memories:
            return "📭 No memories stored yet."
        
        result = f"🧠 **Recent Memories ({len(memories)})**\n\n"
        for mem in memories:
            timestamp = mem['metadata'].get('timestamp', 'unknown')[:10]
            cat = mem['metadata'].get('category', 'general')
            content = mem['content'][:80] + "..." if len(mem['content']) > 80 else mem['content']
            result += f"• `{mem['id']}` [{cat}] ({timestamp}): {content}\n"
        
        return result
    
    # ═══════════════════════════════════════════════════════════════════════════
    # IMAGE GENERATION TOOLS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _execute_generate_image(self, args: Dict) -> str:
        """Generate an image from a prompt using Flux Pro."""
        from bot.image_gen import get_image_generator
        
        prompt = args.get("prompt")
        width = args.get("width", 1024)
        height = args.get("height", 1024)
        channel_name = args.get("channel_name")
        
        if not prompt:
            raise ValueError("No prompt provided for image generation")
        
        # Clamp dimensions
        width = max(256, min(2048, width))
        height = max(256, min(2048, height))
        
        # Find target channel
        if channel_name:
            channel = self._find_channel(channel_name)
            if not channel:
                raise ValueError(f"Channel '{channel_name}' not found")
        else:
            # Use current channel context
            channel = self.current_channel
        
        if channel:
            # Use interactive view for model selection
            from bot.image_views import send_image_generation_prompt
            
            await send_image_generation_prompt(
                channel=channel,
                user=self.user,
                prompt=prompt,
                reference_urls=None  # No reference for text-to-image
            )
            
            return f"🎨 **Image generation started!**\n\nI've sent a model selection menu. Please select your preferred model from the dropdown.\n\n**Prompt:** {prompt[:100]}..."
        else:
            return "⚠️ No channel context available for image generation. Please use the `/image` command."
    
    async def _execute_enhance_and_generate(self, args: Dict) -> str:
        """Enhance a simple idea into a detailed prompt, then generate."""
        from bot.image_gen import get_image_generator
        
        idea = args.get("idea")
        style = args.get("style", "artistic")
        width = args.get("width", 1024)
        height = args.get("height", 1024)
        
        if not idea:
            raise ValueError("No idea provided for image generation")
        
        # Clamp dimensions
        width = max(256, min(2048, width))
        height = max(256, min(2048, height))
        
        # Style-specific prompt enhancements
        style_prompts = {
            "realistic": "photorealistic, highly detailed, 8k, professional photography",
            "artistic": "artistic, creative, vibrant colors, masterful composition",
            "cyberpunk": "cyberpunk aesthetic, neon lights, futuristic, dark atmosphere, rain",
            "minimalist": "minimalist design, clean lines, simple, elegant, whitespace",
            "logo": "professional logo design, vector art style, clean, memorable, brand identity",
            "icon": "app icon, simple, recognizable, clean design, centered",
            "photographic": "professional photograph, DSLR, sharp focus, natural lighting",
            "3d": "3D render, octane render, realistic materials, studio lighting",
            "anime": "anime style, Japanese animation, vibrant, expressive",
            "abstract": "abstract art, shapes, colors, non-representational, modern art"
        }
        
        style_suffix = style_prompts.get(style, style_prompts["artistic"])
        enhanced_prompt = f"{idea}, {style_suffix}"
        
        generator = get_image_generator()
        
        # Use enhance=True for Pollinations auto-enhancement
        image_data, url_or_error = await generator.generate(
            prompt=enhanced_prompt,
            width=width,
            height=height,
            enhance=True
        )
        
        if image_data:
            return f"🎨 Image generated with enhanced prompt!\n\n**Original idea:** {idea}\n**Style:** {style}\n**Enhanced prompt:** {enhanced_prompt[:150]}...\n**Size:** {width}x{height}"
        else:
            return f"⚠️ Failed to generate image: {url_or_error}"
    
    async def _execute_edit_image(self, args: Dict) -> str:
        """Edit an existing image using image-to-image (Kontext model)."""
        from bot.image_gen import get_image_generator
        
        reference_url = args.get("reference_url")
        prompt = args.get("prompt")
        width = args.get("width", 1024)
        height = args.get("height", 1024)
        
        if not reference_url:
            raise ValueError("No reference image URL provided")
        if not prompt:
            raise ValueError("No prompt provided for editing")
        
        # Clamp dimensions
        width = max(256, min(2048, width))
        height = max(256, min(2048, height))
        
        generator = get_image_generator()
        
        # Use interactive view for model selection
        if self.current_channel:
            from bot.image_views import send_image_generation_prompt
            
            await send_image_generation_prompt(
                channel=self.current_channel,
                user=self.user,
                prompt=prompt,
                reference_urls=[reference_url]
            )
            
            return f"🎨 **Image editing started!**\n\nI've sent a model selection menu with your reference image.\n\n**Changes:** {prompt[:100]}..."
        else:
            return "⚠️ No channel context available for image editing. Please use the `/image_edit` command."
    
    async def _execute_pollen_status(self, args: Dict) -> str:
        """Get current pollen usage status."""
        from bot.pollen_manager import get_pollen_manager
        
        manager = get_pollen_manager()
        return manager.get_usage_report()

    # ═══════════════════════════════════════════════════════════════════════════
    # SERVER MANAGEMENT IMPLEMENTATION
    # ═══════════════════════════════════════════════════════════════════════════

    def _find_role(self, role_name: str) -> Optional[discord.Role]:
        """Find a role by name (case-insensitive partial match) or ID."""
        role_name = str(role_name).lower()
        
        # Try ID match
        if role_name.isdigit():
            role = self.guild.get_role(int(role_name))
            if role: return role

        # Try name match
        for role in self.guild.roles:
            if role.name.lower() == role_name:
                return role
            if role_name in role.name.lower():
                return role
        return None

    def _find_member(self, user_id: str) -> Optional[discord.Member]:
        """Find a member by ID, mention, or name."""
        # Strip mention syntax
        user_id = user_id.replace('<@', '').replace('!', '').replace('>', '')
        
        if user_id.isdigit():
            return self.guild.get_member(int(user_id))
            
        # Try name search
        return discord.utils.find(lambda m: m.name.lower() == user_id.lower(), self.guild.members)

    async def _execute_manage_role(self, args: Dict) -> str:
        """Create, delete, or edit a role."""
        if not self.guild:
            raise ValueError("This tool must be used in a server.")
            
        action = args.get("action")
        role_name = args.get("role_name")
        color_hex = args.get("color_hex")
        hoist = args.get("hoist")
        permissions_data = args.get("permissions")
        
        # Parse color
        color = discord.Color.default()
        if color_hex:
            if color_hex.lower() == 'random':
                color = discord.Color.random()
            else:
                try:
                    color = discord.Color(int(color_hex.replace('#', ''), 16))
                except ValueError:
                    pass # Ignore invalid color

        # Parse Permissions
        repo_perms = discord.Permissions.default()
        if permissions_data:
            if permissions_data.get('all') is True:
                repo_perms = discord.Permissions.all()
            else:
                for perm, value in permissions_data.items():
                    if hasattr(repo_perms, perm):
                        setattr(repo_perms, perm, value)

        if action == "create":
            role = await self.guild.create_role(
                name=role_name,
                color=color,
                hoist=hoist if hoist is not None else False,
                permissions=repo_perms,
                reason="Created by AI Agent"
            )
            return f"✅ Role **{role.name}** created successfully (ID: {role.id})."

        elif action == "delete":
            role = self._find_role(role_name)
            if not role:
                return f"⚠️ Role '{role_name}' not found."
            await role.delete(reason="Deleted by AI Agent")
            return f"🗑️ Role **{role.name}** deleted."

        elif action == "edit":
            role = self._find_role(role_name)
            if not role:
                return f"⚠️ Role '{role_name}' not found."
            
            edit_kwargs = {}
            if color_hex: edit_kwargs['color'] = color
            if hoist is not None: edit_kwargs['hoist'] = hoist
            if permissions_data: edit_kwargs['permissions'] = repo_perms
            
            await role.edit(**edit_kwargs, reason="Edited by AI Agent")
            return f"✏️ Role **{role.name}** updated."

        return "Invalid action."

    async def _execute_assign_role(self, args: Dict) -> str:
        """Add/remove roles from a user."""
        action = args.get("action")
        role_name = args.get("role_name")
        user_identifier = args.get("user_id")
        
        member = self._find_member(user_identifier)
        if not member:
            return f"⚠️ User '{user_identifier}' not found."
            
        role = self._find_role(role_name)
        if not role:
            return f"⚠️ Role '{role_name}' not found."
            
        if action == "add":
            if role in member.roles:
                return f"User {member.display_name} already has role {role.name}."
            await member.add_roles(role, reason="Assigned by AI Agent")
            return f"✅ Role **{role.name}** added to {member.display_name}."
            
        elif action == "remove":
            if role not in member.roles:
                return f"User {member.display_name} does not have role {role.name}."
            await member.remove_roles(role, reason="Removed by AI Agent")
            return f"🚫 Role **{role.name}** removed from {member.display_name}."

        return "Invalid action."

    async def _execute_moderate_user(self, args: Dict) -> str:
        """Kick, ban, or timeout a user."""
        action = args.get("action")
        user_identifier = args.get("user_id")
        reason = args.get("reason", "No reason provided")
        duration = args.get("duration_minutes", 60)
        
        member = self._find_member(user_identifier)
        if not member:
            return f"⚠️ User '{user_identifier}' not found."
            
        if action == "kick":
            await member.kick(reason=f"[AI] {reason}")
            return f"🥾 **{member.display_name}** has been kicked. Reason: {reason}"
            
        elif action == "ban":
            await member.ban(reason=f"[AI] {reason}")
            return f"🔨 **{member.display_name}** has been banned. Reason: {reason}"
            
        elif action == "timeout":
            until = datetime.utcnow() + timedelta(minutes=duration)
            await member.timeout(until, reason=f"[AI] {reason}")
            return f"⏳ **{member.display_name}** has been timed out for {duration} minutes. Reason: {reason}"

        elif action == "remove_timeout":
            await member.timeout(None, reason=f"[AI] Timeout removed")
            return f"✅ Timeout removed from **{member.display_name}**."

        elif action == "unban":
             # Unban requires fetching banned user from guild bans, which is an async iterator
             # Simple implementation assuming user ID is provided for unban
             if not user_identifier.isdigit():
                 return "⚠️ For unbanning, please provide the numeric User ID."
             user_obj = discord.Object(id=int(user_identifier))
             await self.guild.unban(user_obj, reason=f"[AI] {reason}")
             return f"🔓 User ID **{user_identifier}** unbanned."

        return "Invalid action."

    async def _execute_create_temp_channel(self, args: Dict) -> str:
        """Create a channel that auto-deletes."""
        channel_name = args.get("channel_name")
        category_name = args.get("category_name")
        duration = args.get("duration_minutes", 60)
        
        category = None
        if category_name:
            category = discord.utils.get(self.guild.categories, name=category_name)
            
        channel = await self.guild.create_text_channel(
            name=channel_name,
            category=category,
            topic=f"Temporary channel. Auto-deletes in {duration} minutes.",
            reason="Temp Channel created by AI"
        )
        
        # Register with TempChannelManager
        if hasattr(self.bot, 'temp_channel_manager') and self.bot.temp_channel_manager:
            expiry_ts = self.bot.temp_channel_manager.add_channel(channel.id, duration)
            expiry_dt = datetime.fromtimestamp(expiry_ts).strftime('%H:%M')
            return f"⏱️ Created temp channel {channel.mention}. It will be deleted around **{expiry_dt}** ({duration}m)."
        else:
            return f"✅ Created channel {channel.mention}, but **Warning:** TempChannelManager is not active, so auto-delete won't work."

    async def _execute_delete_messages(self, args: Dict) -> str:
        """Delete messages from a channel."""
        channel_name = args.get("channel_name")
        count = args.get("count")
        hours = args.get("hours")
        
        # Determine channel
        if channel_name:
            channel = self._find_channel(channel_name)
            if not channel:
                raise ValueError(f"Channel '{channel_name}' not found")
        else:
            channel = self.current_channel
            if not channel:
                raise ValueError("No channel specified and no current channel context.")
        
        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
             return f"⚠️ Cannot delete messages in #{channel.name} (unsupported channel type)."

        # Determine limits
        limit = 100 # Safety default
        if count:
            limit = min(int(count), 100) # Cap at 100 per call for safety
        
        after_date = None
        if hours:
            after_date = datetime.utcnow() - timedelta(hours=float(hours))
            # If time is specified, we might verify more messages to find the ones in range,
            # but purge() 'after' param handles this efficiently.
            # If both count and hours are provided, purge respects both (deletes N messages that are also after X).
            # If only hours is provided, we need a generic limit or it purges everything in that time.
            if not count:
                limit = 500 # Scan up to 500 messages if only time is given
        
        try:
            # Execute Purge
            deleted = await channel.purge(limit=limit, after=after_date, bulk=True)
            return f"🗑️ Deleted **{len(deleted)}** messages in {channel.mention}."
        except discord.Forbidden:
            return f"⚠️ I don't have permission to delete messages in {channel.mention}."
        except discord.HTTPException as e:
            return f"⚠️ Error deleting messages: {e}"

    # ═══════════════════════════════════════════════════════════════════════════
    # AI SHOPPING IMPLEMENTATION
    # ═══════════════════════════════════════════════════════════════════════════

    async def _execute_manage_product(self, args: Dict) -> str:
        """Admin: Create/Update/Delete products."""
        from bot.managers.product_manager import ProductManager
        # Note: Ideally inject this or get from bot instance.
        # For now, we instantiate to access the singleton-like persistent files.
        # But best practice is to attach it to bot.
        # Let's assume bot has 'ecommerce_cog' or we can pass it, 
        # but for simplicity we'll check if Cog is loaded or just instantiate assuming file lock is handled (JSON is file based).
        # Actually, let's look for the Cog.
        
        ecommerce_cog = self.bot.get_cog("Ecommerce")
        if not ecommerce_cog:
            return "❌ Ecommerce system is not active."
        
        manager = ecommerce_cog.manager
        
        action = args.get("action")
        p_id = args.get("product_id")
        name = args.get("name")
        price = args.get("price")
        desc = args.get("description")
        image_url = args.get("image_url")
        
        if action == "list":
            products = manager.get_all_products()
            if not products:
                return "📭 No products in catalog."
            
            res = "**📦 Product Catalog:**\n"
            for p in products:
                res += f"• `{p['id']}`: {p['name']} - R${p['price']:.2f}\n"
            return res

        if not p_id:
            return "⚠️ `product_id` is required."

        if action == "delete":
            if manager.delete_product(p_id):
                return f"🗑️ Product `{p_id}` deleted."
            else:
                return f"⚠️ Product `{p_id}` not found."

        # Handle 'last_image' logic for Create/Update
        if image_url == "last_image":
            # Search last 20 messages in current channel for an image
            image_url = None
            if self.current_channel:
                async for msg in self.current_channel.history(limit=20):
                    if msg.attachments:
                        # Use first attachment if it's an image
                        for att in msg.attachments:
                            if att.content_type and "image" in att.content_type:
                                image_url = att.url
                                break
                    if image_url: break
            
            if not image_url:
                return "⚠️ Could not find a recent image in chat to use for the product."

        if action == "create":
            if not all([name, price, desc]):
                return "⚠️ Name, Price, and Description are required for creation."
            
            manager.add_product(p_id, name, float(price), desc, image_url=image_url)
            return f"✅ Product **{name}** created! (ID: `{p_id}`)"

        elif action == "update":
            # Get existing
            existing = manager.get_product(p_id)
            if not existing:
                return f"⚠️ Product `{p_id}` not found."
            
            # Merge updates
            new_name = name if name else existing['name']
            new_price = float(price) if price else existing['price']
            new_desc = desc if desc else existing['description']
            new_img = image_url if image_url else existing.get('image_url')
            
            manager.add_product(p_id, new_name, new_price, new_desc, image_url=new_img)
            return f"✏️ Product **{new_name}** updated."
            
        return "Invalid action."

    async def _execute_shopping_assistant(self, args: Dict) -> str:
        """User: Search products, add to cart, checkout."""
        ecommerce_cog = self.bot.get_cog("Ecommerce")
        if not ecommerce_cog:
            return "❌ Ecommerce system is not active."
        
        manager = ecommerce_cog.manager
        
        action = args.get("action")
        query = args.get("query")
        p_id = args.get("product_id")
        
        if action == "search":
            products = manager.get_all_products()
            matches = []
            if not query:
                matches = products[:5] # Show first 5
            else:
                query = query.lower()
                for p in products:
                    if query in p['name'].lower() or query in p['description'].lower():
                        matches.append(p)
            
            if not matches:
                return f"🔍 No products found matching '{query}'."
            
            res = f"🛍️ **Found {len(matches)} products:**\n"
            for p in matches:
                res += f"• **{p['name']}** (R${p['price']:.2f})\n  *ID: `{p['id']}`*\n"
            return res

        elif action == "add_to_cart":
            if not p_id: return "⚠️ Product ID required."
            
            prod = manager.get_product(p_id)
            if not prod: return f"⚠️ Product `{p_id}` not found."
            
            manager.add_to_cart(self.user.id, p_id)
            return f"🛒 Added **{prod['name']}** to your cart."

        elif action == "view_cart":
             items = manager.get_cart(self.user.id)
             if not items: return "🛒 Your cart is empty."
             
             total = sum(i['price'] for i in items)
             res = "**Your Shopping Cart:**\n"
             for i in items:
                 res += f"• {i['name']} - R${i['price']:.2f}\n"
             res += f"\n**Total: R${total:.2f}**"
             return res

        elif action == "checkout":
            from bot.ecommerce_views import start_checkout_flow
            # Trigger the interactive checkout flow
            # We need to simulate an interaction or send a message with the View
            # Since this is tool execution, we return a text response, but we can trigger the view here via channel send.
            
            # Since start_checkout_flow expects an interaction to reply to, we have to adapt.
            # But the AI simply returning text might be boring.
            # Let's call the `start_checkout_flow` logic manually but adapting it for a plain channel.
            
            items = manager.get_cart(self.user.id)
            if not items: return "⚠️ Cart is empty."

            # We can't use interaction here easily if it's just a tool call response string.
            # BUT we can instruct the AI to tell the user to click the button, OR we can send the message ourself.
            
            # Let's send a message to channel with the Checkout Button
            from bot.ecommerce_views import CartView
            embed = discord.Embed(title="🛍️ Ready to Checkout?", description="Click below to finalize your order.", color=discord.Color.blue())
            await self.current_channel.send(content=self.user.mention, embed=embed, view=CartView(manager))
            
            return "✅ I've sent the checkout menu to the channel! Click 'Checkout' to proceed."

        return "Invalid action."

    # ═══════════════════════════════════════════════════════════════════════════
    # AI SERVER CONTEXT & MUTATIONS IMPLEMENTATION
    # ═══════════════════════════════════════════════════════════════════════════

    async def _execute_get_server_context(self, args: Dict) -> str:
        """Get a structured, compact layout representation of roles, categories, and channels."""
        if not self.guild:
            return "⚠️ This tool must be used in a server."
            
        roles_text = ["**Roles:**"]
        for role in sorted(self.guild.roles, key=lambda r: r.position, reverse=True):
            if role.is_default(): continue
            admin = " [ADMIN]" if role.permissions.administrator else ""
            roles_text.append(f"- {role.name} (ID: {role.id}){admin}")
            
        channels_text = ["\n**Channels & Categories:**"]
        for category in self.guild.categories:
            channels_text.append(f"📁 {category.name} (ID: {category.id})")
            for channel in category.channels:
                type_str = str(channel.type)
                channels_text.append(f"  └─ {channel.name} [{type_str}] (ID: {channel.id})")
                
        # Uncategorized channels
        uncategorized = [ch for ch in self.guild.channels if ch.category is None]
        if uncategorized:
            channels_text.append("📁 Uncategorized")
            for channel in uncategorized:
                type_str = str(channel.type)
                channels_text.append(f"  └─ {channel.name} [{type_str}] (ID: {channel.id})")
                
        overwrites_text = ["\n**Explicit Permission Overwrites:**"]
        for channel in self.guild.channels:
            if getattr(channel, "overwrites", None) is None: continue
            for target, overwrite in channel.overwrites.items():
                target_type = "Role" if isinstance(target, discord.Role) else "Member"
                # Just show non-default overwrites to save tokens
                allows = [p for p, v in overwrite if v is True]
                denies = [p for p, v in overwrite if v is False]
                if allows or denies:
                    overwrites_text.append(f"- #{channel.name} -> {target_type} '{target.name}':")
                    if allows: overwrites_text.append(f"    Allow: {', '.join(allows)}")
                    if denies: overwrites_text.append(f"    Deny: {', '.join(denies)}")

        return "\n".join(roles_text + channels_text + overwrites_text)

    async def _execute_manage_channel(self, args: Dict) -> str:
        """Create, edit, or delete a channel."""
        action = args.get("action")
        channel_name = args.get("channel_name")
        type_str = args.get("type")
        new_name = args.get("new_name")
        category_name = args.get("category_name")
        dry_run = args.get("dry_run", True)
        
        if not self.guild:
            return "⚠️ This tool must be used in a server."
            
        if not channel_name:
            return "⚠️ 'channel_name' is required."
            
        if action == "create":
            if dry_run:
                return f"[DRY-RUN] Would create {type_str} channel '{channel_name}' in category '{category_name}'."
            
            category = discord.utils.get(self.guild.categories, name=category_name) if category_name else None
            
            if type_str == "text":
                channel = await self.guild.create_text_channel(name=channel_name, category=category, reason="AI Agent")
            elif type_str == "voice":
                channel = await self.guild.create_voice_channel(name=channel_name, category=category, reason="AI Agent")
            elif type_str == "category":
                channel = await self.guild.create_category_channel(name=channel_name, reason="AI Agent")
            elif type_str == "forum":
                channel = await self.guild.create_forum(name=channel_name, category=category, reason="AI Agent")
            else:
                return f"⚠️ Unsupported channel type '{type_str}'"
            return f"✅ Created {type_str} channel '{channel.name}' (ID: {channel.id})."
            
        elif action == "edit":
            channel = self._find_channel(channel_name)
            if not channel:
                return f"⚠️ Channel '{channel_name}' not found."
                
            if dry_run:
                return f"[DRY-RUN] Would rename channel '{channel_name}' to '{new_name}' (category: '{category_name}')."
                
            edit_kwargs = {}
            if new_name:
                edit_kwargs['name'] = new_name
            if category_name:
                category = discord.utils.get(self.guild.categories, name=category_name)
                if category: edit_kwargs['category'] = category
                
            await channel.edit(**edit_kwargs, reason="AI Agent")
            return f"✅ Channel '{channel_name}' updated."
            
        elif action == "delete":
            channel = self._find_channel(channel_name)
            if not channel:
                return f"⚠️ Channel '{channel_name}' not found."
                
            if dry_run:
                return f"[DRY-RUN] Would delete channel '{channel_name}'."
                
            await channel.delete(reason="AI Agent")
            return f"✅ Channel '{channel_name}' deleted."
            
        return "⚠️ Invalid action."

    async def _execute_modify_channel_permissions(self, args: Dict) -> str:
        """Set permission overrides for a role or user on a specific channel."""
        channel_name = args.get("channel_name")
        target_name = args.get("target_name")
        allow_dict = args.get("allow") or {}
        deny_dict = args.get("deny") or {}
        dry_run = args.get("dry_run", True)
        
        if not self.guild:
            return "⚠️ This tool must be used in a server."
        
        channel = self._find_channel(channel_name)
        if not channel:
            return f"⚠️ Channel '{channel_name}' not found."
            
        target = self._find_role(target_name) or self._find_member(target_name)
        if not target:
            return f"⚠️ Role or member '{target_name}' not found."
            
        if dry_run:
            return f"[DRY-RUN] Would set permission overwrites for '{target_name}' on channel '{channel_name}': allow={allow_dict}, deny={deny_dict}."
            
        overwrite = channel.overwrites_for(target)
        for perm, value in allow_dict.items():
            if hasattr(overwrite, perm):
                setattr(overwrite, perm, True)
        for perm, value in deny_dict.items():
            if hasattr(overwrite, perm):
                setattr(overwrite, perm, False)
                
        await channel.set_permissions(target, overwrite=overwrite, reason="AI Agent")
        return f"✅ Permissions updated for '{target_name}' on channel '{channel_name}'."


def check_permission(user: discord.Member, required_permissions: list) -> bool:
    """Check if user has any of the required permissions."""
    if not required_permissions:
        return True
    
    user_perms = user.guild_permissions
    
    for perm in required_permissions:
        if getattr(user_perms, perm, False):
            return True
    
    return False
