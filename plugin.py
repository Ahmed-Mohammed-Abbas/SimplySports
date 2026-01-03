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
from twisted.internet import reactor, ssl
from twisted.web.client import Agent, readBody, getPage, downloadPage
from twisted.web.http_headers import Headers
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
GITHUB_BASE_URL = "https://raw.githubusercontent.com/Ahmed-Mohammed-Abbas/SimplySports/main/"
CONFIG_FILE = "/etc/enigma2/simply_sports.json"

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
    ("Premier League", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"),
    ("Championship",   "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.2/scoreboard"),
    ("League One",     "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.3/scoreboard"),
    ("League Two",     "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.4/scoreboard"),
    ("FA Cup",         "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.fa/scoreboard"),
    ("Carabao Cup",    "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.league_cup/scoreboard"),
    ("Women's Super Lg","https://site.api.espn.com/apis/site/v2/sports/soccer/eng.w.1/scoreboard"),

    # --- SPAIN ---
    ("La Liga",        "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard"),
    ("La Liga 2",      "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.2/scoreboard"),
    ("Copa del Rey",   "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.copa_del_rey/scoreboard"),

    # --- ITALY ---
    ("Serie A",        "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard"),
    ("Serie B",        "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.2/scoreboard"),
    ("Coppa Italia",   "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.coppa_italia/scoreboard"),

    # --- GERMANY ---
    ("Bundesliga",     "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.1/scoreboard"),
    ("2. Bundesliga",  "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.2/scoreboard"),
    ("DFB Pokal",      "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.dfb_pokal/scoreboard"),

    # --- FRANCE ---
    ("Ligue 1",        "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.1/scoreboard"),
    ("Ligue 2",        "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.2/scoreboard"),
    ("Coupe de France","https://site.api.espn.com/apis/site/v2/sports/soccer/fra.coupe_de_france/scoreboard"),

    # --- EUROPE (REST) ---
    ("Eredivisie (NED)","https://site.api.espn.com/apis/site/v2/sports/soccer/ned.1/scoreboard"),
    ("Primeira (POR)", "https://site.api.espn.com/apis/site/v2/sports/soccer/por.1/scoreboard"),
    ("Süper Lig (TUR)", "https://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard"),
    ("Scottish Prem",  "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.1/scoreboard"),
    ("Belgian Pro Lg", "https://site.api.espn.com/apis/site/v2/sports/soccer/bel.1/scoreboard"),
    ("Austrian Bund",  "https://site.api.espn.com/apis/site/v2/sports/soccer/aut.1/scoreboard"),
    ("Swiss Super Lg", "https://site.api.espn.com/apis/site/v2/sports/soccer/sui.1/scoreboard"),
    ("Danish Super",   "https://site.api.espn.com/apis/site/v2/sports/soccer/den.1/scoreboard"),
    ("Swedish Allsv",  "https://site.api.espn.com/apis/site/v2/sports/soccer/swe.1/scoreboard"),

    # --- UEFA ---
    ("Champions Lg",   "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard"),
    ("Europa League",  "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa/scoreboard"),
    ("Conference Lg",  "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa.conf/scoreboard"),
    ("Nations League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.nations/scoreboard"),
    ("Euro Qualifiers","https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.euroq/scoreboard"),

    # --- AMERICAS ---
    ("MLS (USA)",      "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"),
    ("Liga MX (MEX)",  "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/scoreboard"),
    ("Brasileirão",    "https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard"),
    ("Arg Primera",    "https://site.api.espn.com/apis/site/v2/sports/soccer/arg.1/scoreboard"),
    ("Copa Libertadores","https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.libertadores/scoreboard"),
    ("Copa Sudamer",   "https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.sudamericana/scoreboard"),

    # --- ASIA/OCEANIA ---
    ("Saudi Pro Lg",   "https://site.api.espn.com/apis/site/v2/sports/soccer/sa.1/scoreboard"),
    ("A-League (AUS)", "https://site.api.espn.com/apis/site/v2/sports/soccer/aus.1/scoreboard"),
    ("Chinese Super Lg","https://site.api.espn.com/apis/site/v2/sports/soccer/chn.1/scoreboard"),

    # --- BASKETBALL ---
    ("NBA",            "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"),
    ("WNBA",           "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"),
    ("NCAA Basket (M)","https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"),
    ("NCAA Basket (W)","https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard"),
    ("EuroLeague",     "https://site.api.espn.com/apis/site/v2/sports/basketball/eurl.euroleague/scoreboard"),

    # --- US SPORTS ---
    ("NFL (Football)", "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"),
    ("NCAA Football",  "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"),
    ("UFL (Football)", "https://site.api.espn.com/apis/site/v2/sports/football/ufl/scoreboard"),
    ("NHL (Hockey)",   "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"),
    ("MLB (Baseball)", "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"),
    ("NCAA Baseball",  "https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/scoreboard"),

    # --- RACING & FIGHTING ---
    ("Formula 1",      "https://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard"),
    ("NASCAR Cup",     "https://site.api.espn.com/apis/site/v2/sports/racing/nascar-premier/scoreboard"),
    ("UFC / MMA",      "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"),
]

# ==============================================================================
# UTILS
# ==============================================================================
def get_local_time_str(utc_date_str):
    try:
        # Expected format: "2023-10-25T19:00Z"
        if 'T' in utc_date_str:
            date_part, time_part = utc_date_str.split('T')
            y, m, d = map(int, date_part.split('-'))
            time_part = time_part.replace('Z', '')
            H, M = map(int, time_part.split(':')[:2])
            
            dt_utc = datetime.datetime(y, m, d, H, M)
            timestamp = calendar.timegm(dt_utc.timetuple())
            
            # Convert to local time
            local_dt = datetime.datetime.fromtimestamp(timestamp)
            now = datetime.datetime.now()
            
            # Format time (HH:MM)
            time_str = "{:02d}:{:02d}".format(local_dt.hour, local_dt.minute)
            
            # Logic: If today, show time. If future/past, show Date + Time
            if local_dt.date() == now.date():
                return str(time_str)
            else:
                # Format: "Mon 23/10 20:00"
                # %a=Short Day, %d=Day, %m=Month
                return local_dt.strftime("%a %d/%m") + " " + time_str
    except:
        return "--:--"

# ==============================================================================
# LIST RENDERER
# ==============================================================================
def SportListEntry(entry):
    try:
        status, left_text, score_text, right_text, time_str, goal_side, is_live = entry
        
        status = str(status)
        left_text = str(left_text)
        score_text = str(score_text)
        right_text = str(right_text)
        time_str = str(time_str)
        
        col_white = 0xFFFFFF
        col_gold = 0xFFD700
        col_green = 0x00FF00
        col_red = 0xFF3333
        col_gray = 0xAAAAAA
        col_blue = 0x88CCFF
        
        left_col = col_white
        right_col = col_white
        
        if goal_side == 'home':
            left_text = "(!) " + left_text
            left_col = col_gold
        elif goal_side == 'away':
            right_text = right_text + " (!)"
            right_col = col_gold
        
        status_col = col_gray
        if status == "LIVE": status_col = col_green
        elif status == "FIN": status_col = col_red
        elif status == "INFO": status_col = col_blue
        
        time_col = col_white
        if is_live: 
            time_col = col_green
        elif "/" in time_str: 
            # If it contains a date slash, color it blue-ish to distinguish
            time_col = col_blue
        
        res = [entry]
        # Adjusted widths to fit potential date string in rightmost column
        # Total Width: 620
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 5, 5, 50, 45, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, status, status_col))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 60, 5, 180, 45, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, left_text, left_col))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 245, 5, 80, 45, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, col_gold))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 330, 5, 180, 45, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, right_col))
        # Expanded time column width to 105 to fit "Mon 23/10 20:00"
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 510, 5, 105, 45, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, time_str, time_col))
        
        return res
    except:
        return []

# ==============================================================================
# BACKGROUND SERVICE & SHARED STATE
# ==============================================================================
class SportsMonitor:
    def __init__(self):
        self.active = False
        self.current_league_index = 0
        self.last_scores = {}
        self.goal_flags = {}
        self.live_only_filter = False
        self.timer = eTimer()
        self.timer.callback.append(self.check_goals)
        self.session = None
        self.cached_events = [] 
        self.callbacks = []
        self.status_message = "Initializing..."
        
        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.current_league_index = int(data.get("league_index", 0))
                    self.live_only_filter = bool(data.get("filter", False))
                    self.active = bool(data.get("active", False))
                    if self.active:
                        self.timer.start(60000, False)
            except Exception as e:
                log("Error loading config: " + str(e))

    def save_config(self):
        data = {
            "league_index": self.current_league_index,
            "filter": self.live_only_filter,
            "active": self.active
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            log("Error saving config: " + str(e))

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
        self.save_config()
        return self.active

    def toggle_filter(self):
        self.live_only_filter = not self.live_only_filter
        self.save_config()
        return self.live_only_filter

    def set_league(self, index):
        if index >= 0 and index < len(DATA_SOURCES):
            self.current_league_index = index
            self.last_scores = {}
            self.save_config()
            self.check_goals()

    def check_goals(self):
        try:
            name, url = DATA_SOURCES[self.current_league_index]
            self.status_message = "Loading Data..."
            for cb in self.callbacks: cb(False) 
            
            agent = Agent(reactor)
            d = agent.request(b'GET', url.encode('utf-8'))
            d.addCallback(self.handle_response)
            d.addErrback(self.handle_error) 
        except: pass

    def handle_error(self, failure):
        log("API Error: " + str(failure))
        self.status_message = "API Connection Error"
        self.cached_events = []
        for cb in self.callbacks: cb(True)

    def handle_response(self, response):
        if response.code == 200:
            d = readBody(response)
            d.addCallback(self.parse_json)
        else:
            self.status_message = "HTTP Error: " + str(response.code)
            self.cached_events = []
            for cb in self.callbacks: cb(True)

    def parse_json(self, body):
        try:
            json_str = body.decode('utf-8', errors='ignore')
            data = json.loads(json_str)
            events = data.get('events', [])
            self.cached_events = events 
            
            if len(events) == 0:
                self.status_message = "No Matches Scheduled"
            else:
                self.status_message = "Data Updated"

            now = time.time()
            keys_to_del = []
            for mid, info in self.goal_flags.items():
                if now - info['time'] > 60:
                    keys_to_del.append(mid)
            for k in keys_to_del:
                del self.goal_flags[k]

            for event in events:
                status = event.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                
                if state == 'in':
                    comps = event.get('competitions', [{}])[0].get('competitors', [])
                    if len(comps) > 2: continue 
                    
                    home, away, h_score, a_score = "Home", "Away", 0, 0
                    for team in comps:
                        name = team.get('team', {}).get('shortDisplayName', 'Tm')
                        sc = int(team.get('score', '0'))
                        if team.get('homeAway') == 'home': home, h_score = name, sc
                        else: away, a_score = name, sc
                    
                    match_id = home + "_" + away
                    score_str = str(h_score) + "-" + str(a_score)
                    
                    if match_id in self.last_scores:
                        if self.last_scores[match_id] != score_str:
                            try:
                                prev_h, prev_a = map(int, self.last_scores[match_id].split('-'))
                                if h_score > prev_h:
                                    self.goal_flags[match_id] = {'side': 'home', 'time': time.time()}
                                elif a_score > prev_a:
                                    self.goal_flags[match_id] = {'side': 'away', 'time': time.time()}
                                
                                if self.active and self.session:
                                    self.session.open(GoalToast, "GOAL! {} {} - {} {}".format(home, h_score, a_score, away))
                            except: pass
                    
                    self.last_scores[match_id] = score_str

            for cb in self.callbacks:
                cb(True)
        except Exception as e:
            self.status_message = "JSON Parse Error"
            log("Parse Error: " + str(e))
            for cb in self.callbacks: cb(True)

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
    # PREMIUM SKIN DESIGN
    # #AA000000 = Semi-transparent Black (AA is Alpha)
    # Height reduced to 60px for a sleek look
    # Floating near bottom (1020 Y-position)
    skin = """
        <screen position="center,980" size="1800,60" title="Sports Ticker" backgroundColor="#40000000" flags="wfNoBorder">
            <eLabel position="0,0" size="1800,60" backgroundColor="#AA000000" zPosition="-1" />
            
            <eLabel position="0,0" size="5,60" backgroundColor="#FFD700" zPosition="1" />
            
            <widget name="league_name" position="20,0" size="300,60" font="Regular;28" foregroundColor="#FFD700" backgroundColor="#AA000000" transparent="1" valign="center" halign="left" />
            
            <eLabel position="330,15" size="2,30" backgroundColor="#555555" zPosition="1" />
            
            <widget name="match_info" position="350,0" size="1100,60" font="Regular;30" foregroundColor="#FFFFFF" backgroundColor="#AA000000" transparent="1" valign="center" halign="left" />
            
            <widget name="filter_status" position="1500,0" size="280,60" font="Regular;24" foregroundColor="#AAAAAA" backgroundColor="#AA000000" transparent="1" valign="center" halign="right" />
        </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self.matches = []
        self.current_match_idx = 0
        self["league_name"] = Label("Loading...")
        self["match_info"] = Label("Loading...")
        self["filter_status"] = Label("")
        self["credit"] = Label("")
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close, 
            "green": self.close,
            "yellow": self.toggle_filter_mini
        }, -1)
        
        self.ticker_timer = eTimer()
        self.ticker_timer.callback.append(self.show_next_match)
        self.refresh_timer = eTimer()
        self.refresh_timer.callback.append(self.load_data)
        self.onLayoutFinish.append(self.start_all_timers)

    def start_all_timers(self):
        try:
            current_name = DATA_SOURCES[global_sports_monitor.current_league_index][0]
            self["league_name"].setText(current_name)
        except:
            self["league_name"].setText("Unknown")

        self.update_filter_label()
        self.load_data()
        self.refresh_timer.start(60000)

    def toggle_filter_mini(self):
        global_sports_monitor.toggle_filter()
        self.update_filter_label()
        self.load_data() 

    def update_filter_label(self):
        if global_sports_monitor.live_only_filter:
            self["filter_status"].setText("LIVE ONLY")
        else:
            self["filter_status"].setText("")

    def load_data(self):
        global_sports_monitor.check_goals()
        self.parse_json()

    def parse_json(self):
        events = global_sports_monitor.cached_events
        self.matches = []
        
        if not events:
            self["match_info"].setText(global_sports_monitor.status_message)
            return

        for event in events:
            status = event.get('status', {})
            state = status.get('type', {}).get('state', 'pre')
            clock = status.get('displayClock', '00:00')
            utc_date = event.get('date', '')
            local_time = get_local_time_str(utc_date) # Now returns Time or Date+Time
            
            if global_sports_monitor.live_only_filter and state != 'in':
                continue

            comps = event.get('competitions', [{}])[0].get('competitors', [])
            if len(comps) > 2:
                race = event.get('shortName', 'Race')
                venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                txt = "{} @ {}".format(race, venue)
            else:
                home, away, h_score, a_score = "Home", "Away", "0", "0"
                for team in comps:
                    name = team.get('team', {}).get('shortDisplayName', 'Tm')
                    sc = team.get('score', '0')
                    if team.get('homeAway') == 'home': home, h_score = name, sc
                    else: away, a_score = name, sc
                
                match_id = home + "_" + away
                goal_flag = ""
                if match_id in global_sports_monitor.goal_flags: goal_flag = " GOAL!"
                
                if state == 'in': 
                    txt = "LIVE {}' :: {}{} {} - {} {}".format(clock, home, goal_flag, h_score, a_score, away)
                elif state == 'post': 
                    txt = "FIN :: {} {} - {} {}".format(home, h_score, a_score, away)
                else: 
                    # Use the improved local_time string (might contain date)
                    txt = "{} :: {} vs {}".format(local_time, home, away)
                    
            self.matches.append(txt)
        
        if self.matches:
            if not self.ticker_timer.isActive():
                self.show_next_match()
                self.ticker_timer.start(4000)
        else:
            msg = "No live games." if global_sports_monitor.live_only_filter else global_sports_monitor.status_message
            self["match_info"].setText(msg)

    def show_next_match(self):
        if not self.matches: return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matches)
        self["match_info"].setText(self.matches[self.current_match_idx])

class SimpleSportsScreen(Screen):
    skin = """
        <screen position="0,0" size="620,720" title="SimplySports" backgroundColor="#40000000" flags="wfNoBorder">
            <eLabel position="0,0" size="620,720" backgroundColor="#40000000" zPosition="-1" />
            <eLabel position="0,0" size="620,80" backgroundColor="#002244" zPosition="0" />
            <eLabel position="0,80" size="620,3" backgroundColor="#FFD700" zPosition="1" />
            
            <widget name="header" position="10,5" size="600,40" font="Regular;32" foregroundColor="#FFFFFF" backgroundColor="#002244" transparent="1" valign="center" halign="center" />
            <widget name="league_title" position="10,45" size="600,30" font="Regular;26" foregroundColor="#00FF00" backgroundColor="#002244" transparent="1" halign="center" />
            
            <eLabel position="5,90" size="610,2" backgroundColor="#555555" />
            <widget name="lab_status" position="5,95" size="50,30" font="Regular;20" foregroundColor="#AAAAAA" backgroundColor="#40000000" transparent="1" text="ST" />
            <widget name="lab_home" position="60,95" size="180,30" font="Regular;20" foregroundColor="#AAAAAA" backgroundColor="#40000000" transparent="1" halign="right" text="HOME" />
            <widget name="lab_score" position="245,95" size="80,30" font="Regular;20" foregroundColor="#FFD700" backgroundColor="#40000000" transparent="1" halign="center" text="SCR" />
            <widget name="lab_away" position="330,95" size="180,30" font="Regular;20" foregroundColor="#AAAAAA" backgroundColor="#40000000" transparent="1" halign="left" text="AWAY" />
            <widget name="lab_time" position="510,95" size="105,30" font="Regular;20" foregroundColor="#AAAAAA" backgroundColor="#40000000" transparent="1" halign="right" text="TIME" />
            <eLabel position="5,130" size="610,2" backgroundColor="#555555" />
            
            <widget name="list" position="0,135" size="620,510" scrollbarMode="showOnDemand" transparent="1" />
            
            <eLabel position="0,650" size="620,70" backgroundColor="#181818" zPosition="0" />
            <eLabel position="0,650" size="620,2" backgroundColor="#333333" zPosition="1" />
            
            <eLabel position="10,660" size="15,15" backgroundColor="#FF5555" zPosition="2" />
            <widget name="key_red" position="30,660" size="120,25" font="Regular;22" foregroundColor="#FFFFFF" backgroundColor="#181818" transparent="1" zPosition="2" />
            
            <eLabel position="160,660" size="15,15" backgroundColor="#55FF55" zPosition="2" />
            <widget name="key_green" position="180,660" size="120,25" font="Regular;22" foregroundColor="#FFFFFF" backgroundColor="#181818" transparent="1" zPosition="2" />
            
            <eLabel position="310,660" size="15,15" backgroundColor="#FFFF55" zPosition="2" />
            <widget name="key_yellow" position="330,660" size="120,25" font="Regular;22" foregroundColor="#FFFFFF" backgroundColor="#181818" transparent="1" zPosition="2" />
            
            <eLabel position="10,690" size="15,15" backgroundColor="#5555FF" zPosition="2" />
            <widget name="key_blue" position="30,690" size="180,25" font="Regular;22" foregroundColor="#FFFFFF" backgroundColor="#181818" transparent="1" zPosition="2" />
            
            <widget name="key_menu" position="300,690" size="150,25" font="Regular;22" foregroundColor="#FFFFFF" backgroundColor="#181818" transparent="1" zPosition="2" />
            
            <widget name="credit" position="520,690" size="90,25" font="Regular;16" foregroundColor="#555555" backgroundColor="#181818" transparent="1" halign="right" zPosition="2" />
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        global_sports_monitor.set_session(session)
        self.monitor = global_sports_monitor
        self.monitor.register_callback(self.refresh_ui)
        
        self["header"] = Label("SimplySports")
        self["league_title"] = Label("LOADING...")
        self["lab_status"] = Label("ST")
        self["lab_home"] = Label("HOME")
        self["lab_score"] = Label("SCR")
        self["lab_away"] = Label("AWAY")
        self["lab_time"] = Label("TIME")
        self["list"] = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
        self["list"].l.setFont(0, gFont("Regular", 24))
        self["list"].l.setItemHeight(55)
        
        self["key_red"] = Label("League")
        self["key_green"] = Label("Mini")
        self["key_yellow"] = Label("Live Only")
        self["key_blue"] = Label("Discovery: OFF")
        self["key_menu"] = Label("MENU: Update")
        self["credit"] = Label("Reali22 (v" + CURRENT_VERSION + ")")
        
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
        
        self.auto_refresh_timer = eTimer()
        self.auto_refresh_timer.callback.append(self.fetch_data)
        self.onLayoutFinish.append(self.start_ui)
        self.onClose.append(self.cleanup)

    def start_ui(self):
        self["header"].setText("SimplySports")
        self.update_header()
        self.update_filter_button()
        self.fetch_data()
        self.auto_refresh_timer.start(120000)

    def cleanup(self):
        self.monitor.unregister_callback(self.refresh_ui)

    def update_header(self):
        self["header"].setText("SimplySports")
        try:
            curr = DATA_SOURCES[self.monitor.current_league_index][0]
            self["league_title"].setText(curr)
            if self.monitor.active: self["key_blue"].setText("Discovery: ON")
            else: self["key_blue"].setText("Discovery: OFF")
        except: pass

    def update_filter_button(self):
        if self.monitor.live_only_filter:
            self["key_yellow"].setText("Show All")
        else:
            self["key_yellow"].setText("Live Only")

    def fetch_data(self):
        self.monitor.check_goals()

    def toggle_discovery(self):
        is_active = self.monitor.toggle_activity()
        self.update_header()
        if is_active: self.session.open(MessageBox, "Discovery ON", MessageBox.TYPE_INFO, timeout=2)

    def toggle_filter(self):
        self.monitor.toggle_filter()
        self.update_filter_button()
        self.refresh_ui(True)

    def open_league_select(self):
        options = []
        for idx, (name, url) in enumerate(DATA_SOURCES): options.append((name, idx))
        self.session.openWithCallback(self.league_selected, ChoiceBox, title="Select League", list=options)

    def league_selected(self, selection):
        if selection:
            self.monitor.set_league(selection[1])
            self.update_header()
            self.fetch_data()

    def open_mini_bar(self):
        self.session.open(SimpleSportsMiniBar)

    def check_for_updates(self):
        self["league_title"].setText("CHECKING...")
        url = GITHUB_BASE_URL + "version.txt"
        getPage(url.encode('utf-8')).addCallback(self.got_version).addErrback(self.update_fail)

    def got_version(self, data):
        try:
            remote = data.decode('utf-8').strip()
            if remote > CURRENT_VERSION:
                self.session.openWithCallback(self.start_update, MessageBox, "Update to " + remote + "?", MessageBox.TYPE_YESNO)
            else:
                self.session.open(MessageBox, "Up to date.", MessageBox.TYPE_INFO)
                self.update_header()
        except: self.update_fail(None)

    def update_fail(self, error):
        self.session.open(MessageBox, "Update Failed.", MessageBox.TYPE_ERROR)
        self.update_header()

    def start_update(self, answer):
        if answer:
            self["league_title"].setText("UPDATING...")
            url = GITHUB_BASE_URL + "plugin.py"
            target = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/plugin.py")
            downloadPage(url.encode('utf-8'), target).addCallback(self.update_finished).addErrback(self.update_fail)

    def update_finished(self, data):
        self.session.open(MessageBox, "Updated. Restart GUI.", MessageBox.TYPE_INFO)

    def refresh_ui(self, success):
        self.update_header()
        events = self.monitor.cached_events
        
        if not events:
            status_msg = self.monitor.status_message
            dummy_entry = ("INFO", "Status:", status_msg, "", "", "", False)
            self["list"].setList([SportListEntry(dummy_entry)])
            return
        
        list_content = []
        for event in events:
            try:
                status = event.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                clock = status.get('displayClock', '') 
                
                if ":" in clock:
                    clock_parts = clock.split(':')
                    if len(clock_parts) > 0: clock = clock_parts[0] + "'"
                
                utc_date = event.get('date', '')
                local_time = get_local_time_str(utc_date)
                
                venue_data = event.get('competitions', [{}])[0].get('venue', {})
                venue = venue_data.get('fullName', '')
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                
                is_live = False
                display_time = local_time
                
                if len(comps) > 2:
                    left_text = event.get('shortName', 'Race') 
                    right_text = venue 
                    score_text = "" 
                    if state == 'post': score_text = "FIN"
                    elif state == 'in': 
                        score_text = "LIVE"
                        is_live = True
                    goal_side = None
                else:
                    home, away, h_score, a_score = "Home", "Away", "0", "0"
                    for team in comps:
                        name = team.get('team', {}).get('shortDisplayName', 'Tm')
                        sc = team.get('score', '0')
                        if team.get('homeAway') == 'home': home, h_score = name, sc
                        else: away, a_score = name, sc
                    
                    left_text = home
                    right_text = away
                    score_text = h_score + " - " + a_score if state != 'pre' else "vs"
                    
                    if state == 'in': 
                        is_live = True
                        display_time = clock 
                    
                    match_id = home + "_" + away
                    goal_side = None
                    if match_id in self.monitor.goal_flags:
                        goal_side = self.monitor.goal_flags[match_id]['side']

                status_short = "SCH"
                if state == 'in': status_short = "LIVE"
                elif state == 'post': status_short = "FIN"

                if self.monitor.live_only_filter and state != 'in': continue

                entry_data = (status_short, left_text, score_text, right_text, display_time, goal_side, is_live)
                list_content.append(SportListEntry(entry_data))
            except: continue
        
        if not list_content:
             dummy_entry = ("INFO", "Status:", "No Live Games", "", "", "", False)
             self["list"].setList([SportListEntry(dummy_entry)])
        else:
             self["list"].setList(list_content)

def main(session, **kwargs):
    session.open(SimpleSportsScreen)

def Plugins(**kwargs):
    iconPath = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/picon.png")
    return [
        PluginDescriptor(name="SimplySports", description="Live Scores Sidebar", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main, icon=iconPath),
        PluginDescriptor(name="SimplySports Monitor", where=PluginDescriptor.WHERE_SESSIONSTART, fnc=lambda session, **kwargs: global_sports_monitor.set_session(session))
    ]
