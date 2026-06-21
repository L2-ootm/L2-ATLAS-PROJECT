import discord
import json
from datetime import datetime

class LogEmbedBuilder:
    """
    Builds Ultra Precise Discord Embeds for L2 Systems logs.
    """
    
    # Color Mapping
    COLORS = {
        'LOGIN': 0x3B82F6,              # Blue - INFO
        'VIEW_DASHBOARD': 0x3B82F6,     # Blue - INFO
        'USER_CREATED': 0x8B5CF6,       # Purple - USER
        'USER_UPDATED': 0x8B5CF6,       # Purple - USER
        'PASSWORD_RESET': 0x8B5CF6,     # Purple - USER
        'PAYMENT_SUCCESS': 0x10B981,    # Green - SUCCESS
        'SUBSCRIPTION_CREATED': 0xFBBF24, # Gold - COMMERCE
        'SYNC_COMPLETE': 0x10B981,      # Green - SUCCESS
        'CORRELATED_SUSPICION_TZ': 0xF59E0B, # Orange - WARNING
        'SUBSCRIPTION_CANCELLED': 0xF59E0B, # Orange - WARNING
        'MASS_ATTACK_MITIGATION': 0xF59E0B,  # Orange - WARNING
        'PAYMENT_FAILED': 0xEF4444,     # Red - ERROR
        'API_ERROR': 0xEF4444,          # Red - ERROR
        'HONEYPOT_TRIGGER': 0xDC2626,   # Dark Red - CRITICAL
        'TAMPER_ATTEMPT': 0xDC2626,     # Dark Red - CRITICAL
        'SYSTEM_STARTUP': 0xFFFFFF,     # White - SYSTEM
        'RECORD_CREATED': 0x10B981,     # Green - SUCCESS
        'RECORD_UPDATED': 0x0EA5E9,     # Sky Blue - INFO
        'RECORD_DELETED': 0xEF4444,     # Red - ERROR
    }

    ICONS = {
        'LOGIN': '🔵',
        'VIEW_DASHBOARD': '🔵',
        'USER_CREATED': '👤',
        'USER_UPDATED': '👤',
        'PASSWORD_RESET': '🔐',
        'PAYMENT_SUCCESS': '🟢',
        'SUBSCRIPTION_CREATED': '🏆',
        'SYNC_COMPLETE': '🟢',
        'CORRELATED_SUSPICION_TZ': '⚠️',
        'SUBSCRIPTION_CANCELLED': '⚠️',
        'MASS_ATTACK_MITIGATION': '⚠️',
        'PAYMENT_FAILED': '🔴',
        'API_ERROR': '🔴',
        'HONEYPOT_TRIGGER': '🚨',
        'TAMPER_ATTEMPT': '🚨',
        'SYSTEM_STARTUP': '⚙️',
        'RECORD_CREATED': '🆕',
        'RECORD_UPDATED': '✏️',
        'RECORD_DELETED': '🗑️',
    }

    @staticmethod
    def get_color(event_type):
        return LogEmbedBuilder.COLORS.get(event_type, 0x3B82F6) # Default Blue

    @staticmethod
    def get_icon(event_type):
        return LogEmbedBuilder.ICONS.get(event_type, 'ℹ️')

    @staticmethod
    def create_log_embed(log_entry: dict):
        """
        Creates a Discord Embed from a sys_trace_stream log entry.
        """
        event_type = log_entry.get('event_type', 'UNKNOWN')
        payload = log_entry.get('payload', {})
        actor_id = log_entry.get('actor_id', 'System')
        trace_id = log_entry.get('trace_id', 'N/A')
        created_at = log_entry.get('created_at', datetime.now().isoformat())

        color = LogEmbedBuilder.get_color(event_type)
        icon = LogEmbedBuilder.get_icon(event_type)

        embed = discord.Embed(
            title=f"{icon} {event_type}",
            description=f"**Trace ID:** `{trace_id}`",
            color=color,
            timestamp=datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        )

        # Actor Field
        embed.add_field(name="👤 Actor", value=f"`{actor_id}`", inline=True)

        # Payload Formatting
        if payload:
            # Extract message if present for cleaner display
            message = payload.pop('message', None)
            if message:
                embed.add_field(name="📝 Message", value=message, inline=False)
            
            # Format remaining payload as JSON block
            if payload:
                json_str = json.dumps(payload, indent=2)
                # Truncate if too long for embed field
                if len(json_str) > 1000:
                    json_str = json_str[:1000] + "\n... (truncated)"
                embed.add_field(name="📦 Payload", value=f"```json\n{json_str}\n```", inline=False)

        embed.set_footer(text="L2 SYSTEMS // AUDIT STREAM")
        return embed
