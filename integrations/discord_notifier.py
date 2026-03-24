import asyncio

BOT_INSTANCE = None


def set_bot_instance(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot


async def _send_message(channel_id: int, content: str):
    if BOT_INSTANCE is None:
        return

    channel = BOT_INSTANCE.get_channel(channel_id)
    if channel is None:
        return

    if len(content) <= 1900:
        await channel.send(content)
        return

    chunks = []
    text = content
    while text:
        chunks.append(text[:1900])
        text = text[1900:]

    for chunk in chunks:
        await channel.send(chunk)


def send_message(channel_id: int, content: str):
    if BOT_INSTANCE is None:
        return

    try:
        loop = BOT_INSTANCE.loop
        asyncio.run_coroutine_threadsafe(_send_message(channel_id, content), loop)
    except Exception as e:
        print(f"[DiscordNotifier] Failed to send message: {e}")