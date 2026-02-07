import os
from ..common import *
from ..globals import global_sports_monitor

from .SimplePlayer import SimplePlayer
from .TeamStandingScreen import TeamStandingScreen
class GameInfoScreen(Screen):
    def __init__(self, session, event_id, league_url=""):
        Screen.__init__(self, session)
        self.session = session
        self.event_id = event_id
        self.theme = global_sports_monitor.theme_mode
        self.league_url = league_url  # Store for standings screen
        self.league_name = ""  # Will be set when parsing data
        self.sport_type = get_sport_type(league_url)  # Detect sport type
        
        self.full_rows = []      
        self.current_page = 0    
        self.items_per_page = 10 
        
        base_url = league_url.split('?')[0]
        if "scoreboard" in base_url:
            self.summary_url = base_url.replace("scoreboard", "summary") + "?event=" + str(event_id)
        else:
            self.summary_url = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary?event=" + str(event_id)

        # --- SKIN ---
        # For individual sports (racing, golf, combat), use a single event header
        # For team sports and TENNIS, use the traditional two-team vs layout
        is_individual_sport = self.sport_type in [SPORT_TYPE_RACING, SPORT_TYPE_GOLF, SPORT_TYPE_COMBAT]
        
        if is_individual_sport:
            # Single event layout - centered title, no team logos in header
            common_widgets = """
                <widget name="match_title" position="0,5" size="1600,28" font="Regular;26" foregroundColor="{accent}" transparent="1" halign="center" valign="center" text="" zPosition="6" />
                
                <widget name="h_logo" position="40,30" size="100,100" alphatest="blend" zPosition="5" scale="1" />
                <widget name="h_name" position="0,35" size="1600,60" font="Regular;46" foregroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="5" />
                <widget name="h_score" position="0,0" size="0,0" font="Regular;1" transparent="1" zPosition="-10" />
                <widget name="a_score" position="0,0" size="0,0" font="Regular;1" transparent="1" zPosition="-10" />
                <widget name="a_name" position="0,0" size="0,0" font="Regular;1" transparent="1" zPosition="-10" />
                <widget name="a_logo" position="0,0" size="0,0" alphatest="blend" zPosition="-10" />
                
                <widget name="stadium_name" position="0,105" size="1600,28" font="Regular;24" foregroundColor="#aaaaaa" transparent="1" halign="center" valign="center" zPosition="5" />
 
                <widget name="info_list" position="0,160" size="1600,700" scrollbarMode="showNever" transparent="1" zPosition="5" />
                <widget name="loading" position="0,400" size="1600,100" font="Regular;32" foregroundColor="{accent}" transparent="1" halign="center" zPosition="10" />
                <widget name="page_indicator" position="0,860" size="1600,30" font="Regular;24" foregroundColor="#ffffff" transparent="1" halign="center" zPosition="10" />
            """
        else:
            # Two-team match layout (1600px Wide)
            common_widgets = """
                <widget name="match_title" position="0,5" size="1600,28" font="Regular;26" foregroundColor="{accent}" transparent="1" halign="center" valign="center" text="" zPosition="6" />
                
                <widget name="h_logo" position="50,25" size="110,110" alphatest="blend" zPosition="5" scale="1" />
                <widget name="h_name" position="170,35" size="430,55" font="Regular;44" foregroundColor="#ffffff" transparent="1" halign="left" valign="center" zPosition="5" />
                <widget name="h_score" position="620,35" size="150,90" font="Regular;72" foregroundColor="#ffffff" transparent="1" halign="right" valign="center" zPosition="5" />
                
                <widget name="countdown_label" position="500,35" size="600,45" font="Regular;32" foregroundColor="{accent}" transparent="1" halign="center" valign="center" zPosition="5" />
                <widget name="start_time_label" position="500,80" size="600,45" font="Regular;32" foregroundColor="#cccccc" transparent="1" halign="center" valign="center" zPosition="5" />
                <widget name="score_sep" position="785,50" size="30,50" font="Regular;36" foregroundColor="#888888" transparent="1" halign="center" valign="center" text="-" zPosition="5" />

                <widget name="a_score" position="830,35" size="150,90" font="Regular;72" foregroundColor="#ffffff" transparent="1" halign="left" valign="center" zPosition="5" />
                <widget name="a_name" position="1000,35" size="430,55" font="Regular;44" foregroundColor="#ffffff" transparent="1" halign="right" valign="center" zPosition="5" />
                <widget name="a_logo" position="1440,25" size="110,110" alphatest="blend" zPosition="5" scale="1" />
                
                <widget name="stadium_name" position="0,125" size="1600,25" font="Regular;22" foregroundColor="#aaaaaa" transparent="1" halign="center" valign="center" zPosition="5" />
 
                <widget name="info_list" position="0,160" size="1600,700" scrollbarMode="showNever" transparent="1" zPosition="5" />
                <widget name="loading" position="0,400" size="1600,100" font="Regular;32" foregroundColor="{accent}" transparent="1" halign="center" zPosition="10" />
                <widget name="page_indicator" position="0,860" size="1600,30" font="Regular;24" foregroundColor="#ffffff" transparent="1" halign="center" zPosition="10" />
            """

        if self.theme == "ucl":
            bg_color = "#00000000"; top_bar = "#091442"; accent = "#00ffff"
            skin_widgets = common_widgets.replace("{accent}", accent)
            self.skin = f"""<screen position="center,center" size="1600,900" title="Game Stats" flags="wfNoBorder" backgroundColor="{bg_color}"><eLabel position="0,0" size="1600,150" backgroundColor="{top_bar}" zPosition="0" /><eLabel position="0,150" size="1600,4" backgroundColor="{accent}" zPosition="1" />{skin_widgets}</screen>"""
        else:
            bg_color = "#38003C"; top_bar = "#28002C"; accent = "#00FF85"
            skin_widgets = common_widgets.replace("{accent}", accent)
            self.skin = f"""<screen position="center,center" size="1600,900" title="Game Stats" flags="wfNoBorder" backgroundColor="{bg_color}"><eLabel position="0,0" size="1600,150" backgroundColor="{top_bar}" zPosition="0" /><eLabel position="0,150" size="1600,4" backgroundColor="{accent}" zPosition="1" />{skin_widgets}</screen>"""

        self["h_name"] = Label(""); self["a_name"] = Label("")
        self["h_score"] = Label(""); self["a_score"] = Label("")
        self["score_sep"] = Label("-"); self["start_time_label"] = Label(""); self["countdown_label"] = Label("")
        self["stadium_name"] = Label(""); self["match_title"] = Label("MATCH DETAILS")
        self["h_logo"] = Pixmap(); self["a_logo"] = Pixmap()
        self["loading"] = Label("Fetching Data..."); self["page_indicator"] = Label("")
        
        self["info_list"] = MenuList([], enableWrapAround=False, content=eListboxPythonMultiContent)
        self["info_list"].l.setFont(0, gFont("Regular", 24))
        self["info_list"].l.setFont(1, gFont("Regular", 20))
        self["info_list"].l.setItemHeight(50)
        self.items_per_page = 14 # Fill screen (700px / 50px = 14)
        
        self["actions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions", "WizardActions"], {
            "cancel": self.close, "green": self.close, "ok": self.handle_ok, "back": self.close,
            "up": self["info_list"].up, "down": self["info_list"].down, "left": self.page_up, "right": self.page_down
        }, -2)
        
        self.onLayoutFinish.append(self.start_loading)

    def handle_ok(self):
        idx = self["info_list"].getSelectedIndex()
        if idx is None: return

        # Calculate actual index in full_rows based on pagination
        real_idx = (self.current_page * self.items_per_page) + idx
        if real_idx < len(self.full_rows):
            item = self.full_rows[real_idx]
            # item[0] is the data tuple passed to InfoListEntry/TextListEntry
            data = item[0]
            
            # Check if it's a video entry (Tuple len 4: Label, Icon, Title, URL)
            if isinstance(data, tuple) and len(data) > 3:
                if data[0] == "VIDEO":
                    url = data[3]
                    title = data[2]
                    self.play_video(url, title)
                elif data[0] == "PLAY ALL":
                    self.play_all_videos()
            else:
                # Default behavior: Standings
                self.open_standings()

    def play_all_videos(self):
        if not hasattr(self, 'all_videos') or not self.all_videos: return
        
        formatted_playlist = []
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        
        for url, title in self.all_videos:
            # Clean URL first
            clean_url = url.strip()
            
            # Add headers properly
            if "#" in clean_url:
                # Already has fragment, append
                full_url = "{}&User-Agent={}".format(clean_url, ua)
            else:
                # No fragment, add new one
                full_url = "{}#User-Agent={}".format(clean_url, ua)
            
            # Optional: Add referer for ESPN
            if "espn" in clean_url.lower():
                full_url += "&Referer=https://www.espn.com/"
            
            formatted_playlist.append((full_url, title))
        
        self.session.open(SimplePlayer, sref=None, playlist=formatted_playlist)

    def play_video(self, url, title):
        if not url: return
        
        clean_url = url.strip()
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        
        if "#" in clean_url:
            full_url = "{}&User-Agent={}".format(clean_url, ua)
        else:
            full_url = "{}#User-Agent={}".format(clean_url, ua)
            
        if "espn" in clean_url.lower():
            full_url += "&Referer=https://www.espn.com/"
            
        # Use ServiceMP (4097) for stream playback or inherited by SimplePlayer
        # Note: SimplePlayer will override service_type based on HLS/MP4 detection
        # Create a basic ref to pass through
        ref = "4097:0:1:0:0:0:0:0:0:0:{}:{}".format(full_url.replace(":", "%3a"), title)
        
        self.session.open(SimplePlayer, eServiceReference(ref))



    def open_standings(self):
        """Open the Team Standing Screen for this league"""
        self.session.openWithCallback(self.standings_callback, TeamStandingScreen, self.league_url, self.league_name)
    
    def standings_callback(self, result=None):
        """Handle return from standings screen - close if 'close_all' signal received"""
        if result == "close_all":
            self.close()

    def update_display(self):
        if not self.full_rows:
            self["info_list"].setList([]); self["page_indicator"].setText(""); return
        total_items = len(self.full_rows)
        start_index = self.current_page * self.items_per_page
        end_index = start_index + self.items_per_page
        page_data = self.full_rows[start_index:end_index]
        self["info_list"].setList(page_data)
        import math
        total_pages = int(math.ceil(float(total_items) / float(self.items_per_page)))
        if total_pages > 1: self["page_indicator"].setText("Page {}/{}".format(self.current_page + 1, total_pages))
        else: self["page_indicator"].setText("")

    def page_down(self):
        total_items = len(self.full_rows)
        if total_items > 0:
            import math
            max_page = int(math.ceil(float(total_items) / float(self.items_per_page))) - 1
            if self.current_page < max_page: self.current_page += 1; self.update_display()

    def page_up(self):
        if self.current_page > 0: self.current_page -= 1; self.update_display()

    def start_loading(self):
        from twisted.web.client import getPage
        getPage(self.summary_url.encode('utf-8')).addCallback(self.parse_details).addErrback(self.error_details)

    def error_details(self, error): self["loading"].setText("Error loading details.")

    def download_logo(self, url, widget_name):
        if url and url.startswith("http"):
            hq_url = url.replace("40&h=40", "500&h=500")
            tmp_path = "/tmp/ss_big_{}.png".format(widget_name)
            from twisted.web.client import downloadPage
            downloadPage(hq_url.encode('utf-8'), tmp_path).addCallback(self.logo_ready, widget_name, tmp_path)

    def logo_ready(self, data, widget_name, tmp_path):
        if self[widget_name].instance:
            self[widget_name].instance.setScale(1)
            self[widget_name].instance.setPixmapFromFile(tmp_path)
            self[widget_name].show()

    def thumbnail_ready(self, *args, **kwargs): pass


    def parse_details(self, body):
        try:
            self["loading"].hide()
            json_str = body.decode('utf-8', errors='ignore')
            data = json.loads(json_str)
            
            # --- HEADER ---
            header_comps = data.get('header', {}).get('competitions', [{}])[0].get('competitors', [])
            boxscore_teams = data.get('boxscore', {}).get('teams', [])
            game_status = data.get('header', {}).get('competitions', [{}])[0].get('status', {}).get('type', {}).get('state', 'pre')

            # --- STADIUM ---
            try:
                venue = data.get('gameInfo', {}).get('venue', {})
                v_name = venue.get('fullName', '')
                addr = venue.get('address', {})
                v_city = addr.get('city', '')
                loc_txt = v_name
                if v_city: loc_txt += " - " + v_city
                self["stadium_name"].setText(loc_txt)
            except: self["stadium_name"].setText("")

            # --- TEAMS ---
            home_team = {}; away_team = {}
            if header_comps:
                home_team = next((t for t in header_comps if t.get('homeAway') == 'home'), {})
                away_team = next((t for t in header_comps if t.get('homeAway') == 'away'), {})

            if boxscore_teams:
                h_id = home_team.get('id'); a_id = away_team.get('id')
                if h_id: h_box = next((t for t in boxscore_teams if t.get('team', {}).get('id') == h_id), {})
                else: h_box = boxscore_teams[0] if len(boxscore_teams) > 0 else {}
                if a_id: a_box = next((t for t in boxscore_teams if t.get('team', {}).get('id') == a_id), {})
                else: a_box = boxscore_teams[1] if len(boxscore_teams) > 1 else {}
                if h_box: home_team.update(h_box)
                if a_box: away_team.update(a_box)

            def get_name(t): return t.get('team', {}).get('shortDisplayName') or t.get('team', {}).get('displayName') or "Team"
            self["h_name"].setText(get_name(home_team))
            self["a_name"].setText(get_name(away_team))
            self["h_score"].setText(str(home_team.get('score', '0')))
            self["a_score"].setText(str(away_team.get('score', '0')))

            # SCHEDULED GAME HANDLING: Show Countdown + Date/Time instead of 0-0
            if game_status == 'pre':
                self["h_score"].hide(); self["a_score"].hide(); self["score_sep"].hide()
                match_date = data.get('header', {}).get('competitions', [{}])[0].get('date', '')
                if match_date:
                    import datetime
                    dt = None
                    try:
                        # Clean string (remove Z)
                        # Format expect: 2026-02-05T17:30Z
                        clean_date = match_date.replace("Z", "").replace("T", " ")
                        if "." in clean_date: clean_date = clean_date.split(".")[0]
                        
                        # 1. Try standard parser
                        try: dt = datetime.datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                        except:
                            try: dt = datetime.datetime.strptime(clean_date, "%Y-%m-%d %H:%M")
                            except: pass
                        
                        # 2. Try Manual Construction
                        if not dt:
                            try:
                                parts = clean_date.split(" ")
                                d_parts = parts[0].split("-")
                                t_parts = parts[1].split(":")
                                dt = datetime.datetime(int(d_parts[0]), int(d_parts[1]), int(d_parts[2]), int(t_parts[0]), int(t_parts[1]))
                            except: pass
                            
                    except: pass

                    # LOGIC:
                    if dt:
                        # 3. Countdown
                        try:
                            now = datetime.datetime.utcnow()
                            delta = dt - now
                            d_days = delta.days
                            d_secs = delta.seconds
                            total_seconds = (d_days * 86400) + d_secs
                            
                            if total_seconds > 0:
                                if d_days > 0:
                                    count_str = "{} Days, {} Hours".format(d_days, d_secs // 3600)
                                else:
                                    hrs = d_secs // 3600
                                    mins = (d_secs // 60) % 60
                                    count_str = "{} Hours, {} Mins".format(hrs, mins)
                            else:
                                count_str = "Starting Soon"
                            self["countdown_label"].setText(count_str)
                        except: self["countdown_label"].setText("")

                        # 4. Display Time (Convert UTC to Local)
                        try:
                            # Dynamic Offset Calculation: Local - UTC
                            offset = datetime.datetime.now() - datetime.datetime.utcnow()
                            dt_local = dt + offset
                            time_str = dt_local.strftime("%a %d/%m %H:%M")
                            self["start_time_label"].setText(time_str)
                        except: self["start_time_label"].setText(str(clean_date))
                    else:
                        # FALLBACK: If dt failed completely, just clean the string manually
                        # Slicing: 2026-02-05T17:30Z -> 2026-02-05 17:30
                        self["countdown_label"].setText("")
                        try:
                            fallback_str = match_date.replace("T", " ").replace("Z", "")
                            # Try to make it look nicer 2026-02-05 -> 05/02? Too risky.
                            # Just show clean fallback
                            self["start_time_label"].setText(fallback_str[0:16])
                        except:
                            self["start_time_label"].setText(str(match_date))
                
                self["countdown_label"].show()
                self["start_time_label"].show()
            else:
                self["h_score"].show(); self["a_score"].show(); self["score_sep"].show()
                self["start_time_label"].hide(); self["countdown_label"].hide()

            # --- LOGOS ---
            try:
                header = data.get('header', {})
                league_name = header.get('league', {}).get('name', '') or data.get('league', {}).get('name', '')
                self.league_name = league_name  # Store for standings screen
                sport_cdn = global_sports_monitor.get_cdn_sport_name(league_name)
                h_id = home_team.get('team', {}).get('id', '')
                if h_id: self.download_logo("https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png".format(sport_cdn, h_id), "h_logo")
                a_id = away_team.get('team', {}).get('id', '')
                if a_id: self.download_logo("https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png".format(sport_cdn, a_id), "a_logo")
            except: pass

            self.full_rows = [] 

            # ==========================================================
            # SPORT TYPE BRANCHING - Route to appropriate parser
            # ==========================================================
            if self.sport_type == SPORT_TYPE_RACING:
                self.parse_racing_event(data, league_name, game_status)
                return
            elif self.sport_type == SPORT_TYPE_GOLF:
                self.parse_golf_event(data, league_name, game_status)
                return
            elif self.sport_type == SPORT_TYPE_TENNIS:
                self.parse_tennis_event(data, league_name, game_status, home_team, away_team)
                return
            elif self.sport_type == SPORT_TYPE_COMBAT:
                self.parse_combat_event(data, league_name, game_status)
                return
            elif self.sport_type == SPORT_TYPE_CRICKET:
                self.parse_cricket_event(data, league_name, game_status)
                return
            elif self.sport_type == SPORT_TYPE_RUGBY:
                self.parse_rugby_event(data, league_name, game_status)
                return

            # ==========================================================
            # TEAM SPORTS: FACEBOOK STYLE NEWS FEED (PREVIEW MODE)
            # ==========================================================
            
            # --- VIDEO HIGHLIGHTS ---
            try:
                videos = data.get('videos', [])
                if videos:
                    # Sort Videos: Goals > Highlights > Others
                    def get_vid_priority(v):
                        txt = (v.get('headline') or v.get('title') or "").lower()
                        if "goal" in txt or "score" in txt: return 0
                        if "highlight" in txt or "summary" in txt or "recap" in txt: return 1
                        return 2
                    
                    videos.sort(key=get_vid_priority)

                    # Generic Header for Videos
                    self.full_rows.append(TextListEntry("GAME HIGHLIGHTS", self.theme, is_header=True))
                    self.full_rows.append(TextListEntry("Press OK to play video", self.theme))
                    
                    # Track index to insert "Play All" button
                    insert_idx = len(self.full_rows)
                    self.all_videos = []
                    
                    for vid in videos:
                        title = vid.get('headline') or vid.get('title') or "Video"
                        url = ""
                        
                        # EPSN often nests links deeply
                        links = vid.get('links', {})
                        source = links.get('source', {})
                        
                        # Preferred qualities
                        if 'mezzanine' in source: url = source['mezzanine'].get('href')
                        elif 'flash' in source: url = source['flash'].get('href')
                        elif 'hls' in source: url = source['hls'].get('href')
                        elif 'HD' in links: url = links.get('HD', {}).get('href')
                        elif 'mobile' in links: url = links.get('mobile', {}).get('href')
                        
                        if url:
                            self.all_videos.append((url, title))
                            # Duration
                            dur_txt = "VIDEO"
                            duration = str(vid.get('duration', ''))
                            if duration.isdigit():
                                m = int(duration) // 60
                                s = int(duration) % 60
                                dur_txt = "{}:{:02d}".format(m, s)
                            
                            # Simplified Icon Handling (No Thumbnails)
                            icon_display = "▶"

                            payload = ("VIDEO", icon_display, title, url)
                            self.full_rows.append(InfoListEntry(payload))
                    
                    if len(self.all_videos) > 1:
                         payload = ("PLAY ALL", "▶▶", "    Play All Highlights ({})".format(len(self.all_videos)), "")
                         self.full_rows.insert(insert_idx, InfoListEntry(payload))
                         
                         # STABILIZATION: Removed Early Prefetch. 
                         # We only download when the player is actually open.

            except: pass

            if game_status == 'pre':
                self["match_title"].setText(league_name if league_name else "PREVIEW")
                
                # 1. Prediction (FB Style Post) - ROBUST & SOCCER ENABLED
                try:
                    predictor = data.get('predictor', {})
                    if predictor:
                        h_team_pred = predictor.get('homeTeam', {}) or {}
                        a_team_pred = predictor.get('awayTeam', {}) or {}
                        
                        # Try standard key 'gameProjection', fallback to 'chanceToWin' if available
                        h_prob = h_team_pred.get('gameProjection') or h_team_pred.get('chanceToWin') or '0'
                        a_prob = a_team_pred.get('gameProjection') or a_team_pred.get('chanceToWin') or '0'
                        
                        # Ensure string and clean percent logic
                        h_val = float(h_prob) if h_prob else 0.0
                        a_val = float(a_prob) if a_prob else 0.0
                        
                        if h_val > 0 or a_val > 0:
                            # Post Header
                            self.full_rows.append(TextListEntry("GAME PREDICTION", self.theme, is_header=True))
                            
                            # Calc Draw if not provided (Soccer often needs this)
                            draw_val = max(0.0, 100.0 - h_val - a_val)
                            
                            # Formatting
                            if draw_val > 0.1: # Show draw if significant
                                txt = "Home Win: {:.1f}%  |  Draw: {:.1f}%  |  Away Win: {:.1f}%".format(h_val, draw_val, a_val)
                            else:
                                txt = "Home Win: {:.1f}%  |  Away Win: {:.1f}%".format(h_val, a_val)
                                
                            self.full_rows.append(TextListEntry(txt, self.theme))
                            # Post Footer

                except: pass

                # 2. Betting (FB Style Post)
                try:
                    odds = data.get('pickcenter', [])
                    if odds:
                        self.full_rows.append(TextListEntry("BETTING INSIGHTS", self.theme, is_header=True))
                        for odd in odds:
                            provider = odd.get('provider', {}).get('name', 'Odds')
                            details = odd.get('details', 'N/A')
                            ou = odd.get('overUnder', 'N/A')
                            txt = "{}: Spread {} | O/U {}".format(provider, details, ou)
                            self.full_rows.append(TextListEntry(txt, self.theme))
                        self.full_rows.append(TextListEntry("", self.theme))
                except: pass

                # 3. News Feed (The Main FB Look)
                try:
                    news_items = data.get('news', {}).get('articles', [])
                    if not news_items: news_items = data.get('articles', [])
                    
                    if news_items:
                        self.full_rows.append(TextListEntry("LATEST NEWS", self.theme, is_header=True))
                        count = 0
                        import random
                        for article in news_items:
                            if count >= 5: break
                            headline = article.get('headline', '')
                            desc = article.get('description', '')
                            published = article.get('published', 'Just now')
                            # Clean time if it's full ISO
                            if "T" in published: published = "2 hrs ago" 
                            
                            if headline:
                                # Row 1: Headline as wrapped paragraph
                                headline_lines = wrap_text(headline, max_chars=130)
                                for line in headline_lines:
                                    self.full_rows.append(TextListEntry(line, self.theme, align="left"))
                                
                                # Row 2: Description as wrapped paragraph (if available)
                                if desc:
                                    desc_lines = wrap_text(desc, max_chars=130)
                                    for line in desc_lines:
                                        self.full_rows.append(TextListEntry(line, self.theme, align="left"))
                                
                                # Divider/Spacer between posts
                                self.full_rows.append(TextListEntry("", self.theme)) 
                                count += 1
                except: pass
                
                # 4. Standings
                try:
                    standings = data.get('standings', {}).get('entries', [])
                    if standings:
                        self.full_rows.append(TextListEntry("LEAGUE TABLE", self.theme, is_header=True))
                        for entry in standings:
                            tid = entry.get('team', {}).get('id')
                            if tid == h_id or tid == a_id:
                                t_name = entry.get('team', {}).get('displayName', '')
                                stats = entry.get('stats', [])
                                rec = next((s['displayValue'] for s in stats if s.get('name') == 'rank'), '-')
                                form = next((s['displayValue'] for s in stats if s.get('abbreviation') == 'L10'), '-')
                                txt = "{}: Rank #{} | Form: {}".format(t_name, rec, form)
                                self.full_rows.append(TextListEntry(txt, self.theme, align="left"))
                        self.full_rows.append(TextListEntry("", self.theme))
                except: pass

                if not self.full_rows:
                    self.full_rows.append(TextListEntry("No Preview Data Available", self.theme))

            # ==========================================================
            # MODE B: LIVE/POST GAME (STATS MODE - Unchanged)
            # ==========================================================
            else:
                self["match_title"].setText(league_name if league_name else "DETAILS")
                
                # 0. Prediction (Live Win Probability - Added for Live Games too)
                try:
                    predictor = data.get('predictor', {}) or data.get('winprobability', []) # sometimes separate list
                    # If it's the standard predictor object
                    if isinstance(predictor, dict) and predictor:
                        h_team_pred = predictor.get('homeTeam', {}) or {}
                        a_team_pred = predictor.get('awayTeam', {}) or {}
                        h_prob = h_team_pred.get('gameProjection') or h_team_pred.get('chanceToWin')
                        a_prob = a_team_pred.get('gameProjection') or a_team_pred.get('chanceToWin')
                        
                        if h_prob:
                            h_val = float(h_prob); a_val = float(a_prob) if a_prob else 0.0
                            self.full_rows.append(TextListEntry("LIVE WIN PROBABILITY", self.theme, is_header=True))
                            draw_val = max(0.0, 100.0 - h_val - a_val)
                            if draw_val > 0.1:
                                txt = "Home: {:.1f}%  |  Draw: {:.1f}%  |  Away: {:.1f}%".format(h_val, draw_val, a_val)
                            else:
                                txt = "Home: {:.1f}%  |  Away: {:.1f}%".format(h_val, a_val)
                            self.full_rows.append(TextListEntry(txt, self.theme))
                            self.full_rows.append(TextListEntry("", self.theme))
                except: pass

                # 1. Timeline
                details = []
                comps_data = data.get('competitions', [{}])[0]
                if 'details' in comps_data: details = comps_data['details']
                elif 'details' in data.get('header', {}).get('competitions', [{}])[0]:
                    details = data.get('header', {}).get('competitions', [{}])[0]['details']

                if details:
                    self.full_rows.append(EventListEntry("TIME", "HOME EVENTS", "AWAY EVENTS", self.theme))
                    goals_found = False
                    for play in details:
                        text_desc = play.get('type', {}).get('text', '').lower()
                        # Detect scoring plays for various sports: soccer (goal), football (touchdown), hockey (power play, etc.)
                        is_score = play.get('scoringPlay', False) or "goal" in text_desc or "touchdown" in text_desc or "power play" in text_desc or "short-handed" in text_desc or "even strength" in text_desc or "empty net" in text_desc or "shorthanded" in text_desc
                        is_card = "card" in text_desc
                        is_sub = "substitution" in text_desc
                        
                        if is_score or is_card:
                            goals_found = True
                            clock = play.get('clock', {}).get('displayValue', '')
                            
                            # Get main athlete (scorer or card recipient)
                            scorer = ""
                            assist = ""
                            athletes = play.get('athletesInvolved', [])
                            
                            if athletes:
                                # First athlete is usually the scorer/recipient
                                scorer = athletes[0].get('displayName') or athletes[0].get('shortName') or ''
                                # Check for assist (second athlete for goals)
                                if is_score and len(athletes) > 1:
                                    assist = athletes[1].get('displayName') or athletes[1].get('shortName') or ''
                            elif play.get('participants'):
                                participants = play['participants']
                                if participants:
                                    p = participants[0].get('athlete', {})
                                    scorer = p.get('displayName') or p.get('shortName') or ''
                                    # Check for assist in participants
                                    if is_score and len(participants) > 1:
                                        p2 = participants[1].get('athlete', {})
                                        assist = p2.get('displayName') or p2.get('shortName') or ''
                            else:
                                txt = play.get('type', {}).get('text', '')
                                if " - " in txt: scorer = txt.split(" - ")[-1].strip()
                                elif "Goal" in txt: scorer = txt.replace("Goal", "").strip()
                            
                            if not scorer: scorer = "Event"
                            
                            # Build display text with icons
                            if is_card:
                                if "red" in text_desc:
                                    scorer = u"\U0001F7E5 " + scorer  # Red square
                                elif "yellow" in text_desc:
                                    scorer = u"\U0001F7E8 " + scorer  # Yellow square
                                else:
                                    scorer = u"\U0001F7E8 " + scorer
                            elif is_score:
                                scorer = u"\u26BD " + scorer
                                if assist:
                                    scorer += u" (A: {})".format(assist)
                            
                            t_id = str(play.get('team', {}).get('id', ''))
                            h_id_root = str(home_team.get('id', 'h'))
                            
                            home_evt = ""
                            away_evt = ""
                            if t_id == h_id_root:
                                home_evt = scorer
                            else:
                                away_evt = scorer
                            
                            # Append to list
                            self.full_rows.append(EventListEntry(clock, home_evt, away_evt, self.theme))
                    
                    if not goals_found:
                        self.full_rows.append(StatsListEntry("-", "No Events", "", self.theme))
                
                # 2. Stats
                if boxscore_teams:
                    self.full_rows.append(StatsListEntry("", "", "", self.theme))
                    self.full_rows.append(StatsListEntry("STATS", "HOME", "AWAY", self.theme))
                    h_stats_list = []; a_stats_list = []
                    if 'statistics' in home_team: h_stats_list = home_team['statistics']
                    if 'statistics' in away_team: a_stats_list = away_team['statistics']
                    a_map = {s['label']: s['displayValue'] for s in a_stats_list}
                    for stat in h_stats_list:
                        lbl = stat['label']; h_val = stat['displayValue']; a_val = a_map.get(lbl, "-")
                        self.full_rows.append(StatsListEntry(lbl, h_val, a_val, self.theme))

                # 3. Formations
                try:
                    h_formation = home_team.get('formation', '') or home_team.get('team', {}).get('formation', '')
                    a_formation = away_team.get('formation', '') or away_team.get('team', {}).get('formation', '')
                    if h_formation or a_formation:
                        self.full_rows.append(StatsListEntry("", "", "", self.theme))
                        self.full_rows.append(StatsListEntry("FORMATION", str(h_formation) if h_formation else "-", str(a_formation) if a_formation else "-", self.theme))
                except: pass

                # 4. Lineups / Rosters
                boxscore = data.get('boxscore', {})
                players_data = boxscore.get('players', [])
                rosters = data.get('rosters', [])
                
                # Try boxscore players first
                h_roster = []; a_roster = []
                if players_data:
                    for team_p in players_data:
                        t_id = str(team_p.get('team', {}).get('id', ''))
                        team_list = []
                        stats_groups = team_p.get('statistics', [])
                        for group in stats_groups:
                            grp_name = group.get('name', 'players').upper()
                            team_list.append(u"\u2022 {} \u2022".format(grp_name))
                            for ath in group.get('athletes', []):
                                name = ath.get('athlete', {}).get('displayName') or ath.get('athlete', {}).get('shortName')
                                jersey = ath.get('jersey', '')
                                position = ath.get('athlete', {}).get('position', {}).get('abbreviation', '')
                                if name: 
                                    p_str = "#{} {} ({})".format(jersey, name, position) if jersey and position else ("#{} {}".format(jersey, name) if jersey else name)
                                    team_list.append(p_str)
                        if t_id == str(home_team.get('id')): h_roster = team_list
                        elif t_id == str(away_team.get('id')): a_roster = team_list
                
                # Try rosters if boxscore players empty
                if not h_roster and not a_roster and rosters:
                    for team_r in rosters:
                        t_id = str(team_r.get('team', {}).get('id', ''))
                        team_list = []
                        for entry in team_r.get('roster', []):
                            name = entry.get('athlete', {}).get('displayName') or entry.get('athlete', {}).get('shortName') or ''
                            jersey = entry.get('jersey', '')
                            position = entry.get('position', {}).get('abbreviation', '')
                            starter = entry.get('starter', False)
                            if name:
                                prefix = u"\u2605 " if starter else "  "
                                p_str = "{}#{} {} ({})".format(prefix, jersey, name, position) if jersey and position else "{}{}".format(prefix, name)
                                team_list.append(p_str)
                        if t_id == str(home_team.get('id')): h_roster = team_list
                        elif t_id == str(away_team.get('id')): a_roster = team_list
                
                if h_roster or a_roster:
                    self.full_rows.append(StatsListEntry("", "", "", self.theme))
                    self.full_rows.append(StatsListEntry("LINEUPS", "HOME", "AWAY", self.theme))
                    max_len = max(len(h_roster), len(a_roster))
                    for i in range(max_len):
                        h_p = h_roster[i] if i < len(h_roster) else ""
                        a_p = a_roster[i] if i < len(a_roster) else ""
                        self.full_rows.append(RosterListEntry(h_p, a_p, self.theme))

                # 5. Match Officials
                try:
                    game_info = data.get('gameInfo', {})
                    officials = game_info.get('officials', [])
                    if officials:
                        self.full_rows.append(StatsListEntry("", "", "", self.theme))
                        self.full_rows.append(TextListEntry("MATCH OFFICIALS", self.theme, is_header=True))
                        for official in officials:
                            name = official.get('displayName', '') or official.get('fullName', '')
                            position = official.get('position', {}).get('displayName', '') or official.get('type', '')
                            if name:
                                off_txt = u"\u2022 {}: {}".format(position, name) if position else u"\u2022 {}".format(name)
                                self.full_rows.append(TextListEntry(off_txt, self.theme, align="left"))
                except: pass

                # 6. Game Notes / Key Facts
                try:
                    key_events = data.get('keyEvents', [])
                    if key_events:
                        self.full_rows.append(StatsListEntry("", "", "", self.theme))
                        self.full_rows.append(TextListEntry("KEY MOMENTS", self.theme, is_header=True))
                        for event in key_events[:8]:
                            clock = event.get('clock', {}).get('displayValue', '')
                            evt_type = event.get('type', {}).get('text', '')
                            evt_text = event.get('text', '') or evt_type
                            if evt_text:
                                key_txt = u"\u23F1 {} - {}".format(clock, evt_text) if clock else u"\u2022 {}".format(evt_text)
                                wrapped = wrap_text(key_txt, max_chars=130)
                                for line in wrapped:
                                    self.full_rows.append(TextListEntry(line, self.theme, align="left"))
                except: pass

                # 7. Head-to-Head / Previous Meetings
                try:
                    h2h = data.get('headToHead', [])
                    if h2h:
                        self.full_rows.append(StatsListEntry("", "", "", self.theme))
                        self.full_rows.append(TextListEntry("HEAD TO HEAD", self.theme, is_header=True))
                        for meeting in h2h[:5]:
                            date = meeting.get('date', '')[:10] if meeting.get('date') else ''
                            home_t = meeting.get('homeTeam', {}).get('displayName', 'Home')
                            away_t = meeting.get('awayTeam', {}).get('displayName', 'Away')
                            h_s = meeting.get('homeTeam', {}).get('score', '0')
                            a_s = meeting.get('awayTeam', {}).get('score', '0')
                            h2h_txt = "{}: {} {} - {} {}".format(date, home_t, h_s, a_s, away_t)
                            self.full_rows.append(TextListEntry(h2h_txt, self.theme, align="left"))
                except: pass

                # 8. News / Articles (for live/post match)
                try:
                    news_items = data.get('news', {}).get('articles', [])
                    if not news_items: news_items = data.get('articles', [])
                    if news_items:
                        self.full_rows.append(StatsListEntry("", "", "", self.theme))
                        self.full_rows.append(TextListEntry("MATCH NEWS", self.theme, is_header=True))
                        count = 0
                        for article in news_items:
                            if count >= 3: break
                            headline = article.get('headline', '')
                            if headline:
                                wrapped = wrap_text(headline, max_chars=130)
                                for line in wrapped:
                                    self.full_rows.append(TextListEntry(line, self.theme, align="left"))
                                self.full_rows.append(TextListEntry("", self.theme))
                                count += 1
                except: pass

            self.current_page = 0
            self.update_display()

        except Exception as e:
            self["loading"].setText("Data Error: " + str(e))
            self["loading"].show()

    # ==========================================================
    # RACING EVENTS (F1, NASCAR, IndyCar)
    # ==========================================================
    def parse_racing_event(self, data, league_name, game_status):
        """Parse and display racing event details (F1, NASCAR, IndyCar)"""
        try:
            header = data.get('header', {})
            event_name = header.get('competitions', [{}])[0].get('name', '') or data.get('name', '') or league_name
            
            # Set header display
            self["match_title"].setText(league_name if league_name else "RACE")
            self["h_name"].setText(event_name)
            self["stadium_name"].setText("")
            
            # Try to get venue/track info
            try:
                venue = data.get('gameInfo', {}).get('venue', {})
                track_name = venue.get('fullName', '') or venue.get('name', '')
                if track_name:
                    self["stadium_name"].setText(track_name)
            except: pass
            
            # Download series logo if available
            try:
                league_info = header.get('league', {})
                logo_url = league_info.get('logos', [{}])[0].get('href', '')
                if logo_url:
                    self.download_logo(logo_url, "h_logo")
            except: pass
            
            # Status section
            status_txt = "Scheduled"
            if game_status == 'in': status_txt = "LIVE - In Progress"
            elif game_status == 'post': status_txt = "Finished"
            self.full_rows.append(TextListEntry(u"\U0001F3C1 STATUS: " + status_txt, self.theme, is_header=True))
            self.full_rows.append(TextListEntry("", self.theme))
            
            # Driver Standings / Results
            try:
                competitors = header.get('competitions', [{}])[0].get('competitors', [])
                if competitors:
                    if game_status == 'post':
                        self.full_rows.append(TextListEntry(u"\U0001F3C6 RACE RESULTS", self.theme, is_header=True))
                    else:
                        self.full_rows.append(TextListEntry(u"\U0001F3CE DRIVER STANDINGS", self.theme, is_header=True))
                    
                    for i, driver in enumerate(competitors[:20]):
                        rank = driver.get('rank', i + 1)
                        name = driver.get('athlete', {}).get('displayName', '') or driver.get('team', {}).get('displayName', 'Driver')
                        points = driver.get('points', driver.get('score', ''))
                        status = driver.get('status', '')
                        
                        driver_txt = u"#{} {}".format(rank, name)
                        if points: driver_txt += " - {} pts".format(points)
                        if status and status.lower() not in ['active', 'running']: driver_txt += " ({})".format(status)
                        
                        self.full_rows.append(TextListEntry(driver_txt, self.theme, align="left"))
            except: 
                self.full_rows.append(TextListEntry("No driver data available", self.theme))
            
            # Race Schedule Info
            try:
                schedule = data.get('schedule', [])
                if schedule:
                    self.full_rows.append(TextListEntry("", self.theme))
                    self.full_rows.append(TextListEntry(u"\U0001F4C5 SCHEDULE", self.theme, is_header=True))
                    for event in schedule[:5]:
                        name = event.get('name', 'Session')
                        date = event.get('date', '')[:10] if event.get('date') else ''
                        time_str = get_local_time_str(event.get('date', ''))
                        self.full_rows.append(TextListEntry("{}: {}".format(name, time_str), self.theme, align="left"))
            except: pass
            
            # News
            self._add_news_section(data)
            
        except Exception as e:
            self.full_rows.append(TextListEntry("Error loading race data: " + str(e), self.theme))
        
        self.current_page = 0
        self.update_display()

    # ==========================================================
    # GOLF EVENTS (PGA, LPGA, Euro Tour)
    # ==========================================================
    def parse_golf_event(self, data, league_name, game_status):
        """Parse and display golf tournament details"""
        try:
            header = data.get('header', {})
            event_name = header.get('competitions', [{}])[0].get('name', '') or data.get('name', '') or league_name
            
            # Set header display
            self["match_title"].setText(league_name if league_name else "TOURNAMENT")
            self["h_name"].setText(event_name)
            
            # Course info
            try:
                venue = data.get('gameInfo', {}).get('venue', {})
                course_name = venue.get('fullName', '') or venue.get('name', '')
                if course_name:
                    self["stadium_name"].setText(course_name)
            except: pass
            
            # Download tour logo
            try:
                league_info = header.get('league', {})
                logo_url = league_info.get('logos', [{}])[0].get('href', '')
                if logo_url:
                    self.download_logo(logo_url, "h_logo")
            except: pass
            
            # Status
            status_txt = "Scheduled"
            if game_status == 'in': status_txt = "LIVE - Round in Progress"
            elif game_status == 'post': status_txt = "Tournament Complete"
            self.full_rows.append(TextListEntry(u"\u26F3 STATUS: " + status_txt, self.theme, is_header=True))
            self.full_rows.append(TextListEntry("", self.theme))
            
            # Leaderboard
            try:
                competitors = header.get('competitions', [{}])[0].get('competitors', [])
                if competitors:
                    self.full_rows.append(TextListEntry(u"\U0001F3C6 LEADERBOARD", self.theme, is_header=True))
                    
                    for i, player in enumerate(competitors[:15]):
                        rank = player.get('rank', player.get('position', i + 1))
                        name = player.get('athlete', {}).get('displayName', 'Player')
                        score = player.get('score', player.get('linescores', [{}])[-1].get('value', '')) if player.get('linescores') else player.get('score', 'E')
                        thru = player.get('status', '')
                        
                        # Format score with +/- 
                        score_str = str(score) if score else "E"
                        if score_str.isdigit() or (score_str.startswith('-') and score_str[1:].isdigit()):
                            s = int(score_str)
                            if s > 0: score_str = "+" + str(s)
                            elif s == 0: score_str = "E"
                        
                        player_txt = u"{}. {} ({})".format(rank, name, score_str)
                        if thru and 'thru' in str(thru).lower(): player_txt += " " + str(thru)
                        
                        self.full_rows.append(TextListEntry(player_txt, self.theme, align="left"))
            except:
                self.full_rows.append(TextListEntry("No leaderboard data available", self.theme))
            
            # Round info / Cut line
            try:
                tournament_info = data.get('header', {}).get('competitions', [{}])[0]
                cut_line = tournament_info.get('cutLine', {}).get('score', '')
                if cut_line:
                    self.full_rows.append(TextListEntry("", self.theme))
                    self.full_rows.append(TextListEntry(u"\u2702 CUT LINE: {}".format(cut_line), self.theme, is_header=True))
            except: pass
            
            # News
            self._add_news_section(data)
            
        except Exception as e:
            self.full_rows.append(TextListEntry("Error loading golf data: " + str(e), self.theme))
        
        self.current_page = 0
        self.update_display()

    # ==========================================================
    # TENNIS EVENTS (ATP, WTA)
    # ==========================================================
    def parse_tennis_event(self, data, league_name, game_status, home_team, away_team):
        """Parse and display tennis match/tournament details"""
        try:
            header = data.get('header', {})
            competitions = header.get('competitions', [])
            if not competitions:
                competitions = data.get('competitions', [])
            
            first_comp = competitions[0] if competitions else {}
            event_name = first_comp.get('name', '') or data.get('name', '') or data.get('shortName', '') or league_name
            
            # Try to get competitors from header first, then from competitions
            competitors = first_comp.get('competitors', [])
            if not competitors and 'boxscore' in data:
                competitors = data.get('boxscore', {}).get('players', [])
            
            is_match = len(competitors) >= 2
            
            # Download league logo
            try:
                league_info = header.get('league', {})
                logo_url = league_info.get('logos', [{}])[0].get('href', '')
                if logo_url:
                    self.download_logo(logo_url, "h_logo")
            except: pass
            
            if is_match:
                # Head-to-head match display - extract player names
                player1_name = "Player 1"
                player2_name = "Player 2"
                p1 = {}; p2 = {}
                
                try:
                    p1 = competitors[0]
                    p2 = competitors[1]
                    # Try athlete name first, then team name, then generic name
                    player1_name = p1.get('athlete', {}).get('displayName') or p1.get('athlete', {}).get('shortDisplayName') or p1.get('team', {}).get('displayName') or p1.get('name', 'Player 1')
                    player2_name = p2.get('athlete', {}).get('displayName') or p2.get('athlete', {}).get('shortDisplayName') or p2.get('team', {}).get('displayName') or p2.get('name', 'Player 2')
                except: pass
                
                self["match_title"].setText(league_name if league_name else "TENNIS MATCH")
                self["h_name"].setText(player1_name)
                self["a_name"].setText(player2_name)
                self["stadium_name"].setText("")
                
                # Download athlete logos (flags)
                try:
                    f1 = p1.get('athlete', {}).get('flag', {}).get('href')
                    f2 = p2.get('athlete', {}).get('flag', {}).get('href')
                    if f1: self.download_logo(f1, "h_logo")
                    if f2: self.download_logo(f2, "a_logo")
                except: pass
                
                # Set scores
                try:
                    score1 = p1.get('score', '0')
                    score2 = p2.get('score', '0')
                    self["h_score"].setText(str(score1))
                    self["a_score"].setText(str(score2))
                    self["h_score"].show(); self["a_score"].show(); self["score_sep"].show()
                    
                    linescores1 = p1.get('linescores', [])
                    linescores2 = p2.get('linescores', [])
                    
                    # Display set scores
                    sets_txt = ""
                    for ls1, ls2 in zip(linescores1, linescores2):
                        s1 = ls1.get('value', 0)
                        s2 = ls2.get('value', 0)
                        sets_txt += "{}-{} ".format(s1, s2)
                    
                    if sets_txt:
                        self["stadium_name"].setText("Sets: " + sets_txt.strip())
                except: pass
                
            else:
                # Tournament display
                self["match_title"].setText(league_name if league_name else "TENNIS TOURNAMENT")
                self["h_name"].setText(event_name)
                
                # Try to get venue
                try:
                    venue = data.get('gameInfo', {}).get('venue', {})
                    v_name = venue.get('fullName', '')
                    if v_name:
                        self["stadium_name"].setText(v_name)
                except: pass
            
            # Status
            status_txt = "Scheduled"
            if game_status == 'in': status_txt = "LIVE - In Progress"
            elif game_status == 'post': status_txt = "Completed"
            self.full_rows.append(TextListEntry(u"\U0001F3BE STATUS: " + status_txt, self.theme, is_header=True))
            self.full_rows.append(TextListEntry("", self.theme))
            
            if is_match and competitors:
                # Match details
                self.full_rows.append(TextListEntry(u"\U0001F3C6 MATCH INFO", self.theme, is_header=True))
                
                for i, comp in enumerate(competitors[:2]):
                    try:
                        name = comp.get('athlete', {}).get('displayName') or comp.get('name', 'Player')
                        rank = comp.get('rank', '') or comp.get('athlete', {}).get('rank', '')
                        country = comp.get('athlete', {}).get('flag', {}).get('alt', '')
                        seed = comp.get('seed', '')
                        winner = comp.get('winner', False)
                        
                        player_txt = name
                        if rank: player_txt += " (Rank #{})".format(rank)
                        if seed: player_txt += " [{}]".format(seed)
                        if country: player_txt += " - {}".format(country)
                        if winner: player_txt += " WINNER"
                        
                        self.full_rows.append(TextListEntry(player_txt, self.theme, align="left"))
                    except: 
                        self.full_rows.append(TextListEntry("Player {}".format(i+1), self.theme, align="left"))
            elif competitors:
                # Tournament draws / results
                self.full_rows.append(TextListEntry(u"\U0001F3C6 TOURNAMENT DRAW", self.theme, is_header=True))
                for comp in competitors[:15]:
                    try:
                        name = comp.get('athlete', {}).get('displayName') or comp.get('name', 'Player')
                        seed = comp.get('seed', '')
                        status = comp.get('status', '')
                        
                        player_txt = name
                        if seed: player_txt = "[{}] {}".format(seed, name)
                        if status: player_txt += " - {}".format(status)
                        
                        self.full_rows.append(TextListEntry(player_txt, self.theme, align="left"))
                    except: continue
            else:
                self.full_rows.append(TextListEntry("No match data available", self.theme))
            
            # News
            self._add_news_section(data)
            
        except Exception as e:
            self.full_rows.append(TextListEntry("Error loading tennis data: " + str(e), self.theme))
        
        self.current_page = 0
        self.update_display()

    # ==========================================================
    # COMBAT SPORTS (UFC/MMA, Boxing)
    # ==========================================================
    def parse_combat_event(self, data, league_name, game_status):
        """Parse and display combat sports event details (UFC, Boxing)"""
        try:
            header = data.get('header', {})
            event_name = header.get('competitions', [{}])[0].get('name', '') or data.get('name', '') or league_name
            
            self["match_title"].setText(league_name if league_name else "FIGHT NIGHT")
            self["h_name"].setText(event_name)
            
            # Venue
            try:
                venue = data.get('gameInfo', {}).get('venue', {})
                v_name = venue.get('fullName', '')
                v_city = venue.get('address', {}).get('city', '')
                loc = v_name
                if v_city: loc += " - " + v_city
                if loc: self["stadium_name"].setText(loc)
            except: pass
            
            # Download promotion logo
            try:
                league_info = header.get('league', {})
                logo_url = league_info.get('logos', [{}])[0].get('href', '')
                if logo_url:
                    self.download_logo(logo_url, "h_logo")
            except: pass
            
            # Status
            status_txt = "Scheduled"
            if game_status == 'in': status_txt = "LIVE - In Progress"
            elif game_status == 'post': status_txt = "Event Complete"
            self.full_rows.append(TextListEntry(u"\U0001F94A STATUS: " + status_txt, self.theme, is_header=True))
            self.full_rows.append(TextListEntry("", self.theme))
            
            # Fight Card
            try:
                competitions = header.get('competitions', [])
                if not competitions:
                    competitions = data.get('competitions', [])
                
                if competitions:
                    self.full_rows.append(TextListEntry(u"\U0001F525 FIGHT CARD", self.theme, is_header=True))
                    
                    for fight in competitions[:10]:
                        competitors = fight.get('competitors', [])
                        fight_type = fight.get('type', {}).get('text', '') or fight.get('name', 'Bout')
                        
                        if len(competitors) >= 2:
                            f1 = competitors[0]
                            f2 = competitors[1]
                            name1 = f1.get('athlete', {}).get('displayName', f1.get('name', 'Fighter 1'))
                            name2 = f2.get('athlete', {}).get('displayName', f2.get('name', 'Fighter 2'))
                            record1 = f1.get('record', '')
                            record2 = f2.get('record', '')
                            
                            fight_txt = u"\u2694 {} vs {}".format(name1, name2)
                            self.full_rows.append(TextListEntry(fight_txt, self.theme, align="left"))
                            
                            if record1 or record2:
                                records = "   ({}) vs ({})".format(record1 or '-', record2 or '-')
                                self.full_rows.append(TextListEntry(records, self.theme, align="left"))
                            
                            if fight_type and 'main' in fight_type.lower():
                                self.full_rows.append(TextListEntry("   [MAIN EVENT]", self.theme, align="left"))
                            elif fight_type and 'co-main' in fight_type.lower():
                                self.full_rows.append(TextListEntry("   [CO-MAIN EVENT]", self.theme, align="left"))
                        
                        self.full_rows.append(TextListEntry("", self.theme))
            except:
                self.full_rows.append(TextListEntry("No fight card data available", self.theme))
            
            # Betting / Odds
            try:
                odds = data.get('pickcenter', [])
                if odds:
                    self.full_rows.append(TextListEntry(u"\U0001F4B0 ODDS", self.theme, is_header=True))
                    for odd in odds[:3]:
                        provider = odd.get('provider', {}).get('name', 'Odds')
                        details = odd.get('details', 'N/A')
                        self.full_rows.append(TextListEntry("{}: {}".format(provider, details), self.theme, align="left"))
            except: pass
            
            # News
            self._add_news_section(data)
            
        except Exception as e:
            self.full_rows.append(TextListEntry("Error loading fight data: " + str(e), self.theme))
        
        self.current_page = 0
        self.update_display()

    # ==========================================================
    # CRICKET EVENTS (IPL, Test, ODI, T20)
    # ==========================================================
    def parse_cricket_event(self, data, league_name, game_status):
        """Parse and display cricket match details"""
        try:
            header = data.get('header', {})
            competitions = header.get('competitions', [{}])[0]
            
            # Set header display
            match_desc = competitions.get('status', {}).get('type', {}).get('description', '')
            self["match_title"].setText(match_desc if match_desc else (league_name if league_name else "CRICKET"))
            
            # Teams and Score extraction
            competitors = competitions.get('competitors', [])
            home_comp = next((c for c in competitors if c.get('homeAway') == 'home'), {})
            away_comp = next((c for c in competitors if c.get('homeAway') == 'away'), {})
            
            self["h_name"].setText(home_comp.get('team', {}).get('displayName', 'Home'))
            self["a_name"].setText(away_comp.get('team', {}).get('displayName', 'Away'))
            self["h_score"].setText(home_comp.get('score', ''))
            self["a_score"].setText(away_comp.get('score', ''))
            
            # Match Status / Note
            status_txt = competitions.get('status', {}).get('type', {}).get('shortDetail', '')
            note = competitions.get('notes', [{}])[0].get('headline', '')
            
            self.full_rows.append(TextListEntry(u"\u26BE STATUS: " + status_txt, self.theme, is_header=True))
            if note:
                self.full_rows.append(TextListEntry(note, self.theme, align="left"))
            self.full_rows.append(TextListEntry("", self.theme))

            # Full Innings Scores
            # Cricket scores are often "182/4 (20)"
            # We can list each innings if available
            try:
                self.full_rows.append(TextListEntry(u"\U0001F4CB INNINGS SUMMARY", self.theme, is_header=True))
                # Try to get innings from linescores
                for comp in competitors:
                    team_name = comp.get('team', {}).get('abbreviation', 'Team')
                    score = comp.get('score', '')
                    linescores = comp.get('linescores', [])
                    
                    # If linescores exist (Test match innings), list them
                    if len(linescores) > 1:
                        txt = "{}: ".format(team_name)
                        innings_txt = []
                        for idx, inn in enumerate(linescores):
                            val = inn.get('displayValue', inn.get('value', ''))
                            if val: innings_txt.append(val)
                        txt += " & ".join(innings_txt)
                        self.full_rows.append(TextListEntry(txt, self.theme, align="left"))
                    else:
                        # Limited overs - just show main score
                        # Often in 'linescores'[0] or just 'score'
                        overs = comp.get('linescores', [{}])[-1].get('overs', '')
                        if overs: score += " ({} ov)".format(overs)
                        self.full_rows.append(TextListEntry("{}: {}".format(team_name, score), self.theme, align="left"))
            except: pass

            # Batting/Bowling Leaders (if available)
            try:
                leaders = competitions.get('leaders', [])
                if leaders:
                    self.full_rows.append(TextListEntry("", self.theme))
                    self.full_rows.append(TextListEntry(u"\U0001F3C6 TOP PERFORMERS", self.theme, is_header=True))
                    
                    for leader_group in leaders:
                        name = leader_group.get('displayName', '') # e.g. "Batting", "Bowling"
                        self.full_rows.append(TextListEntry(name + ":", self.theme, align="left"))
                        for player in leader_group.get('leaders', [])[:2]:
                            p_name = player.get('athlete', {}).get('displayName', 'Player')
                            p_val = player.get('displayValue', '')
                            self.full_rows.append(TextListEntry("  {} - {}".format(p_name, p_val), self.theme, align="left"))
            except: pass
            
            # News
            self._add_news_section(data)
            
        except Exception as e:
            self.full_rows.append(TextListEntry("Error loading cricket data: " + str(e), self.theme))
            
        self.current_page = 0
        self.update_display()


    # ==========================================================
    # RUGBY EVENTS (Union, League)
    # ==========================================================
    def parse_rugby_event(self, data, league_name, game_status):
        """Parse and display rugby match details"""
        try:
            # Similar to team sports but with specific stats
            header = data.get('header', {})
            competitions = header.get('competitions', [{}])[0]
            
            status_txt = competitions.get('status', {}).get('type', {}).get('shortDetail', '')
            self["match_title"].setText(league_name if league_name else "RUGBY")
            
            # Logos
            try:
                sport_cdn = global_sports_monitor.get_cdn_sport_name(league_name)
                h_id = data.get('boxscore', {}).get('teams', [{}])[0].get('team', {}).get('id', '')
                a_id = data.get('boxscore', {}).get('teams', [{}])[1].get('team', {}).get('id', '')
                if h_id: self.download_logo("https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png".format(sport_cdn, h_id), "h_logo")
                if a_id: self.download_logo("https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png".format(sport_cdn, a_id), "a_logo")
            except: pass

            self.full_rows.append(TextListEntry(u"\U0001F3C9 STATUS: " + status_txt, self.theme, is_header=True))
            self.full_rows.append(TextListEntry("", self.theme))
            
            # Try to find scoring events (Tries)
            # Rugby often has 'scoringPlays' in the JSON details
            try:
                details = data.get('header', {}).get('competitions', [{}])[0].get('details', [])
                # Or sometimes under boxscore
                
                # Check for key stats if available (Tries, Pens)
                boxscore_teams = data.get('boxscore', {}).get('teams', [])
                if boxscore_teams:
                    self.full_rows.append(TextListEntry(u"\U0001F4CA TEAM STATS", self.theme, is_header=True))
                    
                    # Extract Tries, Cons, Pens, Cards from stats
                    for team in boxscore_teams:
                        t_name = team.get('team', {}).get('abbreviation', 'Team')
                        stats = team.get('statistics', [])
                        
                        # Helper to find stat
                        def get_stat(name):
                            for s in stats:
                                if s.get('name') == name: return s.get('displayValue')
                            return None
                            
                        # Rugby stats structure varies, trying common keys
                        tries = get_stat('tries') or get_stat('triesScored')
                        if tries: self.full_rows.append(TextListEntry("{}: {} Tries".format(t_name, tries), self.theme, align="left"))
                        
                        rc = get_stat('redCards')
                        yc = get_stat('yellowCards')
                        if rc and rc != '0': self.full_rows.append(TextListEntry("  \u26D4 Red Cards: {}".format(rc), self.theme, align="left"))
                        if yc and yc != '0': self.full_rows.append(TextListEntry("  \u25FB Yellow Cards: {}".format(yc), self.theme, align="left"))
            except: pass
            
            # News
            self._add_news_section(data)
            
        except Exception as e:
            self.full_rows.append(TextListEntry("Error loading rugby data: " + str(e), self.theme))
            
        self.current_page = 0
        self.update_display()

    # ==========================================================
    # HELPER: Add News Section
    # ==========================================================
    def _add_news_section(self, data):
        """Helper to add news/articles section for any sport type"""
        try:
            news_items = data.get('news', {}).get('articles', [])
            if not news_items: news_items = data.get('articles', [])
            if news_items:
                self.full_rows.append(TextListEntry("", self.theme))
                self.full_rows.append(TextListEntry(u"\U0001F4F0 NEWS", self.theme, is_header=True))
                count = 0
                for article in news_items:
                    if count >= 3: break
                    headline = article.get('headline', '')
                    if headline:
                        wrapped = wrap_text(headline, max_chars=130)
                        for line in wrapped:
                            self.full_rows.append(TextListEntry(line, self.theme, align="left"))
                        self.full_rows.append(TextListEntry("", self.theme))
                        count += 1
        except: pass

# ==============================================================================
# GOAL TOAST
# ==============================================================================
