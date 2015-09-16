# Copyright (c) 2014-2015 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GLib, Gio, GdkPixbuf

from gettext import gettext as _

from threading import Thread
from cgi import escape

from lollypop.define import Lp
from lollypop import utils


class InfosPopover(Gtk.Popover):
    """
        Popover with artist informations
    """

    def should_be_shown():
        """
            True if we can show popover
        """
        return Lp.lastfm is not None or\
            ArtistInfos.Wikipedia is not None or\
            ArtistInfos.WebKit is not None

    def __init__(self, artist, track_id=None):
        """
            Init popover
            @param artist as string
            @param track id as int
        """
        Gtk.Popover.__init__(self)
        self._infos = ArtistInfos(artist, track_id)
        self._infos.show()
        self.add(self._infos)

    def do_show(self):
        """
            Resize popover and set signals callback
        """
        size_setting = Lp.settings.get_value('window-size')
        if isinstance(size_setting[1], int):
            self.set_size_request(700, size_setting[1]*0.7)
        else:
            self.set_size_request(700, 400)
        Gtk.Popover.do_show(self)

    def do_get_preferred_width(self):
        """
            Preferred width
        """
        return (700, 700)

class ArtistContent(Gtk.Stack):
    """
        Widget showing artist image and bio
    """

    def __init__(self):
        """
            Init artist content
        """
        Gtk.Stack.__init__(self)
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Lollypop/ArtistContent.ui')
        self._content = builder.get_object('content')
        self._image = builder.get_object('image')
        self.add_named(builder.get_object('widget'), 'widget')
        self.add_named(builder.get_object('notfound'), 'notfound')
        self.add_named(builder.get_object('spinner'), 'spinner')
        self.set_visible_child_name('spinner')

    def set_content(self, content, stream):
        """
            Set content
            @param content as string
            @param stream as Gio.MemoryInputStream
        """
        if content:
            self._content.set_text(content)
            if stream is not None:
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream,
                                                                   200,
                                                                   -1,
                                                                   True,
                                                                   None)
                self._image.set_from_pixbuf(pixbuf)
                del pixbuf
            self.set_visible_child_name('widget')
        else:
            self.set_visible_child_name('notfound')
        

class ArtistInfos(Gtk.Bin):
    """
        Artist informations from lastfm
    """

    try:
        from lollypop.wikipedia import Wikipedia
    except Exception as e:
        print(e)
        print(_("Advanced artist informations disabled"))
        print("$ sudo pip3 install wikipedia")
        Wikipedia = None

    try:
        from gi.repository import WebKit
    except Exception as e:
        print(e)
        print(_("Wikia support disabled"))
        WebKit = None

    def __init__(self, artist, track_id):
        """
            Init artist infos
            @param artist as string
            @param track_id as int
        """
        Gtk.Bin.__init__(self)
        self._liked = True  # Liked track or not?
        self._artist = artist
        self._track_id = track_id

        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Lollypop/ArtistInfos.ui')
        builder.connect_signals(self)

        self._stack = builder.get_object('stack')
        self._lastfm = builder.get_object('lastfm')
        self._wikipedia = builder.get_object('wikipedia')
        self._wikia = builder.get_object('wikia')
        self._stack.set_visible_child_name('wikipedia')
        self.add(builder.get_object('widget'))

        if self.Wikipedia is None:
            builder.get_object('wikipedia').destroy()
        if Lp.lastfm is None:
            builder.get_object('lastfm').destroy()
        if self.WebKit is None:
            builder.get_object('wikia').destroy()

#######################
# PRIVATE             #
#######################
    def _on_map_lastfm(self, widget):
        """
            Load on map
        """
        content_widget = ArtistContent()
        content_widget.show()
        child = widget.get_child()
        if child is not None:
            child.destroy()
        widget.add(content_widget)
        t = Thread(target=self._populate_lastfm, args=(content_widget,))
        t.daemon = True
        t.start()

    def _populate_lastfm(self, widget):
        """
            Populate content with lastfm informations
            @param widget as Gtk.ScrolledWindow
            @thread safe
        """
        url = None
        image_url = None
        content = None
        (url, image_url, content) = Lp.lastfm.get_artist_infos(self._artist)
        self._populate(url, image_url, content, widget)

    def _on_map_wikipedia(self, widget):
        """
            Load on map
        """
        content_widget = ArtistContent()
        content_widget.show()
        child = widget.get_child()
        if child is not None:
            child.destroy()
        widget.add(content_widget)
        t = Thread(target=self._populate_wikipedia, args=(content_widget,))
        t.daemon = True
        t.start()

    def _populate_wikipedia(self, widget):
        """
            Populate content with wikipedia informations
            @param widget as Gtk.ScrolledWindow
            @thread safe
        """
        url = None
        image_url = None
        content = None
        (url, image_url, content) = self.Wikipedia().get_artist_infos(
                                                                self._artist)
        self._populate(url, image_url, content, widget)

    def _on_map_wikia(self, widget):
        """
            Load on map
        """
        child = widget.get_child()
        if child is not None:
            child.destroy()
        
        settings = self.WebKit.WebSettings()
        settings.set_property('enable-private-browsing', True)
        settings.set_property('enable-plugins', False)
        settings.set_property('user-agent',
                              "Mozilla/5.0 (Linux; Ubuntu 14.04;"
                              " BlackBerry) AppleWebKit/537.36 Chromium"
                              "/35.0.1870.2 Mobile Safari/537.36")
        view = self.WebKit.WebView()
        view.set_settings(settings)
        view.show()
        view.connect('navigation-policy-decision-requested',
                     self._on_navigation_policy)
        widget.add(view)
        artist = Lp.player.current_track.album_artist.replace(' ', '_')
        title = Lp.player.current_track.title.replace(' ', '_')
        wikia_url = "http://lyrics.wikia.com/wiki/%s:%s" % (artist,
                                                                  title)
        view.load_uri(wikia_url)
        self._stack.set_visible_child_name('wikia')

    def _populate(self, url, image_url, content, widget):
        """
            populate widget with content
            @param url as string
            @param image url as string
            @param content as string
            @param widget as Gtk.ScrolledWindow
            @thread safe
        """
        stream = None
        try:
            if image_url is not None:
                f = Gio.File.new_for_uri(image_url)
                (status, data, tag) = f.load_contents()
                if status:
                    stream = Gio.MemoryInputStream.new_from_data(data,
                                                                 None)
        except Exception as e:
            print("PopArtistInfos::_populate: %s" % e)
        GLib.idle_add(self._set_content, content, url, stream, widget)

    def _set_content(self, content, url, stream, widget):
        """
            Set content on view
            @param content as str
            @param url as str
            @param stream as Gio.MemoryInputStream
            @param widget as Gtk.ScrolledWindow
        """
        widget.set_content(content, stream)

    def _show_love_btn(self):
        """
            Show love button
        """
        sql = Lp.db.get_cursor()
        if self._track_id is not None:
            if utils.is_loved(self._track_id, sql=sql):
                self._liked = False
                self._love_btn.set_tooltip_text(_("I do not love"))
                self._love_btn.get_image().set_opacity(1)
        self._love_btn.show()
        sql.close()

    def _love_track(self):
        """
            Love a track
            @thread safe
        """
        Lp.playlists.add(Lp.playlists._LOVED)

        # Add track to Liked tracks
        sql = Lp.db.get_cursor()
        if self._track_id is not None:
            utils.set_loved(self._track_id, True, sql=sql)
        sql.close()

    def _unlove_track(self):
        """
            Unlove a track
        """
        Lp.playlists.add(Lp.playlists._LOVED)

        # Del track from Liked tracks
        sql = Lp.db.get_cursor()
        if self._track_id is not None:
            utils.set_loved(self._track_id, False, sql=sql)
        sql.close()

    def _on_love_btn_clicked(self, btn):
        """
            Love a track
            @param btn as Gtk.Button
        """
        if self._liked:
            self._love_track()
            self._liked = False
            btn.get_image().set_opacity(1)
            btn.set_tooltip_text(_("I do not love"))
        else:
            self._unlove_track()
            btn.get_image().set_opacity(0.2)
            self._liked = True

    def _on_view_clicked(self, btn):
        """
            Next view
            @param btn as Gtk.Button
        """
        self._view_btn.set_sensitive(False)
        if self.WebKit is not None:
            self._lyrics_btn.show()
        self._url_btn.set_label('')
        self._lyrics_btn.set_sensitive(True)
        self._stack.set_visible_child(self._spinner)
        self.populate()

    def _on_lyrics_clicked(self, btn):
        """
            Show lyrics from wikia with webkit
            @param btn as Gtk.Button, if None, do not show view button
        """
        self._set_label()
        

    def _on_navigation_policy(self, view, frame, request,
                              navigation_action, policy_decision):
        """
            Disallow navigation, launch in external browser
            @param view as WebKit.WebView
            @param frame as WebKit.WebFrame
            @param request as WebKit.NetworkRequest
            @param navigation_action as WebKit.WebNavigationAction
            @param policy_decision as WebKit.WebPolicyDecision
            @return bool
        """
        if navigation_action.get_button() == -1:
            return False
        else:
            GLib.spawn_command_line_async("xdg-open \"%s\"" %
                                          request.get_uri())
            return True
