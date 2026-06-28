# WispByte Hosting Setup

## Quick Start

Follow these steps to deploy your Discord bot to WispByte:

### 1. Prepare Your Local Files
- Navigate to the project directory
- Ensure all files are present (check `requirements.txt`, `.env.example`, `main.py`)
- Delete `__pycache__/` directories and `*.pyc` files
- Remove the local `data/citations.db` (it will be created on first run)

### 2. Create the Archive
Option A: Using PowerShell
```powershell
Compress-Archive -Path .\* -DestinationPath bot.zip -Exclude '__pycache__', 'citations.db', '.env', '.venv', 'env'
```

Option B: Using Windows Explorer
- Select all files (Ctrl+A)
- Right-click → Send to → Compressed (zipped) folder
- Manually exclude: `__pycache__`, `citations.db`, `.env`, `.venv` folders

### 3. Upload to WispByte
1. Go to your WispByte file manager
2. Click **Upload Files** (max 100MiB)
3. Select your `bot.zip` file
4. After upload, click **Extract** to unzip into the container

### 4. Set Main Entry Point
1. In the file manager, find `main.py`
2. Click the menu (•••) next to it
3. Select **Use on startup**

### 5. Configure Environment Variables
1. In WispByte console/settings, set these environment variables:
   - `DISCORD_TOKEN` - Your Discord bot token
   - `GUILD_ID` - Your Discord server ID
   - `UNBELIEVA_API_TOKEN` - Your API token (if using external API)
   - `CITATION_ROLE_ID` - Citation role ID (default: 1518010616290345000)

2. Or create a `.env` file in your container:
   ```
   DISCORD_TOKEN=your_token_here
   GUILD_ID=your_guild_id
   UNBELIEVA_API_TOKEN=your_api_token
   CITATION_ROLE_ID=1518010616290345000
   ```

### 6. Install Dependencies
In the WispByte Console, run:
```bash
pip install -r requirements.txt
```

### 7. Start the Bot
1. Click the Console tab in WispByte
2. Run: `python main.py`
3. Check for "✓ Bot logged in as..." message

## Troubleshooting

**Bot not starting?**
- Check console for errors
- Verify DISCORD_TOKEN is valid
- Ensure all dependencies installed: `pip install -r requirements.txt`

**Database not persisting?**
- The `data/` folder is created automatically
- Database file `citations.db` will persist if in a managed data directory
- Contact WispByte support if database resets on restart

**Commands not syncing?**
- Verify GUILD_ID is correct
- Wait 5-10 seconds after bot starts
- Check console logs for sync confirmation

## File Structure
```
.
├── main.py                 # Entry point (set as "Use on startup")
├── config.py              # Configuration loader
├── requirements.txt       # Python dependencies
├── Procfile              # Process file for hosting
├── .env.example          # Template for environment variables
├── database/
│   ├── __init__.py
│   └── db.py             # Database functions
├── cogs/
│   ├── __init__.py
│   ├── citation.py       # Citation command cog
│   └── players.py        # Player management cog
└── data/
    └── citations.db      # Database (auto-created)
```

## Notes
- The bot creates the `data/` directory automatically if missing
- Database is SQLite and stored locally
- All file paths are relative and should work cross-platform
