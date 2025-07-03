import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box
import logging
from collections import deque
from datetime import datetime
import asyncio

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
            "debug": False,
            "check_interval": 60  # Check every 60 seconds for pending members
        }
        
        self.config.register_guild(**default_guild)
        
        # Track known pending members to detect new applications
        self.known_pending = {}
        
        # Start the background task
        self.check_task = asyncio.create_task(self.periodic_check())
    
    def cog_unload(self):
        """Clean up when cog is unloaded."""
        if hasattr(self, 'check_task'):
            self.check_task.cancel()
    
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
    
    async def periodic_check(self):
        """Periodically check for new pending members."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                for guild in self.bot.guilds:
                    guild_config = await self.config.guild(guild).all()
                    
                    if not guild_config["enabled"]:
                        continue
                    
                    # Check for pending members
                    await self.check_pending_members(guild)
                    
                # Wait for the configured interval
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                log.error(f"Error in periodic check: {e}")
                await asyncio.sleep(60)
    
    async def check_pending_members(self, guild):
        """Check for new pending members in a guild."""
        try:
            guild_config = await self.config.guild(guild).all()
            
            if not guild_config["enabled"]:
                return
            
            # Get current pending members
            pending_members = [member for member in guild.members if member.pending]
            current_pending_ids = {member.id for member in pending_members}
            
            # Get previously known pending members for this guild
            known_pending_ids = self.known_pending.get(guild.id, set())
            
            # Find new pending members
            new_pending_ids = current_pending_ids - known_pending_ids
            
            if new_pending_ids:
                self.add_log(guild.id, f"Found {len(new_pending_ids)} new pending members")
                
                for member_id in new_pending_ids:
                    member = guild.get_member(member_id)
                    if member:
                        await self.notify_new_application(member, guild_config)
            
            # Update known pending members
            self.known_pending[guild.id] = current_pending_ids
            
            if guild_config["debug"]:
                self.add_log(guild.id, f"Periodic check: {len(current_pending_ids)} pending members total")
                
        except Exception as e:
            self.add_log(guild.id, f"Error checking pending members: {e}", "ERROR")
    
    async def notify_new_application(self, member, guild_config):
        """Send notification for a new application."""
        channel_id = guild_config["notification_channel"]
        role_id = guild_config["notification_role"]
        
        if not channel_id or not role_id:
            self.add_log(member.guild.id, f"Notification config missing for new application from {member}")
            return
        
        channel = member.guild.get_channel(channel_id)
        role = member.guild.get_role(role_id)
        
        if not channel or not role:
            self.add_log(member.guild.id, f"Invalid channel or role for new application from {member}")
            return
        
        # Create notification message
        embed = discord.Embed(
            title="🔔 New Membership Application",
            description=f"**{member.mention}** has applied to join the server and is pending approval.",
            color=discord.Color.blue(),
            timestamp=member.joined_at or datetime.utcnow()
        )
        
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="Status", value="⏳ Pending Approval", inline=True)
        
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        try:
            await channel.send(f"{role.mention} - New application received!", embed=embed)
            self.add_log(member.guild.id, f"Sent application notification for {member} to {channel.name}")
        except Exception as e:
            self.add_log(member.guild.id, f"Error sending application notification: {e}", "ERROR")
    
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
        
        if not current:  # If we just enabled it
            # Initialize known pending members (mark existing ones as already known)
            pending_members = [member for member in ctx.guild.members if member.pending]
            self.known_pending[ctx.guild.id] = {member.id for member in pending_members}
            self.add_log(ctx.guild.id, f"Monitoring enabled. Marked {len(pending_members)} existing pending members as known (won't notify for these).")
            await ctx.send(f"Application monitoring has been {status}.\n✅ Found {len(pending_members)} existing pending members - these won't trigger notifications.\n🔔 Only **new** applications from now on will send notifications.")
        else:
            # Clear known pending when disabling
            if ctx.guild.id in self.known_pending:
                del self.known_pending[ctx.guild.id]
            self.add_log(ctx.guild.id, f"Monitoring disabled. Cleared known pending members.")
            await ctx.send(f"Application monitoring has been {status}.")
    
    @appmonitor.command()
    async def debug(self, ctx):
        """Toggle debug mode for troubleshooting."""
        current = await self.config.guild(ctx.guild).debug()
        await self.config.guild(ctx.guild).debug.set(not current)
        status = "enabled" if not current else "disabled"
        await ctx.send(f"Debug mode has been {status}.")
    
    @appmonitor.command()
    async def pending(self, ctx):
        """Show current pending members."""
        pending_members = [member for member in ctx.guild.members if member.pending]
        
        if not pending_members:
            await ctx.send("No pending members found.")
            return
        
        embed = discord.Embed(
            title="📋 Current Pending Members",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        
        for i, member in enumerate(pending_members[:25], 1):  # Limit to 25 for embed limits
            embed.add_field(
                name=f"{i}. {member}",
                value=f"ID: {member.id}\nJoined: {member.joined_at.strftime('%Y-%m-%d %H:%M:%S') if member.joined_at else 'Unknown'}",
                inline=True
            )
        
        if len(pending_members) > 25:
            embed.set_footer(text=f"Showing first 25 of {len(pending_members)} pending members")
        
        await ctx.send(embed=embed)
    
    @appmonitor.command()
    async def reset(self, ctx):
        """Reset the known pending members list (useful if you got wrong notifications)."""
        pending_members = [member for member in ctx.guild.members if member.pending]
        self.known_pending[ctx.guild.id] = {member.id for member in pending_members}
        self.add_log(ctx.guild.id, f"Reset known pending members. Marked {len(pending_members)} current pending members as known.")
    @appmonitor.command()
    async def forcescan(self, ctx):
        """Force scan for pending members now."""
        await ctx.send("🔍 Scanning for pending members...")
        
        try:
            await self.check_pending_members(ctx.guild)
            await ctx.send("✅ Scan completed. Check logs for details.")
        except Exception as e:
            await ctx.send(f"❌ Error during scan: {e}")
    
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
            self.add_log(ctx.guild.id, f"Test notification sent successfully to {channel.name}")
        except discord.Forbidden:
            await ctx.send(f"❌ Missing permissions to send message in {channel.mention}")
            self.add_log(ctx.guild.id, f"Missing permissions to send message in {channel.name}", "ERROR")
        except Exception as e:
            await ctx.send(f"❌ Error sending test notification: {e}")
            self.add_log(ctx.guild.id, f"Error sending test notification: {e}", "ERROR")
    
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
    
    @appmonitor.command()
    async def settings(self, ctx):
        """Show current application monitoring settings."""
        await self.show_settings(ctx)
    
    async def show_settings(self, ctx):
        """Display current settings for the guild."""
        guild_config = await self.config.guild(ctx.guild).all()
        
        enabled = guild_config["enabled"]
        debug = guild_config["debug"]
        channel_id = guild_config["notification_channel"]
        role_id = guild_config["notification_role"]
        
        channel = ctx.guild.get_channel(channel_id) if channel_id else None
        role = ctx.guild.get_role(role_id) if role_id else None
        
        # Check server access settings
        pending_members = [member for member in ctx.guild.members if member.pending]
        
        settings_text = f"""
        Application Monitor Settings for {ctx.guild.name}
        
        Status: {'Enabled' if enabled else 'Disabled'}
        Debug Mode: {'Enabled' if debug else 'Disabled'}
        Notification Channel: {channel.mention if channel else 'Not Set'}
        Notification Role: {role.mention if role else 'Not Set'}
        
        Server Info:
        Current Pending Members: {len(pending_members)}
        Monitoring Method: Periodic Scanning (every 60s)
        Known Pending: {len(self.known_pending.get(ctx.guild.id, set()))}
        """
        
        await ctx.send(box(settings_text, lang="yaml"))
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Triggered when a member's status changes (including passing screening)."""
        guild_config = await self.config.guild(after.guild).all()
        
        # Check if this is a membership screening completion
        if before.pending and not after.pending:
            self.add_log(after.guild.id, f"Member screening completed: {after} ({after.id})")
            
            # Remove from known pending
            if after.guild.id in self.known_pending:
                self.known_pending[after.guild.id].discard(after.id)
            
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
                title="✅ Application Approved",
                description=f"**{after.mention}** has completed membership screening and joined the server!",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="User", value=f"{after} ({after.id})", inline=True)
            embed.add_field(name="Originally Joined", value=after.joined_at.strftime("%Y-%m-%d %H:%M:%S") if after.joined_at else "Unknown", inline=True)
            
            if after.avatar:
                embed.set_thumbnail(url=after.avatar.url)
            
            try:
                await channel.send(f"{role.mention} - Member approved!", embed=embed)
                self.add_log(after.guild.id, f"Sent approval notification for {after} to {channel.name}")
            except Exception as e:
                self.add_log(after.guild.id, f"Error sending approval notification: {e}", "ERROR")
