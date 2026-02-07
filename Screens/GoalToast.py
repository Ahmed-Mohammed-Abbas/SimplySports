import os
from ..common import *
from ..globals import global_sports_monitor

class GoalToast(Screen):
    def __init__(self, session, league_text, home_text, away_text, score_text, scorer_text, l_url, h_url, a_url, event_type="default", scoring_team=None):
        # 1. OPTIMIZATION: Cache Directory
        self.logo_cache_path = "/tmp/simplysports/logos/"
        if not os.path.exists(self.logo_cache_path):
            try: os.makedirs(self.logo_cache_path)
            except: pass

        # FIX: Ensure all inputs are unicode (Py2/3 compatibility)
        def to_unicode(obj):
            if obj is None: return u""
            try:
                if isinstance(obj, bytes): return obj.decode('utf-8', 'ignore')
                return unicode(obj) if 'unicode' in globals() else str(obj)
            except: 
                try: return str(obj).decode('utf-8', 'ignore')
                except: return u""

        league_text = to_unicode(league_text)
        home_text   = to_unicode(home_text)
        away_text   = to_unicode(away_text)
        score_text  = to_unicode(score_text)
        scorer_text = to_unicode(scorer_text)

        # 1.1 REFINEMENT: Format Scorer Time "Player 45'" -> "Player (45')"
        if scorer_text and scorer_text.strip().endswith(u"'") and u"(" not in scorer_text:
            try:
                parts = scorer_text.rsplit(u' ', 1)
                if len(parts) == 2:
                    scorer_text = u"{} ({})".format(parts[0], parts[1])
            except: pass

        # 2. UX: Dynamic Layout Calculation (Center-Clustered)
        def est_width(text, font_size=26):
            if not text: return 10
            try: return int(len(text) * (font_size * 0.6)) + 25
            except: return 100

        w_league = est_width(league_text, 16)
        w_scorer = est_width(scorer_text, 16)
        w_home   = est_width(home_text, 26)
        w_away   = est_width(away_text, 26)
        w_score  = est_width(score_text, 26) + 40 # Padding for score box
        
        h_size = 75
        a_size = 75
        h_logo_y = 60 - (h_size // 2)
        a_logo_y = 60 - (a_size // 2)

        match_block_width = h_size + 5 + w_home + 5 + w_score + 5 + w_away + 5 + a_size
        req_width = max(match_block_width + 40, w_league + w_scorer + 60)
        req_width = int(req_width * 1.15)
        width = max(600, min(1200, req_width))
        
        center_x = width // 2
        start_x = center_x - (match_block_width // 2)
        
        h_logo_x = start_x
        h_name_x = h_logo_x + h_size + 5
        score_x  = h_name_x + w_home + 5
        a_name_x = score_x + w_score + 5
        a_logo_x = a_name_x + w_away + 5
        
        row_y = 25
        scr_x = width - w_scorer - 25

        # 3. UX: Priority Colors & Highlighting (Using #00RRGGBB for Opaque in Enigma2)
        colors = {
            'goal':   '#0000FF85',
            'card':   '#00FFFF00',
            'start':  '#0000FFFF',
            'end':    '#0000FFFF',
            'default':'#0000FF85'
        }
        border_color = colors.get(event_type, '#0000FF85')
        
        h_color = "#00FFFFFF"
        a_color = "#00FFFFFF"
        score_color = "#00FFFFFF"
        
        if event_type == 'goal':
            if scoring_team == 'home': h_color = border_color
            elif scoring_team == 'away': a_color = border_color
        elif event_type in ['start', 'end']:
            score_color = border_color

        # Use safe len() and unicode concatenation
        total_chars = len(league_text) + len(home_text) + len(away_text) + len(scorer_text)
        self.duration_ms = max(5000, min(12000, int(total_chars * 120 + 4000)))

        # 4. SKIN
        if global_sports_monitor.theme_mode == "ucl":
             self.skin = (
                u'<screen position="center,50" size="{width},100" title="Goal Notification" flags="wfNoBorder" backgroundColor="#000e1e5b">'
                u'<eLabel position="0,0" size="{width},100" backgroundColor="#000e1e5b" zPosition="0" />'
                u'<eLabel position="0,0" size="{width},2" backgroundColor="{border_color}" zPosition="2" />'
                u'<widget name="league" position="15,0" size="{w_league},20" font="Regular;16" foregroundColor="{border_color}" backgroundColor="#000e1e5b" valign="center" halign="left" zPosition="3" />'
                u'<widget name="scorer" position="{scr_x},0" size="{w_scorer},20" font="Regular;16" foregroundColor="#00FFFFFF" backgroundColor="#000e1e5b" valign="center" halign="right" zPosition="3" />'
                u'<widget name="h_logo" position="{h_logo_x},{h_logo_y}" size="{h_size},{h_size}" alphatest="blend" zPosition="4" />'
                u'<widget name="home" position="{h_name_x},{row_y}" size="{w_home},50" font="Regular;28" foregroundColor="{h_color}" backgroundColor="#000e1e5b" valign="center" halign="right" zPosition="3" />'
                u'<widget name="score" position="{score_x},{row_y}" size="{w_score},50" font="Regular;28" foregroundColor="{score_color}" backgroundColor="#000e1e5b" valign="center" halign="center" zPosition="3" />'
                u'<widget name="away" position="{a_name_x},{row_y}" size="{w_away},50" font="Regular;28" foregroundColor="{a_color}" backgroundColor="#000e1e5b" valign="center" halign="left" zPosition="3" />'
                u'<widget name="a_logo" position="{a_logo_x},{a_logo_y}" size="{a_size},{a_size}" alphatest="blend" zPosition="4" />'
                u'</screen>'
            ).format(width=width, border_color=border_color, w_league=w_league+20, scr_x=scr_x, w_scorer=w_scorer+20, h_logo_x=h_logo_x, h_logo_y=h_logo_y, h_size=h_size, h_name_x=h_name_x, w_home=w_home, h_color=h_color, score_x=score_x, w_score=w_score, score_color=score_color, a_name_x=a_name_x, w_away=w_away, a_color=a_color, a_logo_x=a_logo_x, a_logo_y=a_logo_y, a_size=a_size, row_y=row_y)
        else:
            self.skin = (
                u'<screen position="center,50" size="{width},100" title="Goal Notification" flags="wfNoBorder" backgroundColor="#00000000">'
                u'<eLabel position="0,0" size="{width},20" backgroundColor="#00000000" zPosition="0" />'
                u'<widget name="league" position="15,0" size="{w_league},20" font="Regular;16" foregroundColor="#00FFD700" backgroundColor="#00000000" valign="center" halign="left" zPosition="3" />'
                u'<widget name="scorer" position="{scr_x},0" size="{w_scorer},20" font="Regular;16" foregroundColor="#00FFFFFF" backgroundColor="#00000000" valign="center" halign="right" zPosition="3" />'
                u'<eLabel position="0,20" size="{width},80" backgroundColor="#00190028" zPosition="0" />'
                u'<widget name="h_logo" position="{h_logo_x},{h_logo_y}" size="{h_size},{h_size}" alphatest="blend" zPosition="4" />'
                u'<widget name="home" position="{h_name_x},20" size="{w_home},80" font="Regular;28" foregroundColor="{h_color}" backgroundColor="#00190028" valign="center" halign="right" zPosition="3" />'
                u'<widget name="score" position="{score_x},20" size="{w_score},80" font="Regular;28" foregroundColor="{score_color}" backgroundColor="#00190028" valign="center" halign="center" zPosition="3" />'
                u'<widget name="away" position="{a_name_x},20" size="{w_away},80" font="Regular;28" foregroundColor="{a_color}" backgroundColor="#00190028" valign="center" halign="left" zPosition="3" />'
                u'<widget name="a_logo" position="{a_logo_x},{a_logo_y}" size="{a_size},{a_size}" alphatest="blend" zPosition="4" />'
                u'<eLabel position="0,98" size="{width},2" backgroundColor="{border_color}" zPosition="2" />'
                u'</screen>'
            ).format(width=width, border_color=border_color, w_league=w_league+20, scr_x=scr_x, w_scorer=w_scorer+20, h_logo_x=h_logo_x, h_logo_y=h_logo_y, h_size=h_size, h_name_x=h_name_x, w_home=w_home, h_color=h_color, score_x=score_x, w_score=w_score, score_color=score_color, a_name_x=a_name_x, w_away=w_away, a_color=a_color, a_logo_x=a_logo_x, a_logo_y=a_logo_y, a_size=a_size)

        Screen.__init__(self, session)
        self["league"] = Label(league_text)
        self["home"] = Label(home_text)
        self["away"] = Label(away_text)
        self["score"] = Label(score_text)
        self["scorer"] = Label(scorer_text)
        
        self["h_logo"] = Pixmap()
        self["a_logo"] = Pixmap()
        
        self.h_url = h_url
        self.a_url = a_url
        self.onLayoutFinish.append(self.load_logos)

        # 5. UX: Cleanup Timer (Dynamic Duration)
        self.timer = eTimer()
        try: self.timer.callback.append(self.close)
        except AttributeError: self.timer.timeout.get().append(self.close)
        
        # 6. UX: Entry Animation (Slide-In)
        self.anim_timer = eTimer()
        try: self.anim_timer.callback.append(self.animate_entry)
        except AttributeError: self.anim_timer.timeout.get().append(self.animate_entry)
        
        # Start position (Off-screen Top)
        self.current_y = -100
        self.target_y = 10
        self.toast_width = width
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
            "ok": self.close, "cancel": self.close, 
            "red": self.close, "green": self.close, "yellow": self.close, "blue": self.close,
            "up": self.close, "down": self.close, "left": self.close, "right": self.close
        }, -1)
        
        self.onLayoutFinish.append(self.start_animation)

    def start_animation(self):
        self.force_top()
        self.anim_timer.start(20, False)

    def animate_entry(self):
        # FIX: Preserve horizontal centering while animating Y
        try:
            step = 10
            if self.current_y < self.target_y:
                self.current_y += step
                from enigma import getDesktop
                desktop = getDesktop(0)
                dw = desktop.size().width()
                # Center X: (DesktopWidth - ToastWidth) / 2
                center_x = (dw - self.toast_width) // 2
                self.instance.move(ePoint(center_x, self.current_y))
            else:
                self.anim_timer.stop()
                self.timer.start(self.duration_ms, True)
        except:
            self.anim_timer.stop()
            self.timer.start(self.duration_ms, True)

    def force_top(self):
        try: self.instance.setZPosition(10)
        except: pass

    def load_logos(self):
        self.load_image(self.h_url, "h_logo")
        self.load_image(self.a_url, "a_logo")

    def load_image(self, url, widget_name):
        if not url:
            self[widget_name].hide()
            return

        try:
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            target_path = self.logo_cache_path + url_hash + ".png"
            
            # Use 100 bytes as minimum for a valid PNG (prevents 1-byte corrupt files from being hits)
            if os.path.exists(target_path) and os.path.getsize(target_path) > 100:
                if self[widget_name].instance:
                    self[widget_name].instance.setPixmapFromFile(target_path)
                    self[widget_name].instance.setScale(1) # Robustness
                    self[widget_name].show()
            else:
                downloadPage(url.encode('utf-8'), target_path).addCallback(
                    self.image_downloaded, widget_name, target_path
                ).addErrback(self.image_error)
        except:
             self[widget_name].hide()

    def image_downloaded(self, data, widget_name, target_path):
        if self[widget_name].instance:
            self[widget_name].instance.setPixmapFromFile(target_path)
            self[widget_name].instance.setScale(1) # Robustness
            self[widget_name].show()

    def image_error(self, error): pass

# ==============================================================================
# ZAP NOTIFICATION SCREEN (Interactive)
# ==============================================================================
