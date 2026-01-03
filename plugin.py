from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Components.Label import Label
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.GUIComponent import GUIComponent
from Components.HTMLComponent import HTMLComponent
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from twisted.internet import reactor
from twisted.web.client import getPage, downloadPage
from enigma import eTimer, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER
import json
import datetime
import time
import calendar
import os

# ==============================================================================
# CONFIGURATION
# ==============================================================================
CURRENT_VERSION = "1.0"
GITHUB_BASE_URL = "http://raw.githubusercontent.com/Ahmed-Mohammed-Abbas/SimplySports/main/"

# ==============================================================================
# DEBUGGER
# ==============================================================================
def log(msg):
    try:
        with open("/tmp/simply_debug.log", "a") as f:
            f.write(str(msg) + "\n")
    except:
        pass

# ==============================================================================
# GLOBAL SERVICE INSTANCE
# ==============================================================================
global_sports_monitor = None

# ==============================================================================
# LEAGUE DATABASE
# ==============================================================================
DATA_SOURCES = [
    # --- ENGLAND ---
    ("Premier League", "http://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"),
    ("Championship",   "http://site.api.espn.com/apis/site/v2/sports/soccer/eng.2/scoreboard"),
    ("League One",     "http://site.api.espn.com/apis/site/v2/sports/soccer/eng.3/scoreboard"),
    ("League Two",     "http://site.api.espn.com/apis/site/v2/sports/soccer/eng.4/scoreboard"),
    ("FA Cup",         "http://site.api.espn.com/apis/site/v2/sports/soccer/eng.fa/scoreboard"),
    ("Carabao Cup",    "http://site.api.espn.com/apis/site/v2/sports/soccer/eng.league_cup/scoreboard"),
    ("Women's Super Lg","http://site.api.espn.com/apis/site/v2/sports/soccer/eng.w.1/scoreboard"),

    # --- SPAIN ---
    ("La Liga",        "http://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard"),
    ("La Liga 2",      "http://site.api.espn.com/apis/site/v2/sports/soccer/esp.2/scoreboard"),
    ("Copa del Rey",   "http://site.api.espn.com/apis/site/v2/sports/soccer/esp.copa_del_rey/scoreboard"),

    # --- ITALY ---
    ("Serie A",        "http://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard"),
    ("Serie B",        "http://site.api.espn.com/apis/site/v2/sports/soccer/ita.2/scoreboard"),
    ("Coppa Italia",   "http://site.api.espn.com/apis/site/v2/sports/soccer/ita.coppa_italia/scoreboard"),

    # --- GERMANY ---
    ("Bundesliga",     "http://site.api.espn.com/apis/site/v2/sports/soccer/ger.1/scoreboard"),
    ("2. Bundesliga",  "http://site.api.espn.com/apis/site/v2/sports/soccer/ger.2/scoreboard"),
    ("DFB Pokal",      "http://site.api.espn.com/apis/site/v2/sports/soccer/ger.dfb_pokal/scoreboard"),

    # --- FRANCE ---
    ("Ligue 1",        "http://site.api.espn.com/apis/site/v2/sports/soccer/fra.1/scoreboard"),
    ("Ligue 2",        "http://site.api.espn.com/apis/site/v2/sports/soccer/fra.2/scoreboard"),
    ("Coupe de France","http://site.api.espn.com/apis/site/v2/sports/soccer/fra.coupe_de_france/scoreboard"),

    # --- EUROPE (REST) ---
    ("Eredivisie (NED)","http://site.api.espn.com/apis/site/v2/sports/soccer/ned.1/scoreboard"),
    ("Primeira (POR)", "http://site.api.espn.com/apis/site/v2/sports/soccer/por.1/scoreboard"),
    ("Süper Lig (TUR)", "http://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard"),
    ("Scottish Prem",  "http://site.api.espn.com/apis/site/v2/sports/soccer/sco.1/scoreboard"),
    ("Belgian Pro Lg", "http://site.api.espn.com/apis/site/v2/sports/soccer/bel.1/scoreboard"),
    ("Austrian Bund",  "http://site.api.espn.com/apis/site/v2/sports/soccer/aut.1/scoreboard"),
    ("Swiss Super Lg", "http://site.api.espn.com/apis/site/v2/sports/soccer/sui.1/scoreboard"),
    ("Danish Super",   "http://site.api.espn.com/apis/site/v2/sports/soccer/den.1/scoreboard"),
    ("Swedish Allsv",  "http://site.api.espn.com/apis/site/v2/sports/soccer/swe.1/scoreboard"),

    # --- UEFA ---
    ("Champions Lg",   "http://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard"),
    ("Europa League",  "http://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa/scoreboard"),
    ("Conference Lg",  "http://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa.conf/scoreboard"),
    ("Nations League", "http://site.api.espn.com/apis/site/v2/sports/soccer/uefa.nations/scoreboard"),
    ("Euro Qualifiers","http://site.api.espn.com/apis/site/v2/sports/soccer/uefa.euroq/scoreboard"),

    # --- AMERICAS ---
    ("MLS (USA)",      "http://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"),
    ("Liga MX (MEX)",  "http://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/scoreboard"),
    ("Brasileirão",    "http://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard"),
    ("Arg Primera",    "http://site.api.espn.com/apis/site/v2/sports/soccer/arg.1/scoreboard"),
    ("Copa Libertadores","http://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.libertadores/scoreboard"),
    ("Copa Sudamer",   "http://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.sudamericana/scoreboard"),

    # --- ASIA/OCEANIA ---
    ("Saudi Pro Lg",   "http://site.api.espn.com/apis/site/v2/sports/soccer/sa.1/scoreboard"),
    ("A-League (AUS)", "http://site.api.espn.com/apis/site/v2/sports/soccer/aus.1/scoreboard"),
    ("Chinese Super Lg","http://site.api.espn.com/apis/site/v2/sports/soccer/chn.1/scoreboard"),

    # --- BASKETBALL ---
    ("NBA",            "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"),
    ("WNBA",           "http://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"),
    ("NCAA Basket (M)","http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"),
    ("NCAA Basket (W)","http://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard"),
    ("EuroLeague",     "http://site.api.espn.com/apis/site/v2/sports/basketball/eurl.euroleague/scoreboard"),

    # --- US SPORTS ---
    ("NFL (Football)", "http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"),
    ("NCAA Football",  "http://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"),
    ("UFL (Football)", "http://site.api.espn.com/apis/site/v2/sports/football/ufl/scoreboard"),
    ("NHL (Hockey)",   "http://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"),
    ("MLB (Baseball)", "http://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"),
    ("NCAA Baseball",  "http://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/scoreboard"),

    # --- RACING & FIGHTING ---
    ("Formula 1",      "http://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard"),
    ("NASCAR Cup",     "http://site.api.espn.com/apis/site/v2/sports/racing/nascar-premier/scoreboard"),
    ("UFC / MMA",      "http://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"),
]

# ==============================================================================
# UTILS
# ==============================================================================
def get_local_time_str(utc_date_str):
    try:
        if 'T' in utc_date_str:
            date_part, time_part = utc_date_str.split('T')
            y, m, d = map(int, date_part.split('-'))
            time_part = time_part.replace('Z', '')
            H, M = map(int, time_part.split(':')[:2])
            
            dt_utc = datetime.datetime(y, m, d, H, M)
            timestamp = calendar.timegm(dt_utc.timetuple())
            
            local_struct = time.localtime(timestamp)
            local_dt = datetime.datetime.fromtimestamp(timestamp)
            now = datetime.datetime.now()
            
            time_str = "{:02d}:{:02d}".format(local_struct.tm_hour, local_struct.tm_min)
            if local_dt.date() == now.date():
                return str(time_str)
            else:
                date_str = local_dt.strftime("%a %d %b")
                return "{} {}".format(date_str, time_str)
    except:
        return "--:--"

# ==============================================================================
# LIST RENDERER
# ==============================================================================
def SportListEntry(entry):
    try:
        status, home, score, away, time_str, venue, full_status = entry
        
        status = str(status)
        home = str(home)
        score = str(score)
        away = str(away)
        time_str = str(time_str)
        
        col_white = 0xFFFFFF
        col_gold = 0xFFD700
        col_green = 0x00FF00
        col_red = 0xFF3333
        col_gray = 0xAAAAAA
        col_blue = 0x88CCFF
        
        status_col = col_gray
        if status == "LIVE": status_col = col_green
        elif status == "FIN": status_col = col_red
        
        time_col = col_white
        if len(time_str) > 6:
            time_col = col_blue
        
        res = [entry]
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 5, 80, 40, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, status, status_col))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 110, 5, 380, 40, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, home, col_white))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 500, 5, 200, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score, col_gold))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 710, 5, 380, 40, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, away, col_white))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1100, 5, 220, 40, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, time_str, time_col))
        return res
    except:
        return []

# ==============================================================================
# BACKGROUND MONITOR
# ==============================================================================
class SportsMonitor:
    def __init__(self):
        self.active = False
        self.current_league_index = 0
        self.last_scores = {}
        self.timer = eTimer()
        self.timer.callback.append(self.check_goals)
        self.session = None
        self.cached_events = [] 
        self.callbacks = []

    def set_session(self, session):
        self.session = session

    def register_callback(self, func):
        if func not in self.callbacks:
            self.callbacks.append(func)

    def unregister_callback(self, func):
        if func in self.callbacks:
            self.callbacks.remove(func)

    def toggle_activity(self):
        self.active = not self.active
        if self.active:
            self.timer.start(60000, False)
            self.check_goals()
        else:
            self.timer.stop()
        return self.active

    def set_league(self, index):
        if index >= 0 and index < len(DATA_SOURCES):
            self.current_league_index = index
            self.last_scores = {}
            self.cached_events = []
            self.check_goals()

    def check_goals(self):
        try:
            if self.current_league_index < len(DATA_SOURCES):
                name, url = DATA_SOURCES[self.current_league_index]
                log("Fetching: " + name)
                getPage(url).addCallback(self.parse_json).addErrback(self.error_fetch)
        except Exception as e:
            log("Fetch Error: " + str(e))

    def error_fetch(self, error):
        log("Network Error: " + str(error))
        for cb in self.callbacks:
            cb(False)

    def parse_json(self, json_data):
        try:
            data = json.loads(json_data)
            events = data.get('events', [])
            self.cached_events = events 
            log("Got " + str(len(events)) + " events")
            
            for cb in self.callbacks:
                cb(True)

            if not self.active or self.session is None: return

            for event in events:
                status = event.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                
                if state == 'in':
                    comps = event.get('competitions', [{}])[0].get('competitors', [])
                    home, away, h_score, a_score = "", "", "0", "0"
                    for team in comps:
                        name = team.get('team', {}).get('shortDisplayName', 'Tm')
                        sc = team.get('score', '0')
                        if team.get('homeAway') == 'home': home, h_score = name, sc
                        else: away, a_score = name, sc
                    
                    match_id = home + "_" + away
                    score_str = str(h_score) + "-" + str(a_score)
                    
                    if match_id in self.last_scores:
                        if self.last_scores[match_id] != score_str:
                            try:
                                self.session.open(GoalToast, "GOAL! {} {} - {} {}".format(home, h_score, a_score, away))
                            except:
                                self.active = False
                    
                    self.last_scores[match_id] = score_str
        except Exception as e:
            log("Parse Error: " + str(e))
            for cb in self.callbacks:
                cb(False)

if global_sports_monitor is None:
    global_sports_monitor = SportsMonitor()

# ==============================================================================
# UI SCREENS
# ==============================================================================
class GoalToast(Screen):
    skin = """
        <screen position="center,50" size="800,120" title="Goal" flags="wfNoBorder" backgroundColor="#40000000">
            <eLabel position="0,0" size="800,120" backgroundColor="#cc0000" zPosition="0" />
            <eLabel position="0,110" size="800,5" backgroundColor="#FFD700" zPosition="1" />
            <widget name="title" position="0,10" size="800,40" font="Regular;32" foregroundColor="#FFD700" backgroundColor="#cc0000" transparent="1" halign="center" zPosition="2" />
            <widget name="message" position="0,60" size="800,50" font="Regular;32" foregroundColor="#FFFFFF" backgroundColor="#cc0000" transparent="1" halign="center" zPosition="2" />
        </screen>
    """
    def __init__(self, session, match_text):
        Screen.__init__(self, session)
        self["title"] = Label("!!! GOAL SCORED !!!")
        self["message"] = Label(match_text)
        self.timer = eTimer()
        self.timer.callback.append(self.close)
        self.timer.start(6000, True)

class SimpleSportsMiniBar(Screen):
    skin = """
        <screen position="0,980" size="1920,100" title="Sports Ticker" backgroundColor="#40000000" flags="wfNoBorder">
            <eLabel position="0,10" size="1920,90" backgroundColor="#151515" zPosition="-1" />
            <eLabel position="0,10" size="1920,2" backgroundColor="#00FF00" zPosition="0" />
            <widget name="league_name" position="40,25" size="350,60" font="Regular;32" foregroundColor="#00FF00" backgroundColor="#151515" transparent="1" valign="center" />
            <eLabel position="400,25" size="2,60" backgroundColor="#333333" />
            <widget name="match_info" position="430,20" size="1450,70" font="Regular;36" foregroundColor="#FFFFFF" backgroundColor="#151515" transparent="1" valign="center" halign="left" />
            <widget name="credit" position="1600,60" size="300,30" font="Regular;20" foregroundColor="#555555" backgroundColor="#151515" transparent="1" halign="right" />
        </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self.matches = []
        self.current_match_idx = 0
        self["league_name"] = Label("MINI MODE")
        self["match_info"] = Label("Loading...")
        self["credit"] = Label("Dev: Reali22")
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close, "green": self.close 
        }, -1)
        
        self.ticker_timer = eTimer()
        self.ticker_timer.callback.append(self.show_next_match)
        self.onLayoutFinish.append(self.load_data)

    def load_data(self):
        try:
            if global_sports_monitor.current_league_index < len(DATA_SOURCES):
                name = DATA_SOURCES[global_sports_monitor.current_league_index][0]
                self["league_name"].setText(name)
            
            events = global_sports_monitor.cached_events
            self.matches = []
            
            for event in events:
                status = event.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                clock = status.get('displayClock', '')
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                home, away, h_score, a_score = "Home", "Away", "0", "0"
                for team in comps:
                    name = team.get('team', {}).get('shortDisplayName', 'Tm')
                    sc = team.get('score', '0')
                    if team.get('homeAway') == 'home': home, h_score = name, sc
                    else: away, a_score = name, sc
                
                if state == 'in': txt = "LIVE {}' :: {} {} - {} {}".format(clock, home, h_score, a_score, away)
                elif state == 'post': txt = "FIN :: {} {} - {} {}".format(home, h_score, a_score, away)
                else: txt = "{} vs {}".format(home, away)
                self.matches.append(txt)
                
            if self.matches:
                self.show_next_match()
                self.ticker_timer.start(4000)
            else:
                self["match_info"].setText("No games available.")
        except:
             self["match_info"].setText("Data Error")

    def show_next_match(self):
        if not self.matches: return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matches)
        self["match_info"].setText(self.matches[self.current_match_idx])

# ==============================================================================
# MAIN GUI
# ==============================================================================
class SimpleSportsScreen(Screen):
    skin = """
        <screen position="center,center" size="1280,720" title="SimplySports" backgroundColor="#40000000" flags="wfNoBorder">
            <eLabel position="0,0" size="1280,720" backgroundColor="#40000000" zPosition="-1" />
            <eLabel position="0,0" size="1280,85" backgroundColor="#002244" zPosition="0" />
            <eLabel position="0,85" size="1280,3" backgroundColor="#FFD700" zPosition="1" />
            
            <widget name="header" position="20,15" size="1000,60" font="Regular;38" foregroundColor="#FFFFFF" backgroundColor="#002244" transparent="1" valign="center" />
            <widget name="disc_status" position="1050,15" size="200,60" font="Regular;28" foregroundColor="#AAAAAA" backgroundColor="#002244" transparent="1" halign="right" valign="center" />
            
            <widget name="league_title" position="30,100" size="1220,50" font="Regular;34" foregroundColor="#00FF00" backgroundColor="#40000000" transparent="1" halign="center" />
            
            <eLabel position="30,160" size="1220,2" backgroundColor="#555555" />
            <widget name="lab_status" position="30,170" size="100,40" font="Regular;22" foregroundColor="#AAAAAA" backgroundColor="#40000000" transparent="1" text="STATE" />
            <widget name="lab_home" position="150,170" size="380,40" font="Regular;22" foregroundColor="#AAAAAA" backgroundColor="#40000000" transparent="1" halign="right" text="HOME TEAM" />
            <widget name="lab_score" position="540,170" size="120,40" font="Regular;22" foregroundColor="#FFD700" backgroundColor="#40000000" transparent="1" halign="center" text="SCORE" />
            <widget name="lab_away" position="670,170" size="380,40" font="Regular;22" foregroundColor="#AAAAAA" backgroundColor="#40000000" transparent="1" halign="left" text="AWAY TEAM" />
            <widget name="lab_time" position="1060,170" size="150,40" font="Regular;22" foregroundColor="#AAAAAA" backgroundColor="#40000000" transparent="1" halign="right" text="DATE/TIME" />
            <eLabel position="30,215" size="1220,2" backgroundColor="#555555" />
            
            <widget name="list" position="20,230" size="1240,430" scrollbarMode="showOnDemand" transparent="1" />
            
            <eLabel position="0,670" size="1280,50" backgroundColor="#181818" zPosition="0" />
            <eLabel position="0,670" size="1280,2" backgroundColor="#333333" zPosition="1" />
            
            <eLabel position="30,680" size="30,30" backgroundColor="#FF5555" zPosition="2" />
            <widget name="key_red" position="70,680" size="220,35" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#181818" transparent="1" zPosition="2" />
            
            <eLabel position="300,680" size="30,30" backgroundColor="#55FF55" zPosition="2" />
            <widget name="key_green" position="340,680" size="220,35" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#181818" transparent="1" zPosition="2" />
            
            <eLabel position="570,680" size="30,30" backgroundColor="#FFFF55" zPosition="2" />
            <widget name="key_yellow" position="610,680" size="220,35" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#181818" transparent="1" zPosition="2" />
            
            <eLabel position="840,680" size="30,30" backgroundColor="#5555FF" zPosition="2" />
            <widget name="key_blue" position="880,680" size="240,35" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#181818" transparent="1" zPosition="2" />

            <eLabel position="1120,680" size="30,30" backgroundColor="#777777" zPosition="2" />
            <widget name="key_menu" position="1160,680" size="150,35" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#181818" transparent="1" zPosition="2" />
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        
        global_sports_monitor.set_session(session)
        self.monitor = global_sports_monitor
        self.live_only_filter = False
        
        self.monitor.register_callback(self.refresh_ui)
        
        self["header"] = Label("SimplySports CENTER")
        self["disc_status"] = Label("DISCOVERY: OFF")
        self["league_title"] = Label("LOADING DATA...")
        
        self["lab_status"] = Label("STATE")
        self["lab_home"] = Label("HOME")
        self["lab_score"] = Label("SCORE")
        self["lab_away"] = Label("AWAY")
        self["lab_time"] = Label("DATE / TIME")
        
        self["list"] = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
        self["list"].l.setFont(0, gFont("Regular", 28))
        self["list"].l.setItemHeight(50)
        
        self["key_red"] = Label("LEAGUES")
        self["key_green"] = Label("MINI MODE")
        self["key_yellow"] = Label("LIVE ONLY")
        self["key_blue"] = Label("DISCOVERY")
        self["key_menu"] = Label("UPDATE")
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "MenuActions"], {
            "cancel": self.close,
            "red": self.open_league_select,
            "green": self.open_mini_bar,
            "yellow": self.toggle_filter,
            "blue": self.toggle_discovery,
            "menu": self.check_for_updates,
            "up": self["list"].up,
            "down": self["list"].down,
        }, -1)
        
        self.onLayoutFinish.append(self.start_ui)
        self.onClose.append(self.cleanup)

    def start_ui(self):
        self.update_header()
        self["league_title"].setText("DOWNLOADING DATA...")
        self.monitor.check_goals()

    def cleanup(self):
        self.monitor.unregister_callback(self.refresh_ui)

    def update_header(self):
        try:
            curr_league = DATA_SOURCES[self.monitor.current_league_index][0]
            self["header"].setText("SimplySports")
            self["league_title"].setText(curr_league.upper() + " FIXTURES")
            
            if self.monitor.active:
                self["disc_status"].setText("DISCOVERY: ON")
                self["key_blue"].setText("DISCOVERY: ON")
            else:
                self["disc_status"].setText("DISCOVERY: OFF")
                self["key_blue"].setText("DISCOVERY: OFF")
        except: pass

    def toggle_discovery(self):
        is_active = self.monitor.toggle_activity()
        self.update_header()
        if is_active:
             self.session.open(MessageBox, "Discovery Mode ON\nBackground notifications active.", MessageBox.TYPE_INFO, timeout=2)

    def toggle_filter(self):
        self.live_only_filter = not self.live_only_filter
        if self.live_only_filter: self["key_yellow"].setText("SHOW ALL")
        else: self["key_yellow"].setText("LIVE ONLY")
        self.refresh_ui(True)

    def open_league_select(self):
        options = []
        for idx, (name, url) in enumerate(DATA_SOURCES):
            options.append((name, idx))
        self.session.openWithCallback(self.league_selected, ChoiceBox, title="Select League", list=options)

    def league_selected(self, selection):
        if selection:
            self.monitor.set_league(selection[1])
            self.update_header()
            self["league_title"].setText("DOWNLOADING...")

    def open_mini_bar(self):
        self.session.open(SimpleSportsMiniBar)

    # ---------------- UPDATE LOGIC ----------------
    def check_for_updates(self):
        self["league_title"].setText("CHECKING UPDATES...")
        url = GITHUB_BASE_URL + "version.txt"
        getPage(url.encode('utf-8')).addCallback(self.got_version).addErrback(self.update_fail)

    def got_version(self, data):
        try:
            remote_version = data.decode('utf-8').strip()
            if remote_version > CURRENT_VERSION:
                self.session.openWithCallback(self.start_update, MessageBox, 
                    "New version " + remote_version + " available!\n(Current: " + CURRENT_VERSION + ")\nUpdate now?", 
                    MessageBox.TYPE_YESNO)
            else:
                self.session.open(MessageBox, "You have the latest version.", MessageBox.TYPE_INFO)
                self.update_header()
        except:
            self.update_fail(None)

    def update_fail(self, error):
        self.session.open(MessageBox, "Update check failed.\nCheck internet or GitHub URL.", MessageBox.TYPE_ERROR)
        self.update_header()

    def start_update(self, answer):
        if answer:
            self["league_title"].setText("DOWNLOADING UPDATE...")
            url = GITHUB_BASE_URL + "plugin.py"
            target = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/plugin.py")
            downloadPage(url.encode('utf-8'), target).addCallback(self.update_finished).addErrback(self.update_fail)

    def update_finished(self, data):
        self.session.open(MessageBox, "Update Successful!\nPlease restart GUI.", MessageBox.TYPE_INFO)
    # -----------------------------------------------

    def refresh_ui(self, success):
        if not success:
            self["league_title"].setText("CONNECTION FAILED")
            return

        self.update_header()
        events = self.monitor.cached_events
        
        if not events: 
            self["list"].setList([])
            self["league_title"].setText("NO GAMES TODAY")
            return

        list_content = []
        for event in events:
            try:
                status = event.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                utc_date = event.get('date', '')
                local_time = get_local_time_str(utc_date)
                
                venue_data = event.get('competitions', [{}])[0].get('venue', {})
                venue = venue_data.get('fullName', '')
                
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                home, away, h_score, a_score = "", "", "0", "0"
                for team in comps:
                    name = team.get('team', {}).get('shortDisplayName', 'Tm')
                    sc = team.get('score', '0')
                    if team.get('homeAway') == 'home': home, h_score = name, sc
                    else: away, a_score = name, sc

                status_short = "SCH"
                score_display = "vs"
                if state == 'in': 
                    status_short = "LIVE"
                    score_display = h_score + " - " + a_score
                elif state == 'post': 
                    status_short = "FIN"
                    score_display = h_score + " - " + a_score

                if self.live_only_filter and state != 'in': continue

                entry_data = (status_short, home, score_display, away, local_time, venue, "")
                list_content.append(SportListEntry(entry_data))
            except: continue
        self["list"].setList(list_content)

def main(session, **kwargs):
    session.open(SimpleSportsScreen)

def Plugins(**kwargs):
    # This automatically finds picon.png in your plugin folder
    iconPath = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/picon.png")
    return [
        PluginDescriptor(name="SimplySports", description="Live Scores by Reali22", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main, icon=iconPath),
        PluginDescriptor(name="SimplySports Monitor", where=PluginDescriptor.WHERE_SESSIONSTART, fnc=lambda session, **kwargs: global_sports_monitor.set_session(session))
    ]
