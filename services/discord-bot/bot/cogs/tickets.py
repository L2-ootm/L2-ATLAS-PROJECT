import discord
from discord import app_commands
from discord.ext import commands
from database.database import DatabaseManager

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, interaction: discord.Interaction) -> bool:
        if not self.bot.db_connected:
            await interaction.response.send_message("This command is temporarily disabled as the database is not connected.", ephemeral=True)
            return False
        return True

    @app_commands.command(name="new-ticket", description="Create a new support ticket.")
    async def new_ticket(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if user already has an open ticket
        existing_ticket = await DatabaseManager.fetchrow(
            "SELECT * FROM tickets WHERE user_id = ? AND status = 'OPEN'",
            interaction.user.id
        )
        if existing_ticket:
            await interaction.followup.send("You already have an open ticket.", ephemeral=True)
            return

        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        try:
            channel = await guild.create_text_channel(
                f"ticket-{interaction.user.name}",
                category=category,
                overwrites=overwrites
            )
            
            # Save ticket to database
            await DatabaseManager.execute(
                "INSERT INTO tickets (user_id, channel_id, status) VALUES (?, ?, ?)",
                interaction.user.id, channel.id, 'OPEN'
            )
            
            await channel.send(
                f"Hello {interaction.user.mention}, your support ticket has been created. "
                "A staff member will be with you shortly."
            )
            await interaction.followup.send(f"Your ticket has been created: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred while creating your ticket: {e}", ephemeral=True)

    @app_commands.command(name="close-ticket", description="Close the current support ticket.")
    async def close_ticket(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        ticket = await DatabaseManager.fetchrow(
            "SELECT * FROM tickets WHERE channel_id = $1 AND status = 'OPEN'",
            interaction.channel.id
        )
        
        if not ticket:
            await interaction.followup.send("This is not a valid ticket channel or it is already closed.", ephemeral=True)
            return
            
        try:
            await interaction.channel.delete()
            # Update ticket status in the database
            await DatabaseManager.execute(
                "UPDATE tickets SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP WHERE channel_id = ?",
                interaction.channel.id
            )
            await interaction.followup.send("Ticket closed successfully.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred while closing the ticket: {e}", ephemeral=True)

    @app_commands.command(name="ticket-transcript", description="Save the transcript of this ticket.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def save_transcript(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        ticket = await DatabaseManager.fetchrow(
            "SELECT ticket_id FROM tickets WHERE channel_id = ?",
            interaction.channel.id
        )
        
        if not ticket:
            await interaction.followup.send("This command can only be used in a ticket channel.", ephemeral=True)
            return
            
        try:
            messages = [message async for message in interaction.channel.history(limit=None, oldest_first=True)]
            transcript_content = "\n".join(
                [f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author.name}: {msg.content}" for msg in messages]
            )
            
            # Save transcript to the database
            await DatabaseManager.execute(
                "INSERT INTO ticket_transcripts (ticket_id, content) VALUES (?, ?)",
                ticket['ticket_id'], transcript_content
            )
            
            await interaction.followup.send("The transcript has been saved.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred while saving the transcript: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tickets(bot))