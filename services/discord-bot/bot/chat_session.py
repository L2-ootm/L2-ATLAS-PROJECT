"""
L2 SYSTEMS // Chat Session Manager
Manages seamless conversational sessions with the AI agent.
"""

import discord
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
import re
import logging

logger = logging.getLogger(__name__)

# Farewell phrases that end a chat session (Portuguese + English)
FAREWELL_PHRASES = [
    # Portuguese
    "tchau", "até mais", "ate mais", "valeu", "falou", "flw", "vlw",
    "obrigado", "obrigada", "brigado", "brigada", "thanks",
    "é isso", "e isso", "era isso", "só isso", "so isso",
    "beleza", "blz", "tmj", "tamo junto",
    # English
    "bye", "goodbye", "that's all", "thats all", "that is all",
    "thanks", "thank you", "done", "finished", "end chat",
    "stop", "exit", "quit", "cya", "see ya", "later",
    # Commands
    "/stop", "/end", "/exit", "/bye"
]

# Phrases that indicate the message is directed at the bot
BOT_INDICATORS = [
    "l2", "bot", "oracle", "sistema", "system",
    "você", "voce", "tu", "vc",
    "pode", "poderia", "consegue", "faz", "faça", "faca",
    "me", "mim", "pra mim", "para mim"
]


class ChatSession:
    """Represents an active chat session with a user."""
    
    def __init__(self, user_id: int, channel_id: int, guild_id: int):
        self.user_id = user_id
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.started_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.conversation_history: List[Dict] = []
        self.message_count = 0
        self.active = True
    
    def add_message(self, role: str, content: str):
        """Add a message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.last_activity = datetime.utcnow()
        self.message_count += 1
        
        # Keep last 50 messages to prevent memory issues
        if len(self.conversation_history) > 50:
            self.conversation_history = self.conversation_history[-50:]
    
    def get_context_messages(self) -> List[Dict]:
        """Get messages formatted for LLM context."""
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.conversation_history
        ]
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired due to inactivity."""
        return datetime.utcnow() - self.last_activity > timedelta(minutes=timeout_minutes)
    
    def end(self):
        """End the session."""
        self.active = False


class ChatSessionManager:
    """Manages active chat sessions across the bot."""
    
    def __init__(self):
        # Key: (user_id, channel_id) -> ChatSession
        self.sessions: Dict[tuple, ChatSession] = {}
        self.session_timeout = 30  # minutes
    
    def start_session(self, user_id: int, channel_id: int, guild_id: int) -> ChatSession:
        """Start a new chat session."""
        key = (user_id, channel_id)
        
        # End existing session if any
        if key in self.sessions:
            self.sessions[key].end()
        
        session = ChatSession(user_id, channel_id, guild_id)
        self.sessions[key] = session
        logger.info(f"Started chat session for user {user_id} in channel {channel_id}")
        return session
    
    def get_session(self, user_id: int, channel_id: int) -> Optional[ChatSession]:
        """Get an active session for user in channel."""
        key = (user_id, channel_id)
        session = self.sessions.get(key)
        
        if session and session.active:
            # Check for timeout
            if session.is_expired(self.session_timeout):
                session.end()
                logger.info(f"Session expired for user {user_id}")
                return None
            return session
        return None
    
    def end_session(self, user_id: int, channel_id: int) -> bool:
        """End a chat session."""
        key = (user_id, channel_id)
        if key in self.sessions:
            self.sessions[key].end()
            logger.info(f"Ended chat session for user {user_id}")
            return True
        return False
    
    def has_active_session(self, user_id: int, channel_id: int) -> bool:
        """Check if user has an active session in channel."""
        return self.get_session(user_id, channel_id) is not None
    
    def cleanup_expired(self):
        """Clean up expired sessions."""
        expired_keys = [
            key for key, session in self.sessions.items()
            if not session.active or session.is_expired(self.session_timeout)
        ]
        for key in expired_keys:
            del self.sessions[key]
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired sessions")


def is_farewell(message: str) -> bool:
    """Check if message is a farewell phrase."""
    msg_lower = message.lower().strip()
    
    # Direct match
    if msg_lower in FAREWELL_PHRASES:
        return True
    
    # Check if message starts with farewell
    for phrase in FAREWELL_PHRASES:
        if msg_lower.startswith(phrase + " ") or msg_lower.startswith(phrase + ","):
            return True
        if msg_lower.endswith(" " + phrase) or msg_lower.endswith("," + phrase):
            return True
    
    return False


def is_directed_at_bot(message: str, bot_mentioned: bool = False, in_active_session: bool = False) -> bool:
    """
    Detect if a message is directed at the bot.
    
    When in_active_session is True, we assume ALL messages are directed at the bot
    unless they're clearly not (like links only, or random text to others).
    """
    # In active chat session, respond to everything by default
    if in_active_session:
        msg_lower = message.lower().strip()
        
        # Skip obvious non-directed messages
        if msg_lower.startswith("http") and len(msg_lower.split()) == 1:
            return False  # Just a link
        
        # Skip if it looks like talking to someone else (starts with @mention that's not the bot)
        if message.startswith("<@") and not bot_mentioned:
            return False
        
        # In session, respond to everything else
        return True
    
    # Outside of session, use stricter detection
    if bot_mentioned:
        return True
    
    msg_lower = message.lower().strip()
    
    # Starts with bot name
    if msg_lower.startswith("l2 ") or msg_lower.startswith("l2,"):
        return True
    
    # Contains question mark and bot indicators
    if "?" in message:
        for indicator in BOT_INDICATORS:
            if indicator in msg_lower:
                return True
    
    # Starts with request verbs (Portuguese)
    request_starters = [
        "pode ", "poderia ", "consegue ", "faz ", "faça ", "faca ",
        "me ", "manda ", "envia ", "mostra ", "lista ", "busca ",
        "procura ", "resume ", "sumariza ", "explica ", "baseando",
        "considerando", "levando", "tendo", "aonde", "onde", "qual",
        # English
        "can ", "could ", "would ", "please ", "show ", "list ",
        "send ", "post ", "summarize ", "explain ", "what ", "how ",
        "why ", "where ", "when ", "who ", "based on", "considering"
    ]
    
    for starter in request_starters:
        if msg_lower.startswith(starter):
            return True
    
    return False


def format_session_start_message() -> str:
    """Format the message shown when chat session starts."""
    return """🟢 **CHAT MODE ACTIVATED**

Estou em modo de conversa contínua. Pode falar comigo naturalmente!

**Como funciona:**
- Respondo automaticamente às suas mensagens
- Tenho acesso a todas as ferramentas (enviar msgs, resumir canais, etc.)
- Mantenho o contexto da conversa

**Para encerrar:** Diga "tchau", "valeu", "that's all", ou `/stop`

*O que posso fazer por você?*"""


def format_session_end_message(message_count: int, duration_minutes: int) -> str:
    """Format the message shown when chat session ends."""
    return f"""🔴 **CHAT MODE DEACTIVATED**

**Sessão encerrada.**
- Mensagens trocadas: `{message_count}`
- Duração: `{duration_minutes} min`

*Até a próxima! Use `/chat` para iniciar novamente.*"""
