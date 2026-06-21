"""
L2 SYSTEMS // Image Generation
Image generation using Pollinations.ai API (gen.pollinations.ai).
Supports text-to-image (Flux) and image-to-image (Kontext).
"""

import aiohttp
import discord
import io
import urllib.parse
import logging
import os
import base64
from typing import Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


async def upload_image_to_temp_host(url: str) -> Optional[str]:
    """
    Download an image from URL and upload to temporary hosting.
    Uses catbox.moe (free, no signup required) for temp hosting.
    
    Args:
        url: Image URL to download (e.g., Discord CDN URL)
        
    Returns:
        Public URL of uploaded image, or None if failed
    """
    try:
        # Step 1: Download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    logger.error(f"Failed to download image: HTTP {response.status}")
                    return None
                
                image_data = await response.read()
                content_type = response.headers.get("Content-Type", "image/png")
                
                # Determine file extension
                ext_map = {
                    "image/png": "png",
                    "image/jpeg": "jpg",
                    "image/gif": "gif",
                    "image/webp": "webp"
                }
                ext = ext_map.get(content_type.split(";")[0], "png")
        
        # Step 2: Upload to catbox.moe
        form = aiohttp.FormData()
        form.add_field("reqtype", "fileupload")
        form.add_field(
            "fileToUpload",
            image_data,
            filename=f"image.{ext}",
            content_type=content_type
        )
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://catbox.moe/user/api.php",
                data=form,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    public_url = await response.text()
                    logger.info(f"Image uploaded to: {public_url}")
                    return public_url.strip()
                else:
                    logger.error(f"Catbox upload failed: {response.status}")
                    return None
                    
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        return None


# Legacy alias for compatibility
download_image_as_base64 = upload_image_to_temp_host

# Pollinations.ai API configuration (new gen.pollinations.ai)
POLLINATIONS_BASE_URL = "https://gen.pollinations.ai/image"
DEFAULT_MODEL = "flux"  # Best quality text-to-image
IMG2IMG_MODEL = "kontext"  # For image-to-image transformations
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 1024


class ImageGenerator:
    """
    Generates images using Pollinations.ai API.
    Uses Flux for text-to-image, Kontext for image-to-image.
    Integrates with PollenManager for usage tracking and key rotation.
    """
    
    def __init__(self):
        self.base_url = POLLINATIONS_BASE_URL
        self.model = DEFAULT_MODEL
        self.img2img_model = IMG2IMG_MODEL
        self.default_width = DEFAULT_WIDTH
        self.default_height = DEFAULT_HEIGHT
        # Pollen manager handles key rotation and usage
        from bot.pollen_manager import get_pollen_manager
        self.pollen_manager = get_pollen_manager()
    
    def _build_url(
        self,
        prompt: str,
        width: int = None,
        height: int = None,
        seed: int = None,
        enhance: bool = False,
        reference_url: str = None
    ) -> str:
        """
        Build the Pollinations.ai URL with parameters.
        
        Args:
            prompt: Image description
            width: Image width (default 1024)
            height: Image height (default 1024)
            seed: Random seed for reproducibility
            enhance: Whether to enhance prompt automatically
            reference_url: URL of reference image for img2img
            
        Returns:
            Full URL for image generation
        """
        # URL encode the prompt
        encoded_prompt = urllib.parse.quote(prompt, safe='')
        
        # Build base URL
        url = f"{self.base_url}/{encoded_prompt}"
        
        # Build query parameters
        params = {
            "width": width or self.default_width,
            "height": height or self.default_height,
        }
        
        # Always use the current model (allows external override)
        params["model"] = self.model
        
        # Add reference image if provided (for img2img)
        if reference_url:
            params["image"] = reference_url
        
        if seed is not None and seed != -1:
            params["seed"] = seed
        else:
            params["seed"] = -1  # Random seed
        
        if enhance:
            params["enhance"] = "true"
        
        # Disable content filtering and moderation
        params["safe"] = "false"
        params["private"] = "true"  # Private generations have less moderation
        params["nologo"] = "true"   # No watermark
        
        # Add API key from pollen manager
        api_key = self.pollen_manager.get_current_key()
        if api_key:
            params["key"] = api_key
        
        # Add parameters to URL
        query_parts = []
        for k, v in params.items():
            if isinstance(v, bool):
                query_parts.append(f"{k}={str(v).lower()}")
            elif k == "image":
                # Don't double-encode image URLs - just use as-is with proper escaping
                query_parts.append(f"{k}={urllib.parse.quote(str(v), safe='/:?=&')}")
            else:
                query_parts.append(f"{k}={urllib.parse.quote(str(v), safe='')}")
        
        query_string = "&".join(query_parts)
        return f"{url}?{query_string}"
    
    async def generate(
        self,
        prompt: str,
        width: int = None,
        height: int = None,
        seed: int = None,
        enhance: bool = False,
        reference_url: str = None
    ) -> Tuple[Optional[bytes], str]:
        """
        Generate an image from a prompt.
        
        Args:
            prompt: Image description
            width: Image width
            height: Image height
            seed: Random seed
            enhance: Auto-enhance prompt
            reference_url: URL of reference image for img2img editing
            
        Returns:
            Tuple of (image_bytes, url) or (None, error_message)
        """
        # Get model being used (always use current model, which may have been overridden)
        model_used = self.model
        
        # Get API key from pollen manager (handles rotation)
        api_key = self.pollen_manager.get_current_key()
        
        url = self._build_url(prompt, width, height, seed, enhance, reference_url=reference_url)
        
        mode = "img2img" if reference_url else "text2img"
        logger.info(f"Generating image ({mode}): {prompt[:50]}...")
        logger.debug(f"Full URL: {url[:100]}...")
        
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=180)
                ) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        logger.info(f"Image generated successfully ({len(image_data)} bytes)")
                        
                        # Record successful generation
                        pollen_cost = self.pollen_manager.record_generation(
                            model=model_used,
                            success=True,
                            prompt=prompt
                        )
                        logger.info(f"Pollen used: {pollen_cost:.4f}")
                        
                        return image_data, url
                    elif response.status == 401:
                        error_msg = "API key required or invalid. Set POLLINATIONS_API_KEY in .env"
                        logger.error(error_msg)
                        # Record failed generation
                        self.pollen_manager.record_generation(model=model_used, success=False, prompt=prompt)
                        return None, error_msg
                    else:
                        error_text = await response.text()
                        error_msg = f"API returned status {response.status}: {error_text[:200]}"
                        logger.error(error_msg)
                        # Record failed generation
                        self.pollen_manager.record_generation(model=model_used, success=False, prompt=prompt)
                        return None, error_msg
                        
        except aiohttp.ClientTimeout:
            error_msg = "Image generation timed out (180s limit)"
            logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"Failed to generate image: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    async def edit_image(
        self,
        reference_url: str,
        prompt: str,
        width: int = None,
        height: int = None
    ) -> Tuple[Optional[bytes], str]:
        """
        Edit an existing image based on a text prompt (img2img).
        
        Args:
            reference_url: URL of the image to edit
            prompt: Description of desired changes
            width: Output width
            height: Output height
            
        Returns:
            Tuple of (image_bytes, url) or (None, error_message)
        """
        return await self.generate(
            prompt=prompt,
            width=width,
            height=height,
            reference_url=reference_url
        )
    
    async def generate_and_send(
        self,
        channel: discord.TextChannel,
        prompt: str,
        width: int = None,
        height: int = None,
        seed: int = None,
        enhance: bool = False,
        reply_to: discord.Message = None,
        reference_url: str = None
    ) -> Tuple[bool, str]:
        """
        Generate an image and send it to a Discord channel.
        
        Args:
            channel: Discord channel to send to
            prompt: Image description
            width: Image width
            height: Image height
            seed: Random seed
            enhance: Auto-enhance prompt
            reply_to: Optional message to reply to
            reference_url: URL of reference image for img2img
            
        Returns:
            Tuple of (success, message)
        """
        # Generate image
        image_data, url_or_error = await self.generate(
            prompt, width, height, seed, enhance, reference_url=reference_url
        )
        
        if image_data is None:
            return False, url_or_error
        
        # Create Discord file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"l2_image_{timestamp}.png"
        
        file = discord.File(
            io.BytesIO(image_data),
            filename=filename
        )
        
        # Build embed
        mode = "Image Edited" if reference_url else "Image Generated"
        model_used = "Kontext" if reference_url else "Flux"
        
        embed = discord.Embed(
            title=f"🎨 {mode}",
            description=f"**Prompt:** {prompt[:200]}{'...' if len(prompt) > 200 else ''}",
            color=0x9B59B6  # Purple
        )
        embed.set_image(url=f"attachment://{filename}")
        embed.set_footer(text=f"Model: {model_used} | {width or self.default_width}x{height or self.default_height}")
        
        try:
            if reply_to:
                await reply_to.reply(embed=embed, file=file)
            else:
                await channel.send(embed=embed, file=file)
            
            return True, f"Image sent to #{channel.name}"
        except Exception as e:
            error_msg = f"Failed to send image: {str(e)}"
            logger.error(error_msg)
            return False, error_msg


# Global instance
_image_generator = None

def get_image_generator() -> ImageGenerator:
    """Get or create the global image generator instance."""
    global _image_generator
    if _image_generator is None:
        _image_generator = ImageGenerator()
    return _image_generator
