from .applicationmonitor import ApplicationMonitor

async def setup(bot):
    await bot.add_cog(ApplicationMonitor(bot))
