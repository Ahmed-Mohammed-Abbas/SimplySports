import os
from ..common import *
from ..globals import global_sports_monitor

from .TeamStandingScreen import TeamStandingScreen
from .SimplePlayer import SimplePlayer
from .GameInfoScreen import GameInfoScreen
from .LeagueSelector import LeagueSelector
from .BroadcastingChannelsScreen import BroadcastingChannelsScreen
from .SimpleSportsMiniBar import SimpleSportsMiniBar
from .SimpleSportsMiniBar2 import SimpleSportsMiniBar2
class SimpleSportsScreen(Screen):
    @profile_function("SimpleSportsScreen")
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        global_sports_monitor.set_session(session)
        self.monitor = global_sports_monitor
        self.monitor.register_callback(self.refresh_ui)
        
        self.logo_path = "/tmp/simplysports/logos/"
        if not os.path.exists(self.logo_path):
            try: os.makedirs(self.logo_path)
            except: pass

        self.active_downloads = set()
        self.logo_refresh_timer = eTimer()
        safe_connect(self.logo_refresh_timer, lambda: self.refresh_ui(True))
        
        # Track matches for cursor locking
        self.current_match_ids = []
        
        # Debounce for remote keys
        self.last_key_time = 0
        
        # Cache for channels to avoid re-scanning bouquets
        self.service_cache = None

        valid_alphas = ['00', '1A', '33', '4D', '59', '66', '80', '99', 'B3', 'CC', 'E6', 'FF']
        self.current_alpha = self.monitor.transparency 
        if self.current_alpha not in valid_alphas: self.current_alpha = "59" 

        # ... (Skin setup omitted - keep existing block) ...
        # [PASTE YOUR EXISTING SKIN SETUP HERE]
        if self.monitor.theme_mode == "ucl":
            bg_base = "0e1e5b"; top_base = "050a2e"
            c_bg = "#" + self.current_alpha + bg_base; c_top = "#" + self.current_alpha + top_base
            bg_widget = '<widget name="main_bg" position="0,0" size="1920,1080" backgroundColor="{c_bg}" zPosition="-1" />'.format(c_bg=c_bg)
            try:
                path_jpg = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/ucl.jpg")
                if os.path.exists(path_jpg): bg_widget = '<ePixmap position="0,0" size="1920,1080" pixmap="{}" zPosition="-1" alphatest="on" scale="1" />'.format(path_jpg)
            except: pass
            top_widget = '<widget name="top_bar" position="0,0" size="1920,100" backgroundColor="{c_top}" zPosition="0" />'.format(c_top=c_top)
            header_widget = '<widget name="header_bg" position="0,123" size="1920,34" backgroundColor="{c_bg}" zPosition="0" />'.format(c_bg=c_bg)
            bar_widget = ""; bottom_widget = '<widget name="bottom_bar" position="0,990" size="1920,90" backgroundColor="{c_top}" zPosition="0" />'.format(c_top=c_top)
            fg_title = "#00ffff"; bg_title = "#050a2e"; fg_list_h = "#ffffff"; fg_list_s = "#00ffff"
            clock_x = 1710; clock_w = 180; clock_a = "center"
        else: 
            bg_base = "100015"; bar_base = "38003C"
            c_bg = "#" + self.current_alpha + bg_base; c_bar = "#" + self.current_alpha + bar_base
            bg_widget = '<eLabel position="0,0" size="1920,1080" backgroundColor="{c_bg}" zPosition="-1" />'.format(c_bg=c_bg)
            top_widget = '<widget name="top_bar" position="0,0" size="1920,100" backgroundColor="{c_bg}" zPosition="0" />'.format(c_bg=c_bg)
            header_widget = '<widget name="header_bg" position="0,110" size="1920,45" backgroundColor="{c_bg}" zPosition="0" />'.format(c_bg=c_bg)
            bar_widget = '<widget name="bar_bg" position="0,70" size="1920,40" backgroundColor="{c_bar}" zPosition="0" />'.format(c_bar=c_bar)
            bottom_widget = '<widget name="bottom_bar" position="0,990" size="1920,90" backgroundColor="{c_bg}" zPosition="0" />'.format(c_bg=c_bg)
            fg_title = "#00FF85"; bg_title = "#100015"; fg_list_h = "#FFFFFF"; fg_list_s = "#00FF85"
            clock_x = 1710; clock_w = 180; clock_a = "center"

        self.skin = """
        <screen position="0,0" size="1920,1080" title="SimplySports" flags="wfNoBorder" backgroundColor="#00000000">
            {bg}
            {top}
            <widget name="top_title" position="0,10" size="1920,60" font="SimplySportFont;46" foregroundColor="{fg_t}" backgroundColor="{bg_t}" transparent="1" halign="center" valign="center" zPosition="2" shadowColor="#000000" shadowOffset="-3,-3" />
            <widget name="key_menu" position="40,30" size="300,30" font="SimplySportFont;22" foregroundColor="#bbbbbb" backgroundColor="{bg_t}" transparent="1" halign="left" zPosition="2" />
            <widget name="credit" position="1600,20" size="300,30" font="SimplySportFont;20" foregroundColor="#888888" backgroundColor="{bg_t}" transparent="1" halign="right" zPosition="2" />
            <widget name="clock" position="{cx},75" size="{cw},35" font="SimplySportFont;28" foregroundColor="{fg_ls}" backgroundColor="#38003C" transparent="1" halign="{ca}" zPosition="2" />
            {bar}
            <widget name="league_title" position="50,75" size="500,35" font="SimplySportFont;28" foregroundColor="{fg_lh}" backgroundColor="#38003C" transparent="1" halign="left" zPosition="1" />
            <widget name="list_title" position="0,75" size="1920,35" font="SimplySportFont;28" foregroundColor="{fg_ls}" backgroundColor="#38003C" transparent="1" halign="center" zPosition="1" />
            {header}
            <widget name="head_status" position="30,125" size="80,30" font="SimplySportFont;18" foregroundColor="{fg_ls}" backgroundColor="#0e1e5b" transparent="1" halign="center" zPosition="1" />
            <widget name="head_league" position="110,125" size="80,30" font="SimplySportFont;18" foregroundColor="{fg_ls}" backgroundColor="#0e1e5b" transparent="1" halign="center" zPosition="1" />
            <widget name="head_home" position="195,125" size="575,30" font="SimplySportFont;20" foregroundColor="{fg_ls}" backgroundColor="#0e1e5b" transparent="1" halign="right" zPosition="1" />
            <widget name="head_score" position="860,125" size="200,30" font="SimplySportFont;20" foregroundColor="{fg_ls}" backgroundColor="#0e1e5b" transparent="1" halign="center" zPosition="1" />
            <widget name="head_away" position="1150,125" size="520,30" font="SimplySportFont;20" foregroundColor="{fg_ls}" backgroundColor="#0e1e5b" transparent="1" halign="left" zPosition="1" />
            <widget name="head_time" position="1710,125" size="180,30" font="SimplySportFont;20" foregroundColor="{fg_ls}" backgroundColor="#0e1e5b" transparent="1" halign="center" zPosition="1" />
            <widget name="list" position="0,170" size="1920,800" scrollbarMode="showOnDemand" transparent="1" zPosition="1" />
            {bottom}
            <widget name="key_red" position="40,1005" size="340,60" font="SimplySportFont;30" foregroundColor="#FFFFFF" backgroundColor="#CC0000" transparent="0" zPosition="2" halign="center" valign="center" />
            <widget name="key_green" position="400,1005" size="340,60" font="SimplySportFont;30" foregroundColor="#000000" backgroundColor="#00FF85" transparent="0" zPosition="2" halign="center" valign="center" />
            <widget name="key_yellow" position="760,1005" size="340,60" font="SimplySportFont;30" foregroundColor="#000000" backgroundColor="#FFD700" transparent="0" zPosition="2" halign="center" valign="center" />
            <widget name="key_blue" position="1120,1005" size="340,60" font="SimplySportFont;30" foregroundColor="#FFFFFF" backgroundColor="#0055AA" transparent="0" zPosition="2" halign="center" valign="center" />
            <widget name="key_epg" position="1480,1005" size="400,60" font="SimplySportFont;30" foregroundColor="#FFFFFF" backgroundColor="#444444" transparent="0" zPosition="2" halign="center" valign="center" />
        </screen>
        """.format(bg=bg_widget, top=top_widget, bar=bar_widget, header=header_widget, bottom=bottom_widget, fg_t=fg_title, bg_t=bg_title, fg_lh=fg_list_h, fg_ls=fg_list_s, cx=clock_x, cw=clock_w, ca=clock_a)

        self["top_bar"] = Label(""); self["header_bg"] = Label(""); self["bottom_bar"] = Label(""); self["main_bg"] = Label(""); self["bar_bg"] = Label("")
        self["top_title"] = Label("SIMPLY SPORTS"); self["league_title"] = Label("LOADING..."); self["list_title"] = Label("")
        self["credit"] = Label("v" + CURRENT_VERSION); self["key_menu"] = Label("MENU: Settings & Tools")
        self["clock"] = Label("")  # Clock widget
        self["head_status"] = Label("STATUS"); self["head_league"] = Label("LEAGUE"); self["head_home"] = Label("HOME"); self["head_score"] = Label("SCORE"); self["head_away"] = Label("AWAY"); self["head_time"] = Label("TIME")
        self["list"] = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
        # Use Custom font "SimplySportFont" which is guaranteed to map to a valid system font
        self["list"].l.setFont(0, gFont("SimplySportFont", 26))
        self["list"].l.setFont(1, gFont("SimplySportFont", 28))
        self["list"].l.setFont(2, gFont("SimplySportFont", 38))
        self["list"].l.setFont(3, gFont("SimplySportFont", 20))
        self["list"].l.setItemHeight(90) 
        self["key_red"] = Label("League List"); self["key_green"] = Label("Mini Bar"); self["key_yellow"] = Label("Live Only"); self["key_blue"] = Label("Goal Alert: OFF")
        self["key_epg"] = Label("Info/EPG: Channels")
        
        # Clock timer
        self.clock_timer = eTimer()
        safe_connect(self.clock_timer, self.update_clock)
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "MenuActions", "EPGSelectActions"], 
            {"cancel": self.close, "red": self.open_league_menu, "green": self.open_mini_bar, "yellow": self.toggle_filter, "blue": self.toggle_discovery, "ok": self.open_game_info, "menu": self.open_settings_menu, "up": self["list"].up, "down": self["list"].down, "info": self.open_broadcasting}, -1)
        
        self.container = eConsoleAppContainer(); self.container.appClosed.append(self.download_finished)
        self.onLayoutFinish.append(self.start_ui); self.onClose.append(self.cleanup)

    def update_clock(self):
        """Update clock display with current time"""
        try:
            now = datetime.datetime.now()
            self["clock"].setText(now.strftime("%H:%M"))
        except: pass

    def start_ui(self):
        self.update_clock()  # Initial clock update
        self.clock_timer.start(1000)  # Update every second
        self.update_header(); self.update_filter_button(); self.fetch_data()
    def cleanup(self): 
        self.clock_timer.stop()
        self.monitor.unregister_callback(self.refresh_ui)
    
    # ... (Keep Header, Filter, Download helpers unchanged) ...
    def update_header(self):
        if self.monitor.is_custom_mode: self["league_title"].setText("Custom League View")
        else:
            try: item = DATA_SOURCES[self.monitor.current_league_index]; self["league_title"].setText(item[0])
            except: pass
        mode = self.monitor.filter_mode
        if mode == 0: self["list_title"].setText("Live Matches")
        elif mode == 1: self["list_title"].setText("All Matches")
        elif mode == 2: self["list_title"].setText("Today's Matches")
        elif mode == 3: self["list_title"].setText("Tomorrow's Matches")
        d_mode = self.monitor.discovery_mode
        if d_mode == 0: self["key_blue"].setText("Goal Alert: OFF")
        elif d_mode == 1: self["key_blue"].setText("Goal Alert: VISUAL")
        elif d_mode == 2: self["key_blue"].setText("Goal Alert: SOUND")
    def update_filter_button(self): 
        mode = self.monitor.filter_mode
        if mode == 0: self["key_yellow"].setText("Show All")
        elif mode == 1: self["key_yellow"].setText("Show Today")
        elif mode == 2: self["key_yellow"].setText("Show Tomorrow")
        elif mode == 3: self["key_yellow"].setText("Live Only")
        self.update_header()
    def fetch_data(self): self.monitor.check_goals()
    
    @profile_function("SimpleSportsScreen")
    def get_logo_path(self, url, team_id):
        """Get logo path using team ID naming (aligned with GameInfoScreen approach)"""
        if not url or not team_id: return None
        
        # Check team-ID-named file
        if team_id in self.monitor.logo_path_cache: return self.monitor.logo_path_cache[team_id]
        target_path = self.logo_path + str(team_id) + ".png"
        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            self.monitor.logo_path_cache[team_id] = target_path
            return target_path
        
        # Queue download if not cached
        self.queue_download(url, target_path, team_id)
        return None

    def queue_download(self, url, target_path, filename):
        if filename in self.active_downloads: return
        # Limit concurrent downloads to prevent network congestion
        MAX_CONCURRENT = 5
        if len(self.active_downloads) >= MAX_CONCURRENT:
            # Add to pending queue - will be processed when current downloads finish
            if not hasattr(self, 'pending_downloads'): self.pending_downloads = []
            self.pending_downloads.append((url, target_path, filename))
            return
        self.active_downloads.add(filename)
        from twisted.web.client import downloadPage
        downloadPage(url.encode('utf-8'), target_path).addCallback(self.download_finished, filename, target_path).addErrback(self.download_failed, filename)

    def download_finished(self, data, filename, target_path):
        self.active_downloads.discard(filename)
        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            self.monitor.logo_path_cache[filename] = target_path
            # Batch UI updates - wait for more downloads before refreshing
            if not self.logo_refresh_timer.isActive(): self.logo_refresh_timer.start(1500, True)
        # Process pending downloads
        self._process_pending_downloads()

    def download_failed(self, error, filename):
        self.active_downloads.discard(filename)
        self._process_pending_downloads()
    
    def _process_pending_downloads(self):
        """Process queued downloads when there's capacity"""
        if not hasattr(self, 'pending_downloads') or not self.pending_downloads: return
        MAX_CONCURRENT = 5
        while self.pending_downloads and len(self.active_downloads) < MAX_CONCURRENT:
            url, target_path, filename = self.pending_downloads.pop(0)
            if filename not in self.active_downloads and filename not in self.monitor.logo_path_cache:
                self.active_downloads.add(filename)
                from twisted.web.client import downloadPage
                downloadPage(url.encode('utf-8'), target_path).addCallback(self.download_finished, filename, target_path).addErrback(self.download_failed, filename)
        
    def check_epg_availability(self, home, away):
        epg = eEPGCache.getInstance()
        if not epg: return False
        
        h_terms = get_search_keywords(home)
        a_terms = get_search_keywords(away)
        
        # Check primary keywords for discovery
        queries = []
        if h_terms: queries.append(normalize_text(h_terms[0]))
        if a_terms: queries.append(normalize_text(a_terms[0]))
        
        for kw in queries:
            if not kw: continue
            try:
                # Fast global search
                results = epg.search((kw, 2, 0, 10))
                if results:
                    for entry in results:
                        title = normalize_text(entry[2] or "")
                        # Verification: Name must be in title
                        if kw in title: return True
            except: pass
        return False

    def open_broadcasting(self, forced_event=None):
        target_event = forced_event
        selected_id = None
        
        if not target_event:
            idx = self["list"].getSelectedIndex()
            if idx is None or idx < 0 or idx >= len(self.current_match_ids): return
            selected_id = self.current_match_ids[idx]

        # Re-find event or process target
        events_to_scan = [target_event] if target_event else self.monitor.cached_events
        for event in events_to_scan:
            try:
                # 1. Define comps/status
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                status = event.get('status', {}); state = status.get('type', {}).get('state', 'pre')
                ev_date_str = event.get('date', '')
                league_name = event.get('league_name', '')
                
                # 2. Calculate Timestamp
                match_time_ts = 0
                
                try: 
                    import calendar
                    import time
                    if ev_date_str:
                        # Harden Parsing: Standardize separator and remove Z/fractions
                        clean_date = ev_date_str.replace("Z", "").replace("T", " ")
                        if "." in clean_date: 
                            clean_date = clean_date.split(".")[0]
                        
                        dt = None
                        # Try formats: with seconds, without seconds
                        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                            try:
                                dt = datetime.datetime.strptime(clean_date, fmt)
                                break
                            except ValueError: continue
                            
                        if dt:
                            match_time_ts = calendar.timegm(dt.timetuple())
                except: pass
                
                # FALLBACK: If date parse failed or missing, use CURRENT TIME
                # This assumes the user wants EPG for what's happening NOW.
                if match_time_ts == 0:
                    import time
                    match_time_ts = int(time.time())

                # Define safe defaults for EPG search variables before the loop to avoid UnboundLocalError
                epg_home = ""; epg_away = ""; epg_league = league_name

                if len(comps) > 2:
                    left = event.get('shortName', 'Race'); right = "Event"
                    mid = left + right
                    # For Racing/Golf, use Event Name as "Home" and nothing as "Away"
                    epg_home = event.get('shortName') or event.get('name') or "Event"
                    epg_away = "" 
                else:
                    team_h = next((t for t in comps if t.get('homeAway') == 'home'), comps[0] if comps else None)
                    team_a = next((t for t in comps if t.get('homeAway') == 'away'), comps[1] if len(comps)>1 else None)
                    
                    home = "Home"; away = "Away"
                    if team_h:
                        if 'athlete' in team_h: home = team_h.get('athlete', {}).get('shortName', 'P1')
                        else: home = team_h.get('team', {}).get('displayName', 'Home')
                    if team_a:
                        if 'athlete' in team_a: away = team_a.get('athlete', {}).get('shortName', 'P2')
                        else: away = team_a.get('team', {}).get('displayName', 'Away')
                    mid = home + "_" + away
                    
                    # Set EPG search terms
                    epg_home = home; epg_away = away
                
                # Check ID match only if not forced
                if target_event or mid == selected_id:
                    if not target_event: target_event = event
                    # Extract names and Time for Smart Search
                    self.search_and_display_epg(epg_home, epg_away, epg_league, match_time_ts)
                    return
            except: continue

    def search_and_display_epg(self, home, away, league, match_time_ts):
        from Screens.MessageBox import MessageBox
        import os
        from enigma import eServiceReference, eEPGCache
        
        epg = eEPGCache.getInstance()
        if not epg: 
            self.session.open(MessageBox, "Critical Error: eEPGCache instance is missing.", MessageBox.TYPE_ERROR)
            return

        # --- DIAGNOSTIC: Check EPG File (Expanded Paths) ---
        epg_paths = [
            "/etc/enigma2/epg.dat", "/media/hdd/epg.dat", "/media/usb/epg.dat", "/data/epg.dat", "/hdd/epg.dat",
            "/mnt/egamiboot/epg.dat", "/usr/share/enigma2/epg.dat", "/share/enigma2/epg.dat", "/tmp/epg.dat"
        ]
        found_epg_path = "None"
        for p in epg_paths:
            if os.path.exists(p):
                found_epg_path = "%s (%.2f MB)" % (p, os.path.getsize(p)/1024.0/1024.0)
                break
        # --- DIAGNOSTIC END ---

        # 1. Prepare Target Words
        h_norm = [normalize_text(kw) for kw in get_search_keywords(home)]
        a_norm = [normalize_text(kw) for kw in get_search_keywords(away)]
        l_norm = [normalize_text(kw) for kw in get_search_keywords(league)]
        
        # 2. Get Channels
        if not self.service_cache:
            self.service_cache = get_all_services()
        
        if not self.service_cache:
             self.session.open(MessageBox, "No channels found in bouquets.", MessageBox.TYPE_INFO)
             return

        c_count = len(self.service_cache)
        
        # --- DIAGNOSTIC: Safe Probe (Multi-Channel + Time) ---
        probe_result = "Skipped (No valid ch)"
        sys_time_str = "Unknown"
        if c_count > 0:
            try:
                import time
                import datetime
                cur_time = int(time.time())
                sys_time_str = datetime.datetime.fromtimestamp(cur_time).strftime('%Y-%m-%d %H:%M')
                
                # Try reloading EPG if file found
                if found_epg_path != "None":
                    try: epg.load() 
                    except: pass

                # Probe first few channels
                checked_count = 0
                for s in self.service_cache:
                    if checked_count >= 5: break
                    s_ref_str = s[0]
                    if s_ref_str.startswith("1:0:1:") or s_ref_str.startswith("1:0:19:"):
                        checked_count += 1
                        p_evt = epg.lookupEventTime(eServiceReference(s_ref_str), cur_time)
                        if p_evt: 
                            probe_result = "Success (%s) on %s" % (p_evt.getEventName() or "Unknown", s[1])
                            break
                        else: 
                            probe_result = "No Data on %s" % s[1]
            except Exception as e: probe_result = "Error: %s" % str(e)
        # -------------------------------------
        
        unique_services = {}
        for s in self.service_cache:
            unique_services[str(s[0])] = s

        results = []
        
        # SEARCH LOGIC: Multi-Point Probe for Accuracy
        # We search multiple points relative to start time to catch pre-shows, slightly shifted times, etc.
        # Offsets in seconds: +15m (ideal), +0m (start), +60m (mid-match), -15m (pre-match)
        search_offsets = [900, 0, 3600, -900]
        
        # Determine if we can use "Now" fallback
        now = int(time.time())
        use_fallback_now = True
        
        # If match is in future (> 6 hours), DISABLE "Now" fallback completely
        # Searching "Now" for tomorrow's match yields garbage.
        if match_time_ts > (now + 21600):
            use_fallback_now = False

        # 2. Get Services
        unique_services = {}
        for s in self.service_cache:
            unique_services[str(s[0])] = s

        results = []
        for sref_str, s_info in unique_services.items():
            sref_raw = s_info[0]
            ch_name = s_info[1]
            try:
                evt = None
                sref_obj = eServiceReference(sref_raw)
                
                # 1. Multi-Point Probe
                for offset in search_offsets:
                    probe_time = match_time_ts + offset
                    candidate = epg.lookupEventTime(sref_obj, probe_time)
                    if candidate:
                        evt = candidate
                        break
                
                # 2. Fallback to NOW (Only if allowed and primary failed)
                if not evt and use_fallback_now:
                     if abs(match_time_ts - now) < 7200:
                         evt = epg.lookupEventTime(sref_obj, now)
                
                # 3. IPTV Linking (Fallback logic)
                if not evt and (sref_raw.startswith("4097:") or sref_raw.startswith("5001:")):
                    parts = sref_raw.split(':')
                    if len(parts) > 10:
                        dvb_ref_str = "1:0:1:%s:%s:%s:%s:0:0:0" % (parts[3], parts[4], parts[5], parts[6])
                        dvb_obj = eServiceReference(dvb_ref_str)
                        for offset in search_offsets:
                            probe_time = match_time_ts + offset
                            evt = epg.lookupEventTime(dvb_obj, probe_time)
                            if evt: break
                        if not evt and use_fallback_now and abs(match_time_ts - now) < 7200:
                            evt = epg.lookupEventTime(dvb_obj, now)

                if evt:
                    title = evt.getEventName() or ""
                    desc = evt.getShortDescription() or ""
                    ext = evt.getExtendedDescription() or "" # Multi-field Search: Extended Info
                    
                    # Combine all fields into a single searchable blob
                    # Search Priority: Title > Short Desc > Extended Desc > Channel Name
                    blob = normalize_text(title + " " + desc + " " + ext + " " + ch_name)
                    
                    # --- UNIVERSAL SMART SCORING (Granular) ---
                    STOP_WORDS = ['al', 'el', 'the', 'fc', 'sc', 'fk', 'sk', 'club', 'sport', 'sports', 'vs', 'live', 'hd', 'fhd', '4k', 'uhd']
                    
                    def match_sig_score(keywords, text_blob, require_all=True):
                        sig = [w for w in keywords if w not in STOP_WORDS and len(w) > 1]
                        if not sig: sig = keywords 
                        
                        found_count = 0
                        for w in sig:
                            if w in text_blob: found_count += 1
                        
                        return found_count, len(sig)

                    # Calculate ratios (0.0 to 1.0)
                    h_found, h_total = match_sig_score(h_norm, blob)
                    a_found, a_total = match_sig_score(a_norm, blob) if a_norm else (0, 0)
                    l_found, l_total = match_sig_score(l_norm, blob)
                    
                    h_ratio = h_found / float(h_total) if h_total > 0 else 0.0
                    a_ratio = a_found / float(a_total) if a_total > 0 else 0.0
                    l_ratio = l_found / float(l_total) if l_total > 0 else 0.0
                    
                    score = 0.0
                    # Weighted Scoring: Home(40%) + Away(40%) + League(20%)
                    score += (h_ratio * 40)
                    score += (a_ratio * 40)
                    score += (l_ratio * 20)
                    
                    # Bonus for COMPLETE matches (Exact Phrase match essentially)
                    if h_ratio == 1.0: score += 10
                    if a_ratio == 1.0: score += 10
                    
                    # Huge bonus if BOTH teams match perfectly
                    if h_ratio == 1.0 and (a_ratio == 1.0 or not a_norm):
                        score += 30
                        
                    # Tie-Breaker: Reward matches with MORE matched words total
                    # This favors "Man City" (2 words) over "City" (1 word) if both are 100%
                    score += (h_found + a_found + l_found)

                    # --- TIME PROXIMITY BONUS ---
                    # Prioritize events starting close to match time (Live Coverage)
                    try:
                        evt_start = evt.getBeginTime()
                        diff_min = abs(evt_start - match_time_ts) / 60.0
                        
                        if diff_min <= 15: score += 20     # Starts within 15 mins (Prime Live Slot)
                        elif diff_min <= 45: score += 10   # Starts within 45 mins (Pre-show included)
                        elif diff_min <= 90: score += 5    # Reasonable window
                        elif diff_min > 120: score -= 15   # >2 hours off (Likely replay or different match)
                    except: diff_min = 999
                    
                    # Filtering Thresholds
                    # We want at least one team fully matched OR both partially matched good enough
                    valid_match = False
                    if h_ratio == 1.0 and (a_ratio == 1.0 or not a_norm): valid_match = True
                    elif h_ratio >= 0.5 and a_ratio >= 0.5: valid_match = True # Partial on both
                    elif (h_ratio == 1.0 or a_ratio == 1.0) and l_ratio >= 0.5: valid_match = True # One team + League
                    
                    if valid_match and score > 40:
                        cat_color = 0xffffff
                        if score >= 100: cat_color = 0x00FF00    # Perfect
                        elif score >= 80: cat_color = 0xFFFF00   # Good
                        
                        sat_pos = get_sat_position(sref_raw)
                        full_name = ch_name + ((" (" + sat_pos + ")") if sat_pos else "")
                        # Show score and time diff for transparency
                        time_info = "T+0" if diff_min < 1 else "T-%d" % int(diff_min) if evt_start < match_time_ts else "T+%d" % int(diff_min)
                        display_title = "[%d|%s] %s" % (int(score), time_info, title)
                        results.append((sref_raw, full_name, display_title, cat_color, score))
            except: pass

        # Sort by Score Descending
        results.sort(key=lambda x: x[4], reverse=True)
        final_list = [ (r[0], r[1], r[2], r[3]) for r in results[:200] ]
        
        
        if final_list:
            self.session.open(BroadcastingChannelsScreen, final_list, match_time_ts=match_time_ts)
        else:
             self.session.open(MessageBox, "No EPG matches found.\n\nChecked for:\n%s\n%s\nIn League: %s" % (home, away, league), MessageBox.TYPE_INFO)

    @profile_function("SimpleSportsScreen")
    def refresh_ui(self, success):
        # Guard: Don't refresh UI during loading states
        if not success:
            return
            
        self.update_header()
        events = self.monitor.cached_events
        
        # --- CURSOR PRESERVATION LOGIC START ---
        selected_id = None
        current_idx = self["list"].getSelectedIndex()
        if 0 <= current_idx < len(self.current_match_ids):
            selected_id = self.current_match_ids[current_idx]
        
        new_match_ids = []
        # ----------------------------------------

        # Skip rebuild if no changes and we already have data
        if not self.monitor.has_changes and self.current_match_ids and events:
            return
        
        if not events:
            # If we already have matches and loading is in progress, keep old list to avoid flicker
            if self.current_match_ids and ("Loading" in self.monitor.status_message or "Fetching" in self.monitor.status_message):
                return
            msg = self.monitor.status_message or "No Matches Found"
            dummy_entry = ("INFO", "", msg, "", "", "", False, "", None, None, 0, 0)
            if self.monitor.theme_mode == "ucl": self["list"].setList([UCLListEntry(dummy_entry)])
            else: self["list"].setList([SportListEntry(dummy_entry)])
            self.current_match_ids = []
            return
            
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d"); tom_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        raw_entries = []  # Store (entry_data, match_id, is_live) for sorting
        
        for event in events:
            try:
                status = event.get('status', {}); state = status.get('type', {}).get('state', 'pre')
                clock = status.get('displayClock', ''); local_time = get_local_time_str(event.get('date', ''))
                if ":" in clock: clock = clock.split(':')[0] + "'"
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                league_prefix = event.get('league_name', '')
                h_url = event.get('h_logo_url', ''); a_url = event.get('a_logo_url', '')
                h_id = event.get('h_logo_id', ''); a_id = event.get('a_logo_id', '')
                h_png = self.get_logo_path(h_url, h_id); a_png = self.get_logo_path(a_url, a_id)
                is_live = False; display_time = local_time; h_score_int = 0; a_score_int = 0
                
                # Match ID Generation for Tracking
                match_id = ""
                
                if len(comps) > 2:
                    left_text = event.get('shortName', 'Race'); right_text = "Event"; score_text = ""; goal_side = None
                    if state == 'in': score_text = "LIVE"; is_live = True
                    elif state == 'post': score_text = "FIN"
                    match_id = left_text + right_text # Fallback ID for racing
                else:
                    home, away, h_score, a_score = "Home", "Away", "0", "0"
                    team_h = next((t for t in comps if t.get('homeAway') == 'home'), None)
                    if not team_h and len(comps) > 0: team_h = comps[0]
                    team_a = next((t for t in comps if t.get('homeAway') == 'away'), None)
                    if not team_a and len(comps) > 1: team_a = comps[1]
                    
                    # Handle different sport types - tennis/combat use 'athlete', team sports use 'team'
                    league_url = event.get('league_url', '')
                    sport_type = event.get('sport_type', 'soccer')
                    is_tennis = 'athlete' in (team_h or {}) or 'athlete' in (team_a or {})
                    
                    if team_h:
                        if 'athlete' in team_h:
                            athlete = team_h.get('athlete', {})
                            home = athlete.get('shortName') or athlete.get('displayName') or athlete.get('fullName') or athlete.get('name') or team_h.get('team', {}).get('displayName') or 'Player 1'
                        else:
                            home = team_h.get('team', {}).get('displayName', team_h.get('team', {}).get('name', 'Home'))
                        
                        # For tennis, try multiple score sources
                        if is_tennis:
                            t_s1, t_s2 = calculate_tennis_scores(comps, state)
                            # Assuming team_h is index 0 and team_a is index 1 if available in comps
                            # But comps has all competitors. We need to match team_h to comps index?
                            # Usually comps list is [home, away] or [p1, p2].
                            # team_h logic: derived from first competitor with homeAway='home' OR index 0.
                            h_score = t_s1 if team_h == comps[0] else t_s2
                        else:
                            h_score = team_h.get('score', '0') or '0'
                    
                    if team_a:
                        if 'athlete' in team_a:
                            athlete = team_a.get('athlete', {})
                            away = athlete.get('shortName') or athlete.get('displayName') or athlete.get('fullName') or athlete.get('name') or team_a.get('team', {}).get('displayName') or 'Player 2'
                        else:
                            away = team_a.get('team', {}).get('displayName', team_a.get('team', {}).get('name', 'Away'))
                        
                        # For tennis, try multiple score sources
                        if is_tennis:
                            t_s1, t_s2 = calculate_tennis_scores(comps, state)
                            a_score = t_s1 if team_a == comps[0] else t_s2
                        else:
                            a_score = team_a.get('score', '0') or '0'
                    
                    def truncate_name(name, max_len=25):
                        if len(name) > max_len:
                            return name[:max_len-2] + ".."
                        return name
                    
                    left_text = truncate_name(home)
                    right_text = truncate_name(away)
                    try: h_score_int = int(h_score)
                    except: h_score_int = 0
                    try: a_score_int = int(a_score)
                    except: a_score_int = 0
                    
                    score_text = str(h_score) + " - " + str(a_score) if state in ('in', 'post') else "vs"
                    goal_side = None
                    if state == 'in': is_live = True; display_time = clock
                    match_id = home + "_" + away
                    goal_side = self.monitor.goal_flags[match_id]['side'] if match_id in self.monitor.goal_flags else None
                
                status_short = "SCH"
                if state == 'in': status_short = "LIVE"
                elif state == 'post': status_short = "FIN"
                mode = self.monitor.filter_mode; ev_date = event.get('date', '')[:10]
                if mode == 0 and state != 'in': continue
                if mode == 2 and ev_date != today_str: continue
                if mode == 3 and ev_date != tom_str: continue
                
                has_epg = self.check_epg_availability(home, away) if state == 'pre' or is_live else False
                entry_data = (status_short, get_league_abbr(league_prefix), str(left_text), str(score_text), str(right_text), str(display_time), goal_side, is_live, h_png, a_png, h_score_int, a_score_int, has_epg)
                
                # Store raw data for sorting (include event for excitement calculation)
                raw_entries.append((entry_data, match_id, is_live, event))
                
            except: continue
        
        # Sort: LIVE matches by excitement (highest first), then FIN, then SCH
        def sort_key(item):
            entry_data, match_id, is_live, event = item
            status = entry_data[0]  # status_short is index 0
            if status == "LIVE":
                # Calculate excitement score (higher = more exciting)
                excitement = self.monitor.calculate_excitement(event)
                # Return (0, -excitement) so LIVE comes first, highest excitement at top
                return (0, -excitement)
            elif status == "FIN":
                return (1, 0)
            else:
                return (2, 0)  # SCH
        
        raw_entries.sort(key=sort_key)
        
        # Convert to list entries after sorting
        list_content = []
        new_match_ids = []
        for entry_data, match_id, is_live, event in raw_entries:
            if self.monitor.theme_mode == "ucl": list_content.append(UCLListEntry(entry_data))
            else: list_content.append(SportListEntry(entry_data))
            new_match_ids.append(match_id)
            
        if not list_content: 
            msg = self.monitor.status_message or "No Matches Found"
            dummy_entry = ("INFO", "", msg, "", "", "", False, "", None, None, 0, 0)
            if self.monitor.theme_mode == "ucl": self["list"].setList([UCLListEntry(dummy_entry)])
            else: self["list"].setList([SportListEntry(dummy_entry)])
            self.current_match_ids = []
        else: 
            self["list"].setList(list_content)
            self.current_match_ids = new_match_ids
            
            # --- CURSOR RESTORE ---
            if selected_id:
                try:
                    new_index = new_match_ids.index(selected_id)
                    self["list"].moveToIndex(new_index)
                except ValueError: pass

    # ... (Keep existing Menu, Reminder, and Update methods unchanged) ...
    # [PASTE EXISTING METHODS HERE]
    def open_settings_menu(self):
        in_menu_txt = "Yes" if self.monitor.show_in_menu else "No"
        menu_options = [("Check for Updates", "update"), ("Change Interface Theme", "theme"), ("Window Transparency", "transparency"), ("Show In Main Menu: " + in_menu_txt, "toggle_menu")]
        self.session.openWithCallback(self.settings_menu_callback, ChoiceBox, title="Settings & Tools", list=menu_options)
    def settings_menu_callback(self, selection):
        if selection:
            action = selection[1]
            if action == "update": self.check_for_updates()
            elif action == "theme": self.open_theme_selector()
            elif action == "transparency": self.open_transparency_selector()
            elif action == "toggle_menu":
                self.monitor.show_in_menu = not self.monitor.show_in_menu
                self.monitor.save_config()
                self.session.open(MessageBox, "Setting saved.\nYou must Restart GUI for menu changes to take effect.", MessageBox.TYPE_INFO)
    def open_transparency_selector(self):
        t_options = [("Solid (0% Transparent)", "00"), ("Standard (35% Transparent)", "59"), ("90% Transparent", "E6"), ("Fully Transparent (100%)", "FF")]
        self.session.openWithCallback(self.transparency_selected, ChoiceBox, title="Select Transparency", list=t_options)
    def transparency_selected(self, selection):
        if selection:
            hex_val = selection[1]
            if self.monitor.transparency != hex_val:
                self.monitor.transparency = hex_val; self.monitor.save_config(); self.close(True)
    def open_theme_selector(self):
        menu_list = [("Default", "default"), ("UCL", "ucl")]
        self.session.openWithCallback(self.theme_selected, ChoiceBox, title="Select Theme", list=menu_list)
    def theme_selected(self, selection):
        if selection:
            new_theme = selection[1]
            if new_theme != self.monitor.theme_mode:
                self.monitor.theme_mode = new_theme; self.monitor.save_config(); self.close(True)
    def open_league_menu(self):
        options = [("Select Single League", "single"), ("Custom Leagues (View/Edit)", "custom_leagues")]
        self.session.openWithCallback(self.league_menu_callback, ChoiceBox, title="League Options", list=options)
    def league_menu_callback(self, selection):
        if selection:
            if selection[1] == "single": self.open_single_league_select()
            elif selection[1] == "custom_leagues": self.session.openWithCallback(self.on_selector_closed, LeagueSelector)
    def on_selector_closed(self, result=None):
        if result: self.update_header(); self.fetch_data()
    def open_single_league_select(self):
        options = []
        for idx, item in enumerate(DATA_SOURCES): options.append((item[0], idx))
        self.session.openWithCallback(self.single_league_selected, ChoiceBox, title="Select Single League", list=options)
    def single_league_selected(self, selection):
        if selection: self.monitor.set_league(selection[1]); self.update_header(); self.fetch_data()
    def open_mini_bar(self): self.session.openWithCallback(self.mini_bar_callback, SimpleSportsMiniBar)
    def mini_bar_callback(self, result=None):
        if result == "next": self.session.open(SimpleSportsMiniBar2)
    def open_game_info(self):
        idx = self["list"].getSelectedIndex()
        if idx is None or not self.monitor.cached_events: return
        
        # Build events list with same filtering as refresh_ui
        events = []
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d"); tom_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        for event in self.monitor.cached_events:
            status = event.get('status', {}); state = status.get('type', {}).get('state', 'pre'); ev_date = event.get('date', '')[:10]
            mode = self.monitor.filter_mode
            if mode == 0 and state != 'in': continue
            if mode == 2 and ev_date != today_str: continue
            if mode == 3 and ev_date != tom_str: continue
            events.append(event)
        
        # Apply same sorting as refresh_ui (excitement-based for LIVE matches)
        def sort_key(event):
            status = event.get('status', {})
            state = status.get('type', {}).get('state', 'pre')
            if state == 'in':
                excitement = self.monitor.calculate_excitement(event)
                return (0, -excitement)  # LIVE first, highest excitement at top
            elif state == 'post':
                return (1, 0)  # FIN second
            else:
                return (2, 0)  # SCH last
        
        events.sort(key=sort_key)
        
        if 0 <= idx < len(events):
            selected_event = events[idx]
            self.selected_event_for_reminder = selected_event
            state = selected_event.get('status', {}).get('type', {}).get('state', 'pre')
            if state == 'pre':
                options = [("Game Info / Details", "info"), ("Find Broadcasting Channel", "broadcast_search"), ("Remind me 12 hours before", 720), ("Remind me 9 hours before", 540), ("Remind me 6 hours before", 360), ("Remind me 3 hours before", 180), ("Remind me 2 hours before", 120), ("Remind me 1 hour before", 60), ("Remind me 15 minutes before", 15), ("Remind me 5 minutes before", 5), ("Delete Reminder", -1), ("Cancel", 0)]
                self.session.openWithCallback(self.reminder_selected, ChoiceBox, title="Game Options", list=options)
            else:
                event_id = selected_event.get('id'); league_name = selected_event.get('league_name', ''); url = ""
                for item in DATA_SOURCES:
                    if item[0] == league_name: url = item[1]; break
                if event_id and url: self.session.open(GameInfoScreen, event_id, url)
    def reminder_selected(self, selection):
        if not selection or selection[1] == 0: return
        val = selection[1]
        event = self.selected_event_for_reminder
        if val == "info":
            event_id = event.get('id'); league_name = event.get('league_name', ''); url = ""
            for item in DATA_SOURCES:
                if item[0] == league_name: url = item[1]; break
            if event_id and url: self.session.open(GameInfoScreen, event_id, url)
            return
        if val == "broadcast_search":
            self.open_broadcasting(forced_event=event)
            return
        try:
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            home = "Home"; away = "Away"
            for team in comps:
                name = team.get('team', {}).get('displayName', 'Team')
                if team.get('homeAway') == 'home': home = name
                else: away = name
            match_name = home + " vs " + away
            if val == -1:
                if self.monitor.remove_reminder(match_name): self.session.open(MessageBox, "Reminder removed.", MessageBox.TYPE_INFO, timeout=2)
                else: self.session.open(MessageBox, "No active reminder found.", MessageBox.TYPE_ERROR, timeout=2)
                return
            date_str = event.get('date', '')
            y, m, d = map(int, date_str.split('T')[0].split('-'))
            time_part = date_str.split('T')[1].replace('Z','')
            h, mn = map(int, time_part.split(':')[:2])
            dt_utc = datetime.datetime(y, m, d, h, mn)
            start_timestamp = calendar.timegm(dt_utc.timetuple())
            trigger_time = start_timestamp - (val * 60)
            now = time.time()
            if now >= trigger_time:
                time_left = start_timestamp - now
                if time_left < 0: msg = "Game has already started!"
                else:
                    hrs = int(time_left // 3600); mins = int((time_left % 3600) // 60)
                    msg = "Too late for this reminder!\nGame starts in {}h {}m.".format(hrs, mins)
                self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR, timeout=5)
                return
            label = "Starts in {} Mins".format(val)
            if val >= 60: label = "Starts in {} Hour(s)".format(int(val/60))
            league_name = event.get('league_name', '')
            h_logo = event.get('h_logo_url', '')
            a_logo = event.get('a_logo_url', '')
            self.monitor.add_reminder(match_name, trigger_time, league_name, h_logo, a_logo, label)
            self.session.open(MessageBox, "Reminder set!", MessageBox.TYPE_INFO, timeout=2)
        except: pass
    def toggle_discovery(self):
        if time.time() - self.last_key_time < 0.5: return
        self.last_key_time = time.time()
        self.monitor.cycle_discovery_mode(); self.update_header()
    def toggle_filter(self): 
        if time.time() - self.last_key_time < 0.5: return
        self.last_key_time = time.time()
        self.monitor.toggle_filter(); self.update_filter_button(); self.refresh_ui(True)
    def check_for_updates(self): 
        self["league_title"].setText("CHECKING FOR UPDATES...")
        url = GITHUB_BASE_URL + "version.txt"
        getPage(url.encode('utf-8')).addCallback(self.got_version).addErrback(self.update_fail)
    def got_version(self, data):
        try:
            remote = data.decode('utf-8').strip()
            if remote > CURRENT_VERSION: self.session.openWithCallback(self.start_update, MessageBox, "Update available: " + remote + "\nUpdate now?", MessageBox.TYPE_YESNO)
            else: self.session.open(MessageBox, "Latest version installed!", MessageBox.TYPE_INFO, timeout=3); self.update_header()
        except: self.update_fail(None)
    def update_fail(self, error): self.session.open(MessageBox, "Update check failed.", MessageBox.TYPE_ERROR, timeout=3); self.update_header()
    def start_update(self, answer):
        if answer: 
            self["league_title"].setText("DOWNLOADING...")
            url = GITHUB_BASE_URL + "plugin.py"
            target = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/plugin.py")
            downloadPage(url.encode('utf-8'), target).addCallback(self.download_extra_files).addErrback(self.update_fail)
    def download_extra_files(self, data):
        url = GITHUB_BASE_URL + "ucl.jpg"
        target = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/ucl.jpg")
        downloadPage(url.encode('utf-8'), target).addBoth(self.final_update_success)
    def final_update_success(self, data): self.session.open(MessageBox, "Update success! Restart GUI.", MessageBox.TYPE_INFO)



import os
from enigma import loadPNG

# ==============================================================================
# PICON HELPER
# ==============================================================================
def get_picon(service_ref):
    if not service_ref: return None
    
    # Convert Service Reference to Picon Filename Format
    # 1:0:19:2B66:3F:1:C00000:0:0:0: -> 1_0_19_2B66_3F_1_C00000_0_0_0
    sname = str(service_ref).strip().replace(':', '_').rstrip('_')
    
    # Search Paths
    search_paths = [
        "/omb/picon/",  # User requested specific path
        "/usr/share/enigma2/picon/",
        "/media/hdd/picon/",
        "/media/usb/picon/",
        "/media/mmc/picon/",
        "/picon/"
    ]
    
    for path in search_paths:
        png_file = path + sname + ".png"
        if os.path.exists(png_file) and os.path.getsize(png_file) > 0:
            return loadPNG(png_file)
            
    # Try alternate name format (remove last 0 if trailing)
    if sname.endswith("_0"):
        sname_alt = sname[:-2]
        for path in search_paths:
            png_file = path + sname_alt + ".png"
            if os.path.exists(png_file):
                return loadPNG(png_file)
                
    return None

# ==============================================================================
# BROADCASTING CHANNELS SCREEN
# ==============================================================================
