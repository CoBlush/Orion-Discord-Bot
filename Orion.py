# [Code updated to auto-create VERIFIED_ROLE if missing in verification view.]

import discord
from discord.ext import commands, tasks
import os
import json
import time
import asyncio
from collections import defaultdict

# ─── Configuration ─────────────────────────────────────────────────────────────
TOKEN               = ""  # Your bot token here
DATA_FILE           = "bot_data.json"
JAIL_ROLE_ID        = 123456789012345678  # Fallback ID for the “jailed” role
VERIFIED_ROLE_ID    = 876543210987654321  # ID for the “verified” role
VERIFY_TIMEOUT      = 60                   # Seconds until auto-jail on verification timeout
ANTIRAID_LEVELS     = ["low", "medium", "high"]  # Sensitivity levels for anti-raid
AUTO_JAIL_ROLE_NAME = "jailed"           # Name for auto-created jail role
AUTO_VERIFIED_ROLE_NAME = "verified"     # Name for auto-created verified role

intents = discord.Intents.all()
bot = commands.AutoShardedBot(command_prefix="!", intents=intents, help_command=None)

# ─── In-Memory Guild Data ───────────────────────────────────────────────────────
guild_data = defaultdict(lambda: {
    "blacklist": set(),
    "whitelist": set(),
    "settings": {
        "timeout": 900,
        "spam_threshold": 5,
        "antiraid_enabled": False,
        "antiraid_level": "medium"
    },
    "incident_log": [],
    "log_channel": None
})

# ─── Persist & Load Helpers ────────────────────────────────────────────────────
async def save_data():
    to_save = {}
    for gid, data in guild_data.items():
        to_save[gid] = {
            "blacklist": list(data["blacklist"]),
            "whitelist": list(data["whitelist"]),
            "settings": data["settings"],
            "incident_log": data["incident_log"],
            "log_channel": data["log_channel"]
        }
    with open(DATA_FILE, "w") as f:
        json.dump(to_save, f, indent=2)

# Load saved data on startup
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        raw = json.load(f)
    for gid, data in raw.items():
        guild_data[gid]["blacklist"] = set(data.get("blacklist", []))
        guild_data[gid]["whitelist"] = set(data.get("whitelist", []))
        guild_data[gid]["settings"] = data.get("settings", guild_data[gid]["settings"])
        guild_data[gid]["incident_log"] = data.get("incident_log", [])
        guild_data[gid]["log_channel"] = data.get("log_channel")

# ─── Helper: Ensure Jail Role Exists ───────────────────────────────────────────
async def get_or_create_jail_role(guild: discord.Guild) -> discord.Role:
    role = guild.get_role(JAIL_ROLE_ID)
    if role:
        return role
    role = discord.utils.get(guild.roles, name=AUTO_JAIL_ROLE_NAME)
    if role:
        return role
    return await guild.create_role(name=AUTO_JAIL_ROLE_NAME, reason="Auto-created jail role")

# ─── Helper: Ensure Verified Role Exists ───────────────────────────────────────
async def get_or_create_verified_role(guild: discord.Guild) -> discord.Role:
    role = guild.get_role(VERIFIED_ROLE_ID)
    if role:
        return role
    role = discord.utils.get(guild.roles, name=AUTO_VERIFIED_ROLE_NAME)
    if role:
        return role
    return await guild.create_role(name=AUTO_VERIFIED_ROLE_NAME, reason="Auto-created verified role")

# ─── Verification View ──────────────────────────────────────────────────────────
class VerificationView(discord.ui.View):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=VERIFY_TIMEOUT)
        self.member = member
        self.verified = False

    @discord.ui.button(label="✅ Verify Me", style=discord.ButtonStyle.success)
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            return await interaction.response.send_message("❌ This button isn’t for you.", ephemeral=True)
        verified_role = await get_or_create_verified_role(interaction.guild)
        await self.member.add_roles(verified_role, reason="Completed verification")
        self.verified = True
        await interaction.response.edit_message(content="✅ You’re now verified!", view=None)
        self.stop()

    async def on_timeout(self):
        if not self.verified:
            jail_role = await get_or_create_jail_role(self.member.guild)
            await self.member.add_roles(jail_role, reason="Failed to verify in time")
            try:
                await self.member.send(
                    "🚨 You didn’t verify in time and have been jailed. "
                    "Please contact a moderator to be released."
                )
            except discord.Forbidden:
                pass

# ... rest of the script unchanged ...

# ─── Permission Check ────────────────────────────────────────────────────────────
def is_secbo_member(member: discord.Member) -> bool:
    return any(r.name.lower() == "secbo" for r in member.roles)

@bot.check
async def require_secbo(ctx):
    open_commands = ("help", "makesecadmin", "unmakesecadmin", "verify", "antiraid", "config")
    if ctx.command.name in open_commands:
        return True
    if is_secbo_member(ctx.author):
        return True
    raise commands.MissingRole("secbo")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("❌ You need the **secbo** role to use that command.")
    else:
        raise error

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

# ─── Admin Setup Commands ─────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(administrator=True)
async def makesecadmin(ctx, *members: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="secbo") or await ctx.guild.create_role(name="secbo", reason="Setup secbo role")
    targets = members or (ctx.author,)
    added = []
    for member in targets:
        if role not in member.roles:
            await member.add_roles(role, reason="Granted secbo access")
            added.append(member.mention)
    msg = f"✅ Added {', '.join(added)} to **secbo**." if added else "⚠️ No new members were added."
    await ctx.send(msg)

@bot.command()
@commands.has_permissions(administrator=True)
async def unmakesecadmin(ctx, *members: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="secbo")
    if not role:
        return await ctx.send("⚠️ **secbo** role does not exist.")
    targets = members or (ctx.author,)
    removed = []
    for member in targets:
        if role in member.roles:
            await member.remove_roles(role, reason="Revoked secbo access")
            removed.append(member.mention)
    msg = f"✅ Removed {', '.join(removed)} from **secbo**." if removed else "⚠️ No specified members had the secbo role."
    await ctx.send(msg)

# ─── Core Bot Commands ─────────────────────────────────────────────────────────
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="🛡️ Security Bot Commands", color=discord.Color.blue())
    embed.add_field(name="Verification", value="!verify", inline=False)
    embed.add_field(name="Jail Management", value="!jail @user | !unjail @user | !jailtemp @user <s>", inline=False)
    embed.add_field(name="Anti-Raid", value="!antiraid on/off/low/medium/high", inline=False)
    embed.add_field(name="Logs & Configuration", value="!auditlog | !downloadlog | !setlog #channel | !config <setting> <value>", inline=False)
    embed.add_field(name="Lockdown", value="!lockdown on/off | !paniclock", inline=False)
    embed.add_field(name="Moderation Tools", value="!slowmode <seconds> | !blacklist_add/remove @user | !whitelist_add/remove @user", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def verify(ctx):
    view = VerificationView(ctx.author)
    await ctx.send(
        f"Welcome {ctx.author.mention}! Please verify within {VERIFY_TIMEOUT}s or be jailed.",
        view=view
    )

@bot.command()
async def jail(ctx, member: discord.Member):
    """Assigns the jail role to a member."""
    role = await get_or_create_jail_role(ctx.guild)
    await member.add_roles(role, reason=f"Jailed by {ctx.author.id}")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    gid = str(ctx.guild.id)
    guild_data[gid]["incident_log"].append(f"{ts} - {member.id} jailed by {ctx.author.id}")
    await save_data()
    await ctx.send(f"🚨 {member.mention} has been jailed.")

@bot.command()
async def unjail(ctx, member: discord.Member):
    """Removes the jail role from a member."""
    role = await get_or_create_jail_role(ctx.guild)
    await member.remove_roles(role, reason=f"Unjailed by {ctx.author.id}")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    gid = str(ctx.guild.id)
    guild_data[gid]["incident_log"].append(f"{ts} - {member.id} unjailed by {ctx.author.id}")
    await save_data()
    await ctx.send(f"✅ {member.mention} has been released from jail.")

@bot.command()
async def jailtemp(ctx, member: discord.Member, seconds: int):
    """Temporarily jails a member for a specified duration."""
    role = await get_or_create_jail_role(ctx.guild)
    await member.add_roles(role, reason=f"Temp jailed by {ctx.author.id} for {seconds}s")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    gid = str(ctx.guild.id)
    guild_data[gid]["incident_log"].append(f"{ts} - {member.id} temp-jailed by {ctx.author.id} for {seconds}s")
    await save_data()
    await ctx.send(f"⏱️ {member.mention} has been jailed for {seconds} seconds.")
    await asyncio.sleep(seconds)
    await member.remove_roles(role, reason="Temp jail expired")
    ts2 = time.strftime("%Y-%m-%d %H:%M:%S")
    guild_data[gid]["incident_log"].append(f"{ts2} - {member.id} released from temp-jail")
    await save_data()
    await ctx.send(f"✅ {member.mention} has been released from temp jail.")

@bot.command()
async def antiraid(ctx, mode: str):
    """Toggles or configures anti-raid protection."""
    gid = str(ctx.guild.id)
    setting = mode.lower()
    if setting == "on":
        guild_data[gid]["settings"]["antiraid_enabled"] = True
        response = f"🛡️ Anti-raid enabled. Level: **{guild_data[gid]['settings']['antiraid_level']}**."
    elif setting == "off":
        guild_data[gid]["settings"]["antiraid_enabled"] = False
        response = "❌ Anti-raid disabled."
    elif setting in ANTIRAID_LEVELS:
        guild_data[gid]["settings"]["antiraid_level"] = setting
        guild_data[gid]["settings"]["antiraid_enabled"] = True
        response = f"🛡️ Anti-raid level set to **{setting}** and enabled."
    else:
        return await ctx.send("⚠️ Invalid mode. Use on/off or low/medium/high.")
    await save_data()
    await ctx.send(response)

@bot.command()
async def auditlog(ctx):
    gid = str(ctx.guild.id)
    logs = guild_data[gid].get("incident_log", [])
    if not logs:
        return await ctx.send("📜 No incidents logged.")
    await ctx.send("\n".join(f"- {entry}" for entry in logs[-10:]))

@bot.command()
async def downloadlog(ctx):
    gid = str(ctx.guild.id)
    logs = guild_data[gid].get("incident_log", [])
    if not logs:
        return await ctx.send("📜 No logs to download.")
    # Filter to user-specific entries; fallback to all if none
    user_entries = [e for e in logs if f"{ctx.author.id}" in e]
    lines = user_entries or logs
    filename = f"incident_log_{gid}_{ctx.author.id}.txt"
    with open(filename, "w") as f:
        f.write("\n".join(lines))
    await ctx.send(file=discord.File(filename))
    os.remove(filename)

@bot.command()
async def setlog(ctx, channel: discord.TextChannel):
    gid = str(ctx.guild.id)
    guild_data[gid]["log_channel"] = channel.id
    await ctx.send(f"📜 Log channel set to {channel.mention}.")
    await save_data()

@bot.command()
async def lockdown(ctx, mode: str):
    gid = str(ctx.guild.id)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    if mode.lower() == "on":
        for ch in ctx.guild.text_channels:
            await ch.set_permissions(ctx.guild.default_role, send_messages=False)
        guild_data[gid]["incident_log"].append(f"{ts} - Lockdown ON by {ctx.author.id}")
        await ctx.send("🔒 Server locked down.")
    elif mode.lower() == "off":
        for ch in ctx.guild.text_channels:
            await ch.set_permissions(ctx.guild.default_role, send_messages=True)
        guild_data[gid]["incident_log"].append(f"{ts} - Lockdown OFF by {ctx.author.id}")
        await ctx.send("🔓 Lockdown lifted.")
    await save_data()

@bot.command()
async def paniclock(ctx):
    gid = str(ctx.guild.id)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    for ch in ctx.guild.text_channels:
        await ch.set_permissions(ctx.guild.default_role, send_messages=False)
        await ch.edit(slowmode_delay=10)
    guild_data[gid]["incident_log"].append(f"{ts} - Panic Lockdown by {ctx.author.id}")
    await ctx.send("🚨 Panic lockdown enabled.")
    await save_data()

@bot.command()
async def config(ctx, setting: str, value: str):
    gid = str(ctx.guild.id)
    if setting == "timeout" and value.isdigit():
        guild_data[gid]["settings"]["timeout"] = int(value)
        msg = f"⏱️ Timeout set to {value}s."
    elif setting == "spam_threshold" and value.isdigit():
        guild_data[gid]["settings"]["spam_threshold"] = int(value)
        msg = f"🚦 Spam threshold set to {value}."
    else:
        msg = "⚙️ Usage: !config timeout <seconds> | spam_threshold <number>"
    await save_data()
    await ctx.send(msg)

@bot.command()
async def slowmode(ctx, seconds: int):
    for ch in ctx.guild.text_channels:
        await ch.edit(slowmode_delay=seconds)
    status = "off" if seconds == 0 else f"{seconds}s"
    await ctx.send(f"👒 Slowmode set to {status} for all channels.")

@bot.command()
async def blacklist_add(ctx, member: discord.Member):
    gid = str(ctx.guild.id)
    guild_data[gid]["blacklist"].add(member.id)
    await ctx.send(f"✅ {member.mention} added to blacklist.")
    await save_data()

@bot.command()
async def blacklist_remove(ctx, member: discord.Member):
    gid = str(ctx.guild.id)
    guild_data[gid]["blacklist"].discard(member.id)
    await ctx.send(f"✅ {member.mention} removed from blacklist.")
    await save_data()

@bot.command()
async def whitelist_add(ctx, member: discord.Member):
    gid = str(ctx.guild.id)
    guild_data[gid]["whitelist"].add(member.id)
    await ctx.send(f"✅ {member.mention} added to whitelist.")
    await save_data()

@bot.command()
async def whitelist_remove(ctx, member: discord.Member):
    gid = str(ctx.guild.id)
    guild_data[gid]["whitelist"].discard(member.id)
    await ctx.send(f"✅ {member.mention} removed from whitelist.")
    await save_data()

# ─── Run Bot ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)
