import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box
import logging
from collections import deque
from datetime import datetime

log = logging.getLogger("red.applicationmonitor")

class ApplicationMonitor(commands.Cog):
    """Monitor membership applications and notify specified roles."""
    
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        
        # In-memory log storage (last 50 entries per guild)
        self.guild_logs = {}
        
        # Default settings
        default_guild = {
            "notification_channel": None,
            "notification_role": None,
            "enabled": False,
            "debug": False
        }
        
        self.config.register_guild(**default_guild)
    
    def add_log(self, guild_id: int, message: str, level: str = "INFO"):
        """Add a log entry for a specific guild."""
        if guild_id not in self.guild_logs:
            self.guild_logs[guild_id] = deque(maxlen=50)
        
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.guild_logs[guild_id].append(log_entry)
        
        # Also log to Red's logging system
        if level == "ERROR":
            log.error(message)
        elif level == "WARNING":
            log.warning(message)
        else:
            log.info(message)
    
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
    async def debug(self, ctx):
        """Toggle debug mode for troubleshooting."""
        current = await self.config.guild(ctx.guild).debug()
        await self.config.guild(ctx.guild).debug.set(not current)
        status = "enabled" if not current else "disabled"
        await ctx.send(f"Debug mode has been {status}.")
    
    @appmonitor.command()
    async def test(self, ctx):
        """Send a test notification to verify setup."""
        guild_config = await self.config.guild(ctx.guild).all()
        
        if not guild_config["enabled"]:
            await ctx.send("❌ Application monitoring is disabled. Enable it first with `[p]appmonitor toggle`")
            return
            
        channel_id = guild_config["notification_channel"]
        role_id = guild_config["notification_role"]
        
        if not channel_id or not role_id:
            await ctx.send("❌ Please configure both channel and role first.")
            return
            
        channel = ctx.guild.get_channel(channel_id)
        role = ctx.guild.get_role(role_id)
        
        if not channel or not role:
            await ctx.send("❌ Invalid channel or role configuration.")
            return
        
        # Send test notification
        embed = discord.Embed(
            title="🧪 Test Notification",
            description=f"This is a test notification from Application Monitor.",
            color=discord.Color.orange()
        )
        
        try:
            await channel.send(f"{role.mention} - Test notification!", embed=embed)
            await ctx.send(f"✅ Test notification sent to {channel.mention}")
        except discord.Forbidden:
            await ctx.send(f"❌ Missing permissions to send message in {channel.mention}")
    @appmonitor.command()
    async def settings(self, ctx):
        """Show current application monitoring settings."""
        await self.show_settings(ctx)
    
    @appmonitor.command()
    async def logs(self, ctx, lines: int = 20):
        """Show recent logs for this server (max 50 lines)."""
        guild_id = ctx.guild.id
        
        if guild_id not in self.guild_logs or not self.guild_logs[guild_id]:
            await ctx.send("No logs available for this server.")
            return
        
        # Limit lines to reasonable amount
        lines = min(max(lines, 1), 50)
        
        # Get the most recent logs
        recent_logs = list(self.guild_logs[guild_id])[-lines:]
        
        if not recent_logs:
            await ctx.send("No logs available for this server.")
            return
        
        # Format logs for display
        log_text = "\n".join(recent_logs)
        
        # Split into chunks if too long for Discord
        if len(log_text) > 1900:  # Leave room for code block formatting
            chunks = []
            current_chunk = ""
            
            for log_line in recent_logs:
                if len(current_chunk + log_line + "\n") > 1900:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = log_line + "\n"
                else:
                    current_chunk += log_line + "\n"
            
            if current_chunk:
                chunks.append(current_chunk)
            
            # Send chunks
            for i, chunk in enumerate(chunks):
                header = f"Application Monitor Logs (Part {i+1}/{len(chunks)})" if len(chunks) > 1 else "Application Monitor Logs"
                await ctx.send(f"**{header}**\n{box(chunk, lang='log')}")
        else:
            await ctx.send(f"**Application Monitor Logs (Last {len(recent_logs)} entries)**\n{box(log_text, lang='log')}")
    
    @appmonitor.command()
    async def clearlogs(self, ctx):
        """Clear all logs for this server."""
        guild_id = ctx.guild.id
        
        if guild_id in self.guild_logs:
            self.guild_logs[guild_id].clear()
            await ctx.send("✅ Logs cleared for this server.")
        else:
            await ctx.send("No logs to clear for this server.")
    
    async def show_settings(self, ctx):
        """Display current settings for the guild."""
        guild_config = await self.config.guild(ctx.guild).all()
        
        enabled = guild_config["enabled"]
        debug = guild_config["debug"]
        channel_id = guild_config["notification_channel"]
        role_id = guild_config["notification_role"]
        
        channel = ctx.guild.get_channel(channel_id) if channel_id else None
        role = ctx.guild.get_role(role_id) if role_id else None
        
        # Check membership screening
        has_screening = hasattr(ctx.guild, 'rules_channel') and ctx.guild.rules_channel is not None
        
        settings_text = f"""
        Application Monitor Settings for {ctx.guild.name}
        
        Status: {'Enabled' if enabled else 'Disabled'}
        Debug Mode: {'Enabled' if debug else 'Disabled'}
        Notification Channel: {channel.mention if channel else 'Not Set'}
        Notification Role: {role.mention if role else 'Not Set'}
        
        Server Info:
        Membership Screening: {'Enabled' if has_screening else 'Disabled'}
        Rules Channel: {ctx.guild.rules_channel.mention if ctx.guild.rules_channel else 'Not Set'}
        """
        
        await ctx.send(box(settings_text, lang="yaml"))
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Triggered when a member joins the server."""
        guild_config = await self.config.guild(member.guild).all()
        debug = guild_config["debug"]
        
        self.add_log(member.guild.id, f"Member join event: {member} ({member.id})")
        
        if debug:
            self.add_log(member.guild.id, f"Member pending: {member.pending}")
            self.add_log(member.guild.id, f"Guild has rules channel: {member.guild.rules_channel is not None}")
        
        # Check if monitoring is enabled for this guild
        if not guild_config["enabled"]:
            self.add_log(member.guild.id, f"Monitoring disabled - skipping notification")
            return
        
        # For servers with membership screening, we want to catch pending members
        # For servers without screening, we catch all joins
        should_notify = False
        
        if member.guild.rules_channel:
            # Server has membership screening - notify for pending members
            should_notify = member.pending
            self.add_log(member.guild.id, f"Server has screening, member pending: {member.pending}, will notify: {should_notify}")
        else:
            # Server doesn't have screening - notify for all joins
            should_notify = True
            self.add_log(member.guild.id, f"Server has no screening, notifying for all joins")
        
        if not should_notify:
            self.add_log(member.guild.id, f"Not notifying for {member} - should_notify: {should_notify}")
            return
            
        # Get configuration
        channel_id = guild_config["notification_channel"]
        role_id = guild_config["notification_role"]
        
        if not channel_id or not role_id:
            self.add_log(member.guild.id, f"Application monitor not fully configured (channel: {channel_id}, role: {role_id})", "WARNING")
            return
            
        channel = member.guild.get_channel(channel_id)
        role = member.guild.get_role(role_id)
        
        if not channel or not role:
            self.add_log(member.guild.id, f"Invalid channel or role configuration (channel exists: {channel is not None}, role exists: {role is not None})", "WARNING")
            return
        
        # Create notification message
        title = "New Membership Application" if member.pending else "New Member Joined"
        description = f"**{member.mention}** has {'applied to join' if member.pending else 'joined'} the server."
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue(),
            timestamp=member.joined_at
        )
        
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="Joined At", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        
        if member.pending:
            embed.add_field(name="Status", value="Pending Approval", inline=True)
        
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        # Send notification with role mention
        try:
            message_text = f"{role.mention} - {'New application received!' if member.pending else 'New member joined!'}"
            await channel.send(message_text, embed=embed)
            self.add_log(member.guild.id, f"Sent {'application' if member.pending else 'join'} notification for {member} to {channel.name}")
        except discord.Forbidden:
            self.add_log(member.guild.id, f"Missing permissions to send message in {channel.name}", "ERROR")
        except Exception as e:
            self.add_log(member.guild.id, f"Error sending notification: {e}", "ERROR")
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Triggered when a member's status changes (including passing screening)."""
        guild_config = await self.config.guild(after.guild).all()
        debug = guild_config["debug"]
        
        # Check if this is a membership screening completion
        if before.pending and not after.pending:
            self.add_log(after.guild.id, f"Member screening completed: {after} ({after.id})")
            
            # Check if monitoring is enabled
            if not guild_config["enabled"]:
                self.add_log(after.guild.id, f"Monitoring disabled - skipping approval notification")
                return
                
            # Get configuration
            channel_id = guild_config["notification_channel"]
            role_id = guild_config["notification_role"]
            
            if not channel_id or not role_id:
                self.add_log(after.guild.id, f"Channel or role not configured for approval notifications", "WARNING")
                return
                
            channel = after.guild.get_channel(channel_id)
            role = after.guild.get_role(role_id)
            
            if not channel or not role:
                self.add_log(after.guild.id, f"Invalid channel or role for approval notifications", "WARNING")
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
                self.add_log(after.guild.id, f"Sent approval notification for {after} to {channel.name}")
            except Exception as e:
                self.add_log(after.guild.id, f"Error sending approval notification: {e}", "ERROR")
