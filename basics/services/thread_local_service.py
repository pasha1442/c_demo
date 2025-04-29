import threading
import copy


class ThreadLocal:

    def __init__(self):
        self._local = threading.local()

    @property
    def _data(self):
        if not hasattr(self._local, 'store'):
            self._local.store = dict()

        return self._local.store

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def update(self, data: dict):
        self._data.update(data)

    def delete(self, key):
        if key in self._data:
            del self._data[key]

    def get_all(self):
        return copy.deepcopy(self._data)


thread_local = ThreadLocal()