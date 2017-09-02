# future imports
from __future__ import absolute_import
from __future__ import unicode_literals

# stdlib imports
import logging

from mopidy import core

import paho.mqtt.client as mqtt

# third-party imports
import pykka

logger = logging.getLogger(__name__)


class MQTTFrontend(pykka.ThreadingActor, core.CoreListener):
    SET_TOPIC = 'set'
    GET_TOPIC = 'get'
    REQ_TOPIC = 'req'

    def __init__(self, config, core):
        self.core = core
        self.client = mqtt.Client()
        self.client.on_message = self.mqtt_on_message
        self.config = config['mqtthook']
        host = self.config['mqtthost']
        port = self.config['mqttport']
        self.topic = self.config['topic']
        self.client.connect(host, port, 60)
        self.client.subscribe(self.makeTopic(self.SET_TOPIC, 'state'), qos=1)
        self.client.subscribe(self.makeTopic(self.SET_TOPIC, 'uri'), qos=1)
        self.client.subscribe(self.makeTopic(self.SET_TOPIC, 'volume'), qos=1)
        self.client.subscribe(self.makeTopic(self.REQ_TOPIC, '#'), qos=1)
        self.client.loop_start()
        self.title = ""
        self.uri = ""
        super(MQTTFrontend, self).__init__()
        
    def makeTopic(self, *parts):
        return "/".join([self.topic] + list(parts))

    def mqtt_on_message(self, mqttc, obj, msg):
        logger.info("received message on " + msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
        if msg.topic.startswith(self.makeTopic(self.REQ_TOPIC)):
            if msg.topic.endswith('state'):
                self.send('state', str(self.core.playback.get_state()))
            elif msg.topic.endswith('title'):
                self.send('nowplaying', self.title)
            elif msg.topic.endswith('uri'):
                self.send('uri', self.uri)
            elif msg.topic.endswith('volume'):
                self.send('volume', str(self.core.mixer.get_volume()))
        elif msg.topic.endswith('state'):
            if msg.payload == "playing":
                self.core.playback.play()
            elif msg.payload == "stopped":
                self.core.playback.stop()
            elif msg.payload == "paused":
                self.core.playback.pause()
        elif msg.topic.endswith('uri'):
            self.core.tracklist.clear()
            self.core.tracklist.add(None, None, str(msg.payload), None)
            self.core.playback.play()
        elif msg.topic.endswith('volume'):
            self.core.mixer.set_volume(int(round(float(msg.payload))))
    
    def send(self, topic, data):
        try:
            logger.info('Sending ')
            topic = self.makeTopic(self.GET_TOPIC, topic)
            self.client.publish(topic, data if data is not None else "")
        except Exception as e:
            logger.warning('Unable to send')
        else:
            logger.info('OK ')
    
    def stream_title_changed(self, title):
        self.title = title
        self.send('nowplaying', title)

    def playback_state_changed(self, old_state, new_state):
        self.send("state", new_state)
        
    def track_playback_started(self, tl_track):
        track = tl_track.track
        artists = ', '.join(sorted([a.name for a in track.artists]))
        self.title = " - ".join([element for element in [artists, track.name] if element])
        self.send("nowplaying", self.title)
        self.uri = track.uri
        self.send("uri", track.uri)
        try:
            album = track.album
            albumImage = next(iter(album.images))
            self.send("image", image)
        except:
            logger.debug("no image")

    def volume_changed(self, volume):
        self.send("volume", str(volume))

