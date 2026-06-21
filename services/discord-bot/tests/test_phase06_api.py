"""
Phase 6 API unit tests.

Wave 0: All tests are marked xfail stubs. Slice plans (06-01 through 06-03)
replace these stub bodies with real assertions and remove the xfail marker.
"""
import pytest
import discord
from unittest.mock import MagicMock, AsyncMock


async def test_channel_create(api_client, mock_guild, mock_channel):
    """POST /guilds/{id}/channels validates guild exists before mutation."""
    guild_id = mock_guild.id

    # Happy path: create a text channel
    resp = await api_client.post(
        f'/guilds/{guild_id}/channels',
        json={'name': 'general', 'type': 'text'}
    )
    assert resp.status == 200
    body = await resp.json()
    assert 'id' in body
    assert 'name' in body

    # Verify create_text_channel was called with category=None
    mock_guild.create_text_channel.assert_called_once()
    call_kwargs = mock_guild.create_text_channel.call_args
    assert call_kwargs.kwargs.get('category') is None

    # Unknown guild -> 404
    resp2 = await api_client.post(
        '/guilds/999999999999999999/channels',
        json={'name': 'general', 'type': 'text'}
    )
    assert resp2.status == 404


async def test_channel_edit_notfound(api_client, mock_guild):
    """PATCH /guilds/{id}/channels/{cid} returns 404 for unknown channel."""
    guild_id = mock_guild.id

    # Make get_channel return None for channel 999
    mock_guild.get_channel.return_value = None

    resp = await api_client.patch(
        f'/guilds/{guild_id}/channels/999',
        json={'name': 'new-name'}
    )
    assert resp.status == 404


async def test_channel_delete_forbidden(api_client, mock_guild, mock_channel):
    """DELETE /guilds/{id}/channels/{cid} returns 403 on Forbidden."""
    guild_id = mock_guild.id
    channel_id = mock_channel.id

    # Make delete raise discord.Forbidden
    mock_channel.delete.side_effect = discord.Forbidden(
        MagicMock(status=403, reason='Missing Permissions'), 'Missing Permissions'
    )
    mock_guild.get_channel.return_value = mock_channel

    resp = await api_client.delete(
        f'/guilds/{guild_id}/channels/{channel_id}'
    )
    assert resp.status == 403


async def test_role_create_permissions(api_client, mock_guild, mock_role):
    """POST /guilds/{id}/roles uses discord.Permissions.none() not .default()."""
    import bot.api as api_module
    import inspect

    guild_id = mock_guild.id

    # Verify the source uses Permissions.none() and not Permissions.default()
    src = inspect.getsource(api_module.build_permissions)
    assert 'Permissions.none()' in src, "build_permissions must use Permissions.none()"
    assert 'Permissions.default()' not in src, "build_permissions must NOT use Permissions.default()"

    # Happy path: create a role with specific permissions
    resp = await api_client.post(
        f'/guilds/{guild_id}/roles',
        json={'name': 'Mod', 'permissions': {'manage_messages': True, 'ban_members': True}}
    )
    assert resp.status == 200
    body = await resp.json()
    assert 'id' in body
    assert 'name' in body

    # Verify create_role was called
    mock_guild.create_role.assert_called_once()
    call_kwargs = mock_guild.create_role.call_args.kwargs
    assert call_kwargs.get('name') == 'Mod'
    assert call_kwargs.get('reason') == 'Dashboard'

    # Verify permissions were built correctly using Permissions.none()
    perms = call_kwargs.get('permissions')
    assert perms is not None
    assert isinstance(perms, discord.Permissions)
    assert perms.manage_messages is True
    assert perms.ban_members is True
    # administrator must be False (not inherited from .default())
    assert perms.administrator is False

    # Unknown guild -> 404
    resp2 = await api_client.post(
        '/guilds/999999999999999999/roles',
        json={'name': 'Test'}
    )
    assert resp2.status == 404


async def test_role_list_managed_field(api_client, mock_guild, mock_role):
    """GET /guilds/{id}/roles includes managed field and excludes @everyone."""
    guild_id = mock_guild.id

    # Set up roles list: one regular role + one @everyone (is_default=True)
    everyone_role = MagicMock(spec=discord.Role)
    everyone_role.id = 333333333333333333  # same as guild id (Discord convention)
    everyone_role.name = "@everyone"
    everyone_role.color = MagicMock()
    everyone_role.color.value = 0
    everyone_role.position = 0
    everyone_role.permissions = MagicMock()
    everyone_role.permissions.value = 0
    everyone_role.mentionable = False
    everyone_role.hoist = False
    everyone_role.managed = False
    everyone_role.is_default = MagicMock(return_value=True)

    mock_role.color = MagicMock()
    mock_role.color.value = 0xFF0000
    mock_role.position = 1
    mock_role.permissions = MagicMock()
    mock_role.permissions.value = 8
    mock_role.mentionable = False
    mock_role.hoist = True
    mock_role.managed = False
    mock_role.is_default = MagicMock(return_value=False)

    mock_guild.roles = [everyone_role, mock_role]

    resp = await api_client.get(f'/guilds/{guild_id}/roles')
    assert resp.status == 200
    roles = await resp.json()

    # Must be a list
    assert isinstance(roles, list)

    # @everyone must be excluded
    names = [r['name'] for r in roles]
    assert '@everyone' not in names

    # Every role dict must contain 'managed' key
    for role_dict in roles:
        assert 'managed' in role_dict, f"Role dict missing 'managed' key: {role_dict}"

    # The mock_role should be present
    assert any(r['name'] == mock_role.name for r in roles)


async def test_permission_override_preserves_existing(api_client, mock_guild, mock_channel, mock_role):
    """POST /guilds/{id}/channels/{cid}/permissions fetches existing overwrite before updating."""
    guild_id = mock_guild.id
    channel_id = mock_channel.id

    # Seed the mock_channel to return a PermissionOverwrite with manage_messages=True (pre-existing)
    existing_overwrite = discord.PermissionOverwrite(manage_messages=True)
    mock_channel.overwrites_for.return_value = existing_overwrite
    mock_guild.get_channel.return_value = mock_channel

    # POST with allow={view_channel} and deny={send_messages}; manage_messages NOT in request
    resp = await api_client.post(
        f'/guilds/{guild_id}/channels/{channel_id}/permissions',
        json={
            'role_id': str(mock_role.id),
            'allow': {'view_channel': True},
            'deny': {'send_messages': True},
        }
    )
    assert resp.status == 200
    body = await resp.json()
    assert body.get('success') is True

    # Verify set_permissions was awaited once
    mock_channel.set_permissions.assert_awaited_once()
    call_kwargs = mock_channel.set_permissions.call_args

    # The overwrite passed to set_permissions must preserve existing + apply new flags
    passed_overwrite = call_kwargs.kwargs.get('overwrite') or call_kwargs.args[1]
    assert passed_overwrite.view_channel is True,      "allow flag must be set True"
    assert passed_overwrite.send_messages is False,    "deny flag must be set False"
    assert passed_overwrite.manage_messages is True,   "pre-existing override must be preserved"
    assert passed_overwrite.mention_everyone is None,  "absent flag must remain None (inherit)"
