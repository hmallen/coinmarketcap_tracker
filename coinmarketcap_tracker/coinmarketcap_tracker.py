import datetime
import json
import logging
import os
import time

from pymarketcap import Pymarketcap
import slackclient

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TrackProduct:
    cmc_client = Pymarketcap()


    def __init__(self, slack_alerts=False, config_path=None):
        self.duration = None

        self.trade_product = None

        self.quote_product = None

        self.loop_time = 300    # Time (seconds) between checks

        if not os.path.exists(self.json_directory):
            os.makedirs(self.json_directory, exist_ok=True)


    def set_parameters(self, market, duration, slack_channel=None, slack_thread=None):
        self.trade_product = market.split('/')[0].upper()

        self.quote_product = market.split('/')[-1].upper()

        try:
            cmc_client.ticker(currency=self.trade_product)

        except:
            logger.error('Could not retrieve Coinmarketcap data for ' + self.trade_product + '.')

            return False

        try:
            cmc_client.ticker(currency=self.trade_product, convert=self.quote_product)

        except:
            logger.error('Could not convert Coinmarketcap ticker data using quote product ' + self.quote_product + '.')

            return False

        self.track_end_time = datetime.datetime.now() + datetime.timedelta(hours=duration)

        return True


    def track_product(self):
        while (datetime.datetime.now() < self.track_end_time):
            try:
                cmc_data = cmc_client.ticker(currency=self.trade_product, convert=self.quote_product)

                logger.debug('Dumping Coinmarketcap data to json file.')

                with open(self.cmc_data_file, 'w', encoding='utf-8') as file:
                    json.dump(cmc_data, file, indent=4, sort_keys=True, ensure_ascii=False)

                time.sleep(self.loop_time)

            except Exception as e:
                logger.exception('Exception while retrieving Coinmarketcap data.')
                logger.exception(e)

                time.sleep(5)


if __name__ == '__main__':
    cmc_tracker = TrackProduct()
