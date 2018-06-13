import configparser
import datetime
import json
import logging
import os
import sys
import time

from heartbeatmonitor import Heartbeat
from slackclient import SlackClient

#logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TrackProduct:
    from pymarketcap import Pymarketcap

    cmc_client = Pymarketcap()


    def __init__(self, json_directory='json/coinmarketcap_tracker/', loop_time=300,
                 slack_alerts=False, slack_alert_interval=60,
                 heartbeat_monitor=False, config_path=None):
        self.market_name = None

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

        self.heartbeat_monitor = heartbeat_monitor

        if self.heartbeat_monitor == True:
            if config_path == None:
                logger.error('Must provide path to config file if heartbeat monitor enabled. Exiting.')

                sys.exit(1)

            hb_json_directory = 'json/heartbeat/'

            hb_timeout = self.loop_time * 2

            hb_alert_reset_interval = hb_timeout * 2

            # Initialize Heartbeat Monitor
            self.hb = Heartbeat(module='Coinmarketcap Tracker', monitor='slack',
                                config_path=config_path, json_directory=hb_json_directory,
                                heartbeat_timeout=hb_timeout, alert_reset_interval=hb_alert_reset_interval,
                                flatline_alerts_only=False)

            logger.info('Enabling heartbeat.')

            self.hb.enable_heartbeat()

            time.sleep(5)   # Is this necessary?

            logger.info('Heartbeat monitor ready.')


    def set_parameters(self, market, tracking_duration, slack_channel=None, slack_channel_id=None, slack_thread=None):
        self.market_name = market

        self.trade_product = market.split('/')[0].upper()

        self.quote_product = market.split('/')[-1].upper()

        self.slack_channel = slack_channel

        #self.slack_channel_id = slack_channel_id

        self.slack_thread = slack_thread

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

            if slack_channel_id == None:
                #self.slack_channel_tracker = slack_channel

                #slack_channel_targets = {'tracker': self.slack_channel_tracker}
                slack_channel_targets = {'tracker': self.slack_channel}

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

            else:
                self.slack_channel_id_tracker = slack_channel_id

            #logger.info('Slack channel for tracker alerts: #' + self.slack_channel_tracker +
                        #' (' + self.slack_channel_id_tracker + ')')
            logger.info('Slack channel for tracker alerts: #' + self.slack_channel +
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
        def format_slack_message(input_data, message_type):
            message_formatted = ''

            try:
                if message_type == 'quote':
                    dt_timestamp = datetime.datetime.fromtimestamp(input_data['metadata']['timestamp'])#.isoformat(sep=' ', timespec='seconds')
                    logger.debug('dt_timestamp: ' + str(dt_timestamp))

                    dt_header = dt_timestamp.strftime('%m-%d-%y %H:%M:%S')

                    message_formatted += '*_' + dt_header + ' - ' + self.market_name + '_*\n'

                    quotes_last = input_data['data']['quotes'][self.quote_product]

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

                        message_formatted += message_line

                    message_formatted = message_formatted.rstrip('\n')

                elif message_type == 'final':
                    dt_current = datetime.datetime.now()
                    logger.debug('dt_current: ' + str(dt_current))

                    dt_header = dt_current.strftime('%m-%d-%y %H:%M:%S')
                    logger.debug('dt_header: ' + str(dt_header))

                    message_formatted += '*_' + dt_header + ' - ' + self.market_name + '_*\n'

                    ## Tracking duration ##
                    #message_formatted += '*Tracking Duration:* ' + "{:.2f}".format(input_data['duration_minutes']) + ' hours\n'
                    #message_formatted += '*Tracking Duration:* ' + str(round(input_data['duration_minutes'], 2)) + ' hours\n'
                    message_formatted += '*Tracking Duration:* ' + input_data['duration_string'] + '\n'

                    ## Price change ##
                    message_formatted += '*Price Change:* '

                    if self.quote_product == 'USD':
                        #message_formatted += '$' + "{:.2f}".format(input_data['price_first']) + ' ---> $' + "{:.2f}".format(input_data['price_last']) + ' _('
                        message_formatted += "{:.2f}".format(input_data['price_first']) + ' --> $' + "{:.2f}".format(input_data['price_last']) + ' _('

                        if input_data['price_difference'] > 0:
                            message_formatted += '+'

                        elif input_data['price_difference'] < 0:
                            message_formatted += '-'

                            input_data['price_difference'] = abs(input_data['price_difference'])

                        else:
                            pass    # Nothing required

                        #message_formatted += '$' + "{:.2f}".format(input_data['price_difference']) + ' || '
                        message_formatted += "{:.2f}".format(input_data['price_difference']) + ' || '

                    else:
                        #message_formatted += ("{:.8f}".format(input_data['price_first']) + ' ' + self.quote_product + '/' + self.trade_product + ' ---> ' +
                                              #"{:.8f}".format(input_data['price_last']) + ' ' + self.quote_product + '/' + self.trade_product + ' _(')
                        message_formatted += ("{:.8f}".format(input_data['price_first']) + ' --> ' +
                                              "{:.8f}".format(input_data['price_last']) + ' ' + self.quote_product + '/' + self.trade_product + ' _(')

                        if input_data['price_difference'] > 0:
                            message_formatted += '+'

                        elif input_data['price_difference'] < 0:
                            message_formatted += '-'

                            input_data['price_difference'] = abs(input_data['price_difference'])

                        else:
                            pass    # Nothing required

                        #message_formatted += "{:.8f}".format(input_data['price_difference']) + ' ' + self.quote_product + '/' + self.trade_product + ' || '
                        message_formatted += "{:.8f}".format(input_data['price_difference']) + ' || '

                    if input_data['price_percent_difference'] > 0:
                        message_formatted += '+'

                    elif input_data['price_percent_difference'] < 0:
                        message_formatted += '-'

                        input_data['price_percent_difference'] = abs(input_data['price_percent_difference'])

                    else:
                        pass    # Nothing required

                    message_formatted += "{:.2f}".format(input_data['price_percent_difference']) + '%)_\n'

                    ## Marketcap change ##
                    message_formatted += '*Market Cap Change:* '

                    if self.quote_product == 'USD':
                        #message_formatted += '$' + "{:.2f}".format(input_data['marketcap_first']) + ' ---> $' + "{:.2f}".format(input_data['marketcap_last']) + ' _('
                        message_formatted += "{:.2f}".format(input_data['marketcap_first']) + ' --> $' + "{:.2f}".format(input_data['marketcap_last']) + ' _('

                        if input_data['marketcap_difference'] > 0:
                            message_formatted += '+'

                        elif input_data['marketcap_difference'] < 0:
                            message_formatted += '-'

                            input_data['marketcap_difference'] = abs(input_data['marketcap_difference'])

                        else:
                            pass    # Nothing required

                        #message_formatted += '$' + "{:.2f}".format(input_data['marketcap_difference']) + ' || '
                        message_formatted += "{:.2f}".format(input_data['marketcap_difference']) + ' || '

                    else:
                        #message_formatted += ("{:.2f}".format(input_data['marketcap_first']) + ' ' + self.quote_product + ' ---> ' +
                                              #"{:.2f}".format(input_data['marketcap_last']) + ' ' + self.quote_product + ' _(')
                        message_formatted += ("{:.2f}".format(input_data['marketcap_first']) + ' --> ' +
                                              "{:.2f}".format(input_data['marketcap_last']) + ' ' + self.quote_product + ' _(')

                        if input_data['marketcap_difference'] > 0:
                            message_formatted += '+'

                        elif input_data['marketcap_difference'] < 0:
                            message_formatted += '-'

                            input_data['marketcap_difference'] = abs(input_data['marketcap_difference'])

                        else:
                            pass    # Nothing required

                        #message_formatted += "{:.2f}".format(input_data['marketcap_difference']) + ' ' + self.quote_product + ' || '
                        message_formatted += "{:.2f}".format(input_data['marketcap_difference']) + ' || '

                    if input_data['marketcap_percent_difference'] > 0:
                        message_formatted += '+'

                    elif input_data['marketcap_percent_difference'] < 0:
                        message_formatted += '-'

                        input_data['marketcap_percent_difference'] = abs(input_data['marketcap_percent_difference'])

                    else:
                        pass

                    message_formatted += "{:.2f}".format(input_data['marketcap_percent_difference']) + '%)_\n'

                    ## Rank change ##
                    message_formatted += '*Rank Change:* #' + "{:.0f}".format(input_data['rank_first']) + ' --> #' + "{:.0f}".format(input_data['rank_last']) + ' _('

                    if input_data['rank_difference'] == 0:
                        message_formatted += 'No Change'

                    else:
                        if input_data['rank_difference'] > 0:
                            message_formatted += '+'

                        message_formatted += "{:.0f}".format(input_data['rank_difference'])

                    message_formatted += ')_'

                else:
                    logger.error('Unrecognized message type in format_slack_message().')

            except Exception as e:
                logger.exception('Exception while formatting quote data.')
                logger.exception(e)

            finally:
                return message_formatted


        def prepare_results(data_list):
            results = {'Exception': False,'result': {}}

            try:
                ## Duration, price, market cap, rank ##

                # Timestamp data
                timestamp_last = data_list[-1]['metadata']['timestamp']
                logger.debug('timestamp_last: ' + str(timestamp_last))

                timestamp_first = data_list[0]['metadata']['timestamp']
                logger.debug('timestamp_first: ' + str(timestamp_first))

                # Calculate duration from timestamps
                timestamp_delta = datetime.datetime.fromtimestamp(timestamp_last) - datetime.datetime.fromtimestamp(timestamp_first)
                logger.debug('timestamp_delta: ' + str(timestamp_delta))

                #duration_hours = timestamp_delta / datetime.timedelta(hours=1)
                duration_minutes = timestamp_delta / datetime.timedelta(minutes=1)
                logger.debug('duration_minutes: ' + str(duration_minutes))

                hour_count = int(duration_minutes / 60)
                minute_count = duration_minutes % 60

                duration_string = str(hour_count) + 'hour'

                if hour_count == 0 or hour_count > 1:
                    duration_string += 's'

                duration_string += ' ' + "{:.2f}".format(minute_count) + 'minute'

                if minute_count != 1:
                    duration_string += 's'

                logger.debug('duration_string: ' + duration_string)

                # Price data
                price_first = data_list[0]['data']['quotes'][self.quote_product]['price']
                logger.debug('price_first: ' + str(price_first))

                price_last = data_list[-1]['data']['quotes'][self.quote_product]['price']
                logger.debug('price_last: ' + str(price_last))

                price_difference = price_last - price_first
                logger.debug('price_difference: ' + str(price_difference))

                price_percent_difference = (price_difference / price_first) * 100
                logger.debug('price_percent_difference: ' + str(price_percent_difference))

                # Market cap data
                marketcap_first = data_list[0]['data']['quotes'][self.quote_product]['market_cap']
                logger.debug('marketcap_first: ' + str(marketcap_first))

                marketcap_last = data_list[-1]['data']['quotes'][self.quote_product]['market_cap']
                logger.debug('marketcap_last: ' + str(marketcap_last))

                marketcap_difference = marketcap_last - marketcap_first
                logger.debug('marketcap_difference: ' + str(marketcap_difference))

                marketcap_percent_difference = (marketcap_difference / marketcap_first) * 100
                logger.debug('marketcap_percent_difference: ' + str(marketcap_percent_difference))

                # Ranking data
                rank_first = data_list[0]['data']['rank']
                logger.debug('rank_first: ' + str(rank_first))

                rank_last = data_list[-1]['data']['rank']
                logger.debug('rank_last: ' + str(rank_last))

                rank_difference = rank_first - rank_first
                logger.debug('rank_difference: ' + str(rank_difference))

                results['result'] = dict(price_first=price_first, price_last=price_last, price_difference=price_difference,
                                         price_percent_difference=price_percent_difference,
                                         marketcap_first=marketcap_first, marketcap_last=marketcap_last, marketcap_difference=marketcap_difference,
                                         marketcap_percent_difference=marketcap_percent_difference,
                                         rank_first=rank_first, rank_last=rank_last, rank_difference=rank_difference,
                                         timestamp_first=timestamp_first, timestamp_last=timestamp_last, timestamp_delta=timestamp_delta,
                                         duration_minutes=duration_minutes, duration_string=duration_string)

            except Exception as e:
                logger.exception('Exception while preparing final results from tracker.')
                logger.exception(e)

                results['Exception'] = True

            finally:
                return results


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

        update_count = 0

        loop_start = time.time()

        loop_count = 0
        while (datetime.datetime.now() < self.track_end_time):
            try:
                ## HEARTBEAT
                if self.heartbeat_monitor == True:
                    self.hb.heartbeat(message='Quote Check: ' + self.market_name)

                loop_count += 1
                logger.debug('loop_count: ' + str(loop_count))

                cmc_data = TrackProduct.cmc_client.ticker(currency=self.trade_product, convert=self.quote_product)

                if cmc_data['metadata']['error'] == None:
                    if loop_count > 1 and cmc_data['data']['last_updated'] > market_data_archive[-1]['data']['last_updated']:
                        update_count += 1

                        market_data_archive.append(cmc_data)

                        logger.debug('Dumping Coinmarketcap data to json file.')

                        with open(self.cmc_data_file, 'w', encoding='utf-8') as file:
                            json.dump(market_data_archive, file, indent=4, sort_keys=True, ensure_ascii=False)

                    elif loop_count == 1:
                        update_count += 1

                        market_data_archive.append(cmc_data)

                        slack_message = format_slack_message(cmc_data, message_type='quote')
                        logger.debug('slack_message: ' + slack_message)

                        logger.debug('Sending Slack alert.')

                        alert_result = TrackProduct.send_slack_alert(self,
                                                                     channel_id=self.slack_channel_id_tracker,
                                                                     message=slack_message,
                                                                     thread_id=self.slack_thread)

                        logger.debug('alert_result: ' + str(alert_result))

                        slack_message_last = time.time()

                    else:
                        logger.debug('No new data available. Skipping append to data archive.')

                else:
                    logger.error('Coinmarketcap return metadata indicates an error occurred. Not adding to historical data.')

                    logger.error('Error: ' + str(cmc_data['metadata']['error']))

                if (time.time() - slack_message_last) > self.slack_alert_interval:
                    if cmc_data['data']['last_updated'] > market_data_archive[-1]['data']['last_updated']:
                        slack_message = format_slack_message(cmc_data, message_type='quote')
                        logger.debug('slack_message: ' + slack_message)

                        logger.debug('Sending Slack alert.')

                        alert_result = TrackProduct.send_slack_alert(self,
                                                                     channel_id=self.slack_channel_id_tracker,
                                                                     message=slack_message,
                                                                     thread_id=self.slack_thread)

                        logger.debug('alert_result: ' + str(alert_result))

                        slack_message_last = time.time()

                    else:
                        logger.debug('Slack alert ready, but no data update. Skipping.')

                time_elapsed = time.time() - loop_start
                logger.debug('time_elapsed: ' + "{:.2f}".format(time_elapsed) + ' sec')

                time_remaining = (self.track_end_time - datetime.datetime.now()) / datetime.timedelta(minutes=1)
                logger.debug('time_remaining: ' + "{:.2f}".format(time_remaining) + ' min')

                logger.debug('update_count: ' + str(update_count))

                logger.debug('Sleeping for ' + str(self.loop_time) + ' seconds.')

                time.sleep(self.loop_time)

            except Exception as e:
                logger.exception('Exception while retrieving Coinmarketcap data.')
                logger.exception(e)

                #time.sleep(5)

        try:
            if update_count > 1:
                # Read json data from file or use current data dictionary?
                tracker_results = prepare_results(data_list=market_data_archive)

                logger.debug('tracker_results[\'Exception\']: ' + str(tracker_results['Exception']))

                logger.debug('tracker_results[\'result\']: ' + str(tracker_results['result']))

                if tracker_results['Exception'] == False:
                    tracker_message = format_slack_message(input_data=tracker_results['result'], message_type='final')

                    message_result = TrackProduct.send_slack_alert(self,
                                                                   channel_id=self.slack_channel_id_tracker,
                                                                   message=tracker_message, thread_id=self.slack_thread)

                    logger.debug('message_result: ' + str(message_result))

                else:
                    logger.error('Failed to send final Slack message to due exception while preparing results.')

            else:
                logger.warning('Only 1 update archived from Coinmarketcap. Skipping final analysis.')

        except Exception as e:
            logger.exception('Exception while preparing and sending final tracking results.')
            logger.exception(e)

        if self.heartbeat_monitor == True:
            logger.info('Disabling heartbeat.')

            self.hb.disable_heartbeat()


if __name__ == '__main__':
    import multiprocessing
    from multiprocessing import Process

    test_config_path = '../../TeslaBot/config/config.ini'

    test_slack_channel = 'testing'

    #test_slack_channel_id = 'CAX1A4XU1'

    cmc_tracker = TrackProduct(loop_time=30, slack_alerts=True, slack_alert_interval=1,
                               config_path=test_config_path, heartbeat_monitor=True)

    test_market = 'XLM/BTC'

    # (self, market, tracking_duration, slack_channel=None, slack_thread=None)

    parameter_result = cmc_tracker.set_parameters(market=test_market, tracking_duration=0.1, slack_channel='testing')
    logger.debug('parameter_result: ' + str(parameter_result))

    try:
        #cmc_tracker.track_product(load_data=False)

        arguments = tuple()

        keyword_arguments = {'load_data': False}

        tracker_process = Process(target=cmc_tracker.track_product, args=arguments, kwargs=keyword_arguments)

        logger.info('Starting tracker in separate process.')

        tracker_process.start()

        logger.info('Joining process.')

        tracker_process.join()

    except Exception as e:
        logger.exception('Unhandled exception in main loop.')
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')

        #logger.info('Terminating tracker process.')

        #tracker_process.terminate()

        #logger.info('Joining terminated process to ensure clean exit.')

        #tracker_process.join()

    finally:
        """
        logger.info('Terminating tracker process.')

        tracker_process.terminate()

        logger.info('Joining terminated process to ensure clean exit.')

        tracker_process.join()
        """

        if cmc_tracker.heartbeat_monitor == True:
            logger.info('Disabling heartbeat.')

            cmc_tracker.hb.disable_heartbeat()

        logger.info('Gathering active child processes.')

        active_processes = multiprocessing.active_children()

        logger.info('Terminating all child processes.')

        for proc in active_processes:
            logger.debug('Child Process: ' + str(proc))

            proc.terminate()

            logger.info('Joining terminated process to ensure clean exit.')

            proc.join()

        logger.info('Done.')

        #sys.exit()
