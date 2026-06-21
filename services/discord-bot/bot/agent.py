"""
L2 SYSTEMS // AI Agent
Main agent orchestration with function calling loop.
"""

import discord
from openai import AsyncOpenAI
from typing import Optional, List, Dict, Any
import json
import logging
import os

from bot.tools.registry import TOOLS, TOOL_PERMISSIONS
from bot.tools.executor import ToolExecutor, check_permission

logger = logging.getLogger(__name__)

class L2Agent:
    """
    AI Agent with tool execution capabilities.
    Uses OpenRouter with function calling to enable Discord actions.
    """
    
    def __init__(self, bot, key_manager, supabase_client=None):
        self.bot = bot
        self.key_manager = key_manager
        self.supabase_client = supabase_client
        self.model = "mistralai/devstral-2512:free"
        self.max_tool_iterations = 5  # Prevent infinite loops
    
    async def run(
        self,
        query: str,
        guild: discord.Guild,
        user: discord.Member,
        channel: discord.TextChannel,
        system_prompt: str = None
    ) -> str:
        """
        Run the agent with the given query.
        
        Args:
            query: User's natural language request
            guild: Discord guild context
            user: User making the request
            channel: Channel where the request was made
            system_prompt: Optional custom system prompt
            
        Returns:
            Final response string
        """
        # Load system prompt if not provided
        if not system_prompt:
            system_prompt = self._load_system_prompt()
        
        # Get memory context (auto-retrieve relevant memories)
        memory_context = ""
        try:
            from bot.memory import get_memory_manager
            memory_manager = get_memory_manager()
            memory_context = memory_manager.get_memory_context(query)
            if memory_context:
                memory_context = f"\n\n[PERMANENT MEMORY]\n{memory_context}\n"
        except Exception as e:
            logger.warning(f"Failed to load memory context: {e}")
        
        # Add agent-specific instructions
        agent_instructions = """

## AGENT MODE ACTIVE
You have access to tools to interact with this Discord server. When the user asks you to perform actions (send messages, read channels, summarize, etc.), use the appropriate tool.

**Available Tools:**
- send_message: Post to any channel
- read_channel: Get recent messages
- summarize_channel: Summarize discussions (up to 1000 msgs, 3 months)
- pin_message: Pin important messages
- create_thread: Start a thread
- search_messages: Find messages by keyword
- list_channels: List server channels
- get_channel_info: Channel details
- get_config / set_config: Bot configuration
- **remember**: Save info to permanent memory
- **recall**: Search permanent memory
- **list_memories**: Show stored memories
- **forget**: Delete a memory
- **generate_image**: Create images (shows model dropdown for user to select)
- **enhance_and_generate**: Improve a simple idea and generate image
- **edit_image**: Edit existing image from attached URL (shows model dropdown)
- **manage_role**: Create, delete, or edit roles (color, permissions, etc.).
- **assign_role**: Add/remove roles from users.
- **moderate_user**: Kick, Ban, Timeout, or Unban users.
- **create_temp_channel**: Create auto-deleting text channels.
- **create_forum_post**: Create a post (thread) in a Forum Channel with optional tags.
- **delete_messages**: Purge messages by count (e.g. 10) or time (e.g. 24h).
- **manage_product**: [Admin] Create/Update/Delete shop products (can use attached images).
- **shopping_assistant**: Search catalog, add to cart, or start checkout flow.
- **pollen_status**: Check API usage and remaining budget

**Current Context:**
- Server: {guild_name}
- Channel: #{channel_name}
- User: {user_name}
{memory_section}
If the user's request requires an action, use the appropriate tool. If it's just a question, answer directly.
When user asks to "remember" something, use the remember tool. When they ask "do you remember" or reference past info, use the recall tool.
**Important**: When the user explicitly asks you to SEND a message to a channel (e.g. "Send this update to #general"), execute the `send_message` tool. **DO NOT** reply to the user with a verbose confirmation like "Message sent to...". Instead, just reply with a simple "✅", "Done", or "Sent", or nothing at all if part of a seamless flow. The user wants professional, clutter-free operation.
**CRITICAL**: If the user asks you to **Create/Generate X AND Post it**, do NOT output the generated content to the chat. Generate it internally and pass it directly to the `content` argument of `create_forum_post` or `send_message`. Your goal is to perform the action, not just show the draft.
**ANTI-LOOP RULE**: Once you have successfully executed a tool (especially `create_forum_post` or `send_message`) and received a confirmation ID, **STOP** calling tools. Do not verify, do not edit, do not post again. Just reply to the user confirming it's done. Duplicate posts are forbidden.
""".format(
            guild_name=guild.name,
            channel_name=channel.name,
            user_name=user.display_name,
            memory_section=memory_context
        )
        
        full_system_prompt = system_prompt + agent_instructions
        
        # Initialize tool executor with channel context
        executor = ToolExecutor(self.bot, guild, user, current_channel=channel)
        
        # Prepare messages
        messages = [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": query}
        ]
        
        # Agent loop
        iterations = 0
        executed_tools = set() # Track executed tools to prevent loops
        
        while iterations < self.max_tool_iterations:
            iterations += 1
            
            # Call LLM with tools
            response = await self._call_llm(messages, tools=TOOLS)
            
            if not response:
                return "Error: Failed to get response from AI."
            
            # Check if there are tool calls
            if not response.tool_calls:
                # No tool calls, return the content
                # CRITICAL: If we just performed a posting action, suppress the verbose output
                if "create_forum_post" in executed_tools or "create_thread" in executed_tools:
                    return "✅ Created."
                if "send_message" in executed_tools:
                    return "✅ Sent."
                    
                return response.content or "I processed your request."
            
            # Process tool calls
            tool_results = []
            for tool_call in response.tool_calls:
                tool_name = tool_call.function.name
                
                # Parse arguments
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}
                
                # ANTI-LOOP: Check for duplicate major actions
                if tool_name in ["create_forum_post", "create_thread", "send_message"] and tool_name in executed_tools:
                    logger.warning(f"Prevented duplicate execution of {tool_name}")
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": json.dumps({"error": "Action already performed. Do not repeat."})
                    })
                    continue

                logger.info(f"Executing tool: {tool_name} with args: {arguments}")
                
                # Check permissions
                required_perms = TOOL_PERMISSIONS.get(tool_name, [])
                if not check_permission(user, required_perms):
                    result = {
                        "success": False,
                        "error": f"Permission denied for tool '{tool_name}'"
                    }
                else:
                    # Execute tool
                    result = await executor.execute(tool_name, arguments)
                    executed_tools.add(tool_name)
                
                # Log to local SQLite database
                try:
                    from database.database import DatabaseManager
                    await DatabaseManager.log_event(
                        event_type="TOOL_EXECUTION",
                        actor_id=str(user.id),
                        trace_id=f"TR-{tool_name[:6].upper()}",
                        payload={
                            "action": f"tool:{tool_name}",
                            "arguments": arguments,
                            "result": result,
                            "guild_id": guild.id
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to log tool execution to local DB: {e}")
                
                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps(result)
                })
            
            # Add assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in response.tool_calls
                ]
            })
            
            # Add tool results
            messages.extend(tool_results)
        
        return "Maximum tool iterations reached."
    
    async def _call_llm(self, messages: List[Dict], tools: List[Dict] = None):
        """Call the LLM with optional tools."""
        current_key = self.key_manager.get_current_key()
        if not current_key:
            logger.error("No API key available")
            return None
        
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=current_key
        )
        
        try:
            kwargs = {
                "model": self.model,
                "messages": messages
            }
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            completion = await client.chat.completions.create(**kwargs)
            return completion.choices[0].message
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            
            # Try with backup key
            new_key = self.key_manager.switch_key()
            if new_key:
                client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=new_key
                )
                try:
                    completion = await client.chat.completions.create(**kwargs)
                    return completion.choices[0].message
                except Exception as e2:
                    logger.error(f"LLM retry failed: {e2}")
            
            return None
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from file."""
        try:
            with open("bot/system_context.md", "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Failed to load system_context.md: {e}")
            return "You are L2-ORACLE, an AI assistant for L2 Systems."
