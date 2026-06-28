import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View, Modal, TextInput, Button
from database.db import (
    get_all_laws, insert_citation, init_database, get_citations_by_discord_id, get_player_by_discord_id
)
from config import GUILD_ID, UNBELIEVA_API_TOKEN, CITATION_ROLE_ID
import json
import aiohttp

class PlayerInfoModal(Modal):
    """Modal mängija RP nime ja Discordi ID sisestamiseks"""
    
    player_name = TextInput(label="RP nimi", placeholder="Sisesta RP nimi", max_length=100)
    discord_id = TextInput(label="Discordi ID", placeholder="Sisesta mängija Discordi ID", max_length=20)
    
    def __init__(self, cog):
        super().__init__(title="Tsitaat - Mängija info")
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.cog.on_player_info_submitted(interaction, self.player_name.value, self.discord_id.value)

class LawSelectView(View):
    """View with dropdown menu for selecting laws"""
    
    def __init__(self, laws_data):
        super().__init__()
        self.laws_data = laws_data  # List of (id, name, fine_amount)
        self.selected_laws = {}  # {law_id: (name, fine)}
        self.total_fine = 0.0
        
        # Create dropdown options
        options = [
            discord.SelectOption(
                label=name,
                value=str(law_id),
                description=f"Fine: ${fine:.2f}"
            )
            for law_id, name, fine in laws_data
        ]
        
        self.select = Select(
            placeholder="Vali rikkumised...",
            min_values=0,
            max_values=len(options),
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)
        
        self.continue_button = Button(label="Jätka", style=discord.ButtonStyle.green)
        self.continue_button.callback = self.continue_callback
        self.add_item(self.continue_button)
        
        self.cancel_button = Button(label="Tühista", style=discord.ButtonStyle.red)
        self.cancel_button.callback = self.cancel_callback
        self.add_item(self.cancel_button)
    
    async def select_callback(self, interaction: discord.Interaction):
        """Handle law selection changes"""
        await interaction.response.defer()
        
        # Clear previous selections
        self.selected_laws = {}
        self.total_fine = 0.0
        
        # Process selected values
        for value in self.select.values:
            law_id = int(value)
            for lid, name, fine in self.laws_data:
                if lid == law_id:
                    self.selected_laws[law_id] = (name, fine)
                    self.total_fine += fine
                    break
        
        # Update message with new total
        laws_text = "\n".join([f"• {name} (${fine:.2f})" for name, fine in self.selected_laws.values()])
        embed = discord.Embed(
            title="Vali rikkumised",
            description=f"**Kokku trahv: ${self.total_fine:.2f}**\n\n{laws_text if laws_text else 'Ühtegi rikkumist ei valitud'}",
            color=discord.Color.orange()
        )
        
        await interaction.edit_original_response(embed=embed)
    
    async def continue_callback(self, interaction: discord.Interaction):
        """Continue to confirmation screen"""
        if not self.selected_laws:
            await interaction.response.send_message("Vali enne jätkamist vähemalt üks rikkumine.", ephemeral=True)
            return
        
        self.continue_button.disabled = True
        self.cancel_button.disabled = True
        self.select.disabled = True
        await interaction.response.defer()
        self.stop()
    
    async def cancel_callback(self, interaction: discord.Interaction):
        """Tühista trahvi väljastamine"""
        await interaction.response.send_message("Tsitaat tühistatud.", ephemeral=True)
        self.stop()

class CitationCog(commands.Cog):
    """Citation system cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.citation_data = {}  # Store temporary citation data {user_id: {player_name, discord_id, selected_laws, total_fine}}
    
    @app_commands.command(name="trahv", description="Väljasta isikule trahv")
    @app_commands.guilds(GUILD_ID)
    async def citation_command(self, interaction: discord.Interaction):
        """Start the citation process"""
        
        # Role check - only allow users with the configured role
        member = None
        if interaction.guild:
            member = interaction.guild.get_member(interaction.user.id)
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(interaction.user.id)
                except:
                    member = None
        if not member or not any(r.id == CITATION_ROLE_ID for r in member.roles):
            await interaction.response.send_message("Te ei ole politseiametnik!", ephemeral=True)
            return
        
        # Initialize database
        init_database()
        
        # Step 1: Show player info modal
        modal = PlayerInfoModal(cog=self)
        await interaction.response.send_modal(modal)
    
    async def on_player_info_submitted(self, interaction: discord.Interaction, player_name: str, discord_id: str):
        """Handle player info submission"""
        try:
            target_discord_id = int(discord_id)
        except ValueError:
            await interaction.followup.send("❌ Vale Discordi ID formaat.", ephemeral=True)
            return

        player_record = get_player_by_discord_id(target_discord_id)
        if not player_record or player_record[1].lower() != player_name.lower():
            await interaction.followup.send(
                "Kontrolli andmed üle! Kontrolli, et RP nimi ja isiku discordi ID klapiks. (Caps sensitive)",
                ephemeral=True
            )
            return

        # Store data temporarily
        user_id = interaction.user.id
        self.citation_data[user_id] = {
            "player_name": player_name,
            "discord_id": target_discord_id,
            "selected_laws": {}
        }
        
        print(f"DEBUG on_player_info_submitted: user_id={user_id}, player_name={player_name}, target_discord_id={target_discord_id}")
        
        # Step 2: Show law selection dropdown
        try:
            laws = get_all_laws()
            
            if not laws:
                await interaction.followup.send(
                    "Süsteemis pole seadusi määratud. Palun lisa seadused esmalt.",
                    ephemeral=True
                )
                return
            
            law_select_view = LawSelectView(laws)
            law_select_view.user_id = user_id
            law_select_view.citation_data = self.citation_data
            
            embed = discord.Embed(
                title="Vali rikkumised",
                description="Vali kõik rikkumised. Summa uuendatakse automaatselt.",
                color=discord.Color.orange()
            )
            
            await interaction.followup.send(embed=embed, view=law_select_view, ephemeral=True)
            
            # Wait for law selection
            await law_select_view.wait()
            
            if law_select_view.selected_laws:
                await self.show_confirmation(interaction, user_id, law_select_view)
        except Exception as e:
            print(f"Error in citation flow: {e}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)
            except:
                pass
    
    async def show_confirmation(self, interaction: discord.Interaction, user_id: int, law_select_view: LawSelectView):
        """Show confirmation screen with all citation details"""
        
        data = self.citation_data[user_id]
        data["selected_laws"] = law_select_view.selected_laws
        data["total_fine"] = law_select_view.total_fine
        
        print(f"DEBUG show_confirmation: user_id={user_id}, data={data}")
        
        laws_text = "\n".join([f"• {name} (${fine:.2f})" for name, fine in law_select_view.selected_laws.values()])
        
        embed = discord.Embed(
            title="Trahvi andmed",
            color=discord.Color.blue(),
            description="Kontrolli sisestatud andmed"
        )
        embed.add_field(name="RP nimi", value=data["player_name"], inline=False)
        embed.add_field(name="Discordi ID", value=str(data["discord_id"]), inline=False)
        embed.add_field(name="Rikkumised", value=laws_text, inline=False)
        embed.add_field(name="Kokku trahv", value=f"${data['total_fine']:.2f}", inline=False)
        
        view = ConfirmationView(callback=self.on_citation_confirmed)
        view.user_id = user_id
        view.citation_data = self.citation_data
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="ajalugu", description="Show citation history for a player")
    @app_commands.guilds(GUILD_ID)
    async def history_command(self, interaction: discord.Interaction, target: discord.User):
        """Show citation history for a given user"""
        # Role check - only allow users with the configured role
        member = None
        if interaction.guild:
            member = interaction.guild.get_member(interaction.user.id)
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(interaction.user.id)
                except:
                    member = None
        if not member or not any(r.id == CITATION_ROLE_ID for r in member.roles):
            await interaction.response.send_message("Te ei ole politseiametnik!", ephemeral=True)
            return

        init_database()
        citations = get_citations_by_discord_id(target.id)

        if not citations:
            await interaction.response.send_message(
                f"No citation history found for {target.mention}.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Trahvide ajalugu: {target}",
            color=discord.Color.blurple(),
            description=f"Leitud {len(citations)} trahvi kasutaja jaoks {target.mention}."
        )

        for citation in citations[:10]:
            _, player_name, _, total_fine, laws_broken, created_at, paid, cited_by_id, cited_by_name = citation
            cited_by_text = cited_by_name or str(cited_by_id) if cited_by_id else "Tundmatu"
            paid_text = "Jah" if paid else "Ei"
            embed.add_field(
                name=f"{created_at} — ${total_fine:.2f}",
                value=(
                    f"**Mängija:** {player_name}\n"
                    f"**Rikkumised:** {laws_broken}\n"
                    f"**Kelle poolt:** {target.mention}\n"
                ),
                inline=False
            )

        if len(citations) > 10:
            embed.set_footer(text=f"Kuvatud 10-st {len(citations)} trahvidest")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_citation_confirmed(self, interaction: discord.Interaction, user_id: int, confirmed: bool):
        """Handle citation confirmation"""
        
        if not confirmed:
            await interaction.response.send_message("Trahv tühistatud.", ephemeral=True)
            del self.citation_data[user_id]
            return
        
        print(f"DEBUG on_citation_confirmed: user_id={user_id}")
        print(f"DEBUG citation_data keys: {list(self.citation_data.keys())}")
        print(f"DEBUG citation_data[{user_id}]: {self.citation_data.get(user_id, 'NOT FOUND')}")
        
        data = self.citation_data[user_id]
        player_name = data["player_name"]
        discord_id = data["discord_id"]
        total_fine = data["total_fine"]
        selected_laws = data["selected_laws"]
        
        print(f"DEBUG: Player Name: {player_name}, Discord ID: {discord_id}, Total Fine: {total_fine}")
        
        # Deduct money using UnbelievaBoat API
        laws_names = ", ".join([name for name, _ in selected_laws.values()])
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{discord_id}"
                headers = {
                    "Authorization": UNBELIEVA_API_TOKEN
                }
                payload = {
                    "cash": -int(total_fine),
                    "reason": f"Citation for {laws_names}"
                }
                
                async with session.patch(url, json=payload, headers=headers) as resp:
                    response_text = await resp.text()
                    print(f"API Response Status: {resp.status}")
                    print(f"API Response Body: {response_text}")
                    print(f"URL: {url}")
                    print(f"Payload: {payload}")
                    
                    if resp.status == 200:
                        # Insert citation to database after successful deduction
                        insert_citation(
                            player_name,
                            discord_id,
                            total_fine,
                            laws_names,
                            cited_by_id=interaction.user.id,
                            cited_by_name=interaction.user.mention
                        )
                        
                        # Success message to issuer
                        embed = discord.Embed(
                            title="Trahv väljastatud",
                            color=discord.Color.green(),
                            description=f"Trahv summas **${total_fine:.2f}** väljastatud mängijale **{player_name}**.\n\nRaha on eemaldatud isikult edukalt eemaldatud!"
                        )
                        
                        await interaction.response.send_message(embed=embed, ephemeral=True)

                        # Send DM to fined user
                        try:
                            dm_embed = discord.Embed(
                                title="Trahv väljastatud",
                                color=discord.Color.blue(),
                                description="Sulle väljastati trahv"
                            )
                            dm_embed.add_field(name="Summa", value=f"${total_fine:.2f}", inline=False)
                            dm_embed.add_field(name="Põhjus", value=laws_names or "Määramata", inline=False)
                            dm_embed.add_field(name="Väljastav ametnik", value=interaction.user.mention, inline=False)

                            user_obj = await self.bot.fetch_user(discord_id)
                            await user_obj.send(embed=dm_embed)
                        except Exception as e:
                            print(f"Failed to send DM to {discord_id}: {e}")
                    else:
                        await interaction.response.send_message(
                            f"❌ Viga raha eemaldamisel: {resp.status} - {response_text}",
                            ephemeral=True
                        )
        
        except Exception as e:
            print(f"Error processing citation: {e}")
            import traceback
            traceback.print_exc()
            await interaction.response.send_message(f"Viga: {str(e)}", ephemeral=True)
        
        # Clean up
        del self.citation_data[user_id]

class ConfirmationView(View):
    """View for confirming citation"""
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
    
    @discord.ui.button(label="Salvesta", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"DEBUG confirm_button: user_id={self.user_id}")
        await self.callback(interaction, self.user_id, True)
    
    @discord.ui.button(label="Tühista", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.callback(interaction, self.user_id, False)

async def setup(bot):
    await bot.add_cog(CitationCog(bot))
