import discord
from discord.ext import commands
from discord import app_commands

class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="add-role", description="Add a role to a user (Admin only).")
    @app_commands.default_permissions(administrator=True)
    async def add_role(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
        await interaction.response.defer(ephemeral=True)

        if role in user.roles:
            await interaction.followup.send(f"{user.mention} already has the {role.mention} role.", ephemeral=True)
            return

        try:
            await user.add_roles(role, reason=f"Role added by {interaction.user.name}")
            await interaction.followup.send(f"Successfully added the {role.mention} role to {user.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to add roles.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="remove-role", description="Remove a role from a user (Admin only).")
    @app_commands.default_permissions(administrator=True)
    async def remove_role(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
        await interaction.response.defer(ephemeral=True)

        if role not in user.roles:
            await interaction.followup.send(f"{user.mention} does not have the {role.mention} role.", ephemeral=True)
            return

        try:
            await user.remove_roles(role, reason=f"Role removed by {interaction.user.name}")
            await interaction.followup.send(f"Successfully removed the {role.mention} role from {user.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to remove roles.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Roles(bot))