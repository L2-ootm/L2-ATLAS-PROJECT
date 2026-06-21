"""
L2 SYSTEMS // E-commerce Views
Interactive components (Buttons, Modals) for the shopping system.
"""

import discord
from discord import ui
import logging

logger = logging.getLogger(__name__)

class ProductView(ui.View):
    """View attached to a Product Embed in #catalog."""
    def __init__(self, product_id: str, manager):
        super().__init__(timeout=None) # Persistent view
        self.product_id = product_id
        self.manager = manager
        # Custom ID ensures persistence across restarts
        self.add_item(ProductButton(product_id, "buy", "Buy Now", discord.ButtonStyle.green, "💳"))
        self.add_item(ProductButton(product_id, "add", "Add to Cart", discord.ButtonStyle.blurple, "🛒"))
        self.add_item(ViewCartButton(manager))

class ProductButton(ui.Button):
    def __init__(self, product_id, action, label, style, emoji):
        super().__init__(
            style=style, 
            label=label, 
            emoji=emoji, 
            custom_id=f"shop_prod_{action}_{product_id}"
        )
        self.product_id = product_id
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        manager = self.view.manager
        product = manager.get_product(self.product_id)
        
        if not product:
            await interaction.response.send_message("❌ This product no longer exists.", ephemeral=True)
            return

        if self.action == "add":
            manager.add_to_cart(interaction.user.id, self.product_id)
            await interaction.response.send_message(f"✅ **{product['name']}** added to cart!", ephemeral=True)
            
        elif self.action == "buy":
            # Direct Buy = Add to cart + Checkout flow
            manager.add_to_cart(interaction.user.id, self.product_id)
            await start_checkout_flow(interaction, manager)

class ViewCartButton(ui.Button):
    def __init__(self, manager):
        super().__init__(
            style=discord.ButtonStyle.grey, 
            label="View Cart", 
            emoji="🛍️",
            custom_id="shop_view_cart"
        )
        self.manager = manager

    async def callback(self, interaction: discord.Interaction):
        items = self.manager.get_cart(interaction.user.id)
        if not items:
            await interaction.response.send_message("🛒 Your cart is empty.", ephemeral=True)
            return

        total = sum(i['price'] for i in items)
        
        # Build Cart Embed
        desc = ""
        for item in items:
            desc += f"• **{item['name']}** - R${item['price']:.2f}\n"
        
        desc += f"\n**Total: R${total:.2f}**"
        
        embed = discord.Embed(title="🛍️ Your Shopping Cart", description=desc, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, view=CartView(self.manager), ephemeral=True)


class CartView(ui.View):
    def __init__(self, manager):
        super().__init__(timeout=180)
        self.manager = manager
    
    @ui.button(label="Checkout", style=discord.ButtonStyle.green, emoji="💸")
    async def checkout(self, interaction: discord.Interaction, button: ui.Button):
        await start_checkout_flow(interaction, self.manager)

    @ui.button(label="Clear Cart", style=discord.ButtonStyle.red, emoji="🗑️")
    async def clear(self, interaction: discord.Interaction, button: ui.Button):
        self.manager.clear_cart(interaction.user.id)
        await interaction.response.edit_message(content="🗑️ Cart cleared.", embed=None, view=None)

async def start_checkout_flow(interaction: discord.Interaction, manager):
    """
    Initiates checkout:
    1. Checks cart
    2. Creates private thread (Ticket style) in 'orders' channel (if exists) or current context
    3. Pings user
    """
    user = interaction.user
    items = manager.get_cart(user.id)
    
    if not items:
        if not interaction.response.is_done():
            await interaction.response.send_message("⚠️ Your cart is empty!", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Your cart is empty!", ephemeral=True)
        return

    # Find Orders Channel / Shopping Category
    guild = interaction.guild
    orders_channel = discord.utils.get(guild.text_channels, name="orders")
    
    if not orders_channel:
        # Fallback if setup wasn't run
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Error: #orders channel not found. Admin needs to run `/shop_setup`.", ephemeral=True)
        return

    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    # Create Thread
    total = sum(i['price'] for i in items)
    thread_name = f"order-{user.name}-{user.discriminator if user.discriminator != '0' else user.id}"
    
    try:
        # Create private thread if possible, else public
        # Note: Private threads require level 2 boost or admin usually, but we try standard
        # Actually, best practice for tickets is a private channel or a thread in specific channel (requires type=private_thread)
        
        thread = await orders_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            reason="New Order"
        )
    except Exception as e:
        # Fallback to public thread
        thread = await orders_channel.create_thread(
            name=thread_name,
            reason="New Order (Fallback)"
        )
    
    # Send Invoice to Thread
    desc = f"**Customer:** {user.mention}\n\n**Items:**\n"
    for item in items:
        desc += f"• {item['name']} - R${item['price']:.2f}\n"
    desc += f"\n══════════════════\n**Total: R${total:.2f}**"
    
    embed = discord.Embed(title="🧾 Order Summary", description=desc, color=discord.Color.gold())
    
    await thread.add_user(user)
    await thread.send(content=f"{user.mention} Here is your order!", embed=embed, view=CheckoutControlView(manager, user.id))
    
    # Notify user
    await interaction.followup.send(f"✅ Order ticket created! Proceed to payment here: {thread.mention}", ephemeral=True)


class CheckoutControlView(ui.View):
    def __init__(self, manager, user_id):
        super().__init__(timeout=None)
        self.manager = manager
        self.user_id = user_id

    @ui.button(label="Confirm Payment (Sim)", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_pay(self, interaction: discord.Interaction, button: ui.Button):
        # In real app, this would check Stripe/Pix API
        # For now, simulate success
        
        self.manager.clear_cart(self.user_id)
        
        embed = discord.Embed(
            title="🎉 Payment Confirmed",
            description="Thank you for your purchase! Our team will process it shortly.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        
        # Disable buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        
        # Rename thread to closed or paid
        try:
            await interaction.channel.edit(name=f"paid-{interaction.channel.name}", locked=True, archived=True)
        except:
            pass
