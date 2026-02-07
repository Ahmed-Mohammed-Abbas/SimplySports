import os
from ..common import *
from ..globals import global_sports_monitor

class SimpleSportsMiniBar(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        
        # 1. Register for Data Updates
        global_sports_monitor.register_callback(self.on_data_ready)
        
        # RAM Path
        self.logo_path = "/tmp/simplysports/logos/"
        if not os.path.exists(self.logo_path):
            try: os.makedirs(self.logo_path)
            except: pass

        if global_sports_monitor.theme_mode == "ucl":
            # Compact MiniBar: 770px wide, right-aligned, font adjustments
            self.skin = """<screen position="580,5" size="770,60" title="Sports Ticker" backgroundColor="#00000000" flags="wfNoBorder"><widget name="lbl_league" position="0,0" size="770,16" font="Regular;13" foregroundColor="#00ffff" transparent="1" halign="center" valign="center" zPosition="3" /><eLabel position="0,16" size="770,44" backgroundColor="#800e1e5b" zPosition="0" /><eLabel position="295,16" size="180,44" backgroundColor="#ffffff" zPosition="1" /><widget name="h_logo" position="5,20" size="36,36" alphatest="blend" scale="1" zPosition="2" /><widget name="lbl_home" position="45,16" size="245,44" font="Regular;23" foregroundColor="#ffffff" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="lbl_score" position="295,16" size="180,30" font="Regular;26" foregroundColor="#0e1e5b" backgroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="3" /><widget name="lbl_status" position="295,46" size="180,14" font="Regular;8" foregroundColor="#0e1e5b" backgroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="3" /><widget name="lbl_away" position="483,16" size="245,44" font="Regular;23" foregroundColor="#ffffff" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="a_logo" position="734,20" size="36,36" alphatest="blend" scale="1" zPosition="2" /></screen>"""
        else:
            # Compact MiniBar: 770px wide, right-aligned, font adjustments
            self.skin = """<screen position="580,5" size="770,60" title="Sports Ticker" backgroundColor="#00000000" flags="wfNoBorder"><widget name="lbl_league" position="0,0" size="770,16" font="Regular;13" foregroundColor="#FFFFFF" transparent="1" halign="center" valign="center" zPosition="3" /><eLabel position="0,16" size="5,44" backgroundColor="#E90052" zPosition="1" /><eLabel position="5,16" size="300,44" backgroundColor="#80190028" zPosition="1" /><widget name="h_logo" position="10,20" size="36,36" alphatest="blend" scale="1" zPosition="2" /><widget name="lbl_home" position="51,16" size="250,44" font="Regular;23" foregroundColor="#FFFFFF" transparent="1" halign="right" valign="center" zPosition="2" /><eLabel position="305,16" size="160,44" backgroundColor="#00FF85" zPosition="1" /><widget name="lbl_score" position="305,16" size="160,30" font="Regular;26" foregroundColor="#000000" backgroundColor="#00FF85" transparent="1" halign="center" valign="center" zPosition="2" /><widget name="lbl_status" position="305,46" size="160,14" font="Regular;8" foregroundColor="#000000" backgroundColor="#00FF85" transparent="1" halign="center" valign="center" zPosition="3" /><eLabel position="465,16" size="300,44" backgroundColor="#80190028" zPosition="1" /><widget name="lbl_away" position="472,16" size="250,44" font="Regular;23" foregroundColor="#FFFFFF" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="a_logo" position="724,20" size="36,36" alphatest="blend" scale="1" zPosition="2" /><eLabel position="765,16" size="5,44" backgroundColor="#F6B900" zPosition="1" /></screen>"""

        self["lbl_league"] = Label("")
        self["lbl_home"] = Label("")
        self["lbl_score"] = Label("")
        self["lbl_away"] = Label("")
        self["lbl_status"] = Label("")
        
        self["h_logo"] = Pixmap()
        self["a_logo"] = Pixmap()
        self["h_logo"].hide()
        self["a_logo"].hide()
        
        self.matches = []
        self.current_match_idx = 0
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close,
            "green": self.switch_to_bottom, 
            "yellow": self.toggle_filter_mini
        }, -1)
        
        self.ticker_timer = eTimer()
        safe_connect(self.ticker_timer, self.show_next_match)
        
        self.refresh_timer = eTimer()
        safe_connect(self.refresh_timer, self.refresh_data)
        
        self.onLayoutFinish.append(self.start_ui)
        self.onClose.append(self.cleanup)

    def cleanup(self):
        # Unregister to prevent crashes after closing
        global_sports_monitor.unregister_callback(self.on_data_ready)

    def start_ui(self):
        # 1. Initial Parse (Show cached data if any)
        self.parse_json()
        # 2. Trigger Fetch (Will call on_data_ready when done)
        global_sports_monitor.check_goals()
        # 3. Start periodic refresh
        self.refresh_timer.start(60000)

    def on_data_ready(self, success):
        # This is called AUTOMATICALLY when Monitor finishes downloading
        self.parse_json()

    def switch_to_bottom(self):
        self.close("next")

    def toggle_filter_mini(self): 
        global_sports_monitor.toggle_filter()
        # Trigger reload to apply filter
        self.parse_json()
            
    def refresh_data(self): 
        global_sports_monitor.check_goals()

    def parse_json(self):
        events = global_sports_monitor.cached_events
        new_matches = []
        
        # If Monitor is empty/loading
        if not events:
            # If we already have matches and an update is in progress, keep old matches to avoid flicker
            if self.matches and "Loading" in global_sports_monitor.status_message:
                return
            msg = global_sports_monitor.status_message or "Loading..."
            self.matches = [{'league': "SimplySports", 'color': 0xffffff, 'home': msg, 'away': "", 'score': "", 'status': "", 'h_url': "", 'a_url': "", 'h_id': "", 'a_id': ""}]
            self.show_next_match()
            return
            
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        tom_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        for event in events:
            status = event.get('status', {})
            state = status.get('type', {}).get('state', 'pre')
            clock = status.get('displayClock', '00:00')
            if ":" in clock: clock = clock.split(':')[0] + "'"
            
            league_name = event.get('league_name', '')
            mode = global_sports_monitor.filter_mode
            ev_date = event.get('date', '')[:10]
            
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
                race = event.get('shortName', 'Event')
                venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                match_data = {'league': league_name, 'home': race, 'away': venue, 'score': "VS", 'status': "SCH", 'h_url': "", 'a_url': "", 'h_id': "", 'a_id': ""}
            else:
                home, away, h_score, a_score = "Home", "Away", "0", "0"
                
                # Tennis/Combat use athlete, team sports use team
                if event_sport_type in [SPORT_TYPE_TENNIS, SPORT_TYPE_COMBAT]:
                    for i, comp in enumerate(comps[:2]):
                        name = comp.get('athlete', {}).get('shortName') or comp.get('athlete', {}).get('displayName') or comp.get('name', 'Player')
                        # Truncate long names
                        if len(name) > 15: name = name[:14] + "."
                        
                        sc = comp.get('score', '')
                        if event_sport_type == SPORT_TYPE_TENNIS:
                            t1, t2 = calculate_tennis_scores(comps, state)
                            sc = t1 if i == 0 else t2
                        
                        if not sc: sc = '0'
                        # Tennis: first competitor = player1/home, second = player2/away
                        if i == 0: home, h_score = name, sc
                        else: away, a_score = name, sc
                else:
                    # Team sports
                    for team in comps:
                        name = team.get('team', {}).get('displayName', 'Team')
                        sc = team.get('score', '0')
                        if team.get('homeAway') == 'home': home, h_score = name, sc
                        else: away, a_score = name, sc
                
                score_str = "VS"; status_str = "SCH"
                if state == 'in': score_str = "{} - {}".format(h_score, a_score); status_str = clock
                elif state == 'post': score_str = "{} - {}".format(h_score, a_score); status_str = "FT"
                
                match_data = {'league': league_name, 'home': home, 'away': away, 'score': score_str, 'status': status_str, 'h_url': h_url, 'a_url': a_url, 'h_id': h_id, 'a_id': a_id}
            new_matches.append(match_data)
            
        # Handle Filter Empty
        if not new_matches:
            # If we are currently updating, don't show "No Matches Found" yet if we have old data
            if self.matches and ("Loading" in global_sports_monitor.status_message or "Processing" in global_sports_monitor.status_message):
                return
                
            is_stale = (time.time() - global_sports_monitor.last_update) > 300
            msg = "Updating Data..." if is_stale else "No Matches Found"
            sub = "Please Wait" if is_stale else "Check Filters"
            new_matches.append({'league': "SimplySports", 'color': 0xffffff, 'home': msg, 'away': sub, 'score': "", 'status': "", 'h_url': "", 'a_url': "", 'h_id': "", 'a_id': ""})

        self.matches = new_matches
        if not self.ticker_timer.isActive(): 
            self.show_next_match()
            self.ticker_timer.start(5000)

    def show_next_match(self):
        if not self.matches: return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matches)
        data = self.matches[self.current_match_idx]
        
        self["lbl_league"].setText(str(data.get('league', '')))
        self["lbl_home"].setText(str(data.get('home', '')))
        self["lbl_score"].setText(str(data.get('score', '')))
        self["lbl_away"].setText(str(data.get('away', '')))
        self["lbl_status"].setText(str(data.get('status', '')))
        
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
# MAIN GUI (FIXED: Cursor Lock Logic)
# ==============================================================================
# ==============================================================================
# EPG HELPERS
# ==============================================================================
def get_sat_position(ref_str):
    if ref_str.startswith("4097:") or ref_str.startswith("5001:"): return "IPTV"
    try:
        parts = ref_str.split(":")
        if len(parts) > 6:
            ns_val = int(parts[6], 16)
            orb_pos = (ns_val >> 16) & 0xFFFF
            if orb_pos == 0xFFFF: return "DVB-T/C"
            if orb_pos > 1800: return "{:.1f}W".format((3600 - orb_pos)/10.0)
            else: return "{:.1f}E".format(orb_pos/10.0)
    except: pass
    return ""

def get_search_keywords(text):
    if not text: return []
    # Stop words to ignore
    STOP_WORDS = ['fc', 'fk', 'club', 'united', 'city', 'real', 'sport', 'sports', 'live', 'tv', 'hd', 'league', 'cup', 'match', 'football', 'soccer', 'basket', 'basketball', 'v', 'vs', 'at', 'de', 'la']
    
    # specialized fix for common prefixes like "Real Madrid" -> "Madrid" is handled by stop words
    # Clean and split
    import re
    clean = re.sub(r'[^\w\s]', ' ', text.lower())
    words = clean.split()
    
    valid = []
    for w in words:
        if len(w) >= 2 and w not in STOP_WORDS:
            valid.append(w)
    return valid

def normalize_text(text):
    if not text: return ""
    # Ensure text is unicode
    try:
        if isinstance(text, str): 
            try: text = text.decode('utf-8', 'ignore')
            except: pass
    except: pass
    
    # Basic Greek to Latin mapping for common chars
    greek_map = {
        u'α': u'a', u'β': u'b', u'γ': u'g', u'δ': u'd', u'ε': u'e', u'ζ': u'z', u'η': u'i', u'θ': u'th',
        u'ι': u'i', u'κ': u'k', u'λ': u'l', u'μ': u'm', u'ν': u'n', u'ξ': u'x', u'ο': u'o', u'π': u'p',
        u'ρ': u'r', u'σ': u's', u'ς': u's', u'τ': u't', u'υ': u'y', u'φ': u'f', u'χ': u'ch', u'ψ': u'ps', u'ω': u'o'
    }
    
    import unicodedata
    import re
    # Lowercase
    t = text.lower()
    
    # Manual transliteration for Greek
    for g, l in greek_map.items():
        t = t.replace(g, l)
        
    # Remove accents/diacritics
    t = u''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    
    # Remove specific punctuation
    t = re.sub(r'[^\w\s]', u' ', t)
    # Remove extra spaces
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def is_same_service(ref1, ref2):
    if not ref1 or not ref2: return False
    s1 = clean_service_ref(str(ref1)).split(':')
    s2 = clean_service_ref(str(ref2)).split(':')
    try:
        for i in range(min(len(s1), len(s2), 7)):
            if s1[i].lower() != s2[i].lower(): return False
        return True
    except: return False

def clean_service_ref(ref_str):
    if not ref_str: return ""
    # Strip any directory path or extra metadata often found in bouquet files
    # Standard format: 1:0:19:SID:TID:NID:NAMESPACE:0:0:0:
    parts = ref_str.split(':')
    if len(parts) > 10:
        return ":".join(parts[:10])
    return ref_str.strip(':')

# Category Colors
CAT_SPORTS = 0x00FF00 # Green
CAT_MOVIE = 0x0000FF # Blue
CAT_NEWS = 0xFFFF00 # Yellow
CAT_DEFAULT = 0xAAAAAA # Grey

def classify_enhanced(channel_name, event_name):
    # Determine category and color based on names
    c_name = channel_name.lower()
    e_name = event_name.lower()
    
    if "sport" in c_name or "football" in c_name or "soccer" in c_name or "espn" in c_name or "bein" in c_name:
        return "Sports", CAT_SPORTS
    if "league" in e_name or "cup" in e_name or "vs" in e_name or "champions" in e_name:
        return "Sports", CAT_SPORTS
        
    if "movie" in c_name or "cinema" in c_name or "film" in c_name:
        return "Movies", CAT_MOVIE
    if "news" in c_name or "cnn" in c_name or "bbc" in c_name:
        return "News", CAT_NEWS
        
    return "Other", CAT_DEFAULT

def get_all_services():
    # Helper to get all TV services from bouquets
    services_list = []
    service_handler = eServiceCenter.getInstance()
    if not service_handler: return []
    
    # Root of all bouquets
    ref_str = '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet'
    bouquet_root = eServiceReference(ref_str)
    bouquet_list = service_handler.list(bouquet_root)
    if not bouquet_list: return []
    
    bouquet_content = bouquet_list.getContent("SN", True)
    if not bouquet_content: return []
    
    for bouquet in bouquet_content:
        # bouquet[0] is the service reference string
        srvs = service_handler.list(eServiceReference(bouquet[0]))
        if srvs:
            # get content returns list of (ref, name)
            chan_list = srvs.getContent("SN", True)
            if chan_list:
                for c in chan_list:
                    # Filter markers/separators
                    if "::" not in c[0]:
                        services_list.append(c)
                        # Safety limit? 
                        if len(services_list) > 10000: return services_list
    return services_list

# Picon Paths
PICON_PATHS = ["/usr/share/enigma2/picon/", "/media/hdd/picon/", "/media/usb/picon/", "/picon/", "/mnt/hdd/picon/"]

def get_picon(service_ref):
    # Try to find picon by service reference
    # Ref: 1:0:1:...
    # Picon name: 1_0_1_... .png (replace : with _)
    if not service_ref: return None
    
    sref_str = str(service_ref).strip()
    # Clean ref for filename
    # Remove last : if exists? No, standard is replace : with _
    picon_name = sref_str.replace(':', '_').rstrip('_') + ".png"
    
    for path in PICON_PATHS:
        full_path = path + picon_name
        if os.path.exists(full_path):
            return LoadPixmap(full_path)
            
    return None

