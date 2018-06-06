import datetime
import json
import logging
import os
import sys
import time

import configparser
from slackclient import SlackClient

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TrackProduct:
    from pymarketcap import Pymarketcap

    cmc_client = Pymarketcap()


    def __init__(self, json_directory='json/coinmarketcap_tracker/', loop_time=300,
                 slack_alerts=False, slack_alert_interval=60, config_path=None):
        self.trade_product = None

        self.quote_product = None

        self.loop_time = loop_time    # Time (seconds) between checks

        self.json_directory = json_directory

        if self.json_directory[-1] != '/':
            self.json_directory += '/'

        if not os.path.exists(self.json_directory):
            os.makedirs(self.json_directory, exist_ok=True)

        self.slack_alerts = slack_alerts

        self.slack_alert_interval = slack_alert_interval

        if self.slack_alerts == True:
            if config_path == None:
                logger.error('Must provide path to config file if Slack alerts enabled. Exiting.')

                sys.exit(1)

            else:
                try:
                    config = configparser.ConfigParser()
                    config.read(config_path)

                    slack_token = config['slack']['slack_token']

                    self.slack_client = SlackClient(slack_token)

                    self.slack_bot_user = config['settings']['slack_bot_user']

                    self.slack_bot_icon = config['settings']['slack_bot_icon']

                except Exception as e:
                    logger.exception('Exception while initializing Slack client. Exiting.')
                    logger.exception(e)

                    sys.exit(1)

        else:
            self.slack_client = None


    def set_parameters(self, market, tracking_duration, slack_channel=None, slack_thread=None):
        self.trade_product = market.split('/')[0].upper()

        self.quote_product = market.split('/')[-1].upper()

        try:
            TrackProduct.cmc_client.ticker(currency=self.trade_product)

        except TrackProduct.cmc_client.errors.CoinmarketcapError as e:
            logger.error('Error while retrieving Coinmarketcap data for ' + self.trade_product + '.')
            logger.error(e)

            return False

        except Exception as e:
            logger.exception('Unhandled exception while retrieving Coinmarketcap data for ' + self.trade_product + '.')
            logger.exception(e)

            return False

        try:
            TrackProduct.cmc_client.ticker(currency=self.trade_product, convert=self.quote_product)

        except TrackProduct.cmc_client.errors.CoinmarketcapError as e:
            logger.error('Error while converting Coinmarketcap ticker data using quote product ' + self.quote_product + '.')
            logger.error(e)

            return False

        except Exception as e:
            logger.exception('Unhandled exception while converting Coinmarketcap ticker data using quote product ' + self.quote_product + '.')
            logger.exception(e)

            return False

        self.track_end_time = datetime.datetime.now() + datetime.timedelta(hours=tracking_duration)

        #self.market_directory = self.json_directory + self.trade_product + '_' + self.quote_product + '_' + datetime.datetime.now().strftime('%m%d%Y_%H%M%S') + '/'
        self.market_directory = self.json_directory + self.trade_product + '_' + self.quote_product + '/'

        if not os.path.exists(self.market_directory):
            logger.debug('Creating data directory.')

            os.makedirs(self.market_directory, exist_ok=True)

        self.cmc_data_file = self.market_directory + 'historical_data.json'

        if self.slack_client != None:
            channel_list = self.slack_client.api_call('channels.list')
            group_list = self.slack_client.api_call('groups.list')

            self.slack_channel_tracker = slack_channel

            slack_channel_targets = {'tracker': self.slack_channel_tracker}

            for target in slack_channel_targets:
                try:
                    logger.debug('channel_list.get(\'ok\'): ' + str(channel_list.get('ok')))
                    if channel_list.get('ok'):
                        for chan in channel_list['channels']:
                            logger.debug('chan[\'name\']: ' + chan['name'])
                            if chan['name'] == slack_channel_targets[target]:
                                if target == 'tracker':
                                    slack_channel_id_tracker = chan['id']

                                elif target == 'exceptions':
                                    slack_channel_id_exceptions = chan['id']

                                break
                        else:
                            logger.error('No valid Slack channel found for alert in channel list.')

                            sys.exit(1)

                    else:
                        logger.error('Channel list API call failed.')

                        sys.exit(1)

                except:
                    logger.debug('group_list.get(\'ok\'): ' + str(group_list.get('ok')))
                    if group_list.get('ok'):
                        for group in group_list['groups']:
                            logger.debug('group[\'name\']: ' + group['name'])
                            if group['name'] == slack_channel_targets[target]:
                                if target == 'tracker':
                                    slack_channel_id_tracker = group['id']

                                elif target == 'exceptions':
                                    slack_channel_id_exceptions = group['id']

                                break
                        else:
                            logger.error('No valid Slack channel found for alert in group list.')

                            sys.exit(1)

                    else:
                        logger.error('Group list API call failed.')

                        sys.exit(1)

            self.slack_channel_id_tracker = slack_channel_id_tracker

            logger.info('Slack channel for tracker alerts: #' + self.slack_channel_tracker +
                        ' (' + self.slack_channel_id_tracker + ')')

        return True


    def track_product(self, load_data=False):
        market_data_archive = []

        if os.path.exists(self.cmc_data_file):
            if load_data == True:
                try:
                    with open(self.cmc_data_file, 'r', encoding='utf-8') as file:
                        market_data_archive = json.load(file)

                except:
                    logger.error('Failed to load json data from file.')

                    if market_data_archive != []:
                        market_data_archive = []

            else:
                logger.info('Removing old json data file.')

                os.remove(self.cmc_data_file)

        if market_data_archive == []:
            with open(self.cmc_data_file, 'w', encoding='utf-8') as file:
                json.dump(market_data_archive, file, indent=4, sort_keys=True, ensure_ascii=False)

        while (datetime.datetime.now() < self.track_end_time):
            try:
                cmc_data = TrackProduct.cmc_client.ticker(currency=self.trade_product, convert=self.quote_product)

                if cmc_data['metadata']['error'] == None:
                    market_data_archive.append(cmc_data)

                    logger.debug('Dumping Coinmarketcap data to json file.')

                    with open(self.cmc_data_file, 'w', encoding='utf-8') as file:
                        json.dump(market_data_archive, file, indent=4, sort_keys=True, ensure_ascii=False)

                else:
                    logger.error('Coinmarketcap return metadata indicates an error occurred. Not adding to historical data.')

                logger.debug('Sleeping for ' + str(self.loop_time) + ' seconds.')

                time.sleep(self.loop_time)

            except Exception as e:
                logger.exception('Exception while retrieving Coinmarketcap data.')
                logger.exception(e)

                time.sleep(5)


if __name__ == '__main__':
    from multiprocessing import Process

    test_config_path = '../../TeslaBot/config/config.ini'

    test_slack_channel = 'testing'

    #test_slack_channel_id = 'CAX1A4XU1'

    cmc_tracker = TrackProduct(loop_time=30, slack_alerts=True, slack_alert_interval=5, config_path=test_config_path)

    test_market = 'XLM/BTC'

    # (self, market, tracking_duration, slack_channel=None, slack_thread=None)

    cmc_tracker.set_parameters(market=test_market, tracking_duration=0.2, slack_channel='testing')

    try:
        #cmc_tracker.track_product(load_data=False)

        keyword_arguments = {'load_data': False}

        tracker_process = Process(target=cmc_tracker.track_product, kwargs=keyword_arguments)

        tracker_process.start()

        tracker_process.join()

        logger.info('Done.')

    except Exception as e:
        logger.exception('Unhandled exception in main loop.')
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')

        #sys.exit()
