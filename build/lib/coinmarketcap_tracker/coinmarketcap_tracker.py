import configparser
import datetime
import json
import logging
import os
import sys
import time

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

        self.slack_alert_interval = datetime.timedelta(minutes=slack_alert_interval).total_seconds()

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

                    self.slack_channel_id_tracker = None

                    self.slack_thread = None

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

            self.slack_thread = slack_thread

        return True


    def send_slack_alert(self, channel_id, message, thread_id=None):
        alert_return = {'Exception': False, 'result': None}

        try:
            alert_return['result'] = self.slack_client.api_call(
                'chat.postMessage',
                channel=channel_id,
                text=message,
                username=self.slack_bot_user,
                #icon_emoji=self.slack_bot_icon,
                icon_url=self.slack_bot_icon,
                thread_ts=thread_id,
                reply_broadcast=True
                #attachments=attachments
            )

        except Exception as e:
            logger.exception('Exception while sending Slack alert.')
            logger.exception(e)

            alert_return['Exception'] = True

        finally:
            return alert_return


    def track_product(self, load_data=False):
        def compile_results(data_list):
            results_return = {'Exception': False, 'result': ()}

            try:
                pass

            except Exception as e:
                logger.exception('Exception while compiling product tracker results.')
                logger.exception(e)

                results_return['Exception'] = True

            finally:
                return results_return


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

        slack_message_last = 0

        while (datetime.datetime.now() < self.track_end_time):
            try:
                cmc_data = TrackProduct.cmc_client.ticker(currency=self.trade_product, convert=self.quote_product)

                if cmc_data['metadata']['error'] == None:
                    cmc_data_product = cmc_data['data']

                    market_data_archive.append(cmc_data_product)

                    logger.debug('Dumping Coinmarketcap data to json file.')

                    with open(self.cmc_data_file, 'w', encoding='utf-8') as file:
                        json.dump(market_data_archive, file, indent=4, sort_keys=True, ensure_ascii=False)

                else:
                    logger.error('Coinmarketcap return metadata indicates an error occurred. Not adding to historical data.')

                    logger.error('Error: ' + str(cmc_data['metadata']['error']))

                if (time.time() - slack_message_last) > self.slack_alert_interval:
                    logger.debug('Sending Slack alert.')

                    quotes_last = cmc_data_product['quotes'][self.quote_product]

                    slack_message = ''

                    for quote in quotes_last:
                        quote_title_words = quote.split('_')

                        quote_title = ''

                        for word in quote_title_words:
                            if word[0].isnumeric():
                                word_modified = '(' + word + ')'

                            else:
                                word_modified = word.capitalize()

                            #quote_title += word.capitalize() + ' '
                            quote_title += word_modified + ' '

                        quote_title = quote_title.rstrip(' ')

                        message_line = '*' + quote_title + ':* '# + quotes_last[quote]

                        if 'Volume' in quote_title:
                            if self.quote_product == 'USD':
                                message_line += '$' + "{:.2f}".format(quotes_last[quote])

                            else:
                                message_line += "{:.2f}".format(quotes_last[quote]) + ' ' + self.quote_product

                        elif quote_title == 'Price':
                            if self.quote_product == 'USD':
                                message_line += '$'

                                if quotes_last[quote] < 1:
                                    message_line += "{:.4f}".format(quotes_last[quote])
                                else:
                                    message_line += "{:.2f}".format(quotes_last[quote])

                            else:
                                message_line += "{:.8f}".format(quotes_last[quote]) + ' ' + self.quote_product

                        elif 'Percent' in quote_title:
                            message_line += "{:.2f}".format(quotes_last[quote]) + '%'

                        elif quote_title == 'Market Cap':
                            if self.quote_product == 'USD':
                                message_line += '$' + "{:.2f}".format(quotes_last[quote])

                            else:
                                message_line += "{:.2f}".format(quotes_last[quote]) + ' ' + self.quote_product

                        else:
                            logger.warning('Unknown quote message type.')

                            logger.warning('quote: ' + quote)

                            logger.warning('quote_title: ' + quote_title)

                        message_line += '\n'

                        slack_message += message_line

                    slack_message = slack_message.rstrip('\n')

                    alert_result = TrackProduct.send_slack_alert(self,
                                                                 channel_id=self.slack_channel_id_tracker,
                                                                 message=slack_message,
                                                                 thread_id=self.slack_thread)

                    logger.debug('alert_result: ' + str(alert_result))

                    slack_message_last = time.time()

                logger.debug('Sleeping for ' + str(self.loop_time) + ' seconds.')

                time.sleep(self.loop_time)

            except Exception as e:
                logger.exception('Exception while retrieving Coinmarketcap data.')
                logger.exception(e)

                time.sleep(5)

            except KeyboardInterrupt:
                logger.debug('Exit signal received in tracking loop. Raising exception.')

                raise

        # Read json data from file or use current data dictionary?
        tracker_results = compile_results(data_list=market_data_archive)

        # SEND SLACK ALERT


if __name__ == '__main__':
    from multiprocessing import Process

    test_config_path = '../../TeslaBot/config/config.ini'

    test_slack_channel = 'testing'

    #test_slack_channel_id = 'CAX1A4XU1'

    cmc_tracker = TrackProduct(loop_time=30, slack_alerts=True, slack_alert_interval=2, config_path=test_config_path)

    test_market = 'XLM/BTC'

    # (self, market, tracking_duration, slack_channel=None, slack_thread=None)

    cmc_tracker.set_parameters(market=test_market, tracking_duration=0.1, slack_channel='testing')

    try:
        #cmc_tracker.track_product(load_data=False)

        keyword_arguments = {'load_data': False}

        tracker_process = Process(target=cmc_tracker.track_product, kwargs=keyword_arguments)

        logger.info('Starting tracker in separate process.')

        tracker_process.start()

        logger.info('Joining process.')

        tracker_process.join()

        logger.info('Done.')

    except Exception as e:
        logger.exception('Unhandled exception in main loop.')
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')

        logger.info('Terminating tracker process.')

        tracker_process.terminate()

        logger.info('Joining terminated process to ensure clean exit.')

        tracker_process.join()

    finally:
        #logger.info('Terminating tracker process.')

        #tracker_process.terminate()

        #logger.info('Joining terminated process to ensure clean exit.')

        #tracker_process.join()

        logger.info('Done.')
