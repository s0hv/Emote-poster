"""
Copyright (c) 2017 s0hvaperuna
For licence see file LICENCE
"""

from discord.ext.commands import Bot
import time


class SelfBot(Bot):
    def __init__(self, prefix, **kwargs):
        super().__init__(prefix, **kwargs)
        self.user_id = None
        self.start_time = time.time()
        self.ready = False

    async def on_ready(self):
        print('[INFO] Logged in as {}'.format(self.user))
        print('Startup took %s seconds' % (int((time.time() - self.start_time))))
        self.user_id = self.user.id
        self.ready = True
        self.load_extension('commands')

    async def on_message(self, message):
        if not self.ready:
            return

        if self.user_id is None or message.author.id != self.user_id:
            return

        if message.content.startswith(self.command_prefix):
            await self.process_commands(message)


if __name__ == '__main__':
    import json
    import os
    if not os.path.exists('config.json'):
        print('Copy example_config.json to config.json and put your token there')
        exit()

    with open('config.json') as f:
        json = json.load(f)
        token = json.get('token')
        prefix = json.get('prefix', '=')

    bot = SelfBot(prefix, self_bot=True)
    bot.run(token, bot=False)
