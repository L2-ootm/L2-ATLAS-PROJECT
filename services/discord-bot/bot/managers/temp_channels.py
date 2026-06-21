"""
L2 SYSTEMS // Temporary Channel Manager
Handles creation, persistence, and auto-deletion of temporary channels.
"""

import discord
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TempChannelManager:
    def __init__(self, bot, data_dir: str = "data"):
        self.bot = bot
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.save_file = self.data_dir / "temp_channels.json"
        
        # Dict[channel_id_str, expiry_timestamp_float]
        self.active_channels: Dict[str, float] = {}
        self.running = False
        self._load_state()

    def _load_state(self):
        """Load active temp channels from JSON."""
        if self.save_file.exists():
            try:
                with open(self.save_file, "r") as f:
                    data = json.load(f)
                    self.active_channels = data.get("channels", {})
                logger.info(f"Loaded {len(self.active_channels)} active temp channels.")
            except Exception as e:
                logger.error(f"Failed to load temp channels state: {e}")

    def _save_state(self):
        """Save active temp channels to JSON."""
        try:
            with open(self.save_file, "w") as f:
                json.dump({"channels": self.active_channels}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save temp channels state: {e}")

    def add_channel(self, channel_id: int, duration_minutes: int) -> float:
        """
        Track a new temporary channel.
        Returns the expiry timestamp.
        """
        expiry = time.time() + (duration_minutes * 60)
        self.active_channels[str(channel_id)] = expiry
        self._save_state()
        logger.info(f"Tracking temp channel {channel_id} (expires in {duration_minutes}m)")
        return expiry

    async def start_monitoring(self):
        """Start the background monitoring loop."""
        self.running = True
        logger.info("Temp Channel Monitoring started.")
        while self.running:
            await self._check_expirations()
            await asyncio.sleep(60)  # Check every minute

    async def _check_expirations(self):
        """Check for expired channels and delete them."""
        now = time.time()
        to_delete = []

        # Identify expired channels
        for channel_id_str, expiry in self.active_channels.items():
            if now >= expiry:
                to_delete.append(channel_id_str)

        # Process deletions
        for channel_id_str in to_delete:
            try:
                channel_id = int(channel_id_str)
                channel = self.bot.get_channel(channel_id)
                
                if channel:
                    await channel.delete(reason="Temp channel expired")
                    logger.info(f"Deleted expired temp channel: {channel.name} ({channel_id})")
                else:
                    logger.warning(f"Temp channel {channel_id} not found (already deleted?)")
                
                # Remove from tracking regardless of deletion success (to avoid loops)
                del self.active_channels[channel_id_str]
                self._save_state()
                
            except Exception as e:
                logger.error(f"Failed to delete temp channel {channel_id_str}: {e}")

    def stop(self):
        self.running = False
