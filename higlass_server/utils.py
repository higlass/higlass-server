import redis
import higlass_server.settings as hss

from redis.exceptions import ConnectionError


class EmptyRDB:
    def __init__(self):
        pass

    def exists(self, name):
        return False

    def get(self, name):
        return None

    def set(self, name, value, ex=None, px=None, nx=False, xx=False):
        pass


def getRdb():
    if hss.REDIS_HOST is not None:
        try:
            rdb = redis.Redis(
                host=hss.REDIS_HOST,
                port=hss.REDIS_PORT)

            # Test server connection
            rdb.ping()

            return rdb
        except ConnectionError:
            return EmptyRDB()
    else:
        return EmptyRDB()
