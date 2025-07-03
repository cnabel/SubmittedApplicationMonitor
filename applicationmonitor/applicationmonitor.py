import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box
import logging

log = logging.getLogger("red.applicationmonitor")

class ApplicationMonitor(commands.Cog):
    """Monitor membership applications and notify specified roles."""
    
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        
        # Default settings
        default_guild = {
            "notification_channel": None,
            "notification_role": None,
            "enabled": False
        }
        
        self.config.register_guild(**default_guild)
    
    @commands.group()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def appmonitor(self, ctx):
        """Configure application monitoring settings."""
        if ctx.invoked_subcommand is None:
            await self.show_settings(ctx)
    
    @appmonitor.command()
    async def channel(self, ctx, channel: discord.TextChannel = None):
        """Set the notification channel for application alerts."""
        if channel is None:
            await self.config.guild(ctx.guild).notification_channel.set(None)
            await ctx.send("Notification channel has been cleared.")
        else:
            await self.config.guild(ctx.guild).notification_channel.set(channel.id)
            await ctx.send(f"Notification channel set to {channel.mention}")
    
    @appmonitor.command()
    async def role(self, ctx, role: discord.Role = None):
        """Set the role to notify when applications are received."""
        if role is None:
            await self.config.guild(ctx.guild).notification_role.set(None)
            await ctx.send("Notification role has been cleared.")
        else:
            await self.config.guild(ctx.guild).notification_role.set(role.id)
            await ctx.send(f"Notification role set to {role.mention}")
    
    @appmonitor.command()
    async def toggle(self, ctx):
        """Enable or disable application monitoring."""
        current = await self.config.guild(ctx.guild).enabled()
        await self.config.guild(ctx.guild).enabled.set(not current)
        status = "enabled" if not current else "disabled"
        await ctx.send(f"Application monitoring has been {status}.")
    
    @appmonitor.command()
    async def settings(self, ctx):
        """Show current application monitoring settings."""
        await self.show_settings(ctx)
    
    async def show_settings(self, ctx):
        """Display current settings for the guild."""
        guild_config = await self.config.guild(ctx.guild).all()
        
        enabled = guild_config["enabled"]
        channel_id = guild_config["notification_channel"]
        role_id = guild_config["notification_role"]
        
        channel = ctx.guild.get_channel(channel_id) if channel_id else None
        role = ctx.guild.get_role(role_id) if role_id else None
        
        settings_text = f"""
        Application Monitor Settings for {ctx.guild.name}
        
        Status: {'Enabled' if enabled else 'Disabled'}
        Notification Channel: {channel.mention if channel else 'Not Set'}
        Notification Role: {role.mention if role else 'Not Set'}
        """
        
        await ctx.send(box(settings_text, lang="yaml"))
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Triggered when a member joins the server."""
        # Check if the server has membership screening enabled
        if not member.guild.rules_channel:
            return
            
        # Check if monitoring is enabled for this guild
        if not await self.config.guild(member.guild).enabled():
            return
            
        # Get configuration
        guild_config = await self.config.guild(member.guild).all()
        channel_id = guild_config["notification_channel"]
        role_id = guild_config["notification_role"]
        
        if not channel_id or not role_id:
            log.warning(f"Application monitor not fully configured for {member.guild.name}")
            return
            
        channel = member.guild.get_channel(channel_id)
        role = member.guild.get_role(role_id)
        
        if not channel or not role:
            log.warning(f"Invalid channel or role configuration for {member.guild.name}")
            return
            
        # Create notification message
        embed = discord.Embed(
            title="New Membership Application",
            description=f"**{member.mention}** has applied to join the server.",
            color=discord.Color.blue(),
            timestamp=member.joined_at
        )
        
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="Joined At", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        # Send notification with role mention
        try:
            await channel.send(f"{role.mention} - New application received!", embed=embed)
            log.info(f"Sent application notification for {member} in {member.guild.name}")
        except discord.Forbidden:
            log.error(f"Missing permissions to send message in {channel.name}")
        except Exception as e:
            log.error(f"Error sending application notification: {e}")
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Triggered when a member's status changes (including passing screening)."""
        # Check if this is a membership screening completion
        if (before.pending and not after.pending and 
            hasattr(after, 'joined_at') and after.joined_at):
            
            # Check if monitoring is enabled
            if not await self.config.guild(after.guild).enabled():
                return
                
            # Get configuration
            guild_config = await self.config.guild(after.guild).all()
            channel_id = guild_config["notification_channel"]
            role_id = guild_config["notification_role"]
            
            if not channel_id or not role_id:
                return
                
            channel = after.guild.get_channel(channel_id)
            role = after.guild.get_role(role_id)
            
            if not channel or not role:
                return
                
            # Create approval notification
            embed = discord.Embed(
                title="Application Approved",
                description=f"**{after.mention}** has completed membership screening and joined the server!",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="User", value=f"{after} ({after.id})", inline=True)
            embed.add_field(name="Originally Joined", value=after.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
            
            if after.avatar:
                embed.set_thumbnail(url=after.avatar.url)
            
            try:
                await channel.send(f"{role.mention} - Member approved!", embed=embed)
                log.info(f"Sent approval notification for {after} in {after.guild.name}")
            except Exception as e:
                log.error(f"Error sending approval notification: {e}")
