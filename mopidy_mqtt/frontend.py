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
        super(MQTTFrontend, self).__init__()
        self.core = core
        self.client = mqtt.Client()
        self.client.on_message = self.mqtt_on_message
        self.client.on_connect = self.mqtt_on_connect
        self.config = config['mqtthook']
        self.topic = self.config['topic']
        self.title = ""
        self.uri = ""

    def on_start(self):
        host = self.config['mqtthost']
        port = self.config['mqttport']
        self.client.connect_async(host, port)
        self.client.loop_start()

    def on_stop(self):
        self.client.disconnect()
        self.client.loop_stop()
 
    def makeTopic(self, *parts):
        return "/".join([self.topic] + list(parts))

    def mqtt_on_connect(self, client, userdata, flags, rc):
        logger.debug("Connected with result code " + str(rc))
        self.client.subscribe(self.makeTopic(self.SET_TOPIC, 'state'), qos=1)
        self.client.subscribe(self.makeTopic(self.SET_TOPIC, 'next'), qos=1)
        self.client.subscribe(self.makeTopic(self.SET_TOPIC, 'previous'), qos=1)
        self.client.subscribe(self.makeTopic(self.SET_TOPIC, 'uri'), qos=1)
        self.client.subscribe(self.makeTopic(self.SET_TOPIC, 'playlist'), qos=1)
        self.client.subscribe(self.makeTopic(self.SET_TOPIC, 'volume'), qos=1)
        self.client.subscribe(self.makeTopic(self.REQ_TOPIC, '#'), qos=1)

    def _resetTracklist(self):
        self.core.playback.stop()
        self.core.tracklist.clear()
        self.core.tracklist.set_consume(False)
        self.core.tracklist.set_random(False)
        self.core.tracklist.set_repeat(True)
        self.core.tracklist.set_single(False)

    def mqtt_on_message(self, client, obj, msg):
        logger.info("received message on " + msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
        if msg.topic.startswith(self.makeTopic(self.REQ_TOPIC)):
            if msg.topic.endswith('state'):
                self.send('state', str(self.core.playback.get_state().get()))
            elif msg.topic.endswith('title'):
                self.send('nowplaying', self.title)
            elif msg.topic.endswith('uri'):
                self.send('uri', self.uri)
            elif msg.topic.endswith('volume'):
                self.send('volume', str(self.core.mixer.get_volume().get()))
        elif msg.topic.endswith('state'):
            if msg.payload == "playing":
                self.core.playback.play()
            elif msg.payload == "stopped":
                self.core.playback.stop()
            elif msg.payload == "paused":
                self.core.playback.pause()
        elif msg.topic.endswith('uri'):
            self._resetTracklist()
            self.core.tracklist.add(uri=str(msg.payload))
            self.core.playback.play()
        elif msg.topic.endswith('playlist'):
            self._resetTracklist()
            playlist = self.core.playlists.lookup(msg.payload).get()
            if playlist is not None:
               self.core.tracklist.add(uris=[track.uri for track in playlist.tracks])
            self.core.playback.play()
        elif msg.topic.endswith('volume'):
            self.core.mixer.set_volume(int(round(float(msg.payload))))
        elif msg.topic.endswith('next'):
            self.core.playback.next()
        elif msg.topic.endswith('previous'):
            self.core.playback.previous()
    
    def send(self, topic, data):
        try:
            logger.debug('Sending ')
            topic = self.makeTopic(self.GET_TOPIC, topic)
            self.client.publish(topic, data if data is not None else "")
        except Exception as e:
            logger.warning('Unable to send')
        else:
            logger.debug('OK ')
    
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

