"""
Copyright (c) 2017 s0hvaperuna
For licence see file LICENCE
"""

from discord.ext.commands import Bot
import time
from discord import state
import asyncio
import logging

log = logging.getLogger('discord')


# https://stackoverflow.com/a/34325723/6046713
def print_progress(iteration, total, prefix='', suffix='', decimals=1, length=100, fill='█'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end='\r')
    # Print New Line on Complete
    if iteration == total:
        print()


class ConnectionState(state.ConnectionState):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _delay_ready(self):
        launch = self._ready_state.launch
        while not launch.is_set():
            # this snippet of code is basically waiting 2 seconds
            # until the last GUILD_CREATE was sent
            launch.set()
            await asyncio.sleep(2, loop=self.loop)

        servers = self._ready_state.servers

        # get all the chunks
        chunks = []
        for server in servers:
            chunks.extend(self.chunks_needed(server))

        # we only want to request ~75 guilds per chunk request.
        splits = [servers[i:i + 75] for i in range(0, len(servers), 75)]
        for split in splits:
            await self.chunker(split)

        # wait for the chunks
        if chunks:
            self._progress = 0
            self._total = len(chunks)
            self._start = time.time()
            self._last = self._start
            print_progress(self._progress, self._total, 'Getting servers. Progress ')
            try:
                await asyncio.wait(chunks, timeout=len(chunks) * 30.0,
                                   loop=self.loop)
            except asyncio.TimeoutError:
                log.info('Somehow timed out waiting for chunks.')

        # remove the state
        try:
            del self._ready_state
        except AttributeError:
            pass  # already been deleted somehow

        # call GUILD_SYNC after we're done chunking
        if not self.is_bot:
            log.info('Requesting GUILD_SYNC for %s guilds' % len(self.servers))
            await self.syncer([s.id for s in self.servers])
        # dispatch the event
        self.dispatch('ready')

    def parse_ready(self, data):
        self._ready_state = state.ReadyState(launch=asyncio.Event(), servers=[])
        self.user = state.User(**data['user'])
        guilds = data.get('guilds')

        servers = self._ready_state.servers
        for guild in guilds:
            server = self._add_server_from_data(guild)
            if (not self.is_bot and not server.unavailable) or server.large:
                servers.append(server)

        for pm in data.get('private_channels'):
            self._add_private_channel(state.PrivateChannel(self.user, **pm))

        state.compat.create_task(self._delay_ready(), loop=self.loop)

    def chunks_needed(self, server):
        for chunk in range(state.math.ceil(server._member_count / 1000)):
            yield self.receive_chunk(server.id)

    def receive_chunk(self, guild_id):
        future = asyncio.Future(loop=self.loop)
        future.add_done_callback(self._chunk_done)
        listener = state.Listener(state.ListenerType.chunk, future, lambda s: s.id == guild_id)
        self._listeners.append(listener)
        return future

    def _chunk_done(self, future):
        self._progress += 1
        t = time.time() - self._start
        eta = self._progress/self._total
        if eta != 0:
            eta = 'ETA {0:.2f}s'.format(t/eta - t)
        else:
            eta = 'UNDEFINED'

        self._last = time.time()
        print_progress(self._progress, self._total,
                       'Getting servers. Progress ', suffix=eta)


class SelfBot(Bot):
    def __init__(self, prefix, **kwargs):
        super().__init__(prefix, **kwargs)
        self.user_id = None
        self.start_time = time.time()
        self.ready = False

        max_messages = kwargs.get('max_messages')
        if max_messages is None or max_messages < 100:
            max_messages = 5000

        self.connection = ConnectionState(self.dispatch,
                                          self.request_offline_members,
                                          self._syncer, max_messages,
                                          loop=self.loop)

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
