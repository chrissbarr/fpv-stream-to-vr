#!/usr/bin/env python

import sys
import argparse

display_width = 1920
display_height = 1080

# Set output_port to an output name recognized by xrandr to override where
# we output the video - if output_port is None we'll look for
# the first monitor that is 1920x1080.  If not None, we'll ignore
# display_width and display_height and assume the resolution reported by
# xrandr with half of the screen area for each eye.
#output_port = 'HDMI1'
output_port = None


#dump_pipeline = 'orig. ! queue ! filesink location=capture.h264'
dump_pipeline = ''

DUAL_CAMERAS = True #if false only one camera is used, rendered twice

parser = argparse.ArgumentParser()
parser.add_argument("-s","--single", help="duplicate first camera feed, do not use second")
parser.add_argument("-sw","--swap", help="swap camera order")
args = parser.parse_args()
if args.single:
    DUAL_CAMERAS = False
else:
    DUAL_CAMERAS = True

port1 = '5001'
port2 = '5000'

draw_info_text = False

cam1text = "Camera 1: ...x... @..FPS"
cam2text = "Camera 2: ...x... @..FPS"

if args.swap:
    port1, port2 = port2, port1

src = 'udpsrc port='
input_pipeline = ' ! application/x-rtp, payload=96 ! rtph264depay ! avdec_h264'
input_cam1 = src + port1 + input_pipeline
input_cam2 = src + port2 + input_pipeline


default_scale = 100

import subprocess, re, gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, Gtk, Gdk

# Needed for window.get_xid(), xvimagesink.set_window_handle(), respectively:
from gi.repository import GdkX11, GstVideo

class GTK_Main(object):
    def __init__(self, w, h, x, y):
        window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        window.set_decorated(False)
        window.move(x, y)
        window.resize(w, h)
        window.fullscreen()
        window.connect("destroy", Gtk.main_quit, "WM destroy")
        window.connect("key_press_event", self.on_key_press)
        self.gst_window = Gtk.DrawingArea()
        window.add(self.gst_window)
        window.show_all()



        # TODO: disable screen saver and autosuspend (gsettings?)

        self.per_eye_w = w / 2
        self.per_eye_h = h
        self.video_scale = default_scale
        self.left_x = 0
        self.right_x = w / 2
        self.offset_x = 0
        self.offset_y = 0

        self.caps = Gst.Caps.new_empty_simple('video/x-raw')
        self.caps2 = Gst.Caps.new_empty_simple('video/x-raw')

        # Set up the gstreamer pipeline
        if DUAL_CAMERAS:
            sys.stderr.write('Running in dual camera mode\n')
            self.player = Gst.parse_launch(input_cam1 + ' ! ' +
                    'tee name=orig ! ' +
                    'videoscale ! ' +
                    'capsfilter name=caps ! ' +
                    'tee name=tee ! ' +
                    'textoverlay name=overlay2 text=Cam2 ! ' +
                    'queue ! ' +
                    'videomixer name=mixer background=black ! ' +
                    'video/x-raw,width=' + str(w) + ',height=' + str(h) + ' ! ' +
                    'xvimagesink double-buffer=false sync=false ' +
                    input_cam2 + ' ! ' +
                    'videoscale ! ' +
                    'capsfilter name=caps2 ! ' +
                    'textoverlay name=overlay1 text=Cam1 ! ' +
                    'queue ! ' +
                    'mixer. ')
            self.mixer = self.player.get_by_name('mixer')
            self.caps_elem = self.player.get_by_name('caps')
            self.caps_elem2 = self.player.get_by_name('caps2')	

        else:
            sys.stderr.write('Running in single camera mode\n')
            if args.single == '1':
                input_cam = input_cam1
            else:
                input_cam = input_cam2

            self.player = Gst.parse_launch(input_cam + ' ! ' +
                    'tee name=orig ! ' +
                    'videoscale ! ' +
                    'capsfilter name=caps ! ' +
                    'tee name=tee ! ' +
                    'textoverlay name=overlay1 text=Cam1 ! ' +
                    'queue ! ' +
                    'videomixer name=mixer background=black ! ' +
                    'video/x-raw,width=' + str(w) + ',height=' + str(h) + ' ! ' +
                    'xvimagesink double-buffer=false sync=false ' +
                    'tee. ! ' +
                    'textoverlay name=overlay2 text=Cam2 ! ' +
                    'queue ! ' +
                    'mixer. ' +
                    dump_pipeline)
            self.mixer = self.player.get_by_name('mixer')
            self.caps_elem = self.player.get_by_name('caps')

        self.overlay1 = self.player.get_by_name('overlay1')
        self.overlay2 = self.player.get_by_name('overlay2')

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)

        self.geom_update()

        self.player.set_state(Gst.State.PLAYING)
        sys.stderr.write('Gstreamer pipeline created and started\n')

    def geom_update(self):
        video_w = self.per_eye_w * self.video_scale / 100
        video_h = self.per_eye_h * self.video_scale / 100
        h_pad = (self.per_eye_w - video_w) / 2
        v_pad = (self.per_eye_h - video_h) / 2

        # TODO: reimplement x offset in a way that one eye's video never
        # shows in the other eye's half of the screen

        sink0 = self.mixer.get_static_pad('sink_0')
        sink1 = self.mixer.get_static_pad('sink_1')

        sink0.set_property('xpos', self.left_x + self.offset_x + h_pad)
        sink1.set_property('xpos', self.right_x + self.offset_x + h_pad)
        sink0.set_property('ypos', self.offset_y + v_pad)
        sink1.set_property('ypos', -self.offset_y + v_pad)

        self.caps_elem.set_property('caps', None) # Release lock for a moment
        self.caps.set_value('width', video_w)
        self.caps.set_value('height', video_h)
        self.caps_elem.set_property('caps', self.caps)
        if draw_info_text:
            self.overlay1.set_property('text',"Camera1: " + str(video_w))
            self.overlay2.set_property('text',cam2text)

        if DUAL_CAMERAS:
            self.caps_elem2.set_property('caps', None) # Release lock for a moment
            self.caps2.set_value('width', video_w)
            self.caps2.set_value('height', video_h)
            self.caps_elem2.set_property('caps', self.caps2)

    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            sys.stderr.write('Stream ended\n')
            Gtk.main_quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            sys.stderr.write('Error: ' + str(err) + '\n' + str(debug))
            Gtk.main_quit()

    def on_sync_message(self, bus, message):
        if message.get_structure().get_name() == 'prepare-window-handle':
            imagesink = message.src
            Gdk.threads_enter()
            imagesink.set_window_handle(
                    self.gst_window.get_property('window').get_xid())
            Gdk.threads_leave()
            sys.stderr.write('Gstreamer synced\n')

    def on_key_press(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)

        if keyname in [ 'q', 'Q', 'Escape' ]:
            Gtk.main_quit()
        elif keyname == 'Left':
            self.offset_x -= 4
            self.geom_update()
        elif keyname == 'Right':
            self.offset_x += 4
            self.geom_update()
        elif keyname == 'Up':
            self.offset_y -= 4
            self.geom_update()
        elif keyname == 'Down':
            self.offset_y += 4
            self.geom_update()
        elif keyname == '1' and self.video_scale > 20:
            self.video_scale -= 5
            self.geom_update()
        elif keyname == '2' and self.video_scale < 120:
            self.video_scale += 5
            self.geom_update()
        elif keyname == 'bracketleft':
            self.left_x -= 1
            self.right_x += 1
            self.geom_update()
        elif keyname == 'bracketright':
            self.left_x += 1
            self.right_x -= 1
            self.geom_update()
        elif keyname in [ 'r', 'R' ]:
            self.offset_x = 0
            self.offset_y = 0
            self.video_scale = default_scale
            self.left_x = 0
            self.right_x = w / 2
            self.geom_update()

# Find the selected screen using xrandr directly
#
# Should either use one of the libxrandr bindings libraries but none is popular
# enough to be packaged by distributions, or use gtk.gdk:
# scr = gtk.gdk.screen_get_default()
# n = scr.get_n_monitors()
# [ scr.get_monitor_plug_name(i) for i in range(0, n) ]
# [ scr.get_monitor_geometry(i) for i in range(0, n) ]
# also subscribe to scr signal "monitor-changed"
#
# We'd still need to use xrandr to actually rotate the screen, it seems.

p = subprocess.Popen([ 'xrandr', '-q' ], stdout=subprocess.PIPE)
output = p.communicate()[0]
monitor_line = None
resolution_str1 = ' ' + str(display_width) + 'x' + str(display_height
) + '+'
resolution_str2 = ' ' + str(display_height
) + 'x' + str(display_width) + '+'

for line in output.split('\n'):
    if output_port and line.startswith(output_port):
        monitor_line = line
        break
    if not output_port and (resolution_str1 in line or resolution_str2 in line):
        monitor_line = line
        break

if not monitor_line:
    if output_port:
        sys.stderr.write(outout_port + ' not found\n')
    else:
        sys.stderr.write('No screen found with the right resolution\n')
    sys.exit(-1)

if not output_port:
    output_port = monitor_line.split()[0]
if 'disconnected' in monitor_line:
    sys.stderr.write(output_port + ' seems to be disconnected\n')
    sys.exit(-1)

match = re.search(r'\b([0-9]+)x([0-9]+)\+([0-9]+)\+([0-9]+)\b', monitor_line)
w, h, x, y = [ int(n) for n in match.groups() ]

sys.stderr.write('Using ' + output_port + ' for output\n')

# If screen seems to be in vertical/portrait mode (height > width), rotate it
if h > w:
    sys.stderr.write('Setting --rotate left\n')
    subprocess.check_call([ 'xrandr',
            '--output', output_port,
            '--rotate', 'left' ])
    w, h = h, w

GObject.threads_init()
Gst.init(None)
GTK_Main(w, h, x, y)
Gtk.main()
