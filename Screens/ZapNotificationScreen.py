import os
from ..common import *
from ..globals import global_sports_monitor

from .SimplePlayer import SimplePlayer
class ZapNotificationScreen(Screen):
    def __init__(self, session, match_name, league, h_logo, a_logo, sref, timeout_seconds=30):
        # Calculate Layout similar to GoalToast
        width = 800
        height = 300
        
        # Colors
        c_bg = "#051030"
        c_title = "#00FF85"
        c_text = "#FFFFFF"
        c_dim = "#AAAAAA"
        
        self.sref = sref
        self.timeout_val = timeout_seconds
        
        self.skin = (
            '<screen position="center,center" size="{w},{h}" title="Zap Notification" flags="wfNoBorder" backgroundColor="#00000000">'
            '<eLabel position="0,0" size="{w},{h}" backgroundColor="{bg}" zPosition="0" />'
            '<eLabel position="0,0" size="{w},5" backgroundColor="{title_c}" zPosition="1" />'
            '<widget name="title" position="20,15" size="{w40},40" font="Regular;28" foregroundColor="{title_c}" backgroundColor="{bg}" valign="center" halign="center" transparent="1" zPosition="2" />'
            '<widget name="h_logo" position="50,80" size="100,100" alphatest="blend" zPosition="2" />'
            '<widget name="a_logo" position="{w150},80" size="100,100" alphatest="blend" zPosition="2" />'
            '<widget name="match_name" position="160,80" size="{w320},100" font="Regular;32" foregroundColor="{text_c}" backgroundColor="{bg}" valign="center" halign="center" transparent="1" zPosition="2" />'
            '<widget name="prompt" position="20,200" size="{w40},40" font="Regular;24" foregroundColor="{dim_c}" backgroundColor="{bg}" valign="center" halign="center" transparent="1" zPosition="2" />'
            '<eLabel position="20,260" size="20,20" backgroundColor="#00FF00" zPosition="2" />'
            '<widget name="key_ok" position="50,260" size="150,25" font="Regular;20" foregroundColor="{text_c}" backgroundColor="{bg}" valign="center" halign="left" transparent="1" zPosition="2" />'
            '<eLabel position="{w140},260" size="20,20" backgroundColor="#FF0000" zPosition="2" />'
            '<widget name="key_cancel" position="{w110},260" size="100,25" font="Regular;20" foregroundColor="{text_c}" backgroundColor="{bg}" valign="center" halign="left" transparent="1" zPosition="2" />'
            '<eLabel position="0,{h5}" size="{w},5" backgroundColor="{title_c}" zPosition="1" />'
            '</screen>'
        ).format(
            w=width, h=height, 
            bg=c_bg, title_c=c_title,
            w40=width - 40,
            w150=width - 150,
            w320=width - 320, text_c=c_text,
            dim_c=c_dim,
            w140=width - 140,
            w110=width - 110,
            h5=height - 5
        )
        
        Screen.__init__(self, session)
        
        self["title"] = Label(str(league))
        self["match_name"] = Label(str(match_name))
        self["prompt"] = Label("Match is starting! Zap to channel?")
        self["key_ok"] = Label("Zap Now")
        self["key_cancel"] = Label("Cancel")
        
        self["h_logo"] = Pixmap()
        self["a_logo"] = Pixmap()
        
        # Logo Cache Path
        self.logo_cache_path = "/tmp/simplysports/logos/"
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "ok": self.ok,
            "cancel": self.cancel,
            "green": self.ok,
            "red": self.cancel
        }, -1)
        
        # Timer for auto-action or timeout
        self.timer = eTimer()
        try: self.timer.callback.append(self.timeout_action)
        except AttributeError: self.timer.timeout.get().append(self.timeout_action)
        self.timer.start(self.timeout_val * 1000, True)

        self.onLayoutFinish.append(self.load_logos)
        
        self.h_url = h_logo
        self.a_url = a_logo

    def load_logos(self):
        self.load_image(self.h_url, "h_logo")
        self.load_image(self.a_url, "a_logo")

    def load_image(self, url, widget_name):
        if not url: return
        try:
            import hashlib
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            target_path = self.logo_cache_path + url_hash + ".png"
            
            # Use 100 bytes minimum
            if os.path.exists(target_path) and os.path.getsize(target_path) > 100:
                if self[widget_name].instance:
                    self[widget_name].instance.setPixmapFromFile(target_path)
                    self[widget_name].instance.setScale(1) 
                    self[widget_name].show()
            else:
                downloadPage(url.encode('utf-8'), target_path).addCallback(
                    self.image_downloaded, widget_name, target_path
                ).addErrback(self.image_error)
        except: pass

    def image_downloaded(self, data, widget_name, target_path):
        if self[widget_name].instance:
            self[widget_name].instance.setPixmapFromFile(target_path)
            self[widget_name].instance.setScale(1)
            self[widget_name].show()

    def image_error(self, error): pass

    def ok(self):
        self.close(True)

    def cancel(self):
        self.close(False)

    def timeout_action(self):
        # Default action on timeout: Zap (True)
        self.close(True)

# ==============================================================================
# LEAGUE SELECTOR
# ==============================================================================
