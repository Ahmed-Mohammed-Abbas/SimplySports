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
from twisted.internet import reactor, ssl, defer
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
CURRENT_VERSION = "1.1"
GITHUB_BASE_URL = "https://raw.githubusercontent.com/Ahmed-Mohammed-Abbas/SimplySports/main/"
CONFIG_FILE = "/etc/enigma2/simply_sports.json"

# ==============================================================================
# STYLING (PREMIER LEAGUE STYLE)
# ==============================================================================
C_PL_PURPLE = 0x38003C
C_PL_GREEN  = 0x00FF85
C_PL_PINK   = 0xFF004C
C_WHITE     = 0xFFFFFF
C_BLACK     = 0x000000
C_GREY      = 0x9E9E9E
C_GOLD      = 0xFFD700
C_DARK_GREY = 0x202020

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
# LEAGUE DATABASE (FULLY EXPANDED)
# ==============================================================================
DATA_SOURCES = [
    # --- SOCCER: ENGLAND ---
    ("Premier League", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"),
    ("Championship",   "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.2/scoreboard"),
    ("League One",     "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.3/scoreboard"),
    ("League Two",     "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.4/scoreboard"),
    ("FA Cup",         "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.fa/scoreboard"),
    ("Carabao Cup",    "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.league_cup/scoreboard"),
    ("Women's Super Lg","https://site.api.espn.com/apis/site/v2/sports/soccer/eng.w.1/scoreboard"),

    # --- SOCCER: EUROPE MAJOR ---
    ("La Liga (ESP)",  "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard"),
    ("La Liga 2 (ESP)","https://site.api.espn.com/apis/site/v2/sports/soccer/esp.2/scoreboard"),
    ("Copa del Rey",   "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.copa_del_rey/scoreboard"),
    ("Serie A (ITA)",  "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard"),
    ("Serie B (ITA)",  "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.2/scoreboard"),
    ("Coppa Italia",   "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.coppa_italia/scoreboard"),
    ("Bundesliga (GER)","https://site.api.espn.com/apis/site/v2/sports/soccer/ger.1/scoreboard"),
    ("2. Bundesliga",  "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.2/scoreboard"),
    ("DFB Pokal",      "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.dfb_pokal/scoreboard"),
    ("Ligue 1 (FRA)",  "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.1/scoreboard"),
    ("Ligue 2 (FRA)",  "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.2/scoreboard"),
    ("Coupe de France","https://site.api.espn.com/apis/site/v2/sports/soccer/fra.coupe_de_france/scoreboard"),

    # --- SOCCER: EUROPE OTHER ---
    ("Eredivisie (NED)","https://site.api.espn.com/apis/site/v2/sports/soccer/ned.1/scoreboard"),
    ("Primeira (POR)", "https://site.api.espn.com/apis/site/v2/sports/soccer/por.1/scoreboard"),
    ("Süper Lig (TUR)", "https://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard"),
    ("Scottish Prem",  "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.1/scoreboard"),
    ("Belgian Pro Lg", "https://site.api.espn.com/apis/site/v2/sports/soccer/bel.1/scoreboard"),
    ("Austrian Bund",  "https://site.api.espn.com/apis/site/v2/sports/soccer/aut.1/scoreboard"),
    ("Swiss Super Lg", "https://site.api.espn.com/apis/site/v2/sports/soccer/sui.1/scoreboard"),
    ("Danish Super",   "https://site.api.espn.com/apis/site/v2/sports/soccer/den.1/scoreboard"),
    ("Swedish Allsv",  "https://site.api.espn.com/apis/site/v2/sports/soccer/swe.1/scoreboard"),
    ("Eliteserien (NOR)","https://site.api.espn.com/apis/site/v2/sports/soccer/nor.1/scoreboard"),

    # --- SOCCER: UEFA & INTL ---
    ("Champions Lg",   "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard"),
    ("Europa League",  "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa/scoreboard"),
    ("Conference Lg",  "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa.conf/scoreboard"),
    ("Nations League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.nations/scoreboard"),
    ("Euro Qualifiers","https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.euroq/scoreboard"),
    ("FIFA Friendlies","https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.friendly/scoreboard"),

    # --- SOCCER: AMERICAS ---
    ("MLS (USA)",      "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"),
    ("Liga MX (MEX)",  "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/scoreboard"),
    ("Brasileirão",    "https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard"),
    ("Arg Primera",    "https://site.api.espn.com/apis/site/v2/sports/soccer/arg.1/scoreboard"),
    ("Copa Libertadores","https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.libertadores/scoreboard"),
    ("Copa Sudamer",   "https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.sudamericana/scoreboard"),

    # --- SOCCER: ASIA/OCEANIA ---
    ("Saudi Pro Lg",   "https://site.api.espn.com/apis/site/v2/sports/soccer/sa.1/scoreboard"),
    ("A-League (AUS)", "https://site.api.espn.com/apis/site/v2/sports/soccer/aus.1/scoreboard"),
    ("Chinese Super Lg","https://site.api.espn.com/apis/site/v2/sports/soccer/chn.1/scoreboard"),
    ("J-League (JPN)", "https://site.api.espn.com/apis/site/v2/sports/soccer/jpn.1/scoreboard"),

    # --- BASKETBALL ---
    ("NBA",             "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"),
    ("WNBA",            "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"),
    ("NCAA Basket (M)","https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"),
    ("NCAA Basket (W)","https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard"),
    ("EuroLeague",      "https://site.api.espn.com/apis/site/v2/sports/basketball/eurl.euroleague/scoreboard"),

    # --- US SPORTS ---
    ("NFL (Football)", "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"),
    ("NCAA Football",  "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"),
    ("UFL (Football)", "https://site.api.espn.com/apis/site/v2/sports/football/ufl/scoreboard"),
    ("NHL (Hockey)",   "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"),
    ("MLB (Baseball)", "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"),
    ("NCAA Baseball",  "https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/scoreboard"),
    ("NCAA Softball",  "https://site.api.espn.com/apis/site/v2/sports/baseball/college-softball/scoreboard"),

    # --- RACING ---
    ("Formula 1",      "https://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard"),
    ("NASCAR Cup",     "https://site.api.espn.com/apis/site/v2/sports/racing/nascar-premier/scoreboard"),
    ("IndyCar",        "https://site.api.espn.com/apis/site/v2/sports/racing/irl/scoreboard"),

    # --- FIGHTING ---
    ("UFC / MMA",      "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"),
    ("Boxing",         "https://site.api.espn.com/apis/site/v2/sports/boxing/scoreboard"),

    # --- GOLF ---
    ("PGA Tour",       "https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard"),
    ("LPGA Tour",      "https://site.api.espn.com/apis/site/v2/sports/golf/lpga/scoreboard"),
    ("Euro Tour",      "https://site.api.espn.com/apis/site/v2/sports/golf/eur/scoreboard"),

    # --- TENNIS ---
    ("ATP Tennis",     "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard"),
    ("WTA Tennis",     "https://site.api.espn.com/apis/site/v2/sports/tennis/wta/scoreboard"),
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
            local_dt = datetime.datetime.fromtimestamp(timestamp)
            now = datetime.datetime.now()
            time_str = "{:02d}:{:02d}".format(local_dt.hour, local_dt.minute)
            if local_dt.date() == now.date(): return str(time_str)
            else: return local_dt.strftime("%a %d/%m") + " " + time_str
    except:
        return "--:--"

def get_league_abbr(full_name):
    # Dictionary for common abbreviations
    abbr_map = {
        "Premier League": "EPL", "Championship": "CHA", "League One": "L1", "League Two": "L2",
        "FA Cup": "FAC", "Carabao Cup": "EFL", "Women's Super Lg": "WSL",
        "La Liga": "ESP", "La Liga 2": "ES2", "Copa del Rey": "CDR",
        "Serie A": "ITA", "Serie B": "IT2", "Coppa Italia": "CIT",
        "Bundesliga": "GER", "2. Bundesliga": "GE2", "DFB Pokal": "DFB",
        "Ligue 1": "FRA", "Ligue 2": "FR2", "Coupe de France": "CDF",
        "Eredivisie": "NED", "Primeira": "POR", "Süper Lig": "TUR", "Scottish Prem": "SCO",
        "Champions Lg": "UCL", "Europa League": "UEL", "Conference Lg": "UECL", "Nations League": "UNL",
        "MLS": "MLS", "Liga MX": "MEX", "Brasileirão": "BRA", "Arg Primera": "ARG",
        "Saudi Pro Lg": "KSA", "A-League": "AUS", "Chinese Super Lg": "CHN",
        "NBA": "NBA", "NFL": "NFL", "NHL": "NHL", "MLB": "MLB", "Formula 1": "F1",
        "PGA Tour": "PGA", "LPGA Tour": "LPGA", "Euro Tour": "EUR",
        "ATP Tennis": "ATP", "WTA Tennis": "WTA", "UFC / MMA": "UFC", "Boxing": "BOX",
        "IndyCar": "IND", "NCAA Football": "NCAAF", "NCAA Basket (M)": "NCAAM"
    }
    # Clean up name from tuple (remove parenthetical info if any)
    name = full_name.split('(')[0].strip()
    return abbr_map.get(name, name[:3].upper())

# ==============================================================================
# LIST RENDERERS
# ==============================================================================
def SportListEntry(entry):
    try:
        # Handle unpacking with or without league_name
        if len(entry) == 8:
             status, left_text, score_text, right_text, time_str, goal_side, is_live, league_name = entry
        else:
             status, left_text, score_text, right_text, time_str, goal_side, is_live = entry
             league_name = ""

        status = str(status); left_text = str(left_text); score_text = str(score_text); right_text = str(right_text); time_str = str(time_str)
        
        # Abbreviate League
        league_short = ""
        if league_name:
            league_short = get_league_abbr(league_name)

        left_col = C_WHITE
        right_col = C_WHITE
        
        if goal_side == 'home': 
            left_text = "⚽ " + left_text
            left_col = C_PL_GREEN
        elif goal_side == 'away': 
            right_text = right_text + " ⚽"
            right_col = C_PL_GREEN
        
        status_col = C_WHITE
        status_bg = C_GREY
        if status == "LIVE": 
            status_col = C_WHITE
            status_bg = C_PL_PINK
        elif status == "FIN": 
            status_col = C_BLACK
            status_bg = C_PL_GREEN
        elif status == "INFO": 
            status_col = C_WHITE
            status_bg = C_PL_PURPLE
        
        time_col = C_GREY
        if is_live: 
            time_col = C_PL_GREEN
        elif "/" in time_str: 
            time_col = C_WHITE
        
        score_bg = C_WHITE if (status == "LIVE" or status == "FIN") else None
        score_fg = C_PL_PURPLE if (status == "LIVE" or status == "FIN") else C_WHITE

        res = [entry]
        # 1. Status Badge (Left)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 12, 70, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, status, status_col, status_col, status_bg, status_bg, 0, 5))
        
        # 2. League Abbreviation (New Column beside status)
        if league_short:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 85, 12, 75, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, league_short, C_GOLD))
            
        # 3. Home Team (Shifted Right to fit league column)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 170, 5, 340, 55, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, left_text, left_col))
        
        # 4. Score Box
        if score_bg:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 520, 12, 110, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, score_fg, score_fg, score_bg, score_bg, 0, 0))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 520, 12, 110, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, score_fg))
            
        # 5. Away Team
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 640, 5, 340, 55, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, right_col))
        
        # 6. Time
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 990, 5, 200, 55, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, time_str, time_col))
        
        # Separator
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 63, 1180, 1, 0, RT_HALIGN_CENTER, "", C_DARK_GREY, C_DARK_GREY, C_DARK_GREY, C_DARK_GREY))

        return res
    except: 
        return []

def SelectionListEntry(name, is_selected):
    check_mark = "✓" if is_selected else "○"
    col_sel = C_PL_GREEN if is_selected else C_GREY
    text_col = C_WHITE if is_selected else C_GREY
    
    res = [(name, is_selected)]
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 5, 40, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, check_mark, col_sel))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 70, 5, 700, 40, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, name, text_col))
    return res

# ==============================================================================
# BACKGROUND SERVICE
# ==============================================================================
class SportsMonitor:
    def __init__(self):
        self.active = False
        self.current_league_index = 0
        self.custom_league_indices = []
        self.is_custom_mode = False
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
                    self.custom_league_indices = data.get("custom_indices", [])
                    self.is_custom_mode = bool(data.get("is_custom_mode", False))
                    if self.active: self.timer.start(60000, False)
            except: pass

    def save_config(self):
        data = {
            "league_index": self.current_league_index,
            "filter": self.live_only_filter,
            "active": self.active,
            "custom_indices": self.custom_league_indices,
            "is_custom_mode": self.is_custom_mode
        }
        try:
            with open(CONFIG_FILE, "w") as f: json.dump(data, f)
        except: pass

    def set_session(self, session): self.session = session
    def register_callback(self, func):
        if func not in self.callbacks: self.callbacks.append(func)
    def unregister_callback(self, func):
        if func in self.callbacks: self.callbacks.remove(func)

    def toggle_activity(self):
        self.active = not self.active
        if self.active:
            self.timer.start(60000, False)
            self.check_goals()
        else: self.timer.stop()
        self.save_config()
        return self.active

    def toggle_filter(self):
        self.live_only_filter = not self.live_only_filter
        self.save_config()
        return self.live_only_filter

    def set_league(self, index):
        self.is_custom_mode = False
        if index >= 0 and index < len(DATA_SOURCES):
            self.current_league_index = index
            self.last_scores = {}
            self.save_config()
            self.check_goals()

    def set_custom_leagues(self, indices):
        self.custom_league_indices = indices
        self.is_custom_mode = True
        self.last_scores = {}
        self.save_config()
        self.check_goals()

    def check_goals(self):
        self.status_message = "Loading Data..."
        for cb in self.callbacks: cb(False)
        agent = Agent(reactor)

        if not self.is_custom_mode:
            try:
                name, url = DATA_SOURCES[self.current_league_index]
                d = agent.request(b'GET', url.encode('utf-8'))
                d.addCallback(readBody)
                d.addCallback(self.parse_single_json)
                d.addErrback(self.handle_error)
            except: pass
        else:
            if not self.custom_league_indices:
                self.status_message = "No Leagues Selected"
                self.cached_events = []
                for cb in self.callbacks: cb(True)
                return

            deferreds = []
            for idx in self.custom_league_indices:
                if idx < len(DATA_SOURCES):
                    name, url = DATA_SOURCES[idx]
                    d = agent.request(b'GET', url.encode('utf-8'))
                    d.addCallback(readBody)
                    d.addErrback(lambda f: b"{}") 
                    deferreds.append(d)
            
            dlist = defer.gatherResults(deferreds, consumeErrors=True)
            dlist.addCallback(self.parse_multi_json)
            dlist.addErrback(self.handle_error)

    def handle_error(self, failure):
        self.status_message = "API Connection Error"
        self.cached_events = []
        for cb in self.callbacks: cb(True)

    def parse_single_json(self, body): self.process_events_data([body])
    def parse_multi_json(self, bodies_list): self.process_events_data(bodies_list)

    def process_events_data(self, bodies_list):
        all_events = []
        try:
            for body in bodies_list:
                try:
                    json_str = body.decode('utf-8', errors='ignore')
                    data = json.loads(json_str)
                    
                    league_obj = data.get('leagues', [{}])[0]
                    league_name = league_obj.get('name') or league_obj.get('shortName') or ""
                    
                    events = data.get('events', [])
                    for ev in events:
                        ev['league_name'] = league_name
                        
                    all_events.extend(events)
                except: pass
            
            all_events.sort(key=lambda x: x.get('date', ''))
            self.cached_events = all_events

            if len(all_events) == 0: self.status_message = "No Matches Scheduled"
            else: self.status_message = "Data Updated"

            now = time.time()
            keys_to_del = []
            for mid, info in self.goal_flags.items():
                if now - info['time'] > 60: keys_to_del.append(mid)
            for k in keys_to_del: del self.goal_flags[k]

            for event in all_events:
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
                                if h_score > prev_h: self.goal_flags[match_id] = {'side': 'home', 'time': time.time()}
                                elif a_score > prev_a: self.goal_flags[match_id] = {'side': 'away', 'time': time.time()}
                                if self.active and self.session: self.session.open(GoalToast, "GOAL! {} {} - {} {}".format(home, h_score, a_score, away))
                            except: pass
                    self.last_scores[match_id] = score_str

            for cb in self.callbacks: cb(True)
        except:
            self.status_message = "JSON Parse Error"
            for cb in self.callbacks: cb(True)

if global_sports_monitor is None:
    global_sports_monitor = SportsMonitor()

# ==============================================================================
# UI SCREENS
# ==============================================================================
class GoalToast(Screen):
    skin = """<screen position="center,50" size="900,140" title="Goal" flags="wfNoBorder" backgroundColor="#00000000">
            <eLabel position="0,0" size="900,140" backgroundColor="#00FF85" zPosition="0" />
            <eLabel position="0,0" size="900,5" backgroundColor="#38003C" zPosition="1" />
            <eLabel position="0,135" size="900,5" backgroundColor="#38003C" zPosition="1" />
            <widget name="title" position="20,20" size="860,45" font="Regular;38" foregroundColor="#38003C" backgroundColor="#00FF85" transparent="1" halign="center" zPosition="2" />
            <widget name="message" position="20,75" size="860,50" font="Regular;34" foregroundColor="#000000" backgroundColor="#00FF85" transparent="1" halign="center" zPosition="2" />
        </screen>"""
    def __init__(self, session, match_text):
        Screen.__init__(self, session)
        self["title"] = Label("⚽ GOAL! ⚽")
        self["message"] = Label(match_text)
        self.timer = eTimer()
        self.timer.callback.append(self.close)
        self.timer.start(6000, True)

class SimpleSportsMiniBar(Screen):
    skin = """<screen position="center,980" size="1850,80" title="Sports Ticker" backgroundColor="#00000000" flags="wfNoBorder">
            <eLabel position="0,0" size="1850,80" backgroundColor="#38003C" zPosition="-1" />
            <eLabel position="0,0" size="1850,4" backgroundColor="#00FF85" zPosition="1" />
            <widget name="match_info" position="20,10" size="1520,60" font="Regular;30" foregroundColor="#FFFFFF" backgroundColor="#38003C" transparent="1" valign="center" halign="left" />
            <widget name="filter_status" position="1550,10" size="280,60" font="Regular;26" foregroundColor="#FF004C" backgroundColor="#38003C" transparent="1" valign="center" halign="right" />
        </screen>"""
    def __init__(self, session):
        Screen.__init__(self, session)
        self.matches = []
        self.current_match_idx = 0
        self["match_info"] = Label("Loading...")
        self["filter_status"] = Label("")
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {"cancel": self.close, "green": self.close, "yellow": self.toggle_filter_mini}, -1)
        self.ticker_timer = eTimer()
        self.ticker_timer.callback.append(self.show_next_match)
        self.refresh_timer = eTimer()
        self.refresh_timer.callback.append(self.load_data)
        self.onLayoutFinish.append(self.start_all_timers)

    def start_all_timers(self):
        self.update_filter_label()
        self.load_data()
        self.refresh_timer.start(60000)

    def toggle_filter_mini(self): 
        global_sports_monitor.toggle_filter()
        self.update_filter_label()
        self.load_data()
        
    def update_filter_label(self): 
        if global_sports_monitor.live_only_filter:
            self["filter_status"].setText("🔴 LIVE ONLY")
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
            local_time = get_local_time_str(event.get('date', ''))
            league_name = event.get('league_name', '')
            
            if global_sports_monitor.live_only_filter and state != 'in': 
                continue
                
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            if len(comps) > 2:
                race = event.get('shortName', 'Race')
                venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                txt = "{} :: 🏁 {} @ {}".format(league_name, race, venue)
            else:
                home, away, h_score, a_score = "Home", "Away", "0", "0"
                for team in comps:
                    name = team.get('team', {}).get('shortDisplayName', 'Tm')
                    sc = team.get('score', '0')
                    if team.get('homeAway') == 'home': 
                        home, h_score = name, sc
                    else: 
                        away, a_score = name, sc
                        
                match_id = home + "_" + away
                goal_flag = " ⚽" if match_id in global_sports_monitor.goal_flags else ""
                
                if state == 'in': 
                    txt = "{} :: 🔴 {}'  {} {} - {} {} {}".format(league_name, clock, home, h_score, a_score, away, goal_flag)
                elif state == 'post': 
                    txt = "{} :: FT  {} {} - {} {}".format(league_name, home, h_score, a_score, away)
                else: 
                    txt = "{} :: ⏰ {}  {} vs {}".format(league_name, local_time, home, away)
                    
            self.matches.append(txt)
            
        if self.matches:
            if not self.ticker_timer.isActive(): 
                self.show_next_match()
                self.ticker_timer.start(4000)
        else: 
            msg = "No live games." if global_sports_monitor.live_only_filter else global_sports_monitor.status_message
            self["match_info"].setText(msg)

    def show_next_match(self):
        if not self.matches: 
            return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matches)
        self["match_info"].setText(self.matches[self.current_match_idx])

# ==============================================================================
# CUSTOM LEAGUE SELECTOR
# ==============================================================================
class LeagueSelector(Screen):
    skin = """
        <screen position="center,center" size="900,700" title="Select Leagues" backgroundColor="#38003C" flags="wfNoBorder">
            <eLabel position="0,0" size="900,700" backgroundColor="#38003C" zPosition="-1" />
            <eLabel position="0,0" size="900,4" backgroundColor="#00FF85" zPosition="1" />
            <eLabel position="0,696" size="900,4" backgroundColor="#00FF85" zPosition="1" />
            <eLabel position="0,0" size="4,700" backgroundColor="#00FF85" zPosition="1" />
            <eLabel position="896,0" size="4,700" backgroundColor="#00FF85" zPosition="1" />
            
            <widget name="header" position="30,25" size="840,50" font="Regular;38" foregroundColor="#00FF85" backgroundColor="#38003C" transparent="1" halign="center" />
            <eLabel position="30,80" size="840,2" backgroundColor="#505050" />
            
            <widget name="list" position="30,95" size="840,510" scrollbarMode="showOnDemand" transparent="1" />
            
            <eLabel position="30,615" size="840,2" backgroundColor="#505050" />
            
            <widget name="key_red" position="30,635" size="220,50" font="Regular;28" foregroundColor="#FFFFFF" backgroundColor="#F44336" transparent="0" zPosition="1" halign="center" valign="center" />
            <widget name="key_green" position="650,635" size="220,50" font="Regular;28" foregroundColor="#000000" backgroundColor="#00FF85" transparent="0" zPosition="1" halign="center" valign="center" />
            <widget name="info" position="270,635" size="360,50" font="Regular;24" foregroundColor="#9E9E9E" backgroundColor="#38003C" transparent="1" halign="center" valign="center" />
        </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self["header"] = Label("Select Custom Leagues")
        self["list"] = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
        self["list"].l.setFont(0, gFont("Regular", 28))
        self["list"].l.setItemHeight(50)
        
        self["key_red"] = Label("Cancel")
        self["key_green"] = Label("Save")
        self["info"] = Label("Press OK to Toggle")
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
            "cancel": self.close,
            "red": self.close,
            "green": self.save,
            "ok": self.toggle,
            "up": self["list"].up,
            "down": self["list"].down,
        }, -1)
        
        self.selections = []
        self.onLayoutFinish.append(self.load_list)

    def load_list(self):
        current_indices = global_sports_monitor.custom_league_indices
        self.selections = []
        for i in range(len(DATA_SOURCES)):
            self.selections.append(i in current_indices)
        self.refresh_list()

    def refresh_list(self):
        list_content = []
        for idx, (name, url) in enumerate(DATA_SOURCES):
            is_selected = self.selections[idx]
            list_content.append(SelectionListEntry(name, is_selected))
        self["list"].setList(list_content)

    def toggle(self):
        idx = self["list"].getSelectedIndex()
        if idx is not None and 0 <= idx < len(self.selections):
            self.selections[idx] = not self.selections[idx]
            self.refresh_list()

    def save(self):
        new_indices = []
        for idx, is_selected in enumerate(self.selections):
            if is_selected: 
                new_indices.append(idx)
        
        if not new_indices:
            self.session.open(MessageBox, "Please select at least one league.", MessageBox.TYPE_ERROR)
        else:
            global_sports_monitor.set_custom_leagues(new_indices)
            self.close(True)

# ==============================================================================
# MAIN GUI - PREMIER LEAGUE STYLE
# ==============================================================================
class SimpleSportsScreen(Screen):
    skin = """
        <screen position="center,center" size="1280,860" title="SimplySports" flags="wfNoBorder" backgroundColor="#00000000">
            <eLabel position="0,0" size="1280,860" backgroundColor="#38003C" zPosition="-1" />
            <eLabel position="0,0" size="1280,60" backgroundColor="#28002C" zPosition="0" />
            <widget name="top_title" position="0,10" size="1280,45" font="Regular;34" foregroundColor="#00FF85" backgroundColor="#28002C" transparent="1" halign="center" valign="center" zPosition="1" />
            
            <eLabel position="0,60" size="1280,50" backgroundColor="#38003C" zPosition="0" />
            <widget name="league_title" position="40,65" size="850,35" font="Regular;28" foregroundColor="#FFFFFF" backgroundColor="#38003C" transparent="1" halign="left" zPosition="1" />
            <widget name="credit" position="1020,65" size="240,30" font="Regular;22" foregroundColor="#888888" backgroundColor="#38003C" transparent="1" halign="right" zPosition="2" />
            
            <eLabel position="0,110" size="1280,45" backgroundColor="#28002C" zPosition="0" />
            <widget name="head_status" position="10,115" size="70,35" font="Regular;22" foregroundColor="#00FF85" backgroundColor="#28002C" transparent="1" halign="center" valign="center" zPosition="1" />
            <widget name="head_league" position="85,115" size="75,35" font="Regular;22" foregroundColor="#00FF85" backgroundColor="#28002C" transparent="1" halign="center" valign="center" zPosition="1" />
            <widget name="head_home" position="170,115" size="340,35" font="Regular;22" foregroundColor="#00FF85" backgroundColor="#28002C" transparent="1" halign="right" valign="center" zPosition="1" />
            <widget name="head_score" position="520,115" size="110,35" font="Regular;22" foregroundColor="#00FF85" backgroundColor="#28002C" transparent="1" halign="center" valign="center" zPosition="1" />
            <widget name="head_away" position="640,115" size="340,35" font="Regular;22" foregroundColor="#00FF85" backgroundColor="#28002C" transparent="1" halign="left" valign="center" zPosition="1" />
            <widget name="head_time" position="990,115" size="200,35" font="Regular;22" foregroundColor="#00FF85" backgroundColor="#28002C" transparent="1" halign="right" valign="center" zPosition="1" />
            
            <eLabel position="0,158" size="1280,4" backgroundColor="#00FF85" zPosition="1" />
            <widget name="list" position="20,170" size="1240,590" scrollbarMode="showOnDemand" transparent="1" zPosition="1" />
            <eLabel position="0,770" size="1280,90" backgroundColor="#28002C" zPosition="0" />
            <eLabel position="0,770" size="1280,2" backgroundColor="#505050" zPosition="1" />
            
            <widget name="key_red" position="40,785" size="280,60" font="Regular;26" foregroundColor="#FFFFFF" backgroundColor="#F44336" transparent="0" zPosition="2" halign="center" valign="center" />
            <widget name="key_green" position="340,785" size="280,60" font="Regular;26" foregroundColor="#000000" backgroundColor="#00FF85" transparent="0" zPosition="2" halign="center" valign="center" />
            <widget name="key_yellow" position="640,785" size="280,60" font="Regular;26" foregroundColor="#FFFFFF" backgroundColor="#FFA000" transparent="0" zPosition="2" halign="center" valign="center" />
            <widget name="key_blue" position="940,785" size="300,60" font="Regular;26" foregroundColor="#FFFFFF" backgroundColor="#42A5F5" transparent="0" zPosition="2" halign="center" valign="center" />
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        global_sports_monitor.set_session(session)
        self.monitor = global_sports_monitor
        self.monitor.register_callback(self.refresh_ui)
        
        self["top_title"] = Label("SimplySports Score Center")
        self["league_title"] = Label("LOADING...")
        self["credit"] = Label("Reali22 (v" + CURRENT_VERSION + ")")
        
        self["head_status"] = Label("STAT")
        self["head_league"] = Label("LGE")
        self["head_home"] = Label("HOME")
        self["head_score"] = Label("SCORE")
        self["head_away"] = Label("AWAY")
        self["head_time"] = Label("DATE/TIME")
        
        self["list"] = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
        self["list"].l.setFont(0, gFont("Regular", 28))
        self["list"].l.setItemHeight(65)
        
        self["key_red"] = Label("League Menu")
        self["key_green"] = Label("Mini Bar")
        self["key_yellow"] = Label("Live Only")
        self["key_blue"] = Label("Discovery: OFF")
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "MenuActions"], {
            "cancel": self.close,
            "red": self.open_league_menu,
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
        self.update_header()
        self.update_filter_button()
        self.fetch_data()
        self.auto_refresh_timer.start(120000)
        
    def cleanup(self): 
        self.monitor.unregister_callback(self.refresh_ui)

    def update_header(self):
        if self.monitor.is_custom_mode:
             self["league_title"].setText("🏆 Custom League View")
        else:
            try: 
                self["league_title"].setText(DATA_SOURCES[self.monitor.current_league_index][0])
            except: 
                pass
                
        if self.monitor.active:
            self["key_blue"].setText("Discovery: ON 🔔")
        else:
            self["key_blue"].setText("Discovery: OFF")

    def update_filter_button(self): 
        if self.monitor.live_only_filter:
            self["key_yellow"].setText("Show All")
        else:
            self["key_yellow"].setText("Live Only 🔴")
            
    def fetch_data(self): 
        self.monitor.check_goals()

    def toggle_discovery(self):
        is_active = self.monitor.toggle_activity()
        self.update_header()
        if is_active: 
            self.session.open(MessageBox, "Goal Discovery is now ON\nYou'll receive alerts for new goals!", MessageBox.TYPE_INFO, timeout=3)

    def toggle_filter(self): 
        self.monitor.toggle_filter()
        self.update_filter_button()
        self.refresh_ui(True)

    def open_league_menu(self):
        options = [
            ("Select Single League", "single"),
            ("Configure Custom Leagues", "custom_config"),
        ]
        if self.monitor.custom_league_indices:
             options.append(("View Custom Leagues", "view_custom"))
        self.session.openWithCallback(self.league_menu_callback, ChoiceBox, title="League Options", list=options)

    def league_menu_callback(self, selection):
        if selection:
            if selection[1] == "single": 
                self.open_single_league_select()
            elif selection[1] == "custom_config": 
                self.session.openWithCallback(self.on_selector_closed, LeagueSelector)
            elif selection[1] == "view_custom": 
                self.monitor.set_custom_leagues(self.monitor.custom_league_indices)
                self.update_header()
                self.fetch_data()
    
    def on_selector_closed(self, result=None):
        if result:
            self.update_header()
            self.fetch_data()

    def open_single_league_select(self):
        options = []
        for idx, (name, url) in enumerate(DATA_SOURCES): 
            options.append((name, idx))
        self.session.openWithCallback(self.single_league_selected, ChoiceBox, title="Select Single League", list=options)

    def single_league_selected(self, selection):
        if selection:
            self.monitor.set_league(selection[1])
            self.update_header()
            self.fetch_data()

    def open_mini_bar(self): 
        self.session.open(SimpleSportsMiniBar)

    def check_for_updates(self): 
        self["league_title"].setText("CHECKING FOR UPDATES...")
        url = GITHUB_BASE_URL + "version.txt"
        getPage(url.encode('utf-8')).addCallback(self.got_version).addErrback(self.update_fail)
        
    def got_version(self, data):
        try:
            remote = data.decode('utf-8').strip()
            if remote > CURRENT_VERSION: 
                self.session.openWithCallback(self.start_update, MessageBox, "Update available: " + remote + "\n\nDo you want to update now?", MessageBox.TYPE_YESNO)
            else: 
                self.session.open(MessageBox, "You're running the latest version!", MessageBox.TYPE_INFO, timeout=3)
                self.update_header()
        except: 
            self.update_fail(None)
            
    def update_fail(self, error): 
        self.session.open(MessageBox, "Update check failed.\nPlease try again later.", MessageBox.TYPE_ERROR, timeout=3)
        self.update_header()
        
    def start_update(self, answer):
        if answer: 
            self["league_title"].setText("DOWNLOADING UPDATE...")
            url = GITHUB_BASE_URL + "plugin.py"
            target = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/plugin.py")
            downloadPage(url.encode('utf-8'), target).addCallback(self.update_finished).addErrback(self.update_fail)
            
    def update_finished(self, data): 
        self.session.open(MessageBox, "Update completed successfully!\n\nPlease restart the GUI to apply changes.", MessageBox.TYPE_INFO)

    def refresh_ui(self, success):
        self.update_header()
        events = self.monitor.cached_events
        
        if not events:
            dummy_entry = ("INFO", "Status:", self.monitor.status_message, "", "", "", False, "")
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
                    clock = clock_parts[0] + "'" if len(clock_parts) > 0 else clock
                    
                local_time = get_local_time_str(event.get('date', ''))
                venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                
                # Use league name in both single and custom modes if available
                league_prefix = event.get('league_name', '')
                
                is_live = False
                display_time = local_time
                
                if len(comps) > 2:
                    left_text = event.get('shortName', 'Race')
                    right_text = venue
                    score_text = ""
                    if state == 'post': 
                        score_text = "FIN"
                    elif state == 'in': 
                        score_text = "LIVE"
                        is_live = True
                    goal_side = None
                else:
                    home, away, h_score, a_score = "Home", "Away", "0", "0"
                    for team in comps:
                        name = team.get('team', {}).get('shortDisplayName', 'Tm')
                        sc = team.get('score', '0')
                        if team.get('homeAway') == 'home': 
                            home, h_score = name, sc
                        else: 
                            away, a_score = name, sc
                            
                    left_text = home
                    right_text = away
                    score_text = h_score + " - " + a_score if state != 'pre' else "vs"
                    if state == 'in': 
                        is_live = True
                        display_time = clock
                        
                    match_id = home + "_" + away
                    goal_side = self.monitor.goal_flags[match_id]['side'] if match_id in self.monitor.goal_flags else None

                status_short = "SCH"
                if state == 'in': 
                    status_short = "LIVE"
                elif state == 'post': 
                    status_short = "FIN"

                if self.monitor.live_only_filter and state != 'in': 
                    continue
                
                list_content.append(SportListEntry((status_short, left_text, score_text, right_text, display_time, goal_side, is_live, league_prefix)))
            except: 
                continue
        
        if not list_content: 
            self["list"].setList([SportListEntry(("INFO", "Status:", "No Live Games", "", "", "", False, ""))])
        else: 
            self["list"].setList(list_content)

def main(session, **kwargs): 
    session.open(SimpleSportsScreen)
    
def Plugins(**kwargs):
    iconPath = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/picon.png")
    return [
        PluginDescriptor(name="SimplySports", description="Live Sports Scores & Alerts", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main, icon=iconPath),
        PluginDescriptor(name="SimplySports Monitor", where=PluginDescriptor.WHERE_SESSIONSTART, fnc=lambda session, **kwargs: global_sports_monitor.set_session(session))
    ]
