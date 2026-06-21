"""
L2 SYSTEMS // Tool Registry
Defines all available tools for the AI agent using OpenAI function calling format.
"""

import discord

# ═══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS (OpenAI Function Calling Format)
# ═══════════════════════════════════════════════════════════════════════════════

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send a message to a specific Discord channel. Use this when the user asks you to post, announce, or send something to a channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "The name of the channel to send to (without #). Examples: 'announcements', 'command-center', 'revenue-stream'"
                    },
                    "content": {
                        "type": "string",
                        "description": "The message content to send. Use Discord markdown formatting."
                    }
                },
                "required": ["channel_name", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_channel",
            "description": "Read recent messages from a Discord channel. Use this to get context about what was discussed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "The name of the channel to read from (without #)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of messages to read (default: 20, max: 100)",
                        "default": 20
                    }
                },
                "required": ["channel_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_channel",
            "description": "Read messages from a channel and provide a comprehensive summary. Supports large context (up to 1000 messages) with extended time ranges.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "The name of the channel to summarize"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of messages to include in summary (default: 200, max: 1000)",
                        "default": 200
                    },
                    "time_filter": {
                        "type": "string",
                        "description": "Time filter: 'today', 'yesterday', '3days', 'week', '2weeks', 'month', '3months', or 'all'",
                        "enum": ["today", "yesterday", "3days", "week", "2weeks", "month", "3months", "all"],
                        "default": "all"
                    }
                },
                "required": ["channel_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pin_message",
            "description": "Pin a message in a channel. Use when user asks to pin something important.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "The channel where the message is"
                    },
                    "message_id": {
                        "type": "string",
                        "description": "The ID of the message to pin"
                    }
                },
                "required": ["channel_name", "message_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_thread",
            "description": "Create a new thread in a channel or from a message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "The channel to create thread in"
                    },
                    "thread_name": {
                        "type": "string",
                        "description": "Name for the new thread"
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Optional: Message ID to create thread from",
                        "default": None
                    }
                },
                "required": ["channel_name", "thread_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_forum_post",
            "description": "Create a new post in a Forum Channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "Name of the Forum Channel"
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the post"
                    },
                    "content": {
                        "type": "string",
                        "description": "Body content of the post"
                    },
                    "tag_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: List of tag names to apply (e.g. ['Help', 'Bug'])"
                    }
                },
                "required": ["channel_name", "title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_messages",
            "description": "Search for messages containing specific keywords in a channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "The channel to search in"
                    },
                    "query": {
                        "type": "string",
                        "description": "Keywords to search for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["channel_name", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_config",
            "description": "Get a bot configuration value.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Configuration key to retrieve"
                    }
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_config",
            "description": "Set a bot configuration value. Requires admin permission.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Configuration key to set"
                    },
                    "value": {
                        "type": "string",
                        "description": "Value to set"
                    }
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_channels",
            "description": "List all channels in the server, optionally filtered by category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional: Filter by category name"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_channel_info",
            "description": "Get detailed information about a specific channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "Name of the channel"
                    }
                },
                "required": ["channel_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save important information to permanent memory. Use when user asks to 'remember this', 'save this', or 'don't forget'. Memories are retrieved automatically in future conversations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The information to remember"
                    },
                    "category": {
                        "type": "string",
                        "description": "Category: 'fact', 'decision', 'task', 'preference', 'conversation', 'general'",
                        "enum": ["fact", "decision", "task", "preference", "conversation", "general"],
                        "default": "general"
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Search and retrieve information from permanent memory. Use when user asks 'do you remember', 'what did we discuss', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in memory"
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional: Filter by category",
                        "enum": ["fact", "decision", "task", "preference", "conversation", "general"]
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "forget",
            "description": "Delete a specific memory by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "The ID of the memory to delete"
                    }
                },
                "required": ["memory_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_memories",
            "description": "List recent memories stored in permanent memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max memories to list (default: 10)",
                        "default": 10
                    }
                },
                "required": []
            }
        }
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # IMAGE GENERATION TOOLS
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate an image from a text prompt using AI. Use ONLY when the user explicitly asks for an image, picture, photo, drawing, or sketch. Do NOT use for 'system prompts' or 'text prompts'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Detailed description of the image to generate. Be specific about style, colors, composition, etc."
                    },
                    "width": {
                        "type": "integer",
                        "description": "Image width in pixels (default: 1024, max: 2048)",
                        "default": 1024
                    },
                    "height": {
                        "type": "integer",
                        "description": "Image height in pixels (default: 1024, max: 2048)",
                        "default": 1024
                    },
                    "channel_name": {
                        "type": "string",
                        "description": "Optional: Channel to post the image to. If not specified, posts to current channel."
                    }
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "enhance_and_generate",
            "description": "Enhance a simple prompt into a detailed image description, then generate the image. Use when user gives a vague or simple request like 'make a logo' or 'draw something cool'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea": {
                        "type": "string",
                        "description": "The basic idea or concept for the image"
                    },
                    "style": {
                        "type": "string",
                        "description": "Art style preference",
                        "enum": ["realistic", "artistic", "cyberpunk", "minimalist", "logo", "icon", "photographic", "3d", "anime", "abstract"],
                        "default": "artistic"
                    },
                    "width": {
                        "type": "integer",
                        "description": "Image width in pixels (default: 1024)",
                        "default": 1024
                    },
                    "height": {
                        "type": "integer",
                        "description": "Image height in pixels (default: 1024)",
                        "default": 1024
                    }
                },
                "required": ["idea"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_image",
            "description": "Edit or transform an existing image based on a text prompt (image-to-image). Use when user provides a reference image URL and wants to modify it, change style, add elements, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reference_url": {
                        "type": "string",
                        "description": "URL of the reference image to edit/transform"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Description of desired changes or transformation"
                    },
                    "width": {
                        "type": "integer",
                        "description": "Output image width (default: 1024)",
                        "default": 1024
                    },
                    "height": {
                        "type": "integer",
                        "description": "Output image height (default: 1024)",
                        "default": 1024
                    }
                },
                "required": ["reference_url", "prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pollen_status",
            "description": "Check the Pollinations.ai API usage status, including remaining pollen budget, daily usage, and key rotation status. Use when user asks about image generation limits or usage.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # SERVER MANAGEMENT TOOLS
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "type": "function",
        "function": {
            "name": "manage_role",
            "description": "Create, delete, or edit a role. Use when user asks to create a role, change its color, or delete it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to perform",
                        "enum": ["create", "delete", "edit"]
                    },
                    "role_name": {
                        "type": "string",
                        "description": "Name of the role (new or existing)"
                    },
                    "color_hex": {
                        "type": "string",
                        "description": "Optional: Hex color code (e.g. #ff0000). Use 'random' for random color."
                    },
                    "hoist": {
                        "type": "boolean",
                        "description": "Optional: Whether to display role separately in member list"
                    },
                    "permissions": {
                        "type": "object",
                        "description": "Optional: Permissions to set. Keys should be permission flags (e.g. 'administrator': true, 'kick_members': false). Use 'all': true to grant admin permissions."
                    }
                },
                "required": ["action", "role_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "assign_role",
            "description": "Add or remove a role from a user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to perform",
                        "enum": ["add", "remove"]
                    },
                    "role_name": {
                        "type": "string",
                        "description": "Name of the role to assign/remove"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "ID or @mention of the user"
                    }
                },
                "required": ["action", "role_name", "user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "moderate_user",
            "description": "Perform moderation actions on a user (kick, ban, timeout).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to perform",
                        "enum": ["kick", "ban", "timeout", "unban", "remove_timeout"]
                    },
                    "user_id": {
                        "type": "string",
                        "description": "ID or @mention of the user"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the action"
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duration in minutes (only for timeout)"
                    }
                },
                "required": ["action", "user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_temp_channel",
            "description": "Create a temporary channel that auto-deletes after a specified time. Useful for private meetings or testing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "Name of the channel"
                    },
                    "category_name": {
                        "type": "string",
                        "description": "Optional: Category to place channel in"
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Time in minutes before auto-deletion (default: 60)",
                        "default": 60
                    }
                },
                "required": ["channel_name"]
            }
        }
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # AI SHOPPING TOOLS
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "type": "function",
        "function": {
            "name": "manage_product",
            "description": "Admin tool to create, update, or delete products. If no image_url is provided for 'create', the bot will check for attached images or recent images in chat.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to perform",
                        "enum": ["create", "update", "delete", "list"]
                    },
                    "product_id": {
                        "type": "string",
                        "description": "Unique ID for the product (e.g. 'cyber_sword'). Required for create/update/delete."
                    },
                    "name": {
                        "type": "string",
                        "description": "Display name of the product"
                    },
                    "price": {
                        "type": "number",
                        "description": "Price of the product"
                    },
                    "description": {
                        "type": "string",
                        "description": "Product description"
                    },
                    "image_url": {
                        "type": "string",
                        "description": "Optional URL for product image. Use 'last_image' to grab from chat."
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "shopping_assistant",
            "description": "Assist users with shopping. Can search products, add to cart, or start checkout flow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to perform",
                        "enum": ["search", "add_to_cart", "view_cart", "checkout"]
                    },
                    "query": {
                        "type": "string",
                        "description": "Search term (for search action)"
                    },
                    "product_id": {
                        "type": "string",
                        "description": "Product ID (for add_to_cart action)"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_messages",
            "description": "Delete (purge) multiple messages from a channel. Can delete by count (e.g. last 10) or by time (e.g. last 24 hours).",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "Optional: Name of the channel. Defaults to current channel if not specified."
                    },
                    "count": {
                        "type": "integer",
                        "description": "Optional: Number of messages to delete (max 100 per call)."
                    },
                    "hours": {
                        "type": "number",
                        "description": "Optional: Delete messages from the last N hours."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_server_context",
            "description": "Get a structured, compact layout representation of roles, categories, and channels in the server.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_channel",
            "description": "Create, edit, or delete a channel. Defaults to dry-run mode to prevent accidental changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to perform",
                        "enum": ["create", "edit", "delete"]
                    },
                    "channel_name": {
                        "type": "string",
                        "description": "Name of the target channel"
                    },
                    "type": {
                        "type": "string",
                        "description": "Channel type (only used for create)",
                        "enum": ["category", "text", "voice", "forum"]
                    },
                    "new_name": {
                        "type": "string",
                        "description": "New name for the channel (only used for edit)"
                    },
                    "category_name": {
                        "type": "string",
                        "description": "Category name for the channel"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, simulates the action without making API calls.",
                        "default": True
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify_channel_permissions",
            "description": "Set permission overrides for a role or user on a specific channel. Defaults to dry-run mode.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "Name of the channel"
                    },
                    "target_name": {
                        "type": "string",
                        "description": "Name of the role or member"
                    },
                    "allow": {
                        "type": "object",
                        "description": "Permissions to allow (e.g. {'send_messages': true})"
                    },
                    "deny": {
                        "type": "object",
                        "description": "Permissions to deny (e.g. {'view_channel': true})"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, simulates the action without making API calls.",
                        "default": True
                    }
                },
                "required": ["channel_name", "target_name"]
            }
        }
    }
]

# ═══════════════════════════════════════════════════════════════════════════════
# PERMISSION REQUIREMENTS
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_PERMISSIONS = {
    "send_message": ["administrator", "manage_messages"],
    "read_channel": [],  # Anyone with channel access
    "summarize_channel": [],
    "pin_message": ["manage_messages"],
    "create_thread": ["create_public_threads"],
    "create_forum_post": ["create_public_threads"],
    "search_messages": [],
    "get_config": [],
    "set_config": ["administrator"],
    "list_channels": [],
    "get_channel_info": [],
    # Memory tools
    "remember": [],
    "recall": [],
    "forget": ["administrator"],
    "list_memories": [],
    # Image tools
    "generate_image": [],
    "enhance_and_generate": [],
    "edit_image": [],
    "pollen_status": [],
    # Server Management Tools
    "manage_role": ["manage_roles"],
    "assign_role": ["manage_roles"],
    "moderate_user": ["kick_members", "ban_members", "moderate_members"],
    "create_temp_channel": ["manage_channels"],
    # AI Shopping Tools
    "manage_product": ["administrator"], # Restricted to admin
    "shopping_assistant": [], # Public
    "delete_messages": ["manage_messages"],
    # Server Context & Mutations
    "get_server_context": [],
    "manage_channel": ["manage_channels"],
    "modify_channel_permissions": ["manage_roles"]
}



def get_tool_by_name(name: str) -> dict:
    """Get a tool definition by name."""
    for tool in TOOLS:
        if tool["function"]["name"] == name:
            return tool
    return None

def get_all_tool_names() -> list:
    """Get list of all tool names."""
    return [tool["function"]["name"] for tool in TOOLS]
