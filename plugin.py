# -*- coding: utf-8 -*-
import shutil
import os
import threading
import time
import ssl
import hashlib
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

# ==============================================================================
# PERFORMANCE PROFILING INTEGRATION (Optional Hook)
# ==============================================================================
try:
    from .performance_profiling import (
        profile_function, 
        ProfileBlock, 
        perf_logger,
        finalize_performance_log
    )
except ImportError:
    # Fallback if the profiling file is missing
    def profile_function(name=None): return lambda x: x
    class ProfileBlock:
        def __init__(self, *a, **k): pass
        def __enter__(self): pass
        def __exit__(self, *a): pass
    def finalize_performance_log(): pass

try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request

# ==============================================================================
# CONFIGURATION
# ==============================================================================
CURRENT_VERSION = "2.8" # Performance & Optimization Release
GITHUB_BASE_URL = "https://raw.githubusercontent.com/Ahmed-Mohammed-Abbas/SimplySports/main/"
CONFIG_FILE = "/etc/enigma2/simply_sports.json"
LOG_FILE = "/tmp/simplysports.log"
LOGO_CACHE_DIR = "/tmp/simplysports_logos"

# ==============================================================================
# LOGGING UTILITY
# ==============================================================================
def log_message(message, level="INFO"):
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a") as f:
            f.write("[{}] {}: {}\n".format(timestamp, level, message))
    except:
        pass

# ==============================================================================
# DATA SOURCES (FULL LIST)
# ==============================================================================
DATA_SOURCES = [
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
    ("UEFA Champions League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard"),
    ("UEFA Europa League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa/scoreboard"),
    ("UEFA Conference League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa.conf/scoreboard"),
    ("UEFA Women's Champions League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.wchampions/scoreboard"),
    ("UEFA Super Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.super_cup/scoreboard"),
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
    ("La Liga", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard"),
    ("La Liga 2", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.2/scoreboard"),
    ("Copa del Rey", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.copa_del_rey/scoreboard"),
    ("Spanish Supercopa", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.super_cup/scoreboard"),
    ("Liga F (Women)", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.w.1/scoreboard"),
    ("Copa de la Reina", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.copa_de_la_reina/scoreboard"),
    ("Serie A", "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard"),
    ("Serie B", "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.2/scoreboard"),
    ("Coppa Italia", "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.coppa_italia/scoreboard"),
    ("Italian Supercoppa", "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.super_cup/scoreboard"),
    ("Bundesliga", "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.1/scoreboard"),
    ("2. Bundesliga", "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.2/scoreboard"),
    ("3. Liga", "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.3/scoreboard"),
    ("DFB Pokal", "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.dfb_pokal/scoreboard"),
    ("German Supercup", "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.super_cup/scoreboard"),
    ("Ligue 1", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.1/scoreboard"),
    ("Ligue 2", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.2/scoreboard"),
    ("Coupe de France", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.coupe_de_france/scoreboard"),
    ("Coupe de la Ligue", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.coupe_de_la_ligue/scoreboard"),
    ("Trophee des Champions", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.trophee_des_champions/scoreboard"),
    ("Premiere Ligue (Women)", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.w.1/scoreboard"),
    ("Eredivisie", "https://site.api.espn.com/apis/site/v2/sports/soccer/ned.1/scoreboard"),
    ("Eerste Divisie", "https://site.api.espn.com/apis/site/v2/sports/soccer/ned.2/scoreboard"),
    ("KNVB Beker", "https://site.api.espn.com/apis/site/v2/sports/soccer/ned.cup/scoreboard"),
    ("Johan Cruyff Shield", "https://site.api.espn.com/apis/site/v2/sports/soccer/ned.supercup/scoreboard"),
    ("Primeira Liga", "https://site.api.espn.com/apis/site/v2/sports/soccer/por.1/scoreboard"),
    ("Liga 2 Portugal", "https://site.api.espn.com/apis/site/v2/sports/soccer/por.2/scoreboard"),
    ("Taca de Portugal", "https://site.api.espn.com/apis/site/v2/sports/soccer/por.taca.portugal/scoreboard"),
    ("Taca de Liga", "https://site.api.espn.com/apis/site/v2/sports/soccer/por.liga_cup/scoreboard"),
    ("Scottish Premiership", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.1/scoreboard"),
    ("Scottish Championship", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.2/scoreboard"),
    ("Scottish League One", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.3/scoreboard"),
    ("Scottish League Two", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.4/scoreboard"),
    ("Scottish Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.tennents/scoreboard"),
    ("Scottish League Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.cis/scoreboard"),
    ("Scottish Challenge Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/sco.challenge/scoreboard"),
    ("Super Lig", "https://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard"),
    ("Turkish Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/tur.cup/scoreboard"),
    ("Belgian Pro League", "https://site.api.espn.com/apis/site/v2/sports/soccer/bel.1/scoreboard"),
    ("Belgian Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/bel.cup/scoreboard"),
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
    ("NBA", "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"),
    ("WNBA", "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"),
    ("NCAA Basket (M)", "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"),
    ("NCAA Basket (W)", "https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard"),
    ("EuroLeague", "https://site.api.espn.com/apis/site/v2/sports/basketball/eurl.euroleague/scoreboard"),
    ("NFL", "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"),
    ("NCAA Football", "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"),
    ("UFL", "https://site.api.espn.com/apis/site/v2/sports/football/ufl/scoreboard"),
    ("MLB", "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"),
    ("NCAA Baseball", "https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/scoreboard"),
    ("NHL", "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"),
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
# LOGO CACHE MANAGER (OPTIMIZED: Non-Blocking)
# ==============================================================================
class LogoCacheManager:
    """Manages local caching of team logos with delayed auto-cleanup"""
    @profile_function("LogoCacheManager")
    def __init__(self):
        self.cache_dir = LOGO_CACHE_DIR
        self._ensure_cache_dir()
        
        # OPTIMIZATION: Run pruning 60 seconds AFTER startup to avoid blocking boot
        self.prune_timer = eTimer()
        try:
            self.prune_timer.callback.append(self._prune_cache)
        except AttributeError:
            self.prune_timer.timeout.get().append(self._prune_cache)
        self.prune_timer.start(60000, True) 

    def _ensure_cache_dir(self):
        try:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)
                log_message("Logo cache directory created", "INFO")
        except Exception as e:
            log_message("Failed to create cache dir: {}".format(str(e)), "ERROR")

    @profile_function("LogoCacheManager")
    def _prune_cache(self, days=7):
        """Delete files older than 'days'"""
        try:
            now = time.time()
            cutoff = now - (days * 86400)
            if not os.path.exists(self.cache_dir): return
            
            # Limit the number of files we check to prevent freezing
            count = 0
            for filename in os.listdir(self.cache_dir):
                if count > 50: break # Only check a batch at a time
                file_path = os.path.join(self.cache_dir, filename)
                if os.path.isfile(file_path):
                    if os.path.getmtime(file_path) < cutoff:
                        os.remove(file_path)
                count += 1
            log_message("Cache pruning completed", "INFO")
        except Exception as e:
            log_message("Cache pruning error: {}".format(str(e)), "WARNING")

# ==============================================================================
# GLOBAL OBJECT
# ==============================================================================
global_sports_monitor = None

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
        timer_obj.callback.append(func)
    else:
        try:
            timer_obj.timeout.get().append(func)
        except AttributeError:
            timer_obj.timeout.append(func)

# ==============================================================================
# LIST RENDERERS
# ==============================================================================
def SportListEntry(entry):
    try:
        if len(entry) >= 12:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int = entry[:12]
        else: return []

        if h_png and (not os.path.exists(h_png) or os.path.getsize(h_png) == 0): h_png = None
        if a_png and (not os.path.exists(a_png) or os.path.getsize(a_png) == 0): a_png = None

        c_text = 0xffffff
        c_dim = 0x999999
        c_accent = 0x00FF85 
        c_live = 0xe74c3c   
        c_box = 0x202020    
        
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
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 190, 0, 300, h, 2, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, left_text, c_h_name, c_h_name))
        if h_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 505, 10, 55, 55, LoadPixmap(h_png)))
        
        if "-" in score_text:
            parts = score_text.split('-')
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 580, 15, 50, 45, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, parts[0].strip(), c_h_score, c_h_score, c_box, c_box))
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 630, 0, 20, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "-", c_dim, c_dim))
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 650, 15, 50, 45, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, parts[1].strip(), c_a_score, c_a_score, c_box, c_box))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 580, 0, 120, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, c_dim, c_dim))

        if a_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 720, 10, 55, 55, LoadPixmap(a_png)))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 790, 0, 300, h, 2, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, c_a_name, c_a_name))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1090, 0, 170, h, 3, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, time_str, c_dim, c_dim))

        if goal_side == 'home': res.append((eListboxPythonMultiContent.TYPE_TEXT, 480, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "<", c_accent, c_accent))
        elif goal_side == 'away': res.append((eListboxPythonMultiContent.TYPE_TEXT, 780, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, ">", c_accent, c_accent))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 72, 1240, 2, 0, RT_HALIGN_CENTER, "", 0x303030, 0x303030))
        return res
    except: return []

def UCLListEntry(entry):
    try:
        if len(entry) >= 12:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int = entry[:12]
        else: return []

        if h_png and (not os.path.exists(h_png) or os.path.getsize(h_png) == 0): h_png = None
        if a_png and (not os.path.exists(a_png) or os.path.getsize(a_png) == 0): a_png = None

        c_text = 0xffffff
        c_dim = 0xaaaaaa
        c_accent = 0x00ffff # Cyan
        c_live = 0xff3333   # Red
        c_box = 0x051030    # Dark Navy
        
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
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 190, 0, 300, h, 2, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, left_text, c_h_name, c_h_name))
        if h_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 505, 10, 55, 55, LoadPixmap(h_png)))
        
        if "-" in score_text:
            parts = score_text.split('-')
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 580, 15, 50, 45, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, parts[0].strip(), c_h_score, c_h_score, c_box, c_box))
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 630, 0, 20, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "-", c_dim, c_dim))
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 650, 15, 50, 45, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, parts[1].strip(), c_a_score, c_a_score, c_box, c_box))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 580, 0, 120, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, c_dim, c_dim))

        if a_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 720, 10, 55, 55, LoadPixmap(a_png)))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 790, 0, 300, h, 2, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, c_a_name, c_a_name))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1090, 0, 170, h, 3, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, time_str, c_dim, c_dim))

        if goal_side == 'home': res.append((eListboxPythonMultiContent.TYPE_TEXT, 480, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "<", c_accent, c_accent))
        elif goal_side == 'away': res.append((eListboxPythonMultiContent.TYPE_TEXT, 780, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, ">", c_accent, c_accent))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 72, 1240, 2, 0, RT_HALIGN_CENTER, "", 0x22182c82, 0x22182c82))
        return res
    except: return []

def InfoListEntry(entry):
    # Entry: (Time, Icon, Text)
    col_text = 0xffffff 
    col_none = None
    return [
        entry,
        # 1. Time
        eListboxPythonMultiContent.TYPE_TEXT,
        0, 0, 100, 40, 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, entry[0], col_text, col_none, 
        # 2. Emoji
        eListboxPythonMultiContent.TYPE_TEXT,
        110, 0, 50, 40, 0, RT_HALIGN_CENTER | RT_VALIGN_CENTER, entry[1], col_text, col_none,
        # 3. Text
        eListboxPythonMultiContent.TYPE_TEXT,
        170, 0, 800, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[2], col_text, col_none
    ]

##def StatsListEntry(label, home_val, away_val, theme_mode):
    #if theme_mode == "ucl":
        #col_label, col_val, col_bg = 0x00ffff, 0xffffff, 0x0e1e5b
    #else:
        #col_label, col_val, col_bg = 0x00FF85, 0xFFFFFF, 0x33190028

    #h_w, l_w, a_w = 400, 400, 400
    #h_x, l_x, a_x = 0, 400, 800
    #res = [None]
    #res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 48, 1200, 2, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, 1))
    #res.append((eListboxPythonMultiContent.TYPE_TEXT, l_x, 0, l_w, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(label).upper(), col_label, col_bg))
    #res.append((eListboxPythonMultiContent.TYPE_TEXT, h_x, 0, h_w-20, 50, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, str(home_val), col_val, col_bg))
    #res.append((eListboxPythonMultiContent.TYPE_TEXT, a_x+20, 0, a_w-20, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(away_val), col_val, col_bg))
    #return res  ###

def SelectionListEntry(name, is_selected):
    check_mark = "[x]" if is_selected else "[ ]"
    col_sel = 0x00FF85 if is_selected else 0x9E9E9E
    text_col = 0xFFFFFF if is_selected else 0x9E9E9E
    res = [(name, is_selected)]
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 5, 40, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, check_mark, col_sel, col_sel, None, None))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 70, 5, 700, 40, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, name, text_col, text_col, None, None))
    return res

# ==============================================================================
# SPORTS MONITOR (FIXED: Stable Sorting)
# ==============================================================================
class SportsMonitor:
    @profile_function("SportsMonitor")
    def __init__(self):
        self.active = False
        self.discovery_mode = 0  
        self.current_league_index = 0
        self.custom_league_indices = []
        self.is_custom_mode = False
        self.last_scores = {}
        self.goal_flags = {}
        self.last_states = {} 
        self.filter_mode = 0 
        self.theme_mode = "default"
        self.transparency = "59"
        
        self.logo_path_cache = {} 
        self.missing_logo_cache = [] 
        self.reminders = [] 
        
        self.timer = eTimer()
        safe_connect(self.timer, self.check_goals)
            
        self.session = None
        self.cached_events = [] 
        self.callbacks = []
        self.status_message = "Initializing..."
        self.notification_queue = []
        self.notification_active = False
        
        self.logo_cache = LogoCacheManager()
        log_message("SportsMonitor initialized", "INFO")
        
        self.load_config()
        
        self.boot_timer = eTimer()
        try: self.boot_timer.callback.append(self.check_goals)
        except AttributeError: self.boot_timer.timeout.get().append(self.check_goals)
        self.boot_timer.start(5000, True)

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
                    self.transparency = data.get("transparency", "59")
                    self.discovery_mode = int(data.get("discovery_mode", 0))
                    self.active = (self.discovery_mode > 0)
                    self.custom_league_indices = data.get("custom_indices", [])
                    self.is_custom_mode = bool(data.get("is_custom_mode", False))
                    self.reminders = data.get("reminders", [])
                    if self.active: self.timer.start(60000, False)
            except: self.defaults()
        else: self.defaults()

    def defaults(self):
        self.filter_mode = 0; self.theme_mode = "default"; self.transparency = "59"
        self.discovery_mode = 0; self.reminders = []

    def save_config(self):
        data = {
            "league_index": self.current_league_index, "filter_mode": self.filter_mode,
            "theme_mode": self.theme_mode, "transparency": self.transparency,
            "discovery_mode": self.discovery_mode, "active": self.active,
            "custom_indices": self.custom_league_indices, "is_custom_mode": self.is_custom_mode,
            "reminders": self.reminders
        }
        try:
            with open(CONFIG_FILE, "w") as f: json.dump(data, f)
        except: pass

    # ... (Helpers omitted for brevity, assuming standard methods exist) ...
    def toggle_theme(self):
        if self.theme_mode == "default": self.theme_mode = "ucl"
        else: self.theme_mode = "default"
        self.save_config(); return self.theme_mode
    def toggle_filter(self):
        self.filter_mode = (self.filter_mode + 1) % 4
        self.save_config(); return self.filter_mode
    def cycle_discovery_mode(self):
        self.discovery_mode = (self.discovery_mode + 1) % 3
        if self.discovery_mode > 0: self.active = True; 
        if not self.timer.isActive(): self.timer.start(60000, False); self.check_goals()
        else: self.active = False; self.timer.stop()
        self.save_config(); return self.discovery_mode
    def toggle_activity(self): return self.cycle_discovery_mode()
    def play_sound(self):
        try:
            mp3_path = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/pop.mp3")
            if os.path.exists(mp3_path): os.system('gst-launch-1.0 playbin uri=file://{} audio-sink="alsasink" > /dev/null 2>&1 &'.format(mp3_path))
        except: pass
    def play_stend_sound(self):
        try:
            mp3_path = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/stend.mp3")
            if os.path.exists(mp3_path): os.system('gst-launch-1.0 playbin uri=file://{} audio-sink="alsasink" > /dev/null 2>&1 &'.format(mp3_path))
        except: pass
    def set_league(self, index):
        self.is_custom_mode = False
        if index >= 0 and index < len(DATA_SOURCES):
            self.current_league_index = index; self.last_scores = {}; self.save_config(); self.check_goals()
    def set_custom_leagues(self, indices):
        self.custom_league_indices = indices; self.is_custom_mode = True; self.last_scores = {}; self.save_config(); self.check_goals()
    def add_reminder(self, match_name, trigger_time, league_name, h_logo, a_logo, label):
        new_rem = {"match": match_name, "trigger": trigger_time, "league": league_name, "h_logo": h_logo, "a_logo": a_logo, "label": label}
        for r in self.reminders:
            if r["match"] == match_name and r["trigger"] == trigger_time: return
        self.reminders.append(new_rem); self.save_config()
    def remove_reminder(self, match_name):
        initial_len = len(self.reminders); self.reminders = [r for r in self.reminders if r["match"] != match_name]
        if len(self.reminders) < initial_len: self.save_config(); return True
        return False
    def check_reminders(self):
        now = time.time(); active_reminders = []; reminders_triggered = False
        for rem in self.reminders:
            if now >= rem["trigger"]:
                self.queue_notification(rem["league"], rem["match"], rem["label"], None, rem["h_logo"], rem["a_logo"])
                self.play_stend_sound(); reminders_triggered = True
            else: active_reminders.append(rem)
        if reminders_triggered: self.reminders = active_reminders; self.save_config()

    @profile_function("SportsMonitor")
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
            self.cached_events = []
            for idx in self.custom_league_indices:
                if idx < len(DATA_SOURCES):
                    name, url = DATA_SOURCES[idx]
                    d = agent.request(b'GET', url.encode('utf-8'))
                    d.addCallback(readBody)
                    d.addCallback(self.parse_incremental_json, name, url)
                    d.addErrback(self.handle_error_silent)

    def handle_error(self, failure):
        self.status_message = "Connection Error"
        self.cached_events = []
        for cb in self.callbacks: cb(True)
    def handle_error_silent(self, failure): pass

    @profile_function("SportsMonitor")
    def parse_single_json(self, body, league_name_fixed="", league_url=""): 
        self.process_events_data([(body, league_name_fixed, league_url)], append_mode=False)
        
    @profile_function("SportsMonitor")
    def parse_incremental_json(self, body, league_name_fixed, league_url):
        self.process_events_data([(body, league_name_fixed, league_url)], append_mode=True)

    def parse_multi_json(self, bodies_list): 
        self.process_events_data(bodies_list)

    def queue_notification(self, league, match, scorer, l_url, h_url, a_url):
        self.notification_queue.append((league, match, scorer, l_url, h_url, a_url)); self.process_queue()
    def process_queue(self):
        if self.notification_active or not self.notification_queue: return
        league, match, scorer, l_url, h_url, a_url = self.notification_queue.pop(0)
        self.notification_active = True
        if self.session: self.session.openWithCallback(self.on_toast_closed, GoalToast, league, match, scorer, l_url, h_url, a_url)
        else: self.notification_active = False
    def on_toast_closed(self, *args): self.notification_active = False; self.process_queue()

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
        if sport == 'basketball': return "SCORE (+{})".format(diff)
        if sport == 'football': return "SCORE (+{})".format(diff)
        return "SCORE"
    def get_scorer_text(self, event):
        try:
            details = event.get('competitions', [{}])[0].get('details', [])
            if details:
                for play in reversed(details):
                    is_scoring = play.get('scoringPlay', False)
                    text_desc = play.get('type', {}).get('text', '').lower()
                    if is_scoring or "goal" in text_desc:
                        clock = play.get('clock', {}).get('displayValue', '')
                        athletes = play.get('athletesInvolved', [])
                        if not athletes: athletes = play.get('participants', [])
                        if athletes:
                            p_name = athletes[0].get('displayName') or athletes[0].get('shortName')
                            return "{}  ( {} )".format(p_name, clock)
                        else: return "Goal  ( {} )".format(clock)
        except: pass
        return ""

    @profile_function("SportsMonitor")
    def process_events_data(self, data_list, single_league_name="", append_mode=False):
        new_events = []
        try:
            for item in data_list:
                if isinstance(item, tuple): body, l_name, l_url = item
                else: body, l_name, l_url = item, single_league_name, ""
                try:
                    json_str = body.decode('utf-8', errors='ignore')
                    data = json.loads(json_str)
                    league_obj = data.get('leagues', [{}])[0]
                    if l_name: league_name = l_name
                    else: league_name = league_obj.get('name') or league_obj.get('shortName') or ""
                    events = data.get('events', [])
                    for ev in events:
                        ev['league_name'] = league_name
                        ev['league_url'] = l_url
                    new_events.extend(events)
                except: pass
            
            # --- DE-DUPLICATION ---
            seen_ids = set()
            unique_list = []
            
            # If appending, keep existing unique events
            if append_mode:
                for ev in self.cached_events:
                    eid = ev.get('id')
                    if eid and eid not in seen_ids:
                        seen_ids.add(eid)
                        unique_list.append(ev)
            
            # Add new unique events
            for ev in new_events:
                eid = ev.get('id')
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    unique_list.append(ev)
                elif not eid:
                    unique_list.append(ev)
            
            # --- STABLE SORT: DATE + ID ---
            # Using 'id' as secondary key prevents random flipping for concurrent games
            unique_list.sort(key=lambda x: (x.get('date', ''), x.get('id', '')))
            
            self.cached_events = unique_list
            
            if len(self.cached_events) == 0: self.status_message = "No Matches Found"
            else: self.status_message = "Data Updated"

            now = time.time()
            keys_to_del = []
            for mid, info in self.goal_flags.items():
                if now - info['time'] > 60: keys_to_del.append(mid)
            for k in keys_to_del: del self.goal_flags[k]

            for event in self.cached_events:
                status = event.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                if len(comps) < 2: continue 
                league_name = event.get('league_name', '')
                sport_cdn = self.get_cdn_sport_name(league_name)
                
                team_h = next((t for t in comps if t.get('homeAway') == 'home'), None)
                team_a = next((t for t in comps if t.get('homeAway') == 'away'), None)
                if not team_h and len(comps) > 0: team_h = comps[0]
                if not team_a and len(comps) > 1: team_a = comps[1]

                home = team_h.get('team', {}).get('shortDisplayName') or "Home"
                h_score = int(team_h.get('score', '0'))
                h_id = team_h.get('team', {}).get('id', '')
                h_logo = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png&w=40&h=40&transparent=true".format(sport_cdn, h_id) if h_id else ""

                away = team_a.get('team', {}).get('shortDisplayName') or "Away"
                a_score = int(team_a.get('score', '0'))
                a_id = team_a.get('team', {}).get('id', '')
                a_logo = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png&w=40&h=40&transparent=true".format(sport_cdn, a_id) if a_id else ""

                event['h_logo_url'] = h_logo
                event['a_logo_url'] = a_logo

                match_id = home + "_" + away 
                score_str = str(h_score) + "-" + str(a_score)

                prev_state = self.last_states.get(match_id)
                if self.active and self.session and prev_state:
                    should_play_stend = (self.discovery_mode == 2 and self.get_sport_type(league_name) == 'soccer')
                    if state == 'in' and prev_state == 'pre':
                        match_txt = "{} {} - {} {}".format(home, h_score, a_score, away)
                        self.queue_notification(league_name, match_txt, "MATCH STARTED", "", h_logo, a_logo)
                        if should_play_stend: self.play_stend_sound()
                    elif state == 'post' and prev_state == 'in':
                        match_txt = "{} {} - {} {}".format(home, h_score, a_score, away)
                        self.queue_notification(league_name, match_txt, "FULL TIME", "", h_logo, a_logo)
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
                                should_play_sound = False
                                if self.active and self.discovery_mode == 2 and sport_type == 'soccer':
                                    if diff_h > 0 or diff_a > 0: should_play_sound = True
                                if diff_h != 0:
                                    if diff_h > 0: 
                                        self.goal_flags[match_id] = {'side': 'home', 'time': time.time()}
                                        if should_play_sound: self.play_sound()
                                    if self.active and self.session:
                                        prefix = self.get_score_prefix(sport_type, diff_h)
                                        match_txt = "{} >> {} {} - {} {}".format(prefix, home, h_score, a_score, away)
                                        scorer_txt = self.get_scorer_text(event)
                                        self.queue_notification(league_name, match_txt, scorer_txt, "", h_logo, a_logo)
                                if diff_a != 0:
                                    if diff_a > 0: 
                                        self.goal_flags[match_id] = {'side': 'away', 'time': time.time()}
                                        if should_play_sound: self.play_sound()
                                    if self.active and self.session:
                                        prefix = self.get_score_prefix(sport_type, diff_a)
                                        match_txt = "{} {} {} - {} {} <<".format(prefix, home, h_score, a_score, away)
                                        scorer_txt = self.get_scorer_text(event)
                                        self.queue_notification(league_name, match_txt, scorer_txt, "", h_logo, a_logo)
                            except: pass
                    self.last_scores[match_id] = score_str

            for cb in self.callbacks: cb(True)
        except:
            self.status_message = "JSON Parse Error"
            for cb in self.callbacks: cb(True)

if global_sports_monitor is None:
    global_sports_monitor = SportsMonitor()




# ==============================================================================
# MISSING HELPERS & GAME INFO SCREEN
# ==============================================================================
def InfoListEntry(entry):
    col_text = 0xffffff 
    col_none = None
    return [
        entry,
        # 1. Time
        eListboxPythonMultiContent.TYPE_TEXT,
        0, 0, 100, 40, 0, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, entry[0], col_text, col_none, 
        # 2. Emoji
        eListboxPythonMultiContent.TYPE_TEXT,
        110, 0, 50, 40, 0, RT_HALIGN_CENTER | RT_VALIGN_CENTER, entry[1], col_text, col_none,
        # 3. Text
        eListboxPythonMultiContent.TYPE_TEXT,
        170, 0, 800, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[2], col_text, col_none
    ]

# ==============================================================================
# ==============================================================================
# UPDATED LIST RENDERERS (Added TextListEntry for News/Preview)
# ==============================================================================
def StatsListEntry(label, home_val, away_val, theme_mode):
    """3-Column Layout: [ HOME ] [ LABEL/TIME ] [ AWAY ]"""
    if theme_mode == "ucl": col_label, col_val, col_bg = 0x00ffff, 0xffffff, 0x0e1e5b
    else: col_label, col_val, col_bg = 0x00FF85, 0xFFFFFF, 0x33190028
    # Layout: wider columns to fit scorer names
    h_x, h_w = 20, 460; l_x, l_w = 500, 200; a_x, a_w = 720, 460
    res = [None]
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 48, 1200, 2, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, 1))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, l_x, 0, l_w, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(label).upper(), col_label, col_bg))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, h_x, 0, h_w, 50, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, str(home_val), col_val, col_bg))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, a_x, 0, a_w, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(away_val), col_val, col_bg))
    return res

def RosterListEntry(home_player, away_player, theme_mode):
    """2-Column Layout for Rosters - Stylish Version"""
    # Check if this is a section header (contains bullet point)
    is_header = u"\u2022" in str(home_player) or u"\u2022" in str(away_player)
    is_starter = u"\u2605" in str(home_player) or u"\u2605" in str(away_player)
    
    if theme_mode == "ucl":
        col_text = 0x00ffff if is_header else (0xffd700 if is_starter else 0xffffff)
        col_bg = 0x0e1e5b if is_header else None
        col_sep = 0x182c82
    else:
        col_text = 0x00FF85 if is_header else (0xffd700 if is_starter else 0xffffff)
        col_bg = 0x28002C if is_header else None
        col_sep = 0x505050
    
    h_x, h_w = 30, 560; a_x, a_w = 610, 560
    res = [None]
    # Add separator line
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 48, 1200, 2, 0, RT_HALIGN_CENTER, "", col_sep, col_sep, 1))
    # Background for headers
    if is_header:
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1200, 50, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, 1))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, h_x, 0, h_w, 50, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, str(home_player), col_text, None))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, a_x, 0, a_w, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(away_player), col_text, None))
    return res

def TextListEntry(text, theme_mode, align="center", is_header=False):
    """1-Column Layout for News/Facts/Preview Text"""
    if theme_mode == "ucl": 
        col_text = 0x00ffff if is_header else 0xffffff
        col_bg = 0x0e1e5b if is_header else None
    else: 
        col_text = 0x00FF85 if is_header else 0xFFFFFF
        col_bg = 0x33190028 if is_header else None
    
    flags = RT_HALIGN_CENTER | RT_VALIGN_CENTER
    if align == "left": flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER
    
    res = [None]
    # Background line if header
    if is_header:
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1200, 50, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, 1))
    
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 0, 1160, 50, 0, flags, str(text), col_text, None))
    return res

def wrap_text(text, max_chars=70):
    """Wrap text into multiple lines based on character limit"""
    if not text:
        return []
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) + 1 <= max_chars:
            if current_line:
                current_line += " " + word
            else:
                current_line = word
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

# ==============================================================================
# STANDINGS TABLE ENTRY
# ==============================================================================
def StandingTableEntry(pos, team, played, won, draw, lost, gd, pts, theme_mode, is_header=False):
    """Table Row for Standings: Pos | Team | P | W | D | L | GD | Pts"""
    if theme_mode == "ucl":
        col_text = 0x00ffff if is_header else 0xffffff
        col_accent = 0xffd700  # Gold for top 4
        col_bg = 0x0e1e5b if is_header else None
        col_dim = 0x888888
    else:
        col_text = 0x00FF85 if is_header else 0xffffff
        col_accent = 0xffd700
        col_bg = 0x28002C if is_header else None
        col_dim = 0x888888
    
    # Highlight top 4 positions
    try:
        if not is_header and int(pos) <= 4:
            col_text = col_accent
    except: pass
    
    res = [None]
    # Separator line at bottom
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 48, 1200, 2, 0, RT_HALIGN_CENTER, "", col_dim, col_dim, 1))
    # Background for header
    if is_header:
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1200, 50, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, 1))
    
    # Table columns: Pos(60) | Team(420) | P(80) | W(80) | D(80) | L(80) | GD(100) | Pts(80)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 0, 60, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(pos), col_text, None))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 90, 0, 420, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(team), col_text, None))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 520, 0, 80, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(played), col_dim if not is_header else col_text, None))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 600, 0, 80, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(won), col_dim if not is_header else col_text, None))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 680, 0, 80, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(draw), col_dim if not is_header else col_text, None))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 760, 0, 80, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(lost), col_dim if not is_header else col_text, None))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 840, 0, 100, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(gd), col_dim if not is_header else col_text, None))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 950, 0, 80, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(pts), col_text, None))
    return res

# ==============================================================================
# TEAM STANDING SCREEN
# ==============================================================================
class TeamStandingScreen(Screen):
    def __init__(self, session, league_url="", league_name=""):
        Screen.__init__(self, session)
        self.session = session
        self.league_url = league_url
        self.league_name = league_name
        self.theme = global_sports_monitor.theme_mode
        self.standings_rows = []
        
        # --- SKIN ---
        if self.theme == "ucl":
            bg_color = "#00000000"; top_bar = "#091442"; accent = "#00ffff"
            self.skin = f"""<screen position="center,center" size="1280,720" title="League Standings" flags="wfNoBorder" backgroundColor="{bg_color}">
                <eLabel position="0,0" size="1280,100" backgroundColor="{top_bar}" zPosition="0" />
                <eLabel position="0,100" size="1280,4" backgroundColor="{accent}" zPosition="1" />
                <widget name="title" position="0,30" size="1280,40" font="Regular;32" foregroundColor="{accent}" backgroundColor="{top_bar}" transparent="1" halign="center" valign="center" zPosition="5" />
                <widget name="subtitle" position="0,70" size="1280,25" font="Regular;18" foregroundColor="#aaaaaa" backgroundColor="{top_bar}" transparent="1" halign="center" valign="center" zPosition="5" />
                <widget name="standings_list" position="40,120" size="1200,550" scrollbarMode="showNever" transparent="1" zPosition="5" />
                <widget name="loading" position="0,350" size="1280,100" font="Regular;32" foregroundColor="{accent}" transparent="1" halign="center" zPosition="10" />
                <widget name="hint" position="0,680" size="1280,30" font="Regular;20" foregroundColor="#888888" transparent="1" halign="center" zPosition="5" />
            </screen>"""
        else:
            bg_color = "#38003C"; top_bar = "#28002C"; accent = "#00FF85"
            self.skin = f"""<screen position="center,center" size="1280,720" title="League Standings" flags="wfNoBorder" backgroundColor="{bg_color}">
                <eLabel position="0,0" size="1280,100" backgroundColor="{top_bar}" zPosition="0" />
                <eLabel position="0,100" size="1280,4" backgroundColor="{accent}" zPosition="1" />
                <widget name="title" position="0,30" size="1280,40" font="Regular;32" foregroundColor="{accent}" backgroundColor="{top_bar}" transparent="1" halign="center" valign="center" zPosition="5" />
                <widget name="subtitle" position="0,70" size="1280,25" font="Regular;18" foregroundColor="#aaaaaa" backgroundColor="{top_bar}" transparent="1" halign="center" valign="center" zPosition="5" />
                <widget name="standings_list" position="40,120" size="1200,550" scrollbarMode="showNever" transparent="1" zPosition="5" />
                <widget name="loading" position="0,350" size="1280,100" font="Regular;32" foregroundColor="{accent}" transparent="1" halign="center" zPosition="10" />
                <widget name="hint" position="0,680" size="1280,30" font="Regular;20" foregroundColor="#888888" transparent="1" halign="center" zPosition="5" />
            </screen>"""
        
        self["title"] = Label(league_name.upper() if league_name else "LEAGUE STANDINGS")
        self["subtitle"] = Label("STANDINGS")
        self["loading"] = Label("Loading Standings...")
        self["hint"] = Label("Press OK to return to Main Screen")
        
        self["standings_list"] = MenuList([], enableWrapAround=False, content=eListboxPythonMultiContent)
        self["standings_list"].l.setFont(0, gFont("Regular", 24))
        self["standings_list"].l.setItemHeight(50)
        
        self["actions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions", "WizardActions"], {
            "cancel": self.close_to_main, "ok": self.close_to_main, "back": self.close_to_main,
            "up": self.cursor_up, "down": self.cursor_down,
            "left": self.page_up, "right": self.page_down
        }, -2)
        
        self.current_page = 0
        self.items_per_page = 11
        self.onLayoutFinish.append(self.fetch_standings)
    
    def cursor_up(self):
        self["standings_list"].up()
    
    def cursor_down(self):
        self["standings_list"].down()
    
    def page_up(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_display()
    
    def page_down(self):
        total_items = len(self.standings_rows)
        if total_items > 0:
            import math
            max_page = int(math.ceil(float(total_items) / float(self.items_per_page))) - 1
            if self.current_page < max_page:
                self.current_page += 1
                self.update_display()
    
    def update_display(self):
        if not self.standings_rows:
            self["standings_list"].setList([])
            return
        total_items = len(self.standings_rows)
        start_index = self.current_page * self.items_per_page
        end_index = start_index + self.items_per_page
        page_data = self.standings_rows[start_index:end_index]
        self["standings_list"].setList(page_data)
        import math
        total_pages = int(math.ceil(float(total_items) / float(self.items_per_page)))
        if total_pages > 1:
            self["hint"].setText("Page {}/{} - Left/Right to navigate, OK to exit".format(self.current_page + 1, total_pages))
        else:
            self["hint"].setText("Press OK to return to Main Screen")
    
    def close_to_main(self):
        """Close this screen and signal GameInfoScreen to close too"""
        self.close("close_all")
    
    def fetch_standings(self):
        self["loading"].show()
        # Build standings URL from league URL using ESPN API pattern
        # Example: site.api.espn.com/apis/v2/sports/football/nfl/standings
        standings_url = ""
        
        if self.league_url:
            # Extract sport and league from URL
            # Pattern: .../sports/{sport}/{league}/scoreboard
            try:
                parts = self.league_url.split('/')
                sport_idx = -1
                for i, p in enumerate(parts):
                    if p == 'sports' and i + 2 < len(parts):
                        sport_idx = i
                        break
                
                if sport_idx >= 0:
                    sport = parts[sport_idx + 1]
                    league = parts[sport_idx + 2].split('?')[0]
                    standings_url = "https://site.api.espn.com/apis/v2/sports/{}/{}/standings".format(sport, league)
            except:
                pass
        
        if not standings_url:
            # Fallback - try to extract from league name
            standings_url = "https://site.api.espn.com/apis/v2/sports/soccer/eng.1/standings"
        
        from twisted.web.client import Agent, readBody
        from twisted.internet import reactor
        agent = Agent(reactor)
        d = agent.request(b'GET', standings_url.encode('utf-8'))
        d.addCallback(self.on_response)
        d.addErrback(self.on_error)
    
    def on_response(self, response):
        from twisted.web.client import readBody
        d = readBody(response)
        d.addCallback(self.parse_standings)
        d.addErrback(self.on_error)
    
    def on_error(self, error):
        self["loading"].setText("Failed to load standings")
    
    def parse_standings(self, body):
        try:
            data = json.loads(body)
            self["loading"].hide()
            
            # Add table header
            self.standings_rows.append(StandingTableEntry("#", "TEAM", "P", "W", "D", "L", "GD", "PTS", self.theme, is_header=True))
            
            # Parse standings data - ESPN API structure
            standings_data = data.get('standings', [])
            if not standings_data:
                standings_data = data.get('children', [])
            
            entries = []
            for group in standings_data:
                if isinstance(group, dict):
                    group_entries = group.get('standings', {}).get('entries', [])
                    if not group_entries:
                        group_entries = group.get('entries', [])
                    entries.extend(group_entries)
            
            if not entries:
                # Try direct entries
                entries = data.get('entries', [])
            
            for entry in entries:
                try:
                    team_data = entry.get('team', {})
                    team_name = team_data.get('displayName', '') or team_data.get('shortDisplayName', '') or team_data.get('name', 'Unknown')
                    
                    # Get stats
                    stats = entry.get('stats', [])
                    stats_map = {}
                    for stat in stats:
                        stat_name = stat.get('name', '') or stat.get('abbreviation', '')
                        stats_map[stat_name.lower()] = stat.get('value', stat.get('displayValue', '0'))
                    
                    pos = stats_map.get('rank', stats_map.get('position', '-'))
                    played = stats_map.get('gamesplayed', stats_map.get('played', stats_map.get('p', '-')))
                    won = stats_map.get('wins', stats_map.get('w', '-'))
                    draw = stats_map.get('ties', stats_map.get('draws', stats_map.get('d', '-')))
                    lost = stats_map.get('losses', stats_map.get('l', '-'))
                    gd = stats_map.get('pointdifferential', stats_map.get('goaldifference', stats_map.get('gd', '-')))
                    pts = stats_map.get('points', stats_map.get('pts', '-'))
                    
                    # Fallback for position from overall rank
                    if pos == '-':
                        pos = stats_map.get('playoffseeed', stats_map.get('overall rank', '-'))
                    
                    # Convert float values to integers (remove .0)
                    def clean_num(val):
                        try:
                            f = float(val)
                            if f == int(f):
                                return str(int(f))
                            return str(val)
                        except:
                            return str(val)
                    
                    pos = clean_num(pos)
                    played = clean_num(played)
                    won = clean_num(won)
                    draw = clean_num(draw)
                    lost = clean_num(lost)
                    gd = clean_num(gd)
                    pts = clean_num(pts)
                    
                    self.standings_rows.append(StandingTableEntry(pos, team_name, played, won, draw, lost, gd, pts, self.theme))
                except: continue
            
            if len(self.standings_rows) <= 1:
                self.standings_rows.append(StandingTableEntry("-", "No standings data available", "-", "-", "-", "-", "-", "-", self.theme))
            
            self.current_page = 0
            self.update_display()
            
        except Exception as e:
            self["loading"].setText("Error: " + str(e))

# ==============================================================================
# GAME INFO SCREEN (UPDATED: "Facebook Style" News Feed)
# ==============================================================================
class GameInfoScreen(Screen):
    def __init__(self, session, event_id, league_url=""):
        Screen.__init__(self, session)
        self.session = session
        self.event_id = event_id
        self.theme = global_sports_monitor.theme_mode
        self.league_url = league_url  # Store for standings screen
        self.league_name = ""  # Will be set when parsing data
        
        self.full_rows = []      
        self.current_page = 0    
        self.items_per_page = 10 
        
        base_url = league_url.split('?')[0]
        if "scoreboard" in base_url:
            self.summary_url = base_url.replace("scoreboard", "summary") + "?event=" + str(event_id)
        else:
            self.summary_url = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary?event=" + str(event_id)

        # --- SKIN ---
        common_widgets = """
            <widget name="match_title" position="0,5" size="1280,28" font="Regular;22" foregroundColor="{accent}" transparent="1" halign="center" valign="center" text="" zPosition="6" />
            
            <widget name="h_logo" position="30,35" size="90,90" alphatest="blend" zPosition="5" scale="1" />
            <widget name="h_name" position="130,40" size="300,40" font="Regular;32" foregroundColor="#ffffff" transparent="1" halign="left" valign="center" zPosition="5" />
            <widget name="h_score" position="430,35" size="150,90" font="Regular;72" foregroundColor="#ffffff" transparent="1" halign="right" valign="center" zPosition="5" />

            <eLabel position="595,50" size="90,50" font="Regular;36" foregroundColor="#888888" transparent="1" halign="center" valign="center" text="-" zPosition="5" />

            <widget name="a_score" position="700,35" size="150,90" font="Regular;72" foregroundColor="#ffffff" transparent="1" halign="left" valign="center" zPosition="5" />
            <widget name="a_name" position="850,40" size="300,40" font="Regular;32" foregroundColor="#ffffff" transparent="1" halign="right" valign="center" zPosition="5" />
            <widget name="a_logo" position="1160,35" size="90,90" alphatest="blend" zPosition="5" scale="1" />
            
            <widget name="stadium_name" position="0,125" size="1280,25" font="Regular;18" foregroundColor="#aaaaaa" transparent="1" halign="center" valign="center" zPosition="5" />

            <widget name="info_list" position="40,155" size="1200,555" scrollbarMode="showNever" transparent="1" zPosition="5" />
            <widget name="loading" position="0,350" size="1280,100" font="Regular;32" foregroundColor="{accent}" transparent="1" halign="center" zPosition="10" />
            <widget name="page_indicator" position="0,690" size="1280,30" font="Regular;22" foregroundColor="#ffffff" transparent="1" halign="center" zPosition="10" />
        """

        if self.theme == "ucl":
            bg_color = "#00000000"; top_bar = "#091442"; accent = "#00ffff"
            skin_widgets = common_widgets.replace("{accent}", accent)
            self.skin = f"""<screen position="center,center" size="1280,720" title="Game Stats" flags="wfNoBorder" backgroundColor="{bg_color}"><eLabel position="0,0" size="1280,150" backgroundColor="{top_bar}" zPosition="0" /><eLabel position="0,150" size="1280,4" backgroundColor="{accent}" zPosition="1" />{skin_widgets}</screen>"""
        else:
            bg_color = "#38003C"; top_bar = "#28002C"; accent = "#00FF85"
            skin_widgets = common_widgets.replace("{accent}", accent)
            self.skin = f"""<screen position="center,center" size="1280,720" title="Game Stats" flags="wfNoBorder" backgroundColor="{bg_color}"><eLabel position="0,0" size="1280,150" backgroundColor="{top_bar}" zPosition="0" /><eLabel position="0,150" size="1280,4" backgroundColor="{accent}" zPosition="1" />{skin_widgets}</screen>"""

        self["h_name"] = Label(""); self["a_name"] = Label("")
        self["h_score"] = Label(""); self["a_score"] = Label("")
        self["stadium_name"] = Label(""); self["match_title"] = Label("MATCH DETAILS")
        self["h_logo"] = Pixmap(); self["a_logo"] = Pixmap()
        self["loading"] = Label("Fetching Data..."); self["page_indicator"] = Label("")
        
        self["info_list"] = MenuList([], enableWrapAround=False, content=eListboxPythonMultiContent)
        self["info_list"].l.setFont(0, gFont("Regular", 24))
        self["info_list"].l.setFont(1, gFont("Regular", 20))
        self["info_list"].l.setItemHeight(50)
        
        self["actions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions", "WizardActions"], {
            "cancel": self.close, "green": self.close, "ok": self.open_standings, "back": self.close,
            "up": self.page_up, "down": self.page_down, "left": self.page_up, "right": self.page_down
        }, -2)
        
        self.onLayoutFinish.append(self.start_loading)
    
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
            self[widget_name].instance.setPixmapFromFile(tmp_path)
            self[widget_name].show()

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
            # MODE A: FACEBOOK STYLE NEWS FEED (PREVIEW MODE)
            # ==========================================================
            if game_status == 'pre':
                self["match_title"].setText(league_name if league_name else "PREVIEW")
                
                # 1. Prediction (FB Style Post)
                try:
                    predictor = data.get('predictor', {})
                    h_prob = predictor.get('homeTeam', {}).get('gameProjection', '0')
                    a_prob = predictor.get('awayTeam', {}).get('gameProjection', '0')
                    if h_prob != '0' and a_prob != '0':
                        # Post Header
                        self.full_rows.append(TextListEntry("GAME PREDICTION", self.theme, is_header=True))
                        # Post Body
                        txt = "Home Win: " + h_prob + "%  |  Draw: " + str(100 - float(h_prob) - float(a_prob))[:4] + "%  |  Away Win: " + a_prob + "%"
                        self.full_rows.append(TextListEntry(txt, self.theme))
                        # Post Footer (Fake Social)
                        self.full_rows.append(TextListEntry(u"\u26BD 2.5k  \u2022  \U0001F4AC 342 comments  \u2022  \u27A1 Share", self.theme))
                        self.full_rows.append(TextListEntry("", self.theme)) # Spacer
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
                                headline_lines = wrap_text(headline, max_chars=70)
                                for line in headline_lines:
                                    self.full_rows.append(TextListEntry(line, self.theme, align="left"))
                                
                                # Row 2: Description as wrapped paragraph (if available)
                                if desc:
                                    desc_lines = wrap_text(desc, max_chars=70)
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
                # 1. Timeline
                details = []
                comps_data = data.get('competitions', [{}])[0]
                if 'details' in comps_data: details = comps_data['details']
                elif 'details' in data.get('header', {}).get('competitions', [{}])[0]:
                    details = data.get('header', {}).get('competitions', [{}])[0]['details']

                if details:
                    self.full_rows.append(StatsListEntry("TIME", "HOME EVENTS", "AWAY EVENTS", self.theme))
                    goals_found = False
                    for play in details:
                        text_desc = play.get('type', {}).get('text', '').lower()
                        is_score = play.get('scoringPlay', False) or "goal" in text_desc or "touchdown" in text_desc
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
                            if t_id == h_id_root:
                                self.full_rows.append(StatsListEntry(clock, scorer, "", self.theme))
                            else:
                                self.full_rows.append(StatsListEntry(clock, "", scorer, self.theme))
                    
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
                                wrapped = wrap_text(key_txt, max_chars=70)
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
                                wrapped = wrap_text(headline, max_chars=70)
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

# ==============================================================================
# GOAL TOAST
# ==============================================================================
class GoalToast(Screen):
    def __init__(self, session, league_text, match_text, scorer_text, l_url, h_url, a_url):
        # Dynamic Width
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

        self.timer = eTimer()
        try: self.timer.callback.append(self.close)
        except AttributeError: self.timer.timeout.get().append(self.close)
        self.timer.start(8000, True)

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

    def image_error(self, error): pass

# ==============================================================================
# LEAGUE SELECTOR
# ==============================================================================
class LeagueSelector(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
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
# MINI BAR 2 (Bottom) - FIXED: Callback Synchronization
# ==============================================================================
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
            bar_h = 40; bar_y = height - bar_h; font_lg = "Regular;26"; font_sm = "Regular;22"; logo_s = 35
            x_league=30; w_league=250; x_home_name=290; w_home_name=500; x_h_logo=860
            x_score=920; w_score=140; x_a_logo=1070; x_away_name=1115; w_away_name=500
            x_status=1630; w_status=100; x_time=1740; w_time=170
        else:
            bar_h = 35; bar_y = height - bar_h; font_lg = "Regular;22"; font_sm = "Regular;18"; logo_s = 30
            x_league=10; w_league=180; x_home_name=200; w_home_name=280; x_h_logo=530
            x_score=580; w_score=100; x_a_logo=690; x_away_name=740; w_away_name=280
            x_status=1030; w_status=80; x_time=1120; w_time=150
            
        if global_sports_monitor.theme_mode == "ucl":
            self.skin = """<screen position="0,{y}" size="{w},{h}" title="Sports Ticker Bottom" backgroundColor="#40000000" flags="wfNoBorder"><eLabel position="0,0" size="{w},{h}" backgroundColor="#cc0e1e5b" zPosition="0" /><eLabel position="0,0" size="{w},2" backgroundColor="#00ffff" zPosition="1" /><widget name="lbl_league" position="{xl},0" size="{wl},{h}" font="{fl}" foregroundColor="#00ffff" backgroundColor="#cc0e1e5b" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_home" position="{xh},0" size="{wh},{h}" font="{fl}" foregroundColor="#ffffff" backgroundColor="#cc0e1e5b" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="h_logo" position="{xhl},2" size="{ls},{ls}" alphatest="blend" zPosition="2" /><eLabel position="{xs},0" size="{ws},{h}" backgroundColor="#ffffff" zPosition="1" /><widget name="lbl_score" position="{xs},0" size="{ws},{h}" font="{fl}" foregroundColor="#0e1e5b" backgroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="3" /><widget name="a_logo" position="{xal},2" size="{ls},{ls}" alphatest="blend" zPosition="2" /><widget name="lbl_away" position="{xa},0" size="{wa},{h}" font="{fl}" foregroundColor="#ffffff" backgroundColor="#cc0e1e5b" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_status" position="{xst},0" size="{wst},{h}" font="{fs}" foregroundColor="#ffffff" backgroundColor="#cc0e1e5b" transparent="1" halign="center" valign="center" zPosition="2" /><widget name="lbl_time" position="{xt},0" size="{wt},{h}" font="{fs}" foregroundColor="#00ffff" backgroundColor="#cc0e1e5b" transparent="1" halign="right" valign="center" zPosition="2" /></screen>""".format(y=bar_y, w=width, h=bar_h, fl=font_lg, fs=font_sm, ls=logo_s, xl=x_league, wl=w_league, xh=x_home_name, wh=w_home_name, xhl=x_h_logo, xs=x_score, ws=w_score, xst=x_status, wst=w_status, xal=x_a_logo, xa=x_away_name, wa=w_away_name, xt=x_time, wt=w_time)
        else:
            self.skin = """<screen position="0,{y}" size="{w},{h}" title="Sports Ticker Bottom" backgroundColor="#40000000" flags="wfNoBorder"><eLabel position="0,0" size="{w},{h}" backgroundColor="#cc331900" zPosition="0" /><eLabel position="0,0" size="5,{h}" backgroundColor="#E90052" zPosition="1" /><eLabel position="{rend},{h}" size="5,{h}" backgroundColor="#F6B900" zPosition="1" /><widget name="lbl_league" position="{xl},0" size="{wl},{h}" font="{fl}" foregroundColor="#FFD700" backgroundColor="#cc331900" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_home" position="{xh},0" size="{wh},{h}" font="{fl}" foregroundColor="#FFFFFF" backgroundColor="#cc331900" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="h_logo" position="{xhl},2" size="{ls},{ls}" alphatest="blend" zPosition="2" /><eLabel position="{xs},0" size="{ws},{h}" backgroundColor="#00FF85" zPosition="1" /><widget name="lbl_score" position="{xs},0" size="{ws},{h}" font="{fl}" foregroundColor="#000000" backgroundColor="#00FF85" transparent="1" halign="center" valign="center" zPosition="3" /><widget name="a_logo" position="{xal},2" size="{ls},{ls}" alphatest="blend" zPosition="2" /><widget name="lbl_away" position="{xa},0" size="{wa},{h}" font="{fl}" foregroundColor="#FFFFFF" backgroundColor="#cc331900" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_status" position="{xst},0" size="{wst},{h}" font="{fs}" foregroundColor="#FFFFFF" backgroundColor="#cc331900" transparent="1" halign="center" valign="center" zPosition="2" /><widget name="lbl_time" position="{xt},0" size="{wt},{h}" font="{fs}" foregroundColor="#00FF85" backgroundColor="#cc331900" transparent="1" halign="right" valign="center" zPosition="2" /></screen>""".format(y=bar_y, w=width, h=bar_h, rend=width-5, fl=font_lg, fs=font_sm, ls=logo_s, xl=x_league, wl=w_league, xh=x_home_name, wh=w_home_name, xhl=x_h_logo, xs=x_score, ws=w_score, xst=x_status, wst=w_status, xal=x_a_logo, xa=x_away_name, wa=w_away_name, xt=x_time, wt=w_time)

        self["lbl_league"] = Label(""); self["lbl_home"] = Label(""); self["lbl_score"] = Label("")
        self["lbl_away"] = Label(""); self["lbl_status"] = Label(""); self["lbl_time"] = Label("")
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
                            if "Goal - " in clean: scorer = clean.split("Goal - ")[1].split('(')[0].strip()
                        if scorer:
                            t_id = str(play.get('team', {}).get('id', ''))
                            if t_id == str(home_id): h_scorers.append(scorer)
                            elif t_id == str(away_id): a_scorers.append(scorer)
        except: pass
        def format_list(lst):
            if not lst: return ""
            seen = set(); unique = [x for x in lst if not (x in seen or seen.add(x))]
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
            if mode == 2 and ev_date != today_str: continue
            if mode == 3 and ev_date != tom_str: continue
            
            # Use raw URLs for async check
            h_url = event.get('h_logo_url', '')
            a_url = event.get('a_logo_url', '')
            try: h_id = h_url.split('500/')[-1].split('.png')[0]
            except: h_id = '0'
            try: a_id = a_url.split('500/')[-1].split('.png')[0]
            except: a_id = '0'
            
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            if len(comps) > 2:
                race = event.get('shortName', 'Event'); venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                match_data = {'league': league_name, 'color': 0xffffff, 'home': race, 'away': venue, 'score': "VS", 'status': "SCH", 'time': local_time, 'h_url': h_url, 'a_url': a_url, 'h_id': h_id, 'a_id': a_id}
            else:
                home, away, h_score, a_score = "Home", "Away", "0", "0"; h_team_id, a_team_id = "0", "0"
                for team in comps:
                    name = team.get('team', {}).get('displayName', 'Team'); sc = team.get('score', '0'); tid = team.get('team', {}).get('id', '0')
                    if team.get('homeAway') == 'home': home, h_score, h_team_id = name, sc, tid
                    else: away, a_score, a_team_id = name, sc, tid
                score_str = "VS"; status_str = "SCH"; h_scorers_txt, a_scorers_txt = "", ""
                if state == 'in':
                    score_str = "{} - {}".format(h_score, a_score); status_str = clock
                    h_scorers_txt, a_scorers_txt = self.get_scorers_string(event, h_team_id, a_team_id)
                elif state == 'post':
                    score_str = "{} - {}".format(h_score, a_score); status_str = "FT"
                    h_scorers_txt, a_scorers_txt = self.get_scorers_string(event, h_team_id, a_team_id)
                final_home_txt = home
                if h_scorers_txt: final_home_txt = "({})  {}".format(h_scorers_txt, home)
                final_away_txt = away
                if a_scorers_txt: final_away_txt = "{}  ({})".format(away, a_scorers_txt)
                l_color = 0xffffff
                for key, val in self.league_colors.items():
                    if key in league_name.upper() or key in event.get('shortName', '').upper(): l_color = val; break
                match_data = {'league': league_name, 'color': l_color, 'home': final_home_txt, 'away': final_away_txt, 'score': score_str, 'status': status_str, 'time': local_time, 'h_url': h_url, 'a_url': a_url, 'h_id': h_id, 'a_id': a_id}
            self.matches.append(match_data)
            
        # FIX: EMPTY MATCHES AFTER FILTER
        if not self.matches:
            self.matches.append({'league': "SimplySports", 'color': 0xffffff, 'home': "No Matches Found", 'away': "Check Filters", 'score': "", 'status': "", 'time': "", 'h_url': "", 'a_url': "", 'h_id': "", 'a_id': ""})

        if not self.ticker_timer.isActive(): 
            self.show_next_match()
            self.ticker_timer.start(5000)

    def show_next_match(self):
        if not self.matches: return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matches)
        data = self.matches[self.current_match_idx]
        self["lbl_league"].setText(str(data.get('league', '')))
        try: self["lbl_league"].instance.setForegroundColor(gRGB(data.get('color', 0xffffff)))
        except: pass
        self["lbl_home"].setText(str(data.get('home', ''))); self["lbl_score"].setText(str(data.get('score', '')))
        self["lbl_away"].setText(str(data.get('away', ''))); self["lbl_status"].setText(str(data.get('status', '')))
        self["lbl_time"].setText(str(data.get('time', '')))
        
        self.load_logo(data.get('h_url'), data.get('h_id'), "h_logo")
        self.load_logo(data.get('a_url'), data.get('a_id'), "a_logo")

    def load_logo(self, url, img_id, widget_name):
        if not img_id or img_id == '0': self[widget_name].hide(); return
        file_path = self.logo_path + img_id + ".png"
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            self[widget_name].instance.setPixmapFromFile(file_path)
            self[widget_name].show()
        else:
            self[widget_name].hide()
            from twisted.web.client import downloadPage
            downloadPage(url.encode('utf-8'), file_path).addCallback(self.logo_downloaded, widget_name, file_path).addErrback(self.logo_error)

    def logo_downloaded(self, data, widget_name, file_path):
        if self[widget_name].instance:
            self[widget_name].instance.setPixmapFromFile(file_path)
            self[widget_name].show()
    def logo_error(self, error): pass

# ==============================================================================
# MINI BAR 1 (Top Left) - FIXED: Callback Synchronization
# ==============================================================================
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
            # Compact MiniBar: 700px wide, right-aligned at x=580, 60px tall, transparent league name
            self.skin = """<screen position="580,5" size="700,60" title="Sports Ticker" backgroundColor="#00000000" flags="wfNoBorder"><widget name="lbl_league" position="0,0" size="700,16" font="Regular;13" foregroundColor="#00ffff" transparent="1" halign="center" valign="center" zPosition="3" /><eLabel position="0,16" size="700,44" backgroundColor="#800e1e5b" zPosition="0" /><eLabel position="260,16" size="180,44" backgroundColor="#ffffff" zPosition="1" /><widget name="h_logo" position="5,20" size="36,36" alphatest="blend" zPosition="2" /><widget name="lbl_home" position="42,16" size="210,44" font="Regular;20" foregroundColor="#ffffff" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="lbl_score" position="260,18" size="180,26" font="Regular;22" foregroundColor="#0e1e5b" backgroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="3" /><widget name="lbl_status" position="260,44" size="180,14" font="Regular;12" foregroundColor="#0e1e5b" backgroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="3" /><widget name="lbl_away" position="448,16" size="210,44" font="Regular;20" foregroundColor="#ffffff" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="a_logo" position="659,20" size="36,36" alphatest="blend" zPosition="2" /></screen>"""
        else:
            # Compact MiniBar: 700px wide, right-aligned at x=580, 60px tall, transparent league name
            self.skin = """<screen position="580,5" size="700,60" title="Sports Ticker" backgroundColor="#00000000" flags="wfNoBorder"><widget name="lbl_league" position="0,0" size="700,16" font="Regular;13" foregroundColor="#FFFFFF" transparent="1" halign="center" valign="center" zPosition="3" /><eLabel position="0,16" size="5,44" backgroundColor="#E90052" zPosition="1" /><eLabel position="5,16" size="265,44" backgroundColor="#80190028" zPosition="1" /><widget name="h_logo" position="10,20" size="36,36" alphatest="blend" zPosition="2" /><widget name="lbl_home" position="48,16" size="215,44" font="Regular;20" foregroundColor="#FFFFFF" transparent="1" halign="right" valign="center" zPosition="2" /><eLabel position="270,16" size="160,44" backgroundColor="#00FF85" zPosition="1" /><widget name="lbl_score" position="270,18" size="160,26" font="Regular;22" foregroundColor="#000000" backgroundColor="#00FF85" transparent="1" halign="center" valign="center" zPosition="2" /><widget name="lbl_status" position="270,44" size="160,14" font="Regular;12" foregroundColor="#000000" backgroundColor="#00FF85" transparent="1" halign="center" valign="center" zPosition="3" /><eLabel position="430,16" size="265,44" backgroundColor="#80190028" zPosition="1" /><widget name="lbl_away" position="437,16" size="215,44" font="Regular;20" foregroundColor="#FFFFFF" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="a_logo" position="654,20" size="36,36" alphatest="blend" zPosition="2" /><eLabel position="695,16" size="5,44" backgroundColor="#F6B900" zPosition="1" /></screen>"""

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
        self.matches = []
        
        # If Monitor is empty/loading
        if not events:
            msg = global_sports_monitor.status_message or "Loading..."
            self.matches.append({'league': "SimplySports", 'color': 0xffffff, 'home': msg, 'away': "", 'score': "", 'status': "", 'h_url': "", 'a_url': "", 'h_id': "", 'a_id': ""})
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
            if mode == 2 and ev_date != today_str: continue
            if mode == 3 and ev_date != tom_str: continue

            h_url = event.get('h_logo_url', '')
            a_url = event.get('a_logo_url', '')
            try: h_id = h_url.split('500/')[-1].split('.png')[0]
            except: h_id = '0'
            try: a_id = a_url.split('500/')[-1].split('.png')[0]
            except: a_id = '0'

            comps = event.get('competitions', [{}])[0].get('competitors', [])
            
            if len(comps) > 2:
                race = event.get('shortName', 'Event')
                venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                match_data = {'league': league_name, 'home': race, 'away': venue, 'score': "VS", 'status': "SCH", 'h_url': "", 'a_url': "", 'h_id': "", 'a_id': ""}
            else:
                home, away, h_score, a_score = "Home", "Away", "0", "0"
                for team in comps:
                    name = team.get('team', {}).get('displayName', 'Team')
                    sc = team.get('score', '0')
                    if team.get('homeAway') == 'home': home, h_score = name, sc
                    else: away, a_score = name, sc
                
                score_str = "VS"; status_str = "SCH"
                if state == 'in': score_str = "{} - {}".format(h_score, a_score); status_str = clock
                elif state == 'post': score_str = "{} - {}".format(h_score, a_score); status_str = "FT"
                
                match_data = {'league': league_name, 'home': home, 'away': away, 'score': score_str, 'status': status_str, 'h_url': h_url, 'a_url': a_url, 'h_id': h_id, 'a_id': a_id}
            self.matches.append(match_data)
            
        # Handle Filter Empty
        if not self.matches:
            self.matches.append({'league': "SimplySports", 'color': 0xffffff, 'home': "No Matches Found", 'away': "Check Filters", 'score': "", 'status': "", 'h_url': "", 'a_url': "", 'h_id': "", 'a_id': ""})

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
        if not img_id or img_id == '0': self[widget_name].hide(); return
        file_path = self.logo_path + img_id + ".png"
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            self[widget_name].instance.setPixmapFromFile(file_path)
            self[widget_name].show()
        else:
            self[widget_name].hide()
            # Background download
            from twisted.web.client import downloadPage
            downloadPage(url.encode('utf-8'), file_path).addCallback(self.logo_downloaded, widget_name, file_path).addErrback(self.logo_error)

    def logo_downloaded(self, data, widget_name, file_path):
        if self[widget_name].instance:
            self[widget_name].instance.setPixmapFromFile(file_path)
            self[widget_name].show()
    def logo_error(self, error): pass





# ==============================================================================
# MAIN GUI (FIXED: Cursor Lock Logic)
# ==============================================================================
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

        valid_alphas = ['00', '1A', '33', '4D', '59', '66', '80', '99', 'B3', 'CC', 'E6', 'FF']
        self.current_alpha = self.monitor.transparency 
        if self.current_alpha not in valid_alphas: self.current_alpha = "59" 

        # ... (Skin setup omitted - keep existing block) ...
        # [PASTE YOUR EXISTING SKIN SETUP HERE]
        if self.monitor.theme_mode == "ucl":
            bg_base = "0e1e5b"; top_base = "050a2e"
            c_bg = "#" + self.current_alpha + bg_base; c_top = "#" + self.current_alpha + top_base
            bg_widget = '<widget name="main_bg" position="0,0" size="1280,860" backgroundColor="{c_bg}" zPosition="-1" />'.format(c_bg=c_bg)
            try:
                path_jpg = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/ucl.jpg")
                if os.path.exists(path_jpg): bg_widget = '<ePixmap position="0,0" size="1280,860" pixmap="{}" zPosition="-1" alphatest="on" />'.format(path_jpg)
            except: pass
            top_widget = '<widget name="top_bar" position="0,0" size="1280,100" backgroundColor="{c_top}" zPosition="0" />'.format(c_top=c_top)
            header_widget = '<widget name="header_bg" position="0,120" size="1280,40" backgroundColor="{c_bg}" zPosition="0" />'.format(c_bg=c_bg)
            bar_widget = ""; bottom_widget = '<widget name="bottom_bar" position="0,770" size="1280,90" backgroundColor="{c_top}" zPosition="0" />'.format(c_top=c_top)
            fg_title = "#00ffff"; bg_title = "#050a2e"; fg_list_h = "#ffffff"; fg_list_s = "#00ffff"
        else: 
            bg_base = "100015"; bar_base = "38003C"
            c_bg = "#" + self.current_alpha + bg_base; c_bar = "#" + self.current_alpha + bar_base
            bg_widget = '<eLabel position="0,0" size="1280,860" backgroundColor="{c_bg}" zPosition="-1" />'.format(c_bg=c_bg)
            top_widget = '<widget name="top_bar" position="0,0" size="1280,100" backgroundColor="{c_bg}" zPosition="0" />'.format(c_bg=c_bg)
            header_widget = '<widget name="header_bg" position="0,110" size="1280,45" backgroundColor="{c_bg}" zPosition="0" />'.format(c_bg=c_bg)
            bar_widget = '<widget name="bar_bg" position="0,70" size="1280,40" backgroundColor="{c_bar}" zPosition="0" />'.format(c_bar=c_bar)
            bottom_widget = '<widget name="bottom_bar" position="0,770" size="1280,90" backgroundColor="{c_bg}" zPosition="0" />'.format(c_bg=c_bg)
            fg_title = "#00FF85"; bg_title = "#100015"; fg_list_h = "#FFFFFF"; fg_list_s = "#00FF85"

        self.skin = """
        <screen position="center,center" size="1280,860" title="SimplySports" flags="wfNoBorder" backgroundColor="#00000000">
            {bg}
            {top}
            <widget name="top_title" position="0,10" size="1280,60" font="Regular;46" foregroundColor="{fg_t}" backgroundColor="{bg_t}" transparent="1" halign="center" valign="center" zPosition="2" shadowColor="#000000" shadowOffset="-3,-3" />
            <widget name="key_menu" position="40,30" size="300,30" font="Regular;22" foregroundColor="#bbbbbb" backgroundColor="{bg_t}" transparent="1" halign="left" zPosition="2" />
            <widget name="credit" position="940,25" size="300,30" font="Regular;20" foregroundColor="#888888" backgroundColor="{bg_t}" transparent="1" halign="right" zPosition="2" />
            {bar}
            <widget name="league_title" position="50,75" size="500,35" font="Regular;28" foregroundColor="{fg_lh}" backgroundColor="#38003C" transparent="1" halign="left" zPosition="1" />
            <widget name="list_title" position="0,75" size="1280,35" font="Regular;28" foregroundColor="{fg_ls}" backgroundColor="#38003C" transparent="1" halign="center" zPosition="1" />
            {header}
            <widget name="head_status" position="20,125" size="70,30" font="Regular;20" foregroundColor="{fg_ls}" backgroundColor="#0e1e5b" transparent="1" halign="center" zPosition="1" />
            <widget name="head_league" position="100,125" size="80,30" font="Regular;20" foregroundColor="{fg_ls}" backgroundColor="#0e1e5b" transparent="1" halign="center" zPosition="1" />
            <widget name="head_home" position="190,125" size="300,30" font="Regular;20" foregroundColor="{fg_ls}" backgroundColor="#0e1e5b" transparent="1" halign="right" zPosition="1" />
            <widget name="head_score" position="580,125" size="120,30" font="Regular;20" foregroundColor="{fg_ls}" backgroundColor="#0e1e5b" transparent="1" halign="center" zPosition="1" />
            <widget name="head_away" position="790,125" size="300,30" font="Regular;20" foregroundColor="{fg_ls}" backgroundColor="#0e1e5b" transparent="1" halign="left" zPosition="1" />
            <widget name="head_time" position="1090,125" size="170,30" font="Regular;20" foregroundColor="{fg_ls}" backgroundColor="#0e1e5b" transparent="1" halign="right" zPosition="1" />
            <widget name="list" position="0,170" size="1280,590" scrollbarMode="showOnDemand" transparent="1" zPosition="1" />
            {bottom}
            <widget name="key_red" position="40,785" size="280,60" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#F44336" transparent="0" zPosition="2" halign="center" valign="center" />
            <widget name="key_green" position="340,785" size="280,60" font="Regular;24" foregroundColor="#000000" backgroundColor="#00FF85" transparent="0" zPosition="2" halign="center" valign="center" />
            <widget name="key_yellow" position="640,785" size="280,60" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#FFA000" transparent="0" zPosition="2" halign="center" valign="center" />
            <widget name="key_blue" position="940,785" size="300,60" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#42A5F5" transparent="0" zPosition="2" halign="center" valign="center" />
        </screen>
        """.format(bg=bg_widget, top=top_widget, bar=bar_widget, header=header_widget, bottom=bottom_widget, fg_t=fg_title, bg_t=bg_title, fg_lh=fg_list_h, fg_ls=fg_list_s)

        self["top_bar"] = Label(""); self["header_bg"] = Label(""); self["bottom_bar"] = Label(""); self["main_bg"] = Label(""); self["bar_bg"] = Label("")
        self["top_title"] = Label("SimplySports Score Center"); self["league_title"] = Label("LOADING..."); self["list_title"] = Label("")
        self["credit"] = Label("reali22 (v" + CURRENT_VERSION + ")"); self["key_menu"] = Label("MENU: Settings & Tools")
        self["head_status"] = Label("STAT"); self["head_league"] = Label("LGE"); self["head_home"] = Label("HOME"); self["head_score"] = Label("SCORE"); self["head_away"] = Label("AWAY"); self["head_time"] = Label("TIME")
        self["list"] = MenuList([], enableWrapAround=False, content=eListboxPythonMultiContent)
        self["list"].l.setFont(0, gFont("Regular", 26)); self["list"].l.setFont(1, gFont("Regular", 28)); self["list"].l.setFont(2, gFont("Bold", 34)); self["list"].l.setFont(3, gFont("Regular", 20)); self["list"].l.setItemHeight(75) 
        self["key_red"] = Label("League List"); self["key_green"] = Label("Mini Bar"); self["key_yellow"] = Label("Live Only"); self["key_blue"] = Label("Goal Alert: OFF")
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "MenuActions", "EPGSelectActions"], 
            {"cancel": self.close, "red": self.open_league_menu, "green": self.open_mini_bar, "yellow": self.toggle_filter, "blue": self.toggle_discovery, "ok": self.open_game_info, "menu": self.open_settings_menu, "up": self["list"].up, "down": self["list"].down}, -1)
        
        self.container = eConsoleAppContainer(); self.container.appClosed.append(self.download_finished)
        self.onLayoutFinish.append(self.start_ui); self.onClose.append(self.cleanup)

    def start_ui(self):
        self.update_header(); self.update_filter_button(); self.fetch_data()
    def cleanup(self): self.monitor.unregister_callback(self.refresh_ui)
    
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
    def get_logo_path(self, url, filename):
        if not url: return None
        if filename in self.monitor.logo_path_cache: return self.monitor.logo_path_cache[filename]
        file_png = filename + ".png"; target_path = self.logo_path + file_png
        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            self.monitor.logo_path_cache[filename] = target_path
            return target_path
        self.queue_download(url, target_path, filename)
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
        
    @profile_function("SimpleSportsScreen")
    def refresh_ui(self, success):
        self.update_header()
        events = self.monitor.cached_events
        
        # --- CURSOR PRESERVATION LOGIC START ---
        selected_id = None
        current_idx = self["list"].getSelectedIndex()
        if 0 <= current_idx < len(self.current_match_ids):
            selected_id = self.current_match_ids[current_idx]
        
        new_match_ids = []
        # ----------------------------------------

        if not events:
            dummy_entry = ("INFO", "", "No Live Games", "", "", "", False, "", None, None, 0, 0)
            if self.monitor.theme_mode == "ucl": self["list"].setList([UCLListEntry(dummy_entry)])
            else: self["list"].setList([SportListEntry(dummy_entry)])
            self.current_match_ids = []
            return
            
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d"); tom_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        list_content = []
        
        for event in events:
            try:
                status = event.get('status', {}); state = status.get('type', {}).get('state', 'pre')
                clock = status.get('displayClock', ''); local_time = get_local_time_str(event.get('date', ''))
                if ":" in clock: clock = clock.split(':')[0] + "'"
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                league_prefix = event.get('league_name', '')
                h_url = event.get('h_logo_url', ''); a_url = event.get('a_logo_url', '')
                try: h_id = h_url.split('500/')[-1].split('.png')[0]
                except: h_id = '0'
                try: a_id = a_url.split('500/')[-1].split('.png')[0]
                except: a_id = '0'
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
                    if team_h: home = team_h.get('team', {}).get('shortDisplayName') or team_h.get('team', {}).get('displayName') or "Home"; h_score = team_h.get('score', '0')
                    if team_a: away = team_a.get('team', {}).get('shortDisplayName') or team_a.get('team', {}).get('displayName') or "Away"; a_score = team_a.get('score', '0')
                    left_text = home; right_text = away; score_text = str(h_score) + " - " + str(a_score) if state != 'pre' else "vs"
                    try: h_score_int = int(h_score)
                    except: h_score_int = 0
                    try: a_score_int = int(a_score)
                    except: a_score_int = 0
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
                
                entry_data = (status_short, get_league_abbr(league_prefix), str(left_text), str(score_text), str(right_text), str(display_time), goal_side, is_live, h_png, a_png, h_score_int, a_score_int)
                
                if self.monitor.theme_mode == "ucl": list_content.append(UCLListEntry(entry_data))
                else: list_content.append(SportListEntry(entry_data))
                
                new_match_ids.append(match_id)
                
            except: continue
            
        if not list_content: 
            dummy_entry = ("INFO", "", "No Live Games", "", "", "", False, "", None, None, 0, 0)
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
        menu_options = [("Check for Updates", "update"), ("Change Interface Theme", "theme"), ("Window Transparency", "transparency")]
        self.session.openWithCallback(self.settings_menu_callback, ChoiceBox, title="Settings & Tools", list=menu_options)
    def settings_menu_callback(self, selection):
        if selection:
            action = selection[1]
            if action == "update": self.check_for_updates()
            elif action == "theme": self.open_theme_selector()
            elif action == "transparency": self.open_transparency_selector()
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
        if 0 <= idx < len(events):
            selected_event = events[idx]
            self.selected_event_for_reminder = selected_event
            state = selected_event.get('status', {}).get('type', {}).get('state', 'pre')
            if state == 'pre':
                options = [("Game Info / Details", "info"), ("Remind me 12 hours before", 720), ("Remind me 9 hours before", 540), ("Remind me 6 hours before", 360), ("Remind me 3 hours before", 180), ("Remind me 2 hours before", 120), ("Remind me 1 hour before", 60), ("Remind me 15 minutes before", 15), ("Remind me 5 minutes before", 5), ("Delete Reminder", -1), ("Cancel", 0)]
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
        self.monitor.cycle_discovery_mode(); self.update_header()
    def toggle_filter(self): 
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

# ==============================================================================
# MAIN LAUNCHER (FIXED: Handle Exit/Cancel correctly)
# ==============================================================================
def main(session, **kwargs):
    # The callback handles the plugin restart.
    # We set result=None to handle the case where the user presses Exit/Cancel
    # (which calls close() with no arguments).
    def callback(result=None):
        if result is True:
            # Only restart if explicitly requested (True)
            session.openWithCallback(callback, SimpleSportsScreen)
            
    session.openWithCallback(callback, SimpleSportsScreen)

# ==============================================================================
# PLUGIN REGISTRATION (Updated: Icon = picon.png)
# ==============================================================================
def menu(menuid, **kwargs):
    # This checks if the menu being built is the "Main Menu"
    if menuid == "mainmenu":
        return [("SimplySports", main, "simply_sports", 44)]
    return []

def Plugins(**kwargs):
    return [
        # 1. Show in Plugins Browser (Green Button -> Plugins)
        PluginDescriptor(
            name="SimplySports",
            description="Live Sports Scores & Alerts by reali22",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="picon.png",  # <--- FIXED: Using picon.png
            fnc=main
        ),
        
        # 2. Show in Extensions Menu (Blue Button)
        PluginDescriptor(
            name="SimplySports",
            description="Live Sports Scores & Alerts by reali22",
            where=PluginDescriptor.WHERE_EXTENSIONSMENU,
            fnc=main
        ),
        
        # 3. Show in Main Menu (Menu Button)
        PluginDescriptor(
            name="SimplySports",
            description="Live Sports Scores & Alerts by reali22",
            where=PluginDescriptor.WHERE_MENU,
            fnc=menu
        )
    ]
