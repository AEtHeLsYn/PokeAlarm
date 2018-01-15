# Standard Library Imports
import logging
import requests

# 3rd Party Imports
import telepot

# Local Imports
from PokeAlarm.Alarms import Alarm
from Stickers import sticker_list
from PokeAlarm.Utilities import GenUtils as utils
from PokeAlarm.Utils import require_and_remove_key, get_image_url

log = logging.getLogger('Telegram')

# 2 lazy 2 type
try_sending = Alarm.try_sending
replace = Alarm.replace

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! ATTENTION! !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
#             ONLY EDIT THIS FILE IF YOU KNOW WHAT YOU ARE DOING!
# You DO NOT NEED to edit this file to customize messages! Please ONLY EDIT the
#     the 'alarms.json'. Failing to do so can cause other feature to break!
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! ATTENTION! !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


class TelegramAlarm(Alarm):

    class Alert(object):
        """ Class that defines the settings for each alert."""

        def __init__(self, kind, data, alert_defaults):
            default = TelegramAlarm._defaults[kind]
            default.update(alert_defaults)
            settings = Alarm.pop_type(data, kind, dict, {})

            self.bot_token = Alarm.pop_type(
                settings, 'bot_token', unicode, default['bot_token'])
            self.chat_id = Alarm.pop_type(
                settings, 'chat_id', unicode, default['chat_id'])
            self.sticker = Alarm.pop_type(
                settings, 'sticker', utils.parse_bool, default['sticker'])
            self.sticker_url = Alarm.pop_type(
                settings, 'sticker_url', unicode, default['sticker_url'])
            self.sticker_notify = Alarm.pop_type(
                settings, 'sticker_notify', utils.parse_bool,
                default['sticker_notify'])
            self.message = Alarm.pop_type(
                settings, 'message', unicode, default['message'])
            self.message_notify = Alarm.pop_type(
                settings, 'message_notify', utils.parse_bool,
                default['message_notify'])
            self.venue = Alarm.pop_type(
                settings, 'venue', utils.parse_bool, default['venue'])
            self.venue_notify = Alarm.pop_type(
                settings, 'venue_notify', utils.parse_bool,
                default['venue_notify'])
            self.map = Alarm.pop_type(
                settings, 'map', utils.parse_bool, default['map'])
            self.map_notification = Alarm.pop_type(
                settings, 'map_notify', utils.parse_bool,
                default['map_notify'])
            self.max_attempts = Alarm.pop_type(
                settings, 'max_attempts', int, default['max_attempts'])

            # Reject leftover parameters
            for key in settings:
                raise ValueError(
                    "'{}' is not a recognized parameter for the Alert"
                    " level in a Telegram Alarm".format(key))

    _defaults = {  # No touchy!!! Edit alarms.json!
        'monsters': {
            'message': "*A wild <mon_name> has appeared!*\n"
                       "Available until <24h_time> (<time_left>).",
            'sticker_url': get_image_url(
                "monsters/<mon_id_3>_<form_id_3>.webp")
        },
        'stops': {
            'message': "*Someone has placed a lure on a Pokestop!*\n"
                       "Lure will expire at <24h_time> (<time_left>).",
            'sticker_url': get_image_url("stop/ready.webp")
        },
        'gyms': {
            'message': "*A Team <old_team> gym has fallen!*\n"
                       "It is now controlled by <new_team>.",
            'sticker_url': get_image_url("gyms/<new_team_id>.webp"),
        },
        'eggs': {
            'message': "*A level <egg_lvl> raid is incoming!*\n"
                       "The egg will hatch <24h_hatch_time> "
                       "(<hatch_time_left>).",
            'sticker_url': get_image_url("eggs/<egg_lvl>.webp")
        },
        'raids': {
            'message': "*A raid is available against <mon_name>!*\n"
                       "The raid is available until <24h_raid_end> "
                       "(<raid_time_left>).",
            'sticker_url': get_image_url("monsters/<mon_id_3>_000.webp")
        }
    }

    # Gather settings and create alarm
    def __init__(self, settings):
        # Required Parameters
        self._bot_token = require_and_remove_key(
            'bot_token', settings, "'Telegram' type alarms.")
        self._chat_id = require_and_remove_key(
            'chat_id', settings, "'Telegram' type alarms.")

        self._startup_message = self.pop_type(
            settings, 'startup_message', utils.parse_bool, True)

        # Optional Alert Parameters
        alert_defaults = {
            'bot_token': self._bot_token,
            'chat_id': self._chat_id,
            'sticker': self.pop_type(
                settings, 'sticker', utils.parse_bool, True),
            'sticker_notify': self.pop_type(
                settings, 'sticker_notify', utils.parse_bool, False),
            'message_notify': self.pop_type(
                settings, 'message_notify', utils.parse_bool, True),
            'venue': self.pop_type(
                settings, 'venue', utils.parse_bool, False),
            'venue_notify': self.pop_type(
                settings, 'venue_notify', utils.parse_bool, True),
            'map': self.pop_type(
                settings, 'map', utils.parse_bool, True),
            'map_notify': self.pop_type(
                settings, 'map_notify', utils.parse_bool, False),
            'max_attempts': self.pop_type(
                settings, 'max_attempts', int, 3),
        }

        # Alert Settings
        self._mon_alert = TelegramAlarm.Alert(
            'monsters', settings, alert_defaults)
        self._stop_alert = TelegramAlarm.Alert(
            'stops', settings, alert_defaults)
        self._gym_alert = TelegramAlarm.Alert(
            'gyms', settings, alert_defaults)
        self._egg_alert = TelegramAlarm.Alert(
            'eggs', settings, alert_defaults)
        self._raid_alert = TelegramAlarm.Alert(
            'raids', settings, alert_defaults)

        # Reject leftover parameters
        for key in settings:
            raise ValueError("'{}' is not a recognized parameter for the Alarm"
                             " level in a Telegram Alarm".format(key))

        log.info("Telegram Alarm has been created!")

    # (Re)establishes Telegram connection
    def connect(self):
        pass

    # Sends a start up message on Telegram
    def startup_message(self):
        if self._startup_message:
            self.send_message_new(
                self._bot_token, self._chat_id, "PokeAlarm activated!")
            log.info("Startup message sent!")

    # Send Alert to Telegram
    def send_alert(self, alert, info, sticker_id=None):
        if sticker_id:
            self.send_sticker(alert['chat_id'], sticker_id)

        if alert['venue']:
            self.send_venue(alert, info)
        else:
            text = '<b>' + replace(alert['title'], info)\
                   + '</b> \n' + replace(alert['body'], info)
            self.send_message(alert['chat_id'], text)

        if alert['location']:
            self.send_location(alert, info)

    def generic_alert(self, alert, dts):
        bot_token = replace(alert.bot_token, dts)
        chat_id = replace(alert.chat_id, dts)
        message = replace(alert.message, dts)
        lat, lng = dts['lat'], dts['lng']
        max_attempts = alert.max_attempts
        sticker_url = replace(alert.sticker_url, dts)
        log.debug(sticker_url)
        # Send Sticker
        if alert.sticker and sticker_url is not None:
            self.send_sticker_new(bot_token, chat_id, sticker_url, max_attempts)

        # Send Venue
        if alert.venue:
            self.send_venue_new(bot_token, chat_id, lat, lng, max_attempts)
            return  # Don't send message or map

        # Send Message
        self.send_message_new(bot_token, chat_id, replace(message, dts))

        # Send Map
        if alert.map:
            self.send_location_new(bot_token, chat_id, lat, lng, max_attempts)

    # Trigger an alert based on Pokemon info
    def pokemon_alert(self, mon_dts):
        self.generic_alert(self._mon_alert, mon_dts)

    # Trigger an alert based on Pokestop info
    def pokestop_alert(self, stop_dts):
        self.generic_alert(self._stop_alert, stop_dts)

    # Trigger an alert based on Pokestop info
    def gym_alert(self, gym_dts):
        self.generic_alert(self._gym_alert, gym_dts)

    # Trigger an alert when a raid egg has spawned (UPCOMING raid event)
    def raid_egg_alert(self, egg_dts):
        self.generic_alert(self._egg_alert, egg_dts)

    # Trigger an alert based on Raid info
    def raid_alert(self, raid_dts):
        self.generic_alert(self._raid_alert, raid_dts)

    # Send a message to telegram
    def send_message(self, chat_id, text):
        args = {
            'chat_id': chat_id,
            'text': text,
            'disable_web_page_preview': 'False',
            'disable_notification': 'False',
            'parse_mode': 'HTML'
        }
        try_sending(log, self.connect,
                    "Telegram", self.__client.sendMessage, args)

    # Send a sticker to telegram
    def send_sticker(self, chat_id, sticker_id):
        args = {
            'chat_id': chat_id,
            'sticker': sticker_id,
            'disable_notification': 'True'
        }
        try_sending(log, self.connect, 'Telegram (sticker)',
                    self.__client.sendSticker, args)

    # Send a venue message to telegram
    def send_venue(self, alert, info):
        args = {
            'chat_id': alert['chat_id'],
            'latitude': info['lat'],
            'longitude': info['lng'],
            'title': replace(alert['title'], info),
            'address': replace(alert['body'], info),
            'disable_notification': 'False'
        }
        try_sending(log, self.connect, "Telegram (venue)",
                    self.__client.sendVenue, args)

    # Send a location message to telegram
    def send_location(self, alert, info):
        args = {
            'chat_id': alert['chat_id'],
            'latitude': info['lat'],
            'longitude': info['lng'],
            'disable_notification': "{}".format(
                alert['disable_map_notification'])
        }
        try_sending(log, self.connect, "Telegram (location)",
                    self.__client.sendLocation, args)

    def send_sticker_new(self, bot_token, chat_id, sticker_url,
                         max_attempts=3, notify=False):
        args = {
            'url':
                "https://api.telegram.org/bot{}/sendSticker".format(bot_token),
            'payload': {
                'chat_id': chat_id,
                'sticker': sticker_url,
                'disable_notification': not notify
            }
        }
        try_sending(
            log, self.connect, "Telegram (STKR)", self.send_webhook, args,
            max_attempts)

    def send_message_new(self, bot_token, chat_id, message,
                         max_attempts=3, notify=True):
        args = {
            'url':
                "https://api.telegram.org/bot{}/sendMessage".format(bot_token),
            'payload': {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': False,
                'disable_notification': not notify
            }
        }
        try_sending(
            log, self.connect, "Telegram (MSG)", self.send_webhook, args, 
            max_attempts)

    def send_location_new(self, bot_token, chat_id, lat, lng,
                          max_attempts=3, notify=False):
        args = {
            'url': "https://api.telegram.org/bot{}/sendLocation".format(
                    bot_token),
            'payload': {
                'chat_id': chat_id,
                'latitude': lat,
                'longitude': lng,
                'disable_notification': not notify
            }
        }
        try_sending(
            log, self.connect, "Telegram (LOC)", self.send_webhook, args,
            max_attempts)

    def send_venue_new(self, bot_token, chat_id, lat, lng, max_attempts):
        args = {
            'url': "https://api.telegram.org/bot{}/sendVenue".format(
                bot_token),
            'payload': {
                'chat_id': chat_id,
                'latitude': lat,
                'longitude': lng,
                'disable_notification': False
            }
        }
        try_sending(
            log, self.connect, "Telegram (VEN)", self.send_webhook, args,
            max_attempts)

    # Send a payload to the webhook url
    def send_webhook(self, url, payload):
        log.debug(url)
        log.debug(payload)
        resp = requests.post(url, json=payload, timeout=5)
        if resp.ok is True:
            log.debug("Notification successful (returned {})".format(
                resp.status_code))
        else:
            log.debug("Telegram response was {}".format(resp.content))
            raise requests.exceptions.RequestException(
                "Response received {}, webhook not accepted.".format(
                    resp.status_code))
