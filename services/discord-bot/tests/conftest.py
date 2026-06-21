"""
Shared pytest fixtures for Phase 6 API tests.

Uses aiohttp's pytest plugin to build a TestClient from setup_bot_api().
"""
import pytest
import discord
from unittest.mock import MagicMock, AsyncMock

pytest_plugins = ('aiohttp.pytest_plugin',)


@pytest.fixture
def mock_channel():
    ch = MagicMock(spec=discord.TextChannel)
    ch.id = 111111111111111111
    ch.name = "test-channel"
    ch.edit = AsyncMock()
    ch.delete = AsyncMock()
    ch.set_permissions = AsyncMock()
    ch.overwrites_for = MagicMock(return_value=discord.PermissionOverwrite())
    return ch


@pytest.fixture
def mock_role():
    role = MagicMock(spec=discord.Role)
    role.id = 222222222222222222
    role.name = "test-role"
    role.managed = False
    role.permissions = MagicMock()
    role.permissions.value = 0
    role.edit = AsyncMock()
    role.delete = AsyncMock()
    return role


@pytest.fixture
def mock_guild(mock_channel, mock_role):
    guild = MagicMock(spec=discord.Guild)
    guild.id = 333333333333333333
    guild.name = "Test Guild"
    guild.create_text_channel = AsyncMock(return_value=mock_channel)
    guild.create_voice_channel = AsyncMock(return_value=mock_channel)
    guild.create_forum = AsyncMock(return_value=mock_channel)
    guild.create_category_channel = AsyncMock(return_value=mock_channel)
    guild.create_role = AsyncMock(return_value=mock_role)
    guild.get_channel = MagicMock(return_value=mock_channel)
    guild.get_role = MagicMock(return_value=mock_role)
    return guild


@pytest.fixture
def mock_bot(mock_guild):
    bot = MagicMock()
    bot.get_guild = MagicMock(side_effect=lambda gid: mock_guild if gid == mock_guild.id else None)
    bot.get_channel = MagicMock(return_value=None)
    return bot


@pytest.fixture
async def api_client(aiohttp_client, mock_bot):
    """aiohttp TestClient wrapping setup_bot_api(mock_bot)."""
    import sys
    import os
    # Ensure the project root is on the path so bot.api can be imported
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from bot.api import setup_bot_api
    app = setup_bot_api(mock_bot)
    client = await aiohttp_client(app)
    return client
