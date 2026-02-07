import os
from ..common import *
from ..globals import global_sports_monitor

class SimpleSportsMiniBar2(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        
        # 1. Register
        global_sports_monitor.register_callback(self.on_data_ready)
        
        self.logo_path = "/tmp/simplysports/logos/"
        if not os.path.exists(self.logo_path):
            try: os.makedirs(self.logo_path)
            except: pass

        d_size = getDesktop(0).size()
        width = d_size.width(); height = d_size.height()
        
        if width > 1280:
            bar_h = 65; y_sc = 39; bar_y = height - bar_h + 11; font_lg = "Regular;25"; font_nm = "Regular;34"; font_sm = "Regular;22"; font_sc = "Regular;18"; logo_s = 35
            x_league=20; w_league=363; x_home_name=393; w_home_name=467; x_h_logo=875
            x_score=920; w_score=140; x_a_logo=1065; x_away_name=1115; w_away_name=490
            x_status=1615; w_status=90; x_time=1707; w_time=210
        else:
            bar_h = 57; y_sc = 33; bar_y = height - bar_h + 11; font_lg = "Regular;21"; font_nm = "Regular;28"; font_sm = "Regular;18"; font_sc = "Regular;16"; logo_s = 30
            x_league=0; w_league=253; x_home_name=263; w_home_name=257; x_h_logo=540
            x_score=580; w_score=100; x_a_logo=685; x_away_name=740; w_away_name=260
            x_status=1010; w_status=80; x_time=1092; w_time=175
            
        if global_sports_monitor.theme_mode == "ucl":
            self.skin = """<screen position="0,{y}" size="{w},{h}" title="Sports Ticker Bottom" backgroundColor="#40000000" flags="wfNoBorder"><eLabel position="0,0" size="{w},{h}" backgroundColor="#c00e1e5b" zPosition="0" /><eLabel position="0,0" size="{w},2" backgroundColor="#00ffff" zPosition="1" /><widget name="lbl_league" position="{xl},0" size="{wl},{h}" font="{fl}" foregroundColor="#00ffff" backgroundColor="#c00e1e5b" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_home" position="{xh},0" size="{wh},44" font="{fn}" foregroundColor="#ffffff" backgroundColor="#c00e1e5b" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="lbl_home_sc" position="{xh},{ysc}" size="{wh},24" font="{fsc}" foregroundColor="#cccccc" backgroundColor="#c00e1e5b" transparent="1" halign="right" valign="top" zPosition="2" /><widget name="h_logo" position="{xhl},4" size="{ls},{ls}" alphatest="blend" scale="1" zPosition="2" /><eLabel position="{xs},0" size="{ws},{h}" backgroundColor="#ffffff" zPosition="1" /><widget name="lbl_score" position="{xs},0" size="{ws},{h}" font="{fl}" foregroundColor="#0e1e5b" backgroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="3" /><widget name="a_logo" position="{xal},4" size="{ls},{ls}" alphatest="blend" scale="1" zPosition="2" /><widget name="lbl_away" position="{xa},0" size="{wa},44" font="{fn}" foregroundColor="#ffffff" backgroundColor="#c00e1e5b" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_away_sc" position="{xa},{ysc}" size="{wa},24" font="{fsc}" foregroundColor="#cccccc" backgroundColor="#c00e1e5b" transparent="1" halign="left" valign="top" zPosition="2" /><widget name="lbl_status" position="{xst},0" size="{wst},{h}" font="{fs}" foregroundColor="#ffffff" backgroundColor="#c00e1e5b" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="lbl_time" position="{xt},0" size="{wt},{h}" font="{fs}" foregroundColor="#00ffff" backgroundColor="#c00e1e5b" transparent="1" halign="right" valign="center" zPosition="2" /></screen>""".format(y=bar_y, w=width, h=bar_h, fl=font_lg, fn=font_nm, fs=font_sm, fsc=font_sc, ls=logo_s, xl=x_league, wl=w_league, xh=x_home_name, wh=w_home_name, xhl=x_h_logo, xs=x_score, ws=w_score, xst=x_status, wst=w_status, xal=x_a_logo, xa=x_away_name, wa=w_away_name, xt=x_time, wt=w_time, ysc=y_sc-2)
        else:
            self.skin = """<screen position="0,{y}" size="{w},{h}" title="Sports Ticker Bottom" backgroundColor="#40000000" flags="wfNoBorder"><eLabel position="0,0" size="{w},{h}" backgroundColor="#c0331900" zPosition="0" /><eLabel position="0,0" size="5,{h}" backgroundColor="#E90052" zPosition="1" /><eLabel position="{rend},{h}" size="5,{h}" backgroundColor="#F6B900" zPosition="1" /><widget name="lbl_league" position="{xl},0" size="{wl},{h}" font="{fl}" foregroundColor="#FFD700" backgroundColor="#c0331900" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_home" position="{xh},0" size="{wh},38" font="{fn}" foregroundColor="#FFFFFF" backgroundColor="#c0331900" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="lbl_home_sc" position="{xh},{ysc}" size="{wh},24" font="{fsc}" foregroundColor="#cccccc" backgroundColor="#c0331900" transparent="1" halign="right" valign="top" zPosition="2" /><widget name="h_logo" position="{xhl},4" size="{ls},{ls}" alphatest="blend" scale="1" zPosition="2" /><eLabel position="{xs},0" size="{ws},{h}" backgroundColor="#00FF85" zPosition="1" /><widget name="lbl_score" position="{xs},0" size="{ws},{h}" font="{fl}" foregroundColor="#000000" backgroundColor="#00FF85" transparent="1" halign="center" valign="center" zPosition="3" /><widget name="a_logo" position="{xal},4" size="{ls},{ls}" alphatest="blend" scale="1" zPosition="2" /><widget name="lbl_away" position="{xa},0" size="{wa},38" font="{fn}" foregroundColor="#FFFFFF" backgroundColor="#c0331900" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_away_sc" position="{xa},{ysc}" size="{wa},24" font="{fsc}" foregroundColor="#cccccc" backgroundColor="#c0331900" transparent="1" halign="left" valign="top" zPosition="2" /><widget name="lbl_status" position="{xst},0" size="{wst},{h}" font="{fs}" foregroundColor="#FFFFFF" backgroundColor="#c0331900" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="lbl_time" position="{xt},0" size="{wt},{h}" font="{fs}" foregroundColor="#00FF85" backgroundColor="#c0331900" transparent="1" halign="right" valign="center" zPosition="2" /></screen>""".format(y=bar_y-6, w=width, h=bar_h, rend=width-5, fl=font_lg, fn=font_nm, fs=font_sm, fsc=font_sc, ls=logo_s, xl=x_league, wl=w_league, xh=x_home_name, wh=w_home_name, xhl=x_h_logo, xs=x_score, ws=w_score, xst=x_status, wst=w_status, xal=x_a_logo, xa=x_away_name, wa=w_away_name, xt=x_time, wt=w_time, ysc=y_sc)

        self["lbl_league"] = Label(""); self["lbl_home"] = Label(""); self["lbl_score"] = Label("")
        self["lbl_away"] = Label(""); self["lbl_status"] = Label(""); self["lbl_time"] = Label("")
        self["lbl_home_sc"] = Label(""); self["lbl_away_sc"] = Label("")
        self["h_logo"] = Pixmap(); self["a_logo"] = Pixmap()
        self["h_logo"].hide(); self["a_logo"].hide()
        self.matches = []; self.current_match_idx = 0
        self.league_colors = {"ENG": 0x00ff85, "ESP": 0xff4b4b, "ITA": 0x008fd7, "GER": 0xd3010c, "FRA": 0xdae025, "UCL": 0x00ffff, "UEL": 0xff8800, "NBA": 0xC9082A, "NFL": 0x013369}
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {"cancel": self.close, "green": self.close, "yellow": self.toggle_filter_mini}, -1)
        self.ticker_timer = eTimer(); safe_connect(self.ticker_timer, self.show_next_match)
        self.refresh_timer = eTimer(); safe_connect(self.refresh_timer, self.refresh_data)
        self.onLayoutFinish.append(self.start_all_timers)
        self.onClose.append(self.cleanup)

    def cleanup(self):
        global_sports_monitor.unregister_callback(self.on_data_ready)

    def start_all_timers(self):
        self.parse_json()
        global_sports_monitor.check_goals()
        self.refresh_timer.start(60000)

    def on_data_ready(self, success):
        self.parse_json()

    def toggle_filter_mini(self): 
        global_sports_monitor.toggle_filter()
        self.parse_json()
            
    def refresh_data(self): 
        global_sports_monitor.check_goals()

    def get_scorers_string(self, event, home_id, away_id):
        # ... (Same implementation as previously provided) ...
        # Copied for completeness
        h_scorers = []; a_scorers = []
        try:
            details = event.get('competitions', [{}])[0].get('details', [])
            if not details: details = event.get('header', {}).get('competitions', [{}])[0].get('details', [])
            if details:
                for play in details:
                    text_desc = play.get('type', {}).get('text', '').lower()
                    is_scoring = play.get('scoringPlay', False) or "goal" in text_desc or "score" in text_desc or "touchdown" in text_desc
                    if is_scoring and "disallowed" not in text_desc:
                        scorer = ""
                        athletes = play.get('athletesInvolved', [])
                        if athletes: scorer = athletes[0].get('shortName') or athletes[0].get('displayName')
                        elif play.get('participants'): scorer = play['participants'][0].get('athlete', {}).get('shortName')
                        if not scorer:
                            clean = play.get('type', {}).get('text', '')
                            # NHL Specific: "Goal - Name" or just "Name" in some fields
                            if "Goal - " in clean: scorer = clean.split("Goal - ")[1].split('(')[0].strip()
                            elif "Gamewinner - " in clean: scorer = clean.split("Gamewinner - ")[1].split('(')[0].strip()
                            elif "Short Handed Goal - " in clean: scorer = clean.split("Short Handed Goal - ")[1].split('(')[0].strip()
                            elif "Power Play Goal - " in clean: scorer = clean.split("Power Play Goal - ")[1].split('(')[0].strip()
                        if scorer:
                            # Add goal time if available
                            g_time = play.get('clock', {}).get('displayValue', '')
                            if g_time: scorer = "{} {}".format(scorer, g_time)
                            
                            t_id = str(play.get('team', {}).get('id', ''))
                            if t_id == str(home_id): h_scorers.append(scorer)
                            elif t_id == str(away_id): a_scorers.append(scorer)
        except: pass
        def format_list(lst):
            if not lst: return ""
            seen = set(); unique = [x for x in lst if not (x in seen or seen.add(x))]
            final_str = ", ".join(unique)
            if len(final_str) > 35:
                # If too long, try shortening names but ALWAYS keep Name + Time
                short_list = []
                for n in unique:
                    parts = n.split(' ')
                    if len(parts) >= 2:
                        # Keep last name and time
                        short_list.append("{} {}".format(parts[-2], parts[-1]))
                    else:
                        short_list.append(n)
                final_str = ", ".join(short_list)
            return final_str
        return format_list(h_scorers), format_list(a_scorers)

    def parse_json(self):
        events = global_sports_monitor.cached_events
        new_matches = []
        if not events:
            # If we already have matches and an update is in progress, keep old matches to avoid flicker
            if self.matches and "Loading" in global_sports_monitor.status_message:
                return
            msg = global_sports_monitor.status_message or "Loading..."
            self.matches = [{'league': "SimplySports", 'color': 0xffffff, 'home': msg, 'away': "", 'score': "", 'status': "", 'time': "", 'h_png': None, 'a_png': None}]
            self.show_next_match()
            return
            
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d"); tom_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        # LOGO CHECKING
        tmp_path = "/tmp/simplysports/logos/"
        
        for event in events:
            status = event.get('status', {}); state = status.get('type', {}).get('state', 'pre')
            clock = status.get('displayClock', '00:00')
            if ":" in clock: clock = clock.split(':')[0] + "'"
            local_time = get_local_time_str(event.get('date', ''))
            league_name = event.get('league_name', '')
            mode = global_sports_monitor.filter_mode; ev_date = event.get('date', '')[:10]
            if mode == 0 and state != 'in': continue
            # Fix: Always show LIVE matches in "Today" view, even if UTC date was yesterday
            if mode == 2 and ev_date != today_str and state != 'in': continue
            if mode == 3 and ev_date != tom_str: continue
            
            # Use logo URLs and IDs directly from event (set by process_events_data)
            h_url = event.get('h_logo_url', '')
            a_url = event.get('a_logo_url', '')
            h_id = event.get('h_logo_id', '') or '0'
            a_id = event.get('a_logo_id', '') or '0'
            
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            
            # Detect sport type for proper name extraction
            league_url = event.get('league_url', '')
            event_sport_type = get_sport_type(league_url)
            
            if len(comps) > 2:
                race = event.get('shortName', 'Event'); venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                match_data = {'league': league_name, 'color': 0xffffff, 'home': race, 'away': venue, 'score': "VS", 'status': "SCH", 'time': local_time, 'h_url': h_url, 'a_url': a_url, 'h_id': h_id, 'a_id': a_id}
            else:
                home, away, h_score, a_score = "Home", "Away", "0", "0"; h_team_id, a_team_id = "0", "0"
                
                # Tennis/Combat use athlete, team sports use team
                if event_sport_type in [SPORT_TYPE_TENNIS, SPORT_TYPE_COMBAT]:
                    for i, comp in enumerate(comps[:2]):
                        name = comp.get('athlete', {}).get('shortName') or comp.get('athlete', {}).get('displayName') or comp.get('name', 'Player')
                        if len(name) > 15: name = name[:14] + "."
                        
                        sc = comp.get('score', '')
                        if event_sport_type == SPORT_TYPE_TENNIS:
                            t1, t2 = calculate_tennis_scores(comps, state)
                            sc = t1 if i == 0 else t2
                        
                        if not sc: sc = '0'
                        tid = comp.get('athlete', {}).get('id', '0')
                        # Tennis: first competitor = player1/home, second = player2/away
                        if i == 0: home, h_score, h_team_id = name, sc, tid
                        else: away, a_score, a_team_id = name, sc, tid
                else:
                    # Team sports
                    for team in comps:
                        name = team.get('team', {}).get('displayName', 'Team'); sc = team.get('score', '0'); tid = team.get('team', {}).get('id', '0')
                        if team.get('homeAway') == 'home': home, h_score, h_team_id = name, sc, tid
                        else: away, a_score, a_team_id = name, sc, tid
                        
                score_str = "VS"; status_str = "SCH"
                # OPTIMIZATION: Defer scorer calculation to show_next_match (lazy loading)
                if state == 'in':
                    score_str = "{} - {}".format(h_score, a_score); status_str = clock
                    local_time = "Live"
                elif state == 'post':
                    score_str = "{} - {}".format(h_score, a_score); status_str = "FT"
                    
                l_color = 0xffffff
                for key, val in self.league_colors.items():
                    if key in league_name.upper() or key in event.get('shortName', '').upper(): l_color = val; break
                    
                # Store event reference and IDs for lazy scorer loading
                match_data = {'league': league_name, 'color': l_color, 'home': home, 'away': away, 'score': score_str, 'status': status_str, 'time': local_time, 'h_url': h_url, 'a_url': a_url, 'h_id': h_id, 'a_id': a_id,
                              'home_clean': home, 'away_clean': away, 'h_scorers': None, 'a_scorers': None, 
                              'event_ref': event, 'h_team_id': h_team_id, 'a_team_id': a_team_id, 'sport_type': event_sport_type, 'state': state}
            new_matches.append(match_data)
            
        # Handle Filter Empty
        if not new_matches:
            # If we are currently updating, don't show "No Matches Found" yet if we have old data
            if self.matches and ("Loading" in global_sports_monitor.status_message or "Processing" in global_sports_monitor.status_message):
                return
                
            is_stale = (time.time() - global_sports_monitor.last_update) > 300
            msg = "Updating Data..." if is_stale else "No Matches Found"
            sub = "Please Wait" if is_stale else "Check Filters"
            new_matches.append({'league': "SimplySports", 'color': 0xffffff, 'home': msg, 'away': sub, 'score': "", 'status': "", 'time': "", 'h_url': "", 'a_url': "", 'h_id': "", 'a_id': ""})

        self.matches = new_matches
        if not self.ticker_timer.isActive(): 
            self.show_next_match()
            self.ticker_timer.start(5000)

    def show_next_match(self):
        if not self.matches: return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matches)
        data = self.matches[self.current_match_idx]
        
        # DYNAMIC FONT SIZING (Request: Soccer Score +25%)
        try:
            league_name = str(data.get('league', ''))
            sport_type = global_sports_monitor.get_sport_type(league_name)
            d_size = getDesktop(0).size()
            is_hd = d_size.width() > 1280
            
            # Base Sizes: HD=25, SD=21
            # Soccer Sizes (+25%): HD=31, SD=26
            if sport_type == 'soccer':
                f_size = 31 if is_hd else 26
            else:
                f_size = 25 if is_hd else 21
            
            self["lbl_score"].instance.setFont(gFont("Regular", f_size))
        except: pass

        self["lbl_league"].setText(str(data.get('league', '')))
        try: self["lbl_league"].instance.setForegroundColor(gRGB(data.get('color', 0xffffff)))
        except: pass
        # Use separated data if available
        h_txt = data.get('home_clean') or data.get('home', '')
        a_txt = data.get('away_clean') or data.get('away', '')
        
        # LAZY SCORER LOADING: Calculate scorers on-demand only for displayed match
        h_sc = data.get('h_scorers')
        a_sc = data.get('a_scorers')
        if h_sc is None and data.get('event_ref') and data.get('sport_type') == SPORT_TYPE_TEAM and data.get('state') in ['in', 'post']:
            h_sc, a_sc = self.get_scorers_string(data['event_ref'], data.get('h_team_id', '0'), data.get('a_team_id', '0'))
            data['h_scorers'] = h_sc
            data['a_scorers'] = a_sc
        
        # Ensure strings for display
        h_sc = h_sc or ''
        a_sc = a_sc or ''
        
        self["lbl_home"].setText(str(h_txt)); self["lbl_score"].setText(str(data.get('score', '')))
        self["lbl_away"].setText(str(a_txt)); self["lbl_status"].setText(str(data.get('status', '')))
        
        # Set scorers if they exist
        if h_sc: self["lbl_home_sc"].setText("({})".format(h_sc))
        else: self["lbl_home_sc"].setText("")
        
        if a_sc: self["lbl_away_sc"].setText("({})".format(a_sc))
        else: self["lbl_away_sc"].setText("")
        
        self["lbl_time"].setText(str(data.get('time', '')))
        
        self.load_logo(data.get('h_url'), data.get('h_id'), "h_logo")
        self.load_logo(data.get('a_url'), data.get('a_id'), "a_logo")

    def load_logo(self, url, img_id, widget_name):
        """Load logo using team ID naming (aligned with GameInfoScreen approach)"""
        if not url or not img_id or img_id == '0': self[widget_name].hide(); return
        
        file_path = self.logo_path + str(img_id) + ".png"
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            self[widget_name].instance.setScale(1)
            self[widget_name].instance.setPixmapFromFile(file_path)
            self[widget_name].show()
        else:
            self[widget_name].hide()
            # Download to team ID path
            from twisted.web.client import downloadPage
            downloadPage(url.encode('utf-8'), file_path).addCallback(self.logo_downloaded, widget_name, file_path).addErrback(self.logo_error)

    def logo_downloaded(self, data, widget_name, file_path):
        if self[widget_name].instance:
            self[widget_name].instance.setScale(1)
            self[widget_name].instance.setPixmapFromFile(file_path)
            self[widget_name].show()
    def logo_error(self, error): pass

# ==============================================================================
# MINI BAR 1 (Top Left) - FIXED: Callback Synchronization
# ==============================================================================
