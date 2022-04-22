import multiprocessing
from queue import Empty
import time
from influxdb import InfluxDBClient
import multiprocessing as mp
from multiprocessing import Queue
import queue
import logging
logging.basicConfig(filename='influx.log', level=logging.INFO)
logger = logging.getLogger('InfluxDB Handler')

class InfluxDBHandler(multiprocessing.Process):
    def __init__(self, host, port ,user, password, database, queue):
        super(InfluxDBHandler,self).__init__()
        self.client = InfluxDBClient(host=host, port=port, username=user, password=password, database=database)
        self.queue = queue
        self.batch = []
        self.last_batch_time = time.time()
        self.BATCH_WAIT_TIME = 2
        self.BATCH_MAX_SIZE = 100
        
    def run(self):
        while True:
            try:
                # Insert into database
                num_points = len(self.batch)
                curr_time = time.time()
                if num_points >= self.BATCH_MAX_SIZE or (num_points > 0 and curr_time - self.last_batch_time >= self.BATCH_WAIT_TIME):
                    logger.debug(f'Storing batch into InfluxDB with len {num_points}')
                    self.client.write_points(self.batch, time_precision='ms')
                    self.last_batch_time = curr_time
                    self.batch.clear()
                # Add more info to batch
                self.add_to_batch()
            except queue.Empty:
                logger.debug("Empty queue found")
                continue

    def add_to_batch(self):
        logger.debug("Saving to batch")
        data = self.queue.get(timeout=2)
        logger.debug("Queue received data")
        device = data["thingId"]
        timestamp = data["_modified"]
        for feature in data["features"]:
            tmp_data = {'measurement': feature,
                    'tags': {'thingId':device},
                    'time': timestamp, 'fields': dict(value=data["features"][feature]["properties"]["value"])}
            self.batch.append(tmp_data)

    def _check_database(self,database):
        for db in self.client.get_list_database():
            if db["name"] == database:
                return 
    
        logger.info(f"Database {database} doesn't exist. Creating...")
        self._create_database(database)