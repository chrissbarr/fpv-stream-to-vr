receiveStream.py
=========
Forked and modified from https://github.com/balrog-kun/fpv-stream-to-vr

A simple python script to open and display dual video feeds to an
Oculus Rift DK2.

Input can be either single or dual camera. In single camera mode, the camera will be duplicated and displayed for each eye.  This works great for wide-angle
/ fish-eye lens cameras used for FPV but won't look good for a narrow-angle
camera -- the image will look deformed.

    $ ./receiveStream.py [ options ... ]

-s --single enables single camera mode

-sw --swap swaps the camera feeds - in dual mode this will swap the position of each feed, in single camera mode it will select which feed is used.

Keys
====

When the script runs the following keys can be used:

* Esc or 'q': exit.

* Left / right arrows: Move video slightly left/right, useful if analog
  signal has a black band on one side.

* Up / down arrows: Adjust vertical offset between left/right eyes. Can be used to compensate for slight camera vertical alignment issues.


* 1 / 2:  Increase / Decrease video scale. 


* '[' / ']': slightly increase/decrease left-to-right-eye video frame
  distance, basically move the virtual screen closer / farther.

Ideas
=====

* Basic text rendering is working, but so far only static. Dynamic text would be interesting.

Dependencies
============

Gstreamer-1.0 or later is required, gobject and GTK libraries and their
python bindings.  dbus-python is optional: it allows the script to inhibit
the Gnome screen saver while streaming video.  Installing the gstreamer
python bindings should in theory pull everything else in as dependency
(`apt-get install python-gst-1.0`).

Problems
========

Sometimes gstreamer will pop an internal error of some kind or a cryptic
X11 error on start.  The script can be retried and should eventually run.
