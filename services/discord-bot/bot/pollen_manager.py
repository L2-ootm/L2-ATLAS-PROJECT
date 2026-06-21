"""
L2 SYSTEMS // Pollen Manager
Tracks Pollinations.ai API usage (pollen) with key rotation support.
"""

import os
import json
import logging
from datetime import datetime, date
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# MODEL PRICING (pollen cost per generation)
# Based on Pollinations.ai pricing: 1 pollen ≈ X images/responses
# ═══════════════════════════════════════════════════════════════════════════════

IMAGE_MODELS = {
    # Model: (pollen_per_image, images_per_pollen, description)
    "flux": (0.0002, 5000, "Flux Schnell - Fast, good quality"),
    "zimage": (0.0002, 5000, "Z-Image Turbo - Fast"),
    "turbo": (0.0003, 3300, "SDXL Turbo - Quick generations"),
    "gptimage": (0.0143, 70, "GPT Image 1 Mini - High quality"),
    "gptimage-large": (0.0667, 15, "GPT Image 1.5 - Highest quality"),
    "seedream": (0.0286, 35, "Seedream 4.0"),
    "seedream-pro": (0.04, 25, "Seedream 4.5 Pro"),
    "kontext": (0.04, 25, "FLUX.1 Kontext - Image editing"),
    "nanobanana": (0.04, 25, "NanoBanana"),
    "nanobanana-pro": (0.1667, 6, "NanoBanana Pro - Premium"),
}

VIDEO_MODELS = {
    # Model: (pollen_per_second, description)
    "veo": (0.15, "Veo 3.1 Fast - 4-8 sec videos"),
    "seedance": (1.8, "Seedance Lite"),
    "seedance-pro": (1.0, "Seedance Pro-Fast"),
}

TEXT_MODELS = {
    # Model: (output_pollen_per_M, description)
    "openai": (0.6, "OpenAI GPT-5 Mini"),
    "openai-fast": (0.44, "OpenAI GPT-5 Nano"),
    "openai-large": (14.0, "OpenAI GPT-5.2"),
    "gemini": (3.0, "Google Gemini 3 Flash"),
    "gemini-fast": (0.4, "Google Gemini 2.5 Flash Lite"),
    "gemini-large": (12.0, "Google Gemini 3 Pro"),
    "claude": (15.0, "Anthropic Claude Sonnet 4.5"),
    "claude-fast": (5.0, "Anthropic Claude Haiku 4.5"),
    "claude-large": (25.0, "Anthropic Claude Opus 4.5"),
    "deepseek": (1.68, "DeepSeek V3.2"),
    "grok": (0.5, "xAI Grok 4 Fast"),
    "mistral": (0.35, "Mistral Small 3.2 24B"),
}


class PollenKey:
    """Represents a single Pollinations API key with usage tracking."""
    
    def __init__(self, key: str, name: str = None, daily_limit: float = 1.0):
        self.key = key
        self.name = name or key[:8] + "..."
        self.daily_limit = daily_limit
        self.usage_today: float = 0.0
        self.total_usage: float = 0.0
        self.last_reset_date: str = str(date.today())
        self.generation_count: int = 0
        self.is_active: bool = True
    
    def reset_daily_if_needed(self):
        """Reset daily usage if it's a new day."""
        today = str(date.today())
        if self.last_reset_date != today:
            self.usage_today = 0.0
            self.last_reset_date = today
            logger.info(f"Daily usage reset for key: {self.name}")
    
    def can_use(self, pollen_cost: float) -> bool:
        """Check if this key has enough pollen budget for today."""
        self.reset_daily_if_needed()
        return self.is_active and (self.usage_today + pollen_cost) <= self.daily_limit
    
    def record_usage(self, pollen_cost: float, model: str, success: bool = True):
        """Record pollen usage for this key."""
        self.reset_daily_if_needed()
        if success:
            self.usage_today += pollen_cost
            self.total_usage += pollen_cost
            self.generation_count += 1
            logger.info(f"Key {self.name}: Used {pollen_cost:.4f} pollen ({model}). Daily: {self.usage_today:.4f}/{self.daily_limit}")
    
    def remaining_today(self) -> float:
        """Get remaining pollen budget for today."""
        self.reset_daily_if_needed()
        return max(0, self.daily_limit - self.usage_today)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "name": self.name,
            "daily_limit": self.daily_limit,
            "usage_today": self.usage_today,
            "total_usage": self.total_usage,
            "last_reset_date": self.last_reset_date,
            "generation_count": self.generation_count,
            "is_active": self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PollenKey":
        """Deserialize from dictionary."""
        key = cls(data["key"], data.get("name"), data.get("daily_limit", 1.0))
        key.usage_today = data.get("usage_today", 0.0)
        key.total_usage = data.get("total_usage", 0.0)
        key.last_reset_date = data.get("last_reset_date", str(date.today()))
        key.generation_count = data.get("generation_count", 0)
        key.is_active = data.get("is_active", True)
        return key


class PollenManager:
    """
    Manages Pollinations.ai API keys with usage tracking and rotation.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.usage_file = self.data_dir / "pollen_usage.json"
        
        self.keys: List[PollenKey] = []
        self.current_key_index: int = 0
        self.usage_history: List[Dict] = []
        
        self._load_keys_from_env()
        self._load_usage_data()
    
    def _load_keys_from_env(self):
        """Load API keys from environment variables."""
        # Primary key
        primary_key = os.getenv("POLLINATIONS_API_KEY")
        if primary_key:
            self.keys.append(PollenKey(primary_key, "Primary", daily_limit=1.0))
        
        # Additional keys (POLLINATIONS_API_KEY_2, POLLINATIONS_API_KEY_3, etc.)
        for i in range(2, 10):
            key = os.getenv(f"POLLINATIONS_API_KEY_{i}")
            if key:
                self.keys.append(PollenKey(key, f"Key_{i}", daily_limit=1.0))
        
        logger.info(f"Loaded {len(self.keys)} Pollinations API key(s)")
    
    def _load_usage_data(self):
        """Load usage data from file."""
        if self.usage_file.exists():
            try:
                with open(self.usage_file, "r") as f:
                    data = json.load(f)
                
                # Update keys with saved usage data
                saved_keys = {k["key"]: k for k in data.get("keys", [])}
                for key in self.keys:
                    if key.key in saved_keys:
                        saved = saved_keys[key.key]
                        key.usage_today = saved.get("usage_today", 0.0)
                        key.total_usage = saved.get("total_usage", 0.0)
                        key.last_reset_date = saved.get("last_reset_date", str(date.today()))
                        key.generation_count = saved.get("generation_count", 0)
                        key.reset_daily_if_needed()
                
                self.usage_history = data.get("history", [])[-100:]  # Keep last 100
                logger.info("Loaded pollen usage data")
            except Exception as e:
                logger.error(f"Failed to load usage data: {e}")
    
    def _save_usage_data(self):
        """Save usage data to file."""
        try:
            data = {
                "keys": [k.to_dict() for k in self.keys],
                "history": self.usage_history[-100:],
                "last_updated": datetime.utcnow().isoformat()
            }
            with open(self.usage_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save usage data: {e}")
    
    def get_current_key(self) -> Optional[str]:
        """Get the current API key to use."""
        if not self.keys:
            return None
        
        # Find a key with remaining budget
        for _ in range(len(self.keys)):
            key = self.keys[self.current_key_index]
            if key.can_use(0.01):  # Check if key has any budget
                return key.key
            
            # Try next key
            self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        
        # All keys exhausted
        logger.warning("All API keys have reached daily limit!")
        return self.keys[0].key if self.keys else None
    
    def get_pollen_cost(self, model: str, is_image: bool = True) -> float:
        """Get the pollen cost for a model."""
        if is_image:
            if model in IMAGE_MODELS:
                return IMAGE_MODELS[model][0]
            return 0.01  # Default cost for unknown models
        else:
            if model in TEXT_MODELS:
                return TEXT_MODELS[model][0] / 1000  # Rough estimate per response
            return 0.001
    
    def record_generation(
        self,
        model: str,
        success: bool,
        user_id: int = None,
        guild_id: int = None,
        prompt: str = None
    ) -> float:
        """
        Record a generation and return the pollen cost.
        """
        if not self.keys:
            return 0.0
        
        pollen_cost = self.get_pollen_cost(model)
        current_key = self.keys[self.current_key_index]
        
        # Record usage
        current_key.record_usage(pollen_cost, model, success)
        
        # Add to history
        self.usage_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "model": model,
            "pollen_cost": pollen_cost,
            "success": success,
            "user_id": user_id,
            "guild_id": guild_id,
            "prompt_preview": prompt[:50] if prompt else None,
            "key_name": current_key.name
        })
        
        # Rotate key if limit reached
        if not current_key.can_use(0.01):
            self.current_key_index = (self.current_key_index + 1) % len(self.keys)
            logger.info(f"Rotating to next key due to daily limit")
        
        # Save immediately
        self._save_usage_data()
        
        return pollen_cost
    
        return pollen_cost
    
    def set_key_usage(self, key_name: str, usage_today: float) -> bool:
        """
        Manually set the usage for a specific key (e.g. to sync with API).
        """
        for key in self.keys:
            if key.name == key_name or (key_name == "Primary" and key.name.startswith("Primary")):
                diff = usage_today - key.usage_today
                key.usage_today = usage_today
                key.total_usage += diff
                logger.info(f"Manually set usage for {key.name} to {usage_today}")
                self._save_usage_data()
                return True
        return False
    
    def get_status(self) -> Dict:
        """Get current pollen usage status."""
        total_remaining = sum(k.remaining_today() for k in self.keys)
        total_used_today = sum(k.usage_today for k in self.keys)
        total_ever = sum(k.total_usage for k in self.keys)
        total_generations = sum(k.generation_count for k in self.keys)
        
        return {
            "keys_count": len(self.keys),
            "total_remaining_today": round(total_remaining, 4),
            "total_used_today": round(total_used_today, 4),
            "total_used_ever": round(total_ever, 4),
            "total_generations": total_generations,
            "current_key": self.keys[self.current_key_index].name if self.keys else None,
            "keys": [
                {
                    "name": k.name,
                    "remaining": round(k.remaining_today(), 4),
                    "used_today": round(k.usage_today, 4),
                    "total": round(k.total_usage, 4),
                    "generations": k.generation_count,
                    "active": k.is_active
                }
                for k in self.keys
            ]
        }
    
    def get_usage_report(self) -> str:
        """Generate a formatted usage report."""
        status = self.get_status()
        
        report = "🌸 **POLLEN USAGE REPORT**\n\n"
        report += f"**Keys:** {status['keys_count']}\n"
        report += f"**Today Used:** `{status['total_used_today']:.4f}` pollen\n"
        report += f"**Today Remaining:** `{status['total_remaining_today']:.4f}` pollen\n"
        report += f"**All-Time:** `{status['total_used_ever']:.4f}` pollen ({status['total_generations']} generations)\n\n"
        
        report += "**Keys Status:**\n"
        for key in status["keys"]:
            status_emoji = "🟢" if key["remaining"] > 0 else "🔴"
            report += f"{status_emoji} `{key['name']}`: {key['used_today']:.4f}/{1.0} ({key['generations']} gens)\n"
        
        return report


# Global instance
_pollen_manager = None

def get_pollen_manager() -> PollenManager:
    """Get or create the global pollen manager instance."""
    global _pollen_manager
    if _pollen_manager is None:
        _pollen_manager = PollenManager()
    return _pollen_manager
