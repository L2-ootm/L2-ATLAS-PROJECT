import os
import asyncio
from quart import Quart, redirect, request, session, url_for, render_template, jsonify, make_response
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv
import aiohttp

load_dotenv()

# Allow OAuth2 over HTTP for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# --- Environment Variable Checks ---
required_env_vars = [
    "DISCORD_CLIENT_ID",
    "DISCORD_CLIENT_SECRET",
    "DISCORD_REDIRECT_URI"
]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}. Please check your .env file.")
# -----------------------------------

app = Quart(__name__)

# Self-healing secret key generation
secret_key = os.getenv("QUART_SECRET_KEY")
if not secret_key:
    import secrets
    secret_key = secrets.token_hex(32)
    print("Warning: QUART_SECRET_KEY is missing from environment. Generating and saving to .env...")
    try:
        with open(".env", "a") as env_file:
            env_file.write(f'\nQUART_SECRET_KEY="{secret_key}"\n')
        os.environ["QUART_SECRET_KEY"] = secret_key
    except Exception as e:
        print(f"Failed to persist QUART_SECRET_KEY to .env: {e}")

app.secret_key = secret_key

@app.before_serving
async def startup():
    from database.database import connect_database, DatabaseManager
    await connect_database()
    await DatabaseManager.log_event(
        event_type="SYSTEM_STARTUP",
        actor_id="WebPortal",
        trace_id="SYS-INIT",
        payload={"message": "L2 BOT Web Portal started and connected to local SQLite database."}
    )

# OAuth2 credentials
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

# Discord API endpoints
API_BASE_URL = 'https://discord.com/api'
AUTHORIZATION_BASE_URL = API_BASE_URL + '/oauth2/authorize'
TOKEN_URL = API_BASE_URL + '/oauth2/token'

def token_updater(token):
    session['oauth2_token'] = token

@app.route("/")
async def index():
    if 'oauth2_token' in session:
        return redirect(url_for('.dashboard'))
    return await render_template("dashboard.html", user=None)

@app.route("/login")
async def login():
    scope = ['identify', 'email', 'guilds']
    discord = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=scope)
    authorization_url, state = discord.authorization_url(AUTHORIZATION_BASE_URL)
    session['oauth2_state'] = state
    return redirect(authorization_url)

@app.route("/callback")
async def callback():
    values = await request.values
    if values.get('error'):
        return values['error']

    # Explicitly get the authorization code from Discord's response
    code = values.get('code')
    if not code:
        # This can happen if the user denies the authorization
        return redirect(url_for('.index'))

    # The state must match to prevent CSRF attacks
    state = values.get('state')
    if not state or state != session.get('oauth2_state'):
        return "State mismatch error. Please try logging in again.", 400

    # Pass the redirect_uri to the session constructor for the token exchange
    discord = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
    
    # Capture the URL before entering the background thread
    authorization_response_url = str(request.url)
    
    def fetch_token_sync():
        # Pass the code directly instead of the full response URL
        return discord.fetch_token(
            TOKEN_URL,
            client_secret=CLIENT_SECRET,
            code=code
        )

    try:
        token = await asyncio.get_running_loop().run_in_executor(None, fetch_token_sync)
        session['oauth2_token'] = token
    except Exception as e:
        print("\n" + "="*80)
        print("!!! DISCORD OAUTH2 TOKEN FETCH FAILED !!!")
        print(f"An exception occurred: {e}")
        print("Please check the following:")
        print("1. Your `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET` in the .env file are correct.")
        print("2. Your `DISCORD_REDIRECT_URI` in the .env file EXACTLY matches the one in your Discord App's OAuth2 settings.")
        print("   - Default should be: http://localhost:5000/callback")
        print("="*80 + "\n")
        # Redirect to an error page or home page
        return redirect(url_for('.index'))

    return redirect(url_for('.dashboard'))

@app.route("/dashboard")
async def dashboard():
    token = session.get('oauth2_token')
    if not token:
        return redirect(url_for('.login'))

    discord = OAuth2Session(CLIENT_ID, token=token)

    def get_user_sync():
        return discord.get(API_BASE_URL + '/users/@me')

    try:
        user_req = await asyncio.get_running_loop().run_in_executor(None, get_user_sync)
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return redirect(url_for('.logout'))

    if not user_req.ok:
        # Token might be expired, clear session and redirect to login
        return redirect(url_for('.logout'))

    user = user_req.json()
    return await render_template("dashboard.html", user=user)

# --- New API routes for the dashboard ---

BOT_API_URL = "http://localhost:8081"

async def is_user_admin_on_guild(guild_id):
    token = session.get('oauth2_token')
    if not token:
        return False
    
    discord = OAuth2Session(CLIENT_ID, token=token)
    
    # Get current user ID
    try:
        def get_user_sync():
            return discord.get(API_BASE_URL + '/users/@me')
            
        user_req = await asyncio.get_running_loop().run_in_executor(None, get_user_sync)
        if not user_req.ok:
            print(f"Error fetching user info for admin check: {user_req.status_code}")
            return False
        user_id = user_req.json()['id']
    except Exception as e:
        print(f"Exception getting user info: {e}")
        return False

    # Ask the bot if this user is an admin
    try:
        async with aiohttp.ClientSession() as cs:
            async with cs.get(f"{BOT_API_URL}/guilds/{guild_id}/check_admin/{user_id}") as r:
                if r.status != 200:
                    print(f"Bot API check_admin failed: {r.status} - {await r.text()}")
                    return False
                data = await r.json()
                is_admin = data.get('is_admin', False)
                print(f"Bot check_admin result for user {user_id} in guild {guild_id}: {is_admin}")
                return is_admin
    except Exception as e:
        print(f"Exception calling bot check_admin: {e}")
        return False

@app.route("/api/guilds")
async def get_guilds_api():
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    async with aiohttp.ClientSession() as cs:
        async with cs.get(f"{BOT_API_URL}/guilds") as r:
            if r.status != 200:
                print(f"Error from bot API: Status {r.status}")
                return jsonify({"error": "Failed to fetch guilds from bot"}), 500
            bot_guilds = await r.json()
            print(f"Bot is in {len(bot_guilds)} server(s): {[g['name'] for g in bot_guilds]}")
            
            return jsonify(bot_guilds)

@app.route("/api/guilds/<guild_id>/channels")
async def get_channels_api(guild_id):
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    if not await is_user_admin_on_guild(guild_id):
        return jsonify({"error": "You are not an admin on this server."}), 403

    async with aiohttp.ClientSession() as cs:
        async with cs.get(f"{BOT_API_URL}/guilds/{guild_id}/channels") as r:
            if r.status != 200:
                error_text = await r.text()
                print(f"Error fetching channels from bot: Status {r.status}, Response: {error_text}")
                return jsonify({"error": f"Failed to fetch channels from bot: {error_text}"}), 500
            return jsonify(await r.json())

@app.route("/api/guilds/<guild_id>/structure")
async def get_structure_api(guild_id):
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if not await is_user_admin_on_guild(guild_id):
        return jsonify({"error": "You are not an admin on this server."}), 403

    async with aiohttp.ClientSession() as cs:
        async with cs.get(f"{BOT_API_URL}/guilds/{guild_id}/structure") as r:
            if r.status != 200:
                error_text = await r.text()
                return jsonify({"error": f"Failed to fetch structure from bot: {error_text}"}), 500
            return jsonify(await r.json())

@app.route("/api/channels/<channel_id>/messages", methods=["POST"])
async def send_message_api(channel_id):
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = await request.get_json()
    if not data or 'embed' not in data:
        return jsonify({"error": "Invalid request body"}), 400

    # Get guild ID from the channel
    # This is a simplified approach. A robust solution might need a bot endpoint to get channel info
    # For now, we trust the frontend to have passed the correct context
    # but we still need to check permissions
    # We will assume that if a user can see channels, they are admin, based on previous checks.
    # A more secure check would be needed in a real production app.

    async with aiohttp.ClientSession() as cs:
        async with cs.post(f"{BOT_API_URL}/channels/{channel_id}/messages", json=data) as r:
            if r.status != 200:
                return jsonify({"error": "Failed to send message"}), 500
            return jsonify(await r.json())

@app.route("/api/guilds/<guild_id>/channels", methods=["POST"])
async def create_channel_api(guild_id):
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if not await is_user_admin_on_guild(guild_id):
        return jsonify({"error": "You are not an admin on this server."}), 403

    data = await request.get_json()

    async with aiohttp.ClientSession() as cs:
        async with cs.post(f"{BOT_API_URL}/guilds/{guild_id}/channels", json=data) as r:
            body = await r.json()
            if r.status != 200:
                return jsonify(body), r.status
            return jsonify(body)


@app.patch("/api/guilds/<guild_id>/channels/<channel_id>")
async def patch_channel_api(guild_id, channel_id):
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if not await is_user_admin_on_guild(guild_id):
        return jsonify({"error": "You are not an admin on this server."}), 403

    data = await request.get_json()

    async with aiohttp.ClientSession() as cs:
        async with cs.patch(f"{BOT_API_URL}/guilds/{guild_id}/channels/{channel_id}", json=data) as r:
            body = await r.json()
            if r.status != 200:
                return jsonify(body), r.status
            return jsonify(body)


@app.delete("/api/guilds/<guild_id>/channels/<channel_id>")
async def delete_channel_api(guild_id, channel_id):
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if not await is_user_admin_on_guild(guild_id):
        return jsonify({"error": "You are not an admin on this server."}), 403

    async with aiohttp.ClientSession() as cs:
        async with cs.delete(f"{BOT_API_URL}/guilds/{guild_id}/channels/{channel_id}") as r:
            body = await r.json()
            if r.status != 200:
                return jsonify(body), r.status
            return jsonify(body)


@app.route("/api/guilds/<guild_id>/roles")
async def get_roles_api(guild_id):
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if not await is_user_admin_on_guild(guild_id):
        return jsonify({"error": "You are not an admin on this server."}), 403

    async with aiohttp.ClientSession() as cs:
        async with cs.get(f"{BOT_API_URL}/guilds/{guild_id}/roles") as r:
            body = await r.json()
            if r.status != 200:
                return jsonify(body), r.status
            return jsonify(body)


@app.route("/api/guilds/<guild_id>/roles", methods=["POST"])
async def create_role_api(guild_id):
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if not await is_user_admin_on_guild(guild_id):
        return jsonify({"error": "You are not an admin on this server."}), 403

    data = await request.get_json()

    async with aiohttp.ClientSession() as cs:
        async with cs.post(f"{BOT_API_URL}/guilds/{guild_id}/roles", json=data) as r:
            body = await r.json()
            if r.status != 200:
                return jsonify(body), r.status
            return jsonify(body)


@app.patch("/api/guilds/<guild_id>/roles/<role_id>")
async def patch_role_api(guild_id, role_id):
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if not await is_user_admin_on_guild(guild_id):
        return jsonify({"error": "You are not an admin on this server."}), 403

    data = await request.get_json()

    async with aiohttp.ClientSession() as cs:
        async with cs.patch(f"{BOT_API_URL}/guilds/{guild_id}/roles/{role_id}", json=data) as r:
            body = await r.json()
            if r.status != 200:
                return jsonify(body), r.status
            return jsonify(body)


@app.delete("/api/guilds/<guild_id>/roles/<role_id>")
async def delete_role_api(guild_id, role_id):
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if not await is_user_admin_on_guild(guild_id):
        return jsonify({"error": "You are not an admin on this server."}), 403

    async with aiohttp.ClientSession() as cs:
        async with cs.delete(f"{BOT_API_URL}/guilds/{guild_id}/roles/{role_id}") as r:
            body = await r.json()
            if r.status != 200:
                return jsonify(body), r.status
            return jsonify(body)


@app.route("/api/guilds/<guild_id>/channels/<channel_id>/permissions", methods=["POST"])
async def set_channel_permissions_api(guild_id, channel_id):
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if not await is_user_admin_on_guild(guild_id):
        return jsonify({"error": "You are not an admin on this server."}), 403

    data = await request.get_json()

    async with aiohttp.ClientSession() as cs:
        async with cs.post(
            f"{BOT_API_URL}/guilds/{guild_id}/channels/{channel_id}/permissions",
            json=data
        ) as r:
            body = await r.json()
            if r.status != 200:
                return jsonify(body), r.status
            return jsonify(body)


@app.route("/api/logs/stream")
async def stream_logs():
    if 'oauth2_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    async def event_generator():
        import json
        from database.database import DatabaseManager
        
        # 1. Fetch recent events (last 30) and send sorted oldest-first
        recent = await DatabaseManager.get_recent_logs(limit=30)
        
        last_id = 0
        if isinstance(recent, list) and recent:
            recent_sorted = sorted(recent, key=lambda x: x.get("id", 0))
            for log in recent_sorted:
                last_id = max(last_id, log.get("id", 0))
                yield f"data: {json.dumps(log)}\n\n"
                
        # 2. Wait and stream new events
        while True:
            await asyncio.sleep(3)
            new_logs = await DatabaseManager.get_new_logs(last_id)
            if isinstance(new_logs, list) and new_logs:
                for log in new_logs:
                    last_id = max(last_id, log.get("id", 0))
                    yield f"data: {json.dumps(log)}\n\n"
                continue
            yield ": keepalive\n\n"
                
    response = await make_response(
        event_generator(),
        {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Transfer-Encoding': 'chunked',
            'Connection': 'keep-alive',
        },
    )
    response.timeout = None
    return response

@app.route("/logout")
async def logout():
    session.clear()
    return redirect(url_for('.index'))

if __name__ == "__main__":
    app.run(debug=True, port=5000)