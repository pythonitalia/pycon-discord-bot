import asyncio
import datetime
import httpx
import discord
import os
from dotenv import load_dotenv
from discord import app_commands
from zoneinfo import ZoneInfo
import redis

EuropeRomeTz = ZoneInfo("Europe/Rome")

load_dotenv()

redis_conn = redis.Redis.from_url(os.getenv("REDIS_URL"))

BOT_TOKEN = os.getenv("BOT_TOKEN")
DISCORD_GUILD = os.getenv("DISCORD_GUILD")

# Channels
RECRUITING_CHANNEL_ID = 1108821274395934823
LUNCH_CHANNEL_ID = 1108824701175857224

# Roles
LUNCH_ROLE_ID = 1109064288418676846
LOOKING_FOR_A_JOB_ROLE_ID = 1109813880105996328
RECRUITING_ROLE_ID = 1109062803068829769

# Setup
intents = discord.Intents.default()
intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@tree.command(name="lunch", description = "Post lunch text", guild=discord.Object(id=DISCORD_GUILD))
async def lunch_command(interaction):
    if not interaction.permissions.administrator:
        await interaction.response.send_message('Only admins can use this.', ephemeral=True)
        return

    await interaction.response.send_message('Done', ephemeral=True, delete_after=1)
    channel = client.get_channel(LUNCH_CHANNEL_ID)
    await channel.send(f'''Hello <@&{LUNCH_ROLE_ID}>!

You can now pick up a takeaway box or a ticket to the Osteria from the registration desk!
Check today's menu at: https://pycon.it/lunch
''')


def get_conference_schedule():
    request = httpx.post('https://beri.python.it/graphql', json={
        'query': '''query {
            conference(code: "pycon2023") {
        id
        isRunning
        currentDay {
            day
            runningEvents {
                id
                title
                start
                end
                rooms {
                    id
                    name
                }
            }
        }
    }
}'''
    })
    response = request.json()
    return response


async def tick():
    current_time = datetime.datetime.now(EuropeRomeTz)
    if current_time.day not in (25, 26, 27, 28):
        print('Not doing anything: conference is not running.')
        return

    print('Checking if we need to notify about events')
    conference_schedule = get_conference_schedule()
    current_day = conference_schedule['data']['conference']['currentDay']

    if not current_day:
        return

    await check_for_recruiting_event_notification(current_day)


async def check_for_recruiting_event_notification(current_day):
    running_events = current_day['runningEvents']
    recruiting_event = next(
        (event for event in running_events if any(room['name'].lower() == 'recruiting' for room in event['rooms'])),
        None
    )

    if not recruiting_event:
        return

    event_id = recruiting_event['id']
    end_time = datetime.datetime.strptime(recruiting_event['end'], '%Y-%m-%dT%H:%M:%S')

    if redis_conn.sismember('notified_events', event_id):
        # we already notified this event
        return
    redis_conn.sadd('notified_events', event_id)

    sponsor_name = recruiting_event['title'].replace('Recruiting - ', '').strip()
    recruiting_channel = client.get_channel(RECRUITING_CHANNEL_ID)
    formatted_end = end_time.strftime('%H:%M')
    await recruiting_channel.send(f'''Hello <@&{RECRUITING_ROLE_ID}> and <@&{LOOKING_FOR_A_JOB_ROLE_ID}>!

If you head to the Recruiting Room now you can find **{sponsor_name}** until **{formatted_end}**!

Learn what are up to, any open positions they might have and how you can join their team!
''')


@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=DISCORD_GUILD))

    for guild in client.guilds:
        if guild.name == DISCORD_GUILD:
            break

    print(
        f'{client.user} is connected to the following guild:\n'
        f'{guild.name}(id: {guild.id})'
    )

    while True:
        await tick()
        await asyncio.sleep(5 * 60)

client.run(BOT_TOKEN)
