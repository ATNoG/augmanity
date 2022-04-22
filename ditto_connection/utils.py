# coding: utf-8


__author__ = 'Mário Antunes'
__version__ = '0.2'
__email__ = 'mario.antunes@ua.pt'
__status__ = 'Development'

import argparse
import json
import datetime
import threading
import statistics

def synchronized(func):
    func.__lock__ = threading.Lock()

    def synced_func(*args, **kws):
        with func.__lock__:
            return func(*args, **kws)

    return synced_func


class Cache:

    def __init__(self, max_cache_size=30):
        self.cache = {}
        self.max_cache_size = max_cache_size

    @synchronized
    def __contains__(self, key):
        """
        Returns True or False depending on whether or not the key is in the 
        cache
        """
        if key in self.cache:
            value = self.cache[key]['value']
            self.cache[key] = {'date_accessed': datetime.datetime.now(), 'value': value}
            return True
        return False

    @synchronized
    def update(self, key, value):
        """
        Update the cache dictionary and optionally remove the oldest item
        """
        if key not in self.cache and len(self.cache) >= self.max_cache_size:
            self.remove_oldest()

        self.cache[key] = {'date_accessed': datetime.datetime.now(), 'value': value}

    @synchronized
    def remove_oldest(self):
        """
        Remove the entry that has the oldest accessed date
        """
        oldest_entry = None
        for key in self.cache:
            if oldest_entry is None:
                oldest_entry = key
            elif self.cache[key]['date_accessed'] < self.cache[oldest_entry]['date_accessed']:
                oldest_entry = key
        self.cache.pop(oldest_entry)

    @property
    def size(self):
        """
        Return the size of the cache
        """
        return len(self.cache)


# Check if a int port number is valid
# Valid is bigger than base port number
def check_port(port, base=1024):
    value = int(port)
    if value <= base:
        raise argparse.ArgumentTypeError('%s is an invalid positive int value' % value)
    return value


def is_json(txt):
    try:
        json.loads(txt)
    except:
        return False
    return True


def deserialize(obj) -> dict:
    if isinstance(obj, dict):
        return obj
    return json.loads(obj)


def is_list_numeric(lst):
    if isinstance(lst, list):
        return all(isinstance(x, (int, float)) for x in lst)
    return False


def is_list_str(lst):
    if isinstance(lst, list):
        return all(isinstance(x, str) for x in lst)
    return False


def is_list_dict(lst):
    if isinstance(lst, list):
        return all(isinstance(x, dict) for x in lst)
    return False


def new_prefix(prefix, key):
    if not prefix:
        return str(key)
    return '%s.%s' % (prefix, key)


def flat_dict(data, prefix=''):
    stack = [(data, prefix)]
    flat = {}

    while stack:
        d, p = stack.pop()
        for key in d.keys():
            value = d[key]
            if isinstance(value, dict):
                stack.append((value, new_prefix(p, key)))
            else:
                if isinstance(value, int):
                    value = float(value)
                flat[new_prefix(prefix, key)] = value
    return flat


def flat_json(j):
    d = deserialize(j)
    return flat_dict(d)


def json_to_influx(device, timestamp, data):
    json_body = {'measurement': "augmanity",
                    'tags': {'device':device},
                    'time': timestamp.isoformat(), 'fields': data["value"]}
    return json_body


def json_to_features(j):
    if is_json(j):
        flat = flat_json(j)
    else:
        flat = flat_dict(j)
    rv = {}
    for key in flat.keys():
        rv[key] = {'properties': {'value': None}}
    return rv


def json_to_function(tenant, j):
    if is_json(j):
        flat = flat_json(j)
    else:
        flat = flat_dict(j)
    values = []
    keys = list(flat.keys())
    for i in range(len(keys) - 1):
        values.append('"{0}": {{"properties": {{"value": jsonData.{1}}}}},'.format(keys[i], keys[i]))
    values.append('"{0}": {{"properties": {{"value": jsonData.{1}}}}}'.format(keys[-1], keys[-1]))
    values = '{{{0}}}'.format(''.join(values))

    function = '''function mapToDittoProtocolMsg(headers, textPayload, bytePayload, contentType) {{
    var jsonData;
    if (contentType == "application/json"){{
        jsonData = JSON.parse(textPayload);
    }} else  {{
        var payload = Ditto.asByteBuffer(bytePayload);
        jsonData = JSON.parse(payload.toUTF8());
    }}
    value = {0};
    return Ditto.buildDittoProtocolMsg({1}, headers["device_id"], "things", "twin", "commands", "modify", "/features", headers, value);
    }}'''.format(values, tenant)

    return function
