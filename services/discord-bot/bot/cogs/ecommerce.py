"""
L2 SYSTEMS // E-commerce Module
Handles Shop Management, Product Catalog, and Admin Commands.
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.managers.product_manager import ProductManager
from bot.ecommerce_views import ProductView
import logging

logger = logging.getLogger(__name__)

class Ecommerce(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.manager = ProductManager()
        
        # Re-register views for persistence if bot restarts
        # This requires the view to have timeout=None and we normally register in setup_hook
        # But doing it here or in on_ready is fine for now
        self.bot.loop.create_task(self.register_persistent_views())

    async def register_persistent_views(self):
        await self.bot.wait_until_ready()
        products = self.manager.get_all_products()
        count = 0
        for p in products:
            self.bot.add_view(ProductView(p['id'], self.manager))
            count += 1
        logger.info(f"Registered {count} persistent product views.")

    # ═══════════════════════════════════════════════════════════════════════════
    # ADMIN COMMANDS (Shop Management)
    # ═══════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="shop_setup", description="[Admin] Auto-deploy the shopping infrastructure.")
    @app_commands.default_permissions(administrator=True)
    async def shop_setup(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.guild
        
        # 1. Create Category
        category = discord.utils.get(guild.categories, name="🛒・SHOPPING")
        if not category:
            category = await guild.create_category("🛒・SHOPPING")
        
        # 2. Create Catalog Channel (Read-Only)
        catalog = discord.utils.get(guild.text_channels, name="catalog")
        if not catalog:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(send_messages=False, add_reactions=False),
                guild.me: discord.PermissionOverwrite(send_messages=True)
            }
            catalog = await guild.create_text_channel("catalog", category=category, overwrites=overwrites)
            
        # 3. Create Orders Channel (Private)
        orders = discord.utils.get(guild.text_channels, name="orders")
        if not orders:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            orders = await guild.create_text_channel("orders", category=category, overwrites=overwrites)

        await interaction.followup.send(f"✅ Shop infrastructure ready!\nCategory: {category.name}\nChannels: {catalog.mention}, {orders.mention}")

    @app_commands.command(name="shop_add_product", description="[Admin] Add a product to the database.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        product_id="Unique ID (short, no spaces, e.g. 'boost_1')",
        name="Display Name",
        price="Price (e.g. 10.00)",
        description="Product Description",
        image_url="Optional: URL to product image"
    )
    async def shop_add_product(self, interaction: discord.Interaction, product_id: str, name: str, price: float, description: str, image_url: str = None):
        if self.manager.add_product(product_id, name, price, description, image_url=image_url):
            await interaction.response.send_message(f"✅ Product **{name}** (ID: {product_id}) added/updated!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to save product.", ephemeral=True)

    @app_commands.command(name="shop_publish", description="[Admin] Post all products to the catalog channel.")
    @app_commands.default_permissions(administrator=True)
    async def shop_publish(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        channel = discord.utils.get(interaction.guild.text_channels, name="catalog")
        if not channel:
            await interaction.followup.send("❌ Channel #catalog not found. Run `/shop_setup` first.", ephemeral=True)
            return

        # Optional: Clear old messages? 
        # await channel.purge(limit=100) # Only if desired. Let's append for safety.
        
        products = self.manager.get_all_products()
        if not products:
            await interaction.followup.send("⚠️ No products found in database.", ephemeral=True)
            return

        count = 0
        for p in products:
            embed = discord.Embed(
                title=p['name'],
                description=p['description'],
                color=discord.Color.gold()
            )
            embed.add_field(name="Price", value=f"R${p['price']:.2f}", inline=True)
            if p.get('stock', -1) != -1:
                embed.add_field(name="Stock", value=str(p['stock']), inline=True)
            
            if p.get('image_url'):
                try:
                    embed.set_image(url=p['image_url'])
                except:
                    pass
            
            # Attach persistent view
            view = ProductView(p['id'], self.manager)
            await channel.send(embed=embed, view=view)
            count += 1
            
        await interaction.followup.send(f"✅ Published {count} products to {channel.mention}.", ephemeral=True)

    @app_commands.command(name="shop_clear_db", description="[Admin] Clear all products (Dangerous).")
    @app_commands.default_permissions(administrator=True)
    async def shop_clear_db(self, interaction: discord.Interaction):
        # Could add confirmation here
        self.manager.products = {}
        self.manager._save_products()
        await interaction.response.send_message("🗑️ Database cleared.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Ecommerce(bot))
