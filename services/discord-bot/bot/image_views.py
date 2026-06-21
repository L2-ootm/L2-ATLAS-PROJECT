"""
L2 SYSTEMS // Image Views
Discord UI components for interactive image generation.
"""

import discord
from discord.ui import View, Select, Button, Modal, TextInput
from typing import List, Optional
import asyncio


# Model options for dropdown
IMAGE_MODELS = [
    ("🚀 Flux Schnell (Fast)", "flux"),
    ("⚡ Z-Image Turbo", "zimage"),
    ("🎨 SDXL Turbo", "turbo"),
    ("🌟 GPT Image Mini", "gptimage"),
    ("💎 GPT Image 1.5 (Best)", "gptimage-large"),
    ("🌸 Seedream 4.0", "seedream"),
    ("🌺 Seedream 4.5 Pro", "seedream-pro"),
    ("✏️ FLUX Kontext (Edit)", "kontext"),
    ("🍌 NanoBanana", "nanobanana"),
    ("🍌 NanoBanana Pro", "nanobanana-pro"),
]


class ImageModelSelect(Select):
    """Dropdown for selecting image generation model."""
    
    def __init__(self, prompt: str, reference_urls: List[str] = None):
        self.prompt = prompt
        self.reference_urls = reference_urls or []
        
        options = [
            discord.SelectOption(
                label=name,
                value=value,
                description=f"{'Editing' if value == 'kontext' else 'Generation'}"
            )
            for name, value in IMAGE_MODELS
        ]
        
        # Default to kontext if images attached, otherwise flux
        default = "kontext" if self.reference_urls else "flux"
        
        super().__init__(
            placeholder="🎨 Select a model...",
            options=options,
            custom_id="image_model_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        model = self.values[0]
        
        # Disable the select and show processing
        self.disabled = True
        self.placeholder = f"Selected: {model}"
        await interaction.response.edit_message(view=self.view)
        
        # Process the image generation
        await self.view.generate_image(interaction, model)


class ImageGenerationView(View):
    """Interactive view for image generation with model selection."""
    
    def __init__(
        self, 
        prompt: str, 
        channel: discord.TextChannel,
        user: discord.User,
        reference_urls: List[str] = None,
        timeout: float = 120
    ):
        super().__init__(timeout=timeout)
        self.prompt = prompt
        self.channel = channel
        self.user = user
        self.reference_urls = reference_urls or []
        self.message: Optional[discord.Message] = None
        
        # Add model selector
        self.add_item(ImageModelSelect(prompt, reference_urls))
        
        # Add cancel button
        cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="cancel")
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to interact."""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "❌ Only the person who requested this can use these controls.",
                ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self):
        """Handle timeout - disable all components."""
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(
                    content="⏰ Selection timed out. Use `/image` or ask again.",
                    view=self
                )
            except:
                pass
    
    async def cancel_callback(self, interaction: discord.Interaction):
        """Handle cancel button."""
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content="❌ Image generation cancelled.",
            view=self
        )
        self.stop()
    
    async def generate_image(self, interaction: discord.Interaction, model: str):
        """Generate the image with selected model."""
        from bot.image_gen import get_image_generator
        from bot.pollen_manager import get_pollen_manager
        
        # Send processing message
        processing_msg = await self.channel.send(
            f"⏳ **Generating with {model}...**\n"
            f"Prompt: {self.prompt[:100]}{'...' if len(self.prompt) > 100 else ''}"
        )
        
        generator = get_image_generator()
        pollen_mgr = get_pollen_manager()
        
        # Set model
        original_model = generator.model
        generator.model = model
        
        try:
            # Convert Discord URL to base64 if reference image provided
            reference_url = None
            if self.reference_urls:
                from bot.image_gen import download_image_as_base64
                
                await processing_msg.edit(content=f"⏳ **Downloading reference image...**")
                
                base64_image = await download_image_as_base64(self.reference_urls[0])
                if base64_image:
                    reference_url = base64_image
                else:
                    await self.message.edit(
                        content="❌ **Failed to download reference image.** Try using a public image URL.",
                        view=None
                    )
                    await processing_msg.delete()
                    self.stop()
                    return
                
                await processing_msg.edit(
                    content=f"⏳ **Generating with {model}...**\n"
                    f"Prompt: {self.prompt[:100]}{'...' if len(self.prompt) > 100 else ''}"
                )
            
            async with self.channel.typing():
                success, message = await generator.generate_and_send(
                    channel=self.channel,
                    prompt=self.prompt,
                    width=1024,
                    height=1024,
                    reference_url=reference_url
                )
            
            await processing_msg.delete()
            
            status = pollen_mgr.get_status()
            
            if success:
                # Update the original message
                await self.message.edit(
                    content=f"✅ **Generated with {model}!**\n📊 Pollen: `{status['total_used_today']:.4f}`",
                    view=None
                )
            else:
                await self.message.edit(
                    content=f"❌ **Failed:** {message}",
                    view=None
                )
                
        except Exception as e:
            await processing_msg.delete()
            await self.message.edit(
                content=f"❌ **Error:** {e}",
                view=None
            )
        finally:
            generator.model = original_model
            self.stop()


async def send_image_generation_prompt(
    channel: discord.TextChannel,
    user: discord.User,
    prompt: str,
    reference_urls: List[str] = None
) -> discord.Message:
    """
    Send an interactive image generation prompt with model selection.
    
    Args:
        channel: Discord channel to send to
        user: User who requested the generation
        prompt: Image generation prompt
        reference_urls: Optional list of reference image URLs
        
    Returns:
        The sent message
    """
    view = ImageGenerationView(
        prompt=prompt,
        channel=channel,
        user=user,
        reference_urls=reference_urls
    )
    
    # Build the prompt message
    content = f"🎨 **Image Generation Request**\n\n"
    content += f"**Prompt:** {prompt[:200]}{'...' if len(prompt) > 200 else ''}\n"
    
    if reference_urls:
        content += f"📎 **Reference Images:** {len(reference_urls)}\n"
        content += f"*Recommended model: ✏️ FLUX Kontext for editing*\n"
    
    content += f"\n👇 **Select a model to generate:**"
    
    message = await channel.send(content, view=view)
    view.message = message
    
    return message
