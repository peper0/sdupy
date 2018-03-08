import asyncio
from collections import deque


class Tee:
    def __init__(self, gen):
        self.gen = gen.__aiter__()
        self.outputs = 0
        self.queue = deque()
        self.queue_index_offset = 0
        self.finished = False
        self.fetch_idle = asyncio.Event()
        self.fetch_idle.set()

    def ref(self):
        self.outputs += 1

    def unref(self, next_index):
        self.outputs -= 1
        assert self.outputs >= 0
        for i in range(next_index - self.queue_index_offset, len(self.queue)):
            self.queue[i][1] -= 1

    def request_out(self):
        return TeeOut(self)

    async def pull_item(self, index):
        assert index >= self.queue_index_offset, "requested too old item; it's a bug"
        assert index <= self.next_index(), "non-sequential getter?"
        if index == self.next_index():
            if not await self._fetch_next():
                raise StopAsyncIteration

        assert index < self.next_index(), "fetch failed?"

        index_in_queue = index - self.queue_index_offset
        self.queue[index_in_queue][1] -= 1
        print("returning")
        return self.queue[index_in_queue][0]

    async def _fetch_next(self):
        if not self.finished:
            print("fetching")
            if self.fetch_idle.is_set():
                print("really fetching")
                self.fetch_idle.clear()
                try:
                    self.queue.append([await self.gen.__anext__(), self.outputs])
                    print("fetched")
                except StopAsyncIteration:
                    self.finished = True
                self.fetch_idle.set()
            else:
                # someone other is already fething
                await self.fetch_idle.wait()
        return not self.finished

    def next_index(self):
        return self.queue_index_offset + len(self.queue)


class TeeOut:
    def __init__(self, tee: Tee):
        self.tee = tee
        tee.ref()
        self.next_index = tee.next_index()

    def __del__(self):
        self.tee.unref(self.next_index)

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.tee.pull_item(self.next_index)
        self.next_index += 1
        return item