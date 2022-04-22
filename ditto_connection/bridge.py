# coding: utf-8

import argparse
import logging
import multiprocessing
import time
import multiprocessing as mp
from collections import defaultdict
from multiprocessing import Queue
from utils import check_port
from datetime import datetime, timedelta
from handlers.influxdb_handler import InfluxDBHandler
import requests
import sseclient
import time
import json

logger = logging.getLogger('BRIDGE')

# Ditto handler
class DittoHandler(multiprocessing.Process):
    def __init__(self, addr: str, port: int, user: str, pwd: str,
                 db_queues: list):
        logger.debug("Ditto worker starting")
        super(DittoHandler,self).__init__()
        self.addr = addr
        self.port = port
        self.user = user
        self.pwd = pwd
        self.db_queues = db_queues

    def run(self):
        logger.debug("Starting DittoHandler")
        url = f'http://{self.addr}:{self.port}/api/2/things?fields=thingId,features'
        headers = {'Accept': 'text/event-stream'}
        stream_response = requests.get(url, auth=requests.auth.HTTPBasicAuth(self.user,self.pwd), stream=True, headers = headers)
        
        client = sseclient.SSEClient(stream_response)

        for event in client.events():
            if len(event.data)>0:
                # TODO change to something differente when receiving from hono
                obj = json.loads(event.data)
                for db_queue in self.db_queues:
                    try:
                        logger.debug('on_message database insert')
                        db_queue.put(obj, False)
                    except:
                        logger.warning('A queue is full!')

def main(args):

    db_queues = []
    processes = []

    manager = mp.Manager()
    influx_queue = manager.Queue(maxsize=10000)
    db_queues.append(influx_queue)
   
    processes.append(InfluxDBHandler(host=args.addr_influxdb, 
                                    port=args.port_influxdb,
                                    user=args.influxdb_user, password=args.influxdb_pwd, database='bosch',
                                    queue=influx_queue))
    processes.append(DittoHandler(addr=args.addr_ditto, 
                        port=args.port_ditto, user=args.ditto_user, pwd=args.ditto_pwd, db_queues=db_queues))
    
    for process in processes:
        process.start()
        
    while True:
        try:
            time.sleep(100)
        except KeyboardInterrupt:
            for process in processes:
                process.terminate()
                exit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Bosch Hono to Influx bridge')

    parser.add_argument('--addr_ditto', help='ip address Hono', default='10.0.13.32')
    parser.add_argument('--port_ditto', type=check_port, help='ip port Hono', default=30525)
    parser.add_argument('--ditto_user', help="hono user", default="ditto")
    parser.add_argument('--ditto_pwd', help="hono password",default="ditto")
    
    parser.add_argument('--addr_influxdb', help='ip address influxdb', default='10.152.183.48')
    parser.add_argument('--port_influxdb', type=check_port, help='ip port influxdb', default=8086)
    parser.add_argument('--influxdb_db',help="influxdb database",default="bosch")
    parser.add_argument('--influxdb_user', help="influxdb user",default="root")
    parser.add_argument('--influxdb_pwd', help="influxdb password",default="root")
    
    args = parser.parse_args()
    main(args)
