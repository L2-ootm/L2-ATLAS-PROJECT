from aiohttp import web
import discord

async def _reason_from(request, default='Dashboard'):
    """Extract the ATLAS audit reason from a request body, tolerant of an empty
    or non-JSON body (DELETE requests may carry only {"reason": ...} or nothing)."""
    try:
        data = await request.json()
    except Exception:
        return default
    if isinstance(data, dict):
        return data.get('reason') or default
    return default


def _channel_type_str(ch):
    type_map = {
        discord.ChannelType.text: 'text',
        discord.ChannelType.voice: 'voice',
        discord.ChannelType.forum: 'forum',
        discord.ChannelType.stage_voice: 'stage',
        discord.ChannelType.news: 'announcement',
    }
    return type_map.get(ch.type, 'text')

async def health(request):
    """Readiness probe for the ATLAS sidecar lifecycle (atlas discord status).

    The aiohttp API binds before the Discord gateway is ready, so `ready`
    distinguishes "API up" from "bot connected with guilds cached".
    """
    bot = request.app['bot']
    ready = bool(getattr(bot, 'is_ready', lambda: False)())
    return web.json_response({
        'status': 'ok',
        'ready': ready,
        'guild_count': len(bot.guilds) if ready else 0,
    })

async def get_guilds(request):
    bot = request.app['bot']
    guilds = [{'id': str(g.id), 'name': g.name} for g in bot.guilds]
    return web.json_response(guilds)

async def get_channels(request):
    bot = request.app['bot']
    guild_id = request.match_info['guild_id']
    try:
        guild = bot.get_guild(int(guild_id))
    except ValueError:
        return web.json_response({'error': 'Invalid guild ID'}, status=400)

    if not guild:
        print(f"API Error: Guild {guild_id} not found")
        return web.json_response({'error': 'Guild not found'}, status=404)
    
    bot_member = guild.get_member(bot.user.id)
    if not bot_member:
        print(f"API Error: Bot is not a member of guild {guild.name} ({guild.id})")
        return web.json_response({'error': 'Bot is not a member of this guild?'}, status=500)

    categorized_channels = {}
    for channel in guild.text_channels:
        # Check if the bot has permission to send messages
        permissions = channel.permissions_for(bot_member)
        if permissions.send_messages and permissions.view_channel:
            category_name = channel.category.name if channel.category else "Uncategorized"
            if category_name not in categorized_channels:
                categorized_channels[category_name] = []
            
            categorized_channels[category_name].append({'id': str(channel.id), 'name': channel.name})

    # Convert to the list format the frontend will expect
    response_data = [
        {'category_name': name, 'channels': channels}
        for name, channels in categorized_channels.items()
    ]
    
    return web.json_response(response_data)

async def get_structure(request):
    bot = request.app['bot']
    guild_id = request.match_info['guild_id']
    try:
        guild = bot.get_guild(int(guild_id))
    except ValueError:
        return web.json_response({'error': 'Invalid guild ID'}, status=400)

    if not guild:
        return web.json_response({'error': 'Guild not found'}, status=404)

    def build_channel(ch, category_name=None):
        overwrites = []
        for target, ow in ch.overwrites.items():
            if not isinstance(target, discord.Role):
                continue
            allow_perms, deny_perms = ow.pair()
            overwrites.append({
                'role_id': str(target.id),
                'role_name': target.name,
                'allow': allow_perms.value,
                'deny': deny_perms.value,
            })
        return {
            'id': str(ch.id),
            'name': ch.name,
            'type': _channel_type_str(ch),
            'position': ch.position,
            'topic': getattr(ch, 'topic', None),
            'category_name': category_name,
            'permission_overwrites': overwrites,
        }

    categories = []
    for cat in sorted(guild.categories, key=lambda c: c.position):
        categories.append({
            'id': str(cat.id),
            'name': cat.name,
            'position': cat.position,
            'channels': [build_channel(ch, category_name=cat.name) for ch in cat.channels],
        })

    uncategorized = [
        build_channel(ch)
        for ch in guild.channels
        if ch.category is None and not isinstance(ch, discord.CategoryChannel)
    ]

    roles = []
    for r in sorted(guild.roles, key=lambda r: r.position, reverse=True):
        roles.append({
            'id': str(r.id),
            'name': r.name,
            'color': f'#{r.color.value:06x}',
            'position': r.position,
            'permissions': r.permissions.value,
            'mentionable': r.mentionable,
            'hoist': r.hoist,
            'managed': r.managed,
        })

    return web.json_response({
        'guild': {
            'id': str(guild.id),
            'name': guild.name,
            'member_count': guild.member_count,
        },
        'categories': categories,
        'uncategorized': uncategorized,
        'roles': roles,
    })

async def send_message(request):
    bot = request.app['bot']
    channel_id = request.match_info['channel_id']
    try:
        channel = bot.get_channel(int(channel_id))
    except ValueError:
        return web.json_response({'error': 'Invalid channel ID'}, status=400)

    if not channel:
        return web.json_response({'error': 'Channel not found'}, status=404)
        
    data = await request.json()
    embed_data = data.get('embed')
    
    if not embed_data:
        return web.json_response({'error': 'Embed data is required'}, status=400)
        
    try:
        embed = discord.Embed.from_dict(embed_data)
        await channel.send(embed=embed)
        return web.json_response({'success': True})
    except Exception as e:
        return web.json_response({'error': f'Failed to send message: {e}'}, status=500)

async def check_admin(request):
    bot = request.app['bot']
    guild_id = request.match_info['guild_id']
    user_id = request.match_info['user_id']
    
    try:
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({'error': 'Guild not found'}, status=404)
            
        member = guild.get_member(int(user_id))
        if not member:
            # Try to fetch if not in cache
            try:
                member = await guild.fetch_member(int(user_id))
            except discord.NotFound:
                return web.json_response({'error': 'Member not found'}, status=404)
        
        is_admin = False
        # Check owner
        if guild.owner_id == int(user_id):
            is_admin = True
        # Check permissions
        elif member.guild_permissions.administrator or member.guild_permissions.manage_guild:
            is_admin = True
            
        return web.json_response({'is_admin': is_admin})
    except ValueError:
        return web.json_response({'error': 'Invalid ID format'}, status=400)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def create_channel(request):
    bot = request.app['bot']
    guild_id = request.match_info['guild_id']
    try:
        guild = bot.get_guild(int(guild_id))
    except ValueError:
        return web.json_response({'error': 'Invalid guild ID'}, status=400)

    if not guild:
        return web.json_response({'error': 'Guild not found'}, status=404)

    data = await request.json()
    name = (data.get('name') or '').strip()
    if not name:
        return web.json_response({'error': 'Channel name is required'}, status=400)

    channel_type = data.get('type', 'text')
    category_id = data.get('category_id')
    topic = data.get('topic') or ''
    reason = data.get('reason') or 'Dashboard'

    cat = None
    if category_id:
        try:
            cat = guild.get_channel(int(category_id))
        except (TypeError, ValueError):
            return web.json_response({'error': 'Invalid category_id'}, status=400)
        if not isinstance(cat, discord.CategoryChannel):
            return web.json_response({'error': 'category_id is not a category'}, status=400)

    try:
        if channel_type == 'text':
            kwargs = {'category': cat, 'reason': reason}
            if topic:
                kwargs['topic'] = topic
            ch = await guild.create_text_channel(name, **kwargs)
        elif channel_type == 'voice':
            ch = await guild.create_voice_channel(name, category=cat, reason=reason)
        elif channel_type == 'forum':
            kwargs = {'category': cat, 'reason': reason}
            if topic:
                kwargs['topic'] = topic
            ch = await guild.create_forum(name, **kwargs)
        elif channel_type == 'category':
            ch = await guild.create_category_channel(name, reason=reason)
        else:
            return web.json_response({'error': f'Unknown channel type: {channel_type}'}, status=400)
        return web.json_response({'id': str(ch.id), 'name': ch.name})
    except discord.Forbidden:
        return web.json_response({'error': 'Forbidden'}, status=403)
    except discord.NotFound:
        return web.json_response({'error': 'Not found'}, status=404)
    except discord.HTTPException as e:
        return web.json_response({'error': str(e)}, status=500)
    except (TypeError, ValueError) as e:
        return web.json_response({'error': str(e)}, status=400)


async def edit_channel(request):
    bot = request.app['bot']
    guild_id = request.match_info['guild_id']
    channel_id = request.match_info['channel_id']
    try:
        guild = bot.get_guild(int(guild_id))
    except ValueError:
        return web.json_response({'error': 'Invalid guild ID'}, status=400)

    if not guild:
        return web.json_response({'error': 'Guild not found'}, status=404)

    try:
        channel = guild.get_channel(int(channel_id))
    except ValueError:
        return web.json_response({'error': 'Invalid channel ID'}, status=400)

    if not channel:
        return web.json_response({'error': 'Channel not found'}, status=404)

    data = await request.json()
    edit_kwargs = {}

    if data.get('name'):
        edit_kwargs['name'] = data['name'].strip()

    if 'category_id' in data:
        cat_id = data['category_id']
        if cat_id:
            try:
                cat = guild.get_channel(int(cat_id))
            except (TypeError, ValueError):
                return web.json_response({'error': 'Invalid category_id'}, status=400)
            if not isinstance(cat, discord.CategoryChannel):
                return web.json_response({'error': 'category_id is not a category'}, status=400)
            edit_kwargs['category'] = cat
        else:
            edit_kwargs['category'] = None

    if data.get('topic') is not None and isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
        edit_kwargs['topic'] = data['topic']

    try:
        await channel.edit(**edit_kwargs, reason=(data.get('reason') or 'Dashboard'))
        return web.json_response({'success': True})
    except discord.Forbidden:
        return web.json_response({'error': 'Forbidden'}, status=403)
    except discord.NotFound:
        return web.json_response({'error': 'Not found'}, status=404)
    except discord.HTTPException as e:
        return web.json_response({'error': str(e)}, status=500)
    except (TypeError, ValueError) as e:
        return web.json_response({'error': str(e)}, status=400)


async def delete_channel(request):
    bot = request.app['bot']
    guild_id = request.match_info['guild_id']
    channel_id = request.match_info['channel_id']
    try:
        guild = bot.get_guild(int(guild_id))
    except ValueError:
        return web.json_response({'error': 'Invalid guild ID'}, status=400)

    if not guild:
        return web.json_response({'error': 'Guild not found'}, status=404)

    try:
        channel = guild.get_channel(int(channel_id))
    except ValueError:
        return web.json_response({'error': 'Invalid channel ID'}, status=400)

    if not channel:
        return web.json_response({'error': 'Channel not found'}, status=404)

    try:
        await channel.delete(reason=await _reason_from(request))
        return web.json_response({'success': True})
    except discord.Forbidden:
        return web.json_response({'error': 'Forbidden'}, status=403)
    except discord.NotFound:
        return web.json_response({'error': 'Not found'}, status=404)
    except discord.HTTPException as e:
        return web.json_response({'error': str(e)}, status=500)
    except (TypeError, ValueError) as e:
        return web.json_response({'error': str(e)}, status=400)


def build_permissions(perm_dict):
    """Build a discord.Permissions object from a dict of {flag: bool}.

    Uses Permissions.none() as base (NOT .default()) per discord.py 2.x.
    Unknown flag names and non-bool values are silently skipped (T-6-02-FLAG).
    """
    p = discord.Permissions.none()
    for flag, value in perm_dict.items():
        if hasattr(p, flag) and isinstance(value, bool):
            setattr(p, flag, value)
    return p


async def get_roles(request):
    bot = request.app['bot']
    guild_id = request.match_info['guild_id']
    try:
        guild = bot.get_guild(int(guild_id))
    except ValueError:
        return web.json_response({'error': 'Invalid guild ID'}, status=400)

    if not guild:
        return web.json_response({'error': 'Guild not found'}, status=404)

    roles = []
    for r in sorted(guild.roles, key=lambda r: r.position, reverse=True):
        if r.is_default():
            continue
        roles.append({
            'id': str(r.id),
            'name': r.name,
            'color': f'#{r.color.value:06x}',
            'position': r.position,
            'permissions': r.permissions.value,
            'mentionable': r.mentionable,
            'hoist': r.hoist,
            'managed': r.managed,
        })
    return web.json_response(roles)


async def create_role(request):
    bot = request.app['bot']
    guild_id = request.match_info['guild_id']
    try:
        guild = bot.get_guild(int(guild_id))
    except ValueError:
        return web.json_response({'error': 'Invalid guild ID'}, status=400)

    if not guild:
        return web.json_response({'error': 'Guild not found'}, status=404)

    try:
        data = await request.json()
        name = (data.get('name') or '').strip()
        if not name:
            return web.json_response({'error': 'Role name is required'}, status=400)

        color_hex = data.get('color_hex') or ''
        hoist = data.get('hoist', False)
        permissions_dict = data.get('permissions') or {}

        color = discord.Color(int(color_hex.lstrip('#'), 16)) if color_hex else discord.Color.default()
        role = await guild.create_role(
            name=name,
            color=color,
            hoist=bool(hoist),
            permissions=build_permissions(permissions_dict),
            reason=(data.get('reason') or 'Dashboard'),
        )
        return web.json_response({'id': str(role.id), 'name': role.name})
    except discord.Forbidden:
        return web.json_response({'error': 'Forbidden'}, status=403)
    except discord.NotFound:
        return web.json_response({'error': 'Not found'}, status=404)
    except discord.HTTPException as e:
        return web.json_response({'error': str(e)}, status=500)
    except (TypeError, ValueError) as e:
        return web.json_response({'error': str(e)}, status=400)


async def edit_role(request):
    bot = request.app['bot']
    guild_id = request.match_info['guild_id']
    role_id = request.match_info['role_id']
    try:
        guild = bot.get_guild(int(guild_id))
    except ValueError:
        return web.json_response({'error': 'Invalid guild ID'}, status=400)

    if not guild:
        return web.json_response({'error': 'Guild not found'}, status=404)

    try:
        role = guild.get_role(int(role_id))
    except ValueError:
        return web.json_response({'error': 'Invalid role ID'}, status=400)

    if not role:
        return web.json_response({'error': 'Role not found'}, status=404)

    try:
        data = await request.json()
        edit_kwargs = {}

        if data.get('name'):
            edit_kwargs['name'] = data['name'].strip()

        color_hex = data.get('color_hex')
        if color_hex is not None:
            edit_kwargs['color'] = discord.Color(int(color_hex.lstrip('#'), 16)) if color_hex else discord.Color.default()

        if 'hoist' in data:
            edit_kwargs['hoist'] = bool(data['hoist'])

        if 'permissions' in data and isinstance(data['permissions'], dict):
            edit_kwargs['permissions'] = build_permissions(data['permissions'])

        await role.edit(**edit_kwargs, reason=(data.get('reason') or 'Dashboard'))
        return web.json_response({'success': True})
    except discord.Forbidden:
        return web.json_response({'error': 'Forbidden'}, status=403)
    except discord.NotFound:
        return web.json_response({'error': 'Not found'}, status=404)
    except discord.HTTPException as e:
        return web.json_response({'error': str(e)}, status=500)
    except (TypeError, ValueError) as e:
        return web.json_response({'error': str(e)}, status=400)


async def delete_role(request):
    bot = request.app['bot']
    guild_id = request.match_info['guild_id']
    role_id = request.match_info['role_id']
    try:
        guild = bot.get_guild(int(guild_id))
    except ValueError:
        return web.json_response({'error': 'Invalid guild ID'}, status=400)

    if not guild:
        return web.json_response({'error': 'Guild not found'}, status=404)

    try:
        role = guild.get_role(int(role_id))
    except ValueError:
        return web.json_response({'error': 'Invalid role ID'}, status=400)

    if not role:
        return web.json_response({'error': 'Role not found'}, status=404)

    try:
        await role.delete(reason=await _reason_from(request))
        return web.json_response({'success': True})
    except discord.Forbidden:
        return web.json_response({'error': 'Forbidden'}, status=403)
    except discord.NotFound:
        return web.json_response({'error': 'Not found'}, status=404)
    except discord.HTTPException as e:
        return web.json_response({'error': str(e)}, status=500)
    except (TypeError, ValueError) as e:
        return web.json_response({'error': str(e)}, status=400)


async def set_channel_permissions(request):
    bot = request.app['bot']
    guild_id = request.match_info['guild_id']
    channel_id = request.match_info['channel_id']
    try:
        guild = bot.get_guild(int(guild_id))
    except ValueError:
        return web.json_response({'error': 'Invalid guild ID'}, status=400)

    if not guild:
        return web.json_response({'error': 'Guild not found'}, status=404)

    try:
        channel = guild.get_channel(int(channel_id))
    except ValueError:
        return web.json_response({'error': 'Invalid channel ID'}, status=400)

    if not channel:
        return web.json_response({'error': 'Channel not found'}, status=404)

    try:
        data = await request.json()
        role_id = data.get('role_id')
        allow_dict = data.get('allow', {})
        deny_dict = data.get('deny', {})

        if role_id is None:
            return web.json_response({'error': 'role_id is required'}, status=400)

        role = guild.get_role(int(role_id))
        if not role:
            return web.json_response({'error': 'Role not found'}, status=404)

        # D-19: Start from EXISTING overwrite — do NOT construct a fresh PermissionOverwrite
        overwrite = channel.overwrites_for(role)
        for perm in allow_dict:
            if hasattr(overwrite, perm):
                setattr(overwrite, perm, True)
        for perm in deny_dict:
            if hasattr(overwrite, perm):
                setattr(overwrite, perm, False)

        await channel.set_permissions(role, overwrite=overwrite, reason=(data.get('reason') or 'Dashboard'))
        return web.json_response({'success': True})
    except discord.Forbidden:
        return web.json_response({'error': 'Forbidden'}, status=403)
    except discord.NotFound:
        return web.json_response({'error': 'Not found'}, status=404)
    except discord.HTTPException as e:
        return web.json_response({'error': str(e)}, status=500)
    except (TypeError, ValueError) as e:
        return web.json_response({'error': str(e)}, status=400)


def setup_bot_api(bot_instance):
    app = web.Application()
    app['bot'] = bot_instance
    app.router.add_get('/health', health)
    app.router.add_get('/guilds', get_guilds)
    app.router.add_get('/guilds/{guild_id}/channels', get_channels)
    app.router.add_get('/guilds/{guild_id}/structure', get_structure)
    app.router.add_get('/guilds/{guild_id}/check_admin/{user_id}', check_admin)
    app.router.add_post('/channels/{channel_id}/messages', send_message)
    app.router.add_post('/guilds/{guild_id}/channels', create_channel)
    app.router.add_patch('/guilds/{guild_id}/channels/{channel_id}', edit_channel)
    app.router.add_delete('/guilds/{guild_id}/channels/{channel_id}', delete_channel)
    app.router.add_get('/guilds/{guild_id}/roles', get_roles)
    app.router.add_post('/guilds/{guild_id}/roles', create_role)
    app.router.add_patch('/guilds/{guild_id}/roles/{role_id}', edit_role)
    app.router.add_delete('/guilds/{guild_id}/roles/{role_id}', delete_role)
    app.router.add_post('/guilds/{guild_id}/channels/{channel_id}/permissions', set_channel_permissions)
    return app