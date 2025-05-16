from pathlib import Path

# Updated README content with secbo role requirement
readme_content = """# 🛡️ Discord Security Bot (Orion)

A multi-server, auto-sharded security bot built with `discord.py` that provides verification, jail management, anti-raid protection, audit logging, and more. Designed for moderation and anti-abuse in active Discord communities.

---

## 🚀 Features

- ✅ **Verification System**
  - Users must verify with a button or get jailed after a timeout.
  - Auto-creates a `verified` role if not found.

- 🚓 **Jail System**
  - Commands to `!jail`, `!unjail`, or temporarily jail users with `!jailtemp`.
  - Automatically jails users who don’t verify in time.
  - Jail role is auto-created if missing.

- 🛡️ **Anti-Raid Protection**
  - Toggle with `!antiraid on/off`.
  - Configurable levels: `low`, `medium`, `high`.

- 📜 **Audit Logging**
  - Record and download recent moderation actions via `!auditlog` and `!downloadlog`.

- 🔒 **Server Lockdown Tools**
  - `!lockdown on/off` to restrict all channels.
  - `!paniclock` enables lockdown + slowmode instantly.

- 🧰 **Moderation Settings**
  - Adjust slowmode across channels with `!slowmode <seconds>`.
  - Maintain `blacklist` and `whitelist`.

- 🔐 **Role-Based Permissions**
  - Only users with the `secbo` role can execute security and moderation commands.
  - `!makesecadmin` / `!unmakesecadmin` lets admins assign or remove this role.

---

## 📦 Setup

### Requirements

- Python 3.8+
- `discord.py` library

### Configuration
TOKEN = "Your_Discord_BOT_TOKEN"

### Installation

```bash
python3 -m venv .venv
source .venv/bin/activate  # or .venv\\Scripts\\activate on Windows
pip install -r requirements.txt





