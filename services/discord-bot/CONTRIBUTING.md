# 🤝 Contributing

## Development Setup

### Prerequisites
- Python 3.11+
- Discord Developer Account
- Git

### Local Setup

1. Fork and clone the repository
2. Create virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and configure

---

## Code Style

### Python
- Follow PEP 8
- Use type hints where possible
- Docstrings for public functions
- Maximum line length: 120 characters

### Discord.py Cogs

```python
import discord
from discord.ext import commands
from discord import app_commands

class MyCog(commands.Cog):
    """Cog description."""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="command", description="What it does")
    async def my_command(self, interaction: discord.Interaction):
        """Command docstring."""
        await interaction.response.defer()
        # Logic here
        await interaction.followup.send("Response")

async def setup(bot):
    await bot.add_cog(MyCog(bot))
```

### Naming Conventions

| Type | Convention | Example |
|:-----|:-----------|:--------|
| Files | snake_case | `my_cog.py` |
| Classes | PascalCase | `MyCog` |
| Functions | snake_case | `my_function()` |
| Constants | UPPER_SNAKE | `API_BASE_URL` |

---

## Git Workflow

### Branches
- `main` - Production-ready code
- `develop` - Integration branch
- `feature/*` - New features
- `fix/*` - Bug fixes

### Commit Messages

Format: `type: description`

Types:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `refactor:` - Code refactoring
- `test:` - Tests
- `chore:` - Maintenance

Examples:
```
feat: add infrastructure deployment command
fix: forum channel creation error
docs: update API documentation
```

---

## Adding a New Cog

1. Create file in `bot/cogs/`
2. Implement cog class with `setup()` function
3. Bot auto-loads on restart
4. Test locally before committing

---

## Testing

### Manual Testing
1. Start bot: `python -m bot.main`
2. Test commands in Discord
3. Check console for errors

### Sync Commands
If commands don't appear:
```
!sync
```

---

## Documentation

- Update `README.md` for user-facing changes
- Update `docs/API.md` for API changes
- Update `CHANGELOG.md` for all changes

---

## Pull Request Process

1. Create branch from `develop`
2. Make changes
3. Test locally
4. Update documentation
5. Create PR with description
6. Wait for review

---

## Questions?

Open an issue or contact the L2 Systems team.
