import discord
from discord import app_commands
from discord.ext import commands
from database.db import (
    player_exists,
    add_player,
    remove_player,
    get_player_by_discord_id
)
from config import GUILD_ID


def _format_player_record(record):
    discord_id, player_name, _, _, _ = record
    return f"**RP nimi:** {player_name}\n**Discordi ID:** {discord_id}"


class PlayerManagementCog(commands.Cog):
    """Player management commands for the player database"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="addplayer", description="Lisa isik andmebaasi")
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(
        discord_id="Player's Discord ID",
        rp_name="Player's RP name"
    )
    async def add_player(self, interaction: discord.Interaction, discord_id: str, rp_name: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Sul peab olema **Administraatori** õigused, et seda käsku kasutada.",
                ephemeral=True
            )
            return

        try:
            target_id = int(discord_id)
        except ValueError:
            await interaction.response.send_message("❌ Vale Discordi ID formaat.", ephemeral=True)
            return

        if player_exists(target_id):
            await interaction.response.send_message(
                f"❌ Mängija Discordi ID-ga {target_id} juba eksisteerib.",
                ephemeral=True
            )
            return

        add_player(target_id, rp_name)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Mängija lisatud",
                color=discord.Color.green(),
                description=(
                    f"**RP nimi:** {rp_name}\n"
                    f"**Discordi ID:** {target_id}\n"
                    "Mängija andmed lisatud andmebaasi."
                )
            ),
            ephemeral=True
        )

    @app_commands.command(name="removeplayer", description="Eemalda mängija andmebaasist")
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(discord_id="Player's Discord ID")
    async def remove_player(self, interaction: discord.Interaction, discord_id: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Sul peab olema **Administraatori** õigused, et seda käsku kasutada.",
                ephemeral=True
            )
            return

        try:
            target_id = int(discord_id)
        except ValueError:
            await interaction.response.send_message("❌ Vale Discordi ID formaat.", ephemeral=True)
            return

        if not player_exists(target_id):
            await interaction.response.send_message(
                f"❌ Mängijat Discordi ID-ga {target_id} ei leitud.",
                ephemeral=True
            )
            return

        remove_player(target_id)
        await interaction.response.send_message(
            f"✅ Eemaldatud mängija Discordi ID-ga {target_id} andmebaasist.",
            ephemeral=True
        )

    @app_commands.command(name="playerinfo", description="View a registered player's information")
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(discord_id="Player's Discord ID")
    async def player_info(self, interaction: discord.Interaction, discord_id: str):
        try:
            target_id = int(discord_id)
        except ValueError:
            await interaction.response.send_message("❌ Vale Discordi ID formaat.", ephemeral=True)
            return

        record = get_player_by_discord_id(target_id)
        if not record:
            await interaction.response.send_message(
                f"❌ Mängijat Discordi ID-ga {target_id} ei leitud.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Mängija info",
            color=discord.Color.blue(),
            description=_format_player_record(record)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(PlayerManagementCog(bot))
