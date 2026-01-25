# -*- coding: utf-8 -*-
import shutil
import os
import threading
import time
import ssl
import hashlib  # NEW: For logo caching
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
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap
from twisted.internet import reactor, ssl, defer
from twisted.web.client import Agent, readBody, getPage, downloadPage
from twisted.web.http_headers import Headers
from enigma import eTimer, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, getDesktop, eConsoleAppContainer, gRGB
from Components.Sources.StaticText import StaticText
import json
import datetime
import calendar



try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request

# ==============================================================================
# CONFIGURATION
# ==============================================================================
CURRENT_VERSION = "2.7"       #visual enhancements
GITHUB_BASE_URL = "https://raw.githubusercontent.com/Ahmed-Mohammed-Abbas/SimplySports/main/"
CONFIG_FILE = "/etc/enigma2/simply_sports.json"
LOG_FILE = "/tmp/simplysports.log"  # NEW: For error logging
LOGO_CACHE_DIR = "/tmp/simplysports_logos"  # NEW: For logo caching

# ==============================================================================
# STYLING
# ==============================================================================
C_UCL_BLUE_DARK  = 0x0e1e5b  # Deep Blue background
C_UCL_BLUE_LIGHT = 0x182c82  # Lighter Blue for list rows
C_UCL_CYAN       = 0x00ffff  # Cyan accents/text
C_UCL_WHITE      = 0xffffff
C_PL_PURPLE = 0x38003C
C_PL_GREEN  = 0x00FF85
C_PL_PINK   = 0xFF004C
C_WHITE     = 0xFFFFFF
C_BLACK     = 0x000000
C_GREY      = 0x9E9E9E
C_GOLD      = 0xFFD700
C_DARK_GREY = 0x202020
C_BLUE_HEADER = 0x004080

# ==============================================================================
# LOGGING UTILITY (NEW ENHANCEMENT)
# ==============================================================================
def log_message(message, level="INFO"):
    """Write log messages to file with timestamp"""
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a") as f:
            f.write("[{}] {}: {}\n".format(timestamp, level, message))
    except:
        pass

# ==============================================================================
# LOGO CACHE MANAGER (NEW ENHANCEMENT)
# ==============================================================================
class LogoCacheManager:
    """Manages local caching of team logos with auto-cleanup and validation"""
    def __init__(self):
        self.cache_dir = LOGO_CACHE_DIR
        self._ensure_cache_dir()
        self._prune_cache()  # Clean old logos on startup

    def _ensure_cache_dir(self):
        try:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)
                log_message("Logo cache directory created", "INFO")
        except Exception as e:
            log_message("Failed to create cache dir: {}".format(str(e)), "ERROR")

    def _prune_cache(self, days=7):
        """Delete files older than 'days'"""
        try:
            now = time.time()
            cutoff = now - (days * 86400)
            if not os.path.exists(self.cache_dir): return
            
            for filename in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, filename)
                if os.path.isfile(file_path):
                    if os.path.getmtime(file_path) < cutoff:
                        os.remove(file_path)
            log_message("Cache pruning completed", "INFO")
        except Exception as e:
            log_message("Cache pruning error: {}".format(str(e)), "WARNING")

    def get_cached_path(self, url):
        """Returns path if exists and valid, else None"""
        if not url: return None
        try:
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            cached_path = os.path.join(self.cache_dir, "{}.png".format(url_hash))
            # Verify file exists and has content (size > 0)
            if os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
                return cached_path
        except: pass
        return None

    def get_cache_filename(self, url):
        """Returns the expected filename for a URL"""
        if not url: return None
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, "{}.png".format(url_hash))

# ==============================================================================
# GLOBAL SERVICE INSTANCE
# ==============================================================================
global_sports_monitor = None

# ==============================================================================
# LEAGUE DATABASE
# ==============================================================================
DATA_SOURCES = [
    # --- INTERNATIONAL & QUALIFIERS ---
    ("World Cup Qualifying - UEFA", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.worldq.uefa/scoreboard"),
    ("World Cup Qualifying - CAF", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.worldq.caf/scoreboard"),
    ("World Cup Qualifying - AFC", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.worldq.afc/scoreboard"),
    ("World Cup Qualifying - CONCACAF", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.worldq.concacaf/scoreboard"),
    ("World Cup Qualifying - CONMEBOL", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.worldq.conmebol/scoreboard"),
    ("World Cup Qualifying - OFC", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.worldq.ofc/scoreboard"),
    ("International Friendly", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.friendly/scoreboard"),
    ("Women's Int. Friendly", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.friendly.w/scoreboard"),
    ("UEFA Euro Qualifiers", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.euroq/scoreboard"),
    ("UEFA Nations League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.nations/scoreboard"),
    ("UEFA U21 Qualifiers", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.euro_u21_qual/scoreboard"),
    
    # --- EUROPE: UEFA CLUB ---
    ("UEFA Champions League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard"),
    ("UEFA Europa League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa/scoreboard"),
    ("UEFA Conference League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa.conf/scoreboard"),
    ("UEFA Women's Champions League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.wchampions/scoreboard"),
    ("UEFA Super Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.super_cup/scoreboard"),

    # --- ENGLAND ---
    ("Premier League", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"),
    ("Championship", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.2/scoreboard"),
    ("League One", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.3/scoreboard"),
    ("League Two", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.4/scoreboard"),
    ("FA Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.fa/scoreboard"),
    ("Carabao Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.league_cup/scoreboard"),
    ("Community Shield", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.charity/scoreboard"),
    ("Women's Super League", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.w.1/scoreboard"),
    ("Women's FA Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.w.fa/scoreboard"),
    ("EFL Trophy", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.trophy/scoreboard"),
    ("National League", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.5/scoreboard"),

    # --- SPAIN ---
    ("La Liga", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard"),
    ("La Liga 2", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.2/scoreboard"),
    ("Copa del Rey", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.copa_del_rey/scoreboard"),
    ("Spanish Supercopa", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.super_cup/scoreboard"),
    ("Liga F (Women)", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.w.1/scoreboard"),
    ("Copa de la Reina", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.copa_de_la_reina/scoreboard"),

    # --- ITALY ---
    ("Serie A", "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard"),
    ("Serie B", "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.2/scoreboard"),
    ("Coppa Italia", "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.coppa_italia/scoreboard"),
    ("Italian Supercoppa", "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.super_cup/scoreboard"),

    # --- GERMANY ---
    ("Bundesliga", "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.1/scoreboard"),
    ("2. Bundesliga", "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.2/scoreboard"),
    ("3. Liga", "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.3/scoreboard"),
    ("DFB Pokal", "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.dfb_pokal/scoreboard"),
    ("German Supercup", "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.super_cup/scoreboard"),

    # --- FRANCE ---
    ("Ligue 1", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.1/scoreboard"),
    ("Ligue 2", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.2/scoreboard"),
    ("Coupe de France", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.coupe_de_france/scoreboard"),
    ("Coupe de la Ligue", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.coupe_de_la_ligue/scoreboard"),
    ("Trophee des Champions", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.trophee_des_champions/scoreboard"),
    ("Premiere Ligue (Women)", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.w.1/scoreboard"),

    # --- NETHERLANDS ---
    ("Eredivisie", "https://site.api.espn.com/apis/site/v2/sports/soccer/ned.1/scoreboard"),
    ("Eerste Divisie", "https://site.api.espn.com/apis/site/v2/sports/soccer/ned.2/scoreboard"),
    ("KNVB Beker", "https://site.api.espn.com/apis/site/v2/sports/soccer/ned.cup/scoreboard"),
    ("Johan Cruyff Shield", "https://site.api.espn.com/apis/site/v2/sports/soccer/ned.supercup/scoreboard"),

    # --- PORTUGAL ---
    ("Primeira Liga", "https://site.api.espn.com/apis/site/v2/sports/soccer/por.1/scoreboard"),
    ("Liga 2 Portugal", "https://site.api.espn.com/apis/site/v2/sports/soccer/por.2/scoreboard"),
    ("Taca de Portugal", "https://site.api.espn.com/apis/site/v2/sports/soccer/por.taca.portugal/scoreboard"),
    ("Taca de Liga", "https://site.api.espn.com/apis/site/v2/sports/soccer/por.liga_cup/scoreboard"),

    # --- SCOTLAND ---
    ("Scottish Premiership", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.1/scoreboard"),
    ("Scottish Championship", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.2/scoreboard"),
    ("Scottish League One", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.3/scoreboard"),
    ("Scottish League Two", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.4/scoreboard"),
    ("Scottish Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.tennents/scoreboard"),
    ("Scottish League Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.cis/scoreboard"),
    ("Scottish Challenge Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.challenge/scoreboard"),

    # --- TURKEY ---
    ("Super Lig", "https://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard"),
    ("Turkish Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/tur.cup/scoreboard"),

    # --- BELGIUM ---
    ("Belgian Pro League", "https://site.api.espn.com/apis/site/v2/sports/soccer/bel.1/scoreboard"),
    ("Belgian Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/bel.cup/scoreboard"),

    # --- OTHER EUROPE ---
    ("Austrian Bundesliga", "https://site.api.espn.com/apis/site/v2/sports/soccer/aut.1/scoreboard"),
    ("Swiss Super League", "https://site.api.espn.com/apis/site/v2/sports/soccer/sui.1/scoreboard"),
    ("Danish Superliga", "https://site.api.espn.com/apis/site/v2/sports/soccer/den.1/scoreboard"),
    ("Swedish Allsvenskan", "https://site.api.espn.com/apis/site/v2/sports/soccer/swe.1/scoreboard"),
    ("Norwegian Eliteserien", "https://site.api.espn.com/apis/site/v2/sports/soccer/nor.1/scoreboard"),
    ("Greek Super League", "https://site.api.espn.com/apis/site/v2/sports/soccer/gre.1/scoreboard"),
    ("Czech First League", "https://site.api.espn.com/apis/site/v2/sports/soccer/cze.1/scoreboard"),
    ("Polish Ekstraklasa", "https://site.api.espn.com/apis/site/v2/sports/soccer/pol.1/scoreboard"),
    ("Russian Premier League", "https://site.api.espn.com/apis/site/v2/sports/soccer/rus.1/scoreboard"),
    ("Ukrainian Premier League", "https://site.api.espn.com/apis/site/v2/sports/soccer/ukr.1/scoreboard"),

    # --- USA / NORTH AMERICA ---
    ("MLS", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"),
    ("USL Championship", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.2/scoreboard"),
    ("USL League One", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.usl.1/scoreboard"),
    ("NWSL", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.nwsl/scoreboard"),
    ("NWSL Challenge Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.nwsl.cup/scoreboard"),
    ("U.S. Open Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.open/scoreboard"),
    ("Canadian Premier League", "https://site.api.espn.com/apis/site/v2/sports/soccer/can.1/scoreboard"),
    ("Liga MX", "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/scoreboard"),
    ("Concacaf Champions Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/concacaf.champions/scoreboard"),
    ("Concacaf Gold Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/concacaf.gold/scoreboard"),
    ("Concacaf Nations League", "https://site.api.espn.com/apis/site/v2/sports/soccer/concacaf.nations.league/scoreboard"),
    ("Leagues Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/concacaf.leagues.cup/scoreboard"),
    ("Campeones Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/campeones.cup/scoreboard"),

    # --- SOUTH AMERICA ---
    ("Brasileirao", "https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard"),
    ("Serie B Brazil", "https://site.api.espn.com/apis/site/v2/sports/soccer/bra.2/scoreboard"),
    ("Argentina Primera", "https://site.api.espn.com/apis/site/v2/sports/soccer/arg.1/scoreboard"),
    ("Colombia Primera A", "https://site.api.espn.com/apis/site/v2/sports/soccer/col.1/scoreboard"),
    ("Chilean Primera", "https://site.api.espn.com/apis/site/v2/sports/soccer/chi.1/scoreboard"),
    ("Ecuador Primera A", "https://site.api.espn.com/apis/site/v2/sports/soccer/ecu.1/scoreboard"),
    ("Paraguay Primera", "https://site.api.espn.com/apis/site/v2/sports/soccer/par.1/scoreboard"),
    ("Uruguay Primera", "https://site.api.espn.com/apis/site/v2/sports/soccer/uru.1/scoreboard"),
    ("Venezuela Primera", "https://site.api.espn.com/apis/site/v2/sports/soccer/ven.1/scoreboard"),
    ("Copa Libertadores", "https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.libertadores/scoreboard"),
    ("Copa Sudamericana", "https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.sudamericana/scoreboard"),
    ("Copa America", "https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.america/scoreboard"),

    # --- ASIA / AFRICA / OCEANIA ---
    ("Saudi Pro League", "https://site.api.espn.com/apis/site/v2/sports/soccer/ksa.1/scoreboard"),
    ("Saudi Kings Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/ksa.kings.cup/scoreboard"),
    ("J1 League Japan", "https://site.api.espn.com/apis/site/v2/sports/soccer/jpn.1/scoreboard"),
    ("K League 1 Korea", "https://site.api.espn.com/apis/site/v2/sports/soccer/kor.1/scoreboard"),
    ("Chinese Super League", "https://site.api.espn.com/apis/site/v2/sports/soccer/chn.1/scoreboard"),
    ("Indian Super League", "https://site.api.espn.com/apis/site/v2/sports/soccer/ind.1/scoreboard"),
    ("A-League Australia", "https://site.api.espn.com/apis/site/v2/sports/soccer/aus.1/scoreboard"),
    ("A-League Women", "https://site.api.espn.com/apis/site/v2/sports/soccer/aus.w.1/scoreboard"),
    ("UAE Pro League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uae.1/scoreboard"),
    ("Qatar Stars League", "https://site.api.espn.com/apis/site/v2/sports/soccer/qat.1/scoreboard"),
    ("South African Premier", "https://site.api.espn.com/apis/site/v2/sports/soccer/rsa.1/scoreboard"),
    ("Egyptian Premier", "https://site.api.espn.com/apis/site/v2/sports/soccer/egy.1/scoreboard"),
    ("AFC Champions League Elite", "https://site.api.espn.com/apis/site/v2/sports/soccer/afc.champions/scoreboard"),
    ("AFC Asian Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/afc.asian.cup/scoreboard"),
    ("Africa Cup of Nations", "https://site.api.espn.com/apis/site/v2/sports/soccer/caf.nations/scoreboard"),

    # --- BASKETBALL ---
    ("NBA", "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"),
    ("WNBA", "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"),
    ("NCAA Basket (M)", "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"),
    ("NCAA Basket (W)", "https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard"),
    ("EuroLeague", "https://site.api.espn.com/apis/site/v2/sports/basketball/eurl.euroleague/scoreboard"),

    # --- AMERICAN FOOTBALL ---
    ("NFL", "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"),
    ("NCAA Football", "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"),
    ("UFL", "https://site.api.espn.com/apis/site/v2/sports/football/ufl/scoreboard"),

    # --- BASEBALL / HOCKEY ---
    ("MLB", "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"),
    ("NCAA Baseball", "https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/scoreboard"),
    ("NHL", "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"),

    # --- RACING / FIGHTING / GOLF / TENNIS ---
    ("Formula 1", "https://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard"),
    ("NASCAR Cup", "https://site.api.espn.com/apis/site/v2/sports/racing/nascar-premier/scoreboard"),
    ("IndyCar", "https://site.api.espn.com/apis/site/v2/sports/racing/irl/scoreboard"),
    ("UFC / MMA", "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"),
    ("Boxing", "https://site.api.espn.com/apis/site/v2/sports/boxing/scoreboard"),
    ("PGA Tour", "https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard"),
    ("LPGA Tour", "https://site.api.espn.com/apis/site/v2/sports/golf/lpga/scoreboard"),
    ("Euro Tour", "https://site.api.espn.com/apis/site/v2/sports/golf/eur/scoreboard"),
    ("ATP Tennis", "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard"),
    ("WTA Tennis", "https://site.api.espn.com/apis/site/v2/sports/tennis/wta/scoreboard"),
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
    if not full_name: return ""
    return full_name[:3].upper()


def safe_connect(timer_obj, func):
    """Safely connects a timer function across different Enigma2 versions"""
    if hasattr(timer_obj, 'callback'):
        # Modern Enigma2 (Python 3 / OpenATV 6.4+)
        timer_obj.callback.append(func)
    else:
        # Older Enigma2 (Python 2.7)
        try:
            # Standard Old Method
            timer_obj.timeout.get().append(func)
        except AttributeError:
            # Specific Old Method (Fix for your error)
            timer_obj.timeout.append(func)
            
# ==============================================================================
# LIST RENDERERS (SCORE BOX & COMPACT TIME)
# ==============================================================================
def SportListEntry(entry):
    try:
        if len(entry) >= 10:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int = entry[:12]
        else: return []

        if h_png and (not os.path.exists(h_png) or os.path.getsize(h_png) == 0): h_png = None
        if a_png and (not os.path.exists(a_png) or os.path.getsize(a_png) == 0): a_png = None

        # --- COLORS ---
        c_text = 0xffffff
        c_dim = 0x999999
        c_accent = 0x00FF85 # Green
        c_live = 0xe74c3c   # Red
        c_box = 0x202020    # Dark Grey Background for Score Box
        
        # --- WINNER COLOR LOGIC ---
        c_h_score = c_text
        c_a_score = c_text
        c_h_name = c_text
        c_a_name = c_text

        if h_score_int > a_score_int:
            c_h_score = c_accent
            c_h_name = c_accent 
        elif a_score_int > h_score_int:
            c_a_score = c_accent
            c_a_name = c_accent

        c_status = c_dim
        if status == "LIVE": c_status = c_live
        if status == "FIN": c_status = c_accent

        res = [entry]
        h = 75 

        # 1. STATUS
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 0, 70, h, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, status, c_status, c_status))
        
        # 2. LEAGUE
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 100, 0, 80, h, 1, RT_HALIGN_CENTER|RT_VALIGN_CENTER, league_short, c_dim, c_dim))
        
        # 3. HOME TEAM
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 190, 0, 300, h, 1, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, left_text, c_h_name, c_h_name))

        # 4. LOGOS
        if h_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 505, 10, 55, 55, LoadPixmap(h_png)))
        
        # 5. SCOREBOARD (With Box Background)
        # y=15, h=45 creates a nice centered box effect within the 75px row
        if "-" in score_text:
            parts = score_text.split('-')
            # Home Score Box
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 580, 15, 50, 45, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, parts[0].strip(), c_h_score, c_h_score, c_box, c_box))
            # Dash
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 630, 0, 20, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "-", c_dim, c_dim))
            # Away Score Box
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 650, 15, 50, 45, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, parts[1].strip(), c_a_score, c_a_score, c_box, c_box))
        else:
            # "vs" - No box, just text
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 580, 0, 120, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, c_dim, c_dim))

        # 6. AWAY LOGO
        if a_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 720, 10, 55, 55, LoadPixmap(a_png)))

        # 7. AWAY TEAM
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 790, 0, 300, h, 1, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, c_a_name, c_a_name))
        
        # 8. TIME (Font 3: Smaller Size 20)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1090, 0, 170, h, 3, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, time_str, c_dim, c_dim))

        # Goal Indicators
        if goal_side == 'home':
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 480, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "<", c_accent, c_accent))
        elif goal_side == 'away':
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 780, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, ">", c_accent, c_accent))

        # Divider
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 72, 1240, 2, 0, RT_HALIGN_CENTER, "", 0x303030, 0x303030))

        return res
    except: return []

def UCLListEntry(entry):
    try:
        if len(entry) >= 10:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int = entry[:12]
        else: return []

        if h_png and (not os.path.exists(h_png) or os.path.getsize(h_png) == 0): h_png = None
        if a_png and (not os.path.exists(a_png) or os.path.getsize(a_png) == 0): a_png = None

        c_text = 0xffffff
        c_dim = 0xaaaaaa
        c_accent = 0x00ffff # Cyan
        c_live = 0xff3333   # Red
        c_box = 0x051030    # Dark Navy for UCL Box
        
        c_h_score = c_text
        c_a_score = c_text
        c_h_name = c_text
        c_a_name = c_text

        if h_score_int > a_score_int:
            c_h_score = c_accent
            c_h_name = c_accent 
        elif a_score_int > h_score_int:
            c_a_score = c_accent
            c_a_name = c_accent

        c_status = c_dim
        if status == "LIVE": c_status = c_live
        if status == "FIN": c_status = c_accent

        res = [entry]
        h = 75 

        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 0, 70, h, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, status, c_status, c_status))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 100, 0, 80, h, 1, RT_HALIGN_CENTER|RT_VALIGN_CENTER, league_short, c_dim, c_dim))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 190, 0, 300, h, 1, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, left_text, c_h_name, c_h_name))

        if h_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 505, 10, 55, 55, LoadPixmap(h_png)))
        
        if "-" in score_text:
            parts = score_text.split('-')
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 580, 15, 50, 45, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, parts[0].strip(), c_h_score, c_h_score, c_box, c_box))
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 630, 0, 20, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "-", c_dim, c_dim))
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 650, 15, 50, 45, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, parts[1].strip(), c_a_score, c_a_score, c_box, c_box))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 580, 0, 120, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, c_dim, c_dim))

        if a_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 720, 10, 55, 55, LoadPixmap(a_png)))

        res.append((eListboxPythonMultiContent.TYPE_TEXT, 790, 0, 300, h, 1, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, c_a_name, c_a_name))
        
        # Font 3 (Smaller)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1090, 0, 170, h, 3, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, time_str, c_dim, c_dim))

        if goal_side == 'home': res.append((eListboxPythonMultiContent.TYPE_TEXT, 480, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "<", c_accent, c_accent))
        elif goal_side == 'away': res.append((eListboxPythonMultiContent.TYPE_TEXT, 780, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, ">", c_accent, c_accent))

        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 72, 1240, 2, 0, RT_HALIGN_CENTER, "", 0x22182c82, 0x22182c82))

        return res
    except: return []



def GameInfoEntry(label, val_home, val_away, is_header=False):
    # THEME CHECK
    is_ucl = False
    if global_sports_monitor and hasattr(global_sports_monitor, 'theme_mode'):
        is_ucl = (global_sports_monitor.theme_mode == 'ucl')

    # Colors
    if is_ucl:
        # UCL Theme Colors
        col_text = C_UCL_WHITE
        col_val  = C_UCL_WHITE
        col_bg   = None
        col_div  = C_UCL_BLUE_LIGHT
        
        if is_header:
            col_text = C_UCL_CYAN
            col_bg   = C_UCL_BLUE_LIGHT
            col_val  = C_UCL_CYAN
    else:
        # Default Theme Colors
        col_text = C_WHITE
        col_val  = C_PL_GREEN
        col_bg   = None
        col_div  = C_DARK_GREY
        
        if is_header:
            col_text = C_GOLD
            col_bg   = C_BLUE_HEADER
            col_val  = C_WHITE

    font_size = 28
    if is_header: font_size = 30

    res = ["entry"]
    
    if col_bg:
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1200, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "", None, None, col_bg, col_bg))
    
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 0, 500, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, label, col_text, col_text, None, None, 0, 0, font_size))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 550, 0, 300, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, val_home, col_val, col_val, None, None, 0, 0, font_size))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 880, 0, 300, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, val_away, col_val, col_val, None, None, 0, 0, font_size))
    # Divider line
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 48, 1200, 2, 0, RT_HALIGN_CENTER, "", col_div, col_div, col_div, col_div))
    return res

def SelectionListEntry(name, is_selected):
    # THEME CHECK
    is_ucl = False
    if global_sports_monitor and hasattr(global_sports_monitor, 'theme_mode'):
        is_ucl = (global_sports_monitor.theme_mode == 'ucl')

    check_mark = "[x]" if is_selected else "[ ]"
    
    if is_ucl:
        col_sel = C_UCL_CYAN if is_selected else C_GREY
        text_col = C_UCL_WHITE if is_selected else C_GREY
    else:
        col_sel = C_PL_GREEN if is_selected else C_GREY
        text_col = C_WHITE if is_selected else C_GREY

    res = [(name, is_selected)]
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 5, 40, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, check_mark, col_sel, col_sel, None, None))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 70, 5, 700, 40, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, name, text_col, text_col, None, None))
    return res

# ==============================================================================
# GOAL NOTIFICATION (Mini-Bar Style - Top Left)
# ==============================================================================
class GoalToast(Screen):
    def __init__(self, session, league_text, match_text, scorer_text, l_url, h_url, a_url):
        # --- DYNAMIC WIDTH CALCULATION ---
        len_league = len(str(league_text))
        len_match = len(str(match_text))
        len_scorer = len(str(scorer_text))
        max_len = max(len_league, len_match, len_scorer)
        calc_width = (max_len * 16) + 160
        width = max(620, min(1200, int(calc_width)))
        
        right_logo_x = width - 65
        right_bar_x = width - 5
        center_text_w = width - 140
        
        if global_sports_monitor.theme_mode == "ucl":
            self.skin = """
                <screen position="40,10" size="{w},80" title="Goal Notification" flags="wfNoBorder" backgroundColor="#00000000">
                    <eLabel position="0,0" size="{w},80" backgroundColor="#0e1e5b" zPosition="0" />
                    <eLabel position="0,0" size="{w},2" backgroundColor="#00ffff" zPosition="2" />
                    <widget name="league" position="10,5" size="{text_w_half},20" font="Regular;16" foregroundColor="#00ffff" backgroundColor="#0e1e5b" valign="center" halign="left" transparent="1" zPosition="3" />
                    <widget name="scorer" position="{scr_x},5" size="{text_w_half},20" font="Regular;16" foregroundColor="#ffffff" backgroundColor="#0e1e5b" valign="center" halign="right" transparent="1" zPosition="3" />
                    <widget name="h_logo" position="15,30" size="45,45" alphatest="blend" zPosition="4" />
                    <widget name="a_logo" position="{log_x},30" size="45,45" alphatest="blend" zPosition="4" />
                    <widget name="match" position="70,25" size="{txt_w},50" font="Regular;26" foregroundColor="#ffffff" backgroundColor="#0e1e5b" valign="center" halign="center" transparent="1" zPosition="3" />
                </screen>
            """.format(w=width, log_x=right_logo_x, txt_w=center_text_w, text_w_half=(width//2)-20, scr_x=(width//2)+10)
        else:
            self.skin = """
            <screen position="40,10" size="{w},80" title="Goal Notification" flags="wfNoBorder" backgroundColor="#00000000">
                <eLabel position="0,0" size="{w},20" backgroundColor="#E6000000" zPosition="0" />
                <widget name="league" position="10,0" size="{text_w_half},20" font="Regular;16" foregroundColor="#FFD700" backgroundColor="#E6000000" valign="center" halign="left" transparent="1" zPosition="3" />
                <widget name="scorer" position="{scr_x},0" size="{text_w_half},20" font="Regular;16" foregroundColor="#00FF85" backgroundColor="#E6000000" valign="center" halign="right" transparent="1" zPosition="3" />
                <eLabel position="0,20" size="{w},60" backgroundColor="#33190028" zPosition="0" />
                <eLabel position="0,20" size="5,60" backgroundColor="#E90052" zPosition="1" /> 
                <eLabel position="{bar_x},20" size="5,60" backgroundColor="#F6B900" zPosition="1" /> 
                <widget name="h_logo" position="15,25" size="50,50" alphatest="blend" zPosition="4" />
                <widget name="a_logo" position="{log_x},25" size="50,50" alphatest="blend" zPosition="4" />
                <widget name="match" position="70,20" size="{txt_w},60" font="Regular;26" foregroundColor="#FFFFFF" backgroundColor="#33190028" valign="center" halign="center" transparent="1" zPosition="3" />
                <eLabel position="0,78" size="{w},2" backgroundColor="#00FF85" zPosition="2" />
            </screen>
            """.format(w=width, log_x=right_logo_x, bar_x=right_bar_x, txt_w=center_text_w, text_w_half=(width//2)-20, scr_x=(width//2)+10)

        Screen.__init__(self, session)
        self["league"] = Label(str(league_text))
        self["match"] = Label(str(match_text))
        self["scorer"] = Label(str(scorer_text))
        
        self["l_logo"] = Pixmap()
        self["h_logo"] = Pixmap()
        self["a_logo"] = Pixmap()
        
        self.download_image(l_url, "l_logo", "/tmp/ss_l_logo.png")
        self.download_image(h_url, "h_logo", "/tmp/ss_h_logo.png")
        self.download_image(a_url, "a_logo", "/tmp/ss_a_logo.png")

        # --- TIMER COMPATIBILITY FIX ---
        self.timer = eTimer()
        try:
            self.timer.callback.append(self.close)
        except AttributeError:
            self.timer.timeout.get().append(self.close)
        self.timer.start(8000, True)

        # --- UPDATE: DISMISS ON ANY KEY ---
        self["actions"] = ActionMap([
            "SetupActions", "ColorActions", "DirectionActions", "MenuActions", 
            "NumberActions", "EPGSelectActions", "InfobarActions", "GlobalActions"
        ], {
            "ok": self.close, "cancel": self.close,
            "up": self.close, "down": self.close, "left": self.close, "right": self.close,
            "red": self.close, "green": self.close, "yellow": self.close, "blue": self.close,
            "menu": self.close, "info": self.close, "epg": self.close, 
            "1": self.close, "2": self.close, "3": self.close, "4": self.close, "5": self.close,
            "6": self.close, "7": self.close, "8": self.close, "9": self.close, "0": self.close,
            "volumeUp": self.close, "volumeDown": self.close, "volumeMute": self.close,
            "channelUp": self.close, "channelDown": self.close
        }, -1)
        
        self.onLayoutFinish.append(self.force_top)

    def force_top(self):
        try: self.instance.setZPosition(10)
        except: pass

    def download_image(self, url, widget_name, target_path):
        if url and url.startswith("http"):
            from twisted.web.client import downloadPage
            downloadPage(url.encode('utf-8'), target_path).addCallback(self.image_downloaded, widget_name, target_path).addErrback(self.image_error)

    def image_downloaded(self, data, widget_name, target_path):
        if self[widget_name].instance:
            self[widget_name].instance.setPixmapFromFile(target_path)
            self[widget_name].show()

    def image_error(self, error):
        pass

# ==============================================================================
# SPORTS MONITOR (OPTIMIZED)
# ==============================================================================
class SportsMonitor:
    def __init__(self):
        self.active = False
        self.discovery_mode = 0  # 0: OFF, 1: ON (Visual), 2: ON (Sound)
        self.current_league_index = 0
        self.custom_league_indices = []
        self.is_custom_mode = False
        self.last_scores = {}
        self.goal_flags = {}
        self.last_states = {} 
        self.filter_mode = 0 
        self.theme_mode = "default"
        
        self.reminders = [] 
        
        self.timer = eTimer()
        safe_connect(self.timer, self.check_goals)
            
        self.session = None
        self.cached_events = [] 
        self.callbacks = []
        self.status_message = "Initializing..."
        self.notification_queue = []
        self.notification_active = False
        
        # Initialize logo cache
        self.logo_cache = LogoCacheManager()
        log_message("SportsMonitor initialized", "INFO")
        
        self.load_config()

    def set_session(self, session): self.session = session

    def register_callback(self, func):
        if func not in self.callbacks: self.callbacks.append(func)

    def unregister_callback(self, func):
        if func in self.callbacks: self.callbacks.remove(func)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.current_league_index = int(data.get("league_index", 0))
                    self.filter_mode = int(data.get("filter_mode", 0))
                    self.theme_mode = data.get("theme_mode", "default")
                    
                    self.discovery_mode = int(data.get("discovery_mode", 0))
                    self.active = (self.discovery_mode > 0)
                    
                    self.custom_league_indices = data.get("custom_indices", [])
                    self.is_custom_mode = bool(data.get("is_custom_mode", False))
                    
                    self.reminders = data.get("reminders", [])
                    
                    if self.active: self.timer.start(60000, False)
            except: 
                self.filter_mode = 0
                self.theme_mode = "default"
                self.discovery_mode = 0
                self.reminders = []

    def save_config(self):
        data = {
            "league_index": self.current_league_index,
            "filter_mode": self.filter_mode,
            "theme_mode": self.theme_mode,
            "discovery_mode": self.discovery_mode,
            "active": self.active,
            "custom_indices": self.custom_league_indices,
            "is_custom_mode": self.is_custom_mode,
            "reminders": self.reminders
        }
        try:
            with open(CONFIG_FILE, "w") as f: json.dump(data, f)
        except: pass

    def toggle_theme(self):
        if self.theme_mode == "default": self.theme_mode = "ucl"
        else: self.theme_mode = "default"
        self.save_config()
        return self.theme_mode

    def toggle_filter(self):
        self.filter_mode = (self.filter_mode + 1) % 4
        self.save_config()
        return self.filter_mode

    def cycle_discovery_mode(self):
        self.discovery_mode = (self.discovery_mode + 1) % 3
        
        if self.discovery_mode > 0:
            self.active = True
            if not self.timer.isActive():
                self.timer.start(60000, False)
            self.check_goals()
        else:
            self.active = False
            self.timer.stop()
            
        self.save_config()
        return self.discovery_mode

    def toggle_activity(self):
        return self.cycle_discovery_mode()

    def play_sound(self):
        try:
            mp3_path = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/pop.mp3")
            if os.path.exists(mp3_path):
                cmd = 'gst-launch-1.0 playbin uri=file://{} audio-sink="alsasink" > /dev/null 2>&1 &'.format(mp3_path)
                os.system(cmd)
        except: pass

    def play_stend_sound(self):
        try:
            mp3_path = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/stend.mp3")
            if os.path.exists(mp3_path):
                cmd = 'gst-launch-1.0 playbin uri=file://{} audio-sink="alsasink" > /dev/null 2>&1 &'.format(mp3_path)
                os.system(cmd)
        except: pass

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

    def add_reminder(self, match_name, trigger_time, league_name, h_logo, a_logo, label):
        new_rem = {
            "match": match_name,
            "trigger": trigger_time,
            "league": league_name,
            "h_logo": h_logo,
            "a_logo": a_logo,
            "label": label
        }
        for r in self.reminders:
            if r["match"] == match_name and r["trigger"] == trigger_time:
                return
                
        self.reminders.append(new_rem)
        self.save_config()

    def remove_reminder(self, match_name):
        initial_len = len(self.reminders)
        self.reminders = [r for r in self.reminders if r["match"] != match_name]
        
        if len(self.reminders) < initial_len:
            self.save_config()
            return True
        return False

    def check_reminders(self):
        now = time.time()
        active_reminders = []
        reminders_triggered = False
        
        for rem in self.reminders:
            if now >= rem["trigger"]:
                self.queue_notification(
                    rem["league"], 
                    rem["match"], 
                    rem["label"],
                    None, 
                    rem["h_logo"], 
                    rem["a_logo"]
                )
                self.play_stend_sound()
                reminders_triggered = True
            else:
                active_reminders.append(rem)
        
        if reminders_triggered:
            self.reminders = active_reminders
            self.save_config()

    def check_goals(self):
        self.check_reminders()
        
        self.status_message = "Loading Data..."
        for cb in self.callbacks: cb(False)
        agent = Agent(reactor)

        if not self.is_custom_mode:
            try:
                name, url = DATA_SOURCES[self.current_league_index]
                d = agent.request(b'GET', url.encode('utf-8'))
                d.addCallback(readBody)
                d.addCallback(self.parse_single_json, name, url) 
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
                    # Pass URL to callback
                    d.addCallback(lambda b, n=name, u=url: (b, n, u))
                    d.addErrback(lambda f: (b"{}", "", "")) 
                    deferreds.append(d)
            
            dlist = defer.gatherResults(deferreds, consumeErrors=True)
            dlist.addCallback(self.parse_multi_json)
            dlist.addErrback(self.handle_error)

    def handle_error(self, failure):
        self.status_message = "API Connection Error"
        self.cached_events = []
        for cb in self.callbacks: cb(True)

    def parse_single_json(self, body, league_name_fixed="", league_url=""): 
        self.process_events_data([(body, league_name_fixed, league_url)])
        
    def parse_multi_json(self, bodies_list): 
        self.process_events_data(bodies_list)

    def queue_notification(self, league, match, scorer, l_url, h_url, a_url):
        self.notification_queue.append((league, match, scorer, l_url, h_url, a_url))
        self.process_queue()

    def process_queue(self):
        if self.notification_active or not self.notification_queue:
            return

        league, match, scorer, l_url, h_url, a_url = self.notification_queue.pop(0)
        self.notification_active = True
        
        if self.session:
            self.session.openWithCallback(self.on_toast_closed, GoalToast, league, match, scorer, l_url, h_url, a_url)
        else:
            self.notification_active = False

    def on_toast_closed(self, *args):
        self.notification_active = False
        self.process_queue()

    def get_sport_type(self, league_name):
        lname = league_name.lower()
        if any(x in lname for x in ['nba', 'wnba', 'basket', 'euroleague']): return 'basketball'
        if any(x in lname for x in ['nfl', 'ncaa football', 'ufl']): return 'football'
        if any(x in lname for x in ['mlb', 'baseball']): return 'baseball'
        if any(x in lname for x in ['nhl', 'hockey']): return 'hockey'
        return 'soccer'

    def get_cdn_sport_name(self, league_name):
        lname = league_name.lower()
        if 'nba' in lname or 'basket' in lname: return 'nba'
        if 'nfl' in lname: return 'nfl'
        if 'mlb' in lname: return 'mlb'
        if 'nhl' in lname: return 'nhl'
        if 'college' in lname or 'ncaa' in lname: return 'ncaa'
        return 'soccer'

    def get_score_prefix(self, sport, diff):
        if diff < 0: return "GOAL DISALLOWED" 
        if sport == 'soccer' or sport == 'hockey': return "GOAL!"
        if sport == 'basketball':
            if diff == 1: return "Free Throw (+1)"
            if diff == 2: return "Two Points!"
            if diff == 3: return "Three Points!"
            return "SCORE (+{})".format(diff)
        if sport == 'football':
            if diff == 6: return "TOUCHDOWN!"
            if diff == 3: return "Field Goal"
            if diff == 1: return "Extra Point"
            if diff == 2: return "Safety"
            if diff == 7: return "Touchdown + XP"
            if diff == 8: return "Touchdown + 2Pt"
            return "SCORE (+{})".format(diff)
        if sport == 'baseball':
            if diff >= 4: return "GRAND SLAM!"
            if diff == 1: return "RUN SCORED"
            return "{} RUNS SCORED".format(diff)
        return "SCORE (+{})".format(diff)

    def get_scorer_text(self, event):
        try:
            details = event.get('competitions', [{}])[0].get('details', [])
            if details:
                for play in reversed(details):
                    is_scoring = play.get('scoringPlay', False)
                    text_desc = play.get('type', {}).get('text', '').lower()
                    if is_scoring or "goal" in text_desc or "touchdown" in text_desc or "run" in text_desc:
                        clock = play.get('clock', {}).get('displayValue', '')
                        athletes = play.get('athletesInvolved', [])
                        if not athletes:
                            athletes = play.get('participants', [])

                        if athletes:
                            player = athletes[0]
                            p_name = player.get('displayName') or player.get('fullName') or player.get('shortName') or "Unknown"
                            return "{}  ( {} )".format(p_name, clock)
                        else:
                            return "Goal  ( {} )".format(clock)
        except: pass
        return ""

    def process_events_data(self, data_list, single_league_name=""):
        all_events = []
        try:
            for item in data_list:
                if isinstance(item, tuple):
                    body, l_name, l_url = item
                else:
                    body = item
                    l_name = single_league_name
                    l_url = ""

                try:
                    json_str = body.decode('utf-8', errors='ignore')
                    data = json.loads(json_str)
                    
                    league_obj = data.get('leagues', [{}])[0]
                    if l_name:
                        league_name = l_name
                    else:
                        league_name = league_obj.get('name') or league_obj.get('shortName') or ""
                    
                    events = data.get('events', [])
                    for ev in events:
                        ev['league_name'] = league_name
                        ev['league_url'] = l_url
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
                
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                if len(comps) < 2: continue 
                
                league_name = event.get('league_name', '')
                sport_cdn = self.get_cdn_sport_name(league_name)
                
                # --- FIXED: Robust Team Extraction (Solves "Home vs Away" & "Missing Basketball" bugs) ---
                team_h = next((t for t in comps if t.get('homeAway') == 'home'), None)
                team_a = next((t for t in comps if t.get('homeAway') == 'away'), None)
                
                # Fallback: If 'homeAway' tag is missing, assume index 0 is Home, index 1 is Away
                if not team_h and len(comps) > 0: team_h = comps[0]
                if not team_a and len(comps) > 1: team_a = comps[1]

                # Extract Details
                home = team_h.get('team', {}).get('shortDisplayName') or team_h.get('team', {}).get('displayName') or "Home"
                h_score = int(team_h.get('score', '0'))
                h_id = team_h.get('team', {}).get('id', '')
                h_logo = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png&w=40&h=40&transparent=true".format(sport_cdn, h_id) if h_id else ""

                away = team_a.get('team', {}).get('shortDisplayName') or team_a.get('team', {}).get('displayName') or "Away"
                a_score = int(team_a.get('score', '0'))
                a_id = team_a.get('team', {}).get('id', '')
                a_logo = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png&w=40&h=40&transparent=true".format(sport_cdn, a_id) if a_id else ""

                event['h_logo_url'] = h_logo
                event['a_logo_url'] = a_logo

                l_logo = "" 
                match_id = home + "_" + away # ID is now guaranteed to be real names, not "Home_Away"
                score_str = str(h_score) + "-" + str(a_score)

                prev_state = self.last_states.get(match_id)
                if self.active and self.session and prev_state:
                    should_play_stend = (self.discovery_mode == 2 and self.get_sport_type(league_name) == 'soccer')
                    
                    if state == 'in' and prev_state == 'pre':
                        match_txt = "{} {} - {} {}".format(home, h_score, a_score, away)
                        self.queue_notification(league_name, match_txt, "MATCH STARTED", l_logo, h_logo, a_logo)
                        if should_play_stend: self.play_stend_sound()
                        
                    elif state == 'post' and prev_state == 'in':
                        match_txt = "{} {} - {} {}".format(home, h_score, a_score, away)
                        self.queue_notification(league_name, match_txt, "FULL TIME", l_logo, h_logo, a_logo)
                        if should_play_stend: self.play_stend_sound()

                self.last_states[match_id] = state

                if state == 'in':
                    if match_id in self.last_scores:
                        if self.last_scores[match_id] != score_str:
                            try:
                                prev_h, prev_a = map(int, self.last_scores[match_id].split('-'))
                                diff_h = h_score - prev_h
                                diff_a = a_score - prev_a
                                sport_type = self.get_sport_type(league_name)

                                # Sound Logic: Active ONLY for Soccer in Mode 2
                                should_play_sound = False
                                if self.active and self.discovery_mode == 2 and sport_type == 'soccer':
                                    if diff_h > 0 or diff_a > 0:
                                        should_play_sound = True

                                # Notification Logic: Active for ALL sports if Mode > 0
                                if diff_h != 0:
                                    if diff_h > 0: 
                                        self.goal_flags[match_id] = {'side': 'home', 'time': time.time()}
                                        if should_play_sound: self.play_sound()
                                    
                                    if self.active and self.session:
                                        prefix = self.get_score_prefix(sport_type, diff_h)
                                        match_txt = "{} >> {} {} - {} {}".format(prefix, home, h_score, a_score, away)
                                        scorer_txt = self.get_scorer_text(event)
                                        self.queue_notification(league_name, match_txt, scorer_txt, l_logo, h_logo, a_logo)

                                if diff_a != 0:
                                    if diff_a > 0: 
                                        self.goal_flags[match_id] = {'side': 'away', 'time': time.time()}
                                        if should_play_sound: self.play_sound()

                                    if self.active and self.session:
                                        prefix = self.get_score_prefix(sport_type, diff_a)
                                        match_txt = "{} {} {} - {} {} <<".format(prefix, home, h_score, a_score, away)
                                        scorer_txt = self.get_scorer_text(event)
                                        self.queue_notification(league_name, match_txt, scorer_txt, l_logo, h_logo, a_logo)
                            except: pass
                    
                    self.last_scores[match_id] = score_str

            for cb in self.callbacks: cb(True)
        except:
            self.status_message = "JSON Parse Error"
            for cb in self.callbacks: cb(True)

if global_sports_monitor is None:
    global_sports_monitor = SportsMonitor()
    

# ==============================================================================
# 1. HELPER FUNCTION (Unchanged)
# ==============================================================================
def StatsListEntry(label, home_val, away_val, theme_mode):
    """Creates a 3-column entry: HomeVal | LABEL | AwayVal"""
    
    # Theme Colors
    if theme_mode == "ucl":
        col_label = 0x00ffff # Cyan
        col_val = 0xffffff   # White
        col_bg = 0x0e1e5b    # Dark Blue bg
    else:
        col_label = 0x00FF85 # Green
        col_val = 0xFFFFFF   # White
        col_bg = 0x33190028  # Dark Purple bg

    # Layout Constants (Total width approx 1200)
    h_w, l_w, a_w = 400, 400, 400
    h_x, l_x, a_x = 0, 400, 800
    
    res = [None]
    # Background line
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 48, 1200, 2, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, 1))

    # CENTER: Label (Uppercase)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, l_x, 0, l_w, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(label).upper(), col_label, col_bg))

    # LEFT: Home Value (Right Aligned)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, h_x, 0, h_w-20, 50, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, str(home_val), col_val, col_bg))

    # RIGHT: Away Value (Left Aligned)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, a_x+20, 0, a_w-20, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(away_val), col_val, col_bg))
    
    return res
    
    
    
        
# ==============================================================================
# 2. GAME INFO SCREEN (Paginated)
# ==============================================================================
class GameInfoScreen(Screen):
    def __init__(self, session, event_id, league_url):
        Screen.__init__(self, session)
        self.theme = global_sports_monitor.theme_mode
        
        # Pagination Variables
        self.full_rows = []      # Stores all data
        self.current_page = 0    
        self.items_per_page = 10 
        
        # --- SKIN DEFINITION ---
        common_widgets = """
            <widget name="h_logo" position="30,25" size="100,100" alphatest="blend" zPosition="5" scale="1" />
            <widget name="h_name" position="150,35" size="250,40" font="Regular;26" foregroundColor="#ffffff" transparent="1" halign="left" valign="center" zPosition="5" />
            
            <widget name="h_score" position="410,15" size="180,120" font="Regular;80" foregroundColor="#ffffff" transparent="1" halign="right" valign="center" zPosition="5" />

            <widget name="match_title" position="590,20" size="100,35" font="Regular;24" foregroundColor="{accent}" transparent="1" halign="center" valign="center" text="STATS" zPosition="5" />
            <eLabel position="590,60" size="100,40" font="Regular;32" foregroundColor="#ffffff" transparent="1" halign="center" valign="center" text="V" zPosition="5" />
            
            <widget name="stadium_name" position="340,105" size="600,40" font="Regular;20" foregroundColor="#bbbbbb" transparent="1" halign="center" valign="center" zPosition="5" />

            <widget name="a_score" position="690,15" size="180,120" font="Regular;80" foregroundColor="#ffffff" transparent="1" halign="left" valign="center" zPosition="5" />
            
            <widget name="a_name" position="880,35" size="250,40" font="Regular;26" foregroundColor="#ffffff" transparent="1" halign="right" valign="center" zPosition="5" />
            <widget name="a_logo" position="1150,25" size="100,100" alphatest="blend" zPosition="5" scale="1" />

            <widget name="info_list" position="40,170" size="1200,540" scrollbarMode="showNever" transparent="1" zPosition="5" />
            <widget name="loading" position="0,300" size="1280,100" font="Regular;32" foregroundColor="{accent}" transparent="1" halign="center" zPosition="10" />
            
            <widget name="page_indicator" position="0,670" size="1280,40" font="Regular;24" foregroundColor="#ffffff" transparent="1" halign="center" zPosition="10" />
        """

        if self.theme == "ucl":
            bg_color = "#00000000"
            top_bar = "#091442"
            accent = "#00ffff"
            skin_widgets = common_widgets.replace("{accent}", accent)
            
            self.skin = f"""
            <screen position="center,center" size="1280,720" title="Game Stats" flags="wfNoBorder" backgroundColor="{bg_color}">
                <eLabel position="0,0" size="1280,150" backgroundColor="{top_bar}" zPosition="0" />
                <eLabel position="0,150" size="1280,4" backgroundColor="{accent}" zPosition="1" />
                {skin_widgets}
            </screen>
            """
        else:
            bg_color = "#38003C"
            top_bar = "#28002C"
            accent = "#00FF85"
            skin_widgets = common_widgets.replace("{accent}", accent)

            self.skin = f"""
            <screen position="center,center" size="1280,720" title="Game Stats" flags="wfNoBorder" backgroundColor="{bg_color}">
                <eLabel position="0,0" size="1280,150" backgroundColor="{top_bar}" zPosition="0" />
                <eLabel position="0,150" size="1280,4" backgroundColor="{accent}" zPosition="1" />
                {skin_widgets}
            </screen>
            """

        # Header Widgets
        self["h_name"] = Label("")
        self["a_name"] = Label("")
        self["h_score"] = Label("")
        self["a_score"] = Label("")
        self["stadium_name"] = Label("")
        self["match_title"] = Label("MATCH STATS")
        self["h_logo"] = Pixmap()
        self["a_logo"] = Pixmap()
        self["loading"] = Label("Fetching Stats...")
        self["page_indicator"] = Label("")
        
        # LIST SETUP
        self["info_list"] = MenuList([], enableWrapAround=False, content=eListboxPythonMultiContent)
        self["info_list"].l.setFont(0, gFont("Regular", 28))
        self["info_list"].l.setItemHeight(50)
        
        # NAVIGATION ACTIONS
        self["actions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions", "WizardActions"], {
            "cancel": self.close, "green": self.close, "ok": self.close, "back": self.close,
            "up": self.page_up, 
            "down": self.page_down,
            "left": self.page_up, 
            "right": self.page_down
        }, -2)
        
        self.event_id = event_id
        self.summary_url = league_url.replace("scoreboard", "summary") + "?event=" + str(event_id)
        self.onLayoutFinish.append(self.start_loading)

    def update_display(self):
        if not self.full_rows:
            self["info_list"].setList([])
            self["page_indicator"].setText("")
            return

        total_items = len(self.full_rows)
        start_index = self.current_page * self.items_per_page
        end_index = start_index + self.items_per_page
        
        page_data = self.full_rows[start_index:end_index]
        self["info_list"].setList(page_data)
        
        import math
        total_pages = int(math.ceil(float(total_items) / float(self.items_per_page)))
        if total_pages > 1:
            self["page_indicator"].setText("Page {}/{}".format(self.current_page + 1, total_pages))
        else:
            self["page_indicator"].setText("")

    def page_down(self):
        total_items = len(self.full_rows)
        max_page = 0
        if total_items > 0:
            import math
            max_page = int(math.ceil(float(total_items) / float(self.items_per_page))) - 1
            
        if self.current_page < max_page:
            self.current_page += 1
            self.update_display()

    def page_up(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_display()

    def start_loading(self):
        self.fetch_details()

    def fetch_details(self):
        from twisted.web.client import getPage
        getPage(self.summary_url.encode('utf-8')).addCallback(self.parse_details).addErrback(self.error_details)

    def error_details(self, error):
        self["loading"].setText("Error loading details.")

    def download_logo(self, url, widget_name):
        if url and url.startswith("http"):
            hq_url = url.replace("40&h=40", "500&h=500")
            tmp_path = "/tmp/ss_big_{}.png".format(widget_name)
            from twisted.web.client import downloadPage
            downloadPage(hq_url.encode('utf-8'), tmp_path).addCallback(self.logo_ready, widget_name, tmp_path)

    def logo_ready(self, data, widget_name, tmp_path):
        if self[widget_name].instance:
            self[widget_name].instance.setPixmapFromFile(tmp_path)
            self[widget_name].show()

    def parse_details(self, body):
        try:
            self["loading"].hide()
            json_str = body.decode('utf-8', errors='ignore')
            data = json.loads(json_str)
            
            # --- 1. DATA EXTRACTION ---
            header_competitors = data.get('header', {}).get('competitions', [{}])[0].get('competitors', [])
            boxscore_teams = data.get('boxscore', {}).get('teams', [])

            # --- STADIUM & LOCATION EXTRACTION ---
            try:
                game_info = data.get('gameInfo', {})
                venue = game_info.get('venue', {})
                v_name = venue.get('fullName', '')
                
                # Get City/State
                addr = venue.get('address', {})
                v_city = addr.get('city', '')
                v_state = addr.get('state', '')
                
                location_text = ""
                if v_name:
                    location_text = v_name
                    if v_city:
                        location_text += " - {}, {}".format(v_city, v_state) if v_state else " - {}".format(v_city)
                
                self["stadium_name"].setText(location_text)
            except:
                self["stadium_name"].setText("")

            home_team = {}
            away_team = {}

            if header_competitors:
                home_team = next((t for t in header_competitors if t.get('homeAway') == 'home'), {})
                away_team = next((t for t in header_competitors if t.get('homeAway') == 'away'), {})

            if not home_team.get('team', {}).get('displayName') and boxscore_teams:
                h_id = home_team.get('id')
                if h_id:
                    home_team_box = next((t for t in boxscore_teams if t.get('team', {}).get('id') == h_id), {})
                else:
                    home_team_box = boxscore_teams[0] if len(boxscore_teams) > 0 else {}
                if home_team_box: home_team.update(home_team_box)

                a_id = away_team.get('id')
                if a_id:
                    away_team_box = next((t for t in boxscore_teams if t.get('team', {}).get('id') == a_id), {})
                else:
                    away_team_box = boxscore_teams[1] if len(boxscore_teams) > 1 else {}
                if away_team_box: away_team.update(away_team_box)

            # --- 2. NAME & SCORE ---
            def get_name(t_obj):
                team = t_obj.get('team', {})
                return team.get('shortDisplayName') or team.get('displayName') or team.get('name') or team.get('abbreviation') or ""

            h_name = get_name(home_team)
            a_name = get_name(away_team)
            
            if not h_name: h_name = "Home"
            if not a_name: a_name = "Away"

            h_score_val = home_team.get('score')
            a_score_val = away_team.get('score')
            h_score_txt = str(h_score_val) if h_score_val is not None else "0"
            a_score_txt = str(a_score_val) if a_score_val is not None else "0"

            self["h_name"].setText(h_name)
            self["a_name"].setText(a_name)
            self["h_score"].setText(h_score_txt)
            self["a_score"].setText(a_score_txt)

            # Logos
            header = data.get('header', {})
            league_name = header.get('league', {}).get('name', '')
            if not league_name: league_name = data.get('league', {}).get('name', '')

            sport_cdn = global_sports_monitor.get_cdn_sport_name(league_name)
            h_id = home_team.get('team', {}).get('id', '')
            a_id = away_team.get('team', {}).get('id', '')
            
            if h_id:
                h_url = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png&w=40&h=40&transparent=true".format(sport_cdn, h_id)
                self.download_logo(h_url, "h_logo")
            if a_id:
                a_url = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png&w=40&h=40&transparent=true".format(sport_cdn, a_id)
                self.download_logo(a_url, "a_logo")

            # --- 3. BUILD FULL LIST ---
            self.full_rows = [] 

            competitions_data = data.get('competitions', [{}])[0]
            if not competitions_data.get('details'):
                competitions_data = data.get('header', {}).get('competitions', [{}])[0]

            details = competitions_data.get('details', [])
            goals_found = False
            
            if details:
                self.full_rows.append(StatsListEntry("TIME", "SCORER (HOME)", "SCORER (AWAY)", self.theme))
                
                for play in details:
                    text_desc = play.get('type', {}).get('text', '').lower()
                    is_scoring = play.get('scoringPlay', False) or \
                                 "goal" in text_desc or \
                                 "score" in text_desc or \
                                 "touchdown" in text_desc
                    
                    if is_scoring:
                        goals_found = True
                        clock = play.get('clock', {}).get('displayValue', '')
                        
                        scorer_name = "Unknown"
                        athletes = play.get('athletesInvolved', [])
                        if athletes:
                            scorer_name = athletes[0].get('displayName') or athletes[0].get('shortName')
                        elif play.get('participants'):
                            p = play['participants'][0].get('athlete', {})
                            scorer_name = p.get('displayName') or p.get('shortName')
                        else:
                            clean_text = play.get('type', {}).get('text', 'Goal')
                            if " - " in clean_text:
                                scorer_name = clean_text.split(" - ")[-1]
                            else:
                                scorer_name = clean_text

                        if not scorer_name: scorer_name = "Goal"

                        team_id = str(play.get('team', {}).get('id', ''))
                        h_id_root = str(home_team.get('id', 'h'))
                        
                        if team_id == h_id_root:
                            self.full_rows.append(StatsListEntry(clock, scorer_name, "", self.theme))
                        else:
                            self.full_rows.append(StatsListEntry(clock, "", scorer_name, self.theme))

            if not goals_found:
                if h_score_txt == "0" and a_score_txt == "0":
                     self.full_rows.append(StatsListEntry("-", "No Goals", "Recorded", self.theme))
                else:
                     self.full_rows.append(StatsListEntry("-", "Details", "Unavailable", self.theme))

            # --- 4. STATISTICS ---
            if boxscore_teams:
                self.full_rows.append(StatsListEntry("", "", "", self.theme))
                
                h_stats = next((t.get('statistics', []) for t in boxscore_teams if str(t.get('team', {}).get('id')) == str(home_team.get('id'))), [])
                a_stats = next((t.get('statistics', []) for t in boxscore_teams if str(t.get('team', {}).get('id')) == str(away_team.get('id'))), [])
                
                if not h_stats and len(boxscore_teams) > 0: h_stats = boxscore_teams[0].get('statistics', [])
                if not a_stats and len(boxscore_teams) > 1: a_stats = boxscore_teams[1].get('statistics', [])

                a_stats_map = {s['label']: s['displayValue'] for s in a_stats}
                
                for stat in h_stats:
                    label = stat['label']
                    h_val = stat['displayValue']
                    a_val = a_stats_map.get(label, "-")
                    self.full_rows.append(StatsListEntry(label, h_val, a_val, self.theme))

            self.current_page = 0
            self.update_display()

        except Exception as e:
            self["loading"].setText("Error: " + str(e))
            self["loading"].show()

# ==============================================================================
# LEAGUE SELECTOR
# ==============================================================================
class LeagueSelector(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        
        # THEME SELECTION
        if global_sports_monitor.theme_mode == "ucl":
             self.skin = """
            <screen position="center,center" size="900,700" title="Select Leagues" backgroundColor="#00000000" flags="wfNoBorder">
                <eLabel position="0,0" size="900,700" backgroundColor="#0e1e5b" zPosition="-1" />
                <eLabel position="0,0" size="900,4" backgroundColor="#00ffff" zPosition="1" />
                <eLabel position="0,696" size="900,4" backgroundColor="#00ffff" zPosition="1" />
                <eLabel position="0,0" size="4,700" backgroundColor="#00ffff" zPosition="1" />
                <eLabel position="896,0" size="4,700" backgroundColor="#00ffff" zPosition="1" />
                
                <widget name="header" position="30,25" size="840,50" font="Regular;38" foregroundColor="#00ffff" backgroundColor="#0e1e5b" transparent="1" halign="center" />
                <eLabel position="30,80" size="840,2" backgroundColor="#182c82" />
                
                <widget name="list" position="30,95" size="840,510" scrollbarMode="showOnDemand" transparent="1" />
                
                <eLabel position="30,615" size="840,2" backgroundColor="#182c82" />
                
                <widget name="key_red" position="30,635" size="220,50" font="Regular;28" foregroundColor="#FFFFFF" backgroundColor="#F44336" transparent="0" zPosition="1" halign="center" valign="center" />
                <widget name="key_green" position="650,635" size="220,50" font="Regular;28" foregroundColor="#000000" backgroundColor="#00FF85" transparent="0" zPosition="1" halign="center" valign="center" />
                <widget name="info" position="270,635" size="360,50" font="Regular;24" foregroundColor="#00ffff" backgroundColor="#0e1e5b" transparent="1" halign="center" valign="center" />
            </screen>
            """
        else:
            self.skin = """
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
        for idx, item in enumerate(DATA_SOURCES):
            name = item[0]
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
# MINI BAR 2 (Bottom Screen - Dynamic FHD/HD Support)
# ==============================================================================
class SimpleSportsMiniBar2(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        
        # DETECT RESOLUTION
        d_size = getDesktop(0).size()
        width = d_size.width()
        height = d_size.height()
        
        # LAYOUT CONFIGURATION
        if width > 1280:
            # FHD (1920x1080)
            is_fhd = True
            bar_h = 40 
            bar_y = height - bar_h 
            
            font_lg = "Regular;26"
            font_sm = "Regular;22"
            logo_s = 35 
            
            # --- MODIFIED GRID FOR SCORERS ---
            x_league = 30
            w_league = 250
            
            x_home_name = 290 
            w_home_name = 560
            x_h_logo = 860
            
            x_score = 920
            w_score = 140 
            
            x_a_logo = 1070
            x_away_name = 1115
            w_away_name = 560
            
            x_status = 1680
            w_status = 100
            x_time = 1790
            w_time = 120
        else:
            # HD (1280x720)
            is_fhd = False
            bar_h = 35
            bar_y = height - bar_h
            
            font_lg = "Regular;22"
            font_sm = "Regular;18"
            logo_s = 30
            
            x_league = 10
            w_league = 180          
            
            x_home_name = 200
            w_home_name = 320
            x_h_logo = 530
            
            x_score = 580
            w_score = 100
            
            x_a_logo = 690
            x_away_name = 740
            w_away_name = 320
            
            x_status = 1070
            w_status = 80
            x_time = 1160
            w_time = 110

        # BUILD SKIN
        if global_sports_monitor.theme_mode == "ucl":
            self.skin = """
            <screen position="0,{y}" size="{w},{h}" title="Sports Ticker Bottom" backgroundColor="#40000000" flags="wfNoBorder">
                <eLabel position="0,0" size="{w},{h}" backgroundColor="#cc0e1e5b" zPosition="0" />
                <eLabel position="0,0" size="{w},2" backgroundColor="#00ffff" zPosition="1" />
                
                <widget name="lbl_league" position="{xl},0" size="{wl},{h}" font="{fl}" foregroundColor="#00ffff" backgroundColor="#cc0e1e5b" transparent="1" halign="left" valign="center" zPosition="2" />
                
                <widget name="lbl_home" position="{xh},0" size="{wh},{h}" font="{fl}" foregroundColor="#ffffff" backgroundColor="#cc0e1e5b" transparent="1" halign="right" valign="center" zPosition="2" />
                <widget name="h_logo" position="{xhl},2" size="{ls},{ls}" alphatest="blend" zPosition="2" />
                
                <eLabel position="{xs},0" size="{ws},{h}" backgroundColor="#ffffff" zPosition="1" />
                <widget name="lbl_score" position="{xs},0" size="{ws},{h}" font="{fl}" foregroundColor="#0e1e5b" backgroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="3" />
                
                <widget name="a_logo" position="{xal},2" size="{ls},{ls}" alphatest="blend" zPosition="2" />
                <widget name="lbl_away" position="{xa},0" size="{wa},{h}" font="{fl}" foregroundColor="#ffffff" backgroundColor="#cc0e1e5b" transparent="1" halign="left" valign="center" zPosition="2" />
                
                <widget name="lbl_status" position="{xst},0" size="{wst},{h}" font="{fs}" foregroundColor="#ffffff" backgroundColor="#cc0e1e5b" transparent="1" halign="center" valign="center" zPosition="2" />
                <widget name="lbl_time" position="{xt},0" size="{wt},{h}" font="{fs}" foregroundColor="#00ffff" backgroundColor="#cc0e1e5b" transparent="1" halign="right" valign="center" zPosition="2" />
            </screen>
            """.format(y=bar_y, w=width, h=bar_h, fl=font_lg, fs=font_sm, ls=logo_s,
                       xl=x_league, wl=w_league, xh=x_home_name, wh=w_home_name, xhl=x_h_logo,
                       xs=x_score, ws=w_score, xst=x_status, wst=w_status, xal=x_a_logo,
                       xa=x_away_name, wa=w_away_name, xt=x_time, wt=w_time)
        else:
            self.skin = """
            <screen position="0,{y}" size="{w},{h}" title="Sports Ticker Bottom" backgroundColor="#40000000" flags="wfNoBorder">
                <eLabel position="0,0" size="{w},{h}" backgroundColor="#cc331900" zPosition="0" />
                <eLabel position="0,0" size="5,{h}" backgroundColor="#E90052" zPosition="1" /> 
                <eLabel position="{rend},{h}" size="5,{h}" backgroundColor="#F6B900" zPosition="1" />
                
                <widget name="lbl_league" position="{xl},0" size="{wl},{h}" font="{fl}" foregroundColor="#FFD700" backgroundColor="#cc331900" transparent="1" halign="left" valign="center" zPosition="2" />
                
                <widget name="lbl_home" position="{xh},0" size="{wh},{h}" font="{fl}" foregroundColor="#FFFFFF" backgroundColor="#cc331900" transparent="1" halign="right" valign="center" zPosition="2" />
                <widget name="h_logo" position="{xhl},2" size="{ls},{ls}" alphatest="blend" zPosition="2" />
                
                <eLabel position="{xs},0" size="{ws},{h}" backgroundColor="#00FF85" zPosition="1" />
                <widget name="lbl_score" position="{xs},0" size="{ws},{h}" font="{fl}" foregroundColor="#000000" backgroundColor="#00FF85" transparent="1" halign="center" valign="center" zPosition="3" />
                
                <widget name="a_logo" position="{xal},2" size="{ls},{ls}" alphatest="blend" zPosition="2" />
                <widget name="lbl_away" position="{xa},0" size="{wa},{h}" font="{fl}" foregroundColor="#FFFFFF" backgroundColor="#cc331900" transparent="1" halign="left" valign="center" zPosition="2" />
                
                <widget name="lbl_status" position="{xst},0" size="{wst},{h}" font="{fs}" foregroundColor="#FFFFFF" backgroundColor="#cc331900" transparent="1" halign="center" valign="center" zPosition="2" />
                <widget name="lbl_time" position="{xt},0" size="{wt},{h}" font="{fs}" foregroundColor="#00FF85" backgroundColor="#cc331900" transparent="1" halign="right" valign="center" zPosition="2" />
            </screen>
            """.format(y=bar_y, w=width, h=bar_h, rend=width-5, fl=font_lg, fs=font_sm, ls=logo_s,
                       xl=x_league, wl=w_league, xh=x_home_name, wh=w_home_name, xhl=x_h_logo,
                       xs=x_score, ws=w_score, xst=x_status, wst=w_status, xal=x_a_logo,
                       xa=x_away_name, wa=w_away_name, xt=x_time, wt=w_time)

        self["lbl_league"] = Label("")
        self["lbl_home"] = Label("")
        self["lbl_score"] = Label("")
        self["lbl_away"] = Label("")
        self["lbl_status"] = Label("")
        self["lbl_time"] = Label("")
        
        self["h_logo"] = Pixmap()
        self["a_logo"] = Pixmap()
        self["h_logo"].hide()
        self["a_logo"].hide()
        
        self.matches = []
        self.current_match_idx = 0
        
        self.league_colors = {
            "ENG": 0x00ff85, "ESP": 0xff4b4b, "ITA": 0x008fd7, "GER": 0xd3010c, 
            "FRA": 0xdae025, "UCL": 0x00ffff, "UEL": 0xff8800, "NBA": 0xC9082A, "NFL": 0x013369
        }
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close, 
            "green": self.close, 
            "yellow": self.toggle_filter_mini
        }, -1)
        
        self.ticker_timer = eTimer()
        safe_connect(self.ticker_timer, self.show_next_match)
        
        self.refresh_timer = eTimer()
        safe_connect(self.refresh_timer, self.load_data)
        
        self.onLayoutFinish.append(self.start_all_timers)

    def start_all_timers(self):
        self.load_data()
        self.refresh_timer.start(60000)

    def toggle_filter_mini(self): 
        global_sports_monitor.toggle_filter()
        self.load_data()
            
    def load_data(self): 
        global_sports_monitor.check_goals()
        self.parse_json()

    def get_scorers_string(self, event, home_id, away_id):
        h_scorers = []
        a_scorers = []
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
                            if "Goal - " in clean: scorer = clean.split("Goal - ")[1].split('(')[0].strip()
                        if scorer:
                            t_id = str(play.get('team', {}).get('id', ''))
                            if t_id == str(home_id): h_scorers.append(scorer)
                            elif t_id == str(away_id): a_scorers.append(scorer)
        except: pass
        
        def format_list(lst):
            if not lst: return ""
            seen = set()
            unique = [x for x in lst if not (x in seen or seen.add(x))]
            final_str = ", ".join(unique)
            if len(final_str) > 25:
                short_list = [n.split(' ')[-1] for n in unique]
                final_str = ", ".join(short_list)
            return final_str

        return format_list(h_scorers), format_list(a_scorers)

    def parse_json(self):
        events = global_sports_monitor.cached_events
        self.matches = []
        
        if not events:
            self.matches.append({'league': "SimplySports", 'color': 0xffffff, 'home': global_sports_monitor.status_message, 'away': "", 'score': "", 'status': "", 'time': "", 'h_png': None, 'a_png': None})
            return
            
        tmp_path = "/tmp/simplysports/logos/"
        if os.path.exists("/media/hdd/"): hdd_path = "/media/hdd/simplysports/logos/"
        elif os.path.exists("/hdd/"): hdd_path = "/hdd/simplysports/logos/"
        elif os.path.exists("/media/usb/"): hdd_path = "/media/usb/simplysports/logos/"
        else: hdd_path = "/tmp/simplysports/logos/"

        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        tom_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        for event in events:
            status = event.get('status', {})
            state = status.get('type', {}).get('state', 'pre')
            clock = status.get('displayClock', '00:00')
            if ":" in clock: clock = clock.split(':')[0] + "'"
            
            local_time = get_local_time_str(event.get('date', ''))
            league_name = event.get('league_name', '')
            
            mode = global_sports_monitor.filter_mode
            ev_date = event.get('date', '')[:10]
            if mode == 0 and state != 'in': continue
            if mode == 2 and ev_date != today_str: continue
            if mode == 3 and ev_date != tom_str: continue

            h_url = event.get('h_logo_url', '')
            a_url = event.get('a_logo_url', '')
            try: h_id = h_url.split('500/')[-1].split('.png')[0]
            except: h_id = '0'
            try: a_id = a_url.split('500/')[-1].split('.png')[0]
            except: a_id = '0'
            
            h_png = hdd_path + h_id + ".png"
            if not os.path.exists(h_png) or os.path.getsize(h_png) == 0:
                h_png = tmp_path + h_id + ".png"
                if not os.path.exists(h_png) or os.path.getsize(h_png) == 0: h_png = None
            
            a_png = hdd_path + a_id + ".png"
            if not os.path.exists(a_png) or os.path.getsize(a_png) == 0:
                a_png = tmp_path + a_id + ".png"
                if not os.path.exists(a_png) or os.path.getsize(a_png) == 0: a_png = None

            comps = event.get('competitions', [{}])[0].get('competitors', [])
            
            if len(comps) > 2:
                race = event.get('shortName', 'Event')
                venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                match_data = {'league': league_name, 'color': 0xffffff, 'home': race, 'away': venue, 'score': "VS", 'status': "SCH", 'time': local_time, 'h_png': None, 'a_png': None}
            else:
                home, away, h_score, a_score = "Home", "Away", "0", "0"
                h_team_id, a_team_id = "0", "0"
                for team in comps:
                    name = team.get('team', {}).get('displayName', 'Team')
                    sc = team.get('score', '0')
                    tid = team.get('team', {}).get('id', '0')
                    if team.get('homeAway') == 'home': home, h_score, h_team_id = name, sc, tid
                    else: away, a_score, a_team_id = name, sc, tid
                
                score_str = "VS"
                status_str = "SCH"
                time_display = local_time
                h_scorers_txt, a_scorers_txt = "", ""
                
                if state == 'in':
                    score_str = "{} - {}".format(h_score, a_score)
                    status_str = "LIVE"
                    time_display = clock
                    h_scorers_txt, a_scorers_txt = self.get_scorers_string(event, h_team_id, a_team_id)
                elif state == 'post':
                    score_str = "{} - {}".format(h_score, a_score)
                    status_str = "FT"
                    h_scorers_txt, a_scorers_txt = self.get_scorers_string(event, h_team_id, a_team_id)
                
                final_home_txt = home
                if h_scorers_txt: final_home_txt = "({})  {}".format(h_scorers_txt, home)
                final_away_txt = away
                if a_scorers_txt: final_away_txt = "{}  ({})".format(away, a_scorers_txt)
                
                l_color = 0xffffff
                for key, val in self.league_colors.items():
                    if key in league_name.upper() or key in event.get('shortName', '').upper():
                        l_color = val
                        break

                match_data = {'league': league_name, 'color': l_color, 'home': final_home_txt, 'away': final_away_txt, 'score': score_str, 'status': status_str, 'time': time_display, 'h_png': h_png, 'a_png': a_png}
            self.matches.append(match_data)
        if self.matches:
            if not self.ticker_timer.isActive(): 
                self.show_next_match()
                self.ticker_timer.start(5000)

    def show_next_match(self):
        if not self.matches: return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matches)
        data = self.matches[self.current_match_idx]
        
        self["lbl_league"].setText(str(data.get('league', '')))
        # CRASH FIX: Wrap color integer in gRGB
        try:
            self["lbl_league"].instance.setForegroundColor(gRGB(data.get('color', 0xffffff)))
        except: pass
        
        self["lbl_home"].setText(str(data.get('home', '')))
        self["lbl_score"].setText(str(data.get('score', '')))
        self["lbl_away"].setText(str(data.get('away', '')))
        self["lbl_status"].setText(str(data.get('status', '')))
        self["lbl_time"].setText(str(data.get('time', '')))
        
        if data.get('h_png'):
            self["h_logo"].instance.setPixmapFromFile(data['h_png'])
            self["h_logo"].show()
        else: self["h_logo"].hide()

        if data.get('a_png'):
            self["a_logo"].instance.setPixmapFromFile(data['a_png'])
            self["a_logo"].show()
        else: self["a_logo"].hide()


# ==============================================================================
# MINI BAR 1 (Top Left)
# ==============================================================================
class SimpleSportsMiniBar(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        
        if global_sports_monitor.theme_mode == "ucl":
            # UPDATED SKIN: Widened Score Box (160 -> 200)
            self.skin = """
            <screen position="40,10" size="900,90" title="Sports Ticker" backgroundColor="#40000000" flags="wfNoBorder">
                <widget name="lbl_league" position="0,0" size="900,20" font="Regular;16" foregroundColor="#00ffff" transparent="1" halign="center" valign="center" zPosition="2" />
                <eLabel position="0,20" size="900,70" backgroundColor="#0e1e5b" zPosition="0" />
                
                <eLabel position="350,20" size="200,70" backgroundColor="#ffffff" zPosition="1" />
                
                <widget name="h_logo" position="10,35" size="50,50" alphatest="blend" zPosition="2" />
                <widget name="lbl_home" position="50,35" size="290,50" font="Regular;24" foregroundColor="#ffffff" backgroundColor="#0e1e5b" transparent="1" halign="right" valign="center" zPosition="2" />
                
                <widget name="lbl_score" position="350,30" size="200,35" font="Regular;30" foregroundColor="#0e1e5b" backgroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="3" />
                <widget name="lbl_status" position="350,65" size="200,20" font="Regular;18" foregroundColor="#0e1e5b" backgroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="3" />
                
                <widget name="lbl_away" position="560,35" size="290,50" font="Regular;24" foregroundColor="#ffffff" backgroundColor="#0e1e5b" transparent="1" halign="left" valign="center" zPosition="2" />
                <widget name="a_logo" position="840,35" size="50,50" alphatest="blend" zPosition="2" />
            </screen>
            """
        else:
            self.skin = """
                <screen position="40,10" size="900,100" title="Sports Ticker" backgroundColor="#40000000" flags="wfNoBorder">
                    <widget name="lbl_league" position="0,0" size="900,30" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#E6000000" transparent="0" halign="center" valign="center" />
                    <eLabel position="0,30" size="5,70" backgroundColor="#E90052" zPosition="1" /> 
                    <eLabel position="5,30" size="375,70" backgroundColor="#33190028" zPosition="1" />
                    <widget name="h_logo" position="15,35" size="60,60" alphatest="blend" zPosition="2" />
                    <widget name="lbl_home" position="80,30" size="290,70" font="Regular;26" foregroundColor="#FFFFFF" backgroundColor="#33190028" transparent="1" halign="right" valign="center" zPosition="2" />
                    
                    <eLabel position="380,30" size="140,70" backgroundColor="#00FF85" zPosition="1" /> 
                    <widget name="lbl_score" position="380,30" size="140,40" font="Regular;34" foregroundColor="#000000" backgroundColor="#00FF85" transparent="1" halign="center" valign="center" zPosition="2" />
                    <eLabel position="380,70" size="140,30" backgroundColor="#FFFFFF" zPosition="2" />
                    <widget name="lbl_status" position="380,70" size="140,30" font="Regular;24" foregroundColor="#000000" backgroundColor="#FFFFFF" transparent="1" halign="center" valign="center" zPosition="3" />
                    
                    <eLabel position="520,30" size="375,70" backgroundColor="#33190028" zPosition="1" /> 
                    <widget name="lbl_away" position="530,30" size="290,70" font="Regular;26" foregroundColor="#FFFFFF" backgroundColor="#33190028" transparent="1" halign="left" valign="center" zPosition="2" />
                    <widget name="a_logo" position="825,35" size="60,60" alphatest="blend" zPosition="2" />
                    <eLabel position="895,30" size="5,70" backgroundColor="#F6B900" zPosition="1" /> 
                </screen>
            """

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
        safe_connect(self.refresh_timer, self.load_data)
        
        self.onLayoutFinish.append(self.start_all_timers)

    def switch_to_bottom(self):
        self.close("next")

    def start_all_timers(self):
        self.load_data()
        self.refresh_timer.start(60000)

    def toggle_filter_mini(self): 
        global_sports_monitor.toggle_filter()
        self.load_data()
            
    def load_data(self): 
        global_sports_monitor.check_goals()
        self.parse_json()

    def parse_json(self):
        events = global_sports_monitor.cached_events
        self.matches = []
        if not events:
            self.matches.append({'league': "SimplySports", 'home': global_sports_monitor.status_message, 'away': "", 'score': "", 'status': "", 'h_png': None, 'a_png': None})
            return
        tmp_path = "/tmp/simplysports/logos/"
        if os.path.exists("/media/hdd/"): hdd_path = "/media/hdd/simplysports/logos/"
        elif os.path.exists("/hdd/"): hdd_path = "/hdd/simplysports/logos/"
        elif os.path.exists("/media/usb/"): hdd_path = "/media/usb/simplysports/logos/"
        else: hdd_path = "/tmp/simplysports/logos/"
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        tom_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        for event in events:
            status = event.get('status', {})
            state = status.get('type', {}).get('state', 'pre')
            clock = status.get('displayClock', '00:00')
            local_time = get_local_time_str(event.get('date', ''))
            league_name = event.get('league_name', '')
            mode = global_sports_monitor.filter_mode
            ev_date = event.get('date', '')[:10]
            if mode == 0 and state != 'in': continue
            if mode == 2 and ev_date != today_str: continue
            if mode == 3 and ev_date != tom_str: continue
            h_url = event.get('h_logo_url', '')
            a_url = event.get('a_logo_url', '')
            try: h_id = h_url.split('500/')[-1].split('.png')[0]
            except: h_id = '0'
            try: a_id = a_url.split('500/')[-1].split('.png')[0]
            except: a_id = '0'
            h_png = hdd_path + h_id + ".png"
            if not os.path.exists(h_png) or os.path.getsize(h_png) == 0:
                h_png = tmp_path + h_id + ".png"
                if not os.path.exists(h_png) or os.path.getsize(h_png) == 0: h_png = None
            a_png = hdd_path + a_id + ".png"
            if not os.path.exists(a_png) or os.path.getsize(a_png) == 0:
                a_png = tmp_path + a_id + ".png"
                if not os.path.exists(a_png) or os.path.getsize(a_png) == 0: a_png = None
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            if len(comps) > 2:
                race = event.get('shortName', 'Event')
                venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                match_data = {'league': league_name, 'home': race, 'away': venue, 'score': "VS", 'status': "SCH", 'h_png': None, 'a_png': None}
            else:
                home, away, h_score, a_score = "Home", "Away", "0", "0"
                for team in comps:
                    name = team.get('team', {}).get('displayName', 'Team')
                    sc = team.get('score', '0')
                    if team.get('homeAway') == 'home': home, h_score = name, sc
                    else: away, a_score = name, sc
                score_str = "VS"
                status_str = "SCH"
                if state == 'in':
                    score_str = "{} - {}".format(h_score, a_score)
                    status_str = clock + "'" if ":" not in clock else clock
                elif state == 'post':
                    score_str = "{} - {}".format(h_score, a_score)
                    status_str = "FT"
                match_data = {'league': league_name, 'home': home, 'away': away, 'score': score_str, 'status': status_str, 'h_png': h_png, 'a_png': a_png}
            self.matches.append(match_data)
        if self.matches:
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
        if data.get('h_png'):
            self["h_logo"].instance.setPixmapFromFile(data['h_png'])
            self["h_logo"].show()
        else: self["h_logo"].hide()
        if data.get('a_png'):
            self["a_logo"].instance.setPixmapFromFile(data['a_png'])
            self["a_logo"].show()
        else: self["a_logo"].hide()



# ==============================================================================
# MAIN GUI (OPTIMIZED)
# ==============================================================================
class SimpleSportsScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        global_sports_monitor.set_session(session)
        self.monitor = global_sports_monitor
        self.monitor.register_callback(self.refresh_ui)
        
        # ======================================================================
        # SKINS (UCL.JPG PRIORITY)
        # ======================================================================
        
        # --- HEADER ALIGNMENT GRID (Must match ListEntry) ---
        # Status: 20
        # League: 100
        # Home: 190 (Width 300)
        # Score: 580 (Center)
        # Away: 790 (Width 300)
        # Time: 1090 (Width 170)

        if self.monitor.theme_mode == "ucl":
            # --- UCL THEME (Blue/Cyan) ---
            bg_color = "#A60e1e5b" 
            
            # Default to color
            bg_element = '<eLabel position="0,0" size="1280,860" backgroundColor="{}" zPosition="-1" />'.format(bg_color)
            
            # Check for Images (JPG Priority)
            try:
                path_jpg = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/ucl.jpg")
                path_png = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/ucl.png")
                
                if os.path.exists(path_jpg):
                    bg_element = '<ePixmap position="0,0" size="1280,860" pixmap="{}" zPosition="-1" alphatest="on" />'.format(path_jpg)
                elif os.path.exists(path_png):
                    bg_element = '<ePixmap position="0,0" size="1280,860" pixmap="{}" zPosition="-1" alphatest="on" />'.format(path_png)
            except: pass

            self.skin = """
            <screen position="center,center" size="1280,860" title="SimplySports" flags="wfNoBorder" backgroundColor="#00000000">
                {bg}
                <eLabel position="0,0" size="1280,100" backgroundColor="#A6050a2e" zPosition="0" />
                
                <widget name="top_title" position="0,10" size="1280,60" font="Regular;46" foregroundColor="#00ffff" backgroundColor="#050a2e" transparent="1" halign="center" valign="center" zPosition="2" shadowColor="#000000" shadowOffset="-3,-3" />
                <widget name="key_epg" position="40,15" size="300,30" font="Regular;22" foregroundColor="#ffffff" backgroundColor="#050a2e" transparent="1" halign="left" zPosition="2" />
                <widget name="key_menu" position="40,45" size="300,30" font="Regular;22" foregroundColor="#aaaaaa" backgroundColor="#050a2e" transparent="1" halign="left" zPosition="2" />
                <widget name="credit" position="940,25" size="300,30" font="Regular;20" foregroundColor="#00ffff" backgroundColor="#050a2e" transparent="1" halign="right" zPosition="2" />

                <widget name="league_title" position="50,80" size="500,35" font="Regular;26" foregroundColor="#ffffff" backgroundColor="#A60e1e5b" transparent="1" halign="left" zPosition="1" />
                <widget name="list_title" position="0,80" size="1280,35" font="Regular;26" foregroundColor="#00ffff" backgroundColor="#A60e1e5b" transparent="1" halign="center" zPosition="1" />
                
                <eLabel position="0,120" size="1280,40" backgroundColor="#A60e1e5b" zPosition="0" />
                <widget name="head_status" position="20,125" size="70,30" font="Regular;20" foregroundColor="#00ffff" backgroundColor="#0e1e5b" transparent="1" halign="center" zPosition="1" />
                <widget name="head_league" position="100,125" size="80,30" font="Regular;20" foregroundColor="#00ffff" backgroundColor="#0e1e5b" transparent="1" halign="center" zPosition="1" />
                <widget name="head_home" position="190,125" size="300,30" font="Regular;20" foregroundColor="#00ffff" backgroundColor="#0e1e5b" transparent="1" halign="right" zPosition="1" />
                <widget name="head_score" position="580,125" size="120,30" font="Regular;20" foregroundColor="#00ffff" backgroundColor="#0e1e5b" transparent="1" halign="center" zPosition="1" />
                <widget name="head_away" position="790,125" size="300,30" font="Regular;20" foregroundColor="#00ffff" backgroundColor="#0e1e5b" transparent="1" halign="left" zPosition="1" />
                <widget name="head_time" position="1090,125" size="170,30" font="Regular;20" foregroundColor="#00ffff" backgroundColor="#0e1e5b" transparent="1" halign="right" zPosition="1" />
                
                <widget name="list" position="0,170" size="1280,590" scrollbarMode="showOnDemand" transparent="1" zPosition="1" />
                
                <eLabel position="0,770" size="1280,90" backgroundColor="#A6050a2e" zPosition="0" />
                <widget name="key_red" position="40,785" size="280,60" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#F44336" transparent="0" zPosition="2" halign="center" valign="center" />
                <widget name="key_green" position="340,785" size="280,60" font="Regular;24" foregroundColor="#000000" backgroundColor="#00FF85" transparent="0" zPosition="2" halign="center" valign="center" />
                <widget name="key_yellow" position="640,785" size="280,60" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#FFA000" transparent="0" zPosition="2" halign="center" valign="center" />
                <widget name="key_blue" position="940,785" size="300,60" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#42A5F5" transparent="0" zPosition="2" halign="center" valign="center" />
            </screen>
            """.format(bg=bg_element)
        else:
            # --- DEFAULT THEME (Purple/Green) ---
            self.skin = """
            <screen position="center,center" size="1280,860" title="SimplySports" flags="wfNoBorder" backgroundColor="#00000000">
                <eLabel position="0,0" size="1280,860" backgroundColor="#A6100015" zPosition="-1" />
                <eLabel position="0,0" size="1280,100" backgroundColor="#A6100015" zPosition="0" />
                
                <widget name="top_title" position="0,10" size="1280,60" font="Regular;46" foregroundColor="#00FF85" backgroundColor="#100015" transparent="1" halign="center" valign="center" zPosition="2" shadowColor="#000000" shadowOffset="-3,-3" />
                <widget name="key_epg" position="40,15" size="300,30" font="Regular;22" foregroundColor="#ffffff" backgroundColor="#100015" transparent="1" halign="left" zPosition="2" />
                <widget name="key_menu" position="40,45" size="300,30" font="Regular;22" foregroundColor="#bbbbbb" backgroundColor="#100015" transparent="1" halign="left" zPosition="2" />
                <widget name="credit" position="940,25" size="300,30" font="Regular;20" foregroundColor="#888888" backgroundColor="#100015" transparent="1" halign="right" zPosition="2" />

                <eLabel position="0,70" size="1280,40" backgroundColor="#A638003C" zPosition="0" />
                <widget name="league_title" position="50,75" size="500,35" font="Regular;28" foregroundColor="#FFFFFF" backgroundColor="#38003C" transparent="1" halign="left" zPosition="1" />
                <widget name="list_title" position="0,75" size="1280,35" font="Regular;28" foregroundColor="#00FF85" backgroundColor="#38003C" transparent="1" halign="center" zPosition="1" />
                
                <eLabel position="0,110" size="1280,45" backgroundColor="#A6100015" zPosition="0" />
                <widget name="head_status" position="20,115" size="70,35" font="Regular;20" foregroundColor="#00FF85" backgroundColor="#100015" transparent="1" halign="center" valign="center" zPosition="1" />
                <widget name="head_league" position="100,115" size="80,35" font="Regular;20" foregroundColor="#00FF85" backgroundColor="#100015" transparent="1" halign="center" valign="center" zPosition="1" />
                <widget name="head_home" position="190,115" size="300,35" font="Regular;20" foregroundColor="#00FF85" backgroundColor="#100015" transparent="1" halign="right" valign="center" zPosition="1" />
                <widget name="head_score" position="580,115" size="120,35" font="Regular;20" foregroundColor="#00FF85" backgroundColor="#100015" transparent="1" halign="center" valign="center" zPosition="1" />
                <widget name="head_away" position="790,115" size="300,35" font="Regular;20" foregroundColor="#00FF85" backgroundColor="#100015" transparent="1" halign="left" valign="center" zPosition="1" />
                <widget name="head_time" position="1090,115" size="170,35" font="Regular;20" foregroundColor="#00FF85" backgroundColor="#100015" transparent="1" halign="right" valign="center" zPosition="1" />
                
                <eLabel position="0,158" size="1280,2" backgroundColor="#00FF85" zPosition="1" />
                <widget name="list" position="0,170" size="1280,590" scrollbarMode="showOnDemand" transparent="1" zPosition="1" />
                
                <eLabel position="0,770" size="1280,90" backgroundColor="#A6100015" zPosition="0" />
                <eLabel position="0,770" size="1280,2" backgroundColor="#505050" zPosition="1" />
                
                <widget name="key_red" position="40,785" size="280,60" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#F44336" transparent="0" zPosition="2" halign="center" valign="center" />
                <widget name="key_green" position="340,785" size="280,60" font="Regular;24" foregroundColor="#000000" backgroundColor="#00FF85" transparent="0" zPosition="2" halign="center" valign="center" />
                <widget name="key_yellow" position="640,785" size="280,60" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#FFA000" transparent="0" zPosition="2" halign="center" valign="center" />
                <widget name="key_blue" position="940,785" size="300,60" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#42A5F5" transparent="0" zPosition="2" halign="center" valign="center" />
            </screen>
            """
        
        self.logo_timer = eTimer()
        try: self.logo_timer.callback.append(lambda: self.refresh_ui(True))
        except AttributeError: self.logo_timer.timeout.get().append(lambda: self.refresh_ui(True))
        self.logo_timer.start(5000, False) 
        
        self.path_cache = {} 
        self.download_queue = []          
        self.is_downloading = False       
        self.current_download_key = None
        
        self.container = eConsoleAppContainer()
        self.container.appClosed.append(self.download_finished)
        
        self.tmp_path = "/tmp/simplysports/logos/"
        if os.path.exists("/media/hdd/"): self.hdd_path = "/media/hdd/simplysports/logos/"
        elif os.path.exists("/hdd/"): self.hdd_path = "/hdd/simplysports/logos/"
        elif os.path.exists("/media/usb/"): self.hdd_path = "/media/usb/simplysports/logos/"
        else: self.hdd_path = "/tmp/simplysports/logos/"
            
        for path in [self.tmp_path, self.hdd_path]:
            if not os.path.exists(path):
                try: os.makedirs(path)
                except: pass
        
        self["top_title"] = Label("SimplySports Score Center")
        self["league_title"] = Label("LOADING...")
        self["list_title"] = Label("")
        self["credit"] = Label("reali22 (v" + CURRENT_VERSION + ")")
        
        self["key_epg"] = Label("EPG: Theme")
        self["key_menu"] = Label("MENU: Update")
        
        self["head_status"] = Label("STAT")
        self["head_league"] = Label("LGE")
        self["head_home"] = Label("HOME")
        self["head_score"] = Label("SCORE")
        self["head_away"] = Label("AWAY")
        self["head_time"] = Label("TIME")
        
        # --- FONT DEFINITIONS (Including Font 3 for Time) ---
        self["list"] = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
        self["list"].l.setFont(0, gFont("Regular", 26)) 
        self["list"].l.setFont(1, gFont("Regular", 30)) 
        self["list"].l.setFont(2, gFont("Bold", 32))    
        self["list"].l.setFont(3, gFont("Regular", 20)) # Small Time Font
        self["list"].l.setItemHeight(75) 
        
        self["key_red"] = Label("League Menu")
        self["key_green"] = Label("Mini Bar")
        self["key_yellow"] = Label("Live Only")
        self["key_blue"] = Label("Goal Alert: OFF")
        
        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions", "DirectionActions", "MenuActions", "EPGSelectActions"], 
            {
                "cancel": self.close,
                "red": self.open_league_menu,
                "green": self.open_mini_bar,
                "yellow": self.toggle_filter,
                "blue": self.toggle_discovery,
                "ok": self.open_game_info,
                "menu": self.check_for_updates,
                "epg": self.open_theme_selector,   
                "info": self.open_theme_selector,
                "up": self["list"].up,
                "down": self["list"].down,
            }, -1
        )
        
        self.auto_refresh_timer = eTimer()
        try: self.auto_refresh_timer.callback.append(self.fetch_data)
        except AttributeError: self.auto_refresh_timer.timeout.get().append(self.fetch_data)
            
        self.onLayoutFinish.append(self.start_ui)
        self.onClose.append(self.cleanup)

    def start_ui(self):
        self.update_header()
        self.update_filter_button()
        self.fetch_data()
        self.auto_refresh_timer.start(120000)
        
    def cleanup(self): 
        self.monitor.unregister_callback(self.refresh_ui)

    def open_theme_selector(self):
        menu_list = [("SimplySports Default (Purple/Green)", "default"), ("UEFA Champions League (Blue/Cyan)", "ucl")]
        self.session.openWithCallback(self.theme_selected, ChoiceBox, title="Select Interface Theme", list=menu_list)

    def theme_selected(self, selection):
        if selection:
            new_theme = selection[1]
            if new_theme != self.monitor.theme_mode:
                self.monitor.theme_mode = new_theme
                self.monitor.save_config()
                self.session.open(MessageBox, "Theme changed. Reloading...", MessageBox.TYPE_INFO, timeout=2)
                self.close()
                self.session.open(SimpleSportsScreen)

    def update_header(self):
        if self.monitor.is_custom_mode:
             self["league_title"].setText("Custom League View")
        else:
            try: 
                item = DATA_SOURCES[self.monitor.current_league_index]
                self["league_title"].setText(item[0])
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
            
    def fetch_data(self): 
        self.monitor.check_goals()
        
    def get_logo_path(self, url, filename):
        if not url: return None
        if filename in self.path_cache: return self.path_cache[filename]
        file_png = filename + ".png"
        target_tmp = self.tmp_path + file_png
        target_hdd = self.hdd_path + file_png
        final_path = None
        if os.path.exists(target_hdd) and os.path.getsize(target_hdd) > 0: final_path = target_hdd
        elif os.path.exists(target_tmp) and os.path.getsize(target_tmp) > 0: final_path = target_tmp
        else:
            self.queue_download(url, target_tmp, target_hdd, filename)
            return None
        if final_path:
            self.path_cache[filename] = final_path
            return final_path
        return None

    def queue_download(self, url, tmp_path, hdd_path, filename):
        for q in self.download_queue:
            if q[3] == filename: return
        if self.current_download_key == filename: return
        self.download_queue.append((url, tmp_path, hdd_path, filename))
        self.process_queue()

    def process_queue(self):
        if self.is_downloading or not self.download_queue: return
        url, tmp_path, hdd_path, filename = self.download_queue.pop(0)
        self.is_downloading = True
        self.current_download_key = filename
        cmd = 'wget -U "Mozilla/5.0" --no-check-certificate -q -O "{}" "{}" && cp -f "{}" "{}"'.format(tmp_path, url, tmp_path, hdd_path)
        self.container.execute(cmd)

    def download_finished(self, retval):
        self.is_downloading = False
        self.current_download_key = None
        self.process_queue()

    def toggle_discovery(self):
        new_mode = self.monitor.cycle_discovery_mode()
        self.update_header()
        
        if new_mode == 0: self.session.open(MessageBox, "Goal Alerts OFF", MessageBox.TYPE_INFO, timeout=2)
        elif new_mode == 1: self.session.open(MessageBox, "Goal Alerts: VISUAL ONLY", MessageBox.TYPE_INFO, timeout=2)
        elif new_mode == 2: self.session.open(MessageBox, "Goal Alerts: VISUAL + SOUND", MessageBox.TYPE_INFO, timeout=2)

    def toggle_filter(self): 
        self.monitor.toggle_filter()
        self.update_filter_button()
        self.refresh_ui(True)

    def open_league_menu(self):
        options = [("Select Single League", "single"), ("Configure Custom Leagues", "custom_config")]
        if self.monitor.custom_league_indices: options.append(("View Custom Leagues", "view_custom"))
        self.session.openWithCallback(self.league_menu_callback, ChoiceBox, title="League Options", list=options)

    def league_menu_callback(self, selection):
        if selection:
            if selection[1] == "single": self.open_single_league_select()
            elif selection[1] == "custom_config": self.session.openWithCallback(self.on_selector_closed, LeagueSelector)
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
        for idx, item in enumerate(DATA_SOURCES): options.append((item[0], idx))
        self.session.openWithCallback(self.single_league_selected, ChoiceBox, title="Select Single League", list=options)

    def single_league_selected(self, selection):
        if selection:
            self.monitor.set_league(selection[1])
            self.update_header()
            self.fetch_data()

    def open_mini_bar(self): 
        self.session.openWithCallback(self.mini_bar_callback, SimpleSportsMiniBar)

    def mini_bar_callback(self, result=None):
        if result == "next":
            self.session.open(SimpleSportsMiniBar2)

    def open_game_info(self):
        idx = self["list"].getSelectedIndex()
        if idx is None or not self.monitor.cached_events: return
        
        events = []
        for event in self.monitor.cached_events:
            status = event.get('status', {})
            state = status.get('type', {}).get('state', 'pre')
            ev_date = event.get('date', '')[:10]
            mode = self.monitor.filter_mode
            if mode == 0 and state != 'in': continue
            if mode == 2:
                now = datetime.datetime.now()
                if ev_date != now.strftime("%Y-%m-%d"): continue
            if mode == 3:
                 now = datetime.datetime.now()
                 tom = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                 if ev_date != tom: continue
            events.append(event)
            
        if 0 <= idx < len(events):
            selected_event = events[idx]
            status = selected_event.get('status', {})
            state = status.get('type', {}).get('state', 'pre')
            
            if state == 'pre':
                self.selected_event_for_reminder = selected_event
                options = [("Remind me 3 hours before", 180), ("Remind me 1 hour before", 60), ("Remind me 5 minutes before", 5), ("Delete Reminder", -1), ("Cancel", 0)]
                self.session.openWithCallback(self.reminder_selected, ChoiceBox, title="Set Game Reminder", list=options)
            else:
                event_id = selected_event.get('id')
                league_name = selected_event.get('league_name', '')
                url = ""
                for item in DATA_SOURCES:
                    if item[0] == league_name:
                        url = item[1]
                        break
                if not url:
                    try: 
                        item = DATA_SOURCES[self.monitor.current_league_index]
                        url = item[1]
                    except: pass
                if event_id and url: self.session.open(GameInfoScreen, event_id, url)

    def reminder_selected(self, selection):
        if not selection or selection[1] == 0: return
        val = selection[1]
        event = self.selected_event_for_reminder
        
        try:
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            home = "Home"
            away = "Away"
            for team in comps:
                name = team.get('team', {}).get('displayName', 'Team')
                if team.get('homeAway') == 'home': home = name
                else: away = name
            match_name = home + " vs " + away

            if val == -1:
                if self.monitor.remove_reminder(match_name):
                    self.session.open(MessageBox, "Reminder removed.", MessageBox.TYPE_INFO, timeout=2)
                else:
                    self.session.open(MessageBox, "No active reminder found.", MessageBox.TYPE_ERROR, timeout=2)
                return

            date_str = event.get('date', '')
            y, m, d = map(int, date_str.split('T')[0].split('-'))
            time_part = date_str.split('T')[1].replace('Z','')
            h, mn = map(int, time_part.split(':')[:2])
            dt_utc = datetime.datetime(y, m, d, h, mn)
            start_timestamp = calendar.timegm(dt_utc.timetuple())
            trigger_time = start_timestamp - (val * 60)
            
            label = "Starts in {} Mins".format(val)
            if val == 60: label = "Starts in 1 Hour"
            elif val == 180: label = "Starts in 3 Hours"
            
            league_name = event.get('league_name', '')
            h_logo = event.get('h_logo_url', '')
            a_logo = event.get('a_logo_url', '')
            
            self.monitor.add_reminder(match_name, trigger_time, league_name, h_logo, a_logo, label)
            self.session.open(MessageBox, "Reminder set!", MessageBox.TYPE_INFO, timeout=2)
        except: pass

    def check_for_updates(self): 
        self["league_title"].setText("CHECKING FOR UPDATES...")
        url = GITHUB_BASE_URL + "version.txt"
        getPage(url.encode('utf-8')).addCallback(self.got_version).addErrback(self.update_fail)
        
    def got_version(self, data):
        try:
            remote = data.decode('utf-8').strip()
            if remote > CURRENT_VERSION: 
                self.session.openWithCallback(self.start_update, MessageBox, "Update available: " + remote + "\nUpdate now?", MessageBox.TYPE_YESNO)
            else: 
                self.session.open(MessageBox, "Latest version installed!", MessageBox.TYPE_INFO, timeout=3)
                self.update_header()
        except: self.update_fail(None)
            
    def update_fail(self, error): 
        self.session.open(MessageBox, "Update check failed.", MessageBox.TYPE_ERROR, timeout=3)
        self.update_header()
        
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

    def final_update_success(self, data): 
        self.session.open(MessageBox, "Update success! Restart GUI.", MessageBox.TYPE_INFO)

    def refresh_ui(self, success):
        self.update_header()
        events = self.monitor.cached_events
        if not events:
            dummy_entry = ("INFO", "", "No Live Games", "", "", "", False, "", None, None, 0, 0)
            if self.monitor.theme_mode == "ucl": self["list"].setList([UCLListEntry(dummy_entry)])
            else: self["list"].setList([SportListEntry(dummy_entry)])
            return
        
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        tom_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        list_content = []
        for event in events:
            try:
                status = event.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                clock = status.get('displayClock', '')
                if ":" in clock: clock = clock.split(':')[0] + "'"
                local_time = get_local_time_str(event.get('date', ''))
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                league_prefix = event.get('league_name', '')
                h_url = event.get('h_logo_url', '')
                a_url = event.get('a_logo_url', '')
                try: h_id = h_url.split('500/')[-1].split('.png')[0]
                except: h_id = '0'
                try: a_id = a_url.split('500/')[-1].split('.png')[0]
                except: a_id = '0'
                h_png = self.get_logo_path(h_url, h_id)
                a_png = self.get_logo_path(a_url, a_id)
                
                is_live = False
                display_time = local_time
                h_score_int = 0
                a_score_int = 0
                
                if len(comps) > 2:
                    left_text = event.get('shortName', 'Race')
                    right_text = "Event"
                    score_text = ""
                    goal_side = None
                    if state == 'in': 
                        score_text = "LIVE"
                        is_live = True
                    elif state == 'post': score_text = "FIN"
                else:
                    home, away, h_score, a_score = "Home", "Away", "0", "0"
                    
                    team_h = next((t for t in comps if t.get('homeAway') == 'home'), None)
                    if not team_h and len(comps) > 0: team_h = comps[0]
                    
                    team_a = next((t for t in comps if t.get('homeAway') == 'away'), None)
                    if not team_a and len(comps) > 1: team_a = comps[1]

                    if team_h:
                        home = team_h.get('team', {}).get('shortDisplayName') or team_h.get('team', {}).get('displayName') or "Home"
                        h_score = team_h.get('score', '0')
                    
                    if team_a:
                        away = team_a.get('team', {}).get('shortDisplayName') or team_a.get('team', {}).get('displayName') or "Away"
                        a_score = team_a.get('score', '0')

                    left_text = home
                    right_text = away
                    score_text = str(h_score) + " - " + str(a_score) if state != 'pre' else "vs"
                    
                    try: h_score_int = int(h_score)
                    except: h_score_int = 0
                    try: a_score_int = int(a_score)
                    except: a_score_int = 0
                    
                    if state == 'in': 
                        is_live = True
                        display_time = clock
                    
                    match_id = home + "_" + away
                    goal_side = self.monitor.goal_flags[match_id]['side'] if match_id in self.monitor.goal_flags else None

                status_short = "SCH"
                if state == 'in': status_short = "LIVE"
                elif state == 'post': status_short = "FIN"
                
                mode = self.monitor.filter_mode
                ev_date = event.get('date', '')[:10]
                if mode == 0 and state != 'in': continue
                if mode == 2 and ev_date != today_str: continue
                if mode == 3 and ev_date != tom_str: continue

                entry_data = (status_short, get_league_abbr(league_prefix), str(left_text), str(score_text), str(right_text), str(display_time), goal_side, is_live, h_png, a_png, h_score_int, a_score_int)
                
                if self.monitor.theme_mode == "ucl": list_content.append(UCLListEntry(entry_data))
                else: list_content.append(SportListEntry(entry_data))
            except Exception as e: continue
            
        if not list_content: 
            dummy_entry = ("INFO", "", "No Live Games", "", "", "", False, "", None, None, 0, 0)
            if self.monitor.theme_mode == "ucl": self["list"].setList([UCLListEntry(dummy_entry)])
            else: self["list"].setList([SportListEntry(dummy_entry)])
        else: self["list"].setList(list_content)

def main(session, **kwargs): 
    session.open(SimpleSportsScreen)
    
def Plugins(**kwargs):
    iconPath = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/picon.png")
    return [
        PluginDescriptor(name="SimplySports", description="Live Sports Scores & Alerts by reali22", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main, icon=iconPath),
        PluginDescriptor(name="SimplySports Monitor", where=PluginDescriptor.WHERE_SESSIONSTART, fnc=lambda session, **kwargs: global_sports_monitor.set_session(session))
    ]
