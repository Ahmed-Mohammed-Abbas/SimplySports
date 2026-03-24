from __future__ import absolute_import, division, print_function
import shutil
import os
import threading
import time
import ssl
import hashlib
import sys
from datetime import datetime
import calendar


# Py2/3 Compatibility
try:
    range = xrange
except NameError:
    pass

# SSL Context fix for older Enigma2/Python to allow HTTPS
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

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

# Twisted Imports - Aliasing ssl to avoid conflict with stdlib ssl
from twisted.internet import reactor, defer
try:
    from twisted.internet import ssl as twisted_ssl
except ImportError:
    twisted_ssl = None
    
from twisted.web.client import Agent, readBody, getPage, downloadPage, HTTPConnectionPool
from twisted.web.http_headers import Headers
from functools import partial
from enigma import eTimer, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, getDesktop, eConsoleAppContainer, gRGB, addFont, eEPGCache, eServiceReference, iServiceInformation, eServiceCenter, ePoint

from Components.Sources.StaticText import StaticText
import json
import datetime
import calendar
import math
import random
import collections
import uuid
import os

def get_device_id():
    """Generates a unique, anonymous ID based on the receiver's MAC address."""
    mac = uuid.getnode()
    return hashlib.sha256(str(mac).encode('utf-8')).hexdigest()[:16]

def push_to_firebase_threaded(url, payload_string):
    """Sends a standard POST request but tells Firebase to treat it as a PATCH.
    This is a bulletproof workaround for older Enigma2 systems that may corrupt 
    native PATCH/PUT headers."""
    def _send():
        try:
            # Handle Python 2 (urllib2) vs Python 3 (urllib.request)
            try:
                import urllib2 as request_module
            except ImportError:
                import urllib.request as request_module
            
            # 1. Build a standard POST request with the payload
            # (In standard urllib, adding data= makes it a POST automatically)
            req = request_module.Request(url, data=payload_string.encode('utf-8'))
            
            # 2. Strictly enforce the JSON Content-Type
            req.add_header('Content-Type', 'application/json')
            
            # 3. FIREBASE MAGIC: Tell Firebase this POST is actually a PATCH
            # This allows us to merge data without worrying about native PATCH support.
            req.add_header('X-HTTP-Method-Override', 'PATCH')
            
            # 4. Send the request natively (Python won't corrupt the headers now)
            request_module.urlopen(req, timeout=10)
            
        except Exception as e:
            print("[SimplySports] Firebase upload failed:", str(e))
            
    # Fire and forget in a background thread so the UI never freezes
    import threading
    t = threading.Thread(target=_send)
    t.daemon = True
    t.start()

# Define your new Firebase Base URL
FIREBASE_URL = "https://simplysports-votes-default-rtdb.europe-west1.firebasedatabase.app"

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
CURRENT_VERSION = "4.6" # A new code to include users' predictions in the sports matches.
GITHUB_BASE_URL = "https://raw.githubusercontent.com/Ahmed-Mohammed-Abbas/SimplySports/main/"
CONFIG_FILE = "/etc/enigma2/simply_sports.json"
LEDGER_FILE = "/etc/enigma2/simply_sports_ledger.json"
LOGO_CACHE_DIR = "/tmp/simplysports/logos"

# ==============================================================================
# FONT FALLBACK - Ensures a valid font is available
# ==============================================================================
def load_fallback_font():
    """Ensure we have a usable font registered as SimplySportFont"""
    font_candidates = [
        "/usr/share/fonts/nmsbd.ttf",
        "/usr/share/fonts/ae_AlMateen.ttf",
        "/usr/share/fonts/Roboto-Regular.ttf",
        "/usr/share/fonts/LiberationSans-Regular.ttf"
    ]
    
    for fpath in font_candidates:
        if os.path.exists(fpath):
            try:
                addFont(fpath, "SimplySportFont", 100, 1)
                return
            except Exception as e:
                print("Failed to load font {}: {}".format(fpath, str(e)))

# Call font loader at module load time
load_fallback_font()

# ==============================================================================
# DEBUG LOGGING
# ==============================================================================
DEBUG_LOG_FILE = "/tmp/simply_sport_debug.log"

try:
    import logging
    from logging.handlers import RotatingFileHandler
    _dbg_logger = logging.getLogger("simplysport_dbg")
    _dbg_logger.setLevel(logging.DEBUG)
    _dbg_logger.propagate = False
    if not _dbg_logger.handlers:
        _dbg_handler = RotatingFileHandler(DEBUG_LOG_FILE, maxBytes=50000, backupCount=1)
        _dbg_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        _dbg_logger.addHandler(_dbg_handler)
except: pass

def log_dbg(msg):
    try: _dbg_logger.debug(str(msg))
    except: pass

# ==============================================================================
# DIAGNOSTIC LOGGING (Verbose - for debugging loading issues)
# ==============================================================================
DIAG_LOG_FILE = "/tmp/simplysport_diag.log"

try:
    import logging
    from logging.handlers import RotatingFileHandler
    _diag_logger = logging.getLogger("simplysport_diag")
    _diag_logger.setLevel(logging.DEBUG)
    _diag_logger.propagate = False
    if not _diag_logger.handlers:
        _diag_handler = RotatingFileHandler(DIAG_LOG_FILE, maxBytes=50000, backupCount=1)
        _diag_handler.setFormatter(logging.Formatter("[%(asctime)s.%(msecs)03d] %(message)s", "%H:%M:%S"))
        _diag_logger.addHandler(_diag_handler)
except: pass

def log_diag(msg):
    """Verbose diagnostic log with millisecond timestamps for tracing API/UI flow."""
    try: _diag_logger.debug(str(msg))
    except: pass

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
    ("USL Championship", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.usl.1/scoreboard"),
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
    ("Davis Cup", "https://site.api.espn.com/apis/site/v2/sports/tennis/davis/scoreboard"),
    ("Billie Jean King Cup", "https://site.api.espn.com/apis/site/v2/sports/tennis/fed/scoreboard"),
    # Rugby
    ("Rugby - Six Nations", "https://site.api.espn.com/apis/site/v2/sports/rugby/270557/scoreboard"),
    ("Rugby - World Cup", "https://site.api.espn.com/apis/site/v2/sports/rugby/164205/scoreboard"),
    ("Rugby - Super Rugby", "https://site.api.espn.com/apis/site/v2/sports/rugby/242041/scoreboard"),
    ("Rugby - Premiership", "https://site.api.espn.com/apis/site/v2/sports/rugby/267979/scoreboard"),
    ("Rugby - Pro14", "https://site.api.espn.com/apis/site/v2/sports/rugby/270559/scoreboard"),
    ("Rugby - Top 14", "https://site.api.espn.com/apis/site/v2/sports/rugby/270560/scoreboard"),
    ("Rugby - Champions Cup", "https://site.api.espn.com/apis/site/v2/sports/rugby/271937/scoreboard"),
    ("Rugby League - NRL", "https://site.api.espn.com/apis/site/v2/sports/rugby-league/nrl/scoreboard"),
    ("Rugby League - Super League", "https://site.api.espn.com/apis/site/v2/sports/rugby-league/super-league/scoreboard"),
    # Cricket
    ("Cricket - IPL", "https://site.api.espn.com/apis/site/v2/sports/cricket/ipl/scoreboard"),
    ("Cricket - T20 World Cup", "https://site.api.espn.com/apis/site/v2/sports/cricket/8604/scoreboard"),
    ("Cricket - ODI World Cup", "https://site.api.espn.com/apis/site/v2/sports/cricket/8605/scoreboard"),
    ("Cricket - Test Matches", "https://site.api.espn.com/apis/site/v2/sports/cricket/1/scoreboard"),
    ("Cricket - ODI", "https://site.api.espn.com/apis/site/v2/sports/cricket/2/scoreboard"),
    ("Cricket - T20I", "https://site.api.espn.com/apis/site/v2/sports/cricket/3/scoreboard"),
    ("Cricket - Big Bash", "https://site.api.espn.com/apis/site/v2/sports/cricket/8251/scoreboard"),
    ("Cricket - The Hundred", "https://site.api.espn.com/apis/site/v2/sports/cricket/8676/scoreboard"),
    ("Cricket - PSL", "https://site.api.espn.com/apis/site/v2/sports/cricket/8674/scoreboard"),
    # Lacrosse
    ("Lacrosse - PLL", "https://site.api.espn.com/apis/site/v2/sports/lacrosse/pll/scoreboard"),
    ("Lacrosse - NCAA Men", "https://site.api.espn.com/apis/site/v2/sports/lacrosse/mens-college-lacrosse/scoreboard"),
    ("Lacrosse - NCAA Women", "https://site.api.espn.com/apis/site/v2/sports/lacrosse/womens-college-lacrosse/scoreboard"),
    # Additional Motorsport
    ("MotoGP", "https://site.api.espn.com/apis/site/v2/sports/racing/motogp/scoreboard"),
    ("Formula E", "https://site.api.espn.com/apis/site/v2/sports/racing/frmle/scoreboard"),
    ("NASCAR Xfinity", "https://site.api.espn.com/apis/site/v2/sports/racing/nascar-xfinity/scoreboard"),
    ("NASCAR Trucks", "https://site.api.espn.com/apis/site/v2/sports/racing/nascar-trucks/scoreboard"),
    # Additional Soccer
    ("Ireland Premier", "https://site.api.espn.com/apis/site/v2/sports/soccer/irl.1/scoreboard"),
    ("Romanian Liga I", "https://site.api.espn.com/apis/site/v2/sports/soccer/rou.1/scoreboard"),
    ("Hungarian NB I", "https://site.api.espn.com/apis/site/v2/sports/soccer/hun.1/scoreboard"),
    ("Moroccan Botola", "https://site.api.espn.com/apis/site/v2/sports/soccer/mar.1/scoreboard"),
    ("Peruvian Primera", "https://site.api.espn.com/apis/site/v2/sports/soccer/per.1/scoreboard"),
    ("Bolivian Primera", "https://site.api.espn.com/apis/site/v2/sports/soccer/bol.1/scoreboard"),
    ("Cypriot First Division", "https://site.api.espn.com/apis/site/v2/sports/soccer/cyp.1/scoreboard"),
    ("FIFA World Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"),
    ("FIFA Women's World Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.wwc/scoreboard"),
    ("FIFA Under-20 World Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world.u20/scoreboard"),
    ("FIFA Under-17 World Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world.u17/scoreboard"),
    ("FIFA Under-17 Women's World Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.wworld.u17/scoreboard"),
    ("FIFA Club World Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.cwc/scoreboard"),
    ("Under-21 International Friendly", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.friendly_u21/scoreboard"),
    ("International U20 Friendly", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.u20.friendly/scoreboard"),
    ("SheBelieves Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.shebelieves/scoreboard"),
    ("FIFA Women's Champions Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.w.champions_cup/scoreboard"),
    ("FIFA Intercontinental Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.intercontinental_cup/scoreboard"),
    ("Men's Olympic Soccer Tournament", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.olympics/scoreboard"),
    ("Women's Olympic Soccer Tournament", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.w.olympics/scoreboard"),
    ("World Cup Qualifying", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.worldq/scoreboard"),
    ("FIFA Women's World Cup Qualifying - Playoff", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.wwcq.ply/scoreboard"),
    ("FIFA Women's World Cup Qualifying - UEFA", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.wworldq.uefa/scoreboard"),
    ("UEFA Champions League Qualifying", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions_qual/scoreboard"),
    ("UEFA Europa League Qualifying", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa_qual/scoreboard"),
    ("UEFA Conference League Qualifying", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa.conf_qual/scoreboard"),
    ("UEFA European Championship", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.euro/scoreboard"),
    ("UEFA Women's European Championship", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.weuro/scoreboard"),
    ("UEFA European Under-21 Championship", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.euro_u21/scoreboard"),
    ("UEFA European Under-19 Championship", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.euro.u19/scoreboard"),
    ("UEFA Women's Nations League", "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.w.nations/scoreboard"),
    ("Premier League Asia Trophy", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.asia_trophy/scoreboard"),
    ("English Women's FA Community Shield", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.w.charity/scoreboard"),
    ("Trofeo Joan Gamper", "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.joan_gamper/scoreboard"),
    ("German Bundesliga Promotion/Relegation Playoff", "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.playoff.relegation/scoreboard"),
    ("German Bundesliga 2 Promotion/Relegation Playoffs", "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.2.promotion.relegation/scoreboard"),
    ("French Trophee des Champions", "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.super_cup/scoreboard"),
    ("Dutch Tweede Divisie", "https://site.api.espn.com/apis/site/v2/sports/soccer/ned.3/scoreboard"),
    ("Dutch Vrouwen Eredivisie", "https://site.api.espn.com/apis/site/v2/sports/soccer/ned.w.1/scoreboard"),
    ("Dutch KNVB Beker Vrouwen", "https://site.api.espn.com/apis/site/v2/sports/soccer/ned.w.knvb_cup/scoreboard"),
    ("NWSL X Liga MX Femenil Summer Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.nwsl.summer.cup/scoreboard"),
    ("USL League One", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.usl.l1/scoreboard"),
    ("USL Super League", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.w.usl.1/scoreboard"),
    ("NCAA Men's Soccer", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.ncaa.m.1/scoreboard"),
    ("NCAA Women's Soccer", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.ncaa.w.1/scoreboard"),
    ("Concacaf W Gold Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/concacaf.w.gold/scoreboard"),
    ("Concacaf W Champions Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/concacaf.w.champions_cup/scoreboard"),
    ("Northern Super League (Canada)", "https://site.api.espn.com/apis/site/v2/sports/soccer/can.w.nsl/scoreboard"),
    ("Mexican Liga de Expansion MX", "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.2/scoreboard"),
    ("Mexican Campeon de Campeones", "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.campeon/scoreboard"),
    ("Mexican Supercopa MX", "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.supercopa/scoreboard"),
    ("CONMEBOL Recopa", "https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.recopa/scoreboard"),
    ("Copa America Qualifying", "https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.america_qual/scoreboard"),
    ("Copa America Femenina", "https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.america.femenina/scoreboard"),
    ("CONMEBOL-UEFA Cup of Champions", "https://site.api.espn.com/apis/site/v2/sports/soccer/global.finalissima/scoreboard"),
    ("Copa Argentina", "https://site.api.espn.com/apis/site/v2/sports/soccer/arg.copa/scoreboard"),
    ("Copa do Brasil", "https://site.api.espn.com/apis/site/v2/sports/soccer/bra.copa_do_brazil/scoreboard"),
    ("Africa Cup of Nations Qualifying", "https://site.api.espn.com/apis/site/v2/sports/soccer/caf.nations_qual/scoreboard"),
    ("CAF Champions League", "https://site.api.espn.com/apis/site/v2/sports/soccer/caf.champions/scoreboard"),
    ("CAF Confederation Cup", "https://site.api.espn.com/apis/site/v2/sports/soccer/caf.confed/scoreboard"),
    ("Nigerian Professional League", "https://site.api.espn.com/apis/site/v2/sports/soccer/nga.1/scoreboard"),
    ("Ghanaian Premier League", "https://site.api.espn.com/apis/site/v2/sports/soccer/gha.1/scoreboard"),
    ("AFC Champions League Two", "https://site.api.espn.com/apis/site/v2/sports/soccer/afc.cup/scoreboard"),
    ("Thai League 1", "https://site.api.espn.com/apis/site/v2/sports/soccer/tha.1/scoreboard"),
    ("Malaysian Super League", "https://site.api.espn.com/apis/site/v2/sports/soccer/mys.1/scoreboard"),
    ("Indonesian Super League", "https://site.api.espn.com/apis/site/v2/sports/soccer/idn.1/scoreboard"),
    ("Singaporean Premier League", "https://site.api.espn.com/apis/site/v2/sports/soccer/sgp.1/scoreboard"),
]

# ==============================================================================
# SPORT TYPE CLASSIFICATION
# ==============================================================================
# Defines how to detect and display different sport types appropriately
SPORT_TYPE_TEAM = "team_vs"      # Soccer, Basketball, Football, Hockey, Baseball
SPORT_TYPE_RACING = "racing"     # F1, NASCAR, IndyCar, MotoGP
SPORT_TYPE_GOLF = "golf"         # PGA, LPGA, Euro Tour
SPORT_TYPE_TENNIS = "tennis"     # ATP, WTA, Davis Cup
SPORT_TYPE_COMBAT = "combat"     # UFC/MMA, Boxing
SPORT_TYPE_CRICKET = "cricket"   # IPL, Test, ODI, T20
SPORT_TYPE_RUGBY = "rugby"       # Six Nations, Super Rugby, NRL

def get_sport_type(league_url):
    """
    Classify sport type based on the ESPN API URL.
    Returns one of: team_vs, racing, golf, tennis, combat, cricket, rugby
    """
    if not league_url:
        return SPORT_TYPE_TEAM
    url_lower = league_url.lower()
    if "/racing/" in url_lower:
        return SPORT_TYPE_RACING
    elif "/golf/" in url_lower:
        return SPORT_TYPE_GOLF
    elif "/tennis/" in url_lower:
        return SPORT_TYPE_TENNIS
    elif "/mma/" in url_lower or "/boxing/" in url_lower:
        return SPORT_TYPE_COMBAT
    elif "/cricket/" in url_lower:
        return SPORT_TYPE_CRICKET
    elif "/rugby" in url_lower:  # Matches rugby and rugby-league
        return SPORT_TYPE_RUGBY
    else:
        return SPORT_TYPE_TEAM  # Default: two-team match format (soccer, basketball, lacrosse, etc.)

def get_sport_id_prefix(league_url):
    """
    Extract a unique string for the sport from the URL to prevent ID collisions.
    Example: .../soccer/... -> 'soccer_', .../basketball/... -> 'basketball_'
    """
    if not league_url: return "team_"
    url_lower = league_url.lower()
    parts = url_lower.split('/')
    # ESPN URLs usually look like .../apis/site/v2/sports/{sport}/{league}/...
    if 'sports' in parts:
        try:
            idx = parts.index('sports')
            if idx + 1 < len(parts):
                return parts[idx+1] + "_"
        except: pass
    
    # Fallback to existing classification
    return get_sport_type(league_url) + "_"

def calculate_tennis_scores(competitors, state):
    """
    Calculate sets won for tennis based on completed sets.
    Ignores the current set if match is LIVE.
    Returns strings (score1, score2).
    """
    s1, s2 = 0, 0
    try:
        if len(competitors) < 2: return "0", "0"
        
        # Check if score is already explicitly provided
        c1, c2 = competitors[0], competitors[1]
        sc1 = c1.get('score', '')
        sc2 = c2.get('score', '')
        
        # If valid scores exist (and at least one is non-zero), trust the API
        # But if both are 0 or empty, we may need to calc (or if it's early match)
        # Actually, ESPN sometimes returns '0' for score but has linescores
        # So we only calc if scores are missing or both 0 AND there are linescores indicating play
        
        has_linescores = c1.get('linescores') or c2.get('linescores')
        trust_api = (sc1 and sc1 != '0') or (sc2 and sc2 != '0')
        
        if trust_api:
            return sc1 or '0', sc2 or '0'
            
        if not has_linescores:
            return sc1 or '0', sc2 or '0'

        # fallback calculation
        ls1 = c1.get('linescores', [])
        ls2 = c2.get('linescores', [])
        count = min(len(ls1), len(ls2))
        
        for i in range(count):
            # If match is LIVE ('in'), the last set in the list is the current playing set -> Don't count it yet
            is_last = (i == count - 1)
            if is_last and state == 'in':
                continue
            
            val1 = 0
            val2 = 0
            try: val1 = float(ls1[i].get('value', 0))
            except: pass
            try: val2 = float(ls2[i].get('value', 0))
            except: pass
            
            if val1 > val2: s1 += 1
            elif val2 > val1: s2 += 1
            
    except: pass
    return str(s1), str(s2)

def get_sport_type_display_name(sport_type):
    """Get human-readable name for sport type"""
    names = {
        SPORT_TYPE_TEAM: "Match",
        SPORT_TYPE_RACING: "Race",
        SPORT_TYPE_GOLF: "Tournament",
        SPORT_TYPE_TENNIS: "Match",
        SPORT_TYPE_COMBAT: "Fight"
    }
    return names.get(sport_type, "Event")

# ==============================================================================
# UNIFIED MATCH SNAPSHOT BUILDER
# ==============================================================================
def build_match_snapshot(event):
    """
    Convert a raw ESPN event dict into a normalized, display-ready MatchSnapshot.
    Called once per event after process_events_data().
    All UI classes read from this -- never parse raw ESPN dicts themselves.
    """
    status      = event.get('status', {})
    s_type      = status.get('type', {})
    state       = s_type.get('state', 'pre')
    
    # --- Status Flags ---
    is_postponed  = (s_type.get('name') == 'STATUS_POSTPONED' or
                     'postponed' in s_type.get('description', '').lower())
    is_suspended  = (s_type.get('name') in ['STATUS_SUSPENDED', 'STATUS_DELAYED'] or
                     'suspended' in s_type.get('description', '').lower() or
                     'resume'    in s_type.get('description', '').lower() or
                     'delay'     in s_type.get('description', '').lower())
    
    # --- Status Short Label (Single Definition) ---
    if is_postponed:              status_short = 'PPD'
    elif is_suspended:            status_short = 'SUSP'
    elif state == 'in':           status_short = 'LIVE'
    elif state == 'post':         status_short = 'FIN'
    else:                         status_short = 'SCH'
    
    # --- Clock (Multi-Sport Support) ---
    raw_clock    = status.get('displayClock', '')
    short_detail = s_type.get('shortDetail', '') or s_type.get('description', '')
    league_url   = event.get('league_url', '')
    
    if 'soccer' in league_url:
        # Soccer: show minute mark "45'"
        if raw_clock and ":" in raw_clock:
            clock_display = raw_clock.split(':')[0] + "'"
        else:
            clock_display = raw_clock or ''
    else:
        # American sports / basketball / hockey / baseball:
        # Use ESPN's own human-readable detail ("2nd Qtr 2:34", "Halftime", etc.)
        clock_display = short_detail or raw_clock or ''
    
    # --- Team / Player Names & Scores ---
    sport_type   = get_sport_type(league_url)
    comps        = event.get('competitions', [{}])[0].get('competitors', [])
    
    h_name = 'Home'; a_name = 'Away'
    h_name_short = 'Home'; a_name_short = 'Away'
    h_score_str = '0'; a_score_str = '0'
    h_score_int = 0;  a_score_int = 0
    h_team_id = ''; a_team_id = ''
    
    if len(comps) >= 2:
        # Identify home/away -- handles missing homeAway tags
        if sport_type == SPORT_TYPE_TENNIS:
            team_h, team_a = comps[0], comps[1]
        else:
            team_h = next((c for c in comps if c.get('homeAway') == 'home'), comps[0])
            team_a = next((c for c in comps if c.get('homeAway') == 'away'),
                         comps[1] if len(comps) > 1 else {})
        
        # Extract names
        if sport_type in [SPORT_TYPE_TENNIS, SPORT_TYPE_COMBAT]:
            ath_h = team_h.get('athlete', {})
            ath_a = team_a.get('athlete', {})
            h_name       = ath_h.get('displayName') or ath_h.get('shortName') or 'Player 1'
            a_name       = ath_a.get('displayName') or ath_a.get('shortName') or 'Player 2'
            h_name_short = ath_h.get('shortName') or h_name
            a_name_short = ath_a.get('shortName') or a_name
            h_team_id    = str(ath_h.get('id', ''))
            a_team_id    = str(ath_a.get('id', ''))
        else:
            t_h = team_h.get('team', {}); t_a = team_a.get('team', {})
            h_name       = t_h.get('displayName', 'Home')
            a_name       = t_a.get('displayName', 'Away')
            h_name_short = t_h.get('shortDisplayName') or t_h.get('abbreviation') or h_name
            a_name_short = t_a.get('shortDisplayName') or t_a.get('abbreviation') or a_name
            h_team_id    = str(t_h.get('id', ''))
            a_team_id    = str(t_a.get('id', ''))
        
        # Extract scores
        if sport_type == SPORT_TYPE_TENNIS:
            h_score_str, a_score_str = calculate_tennis_scores(comps, state)
        else:
            h_score_str = str(team_h.get('score', '0') or '0')
            a_score_str = str(team_a.get('score', '0') or '0')
        
        try:   h_score_int = int(h_score_str)
        except: h_score_int = 0
        try:   a_score_int = int(a_score_str)
        except: a_score_int = 0
    
    # --- Score Display String (Single Definition) ---
    if is_postponed:
        score_str = 'P - P'
    elif state in ('in', 'post') or is_suspended:
        score_str = '{} - {}'.format(h_score_str, a_score_str)
    else:
        score_str = 'VS'
    
    # --- Time Display String (Single Definition) ---
    if state == 'in' and not is_suspended:
        time_str = clock_display or 'LIVE'
    elif state == 'post':
        time_str = get_local_time_str(event.get('date', ''))
    else:
        time_str = get_local_time_str(event.get('date', ''))
    
    # --- Red Card Counting (from scoreboard details) ---
    h_red_cards = 0
    a_red_cards = 0
    if state in ('in', 'post') and len(comps) >= 2:
        try:
            details = event.get('competitions', [{}])[0].get('details', [])
            for play in details:
                is_rc = play.get('redCard', False)
                text_desc = play.get('type', {}).get('text', '').lower()
                if is_rc or ('card' in text_desc and 'red' in text_desc):
                    t_id = str(play.get('team', {}).get('id', ''))
                    if t_id == h_team_id:
                        h_red_cards += 1
                    elif t_id == a_team_id:
                        a_red_cards += 1
        except:
            pass
    
    return {
        # Identity
        'event_id':      str(event.get('id', '')),
        'league_name':   event.get('league_name', ''),
        'league_url':    league_url,
        'sport_type':    sport_type,
        'date':          event.get('date', ''),
        
        # State
        'state':         state,
        'status_short':  status_short,
        'is_live':       state == 'in' and not is_suspended,
        'is_postponed':  is_postponed,
        'is_suspended':  is_suspended,
        'clock':         clock_display,
        'period':        status.get('period', 0),
        
        # Teams
        'h_name':        h_name,
        'a_name':        a_name,
        'h_name_short':  h_name_short,
        'a_name_short':  a_name_short,
        'h_team_id':     h_team_id,
        'a_team_id':     a_team_id,
        
        # Scores
        'h_score_str':   h_score_str,
        'a_score_str':   a_score_str,
        'h_score_int':   h_score_int,
        'a_score_int':   a_score_int,
        'score_str':     score_str,     # "2 - 1" or "VS" or "P - P"
        'time_str':      time_str,      # "45'" or "FT" or "20:30"
        
        # Logos (already set by process_events_data)
        'h_logo_url':    event.get('h_logo_url', ''),
        'a_logo_url':    event.get('a_logo_url', ''),
        'l_logo_url':    event.get('l_logo_url', ''),
        'h_logo_id':     event.get('h_logo_id', ''),
        'a_logo_id':     event.get('a_logo_id', ''),
        'l_logo_id':     event.get('l_logo_id', ''),
        
        # Red Cards
        'h_red_cards':   h_red_cards,
        'a_red_cards':   a_red_cards,
        
        # Raw event reference (for GameInfoScreen detail requests only)
        'raw_event':     event,
    }

def snapshot_passes_filter(snap, filter_mode, today, tomorrow, yesterday):
    """Shared filter for all UI screens. filter_mode: 0=Yesterday, 1=Live, 2=Today, 3=Tomorrow, 4=All"""
    state    = snap['state']
    ev_date  = snap['date'][:10] if snap['date'] else ''
    
    if filter_mode == 0 and ev_date != yesterday: return False
    if filter_mode == 1 and state != 'in':        return False
    if filter_mode == 2 and ev_date != today and state != 'in': return False
    if filter_mode == 3 and ev_date != tomorrow:  return False
    return True

# ==============================================================================
# UNIFIED LOGO LOADER
# ==============================================================================
def load_logo_to_widget(screen, widget_name, url, img_id=None, on_loaded=None):
    """
    Single shared logo loader used by ALL screens.
    Uses ID-based filename. Falls back to URL hash.
    Checks file cache first, then downloads asynchronously.
    """
    if not url:
        try: screen[widget_name].hide()
        except: pass
        return
    
    if not img_id or img_id in ('0', ''):
        img_id = hashlib.md5(url.encode('utf-8')).hexdigest()[:12]
    
    cache_dir = LOGO_CACHE_DIR + "/"
    file_path = cache_dir + str(img_id) + ".png"
    
    # Serve from disk cache (100-byte minimum to reject corrupt files)
    if os.path.exists(file_path) and os.path.getsize(file_path) > 100:
        try:
            ptr = GLOBAL_PIXMAP_CACHE.get(file_path)
            if not ptr and LoadPixmap:
                ptr = LoadPixmap(cached=True, path=file_path)
                if ptr: GLOBAL_PIXMAP_CACHE[file_path] = ptr
            if ptr:
                if screen[widget_name].instance:
                    screen[widget_name].instance.setPixmap(ptr)
                    screen[widget_name].instance.setScale(1)
            elif screen[widget_name].instance:
                screen[widget_name].instance.setPixmapFromFile(file_path)
                screen[widget_name].instance.setScale(1)
            screen[widget_name].show()
            if on_loaded: on_loaded()
        except: pass
        return
    
    # Download asynchronously
    def _on_done(data):
        try:
            if not (os.path.exists(file_path) and os.path.getsize(file_path) > 100):
                return
            GLOBAL_VALID_LOGO_PATHS.add(file_path)
            ptr = None
            if LoadPixmap:
                ptr = LoadPixmap(cached=True, path=file_path)
                if ptr: GLOBAL_PIXMAP_CACHE[file_path] = ptr
            if ptr:
                if screen[widget_name].instance:
                    screen[widget_name].instance.setPixmap(ptr)
                    screen[widget_name].instance.setScale(1)
            elif screen[widget_name].instance:
                screen[widget_name].instance.setPixmapFromFile(file_path)
                screen[widget_name].instance.setScale(1)
            screen[widget_name].show()
            if on_loaded: on_loaded()
        except: pass
    
    try: screen[widget_name].hide()
    except: pass
    downloadPage(url.encode('utf-8'), file_path).addCallback(_on_done).addErrback(lambda e: None)

# ==============================================================================
# LOGO CACHE MANAGER (OPTIMIZED: Non-Blocking)
# ==============================================================================
class LogoCacheManager:
    """Manages local caching of team logos with delayed auto-cleanup"""
    @profile_function("LogoCacheManager")
    def __init__(self):
        self.cache_dir = LOGO_CACHE_DIR
        self._ensure_cache_dir()
        
        # Populate in-memory valid logo paths
        try:
            if os.path.exists(self.cache_dir):
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith('.png'):
                        GLOBAL_VALID_LOGO_PATHS.add(os.path.join(self.cache_dir, filename))
            # Also check /tmp/simplysports/logos
            tmp_dir = "/tmp/simplysports/logos/"
            if os.path.exists(tmp_dir):
                for filename in os.listdir(tmp_dir):
                    if filename.endswith('.png'):
                        GLOBAL_VALID_LOGO_PATHS.add(os.path.join(tmp_dir, filename))
        except: pass
        
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
        except: pass

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
                        GLOBAL_VALID_LOGO_PATHS.discard(file_path)
                count += 1
        except: pass

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
# PIXMAP HELPER (Required for logo display in list entries)
# ==============================================================================
try:
    from Tools.LoadPixmap import LoadPixmap
except ImportError:
    LoadPixmap = None
GLOBAL_PIXMAP_CACHE = collections.OrderedDict()
GLOBAL_PIXMAP_CACHE_LIMIT = 200
GLOBAL_VALID_LOGO_PATHS = set()

def get_scaled_pixmap(path, width, height):
    """Load and return a scaled pixmap from file path, cached in memory"""
    if not path: return None
    cache_key = "{}_{}x{}".format(path, width, height)
    
    if cache_key in GLOBAL_PIXMAP_CACHE:
        val = GLOBAL_PIXMAP_CACHE.pop(cache_key)
        GLOBAL_PIXMAP_CACHE[cache_key] = val
        return val
        
    try:
        from enigma import ePicLoad
        sc = ePicLoad()
        sc.setPara((width, height, 1, 1, 0, 1, "#00000000"))
        if sc.startDecode(path, 0, 0, False) == 0:
            ptr = sc.getData()
            if len(GLOBAL_PIXMAP_CACHE) >= GLOBAL_PIXMAP_CACHE_LIMIT:
                GLOBAL_PIXMAP_CACHE.popitem(last=False)
            GLOBAL_PIXMAP_CACHE[cache_key] = ptr
            return ptr
    except: pass
    
    # Fallback to standard LoadPixmap if ePicLoad fails
    if LoadPixmap:
        ptr = LoadPixmap(cached=True, path=path)
        if ptr: 
            if len(GLOBAL_PIXMAP_CACHE) >= GLOBAL_PIXMAP_CACHE_LIMIT:
                GLOBAL_PIXMAP_CACHE.popitem(last=False)
            GLOBAL_PIXMAP_CACHE[cache_key] = ptr
        return ptr
    return None

# ==============================================================================
# LIST RENDERERS
# ==============================================================================
def SportListEntry(entry):
    try:
        if len(entry) >= 17:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int, has_epg, c_score_bg, l_png, h_red_cards, a_red_cards = entry[:17]
        elif len(entry) >= 15:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int, has_epg, c_score_bg, l_png = entry[:15]
             h_red_cards = 0; a_red_cards = 0
        elif len(entry) >= 14:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int, has_epg, c_score_bg = entry[:14]
             l_png = ""; h_red_cards = 0; a_red_cards = 0
        elif len(entry) >= 13:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int = entry[:12]
             c_score_bg = 0x202020; has_epg = entry[12]; l_png = ""; h_red_cards = 0; a_red_cards = 0
        elif len(entry) >= 12:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int = entry[:12]
             c_score_bg = 0x202020; has_epg = False; l_png = ""; h_red_cards = 0; a_red_cards = 0
        else: return []

        if h_png and h_png not in GLOBAL_VALID_LOGO_PATHS: h_png = None
        if a_png and a_png not in GLOBAL_VALID_LOGO_PATHS: a_png = None
        if l_png and l_png not in GLOBAL_VALID_LOGO_PATHS: l_png = None

        c_text = 0xffffff
        c_dim = 0xDDDDDD 
        c_accent = 0x00FF85 
        c_live = 0xe74c3c   
        c_box = 0x202020    
        c_sel = c_accent 
        
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

        c_status = 0xAAAAAA
        if status == "LIVE": c_status = c_live
        if status == "FIN": c_status = c_accent

        res = [entry]
        h = 90 

        # Extended Limits matching visual enhancements
        font_h = 2; font_a = 2
        if len(left_text) > 27: font_h = 0 
        elif len(left_text) > 23: font_h = 1 
        if len(right_text) > 27: font_a = 0 
        elif len(right_text) > 23: font_a = 1 

        # New Coordinates (Refined for Request 102)
        # Status: 30, 80 (+10w) | League: 110, 80 (+10w) | Home: 195, 575 (-40w, shifted +20)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 30, 0, 80, h-12, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, status, c_status, c_sel))
        
        # Draw League Logo or Fallback Text
        if l_png:
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 125, 20, 50, 50, get_scaled_pixmap(l_png, 50, 50)))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 110, 0, 80, h-12, 1, RT_HALIGN_CENTER|RT_VALIGN_CENTER, league_short, c_dim, c_sel))
        
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 195, 0, 575, h-12, font_h, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, left_text, c_h_name, c_sel))
        
        # Center Block: Logos pulled out. Y=5.
        # Home Logo: 780 (was 800) -> 20px gap to 860.
        if h_png: 
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 780, 5, 60, 60, get_scaled_pixmap(h_png, 60, 60)))
        
        if "-" in score_text:
            parts = score_text.split('-')
            s1 = parts[0].strip()
            s2 = parts[1].strip()
            font_idx = 2 
            max_len = max(len(s1), len(s2))
            if max_len > 8: font_idx = 3 
            elif max_len > 5: font_idx = 0 

            res.append((eListboxPythonMultiContent.TYPE_TEXT, 860, 15, 80, 45, font_idx, RT_HALIGN_CENTER|RT_VALIGN_CENTER, s1, c_h_score, c_sel, c_score_bg, c_score_bg))
            # Hyphen Y=-10
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 940, -10, 40, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "-", c_dim, c_sel))
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 980, 15, 80, 45, font_idx, RT_HALIGN_CENTER|RT_VALIGN_CENTER, s2, c_a_score, c_sel, c_score_bg, c_score_bg))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 860, 0, 200, h-12, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, c_dim, c_sel))

        # Away Logo: 1080 (was 1060) -> 20px gap from 1060.
        if a_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 1080, 5, 60, 60, get_scaled_pixmap(a_png, 60, 60)))
        
        # Away Name: 1150 (was 1130), 520 (Reduced for Time move)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1150, 0, 520, h-12, font_a, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, c_a_name, c_sel))
        
        # Time: 1710, 180 (Ends 1890 -> 30px safe margin)
        font_time = 3 
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1710, 0, 180, h-12, font_time, RT_HALIGN_CENTER|RT_VALIGN_CENTER, time_str, c_dim, c_sel))

        if goal_side == 'home': res.append((eListboxPythonMultiContent.TYPE_TEXT, 840, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "<", c_accent, c_accent))
        elif goal_side == 'away': res.append((eListboxPythonMultiContent.TYPE_TEXT, 1060, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, ">", c_accent, c_accent))

        # Red Card Indicators (image or text fallback)
        if h_red_cards > 0 or a_red_cards > 0:
            rc_img = None
            try:
                rc_path = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/red.jpg")
                if rc_path in GLOBAL_VALID_LOGO_PATHS:
                    rc_img = get_scaled_pixmap(rc_path, 16, 22)
                elif os.path.exists(rc_path):
                    GLOBAL_VALID_LOGO_PATHS.add(rc_path)
                    rc_img = get_scaled_pixmap(rc_path, 16, 22)
            except: pass
            if h_red_cards > 0:
                if rc_img:
                    for i in range(h_red_cards):
                        res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 842, 34 + 24 * i, 16, 22, rc_img))
                else:
                    rc_txt = "RC" if h_red_cards == 1 else "{}RC".format(h_red_cards)
                    res.append((eListboxPythonMultiContent.TYPE_TEXT, 840, 55, 20, 25, 3, RT_HALIGN_CENTER|RT_VALIGN_CENTER, rc_txt, 0xFF3333, c_sel))
            if a_red_cards > 0:
                if rc_img:
                    for i in range(a_red_cards):
                        res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 1062, 34 + 24 * i, 16, 22, rc_img))
                else:
                    rc_txt = "RC" if a_red_cards == 1 else "{}RC".format(a_red_cards)
                    res.append((eListboxPythonMultiContent.TYPE_TEXT, 1060, 55, 20, 25, 3, RT_HALIGN_CENTER|RT_VALIGN_CENTER, rc_txt, 0xFF3333, c_sel))

        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 88, 1880, 2, 0, RT_HALIGN_CENTER, "", 0x303030, 0x303030))
        return res
    except: return []

def RacingListEntry(entry, theme_mode="default"):
    """Racing header row: event name + date/time + status, aligned with SportListEntry columns."""
    try:
        if len(entry) >= 15:
            status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int, has_epg, c_score_bg, l_png = entry[:15]
        elif len(entry) >= 14:
            status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int, has_epg, c_score_bg = entry[:14]
            l_png = ""
        else: return []

        if l_png and l_png not in GLOBAL_VALID_LOGO_PATHS: l_png = None

        c_text = 0xffffff
        c_dim = 0xAAAAAA
        c_accent = 0x00FF85
        c_live = 0xe74c3c
        c_gold = 0xFFD700
        
        if theme_mode == "ucl":
            c_bg = 0x051030
            c_accent = 0x00ffff
            c_gold = 0x00ffff
        else:
            c_bg = 0x100015

        c_status = 0xAAAAAA
        if status == "LIVE": c_status = c_live
        elif status == "FIN": c_status = c_accent

        res = [entry]
        h = 90

        # Left accent bar only
        bar_color = c_live if status == "LIVE" else c_accent if status == "FIN" else c_gold
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 4, h, 0, RT_HALIGN_CENTER, "", bar_color, bar_color))

        # Status badge (aligned at x=15)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 0, 70, h, 1, RT_HALIGN_CENTER|RT_VALIGN_CENTER, status, c_status, c_accent))

        # League Logo (at x=95)
        if l_png:
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 95, 20, 50, 50, get_scaled_pixmap(l_png, 50, 50)))

        # Event Name (at x=160, large font, gold for header)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 160, 5, 1100, 45, 2, RT_HALIGN_LEFT|RT_VALIGN_CENTER, left_text, c_gold, c_accent))

        # Track/Venue below event name (smaller font)
        if right_text and right_text != 'Event':
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 160, 48, 900, 32, 3, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, c_dim, c_accent))

        # Date/Time on the right
        display_t = time_str
        if status == "FIN": display_t = "FINISHED"
        elif status == "LIVE": display_t = "IN PROGRESS"
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1500, 0, 390, h, 1, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, display_t, c_status, c_accent))

        # Bottom separator line
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 87, 1890, 3, 0, RT_HALIGN_CENTER, "", c_accent, c_accent))
        return res
    except: return []

def RacingDriverRow(rank, driver_name, country, is_winner=False, team_logo=None, theme_mode="default"):
    """Single driver row in the main screen racing list, with optional team logo."""
    try:
        c_text = 0xffffff
        c_dim = 0xBBBBBB
        c_accent = 0x00FF85
        c_gold = 0xFFD700
        c_winner = 0xFFD700
        
        if theme_mode == "ucl":
            c_bg = 0x051030
            c_accent = 0x00ffff
            c_gold = 0x00ffff
            c_winner = 0x00ffff
            c_sel = c_accent
        else:
            c_bg = 0x111118
            c_sel = c_accent

        name_color = c_winner if is_winner else c_text
        rank_color = c_gold if is_winner else c_accent

        # Dummy entry_data tuple so MenuList doesn't crash
        entry_data = ("DRV", "", driver_name, "", country, "", None, False, None, None, 0, 0, False, c_bg, "")
        res = [entry_data]
        h = 90

        # Rank position (at x=15, aligned with status column)
        rank_txt = u"P{}".format(rank)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 0, 70, h, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, rank_txt, rank_color, c_sel))

        # Team logo (at x=95, aligned with league logo in header)
        if team_logo and team_logo in GLOBAL_VALID_LOGO_PATHS:
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 95, 20, 50, 50, get_scaled_pixmap(team_logo, 50, 50)))

        # Driver name (at x=160, aligned with event name in header)
        name_x = 160
        res.append((eListboxPythonMultiContent.TYPE_TEXT, name_x, 0, 700, h, 1, RT_HALIGN_LEFT|RT_VALIGN_CENTER, driver_name, name_color, c_sel))

        # Winner badge next to name
        if is_winner:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 870, 0, 120, h, 1, RT_HALIGN_LEFT|RT_VALIGN_CENTER, "WINNER", c_gold, c_sel))

        # Country (at x=1050)
        if country:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 1050, 0, 300, h, 1, RT_HALIGN_LEFT|RT_VALIGN_CENTER, country, c_dim, c_sel))

        # Bottom separator (thin, subtle)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 95, 88, 1800, 2, 0, RT_HALIGN_CENTER, "", 0x252530, 0x252530))
        return res
    except: return []

def RacingSessionRow(session_type, session_status, broadcast, time_str, theme_mode="default"):
    """Session sub-header row: [FP1] Final • Apple TV • Thu 10:30 AM"""
    try:
        c_accent = 0x00FF85
        c_live = 0xe74c3c
        c_dim = 0x888888
        c_text = 0xffffff
        c_gold = 0xFFD700
        
        if theme_mode == "ucl":
            c_bg = 0x051030
            c_accent = 0x00ffff
            c_gold = 0x00ffff
        else:
            c_bg = 0x0a0a0a

        # Session type display names
        session_labels = {
            'FP1': 'Practice 1', 'FP2': 'Practice 2', 'FP3': 'Practice 3',
            'Qual': 'Qualifying', 'Race': 'Race', 'SQ': 'Sprint Qualifying',
            'Sprint': 'Sprint Race'
        }
        label = session_labels.get(session_type, session_type)

        # Status coloring
        if session_status == 'LIVE':
            status_color = c_live
        elif session_status == 'FIN':
            status_color = c_accent
        else:
            status_color = c_dim

        # Build info string
        info_parts = []
        if session_status: info_parts.append(session_status)
        if broadcast: info_parts.append(broadcast)
        if time_str: info_parts.append(time_str)
        info_text = "  |  ".join(info_parts) if info_parts else ""

        entry_data = ("SES", "", label, "", info_text, "", None, False, None, None, 0, 0, False, c_bg, "")
        res = [entry_data]
        h = 90

        # Session type badge with accent bar
        badge_color = c_gold if session_type == 'Race' else c_live if session_type == 'Qual' else c_accent
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 30, 0, 6, h, 0, RT_HALIGN_CENTER, "", badge_color, badge_color))

        # Session label (at x=55)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 55, 0, 280, h, 1, RT_HALIGN_LEFT|RT_VALIGN_CENTER, label, c_text, c_accent))

        # Status + Broadcast + Time info (at x=350)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 350, 0, 1200, h, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, info_text, status_color, c_accent))

        # Bottom separator
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 55, 88, 1840, 2, 0, RT_HALIGN_CENTER, "", 0x1a1a2e, 0x1a1a2e))
        return res
    except: return []


def UCLListEntry(entry):
    try:
        if len(entry) >= 17:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int, has_epg, c_score_bg, l_png, h_red_cards, a_red_cards = entry[:17]
        elif len(entry) >= 15:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int, has_epg, c_score_bg, l_png = entry[:15]
             h_red_cards = 0; a_red_cards = 0
        elif len(entry) >= 14:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int, has_epg, c_score_bg = entry[:14]
             l_png = ""; h_red_cards = 0; a_red_cards = 0
        elif len(entry) >= 13:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int = entry[:12]
             has_epg = entry[12]
             c_score_bg = 0x051030; l_png = ""; h_red_cards = 0; a_red_cards = 0
        elif len(entry) >= 12:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int = entry[:12]
             has_epg = False
             c_score_bg = 0x051030; l_png = ""; h_red_cards = 0; a_red_cards = 0
        else: return []

        if h_png and h_png not in GLOBAL_VALID_LOGO_PATHS: h_png = None
        if a_png and a_png not in GLOBAL_VALID_LOGO_PATHS: a_png = None
        if l_png and l_png not in GLOBAL_VALID_LOGO_PATHS: l_png = None

        c_text = 0xffffff
        c_dim = 0xDDDDDD 
        c_accent = 0x00ffff 
        c_live = 0xff3333   
        c_box = 0x051030    
        c_sel = c_accent 
        
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

        c_status = 0xAAAAAA
        if status == "LIVE": c_status = c_live
        if status == "FIN": c_status = c_accent

        res = [entry]
        h = 90 

        # Extended Limits matching visual enhancements
        font_h = 2; font_a = 2
        if len(left_text) > 27: font_h = 0 
        elif len(left_text) > 23: font_h = 1 
        if len(right_text) > 27: font_a = 0 
        elif len(right_text) > 23: font_a = 1 

        # New Coordinates: matching SportListEntry MARGINS
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 30, 0, 80, h-12, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, status, c_status, c_sel))
        
        # Draw League Logo or Fallback Text
        if l_png:
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 125, 20, 50, 50, get_scaled_pixmap(l_png, 50, 50)))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 110, 0, 80, h-12, 1, RT_HALIGN_CENTER|RT_VALIGN_CENTER, league_short, c_dim, c_sel))
            
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 195, 0, 575, h-12, font_h, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, left_text, c_h_name, c_sel))
        
        if h_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 780, 5, 60, 60, get_scaled_pixmap(h_png, 60, 60)))
        
        if "-" in score_text:
            parts = score_text.split('-')
            s1 = parts[0].strip()
            s2 = parts[1].strip()
            font_idx = 2 
            max_len = max(len(s1), len(s2))
            if max_len > 8: font_idx = 3 
            elif max_len > 5: font_idx = 0 

            res.append((eListboxPythonMultiContent.TYPE_TEXT, 860, 15, 80, 45, font_idx, RT_HALIGN_CENTER|RT_VALIGN_CENTER, s1, c_h_score, c_sel, c_score_bg, c_score_bg))
            # Hyphen lifted to -10
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 940, -10, 40, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "-", c_dim, c_sel))
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 980, 15, 80, 45, font_idx, RT_HALIGN_CENTER|RT_VALIGN_CENTER, s2, c_a_score, c_sel, c_score_bg, c_score_bg))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 860, 0, 200, h-12, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, c_dim, c_sel))

        if a_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 1080, 5, 60, 60, get_scaled_pixmap(a_png, 60, 60)))
        # Away Name: 1150, 520
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1150, 0, 520, h-12, font_a, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, c_a_name, c_sel))
        
        # EPG Indicator (x=1670)
        if has_epg:
             res.append((eListboxPythonMultiContent.TYPE_TEXT, 1670, 0, 35, h, 1, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "EPG", c_accent, c_sel))

        # Time: 1710, 180
        font_time = 3 
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1710, 0, 180, h, font_time, RT_HALIGN_CENTER|RT_VALIGN_CENTER, time_str, c_dim, c_sel))

        if goal_side == 'home': res.append((eListboxPythonMultiContent.TYPE_TEXT, 840, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "<", c_accent, c_accent))
        elif goal_side == 'away': res.append((eListboxPythonMultiContent.TYPE_TEXT, 1060, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, ">", c_accent, c_accent))

        # Red Card Indicators (image or text fallback)
        if h_red_cards > 0 or a_red_cards > 0:
            rc_img = None
            try:
                rc_path = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/red.jpg")
                if rc_path in GLOBAL_VALID_LOGO_PATHS:
                    rc_img = get_scaled_pixmap(rc_path, 16, 22)
                elif os.path.exists(rc_path):
                    GLOBAL_VALID_LOGO_PATHS.add(rc_path)
                    rc_img = get_scaled_pixmap(rc_path, 16, 22)
            except: pass
            if h_red_cards > 0:
                if rc_img:
                    for i in range(h_red_cards):
                        res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 842, 34 + 24 * i, 16, 22, rc_img))
                else:
                    rc_txt = "RC" if h_red_cards == 1 else "{}RC".format(h_red_cards)
                    res.append((eListboxPythonMultiContent.TYPE_TEXT, 840, 55, 20, 25, 3, RT_HALIGN_CENTER|RT_VALIGN_CENTER, rc_txt, 0xFF3333, c_sel))
            if a_red_cards > 0:
                if rc_img:
                    for i in range(a_red_cards):
                        res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 1062, 34 + 24 * i, 16, 22, rc_img))
                else:
                    rc_txt = "RC" if a_red_cards == 1 else "{}RC".format(a_red_cards)
                    res.append((eListboxPythonMultiContent.TYPE_TEXT, 1060, 55, 20, 25, 3, RT_HALIGN_CENTER|RT_VALIGN_CENTER, rc_txt, 0xFF3333, c_sel))

        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 88, 1880, 2, 0, RT_HALIGN_CENTER, "", 0x22182c82, 0x22182c82))
        return res
    except: return []

def InfoListEntry(entry):
    # Entry: (Time, Icon, Text)
    col_text = 0xffffff 
    col_none = None
    
    # Alignment: Standard left-aligned for all entries
    text_align = RT_HALIGN_LEFT | RT_VALIGN_CENTER

    res = [
        entry,
        # 1. Time / Tag (Shifted right to X=140 for overscan protection)
        (eListboxPythonMultiContent.TYPE_TEXT, 140, 0, 190, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0], col_text, col_none)
    ]
    
    # 2. Emoji (Shifted to 340)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 340, 0, 50, 40, 0, RT_HALIGN_CENTER | RT_VALIGN_CENTER, entry[1], col_text, col_none))

    # 3. Text (Shifted to 400)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 400, 0, 1200, 40, 0, text_align, entry[2], col_text, col_none))
    
    return res

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




def SelectionListEntry(name, is_selected, logo_path=None, mode="multi"):
    col_sel = 0x00FF85 if is_selected else 0x9E9E9E
    text_col = 0xFFFFFF if is_selected else 0x9E9E9E
    res = [(name, is_selected)]
    
    base_x = 15
    if mode == "multi":
        check_mark = "[x]" if is_selected else "[ ]"
        res.append((eListboxPythonMultiContent.TYPE_TEXT, base_x, 5, 40, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, check_mark, col_sel, col_sel, None, None))
        base_x += 55
    else:
        text_col = 0xFFFFFF # Always bright for single mode
    
    # Add logo if available
    text_x = base_x
    if logo_path:
        is_valid = logo_path in GLOBAL_VALID_LOGO_PATHS
        if not is_valid and os.path.exists(logo_path) and os.path.getsize(logo_path) > 0:
            GLOBAL_VALID_LOGO_PATHS.add(logo_path)
            is_valid = True
            
        if is_valid:
            try:
                # Resize image to fit 35x35
                pixmap = get_scaled_pixmap(logo_path, 35, 35)
                if pixmap:
                    res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, base_x, 7, 35, 35, pixmap))
                    text_x = base_x + 45  # Shift text after logo
            except:
                pass
    
    res.append((eListboxPythonMultiContent.TYPE_TEXT, text_x, 5, 700 - (text_x - 70), 40, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, name, text_col, text_col, None, None))
    return res

def LeaderboardListEntry(rank, name, score, is_me=False):
    # Colors: Gold for 1st, Accent for others. Cyan for ME.
    c_text = 0xffffff
    c_accent = 0x00FF85
    c_gold = 0xFFD700
    c_me = 0x00ffff
    c_sel = c_accent
    
    res = [(rank, name, score, is_me)]
    h = 60
    
    # 1. Rank
    rank_color = c_gold if rank == 1 else c_accent
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 0, 100, h, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "#" + str(rank), rank_color, c_sel))
    
    # 2. Name
    name_color = c_me if is_me else c_text
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 140, 0, 560, h, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, name, name_color, c_sel))
    
    # 3. Score
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 720, 0, 200, h, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, str(score) + " pts", c_text, c_sel))
    
    return res


# ==============================================================================
# SPORTS MONITOR (FIXED: Stable Sorting)
# ==============================================================================
class SportsMonitor:
    @profile_function("SportsMonitor")
    def __init__(self):
        self.active = False
        self._boot_initialized = False # Track initial boot sequence
        self.discovery_mode = 0  
        self.current_league_index = 0
        self.custom_league_indices = []
        self.is_custom_mode = False
        self.last_scores = {}
        self.last_red_cards = {}
        self.goal_flags = {}
        self.last_states = {}
        self.notified_events = set()  # Track fired notifications: {(match_id, event_type)}
        self.filter_mode = 1 
        self.theme_mode = "default"
        self.transparency = "59"
        
        self.logo_path_cache = {} 
        self.missing_logo_cache = set() 
        self.pending_logos = set()
        self.voter_name = "Anonymous"
        self.current_league_index = 0
        self.reminders = [] 
        
        self.timer = eTimer()
        safe_connect(self.timer, self.check_goals)
            
        self.session = None
        self.cached_events = [] 
        self.match_snapshots = {}  # Unified snapshots for all UI consumers
        self.callbacks = []
        self.status_message = "Initializing..."
        self.notification_queue = []
        self.notification_active = False
        self.current_toast = None  # Reference to active GoalToast for live updates
        self.current_toast_match = None  # (home, away) tuple of active toast
        self.has_changes = True  # Track if data changed since last UI refresh
        
        # Batching variables
        self.batch_queue = []
        self.batch_remaining = 0
        self.batch_is_active = False
        self.batch_timer = eTimer()
        safe_connect(self.batch_timer, self.finalize_batch)
        
        self.logo_cache = LogoCacheManager()
        self.last_update = 0
        self.cache_file = "/tmp/simplysports/cache.json"
        
        # Optimization: Persistent Agent with Connection Pool & Request Management
        self.pool = HTTPConnectionPool(reactor)
        self.pool.maxPersistentPerHost = 50  # Allow all 67 leagues to connect concurrently
        self.pool._factory.noisy = False
        self.agent = Agent(reactor, pool=self.pool)
        self.active_requests = set()
        self.last_cache_save = 0
        self.last_callback_time = 0
        self.pending_callback = None
        self.callback_debounce_timer = eTimer()
        safe_connect(self.callback_debounce_timer, self._execute_pending_callback)
        self.event_map = {} # optimization: O(1) lookup
        self.live_summary_timer = None  # Timer for direct summary fetches for live American 
        self._summary_fail_counts = {}   # {eid: consecutive_fail_count}
        self._dead_summary_eids = set()  # EIDs that failed 3+ times, skip for session
        
        self.load_cache()
        
        self.load_config()
        self.load_ledger()
        
        self.boot_timer = eTimer()
        
        try: self.boot_timer.callback.append(self.check_goals)
        except AttributeError: self.boot_timer.timeout.get().append(self.check_goals)
        self.boot_timer.start(5000, True)
        
        self._boot_initialized = True # Mark initialization complete

    def set_session(self, session):
        self.session = session
        # AUTO-START: On first session set (boot via WHERE_SESSIONSTART),
        # load saved config so monitoring and notifications begin immediately
        if not getattr(self, '_boot_initialized', False):
            self._boot_initialized = True
            try:
                self.load_config()
            except: pass
    def register_callback(self, func):
        if func not in self.callbacks: 
            self.callbacks.append(func)
            self.ensure_timer_state() # Ensure timer starts if it was idle
    def unregister_callback(self, func):
        if func in self.callbacks: 
            self.callbacks.remove(func)
            self.ensure_timer_state() # Allow idle shutdown if all UIs closed

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
                    self.menu_section = data.get("menu_section", "all")
                    self.show_in_menu = bool(data.get("show_in_menu", True))
                    self.minibar_color_mode = data.get("minibar_color_mode", "default")
                    self.voter_name = data.get("voter_name", "Anonymous")
                    
                    # FIX: Ensure timer state is set correctly (handles active and reminders)
                    try:
                        self.ensure_timer_state()
                    except Exception as e:
                        log_dbg("ensure_timer_state error during load_config: " + str(e))
            except Exception as e:
                log_dbg("load_config ERROR: " + str(e))
                self.defaults()
        else: self.defaults()

    def defaults(self):
        self.filter_mode = 1; self.theme_mode = "default"; self.transparency = "59"
        self.discovery_mode = 0; self.reminders = []; self.menu_section = "all"
        self.show_in_menu = True; self.minibar_color_mode = "default"
        self.voter_name = "Anonymous"
        # FIX Bug 1: resolved_bets must be a dict (not a list) to support key-based
        # lookups and assignment used throughout the gamification engine.
        # Also ensure total_predictions and correct_predictions are always present.
        self.ledger = {"total_score": 0, "pending_bets": {}, "resolved_bets": {}, "total_predictions": 0, "correct_predictions": 0}

    def save_config(self):
        data = {
            "league_index": self.current_league_index, "filter_mode": self.filter_mode,
            "theme_mode": self.theme_mode, "transparency": self.transparency,
            "discovery_mode": self.discovery_mode, "active": self.active,
            "custom_indices": self.custom_league_indices, "is_custom_mode": self.is_custom_mode,
            "reminders": self.reminders, "menu_section": self.menu_section,
            "show_in_menu": self.show_in_menu, "minibar_color_mode": self.minibar_color_mode,
            "voter_name": self.voter_name
        }
        try:
            with open(CONFIG_FILE, "w") as f: json.dump(data, f)
        except: pass

    def load_ledger(self):
        try:
            if os.path.exists(LEDGER_FILE):
                with open(LEDGER_FILE, "r") as f:
                    self.ledger = json.load(f)
            else:
                self.ledger = {"total_score": 0, "pending_bets": {}, "resolved_bets": {}, "total_predictions": 0, "correct_predictions": 0}
            
            # FIX: Ensure resolved_bets is a dictionary (V2 requirement)
            if not isinstance(self.ledger.get("resolved_bets"), dict):
                # Migration: if it was a list, just convert to empty dict (safer than trying to guess structure)
                self.ledger["resolved_bets"] = {}
                
            # Migration logic for old /tmp votes
            old_votes_file = "/tmp/simplysports_votes.json"
            if os.path.exists(old_votes_file):
                try:
                    with open(old_votes_file, "r") as f:
                        old_data = json.load(f)
                        for eid in old_data:
                            eid_str = str(eid)
                            if eid_str not in self.ledger["resolved_bets"]:
                                self.ledger["resolved_bets"][eid_str] = {"legacy": True}
                    self.save_ledger()
                except: pass
        except:
            self.ledger = {"total_score": 0, "pending_bets": {}, "resolved_bets": {}, "total_predictions": 0, "correct_predictions": 0}

    def save_ledger(self):
        """Saves the current ledger to disk, pruning resolved bets older than 30 days."""
        import json
        import time
        
        if not hasattr(self, 'ledger') or not self.ledger:
            return

        # --- THE JANITOR: 30-Day Pruning Routine ---
        thirty_days_in_seconds = 30 * 24 * 60 * 60
        current_time = int(time.time())
        
        resolved = self.ledger.get("resolved_bets", {})
        if isinstance(resolved, dict):
            stale_keys = []
            
            for event_id, bet_data in resolved.items():
                # Get the timestamp. If it doesn't exist (older bets), assign it today's time
                bet_time = bet_data.get("timestamp")
                if bet_time is None:
                    bet_data["timestamp"] = current_time
                    continue
                    
                # If the bet is older than 30 days, mark it for deletion
                if (current_time - int(bet_time)) > thirty_days_in_seconds:
                    stale_keys.append(event_id)
            
            # Delete the stale bets from the dictionary
            for event_id in stale_keys:
                del resolved[event_id]
                print("[SimplySports Janitor] Deleted stale bet:", event_id)
        # -------------------------------------------

        try:
            # FIX Bug 4: Always use the module-level LEDGER_FILE constant directly.
            # getattr(self, 'LEDGER_FILE', ...) never resolved to the instance because
            # LEDGER_FILE is not an instance attribute — it is a module-level constant.
            # The silent fallback to the hardcoded string meant any rename of the
            # constant at the top of the file would be ignored here, causing a
            # path mismatch between save and load after a restart.
            with open(LEDGER_FILE, "w") as f:
                json.dump(self.ledger, f)
        except Exception as e:
            print("[SimplySports] Failed to save ledger:", e)
    def add_pending_bet(self, event_id, prediction, sport, league, h_name="Home", a_name="Away"):
        eid = str(event_id)
        if eid not in self.ledger["pending_bets"] and eid not in self.ledger["resolved_bets"]:
            self.ledger["pending_bets"][eid] = {
                "prediction": prediction, # 'home', 'away', or 'draw'
                "sport": sport,
                "league": league,
                # Store team names at bet time so the Personal Profile screen can
                # show a meaningful "Arsenal vs Chelsea" label even after the match
                # has dropped out of the live event_map cache.
                "h_name": h_name,
                "a_name": a_name,
                "timestamp": int(time.time())
            }
            self.save_ledger()
            self.evaluate_pending_bets()

    def evaluate_pending_bets(self):
        if not self.ledger.get("pending_bets"): return
        
        log_diag("REFREE: Evaluating {} pending bets...".format(len(self.ledger["pending_bets"])))
        for eid, bet in list(self.ledger["pending_bets"].items()):
            sport = bet.get("sport", "soccer")
            league = bet.get("league", "")
            url = "https://site.api.espn.com/apis/site/v2/sports/{}/{}/summary?event={}".format(sport, league, eid)
            
            if url in self.active_requests: continue
            
            self.active_requests.add(url)
            d = self.agent.request(b'GET', url.encode('utf-8'))
            d.addCallback(readBody)
            d.addCallback(self._on_summary_resolved, eid, bet)
            d.addErrback(lambda x: log_dbg("Referee error for {}: {}".format(eid, x)))
            d.addBoth(lambda x: self.active_requests.discard(url))

    def _on_summary_resolved(self, body, eid, bet):
        try:
            data = json.loads(body)
            header = data.get('header', {})
            comps = header.get('competitions', [{}])
            if not comps: return
            
            comp = comps[0]
            status = comp.get('status', {})
            state = status.get('type', {}).get('state', 'pre')
            
            if state == 'post':
                # Match finished! Calculate winner from scores (V2 Logic)
                competitors = comp.get('competitors', [])
                h_score = 0
                a_score = 0
                
                for c in competitors:
                    score_val = int(c.get('score', 0))
                    if c.get('homeAway') == 'home':
                        h_score = score_val
                    else:
                        a_score = score_val
                
                # Determine actual winner
                if h_score > a_score: actual_winner = 'home'
                elif a_score > h_score: actual_winner = 'away'
                else: actual_winner = 'draw'
                
                prediction = bet.get("prediction")
                sport = bet.get("sport", "soccer")
                current_score = int(self.ledger.get("total_score", 0))
                total_preds = int(self.ledger.get("total_predictions", 0)) + 1
                correct_preds = int(self.ledger.get("correct_predictions", 0))
                
                # Initialize sport-specific tracking
                if "sport_stats" not in self.ledger:
                    self.ledger["sport_stats"] = {}
                if sport not in self.ledger["sport_stats"]:
                    self.ledger["sport_stats"][sport] = {"score": 0, "total": 0, "correct": 0}
                
                self.ledger["sport_stats"][sport]["total"] += 1
                
                if prediction == actual_winner:
                    current_score += 1
                    correct_preds += 1
                    self.ledger["sport_stats"][sport]["score"] += 1
                    self.ledger["sport_stats"][sport]["correct"] += 1
                    log_diag("REFREE: Match {} result ({}) matched prediction! Score: {}".format(eid, actual_winner, current_score))
                else:
                    current_score -= 1
                    self.ledger["sport_stats"][sport]["score"] -= 1
                    log_diag("REFREE: Match {} result ({}) MISMATCHED prediction ({}). Score: {}".format(eid, actual_winner, prediction, current_score))
                
                # Update Ledger with detailed results (V2 Requirement)
                self.ledger["total_score"] = current_score
                self.ledger["total_predictions"] = total_preds
                self.ledger["correct_predictions"] = correct_preds
                
                self.ledger["resolved_bets"][eid] = {
                    "prediction": prediction,
                    "result": actual_winner,
                    "score": "{}-{}".format(h_score, a_score),
                    # Carry team names from the pending bet so the Personal Profile
                    # screen can show "Arsenal vs Chelsea" after the match is over.
                    "h_name": bet.get("h_name", "Home"),
                    "a_name": bet.get("a_name", "Away"),
                    # FIX Bug 6: Use the current time (moment of resolution) rather than
                    # the original bet placement timestamp.  The 30-day pruning janitor in
                    # save_ledger() measures age from this timestamp.  Reusing the placement
                    # time would shorten the retention window for postponed matches — a match
                    # placed 29 days ago would be pruned the very next save after resolution.
                    "timestamp": int(time.time())
                }
                
                # Clean up pending
                if eid in self.ledger["pending_bets"]:
                    del self.ledger["pending_bets"][eid]
                
                self.save_ledger()
                self.sync_leaderboard()
        except Exception as e:
            log_dbg("Referee processing error for {}: {}".format(eid, e))

    def sync_leaderboard(self):
        device_id = get_device_id()
        url = "{}/leaderboard/{}.json".format(FIREBASE_URL, device_id)
        
        # Calculate accuracy safely
        total_preds = int(self.ledger.get("total_predictions", 0))
        correct_preds = int(self.ledger.get("correct_predictions", 0))
        accuracy = (float(correct_preds) / total_preds * 100.0) if total_preds > 0 else 0.0
        total_score = self.ledger.get("total_score", 0)

        # Compute this player's current badge so other users see it on their
        # leaderboard without having to recalculate it client-side.
        badge = get_rank_badge(total_score, accuracy)

        payload = json.dumps({
            "score": total_score,
            "name": self.voter_name,
            "accuracy": round(accuracy, 1),
            "total_bets": total_preds,
            "sports": self.ledger.get("sport_stats", {}),
            "badge": badge,
            "timestamp": int(time.time())
        })
        
        push_to_firebase_threaded(url, payload)

    # ... (Helpers omitted for brevity, assuming standard methods exist) ...
    def toggle_theme(self):
        if self.theme_mode == "default": self.theme_mode = "ucl"
        else: self.theme_mode = "default"
        self.save_config(); return self.theme_mode
    def toggle_filter(self):
        old = self.filter_mode
        self.filter_mode = (self.filter_mode + 1) % 5
        log_diag("MONITOR.toggle_filter: {} -> {} (0=Yesterday,1=Live,2=Today,3=Tomorrow,4=All)".format(old, self.filter_mode))
        self.save_config(); return self.filter_mode
    def cycle_discovery_mode(self):
        old = self.discovery_mode
        self.discovery_mode = (self.discovery_mode + 1) % 3
        
        # FIX: active flag only controlled by mode, but timer checks reminders too
        self.active = (self.discovery_mode > 0)
        log_diag("MONITOR.cycle_discovery_mode: {} -> {} (0=OFF,1=VISUAL,2=SOUND) active={}".format(old, self.discovery_mode, self.active))
        
        # FIX: Clear pending notifications immediately when toggling OFF
        # This prevents queued notifications from showing after disabling Goal Alert
        if self.discovery_mode == 0:
            self.notification_queue = []
            self.notification_active = False
        
        self.ensure_timer_state()
        self.save_config()
        self._trigger_callbacks(True) # Ensure immediate UI update (button label)
        return self.discovery_mode

    def toggle_activity(self): return self.cycle_discovery_mode()

    def _get_timer_interval(self, live_count=0):
        """Return timer interval in ms."""
        # UI is active or Background-Live: 30s
        if len(self.callbacks) > 0 or live_count > 0:
            return 30000 
            
        # Idle background: 300s (5 mins)
        return 300000

    def ensure_timer_state(self):
        # Timer should run if: 
        # 1. Active (Discovery Mode ON)
        # 2. OR Reminders exist
        # 3. OR UI is active (callbacks registered) to ensure main screen updates
        should_run = self.active or (len(self.reminders) > 0) or (len(self.callbacks) > 0)
        
        if should_run:
            new_interval = self._get_timer_interval()
            if not self.timer.isActive():
                # ENSURE: single_shot=False (2nd param) to repeat automatically
                self.timer.start(new_interval, False)
                # If we just started, run a check immediately
                self.check_goals()
            else:
                # Timer already running - refresh interval ONLY if it changed (e.g. Screen opened)
                if getattr(self, '_last_interval', None) != new_interval:
                    self.timer.start(new_interval, False)
            self._last_interval = new_interval
        else:
            if self.timer.isActive():
                self.timer.stop()

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
        
        # FIX: Stop any running batch operations from previous custom mode
        self.batch_is_active = False
        if self.batch_timer.isActive(): self.batch_timer.stop()
        self.batch_queue = []
        self.active_requests.clear() # Cancel/Ignore pending requests

        if index >= 0 and index < len(DATA_SOURCES):
            self.current_league_index = index; self.last_scores = {}; self.last_red_cards = {}; self.last_states = {}; self.notified_events = set()
            # FIX: Clear cache to remove old events from previous selection
            self.event_map = {}; self.cached_events = []
            self.save_config()
            # Restart timer with single-league interval (60s)
            if self.timer.isActive(): self.timer.start(self._get_timer_interval(), False)
            self.check_goals()
    def set_custom_leagues(self, indices):
        self.custom_league_indices = indices; self.is_custom_mode = True; self.last_scores = {}; self.last_red_cards = {}; self.last_states = {}; self.notified_events = set()
        
        # FIX: Stop any running batch operations from previous custom mode
        self.batch_is_active = False
        if self.batch_timer.isActive(): self.batch_timer.stop()
        self.batch_queue = []
        self.active_requests.clear() # Cancel/Ignore pending requests

        # FIX: Clear cache to remove old events from previous selection
        self.event_map = {}; self.cached_events = []
        self.save_config()
        # Restart timer with custom-mode interval (180s)
        if self.timer.isActive(): self.timer.start(self._get_timer_interval(), False)
        self.check_goals()
    def add_reminder(self, match_name, trigger_time, league_name, h_logo, a_logo, label, sref=None, h_id=None, a_id=None):
        new_rem = {"match": match_name, "trigger": trigger_time, "league": league_name, "h_logo": h_logo, "a_logo": a_logo, "label": label, "sref": sref}
        for r in self.reminders:
            if r["match"] == match_name and r["trigger"] == trigger_time: return
        
        # FIX: Prefetch logos immediately using IDs (needed for consistent storage)
        if h_logo: 
            if not h_id: h_id = hashlib.md5(h_logo.encode('utf-8')).hexdigest()[:10]
            self.prefetch_logo(h_logo, h_id)
        if a_logo: 
            if not a_id: a_id = hashlib.md5(a_logo.encode('utf-8')).hexdigest()[:10]
            self.prefetch_logo(a_logo, a_id)

        self.reminders.append(new_rem); self.save_config()
        # FIX: Ensure timer starts if it wasn't running
        self.ensure_timer_state()

    def remove_reminder(self, match_name):
        initial_len = len(self.reminders); self.reminders = [r for r in self.reminders if r["match"] != match_name]
        if len(self.reminders) < initial_len: 
            self.save_config()
            # FIX: Stop timer if no reminders and not active
            self.ensure_timer_state()
            return True
        return False
    def check_reminders(self):
        now = time.time(); active_reminders = []; reminders_triggered = False
        for rem in self.reminders:
            if now >= rem["trigger"]:
                if rem.get("sref"):
                    # Interactive Zap Reminder
                    self.trigger_zap_alert(rem)
                else:
                    # Standard Notification
                    self.queue_notification(rem.get("match", rem.get("eid", "")), rem["label"], "Reminder", 
                        event_type="reminder")
                    self.play_stend_sound()
                reminders_triggered = True
            else: active_reminders.append(rem)
        if reminders_triggered: self.reminders = active_reminders; self.save_config()

    def trigger_zap_alert(self, rem):
        if self.session:
            def _open_zap():
                # Use ZapNotificationScreen instead of MessageBox
                self.session.openWithCallback(partial(self.zap_confirmation_callback, domain=(rem.get("sref"),)), 
                    ZapNotificationScreen, 
                    rem["match"], 
                    rem["league"], 
                    rem.get("h_logo", ""), 
                    rem.get("a_logo", ""), 
                    rem.get("sref"), 
                    timeout_seconds=30
                )
            
            reactor.callLater(0, _open_zap)

    def zap_confirmation_callback(self, answer, domain=None):
        if answer and domain:
            try:
                sref = domain[0]
                from enigma import eServiceReference
                self.session.nav.playService(eServiceReference(sref))
            except: pass


    @profile_function("SportsMonitor")
    def check_goals(self, from_ui=False):
        log_diag("CHECK_GOALS: ENTER from_ui={} active={} is_custom={} discovery_mode={} filter_mode={} cached_events={} batch_remaining={} active_requests={} callbacks={}".format(
            from_ui, self.active, self.is_custom_mode, self.discovery_mode, self.filter_mode, len(self.cached_events), self.batch_remaining, len(self.active_requests), len(self.callbacks)))
        self.check_reminders()
        self.evaluate_pending_bets()

        # Guard: Data fetching happens if:
        # 1. Goal Alert is ON (self.active)
        # 2. OR explicitly requested by UI (from_ui)
        # 3. OR UI is listening (self.callbacks) - ensures main screen updates when Goal Alert is OFF
        if not self.active and not from_ui and not self.callbacks:
            log_diag("CHECK_GOALS: SKIPPED (not active, not from_ui, no callbacks)")
            return

        # Show cached data or loading state - but NOT during an active batch
        # (batch processing shows data via finalize_batch at the end)
        if not self.batch_is_active:
            if not self.cached_events:
                self.status_message = "Loading Data..."
                self._trigger_callbacks(False)
        # Use persistent agent
        if not self.is_custom_mode:
            try:
                name, url = DATA_SOURCES[self.current_league_index]
                log_diag("CHECK_GOALS: SINGLE LEAGUE '{}' url_in_active={}".format(name, url in self.active_requests))
                if url not in self.active_requests:
                    self.active_requests.add(url)
                    d = self.agent.request(b'GET', url.encode('utf-8'))
                    d.addCallback(readBody)
                    d.addCallback(self.parse_single_json, name, url) 
                    d.addErrback(self.handle_error)
                    d.addBoth(lambda x: self.active_requests.discard(url)) 
            except: pass
            

        else:
            if not self.custom_league_indices:
                log_diag("CHECK_GOALS: CUSTOM MODE - No leagues selected")
                self.status_message = "No Leagues Selected"
                self.cached_events = []
                self._trigger_callbacks(True)
                return
            
            # Mark batch as active
            self.batch_is_active = True
            self.batch_queue = []
            selected_indices = [idx for idx in self.custom_league_indices if idx < len(DATA_SOURCES)]
            self.batch_remaining = len(selected_indices)
            log_diag("CHECK_GOALS: CUSTOM MODE - Starting batch for {} leagues".format(len(selected_indices)))
            
            # 10-second safety timer
            self.batch_timer.start(10000, True)
            self.batch_first_response = None
            
            fired = 0; skipped = 0
            for idx in selected_indices:
                name, url = DATA_SOURCES[idx]
                # FIX: We want a fresh copy. We shouldn't skip if it's already in active_requests
                # otherwise batch_remaining drops immediately and batch finalizes prematurely
                # while ghost old requests are still ticking.
                # if url in self.active_requests:
                #     self.batch_remaining -= 1
                #     skipped += 1
                #     continue
                
                self.active_requests.add(url)
                d = self.agent.request(b'GET', url.encode('utf-8'))
                d.addCallback(readBody)
                d.addCallback(self.collect_batch_response_incremental, name, url)
                d.addErrback(self.collect_batch_error, url)
                d.addBoth(lambda x, u=url: self.active_requests.discard(u))
                
                # 10-second per-request timeout
                timeout_call = reactor.callLater(10, d.cancel)
                d.addBoth(lambda x, tc=timeout_call: tc.cancel() if tc.active() else None)
                
                fired += 1
            log_diag("CHECK_GOALS: CUSTOM MODE - Fired {} requests (10s timeout), skipped {}, batch_remaining={}".format(fired, skipped, self.batch_remaining))

    def _save_cache_bg(self):
        try:
            cache_dir = os.path.dirname(self.cache_file)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            
            # Take a shallow copy of the list to prevent mid-iteration modification
            events_copy = list(self.cached_events)
            data = {
                'timestamp': self.last_update,
                'events': events_copy
            }
            with open(self.cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print("[SportsMonitor] Cache Save BG Error: ", e)

    def save_cache(self):
        # Optimization: Write Coalescing (Max once every 2 mins)
        if time.time() - self.last_cache_save < 120 and self.cached_events:
            return

        self.last_cache_save = time.time()
        
        import threading
        t = threading.Thread(target=self._save_cache_bg)
        t.daemon = True
        t.start()

    def load_cache(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self.last_update = data.get('timestamp', 0)
                    events = data.get('events', [])
                    # Quick validation
                    if isinstance(events, list):
                        self.cached_events = events
                        self.match_snapshots = {}
                        self.event_map = {}
                        for ev in self.cached_events:
                            eid = ev.get('id')
                            if eid:
                                str_eid = str(eid)
                                self.match_snapshots[str_eid] = build_match_snapshot(ev)
                                self.event_map[str_eid] = ev
                        self.status_message = "Restored from Cache"
        except Exception as e:
             print("[SportsMonitor] Cache Load Error: ", e)
             self.cached_events = []

    def collect_batch_error(self, failure, url=None):
        """Handle request errors - only fires for network/timeout failures"""
        if not self.batch_is_active:
            log_diag("BATCH_ERROR: DROPPED (batch not active) url={}".format(url))
            if url: self.active_requests.discard(url)
            return
        # FIX: Ignore ghost requests
        if url and url not in self.active_requests:
            log_diag("BATCH_ERROR: DROPPED (ghost deferred) url={}".format(url))
            return
        log_diag("BATCH_ERROR: url={} error={} batch_remaining={}".format(url, str(failure)[:100], self.batch_remaining - 1))
        if url: self.active_requests.discard(url)
        self.batch_remaining -= 1
        if self.batch_remaining <= 0:
            self.finalize_batch()

    def collect_batch_response_incremental(self, body, name, url):
        """Process each response immediately. MUST NEVER RAISE to prevent double-decrement."""
        try:
            if not self.batch_is_active or not self.is_custom_mode:
                self.active_requests.discard(url)
                return
            
            # FIX: Ignore ghost requests entirely (do not decrement batch_remaining)
            if url not in self.active_requests:
                log_diag("BATCH_RESPONSE: DROPPED (ghost deferred) url={}".format(url))
                return
            
            if self.batch_first_response is None:
                self.batch_first_response = time.time()
            
            self.active_requests.discard(url)
            
            # Process data
            try:
                self.process_events_data([(body, name, url)], append_mode=True)
            except Exception as e:
                log_diag("BATCH_RESPONSE: ERROR processing '{}': {}".format(name, e))
            
            self.batch_remaining -= 1
            log_diag("BATCH_RESPONSE: '{}' remaining={}".format(name, self.batch_remaining))
            
            if self.batch_remaining <= 0:
                self.finalize_batch()
        except Exception as e:
            # Never let exceptions propagate to the deferred chain
            log_diag("BATCH_RESPONSE: UNEXPECTED ERROR in '{}': {}".format(name, e))
            self.active_requests.discard(url)
            self.batch_remaining -= 1
            if self.batch_remaining <= 0:
                self.finalize_batch()

    def finalize_batch(self):
        """Cleanup after batch processing"""
        if not self.batch_is_active:
            return
        
        # Mark as inactive immediately to prevent double-firing
        self.batch_is_active = False
        
        if not self.is_custom_mode:
            return
        
        if self.batch_timer.isActive():
            self.batch_timer.stop()
        
        # REAPING: Removed global reaping logic. 
        # Stability fix: Reaping is now league-specific in _run_lazy_process_events_data
        # to prevent matches from disappearing if one league request fails.
        # Stability fix: Reaping is now handled during incremental processing.

        self.status_message = ""
        self.batch_queue = []
        self.batch_remaining = 0
        self.batch_first_response = None
        
        self.save_cache()
        
        # FINAL REBUILD: One full snapshot rebuild after all batch responses
        self.match_snapshots = {}
        for ev in self.cached_events:
            eid = ev.get('id')
            if eid:
                self.match_snapshots[str(eid)] = build_match_snapshot(ev)
                
        # Remove stale snapshot keys for reaped events
        stale_keys = [k for k in self.match_snapshots if k not in self.event_map]
        for k in stale_keys:
            del self.match_snapshots[k]
            
        log_dbg("FINALIZE_BATCH: Final snapshot rebuild \u2014 {} snapshots".format(len(self.match_snapshots)))
        
        # Evaluate goals ONCE after all batch data is complete
        self.evaluate_goals()
        
        log_diag("FINALIZE_BATCH: DONE cached_events={}".format(len(self.cached_events)))
        
        # Determine live_count for timer interval
        live_count = 0
        now = time.time()
        for ev in self.cached_events:
            state = ev.get('status', {}).get('type', {}).get('state', 'pre')
            if state == 'in':
                live_count += 1
            elif state == 'pre':
                # Check if match starts in next 15 mins
                try:
                    m_date = ev.get('date', '')
                    if m_date:
                        dt = datetime.strptime(m_date[:16], "%Y-%m-%dT%H:%M")
                        m_ts = calendar.timegm(dt.timetuple())
                        if 0 <= (m_ts - now) <= 900: # 15 minutes
                            live_count += 1
                except: pass

        # FIX: Restart timer even if self.active is False, as long as UI is open or reminders exist
        should_run = self.active or (len(self.reminders) > 0) or (len(self.callbacks) > 0)
        if should_run:
            new_interval = self._get_timer_interval(live_count)
            log_diag("FINALIZE_BATCH: Restarting timer in {}ms (active={} callbacks={} reminders={})".format(
                new_interval, self.active, len(self.callbacks), len(self.reminders)))
            self.timer.start(new_interval, False)

        # Ensure direct summary fetches are active if live matches exist
        if live_count > 0:
            reactor.callLater(0.5, self.fetch_live_summaries)  # small delay lets lazy processor finish first

        reactor.callLater(0, self._trigger_callbacks, True)

    def fetch_live_summaries(self):
        """For each live non-soccer match, fetch the ESPN summary API directly
        (same endpoint GameInfo uses) and patch the score/status into event_map."""
        live_found = 0
        try:
            for eid, ev in list(self.event_map.items()):
                if ev.get('status', {}).get('type', {}).get('state', '') != 'in':
                    continue
                if eid in self._dead_summary_eids:
                    continue
                league_url = ev.get('league_url', '')
                
                # Build CDN boxscore URL (same structure as GameInfoScreen uses)
                base_url = league_url.split('?')[0]
                sport = ''; league_slug = ''
                for i, part in enumerate(base_url.rstrip('/').split('/')):
                    if part == 'sports' and i + 2 < len(base_url.rstrip('/').split('/')):
                        parts = base_url.rstrip('/').split('/')
                        sport = parts[i+1]; league_slug = parts[i+2]; break
                if not sport or not league_slug or league_slug == 'scoreboard':
                    continue
                
                summary_url = "https://cdn.espn.com/core/{}/{}/boxscore?xhr=1&gameId={}".format(
                    sport, league_slug, eid)
                d = getPage(summary_url.encode('utf-8'))
                d.addCallback(self.on_live_summary, str(eid))
                d.addErrback(self._on_summary_error, str(eid))
                live_found += 1
        except Exception as e:
            log_diag("fetch_live_summaries ERROR: " + str(e))
        
        # Reschedule if there are still live matches
        if self.live_summary_timer and self.live_summary_timer.active():
            self.live_summary_timer.cancel()
        if live_found > 0:
            self.live_summary_timer = reactor.callLater(30, self.fetch_live_summaries)
        else:
            self.live_summary_timer = None

    def _on_summary_error(self, failure, eid):
        count = self._summary_fail_counts.get(eid, 0) + 1
        self._summary_fail_counts[eid] = count
        if count >= 3:
            self._dead_summary_eids.add(eid)
            log_diag("CIRCUIT_BREAKER: eid={} failed {} times, marking dead for session".format(eid, count))
        else:
            log_diag("on_live_summary FETCH_ERR eid={} attempt={} {}".format(eid, count, str(failure)[:80]))

    def on_live_summary(self, body, eid):
        """Parse the summary API response and patch fresh score/status into event_map."""
        self._summary_fail_counts.pop(eid, None)
        try:
            data = json.loads(body)
            # Summary API structure: header.competitions[0].competitors[].score
            # and header.competitions[0].status  -- same as what GameInfo's parse_details reads
            header = data.get('header', {})
            if not header: return
            hdr_comp = header.get('competitions', [{}])[0]
            new_competitors = hdr_comp.get('competitors', [])
            new_status = hdr_comp.get('status', {})
            if not new_competitors: return
            
            ev = self.event_map.get(eid)
            if not ev: return
            
            # Patch scores onto the existing event's competitor entries (preserves logos, names, etc.)
            ev_competitors = ev.get('competitions', [{}])[0].get('competitors', [])
            for nc in new_competitors:
                ha = nc.get('homeAway', '')
                score = nc.get('score', None)
                if ha and score is not None:
                    for ec in ev_competitors:
                        if ec.get('homeAway') == ha:
                            ec['score'] = score
                            break
            
            # Patch status (clock, period, state)
            if new_status:
                ev['status'] = new_status
                if ev.get('competitions'):
                    ev['competitions'][0]['status'] = new_status
            
            # Rebuild snapshot so main screen and mini bars read fresh data
            self.match_snapshots[eid] = build_match_snapshot(ev)
            
            # Update cached_events entry reference
            for i, ce in enumerate(self.cached_events):
                if str(ce.get('id', '')) == eid:
                    self.cached_events[i] = ev
                    break
            # Trigger notification evaluator immediately on live score changes
            self._debounced_evaluate_goals()
            
            self._trigger_callbacks(True)
        except Exception as e:
            log_diag("on_live_summary PARSE_ERR eid={} {}".format(eid, str(e)[:100]))

    def handle_error(self, failure):
        self.status_message = "Connection Error"
        self._trigger_callbacks(True)
    def handle_error_silent(self, failure): pass

    def _trigger_callbacks(self, data_ready=True, force_refresh=False):
        """
        Debounced callback triggering
        Only fires once per 300ms to prevent UI flicker
        """
        now = time.time()
        
        if not hasattr(self, 'pending_force_refresh'):
            self.pending_force_refresh = False
        if force_refresh:
            self.pending_force_refresh = True
            
        # If less than 300ms since last callback, schedule delayed
        if now - self.last_callback_time < 0.3:
            self.pending_callback = data_ready
            if not self.callback_debounce_timer.isActive():
                self.callback_debounce_timer.start(300, True)
            return
        
        # Execute immediately
        self.last_callback_time = now
        do_force = self.pending_force_refresh
        self.pending_force_refresh = False
        
        for cb in self.callbacks: 
            try:
                cb(data_ready, force_refresh=do_force)
            except TypeError:
                try: cb(data_ready)
                except: pass

    def _execute_pending_callback(self):
        """Execute the pending debounced callback"""
        if self.pending_callback is not None:
            self.last_callback_time = time.time()
            data_ready = self.pending_callback
            do_force = getattr(self, 'pending_force_refresh', False)
            self.pending_force_refresh = False
            
            for cb in self.callbacks:
                try:
                    cb(data_ready, force_refresh=do_force)
                except TypeError:
                    try: cb(data_ready)
                    except: pass
            self.pending_callback = None

    @profile_function("SportsMonitor")
    def parse_single_json(self, body, league_name_fixed="", league_url=""): 
        self.process_events_data([(body, league_name_fixed, league_url)], append_mode=False)
        reactor.callLater(0.5, self.fetch_live_summaries)
        
    @profile_function("SportsMonitor")
    def parse_incremental_json(self, body, league_name_fixed, league_url):
        self.process_events_data([(body, league_name_fixed, league_url)], append_mode=True)

    def parse_multi_json(self, bodies_list): 
        self.process_events_data(bodies_list)

    # queue_notification updated to handle split components and IDs
    def queue_notification(self, match_id, score, scorer, event_type="default", scoring_team=None, sound_type=None):
        if self.discovery_mode == 0: return
        match_id = str(match_id)
        snap = self.match_snapshots.get(match_id)
        if not snap: return
        
        sport_type = snap['sport_type']
        notification = (match_id, score, scorer, event_type, scoring_team, sound_type)
        
        # BASKETBALL MERGE: If same basketball match already in queue, merge scorer text
        if sport_type == 'basketball' and event_type == 'goal':
            for i, existing in enumerate(self.notification_queue):
                ex_match_id = existing[0]
                ex_event_type = existing[3]
                if ex_match_id == match_id and ex_event_type == 'goal':
                    # Merge: append new scorer text to existing
                    merged_scorer = u"{}  |  {}".format(existing[2], scorer)
                    # Update score to latest and merge scorer
                    self.notification_queue[i] = (
                        match_id, score, merged_scorer,
                        existing[3], existing[4], existing[5]
                    )
                    return  # Merged, no new entry needed
            
            # LIVE UPDATE: If current active toast is for the same basketball match, update it
            if self.notification_active and self.current_toast and self.current_toast_match == match_id:
                try:
                    old_scorer = self.current_toast["scorer"].getText()
                    merged = u"{}  |  {}".format(old_scorer, scorer)
                    self.current_toast["scorer"].setText(merged)
                    self.current_toast["score"].setText(score)
                    # Reset timer to give time to read the update
                    self.current_toast.timer.stop()
                    self.current_toast.timer.start(4000, True)
                except: pass
                return  # Updated live, no new entry needed
        
        # DEDUP: Prevent identical notifications
        dedup_key = (match_id, score, event_type)
        for existing in self.notification_queue:
            existing_key = (existing[0], existing[1], existing[3])
            if existing_key == dedup_key:
                return
        
        # PRIORITY: Soccer first, others after (FIFO within each tier)
        if sport_type == 'soccer':
            # Insert after any existing soccer entries but before non-soccer
            insert_pos = 0
            for i, existing in enumerate(self.notification_queue):
                ex_snap = self.match_snapshots.get(str(existing[0]))
                if ex_snap and ex_snap['sport_type'] == 'soccer':
                    insert_pos = i + 1
                else:
                    break
            self.notification_queue.insert(insert_pos, notification)
        else:
            self.notification_queue.append(notification)
        
        self.process_queue()
        
    def process_queue(self):
        if self.discovery_mode == 0:
            self.notification_queue = []
            return
        if self.notification_active or not self.notification_queue: return
        
        try:
            item = self.notification_queue.pop(0)
            # Simplified item: (match_id, score, scorer, event_type, scoring_team, sound_type)
            match_id, score, scorer, event_type, scoring_team, sound_type = item[:6]
            self.notification_active = True
            self.current_toast_match = match_id
            
            if self.session: 
                try:
                    def _open_toast():
                        # SYNC: Play sound RIGHT when toast opens
                        if sound_type == 'goal' and self.discovery_mode == 2:
                            self.play_sound()
                        elif sound_type == 'stend' and self.discovery_mode == 2:
                            self.play_stend_sound()
                        
                        try:
                            self.session.openWithCallback(
                                self.on_toast_closed, GoalToast, 
                                match_id, score, scorer, event_type, scoring_team
                            )
                        except Exception as e:
                            print("[SimplySport] Error opening GoalToast: {}".format(e))
                            # RE-QUEUE: Don't lose notification on screen stack error
                            self.notification_queue.insert(0, item)
                            self.notification_active = False
                            self.current_toast = None
                            reactor.callLater(2, self.process_queue)
                    
                    reactor.callLater(0, _open_toast)
                except Exception as e:
                    print("[SimplySport] Error setting up notification thread: {}".format(e))
                    self.notification_queue.insert(0, item)
                    self.notification_active = False
                    self.current_toast = None
                    reactor.callLater(2, self.process_queue)
            else:
                # No session yet - wait and retry
                self.notification_queue.insert(0, item)
                self.notification_active = False
                self.current_toast = None
                reactor.callLater(5, self.process_queue)
        except Exception as e:
            print("[SimplySport] Critical error in process_queue: {}".format(e))
            if 'item' in locals():
                self.notification_queue.insert(0, item)
            self.notification_active = False
            self.current_toast = None
            reactor.callLater(2, self.process_queue)

    def on_toast_closed(self, *args):
        self.notification_active = False
        self.current_toast = None
        self.current_toast_match = None
        reactor.callLater(0.3, self.process_queue)

    def get_sport_type(self, league_name):
        lname = league_name.lower()
        if any(x in lname for x in ['nba', 'wnba', 'basket', 'euroleague']): return 'basketball'
        if any(x in lname for x in ['nfl', 'ncaa football', 'ufl']): return 'football'
        if any(x in lname for x in ['mlb', 'baseball']): return 'baseball'
        if any(x in lname for x in ['nhl', 'hockey']): return 'hockey'
        return 'soccer'
    def get_cdn_sport_name(self, league_name):
        lname = league_name.lower()
        if 'college' in lname or 'ncaa' in lname: return 'ncaa'
        if 'nba' in lname or 'basket' in lname: return 'nba'
        if 'nfl' in lname: return 'nfl'
        if 'mlb' in lname: return 'mlb'
        if 'nhl' in lname: return 'nhl'
        return 'soccer'
    def get_score_prefix(self, sport, diff):
        if diff < 0: return "GOAL DISALLOWED" 
        if sport == 'soccer' or sport == 'hockey': return "GOAL!"
        if sport == 'basketball': return "SCORE (+{})".format(diff)
        if sport == 'football': return "SCORE (+{})".format(diff)
        return "SCORE"
    def fetch_summary_for_scorer(self, event, callback, expected_score=None):
        try:
            event_id = str(event.get('id', ''))
            league_url = event.get('league_url', '')
            if not event_id or not league_url:
                return callback(None)

            sport_type = get_sport_type(league_url)
            base_url = league_url.split('?')[0]
            summary_url = ""

            if sport_type == SPORT_TYPE_TENNIS:
                tournament_id = event.get('tournament_id', '')
                competition_id = event.get('competition_id', '')
                api_link = ""
                
                try:
                    links = event.get('links', [])
                    for link in links:
                         href = link.get('href', '')
                         if "summary" in href and "api.espn.com" in href:
                             api_link = href
                             break
                except: pass
                
                if api_link:
                    summary_url = api_link
                elif tournament_id and competition_id:
                    if "scoreboard" in base_url:
                        summary_url = base_url.replace("scoreboard", "summary") + "?event=" + str(tournament_id) + "&competition=" + str(competition_id)
                    else:
                        summary_url = "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/summary?event=" + str(tournament_id) + "&competition=" + str(competition_id)
                else:
                     if "scoreboard" in base_url:
                        summary_url = base_url.replace("scoreboard", "summary") + "?event=" + str(event_id)
                     else:
                        summary_url = "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/summary?event=" + str(event_id)
            else:
                if "scoreboard" in base_url:
                    summary_url = base_url.replace("scoreboard", "summary") + "?event=" + str(event_id)
                else:
                    sport = 'soccer'
                    league = 'eng.1'
                    parts = base_url.split('/')
                    for i, p in enumerate(parts):
                        if p == 'sports' and i + 2 < len(parts):
                            sport = parts[i+1]
                            league = parts[i+2]
                            break
                    summary_url = "https://site.api.espn.com/apis/site/v2/sports/{}/{}/summary?event={}".format(sport, league, event_id)

            if not summary_url:
                return callback(None)

            def on_summary_success(body):
                try:
                    data = json.loads(body.decode('utf-8', errors='ignore'))
                    header = data.get('header', {})
                    competitions = header.get('competitions', [])
                    if not competitions:
                        competitions = data.get('gamepackageJSON', {}).get('header', {}).get('competitions', [])
                    
                    details = competitions[0].get('details', []) if competitions else []
                    
                    scoring_plays = data.get('scoringPlays', [])
                    if not scoring_plays:
                        scoring_plays = data.get('gamepackageJSON', {}).get('scoringPlays', [])

                    if not scoring_plays and details:
                        for play in details:
                            is_scoring = play.get('scoringPlay', False)
                            text_desc = play.get('type', {}).get('text', '').lower()
                            if is_scoring or "goal" in text_desc:
                                scoring_plays.append(play)
                    
                    if scoring_plays:
                        if expected_score is not None and len(scoring_plays) < expected_score:
                            print("[SimplySport] fetch_summary API stale data. Expected {}, got {}".format(expected_score, len(scoring_plays)))
                            return callback(None)
                            
                        last_play = scoring_plays[-1]
                        clock = last_play.get('clock', {}).get('displayValue', '')
                        
                        text_desc = last_play.get('type', {}).get('text', '').lower()
                        goal_type = "(G)"
                        if "penalty" in text_desc:
                            goal_type = "(P)"
                        elif "own" in text_desc:
                            goal_type = "(O)"

                        athletes = last_play.get('athletesInvolved', [])
                        if not athletes: athletes = last_play.get('participants', [])
                        
                        if athletes:
                            p_name = athletes[0].get('displayName') or athletes[0].get('shortName')
                            result = "{} {} {}".format(p_name, goal_type, clock)
                            print("[SimplySport] fetch_summary_for_scorer API resolved: {}".format(result))
                            return callback(result)
                        else:
                            return callback("Goal {}".format(clock))
                    return callback(None)
                except Exception as e:
                    print("[SimplySport] fetch_summary_for_scorer error parsing:", e)
                    return callback(None)
                    
            getPage(summary_url.encode('utf-8')).addCallback(on_summary_success).addErrback(lambda err: callback(None))
        except Exception as e:
            print("[SimplySport] fetch_summary_for_scorer error:", e)
            return callback(None)

    def get_scorer_text(self, event, allow_pending=False):
        try:
            # 1. Get Actual Total Score
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            if len(comps) >= 2:
                try:
                    s1 = int(comps[0].get('score', '0') or '0')
                    s2 = int(comps[1].get('score', '0') or '0')
                    total_score = s1 + s2
                except (ValueError, TypeError):
                    return ""
            else: return ""

            details = event.get('competitions', [{}])[0].get('details', [])
            
            # --- REMOVED: Red cards are handled as discrete notifications in evaluate_goals ---

            if details:
                # 2. Find all scoring plays
                scoring_plays = []
                for play in details:
                    is_scoring = play.get('scoringPlay', False)
                    text_desc = play.get('type', {}).get('text', '').lower()
                    if is_scoring or "goal" in text_desc:
                        scoring_plays.append(play)

                # 3. Check for Stale Data (API Lag)
                if len(scoring_plays) < total_score:
                    if allow_pending: return None # Signal to wait
                    return "Goal!"

                # 4. Get Latest Scorer
                if scoring_plays:
                    last_play = scoring_plays[-1]
                    clock = last_play.get('clock', {}).get('displayValue', '')
                    
                    # Extract Goal Type (Penalty, Own Goal, or regular Goal)
                    text_desc = last_play.get('type', {}).get('text', '').lower()
                    goal_type = "(G)"
                    if "penalty" in text_desc:
                        goal_type = "(P)"
                    elif "own" in text_desc:
                        goal_type = "(O)"

                    athletes = last_play.get('athletesInvolved', [])
                    if not athletes: athletes = last_play.get('participants', [])
                    
                    if athletes:
                        p_name = athletes[0].get('displayName') or athletes[0].get('shortName')
                        # Format: "Haaland (G) 45'"
                        return "{} {} {}".format(p_name, goal_type, clock)
                    else: 
                        return "Goal {}".format(clock)
        except: pass
        return ""

    def calculate_excitement(self, event):
        """Calculate excitement score for a match (higher = more exciting)"""
        score = 0
        try:
            status = event.get('status', {})
            state = status.get('type', {}).get('state', 'pre')
            
            # Only score LIVE games
            if state != 'in':
                return 0
            
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            if len(comps) < 2:
                return 0
            
            # Get scores safely
            try:
                h_score = int(comps[0].get('score', '0') or '0')
                a_score = int(comps[1].get('score', '0') or '0')
            except:
                h_score, a_score = 0, 0
            
            diff = abs(h_score - a_score)
            total_goals = h_score + a_score
            
            # 1. Close Game Bonus
            if diff == 0:
                score += 50      # Draw is exciting
            elif diff == 1:
                score += 30      # 1-goal lead is tense
            elif diff == 2:
                score += 15      # 2-goal lead still interesting
            
            # 2. "Crunch Time" Bonus (late game drama)
            clock = status.get('displayClock', '0')
            try:
                # Handle formats like "85'" or "85:23"
                clock_str = clock.replace("'", "").split(":")[0]
                minutes = int(clock_str) if clock_str.isdigit() else 0
                
                if minutes >= 80:
                    score *= 1.5  # Multiplier for late drama
                elif minutes >= 70:
                    score *= 1.3  # Moderate multiplier
            except:
                pass
            
            # 3. Drama Bonus (Red Cards)
            try:
                for comp in comps:
                    stats = comp.get('statistics', [])
                    for stat in stats:
                        if stat.get('name', '').lower() in ['redcards', 'red cards']:
                            red_cards = int(stat.get('displayValue', '0') or '0')
                            score += red_cards * 20  # +20 per red card
            except:
                pass
            
            # 4. High-scoring game bonus
            if total_goals >= 6:
                score += 25
            elif total_goals >= 4:
                score += 15
            
        except:
            pass
        
        return score


    def prefetch_logo(self, url, team_id):
        """Pre-download logo to cache using team ID naming (like GameInfoScreen)"""
        if not url or not team_id: return
        if team_id in self.logo_path_cache: return # Skip disk check if already cached in memory
        if team_id in self.pending_logos: return # Skip if already downloading

        try:
            cache_dir = "/tmp/simplysports/logos/"
            if not os.path.exists(cache_dir):
                try: os.makedirs(cache_dir)
                except: pass
            
            target_path = cache_dir + str(team_id) + ".png"
            
            # Download only if missing or empty
            if not os.path.exists(target_path) or os.path.getsize(target_path) == 0:
                self.pending_logos.add(team_id)
                
                def on_download_success(data):
                    if data:
                        with open(target_path, 'wb') as f: f.write(data)
                        self.logo_path_cache[team_id] = target_path # Register globally
                        self.missing_logo_cache.discard(team_id)
                        GLOBAL_VALID_LOGO_PATHS.add(target_path)
                    self.pending_logos.discard(team_id)
                    return data
                
                def on_download_error(err):
                    self.pending_logos.discard(team_id)
                    return None

                self.agent.request(b'GET', url.encode('utf-8')) \
                    .addCallback(readBody) \
                    .addCallback(on_download_success) \
                    .addErrback(on_download_error)
            else:
                self.logo_path_cache[team_id] = target_path # Register globally so subsequent calls skip os.path.exists
        except: 
            self.pending_logos.discard(team_id)


    def _extract_tennis_matches(self, ev, league_name, l_url):
        matches = []
        groupings = ev.get('groupings', [])
        tournament_name = ev.get('name', '') or ev.get('shortName', '')
        
        for grouping in groupings:
            competitions = grouping.get('competitions', [])
            
            for match in competitions:
                # Generate stable ID for tennis matches
                match_id = match.get('id', '')
                if not match_id:
                    # Create stable ID from tournament + player IDs
                    comps = match.get('competitors', [])
                    p1_id = comps[0].get('athlete', {}).get('id', '') if len(comps) > 0 else ''
                    p2_id = comps[1].get('athlete', {}).get('id', '') if len(comps) > 1 else ''
                    match_id = "tennis_{}_{}_{}_{}".format(ev.get('id', ''), p1_id, p2_id, match.get('date', '')[:10])
                
                # Helper to safely extract name, flag AND ID
                def extract_tennis_info(comp):
                    # Singles: athlete.shortName / athlete.displayName + athlete.flag
                    # Doubles: roster.shortDisplayName / roster.displayName + roster entries
                    
                    name = ""
                    flag_url = ""
                    pid = ""
                    
                    # 1. Try Athlete (Singles)
                    ath = comp.get('athlete', {})
                    if ath:
                        name = ath.get('shortName') or ath.get('displayName')
                        pid = ath.get('id', '')
                        flag = ath.get('flag', {})
                        flag_url = flag.get('href') or flag.get('alt')
                        if not flag_url and ath.get('flag', {}).get('iso2'):
                            flag_url = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(ath['flag']['iso2'].lower())

                    # 2. Try Roster (Doubles)
                    if not name:
                        ros = comp.get('roster', {})
                        if ros:
                            name = ros.get('shortDisplayName') or ros.get('displayName')
                            # For doubles, try to get flag of first player if main flag missing
                            entries = comp.get('roster', {}).get('entries', [])
                            if entries:
                                p1 = entries[0].get('athlete', {})
                                if not pid: pid = p1.get('id', '')
                                
                                if not flag_url:
                                    flag = p1.get('flag', {})
                                    flag_url = flag.get('href') or flag.get('alt')
                                    if not flag_url and p1.get('flag', {}).get('iso2'):
                                        flag_url = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(p1['flag']['iso2'].lower())

                    # 3. Fallback to generic name
                    if not name:
                        name = comp.get('name') or ""
                        
                    # 4. Fallback Flag (from country if available)
                    if not flag_url:
                         country = comp.get('country', {})
                         if country.get('iso2'): 
                             flag_url = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(country['iso2'].lower())

                    return name, flag_url, pid

                # Create a flattened event for each match
                match_event = {
                    'id': match_id,
                    'uid': match.get('uid', match_id),
                    'tournament_id': ev.get('id', ''),
                    'date': match.get('date', ev.get('date', '')),
                    'status': match.get('status', {}),
                    'links': match.get('links', []),
                    'competition_id': match.get('id', ''),
                    'shortName': '',  
                    'name': tournament_name,
                    'league_name': league_name,
                    'league_url': l_url,
                    'venue': match.get('venue', {}),
                    'competitions': [{
                        'competitors': match.get('competitors', []),
                        'venue': match.get('venue', {}),
                        'broadcasts': match.get('broadcasts', []),
                        'notes': match.get('notes', []),
                        'round': match.get('round', {})
                    }]
                }
                
                # Enhanced Name & Flag Extraction for Tennis
                comps = match.get('competitors', [])
                p1_name = "Player 1"; p2_name = "Player 2"
                p1_flag = ""; p2_flag = ""
                p1_id = ""; p2_id = ""
                
                if len(comps) >= 2:
                    p1_name, p1_flag, p1_id = extract_tennis_info(comps[0])
                    p2_name, p2_flag, p2_id = extract_tennis_info(comps[1])
                    
                    # Fallback: Parse from match name/shortName
                    if not p1_name or not p2_name or "Player" in p1_name:
                        m_name = match.get('name', '') or match.get('shortName', '')
                        if " vs " in m_name:
                            parts = m_name.split(" vs ")
                            if len(parts) == 2:
                                p1_name_fallback = parts[0].strip()
                                p2_name_fallback = parts[1].strip()
                                if not p1_name or "Player" in p1_name: p1_name = p1_name_fallback
                                if not p2_name or "Player" in p2_name: p2_name = p2_name_fallback
                    
                    # Update the competitor objects with normalized data
                    # This ensures process_events_data generic logo logic works!
                    if not comps[0].get('athlete'): comps[0]['athlete'] = {}
                    if not comps[0]['athlete'].get('shortName'): comps[0]['athlete']['shortName'] = p1_name
                    if not comps[0].get('name'): comps[0]['name'] = p1_name
                    if p1_flag:
                        if not comps[0]['athlete'].get('flag'): comps[0]['athlete']['flag'] = {}
                        comps[0]['athlete']['flag']['href'] = p1_flag
                    if p1_id and not comps[0]['athlete'].get('id'):
                        comps[0]['athlete']['id'] = p1_id

                    if not comps[1].get('athlete'): comps[1]['athlete'] = {}
                    if not comps[1]['athlete'].get('shortName'): comps[1]['athlete']['shortName'] = p2_name
                    if not comps[1].get('name'): comps[1]['name'] = p2_name
                    if p2_flag:
                        if not comps[1]['athlete'].get('flag'): comps[1]['athlete']['flag'] = {}
                        comps[1]['athlete']['flag']['href'] = p2_flag
                    if p2_id and not comps[1]['athlete'].get('id'):
                        comps[1]['athlete']['id'] = p2_id

                    match_event['shortName'] = "{} vs {}".format(p1_name, p2_name)
                    match_event['p1_name_fixed'] = p1_name
                    match_event['p2_name_fixed'] = p2_name
                
                matches.append(match_event)
        
        # If no groupings/matches found, fall back to ev
        if not matches and not groupings:
            matches.append(ev)
            
        return matches

    def _debounced_evaluate_goals(self):
        """
        Debounced evaluation for goals/red-cards.
        Ensures O(N) evaluation only runs once per 300ms window,
        even if multiple live summary API responses arrive simultaneously.
        """
        if getattr(self, '_eval_pending', False):
            return
            
        self._eval_pending = True
        
        def _execute():
            self._eval_pending = False
            self.evaluate_goals()
            
        from twisted.internet import reactor
        reactor.callLater(0.3, _execute)

    def evaluate_goals(self):
        """Evaluate all cached events for goal/start/end/red-card notifications.
        Runs synchronously — NOT inside the cancellable lazy processor.
        Safe to call from CDN path or after lazy processing completes."""
        try:
            if not self.active or not self.session:
                return

            # Cleanup old goal flags (5-minute heat effect)
            now = time.time()
            keys_to_del = [mid for mid, info in self.goal_flags.items() if now - info['time'] > 300]
            for k in keys_to_del: del self.goal_flags[k]

            for event in self.cached_events:
                status = event.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                league_name = event.get('league_name', '')
                league_url = event.get('league_url', '')

                event_sport_type = get_sport_type(league_url)

                # === RACING: Start/Finish notifications only ===
                if event_sport_type == SPORT_TYPE_RACING:
                    race_name = event.get('shortName', '') or event.get('name', league_name)
                    match_id = event.get('id', race_name)
                    l_logo = event.get('l_logo_url', '')
                    l_id = event.get('l_logo_id', '')

                    prev_state = self.last_states.get(match_id)
                    if prev_state:
                        if state == 'in' and prev_state == 'pre':
                            if (match_id, 'start') not in self.notified_events:
                                self.notified_events.add((match_id, 'start'))
                                self.queue_notification(match_id, "", "RACE STARTING", event_type="start")
                        elif state == 'post' and prev_state == 'in':
                            if (match_id, 'end') not in self.notified_events:
                                self.notified_events.add((match_id, 'end'))
                                self.queue_notification(match_id, "", "RACE FINISHED", event_type="end")
                    self.last_states[match_id] = state
                    continue

                if len(comps) < 2: continue

                # Skip individual sports EXCEPT Racing (Racing handled above)
                if event_sport_type in [SPORT_TYPE_GOLF, SPORT_TYPE_TENNIS, SPORT_TYPE_COMBAT]:
                    continue

                # Read names, scores, logos from snapshot
                snap = self.match_snapshots.get(str(event.get('id', '')))
                if not snap: continue

                home   = snap['h_name_short']
                away   = snap['a_name_short']
                h_logo = snap['h_logo_url']
                a_logo = snap['a_logo_url']
                h_id   = snap['h_logo_id']
                a_id   = snap['a_logo_id']
                l_logo = snap['l_logo_url']
                l_id   = snap['l_logo_id']
                h_score = snap['h_score_int']
                a_score = snap['a_score_int']
                match_id = snap['event_id']
                score_str = str(h_score) + "-" + str(a_score)

                prev_state = self.last_states.get(match_id)
                if prev_state:
                    should_play_stend = (self.discovery_mode == 2 and self.get_sport_type(league_name) == 'soccer')

                    # Ensure score string is "1-0" not "1 - 0"
                    score_fmt = "{}-{}".format(h_score, a_score)

                    if state == 'in' and prev_state == 'pre':
                        # DEDUP: Only fire start notification once per match
                        if (match_id, 'start') not in self.notified_events:
                            if event_sport_type != SPORT_TYPE_TENNIS:
                                 self.notified_events.add((match_id, 'start'))
                                 stend_sound = 'stend' if should_play_stend else None
                                 self.queue_notification(match_id, score_fmt, "MATCH STARTED", event_type="start", sound_type=stend_sound)
                    elif state == 'post' and prev_state == 'in':
                        # DEDUP: Only fire end notification once per match
                        if (match_id, 'end') not in self.notified_events:
                            self.notified_events.add((match_id, 'end'))
                            stend_sound = 'stend' if should_play_stend else None
                            self.queue_notification(match_id, score_fmt, "FULL TIME", event_type="end", sound_type=stend_sound)

                self.last_states[match_id] = state
                if state == 'in':
                    if match_id in self.last_scores:
                        if self.last_scores[match_id] != score_str:
                            try:
                                prev_h, prev_a = map(int, self.last_scores[match_id].split('-'))
                                diff_h = h_score - prev_h
                                diff_a = a_score - prev_a
                                sport_type = self.get_sport_type(league_name)

                                # Re-format score display "1-0" NO SPACES
                                score_display = "{}-{}".format(h_score, a_score)

                                if diff_h > 0 or diff_a > 0:
                                    # BASKETBALL SPECIAL HANDLING
                                    if sport_type == 'basketball':
                                        points = max(diff_h, diff_a)
                                        scorer_text = "+{} POINTS".format(points)
                                    elif sport_type == 'football':
                                        # NFL SPECIAL HANDLING
                                        points = max(diff_h, diff_a)
                                        if points == 6: scorer_text = "TOUCHDOWN!"
                                        elif points == 3: scorer_text = "FIELD GOAL"
                                        elif points == 1: scorer_text = "EXTRA POINT"
                                        elif points == 2: scorer_text = "SAFETY / 2PT"
                                        else: scorer_text = "SCORE (+{})".format(points)
                                    else:
                                        # ASYNC: Try to fetch richer data from ESPN Summary API
                                        def schedule_goal_notification(m_id, s_disp, s_type, d_h, d_a, ev, exp_score):
                                            state_container = {'fired': False, 'timeout_call': None}
                                            
                                            def fire_notification(scorer_result):
                                                if state_container['fired']: return
                                                state_container['fired'] = True
                                                if state_container['timeout_call'] and state_container['timeout_call'].active():
                                                    state_container['timeout_call'].cancel()
                                                    
                                                final_text = scorer_result
                                                if not final_text:
                                                    final_text = self.get_scorer_text(ev, allow_pending=False) or "Goal!"
                                                    
                                                if d_h > 0:
                                                    g_sound = 'goal' if s_type != 'basketball' else None
                                                    self.queue_notification(m_id, s_disp, final_text, event_type="goal", scoring_team="home", sound_type=g_sound)
                                                    self.goal_flags[m_id] = {'time': time.time(), 'team': 'home'}
                                                if d_a > 0:
                                                    g_sound = 'goal' if s_type != 'basketball' else None
                                                    self.queue_notification(m_id, s_disp, final_text, event_type="goal", scoring_team="away", sound_type=g_sound)
                                                    self.goal_flags[m_id] = {'time': time.time(), 'team': 'away'}
                                                    
                                            def on_timeout():
                                                if not state_container['fired']:
                                                    print("[SimplySport] fetch_summary_for_scorer timed out.")
                                                    fire_notification(None)
                                                    
                                            from twisted.internet import reactor
                                            state_container['timeout_call'] = reactor.callLater(3.0, on_timeout)
                                            self.fetch_summary_for_scorer(ev, fire_notification, expected_score=exp_score)
                                            
                                        schedule_goal_notification(match_id, score_display, sport_type, diff_h, diff_a, event, h_score + a_score)
                                        
                                        diff_h = 0
                                        diff_a = 0

                                    if diff_h > 0:
                                        goal_sound = 'goal' if sport_type != 'basketball' else None
                                        self.queue_notification(match_id, score_display, scorer_text, event_type="goal", scoring_team="home", sound_type=goal_sound)
                                        self.goal_flags[match_id] = {'time': time.time(), 'team': 'home'}

                                    if diff_a > 0:
                                        goal_sound = 'goal' if sport_type != 'basketball' else None
                                        self.queue_notification(match_id, score_display, scorer_text, event_type="goal", scoring_team="away", sound_type=goal_sound)
                                        self.goal_flags[match_id] = {'time': time.time(), 'team': 'away'}
                            except: pass
                    # Update score ONLY if we didn't 'continue' above
                    self.last_scores[match_id] = score_str

                    # --- RED CARD NOTIFICATIONS ---
                    if state == 'in':
                        h_rc   = snap.get('h_red_cards', 0)
                        a_rc   = snap.get('a_red_cards', 0)
                        rc_str = "{}-{}".format(h_rc, a_rc)

                        if match_id in self.last_red_cards:
                            if self.last_red_cards[match_id] != rc_str:
                                try:
                                    prev_h_rc, prev_a_rc = map(int, self.last_red_cards[match_id].split('-'))
                                    diff_h_rc = h_rc - prev_h_rc
                                    diff_a_rc = a_rc - prev_a_rc

                                    if diff_h_rc > 0 or diff_a_rc > 0:
                                        # Get the latest red-carded player name
                                        rc_player_name = "Red card"
                                        details = event.get('competitions', [{}])[0].get('details', [])
                                        if details:
                                            for play in reversed(details):
                                                is_rc = play.get('redCard', False)
                                                text_desc = play.get('type', {}).get('text', '').lower()
                                                if is_rc or ('card' in text_desc and 'red' in text_desc):
                                                    ath = play.get('athletesInvolved', [])
                                                    if not ath: ath = play.get('participants', [])
                                                    if ath:
                                                        rc_player_name = ath[0].get('displayName') or ath[0].get('shortName', 'Red card')
                                                    break

                                        # Red Card Sound & Notification
                                        if diff_h_rc > 0:
                                            self.queue_notification(match_id, score_display, rc_player_name, event_type="red_card", scoring_team="home", sound_type="stend")
                                        if diff_a_rc > 0:
                                            self.queue_notification(match_id, score_display, rc_player_name, event_type="red_card", scoring_team="away", sound_type="stend")
                                except: pass
                        self.last_red_cards[match_id] = rc_str
        except Exception as e:
            print("[SimplySport] Error in evaluate_goals: {}".format(e))

    @profile_function("SportsMonitor")
    def process_events_data(self, data_list, single_league_name="", append_mode=False):
        if hasattr(self, 'lazy_processor') and self.lazy_processor and self.lazy_processor.active():
            self.lazy_processor.cancel()
        self.lazy_gen = self._run_lazy_process_events_data(data_list, single_league_name, append_mode)
        self.do_lazy_process()

    def do_lazy_process(self):
        try:
            next(self.lazy_gen)
            from twisted.internet import reactor
            self.lazy_processor = reactor.callLater(0.01, self.do_lazy_process)
        except StopIteration:
            self.lazy_processor = None
            # Notifications already evaluated in _run_lazy_process_events_data
            # Prevent UI storm: Only trigger callbacks if we aren't mid-batch.
            # (Batch mode will call _trigger_callbacks inside finalize_batch)
            if getattr(self, 'batch_is_active', False):
                pass
            else:
                self._trigger_callbacks(True)
        except Exception as e:
            print("[SimplySport] Error in background lazy UI sync:", e)
            self.lazy_processor = None

    def _run_lazy_process_events_data(self, data_list, single_league_name="", append_mode=False):
        self.last_update = time.time()
        
        # Optimization: Clear map if not appending (fresh load)
        if not append_mode:
            self.event_map = {}
            
        changed_events = []
        has_changes = False
        
        try:
            for item in data_list:
                if isinstance(item, tuple): body, l_name, l_url = item
                else: body, l_name, l_url = item, single_league_name, ""
                try:
                    json_str = body.decode('utf-8', errors='ignore')
                    data = json.loads(json_str)
                    league_obj = data.get('leagues', [{}])[0]
                    cur_l_logo = league_obj.get('logos', [{}])[0].get('href', '')
                    cur_l_id = str(league_obj.get('id', ''))
                    if l_name: league_name = l_name
                    else: league_name = league_obj.get('name') or league_obj.get('shortName') or ""
                    events = data.get('events', [])
                    league_seen_ids = set()
                    
                    sport_type = get_sport_type(l_url)
                    
                    for i, ev in enumerate(events):
                        # Yield Enigma2 processor control every 5 events
                        if i > 0 and i % 5 == 0: yield
                        
                        ev['league_name'] = league_name
                        ev['league_url'] = l_url
                        
                        current_batch = []
                        if sport_type == SPORT_TYPE_TENNIS:
                            current_batch = self._extract_tennis_matches(ev, league_name, l_url)
                        else:
                            current_batch = [ev]
                            
                        # Process batch and update map
                        for processed_ev in current_batch:
                            eid = processed_ev.get('id')
                            if not eid: continue
                            
                            eid_str = str(eid)
                            league_seen_ids.add(eid_str)
                            status_type_state = processed_ev.get('status', {}).get('type', {}).get('state', '')
                            
                            # Check for changes using fresh scoreboard data vs stored state
                            old_ev = self.event_map.get(eid_str)
                            
                            is_changed = True
                            if old_ev:
                                # Status & Meta comparison
                                old_status = old_ev.get('status', {})
                                new_status = processed_ev.get('status', {})
                                
                                old_type = old_status.get('type', {})
                                new_type = new_status.get('type', {})
                                
                                # 1. Check basic state (pre, in, post)
                                if old_type.get('state') != new_type.get('state'):
                                    is_changed = True
                                # 2. Check Detailed status (PPD, Suspended, etc)
                                elif old_type.get('name') != new_type.get('name'):
                                    is_changed = True
                                # 3. Check Clock and Period (IMPORTANT for real-time updates)
                                elif old_status.get('displayClock') != new_status.get('displayClock'):
                                    is_changed = True
                                elif old_status.get('period') != new_status.get('period'):
                                    is_changed = True
                                else:
                                    # 4. Check Competitors & Scores
                                    old_comps = old_ev.get('competitions', [{}])[0].get('competitors', [])
                                    new_comps = processed_ev.get('competitions', [{}])[0].get('competitors', [])
                                    
                                    if len(old_comps) != len(new_comps):
                                        is_changed = True
                                    else:
                                        scores_match = True
                                        for i in range(len(old_comps)):
                                            if old_comps[i].get('score') != new_comps[i].get('score'):
                                                scores_match = False; break
                                        if scores_match: 
                                            is_changed = False
                                            # Special case for Racing: ALWAYS trigger UI refresh because they have no score tracking pre-race
                                            event_sport_type_early = get_sport_type(processed_ev.get('league_url', ''))
                                            if event_sport_type_early == SPORT_TYPE_RACING:
                                                is_changed = True

                            
                            # =====================================================
                            # LOGO URL/ID CONSTRUCTION - RUN FOR ALL EVENTS
                            # This ensures every event has logo data, not just changed ones
                            # =====================================================
                            comps = processed_ev.get('competitions', [{}])[0].get('competitors', [])
                            league_name = processed_ev.get('league_name', '')
                            league_url = processed_ev.get('league_url', '')
                            sport_cdn = self.get_cdn_sport_name(league_name)
                            event_sport_type = get_sport_type(league_url)
                            
                            # Skip logo construction for golf/combat (no team logos)
                            if len(comps) >= 2 and event_sport_type not in [SPORT_TYPE_GOLF, SPORT_TYPE_COMBAT]:
                                if event_sport_type == SPORT_TYPE_TENNIS:
                                    # Fix: Tennis flags reversed. Force index 0=Home, 1=Away to match MiniBar
                                    team_h = comps[0]
                                    team_a = comps[1]
                                else:
                                    team_h = next((t for t in comps if t.get('homeAway') == 'home'), None)
                                    team_a = next((t for t in comps if t.get('homeAway') == 'away'), None)
                                    if not team_h and len(comps) > 0: team_h = comps[0]
                                    if not team_a and len(comps) > 1: team_a = comps[1]
                                
                                h_id, h_logo = '', ''
                                a_id, a_logo = '', ''
                                
                                if team_h:
                                    if 'athlete' in team_h or event_sport_type == SPORT_TYPE_TENNIS:
                                        # Tennis/Individual: Robust flag extraction (singles + doubles)
                                        ath = team_h.get('athlete', {})
                                        h_id = ath.get('id', '')
                                        flag = ath.get('flag', {})
                                        h_logo = flag.get('href') or flag.get('alt') or ''
                                        if not h_logo and flag.get('iso2'):
                                            h_logo = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(flag['iso2'].lower())
                                        # Doubles: try roster entries
                                        if not h_logo or not h_id:
                                            ros = team_h.get('roster', {})
                                            entries = ros.get('entries', [])
                                            if entries:
                                                p1 = entries[0].get('athlete', {})
                                                if not h_id: h_id = p1.get('id', '')
                                                if not h_logo:
                                                    pf = p1.get('flag', {})
                                                    h_logo = pf.get('href') or pf.get('alt') or ''
                                                    if not h_logo and pf.get('iso2'):
                                                        h_logo = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(pf['iso2'].lower())
                                        # Country fallback
                                        if not h_logo:
                                            country = team_h.get('country', {})
                                            if country.get('iso2'):
                                                h_logo = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(country['iso2'].lower())
                                    else:
                                        team_obj = team_h.get('team', {})
                                        h_id = team_obj.get('id', '')
                                        h_logo = team_obj.get('logo', '')
                                        if not h_logo and h_id: 
                                            h_logo = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png".format(sport_cdn, h_id)
                                
                                if team_a:
                                    if 'athlete' in team_a or event_sport_type == SPORT_TYPE_TENNIS:
                                        # Tennis/Individual: Robust flag extraction (singles + doubles)
                                        ath = team_a.get('athlete', {})
                                        a_id = ath.get('id', '')
                                        flag = ath.get('flag', {})
                                        a_logo = flag.get('href') or flag.get('alt') or ''
                                        if not a_logo and flag.get('iso2'):
                                            a_logo = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(flag['iso2'].lower())
                                        # Doubles: try roster entries
                                        if not a_logo or not a_id:
                                            ros = team_a.get('roster', {})
                                            entries = ros.get('entries', [])
                                            if entries:
                                                p1 = entries[0].get('athlete', {})
                                                if not a_id: a_id = p1.get('id', '')
                                                if not a_logo:
                                                    pf = p1.get('flag', {})
                                                    a_logo = pf.get('href') or pf.get('alt') or ''
                                                    if not a_logo and pf.get('iso2'):
                                                        a_logo = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(pf['iso2'].lower())
                                        # Country fallback
                                        if not a_logo:
                                            country = team_a.get('country', {})
                                            if country.get('iso2'):
                                                a_logo = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(country['iso2'].lower())
                                    else:
                                        # FIX: Added missing else block for standard away teams
                                        team_obj = team_a.get('team', {})
                                        a_id = team_obj.get('id', '')
                                        a_logo = team_obj.get('logo', '')
                                        if not a_logo and a_id:
                                            a_logo = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png".format(sport_cdn, a_id)
                                
                                # Prefix logo IDs with unique sport name to prevent cross-sport collisions
                                sport_prefix = get_sport_id_prefix(league_url)
                                processed_ev['h_logo_id'] = sport_prefix + str(h_id) if h_id else ''
                                processed_ev['a_logo_id'] = sport_prefix + str(a_id) if a_id else ''
                                
                                # Pre-fetch logos for all events (cache warmup)
                                if h_logo and h_id: self.prefetch_logo(h_logo, processed_ev['h_logo_id'])
                                if a_logo and a_id: self.prefetch_logo(a_logo, processed_ev['a_logo_id'])
                                
                                processed_ev['h_logo_url'] = h_logo
                                processed_ev['a_logo_url'] = a_logo

                            # League Logo ALWAYS assigned (Fixes Racing/Individual sports missing logos)
                            processed_ev['l_logo_url'] = cur_l_logo
                            processed_ev['l_logo_id'] = "league_" + cur_l_id if cur_l_id else ''
                            if cur_l_logo and cur_l_id:
                                self.prefetch_logo(cur_l_logo, processed_ev['l_logo_id'])
                            
                            self.event_map[str(eid)] = processed_ev
                            if is_changed: 
                                changed_events.append(processed_ev)
                                has_changes = True
                                
                    # REAPING Stability Fix: Remove entries for THIS specific league that were not in this response.
                    # This prevents matches from appearing/disappearing if unrelated requests fail/timeout.
                    now_date = datetime.now().strftime("%Y-%m-%d")
                    reap_keys = []
                    for mid, ex_ev in self.event_map.items():
                        if ex_ev.get('league_name') != league_name: continue
                        if ex_ev.get('league_url') != l_url: continue
                        if mid in league_seen_ids: continue
                        
                        ex_state = ex_ev.get('status', {}).get('type', {}).get('state', 'pre')
                        ex_date  = ex_ev.get('date', '')[:10]
                        if ex_state == 'pre' and ex_date > now_date:
                            continue # Keep tomorrow's matches
                        reap_keys.append(mid)
                    for rk in reap_keys:
                        if rk in self.event_map: del self.event_map[rk]
                    if reap_keys: has_changes = True
                except: pass
            
            # Rebuild cached_events from map
            unique_list = list(self.event_map.values())
            
            # --- STABLE SORT: STATUS + SPORT + DATE + LEAGUE + ID ---
            # Priority (Ascending for now, consumed/sorted elsewhere):
            # 1) Post=0, Pre=1, Live=2
            # 2) Other=0, Soccer=1
            def get_sort_key(ev):
                status = ev.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                if state == 'post': status_priority = 0
                elif state == 'pre': status_priority = 1
                else: status_priority = 2  # 'in'
                
                # Soccer Priority
                l_url = ev.get('league_url', '')
                sport_priority = 1 if 'soccer' in l_url else 0
                
                return (status_priority, sport_priority, ev.get('date', ''), ev.get('league_name', ''), ev.get('id', ''))
            
            unique_list.sort(key=get_sort_key)
            self.cached_events = unique_list
            
            # Build normalized snapshots for all UI consumers
            if append_mode:
                # INCREMENTAL: Only rebuild snapshots for events that actually changed
                for ev in changed_events:
                    eid = ev.get('id')
                    if eid:
                        self.match_snapshots[str(eid)] = build_match_snapshot(ev)
                # Also rebuild snapshots for any new events not yet in match_snapshots
                for ev in self.cached_events:
                    eid = ev.get('id')
                    if eid and str(eid) not in self.match_snapshots:
                        self.match_snapshots[str(eid)] = build_match_snapshot(ev)
                log_dbg("SNAPSHOTS: Incremental \u2014 rebuilt {} changed, {} total".format(
                    len(changed_events), len(self.match_snapshots)))
                # NOTE: evaluate_goals() deferred to finalize_batch() for append_mode
            else:
                # FULL REBUILD: Single league mode \u2014 rebuild everything
                self.match_snapshots = {}
                for ev in self.cached_events:
                    eid = ev.get('id')
                    if eid:
                        self.match_snapshots[str(eid)] = build_match_snapshot(ev)
                
                # TRIGGER: Evaluate goals IMMEDIATELY after snapshots are built
                self.evaluate_goals()
                log_dbg("SNAPSHOTS: Full rebuild \u2014 {} snapshots".format(len(self.match_snapshots)))
            
            # Only set status message if there's an actual issue (no matches)
            if len(self.cached_events) == 0: self.status_message = "No Matches Found"
            
            # Set flag for UI to know if it needs to rebuild
            if len(unique_list) != len(self.cached_events):
                has_changes = True
            self.has_changes = has_changes

            live_count = 0

            now = time.time()
            for i, event in enumerate(unique_list):
                # Yield Enigma2 processor control every 10 parsed events
                if i > 0 and i % 10 == 0: yield

                status = event.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                if state == 'in':
                    live_count += 1
                elif state == 'pre':
                    # SMART POLLING: Count matches starting in the next 15 minutes as "live"
                    try:
                        m_date = event.get('date', '')
                        if m_date:
                            dt = datetime.strptime(m_date[:16], "%Y-%m-%dT%H:%M")
                            m_ts = calendar.timegm(dt.timetuple())
                            if 0 <= (m_ts - now) <= 900: # 900s = 15m
                                live_count += 1
                    except: pass
            
            # ADAPTIVE POLLING: 60s for Live/Near-start, 300s for Idle
            # FIX: Ensure timer restarts if UI is active (callbacks) or reminders exist
            should_run = self.active or (len(self.callbacks) > 0) or (len(self.reminders) > 0)
            if should_run and not self.batch_is_active:
                new_interval = self._get_timer_interval(live_count)
                log_diag("LAZY_PROCESS: Restarting timer in {}ms (active={} callbacks={} reminders={})".format(
                    new_interval, self.active, len(self.callbacks), len(self.reminders)))
                self.timer.start(new_interval, False)
        except:
            self.status_message = "JSON Parse Error"
            if not self.batch_is_active:
                for cb in self.callbacks: cb(True)

if global_sports_monitor is None:
    global_sports_monitor = SportsMonitor()




# ==============================================================================
# MISSING HELPERS & GAME INFO SCREEN
# ==============================================================================
# Consolidated into line 647

# ==============================================================================
# ==============================================================================
# UPDATED LIST RENDERERS (Added TextListEntry for News/Preview)
# ==============================================================================
def StatsListEntry(label, home_val, away_val, theme_mode):
    """3-Column Layout: [ HOME ] [ LABEL/TIME ] [ AWAY ]"""
    if theme_mode == "ucl":
        col_label, col_val, col_bg, col_sel = 0x00ffff, 0xffffff, 0x0e1e5b, 0x182c82
    else:
        col_label, col_val, col_bg, col_sel = 0x00FF85, 0xFFFFFF, 0x33190028, 0x444444
        
    # Layout: Centered Block. Total width ~1320px
    # Home (400) | Label (520) | Away (400)
    h_x, h_w = 140, 400; l_x, l_w = 540, 520; a_x, a_w = 1060, 400
    res = [None]
    # Highlight full row when selected
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1600, 50, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, col_bg, col_sel))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 100, 48, 1400, 2, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, col_bg, col_sel))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, l_x, 0, l_w, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(label).upper(), col_label, col_label, col_bg, col_sel))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, h_x, 0, h_w, 50, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, str(home_val), col_val, col_val, col_bg, col_sel))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, a_x, 0, a_w, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(away_val), col_val, col_val, col_bg, col_sel))
    return res

def EventListEntry(label, home_val, away_val, theme_mode, h_color=None, a_color=None, payload=None):
    """3-Column Layout for Events (Goals/Cards/Subs) - Optimized for 1600px Width"""
    if theme_mode == "ucl":
        col_label, col_val, col_bg, col_sel = 0x00ffff, 0xffffff, 0x0e1e5b, 0x182c82
    else:
        col_label, col_val, col_bg, col_sel = 0x00FF85, 0xFFFFFF, 0x33190028, 0x444444
    
    # Use custom colors if provided, otherwise default
    col_h = h_color if h_color is not None else col_val
    col_a = a_color if a_color is not None else col_val
    
    # Centered Layout for 1600px width: Center column at 800
    l_x, l_w = 740, 120   # Time label centered (740 + 60 = 800 center)
    h_x, h_w = 90, 640    # Home events on left, right-aligned towards center
    a_x, a_w = 870, 640   # Away events on right, left-aligned from center

    res = [payload]
    # Full Row Highlight (base)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1600, 50, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, col_bg, col_sel))
    # Background line separator
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 48, 1550, 2, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, col_bg, col_sel))
    
    # Time/Label (Center)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, l_x, 0, l_w, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(label), col_label, col_label, col_bg, col_sel))
    # Home Event (Right)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, h_x, 0, h_w, 50, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, str(home_val), col_h, col_h, col_bg, col_sel))
    # Away Event (Left)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, a_x, 0, a_w, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(away_val), col_a, col_a, col_bg, col_sel))
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
    
    h_x, h_w = 220, 560; a_x, a_w = 820, 560
    res = [None]
    # Add separator line
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 200, 48, 1200, 2, 0, RT_HALIGN_CENTER, "", col_sep, col_sep, 1))
    # Background for headers
    if is_header:
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 200, 0, 1200, 50, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, 1))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, h_x, 0, h_w, 50, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, str(home_player), col_text, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, a_x, 0, a_w, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(away_player), col_text, 0xFFFFFF))
    return res

def TextListEntry(text, theme_mode, align="center", is_header=False):
    """1-Column Layout for News/Facts/Preview Text"""
    if theme_mode == "ucl": 
        col_text = 0x00ffff if is_header else 0xffffff
        col_bg = 0x0e1e5b if is_header else None
        col_sel = 0x182c82
    else: 
        col_text = 0x00FF85 if is_header else 0xFFFFFF
        col_bg = 0x33190028 if is_header else None
        col_sel = 0x444444
        
    bg_actual = col_bg if col_bg is not None else 0x00000000
    
    flags = RT_HALIGN_CENTER | RT_VALIGN_CENTER
    if align == "left": flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER
    
    res = [None]
    # Highlight full row when selected
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1600, 50, 0, RT_HALIGN_CENTER, "", bg_actual, bg_actual, bg_actual, col_sel))
    
    # Background line if header
    if is_header:
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 40, 0, 1520, 50, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, bg_actual, col_sel))
    
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 40, 0, 1520, 50, 0, flags, str(text), col_text, col_text, bg_actual, col_sel))
    return res

def VoteListEntry(team_type, team_name, votes, total_votes, theme_mode, has_voted=False, is_pre_match=True):
    """Draws a 2-Column Layout for Voting with Percentages and Lockout states."""
    pct = (votes / float(total_votes) * 100) if total_votes > 0 else 0.0
    
    # 1. NEW LOGIC: Determine what text to show based on match state
    if not is_pre_match:
        display_text = "{}  -  {} Votes ({:.1f}%)  [VOTING CLOSED]".format(team_name, votes, pct)
    elif has_voted or total_votes > 0:
        display_text = "{}  -  {} Votes ({:.1f}%)".format(team_name, votes, pct)
    else:
        display_text = "{}  -  Press OK to Vote!".format(team_name)

    if theme_mode == "ucl":
        col_text, col_bg, col_sel = 0xffffff, 0x051030, 0x182c82
    else:
        col_text, col_bg, col_sel = 0x00FF85, 0x100015, 0x444444
        
    # Payload: ("VOTE", "home" or "away", team_name)
    res = [("VOTE", team_type, team_name)] 
    
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1600, 50, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, col_bg, col_sel))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 40, 0, 1520, 50, 0, RT_HALIGN_CENTER | RT_VALIGN_CENTER, display_text, col_text, col_text, col_bg, col_sel))
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
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 230, 48, 1140, 2, 0, RT_HALIGN_CENTER, "", col_dim, col_dim, 1))
    # Background for header
    if is_header:
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 230, 0, 1140, 50, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, 1))
    
    # Table columns: Pos(60) | Team(420) | P(80) | W(80) | D(80) | L(80) | GD(100) | Pts(80)
    # Start X offset: 280 (Centered for Total Width 1040)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 280, 0, 60, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(pos), col_text, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 350, 0, 420, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(team), col_text, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 780, 0, 80, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(played), col_dim if not is_header else col_text, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 860, 0, 80, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(won), col_dim if not is_header else col_text, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 940, 0, 80, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(draw), col_dim if not is_header else col_text, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 1020, 0, 80, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(lost), col_dim if not is_header else col_text, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 1100, 0, 100, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(gd), col_dim if not is_header else col_text, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 1220, 0, 80, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(pts), col_text, 0xFFFFFF))
    return res

def RacingStandingEntry(rank, driver, country, pts, theme_mode, is_header=False):
    """Racing Championship Table Row: Rank | Driver | Country | Points"""
    if theme_mode == "ucl":
        col_text = 0x00ffff if is_header else 0xffffff
        col_accent = 0xffd700
        col_bg = 0x0e1e5b if is_header else None
        col_dim = 0x888888
    else:
        col_text = 0x00FF85 if is_header else 0xffffff
        col_accent = 0xffd700
        col_bg = 0x28002C if is_header else None
        col_dim = 0x888888
    
    # Highlight top 3 positions
    try:
        if not is_header and int(rank) <= 3:
            col_text = col_accent
    except: pass
    
    res = [None]
    # Separator line
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 230, 48, 1140, 2, 0, RT_HALIGN_CENTER, "", col_dim, col_dim, 1))
    # Background for header
    if is_header:
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 230, 0, 1140, 50, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, 1))
    
    # Racing columns: Rank(80) | Driver(550) | Country(250) | Points(120)
    # Start X offset: 280, Total Width ~1000
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 280, 0, 80, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(rank), col_text, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 370, 0, 550, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(driver), col_text, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 930, 0, 250, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(country), col_dim if not is_header else col_text, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 1200, 0, 120, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(pts), col_text, 0xFFFFFF))
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
        
        # --- SKIN (1600x900 Upgrade) ---
        if self.theme == "ucl":
            bg_color = "#00000000"; top_bar = "#091442"; accent = "#00ffff"
            self.skin = f"""<screen position="center,center" size="1600,900" title="League Standings" flags="wfNoBorder" backgroundColor="{bg_color}">
                <eLabel position="0,0" size="1600,150" backgroundColor="{top_bar}" zPosition="0" />
                <eLabel position="0,150" size="1600,4" backgroundColor="{accent}" zPosition="1" />
                <widget name="title" position="0,50" size="1600,40" font="Regular;32" foregroundColor="{accent}" backgroundColor="{top_bar}" transparent="1" halign="center" valign="center" zPosition="5" />
                <widget name="subtitle" position="0,90" size="1600,25" font="Regular;20" foregroundColor="#aaaaaa" backgroundColor="{top_bar}" transparent="1" halign="center" valign="center" zPosition="5" />
                <widget name="standings_list" position="0,160" size="1600,700" scrollbarMode="showNever" transparent="1" zPosition="5" />
                <widget name="loading" position="0,400" size="1600,100" font="Regular;32" foregroundColor="{accent}" transparent="1" halign="center" zPosition="10" />
                <widget name="hint" position="0,860" size="1600,30" font="Regular;20" foregroundColor="#888888" transparent="1" halign="center" zPosition="5" />
            </screen>"""
        else:
            bg_color = "#38003C"; top_bar = "#28002C"; accent = "#00FF85"
            self.skin = f"""<screen position="center,center" size="1600,900" title="League Standings" flags="wfNoBorder" backgroundColor="{bg_color}">
                <eLabel position="0,0" size="1600,150" backgroundColor="{top_bar}" zPosition="0" />
                <eLabel position="0,150" size="1600,4" backgroundColor="{accent}" zPosition="1" />
                <widget name="title" position="0,50" size="1600,40" font="Regular;32" foregroundColor="{accent}" backgroundColor="{top_bar}" transparent="1" halign="center" valign="center" zPosition="5" />
                <widget name="subtitle" position="0,90" size="1600,25" font="Regular;20" foregroundColor="#aaaaaa" backgroundColor="{top_bar}" transparent="1" halign="center" valign="center" zPosition="5" />
                <widget name="standings_list" position="0,160" size="1600,700" scrollbarMode="showNever" transparent="1" zPosition="5" />
                <widget name="loading" position="0,400" size="1600,100" font="Regular;32" foregroundColor="{accent}" transparent="1" halign="center" zPosition="10" />
                <widget name="hint" position="0,860" size="1600,30" font="Regular;20" foregroundColor="#888888" transparent="1" halign="center" zPosition="5" />
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
        self.items_per_page = 14
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

        url = (self.league_url or '').lower()

        # Sports with no ESPN standings endpoint — show message immediately
        NO_STANDINGS_SPORTS = ('tennis', 'golf', 'mma', 'boxing')
        for ns in NO_STANDINGS_SPORTS:
            if ns in url:
                self["loading"].hide()
                label = ns.upper() if ns != 'mma' else 'MMA / Boxing'
                self.standings_rows = [
                    StandingTableEntry("-", "{} does not have league standings.".format(label),
                                       "-", "-", "-", "-", "-", "-", self.theme)
                ]
                self.current_page = 0
                self.update_display()
                return

        # Build standings URL from the league scoreboard URL
        # Pattern: .../sports/{sport}/{league}/scoreboard  →  .../sports/{sport}/{league}/standings
        # Some sport-only URLs (e.g. boxing) have no league slug - handled above.
        standings_url = ""
        try:
            parts = self.league_url.split('/')
            sport_idx = -1
            for i, p in enumerate(parts):
                if p == 'sports' and i + 1 < len(parts):
                    sport_idx = i
                    break

            if sport_idx >= 0:
                sport = parts[sport_idx + 1]
                # parts[sport_idx + 2] could be the league slug OR 'scoreboard' for sport-only URLs
                if sport_idx + 2 < len(parts):
                    candidate = parts[sport_idx + 2].split('?')[0]
                    if candidate and candidate != 'scoreboard':
                        league = candidate
                        standings_url = "https://site.api.espn.com/apis/v2/sports/{}/{}/standings".format(sport, league)
                    else:
                        # No league slug — no standings endpoint available
                        standings_url = ""
        except Exception as e:
            log_dbg("fetch_standings URL build error: " + str(e))

        if not standings_url:
            self["loading"].hide()
            self.standings_rows = [
                StandingTableEntry("-", "No standings available for this league.", "-", "-", "-", "-", "-", "-", self.theme)
            ]
            self.current_page = 0
            self.update_display()
            return

        log_dbg("fetch_standings URL: " + standings_url)

        from twisted.web.client import Agent, readBody
        from twisted.internet import reactor
        self._standings_url = standings_url
        agent = Agent(reactor)
        d = agent.request(b'GET', standings_url.encode('utf-8'))
        d.addCallback(self.on_response)
        d.addErrback(self.on_error)

    def on_response(self, response):
        from twisted.web.client import readBody
        status = response.code
        log_dbg("standings HTTP status: " + str(status))
        if status != 200:
            self["loading"].setText("Standings unavailable (HTTP {})".format(status))
            return
        d = readBody(response)
        d.addCallback(self.parse_standings)
        d.addErrback(self.on_error)

    def on_error(self, error):
        log_dbg("standings fetch error: " + str(error))
        self["loading"].setText("Failed to load standings")
    
    def parse_standings(self, body):
        try:
            # Log raw body prefix for debugging
            try:
                body_str = body if isinstance(body, str) else body.decode('utf-8', errors='replace')
                log_dbg("standings body[0:600]: " + body_str[:600])
            except: pass

            data = json.loads(body)
        except Exception as e:
            log_dbg("standings JSON parse error: " + str(e))
            self["loading"].setText("Error parsing standings data")
            return

        try:
            self["loading"].hide()
            log_dbg("standings type: " + str(type(data).__name__))
            log_dbg("standings keys: " + str(list(data.keys()) if isinstance(data, dict) else str(data)[:200]))

            # ----------------------------------------------------------------
            # HELPERS
            # ----------------------------------------------------------------
            def clean_num(val):
                try:
                    f = float(str(val))
                    return str(int(f)) if f == int(f) else str(val)
                except: return str(val)

            def clean_pct(val):
                try: return "{:.3f}".format(float(str(val)))
                except: return str(val)

            def build_stats_map(stats):
                m = {}
                for stat in (stats or []):
                    # Use 'name' key first, fall back to 'abbreviation'
                    key = (stat.get('name') or stat.get('abbreviation') or '').lower()
                    if key:
                        # Prefer numeric 'value' for sorting; keep 'displayValue' for display
                        m[key] = stat.get('displayValue', stat.get('value', ''))
                        m[key + '__val'] = stat.get('value', stat.get('displayValue', 0))
                return m

            def sget(m, *keys):
                """Get first matching key from stats map (display value)."""
                for k in keys:
                    v = m.get(k)
                    if v is not None and str(v) not in ('', 'None'): return str(v)
                return '-'

            def sort_keys(m):
                rank = 999
                try: rank = int(float(str(m.get('rank', m.get('position', m.get('playoffseed', 999))))))
                except: pass
                pct = 0.0
                try: pct = float(str(m.get('winpercent', m.get('pct', m.get('winningpct', m.get('pointspercentage', 0))))))
                except: pass
                pts = 0.0
                try: pts = float(str(m.get('points__val', m.get('points', 0))))
                except: pass
                wins = 0
                try: wins = int(float(str(m.get('wins__val', m.get('wins', m.get('w', 0))))))
                except: pass
                return rank, pct, pts, wins

            # ----------------------------------------------------------------
            # RECURSIVE ENTRY COLLECTOR
            # Walks the entire JSON tree, collecting all arrays of entries that
            # contain dicts with a 'team' key (standard ESPN standings entries).
            # Returns list of (group_label, [entry, ...]) tuples in order found.
            # ----------------------------------------------------------------
            def collect_entry_groups(node, label="", depth=0):
                groups = []
                if depth > 10: return groups
                if isinstance(node, dict):
                    # If this node has a 'standings' sub-object with 'entries'
                    standing_sub = node.get('standings')
                    if isinstance(standing_sub, dict):
                        entries = standing_sub.get('entries', [])
                        team_entries = [e for e in entries if isinstance(e, dict) and 'team' in e]
                        if team_entries:
                            lbl = node.get('name', label) or label
                            groups.append((lbl, team_entries))
                            return groups  # Don't descend further — children are sub-groups

                    # If this node directly has 'entries'
                    direct = node.get('entries', [])
                    if direct:
                        team_entries = [e for e in direct if isinstance(e, dict) and 'team' in e]
                        if team_entries:
                            lbl = node.get('name', label) or label
                            groups.append((lbl, team_entries))
                            return groups

                    # Recurse into 'children'
                    for child in node.get('children', []):
                        child_label = child.get('name', '') if isinstance(child, dict) else ''
                        groups.extend(collect_entry_groups(child, child_label, depth + 1))

                    # Recurse into 'standings' as a list
                    standings_list = node.get('standings', [])
                    if isinstance(standings_list, list):
                        for item in standings_list:
                            groups.extend(collect_entry_groups(item, label, depth + 1))

                elif isinstance(node, list):
                    for item in node:
                        groups.extend(collect_entry_groups(item, label, depth + 1))

                return groups

            # ----------------------------------------------------------------
            # RACING — athlete-based entries (no 'team' key)
            # ----------------------------------------------------------------
            def collect_racing_entries(node, depth=0):
                entries = []
                if depth > 8: return entries
                if isinstance(node, dict):
                    sub_entries = (node.get('standings', {}) or {}).get('entries', [])
                    if not sub_entries: sub_entries = node.get('entries', [])
                    ath_entries = [e for e in sub_entries if isinstance(e, dict) and 'athlete' in e]
                    if ath_entries:
                        entries.extend(ath_entries)
                    else:
                        for child in node.get('children', []):
                            entries.extend(collect_racing_entries(child, depth + 1))
                elif isinstance(node, list):
                    for item in node:
                        entries.extend(collect_racing_entries(item, depth + 1))
                return entries

            # ----------------------------------------------------------------
            # ENTRY PARSER — soccer/standard  (P W D L GD PTS)
            # ----------------------------------------------------------------
            def parse_soccer_entry(entry):
                team_data = entry.get('team', {})
                team_name = (team_data.get('displayName') or team_data.get('shortDisplayName') or
                             team_data.get('name') or 'Unknown')
                m = build_stats_map(entry.get('stats', []))
                rank, pct, pts_f, wins = sort_keys(m)
                pos = str(rank) if rank != 999 else sget(m, 'playoffseed', 'rank')
                return {
                    'pos': pos,
                    'team': team_name,
                    'p':   clean_num(sget(m, 'gamesplayed', 'played', 'p')),
                    'w':   clean_num(sget(m, 'wins', 'w')),
                    'd':   clean_num(sget(m, 'ties', 'draws', 'd')),
                    'l':   clean_num(sget(m, 'losses', 'l')),
                    'gd':  clean_num(sget(m, 'pointdifferential', 'goaldifference', 'gd')),
                    'pts': clean_num(sget(m, 'points', 'pts')),
                    '_rank': rank, '_pct': pct, '_wins': wins,
                }

            def parse_american_entry(entry, sport_type):
                team_data = entry.get('team', {})
                team_name = (team_data.get('displayName') or team_data.get('shortDisplayName') or
                             team_data.get('name') or 'Unknown')
                m = build_stats_map(entry.get('stats', []))
                rank, pct, pts_f, wins = sort_keys(m)
                pos = str(rank) if rank != 999 else '-'
                w = sget(m, 'wins', 'w')
                l = sget(m, 'losses', 'l')
                if sport_type == 'football':
                    return {'pos': pos, 'team': team_name, 'p': w, 'w': l,
                            'd': sget(m, 'ties', 't'), 'l': clean_pct(sget(m, 'winpercent', 'pct')),
                            'gd': '', 'pts': '', '_rank': rank, '_pct': pct, '_wins': wins}
                elif sport_type == 'baseball':
                    return {'pos': pos, 'team': team_name, 'p': w, 'w': l,
                            'd': clean_pct(sget(m, 'winpercent', 'pct')),
                            'l': sget(m, 'gamesbehind', 'gb'),
                            'gd': '', 'pts': '', '_rank': rank, '_pct': pct, '_wins': wins}
                elif sport_type == 'hockey':
                    return {'pos': pos, 'team': team_name, 'p': w, 'w': l,
                            'd': sget(m, 'otlosses', 'overtimelosses', 'ot'),
                            'l': sget(m, 'points', 'pts'),
                            'gd': '', 'pts': '', '_rank': rank, '_pct': pct, '_wins': wins}
                else:
                    return {'pos': pos, 'team': team_name, 'p': w, 'w': l,
                            'd': '-', 'l': '-', 'gd': '-', 'pts': '-',
                            '_rank': rank, '_pct': pct, '_wins': wins}

            def sort_entries(entries_list):
                entries_list.sort(key=lambda x: x['_rank'] if x['_rank'] != 999 else (-x['_pct'], -x['_wins']))

            def add_group_to_rows(lbl, parsed, hdr_cols):
                if lbl:
                    self.standings_rows.append(StandingTableEntry("", lbl.upper(), "", "", "", "", "", "", self.theme, is_header=True))
                self.standings_rows.append(StandingTableEntry(*hdr_cols, **{'theme_mode': self.theme, 'is_header': True}))
                for item in parsed:
                    self.standings_rows.append(StandingTableEntry(
                        item['pos'], item['team'], item['p'], item['w'],
                        item['d'], item['l'], item['gd'], item['pts'], self.theme))
                self.standings_rows.append(StandingTableEntry("", "", "", "", "", "", "", "", self.theme))

            # ----------------------------------------------------------------
            # SPORT TYPE DETECTION
            # ----------------------------------------------------------------
            lurl = (self.league_url or '').lower()
            is_racing    = 'racing'     in lurl
            is_football  = 'football'   in lurl
            is_baseball  = 'baseball'   in lurl
            is_hockey    = 'hockey'     in lurl
            is_basketball = ('basketball' in lurl or 'nba' in lurl or 'wnba' in lurl
                             or 'euroleague' in lurl)
            is_rugby     = 'rugby'      in lurl
            is_cricket   = 'cricket'    in lurl
            is_lacrosse  = 'lacrosse'   in lurl

            self.standings_rows = []

            # ================================================================
            # RACING
            # ================================================================
            if is_racing:
                all_entries = collect_racing_entries(data)
                log_dbg("racing entries found: " + str(len(all_entries)))
                if all_entries:
                    self.standings_rows.append(RacingStandingEntry("RK", "DRIVER", "COUNTRY", "PTS", self.theme, is_header=True))
                    for entry in all_entries:
                        athlete = entry.get('athlete', {})
                        driver_name = athlete.get('displayName') or athlete.get('name') or 'Unknown'
                        country = athlete.get('flag', {}).get('alt', '')
                        rank_val = '-'; pts_val = '-'
                        for stat in entry.get('stats', []):
                            if stat.get('name') == 'rank': rank_val = stat.get('displayValue', '-')
                            elif stat.get('name') == 'championshipPts': pts_val = stat.get('displayValue', '-')
                        self.standings_rows.append(RacingStandingEntry(str(rank_val), driver_name, country, str(pts_val), self.theme))

            # ================================================================
            # AMERICAN FOOTBALL (NFL / NCAA Football / UFL)
            # ================================================================
            elif is_football:
                hdr = ("#", "TEAM", "W", "L", "T", "PCT", "", "")
                groups = collect_entry_groups(data)
                log_dbg("football groups found: " + str(len(groups)))
                for lbl, raw_entries in groups:
                    parsed = [parse_american_entry(e, 'football') for e in raw_entries]
                    sort_entries(parsed)
                    add_group_to_rows(lbl, parsed, hdr)

            # ================================================================
            # BASEBALL (MLB / NCAA Baseball)
            # ================================================================
            elif is_baseball:
                hdr = ("#", "TEAM", "W", "L", "PCT", "GB", "", "")
                groups = collect_entry_groups(data)
                log_dbg("baseball groups found: " + str(len(groups)))
                for lbl, raw_entries in groups:
                    parsed = [parse_american_entry(e, 'baseball') for e in raw_entries]
                    sort_entries(parsed)
                    add_group_to_rows(lbl, parsed, hdr)

            # ================================================================
            # HOCKEY (NHL)
            # ================================================================
            elif is_hockey:
                hdr = ("#", "TEAM", "W", "L", "OT", "PTS", "", "")
                groups = collect_entry_groups(data)
                log_dbg("hockey groups found: " + str(len(groups)))
                for lbl, raw_entries in groups:
                    parsed = [parse_american_entry(e, 'hockey') for e in raw_entries]
                    sort_entries(parsed)
                    add_group_to_rows(lbl, parsed, hdr)

            # ================================================================
            # BASKETBALL / RUGBY / LACROSSE  (W D L GD PTS)
            # ================================================================
            elif is_basketball or is_rugby or is_lacrosse:
                hdr = ("#", "TEAM", "GP", "W", "D", "L", "DIFF", "PTS")
                groups = collect_entry_groups(data)
                log_dbg("basket/rugby/lacrosse groups found: " + str(len(groups)))
                # If multiple groups, also show an overall table
                if len(groups) > 1:
                    all_flat = []
                    for lbl, raw_entries in groups:
                        all_flat.extend([parse_soccer_entry(e) for e in raw_entries])
                    all_flat.sort(key=lambda x: (-x['_pct'], -x['_wins']))
                    self.standings_rows.append(StandingTableEntry("", "OVERALL STANDINGS", "", "", "", "", "", "", self.theme, is_header=True))
                    self.standings_rows.append(StandingTableEntry(hdr[0], hdr[1], hdr[2], hdr[3], hdr[4], hdr[5], hdr[6], hdr[7], self.theme, is_header=True))
                    for idx, item in enumerate(all_flat):
                        self.standings_rows.append(StandingTableEntry(str(idx + 1), item['team'], item['p'], item['w'], item['d'], item['l'], item['gd'], item['pts'], self.theme))
                    self.standings_rows.append(StandingTableEntry("", "", "", "", "", "", "", "", self.theme))
                for lbl, raw_entries in groups:
                    parsed = [parse_soccer_entry(e) for e in raw_entries]
                    sort_entries(parsed)
                    add_group_to_rows(lbl, parsed, hdr)

            # ================================================================
            # CRICKET
            # ================================================================
            elif is_cricket:
                hdr = ("#", "TEAM", "W", "L", "NR", "PTS", "NRR", "")
                groups = collect_entry_groups(data)
                log_dbg("cricket groups found: " + str(len(groups)))
                for lbl, raw_entries in groups:
                    if lbl:
                        self.standings_rows.append(StandingTableEntry("", lbl.upper(), "", "", "", "", "", "", self.theme, is_header=True))
                    self.standings_rows.append(StandingTableEntry(hdr[0], hdr[1], hdr[2], hdr[3], hdr[4], hdr[5], hdr[6], hdr[7], self.theme, is_header=True))
                    parsed_cricket = []
                    for entry in raw_entries:
                        try:
                            team_data = entry.get('team', {})
                            team_name = team_data.get('displayName') or team_data.get('name') or 'Unknown'
                            m = build_stats_map(entry.get('stats', []))
                            rank, _, _, _ = sort_keys(m)
                            nrr = sget(m, 'netrunrate', 'nrr')
                            try: nrr = "{:+.3f}".format(float(nrr))
                            except: pass
                            pos = str(rank) if rank != 999 else '-'
                            parsed_cricket.append({
                                'pos': pos, 'team': team_name,
                                'p':   sget(m, 'wins', 'w'),
                                'w':   sget(m, 'losses', 'l'),
                                'd':   sget(m, 'noresult', 'nr'),
                                'l':   sget(m, 'points', 'pts'),
                                'gd':  nrr, 'pts': '', '_rank': rank
                            })
                        except: continue
                    parsed_cricket.sort(key=lambda x: x['_rank'] if x['_rank'] != 999 else 999)
                    for item in parsed_cricket:
                        self.standings_rows.append(StandingTableEntry(item['pos'], item['team'], item['p'], item['w'], item['d'], item['l'], item['gd'], item['pts'], self.theme))
                    self.standings_rows.append(StandingTableEntry("", "", "", "", "", "", "", "", self.theme))

            # ================================================================
            # SOCCER / STANDARD  (P W D L GD PTS)
            # ================================================================
            else:
                hdr = ("#", "TEAM", "P", "W", "D", "L", "GD", "PTS")
                groups = collect_entry_groups(data)
                log_dbg("soccer groups found: " + str(len(groups)))
                if len(groups) > 1:
                    # Multi-group league (e.g. Copa Libertadores group stage) — show each
                    for lbl, raw_entries in groups:
                        parsed = [parse_soccer_entry(e) for e in raw_entries]
                        sort_entries(parsed)
                        add_group_to_rows(lbl, parsed, hdr)
                elif groups:
                    lbl, raw_entries = groups[0]
                    parsed = [parse_soccer_entry(e) for e in raw_entries]
                    sort_entries(parsed)
                    # Single group — just the header row, no sub-label
                    self.standings_rows.append(StandingTableEntry(hdr[0], hdr[1], hdr[2], hdr[3], hdr[4], hdr[5], hdr[6], hdr[7], self.theme, is_header=True))
                    for item in parsed:
                        self.standings_rows.append(StandingTableEntry(item['pos'], item['team'], item['p'], item['w'], item['d'], item['l'], item['gd'], item['pts'], self.theme))

            # ================================================================
            # FALLBACK
            # ================================================================
            if not self.standings_rows:
                log_dbg("standings: no rows produced for " + str(self.league_url))
                self.standings_rows.append(StandingTableEntry("-", "No standings data available", "-", "-", "-", "-", "-", "-", self.theme))

            self.current_page = 0
            self.update_display()

        except Exception as e:
            import traceback
            log_dbg("parse_standings exception: " + str(e) + " | " + traceback.format_exc()[-300:])
            self["loading"].setText("Error: " + str(e))

# ==============================================================================
# GAME INFO SCREEN (UPDATED: "Facebook Style" News Feed)
# ==============================================================================
class SimplePlayer(Screen):
    def __init__(self, session, sref=None, playlist=None):
        Screen.__init__(self, session)
        self.session = session
        self.playlist = playlist
        self.playlist_index = 0
        self.is_listening = False
        self.is_advancing = False
        self.retry_count = {}
        
        # Prefetching Variables
        self.prefetch_client = None
        self.buffer_path = "/tmp/ss_buf_A.mp4"
        self.next_buffer_path = "/tmp/ss_buf_B.mp4"
        self.current_prefetch_url = ""
        self.is_prefetching = False
        
        # Helper to clean buffers on start (ONLY if not inheriting an active prefetch)
        if not hasattr(global_sports_monitor, 'active_prefetch_url'):
            if os.path.exists(self.buffer_path): os.remove(self.buffer_path)
            if os.path.exists(self.next_buffer_path): os.remove(self.next_buffer_path)
        
        # Save current service to restore later
        self.restore_service = self.session.nav.getCurrentlyPlayingServiceReference()
        
        # Prefetch coordination: If GameInfo already started a prefetch, inherit it
        if hasattr(global_sports_monitor, 'active_prefetch_url'):
            self.current_prefetch_url = global_sports_monitor.active_prefetch_url
            # Don't delete buffer A if it's the one being used by active_prefetch
            print("[SimplySport] SimplePlayer: Inherited prefetch for " + self.current_prefetch_url)
        
        # Transparent background for video overlay
        self.skin = """<screen position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="#ff000000">
            <widget name="video_title" position="50,50" size="1000,60" font="Regular;40" foregroundColor="#ffffff" backgroundColor="#000000" transparent="1" zPosition="1" />
            <widget name="progress" position="50,120" size="1000,30" font="Regular;24" foregroundColor="#00FF85" backgroundColor="#000000" transparent="1" zPosition="1" />
            <widget name="hint" position="50,970" size="1820,60" font="Regular;28" foregroundColor="#aaaaaa" backgroundColor="#000000" transparent="1" halign="center" zPosition="1" />
        </screen>"""
        self["video_title"] = Label("Loading Stream...")
        self["progress"] = Label("")
        self["hint"] = Label("◄► Skip | OK/Exit: Stop")
        
        self["actions"] = ActionMap(["OkCancelActions", "InfobarSeekActions", "DirectionActions"], {
            "cancel": self.close, 
            "ok": self.close,
            "seekFwd": self.next_video,      # >> button
            "seekBack": self.prev_video,     # << button
            "right": self.next_video,
            "left": self.prev_video,
        }, -2)
        
        self.sref = sref
        self.onLayoutFinish.append(self.play)

    def prefetch_next(self, index):
        return # DISABLED for stability (user request: less aggressive)
        
        url, title = self.playlist[index]
        
        # Strip User-Agent fragment for downloadPage
        clean_url = url.split('#')[0]
        
        # Only prefetch MP4s (HLS not supported for simple file download)
        if ".m3u8" in clean_url: return
        
        # Determine target buffer (ping-pong)
        target_path = self.next_buffer_path if self.buffer_path == "/tmp/ss_buf_A.mp4" else "/tmp/ss_buf_A.mp4"
        
        # Avoid duplicate requests
        if self.is_prefetching and self.current_prefetch_url == clean_url: return
        
        self.is_prefetching = True
        self.current_prefetch_url = clean_url
        
        print("[SimplySport] Prefetching: " + title)
        
        # Use simple downloadPage with Agent for better control? 
        # Using twisted.web.client.downloadPage for simplicity as used elsewhere
        from twisted.web.client import downloadPage
        
        # NEW: Cancel existing prefetch if active
        if self.prefetch_client:
            try: self.prefetch_client.cancel()
            except: pass

        self.prefetch_client = downloadPage(clean_url.encode('utf-8'), target_path)
        self.prefetch_client.addCallback(self.prefetch_done, target_path, clean_url)
        self.prefetch_client.addErrback(self.prefetch_error)

    def prefetch_done(self, path, url, result):
        print("[SimplySport] Prefetch Complete: " + path)
        self.is_prefetching = False
        # Create a marker or just rely on path check in play()

    def prefetch_error(self, failure):
        print("[SimplySport] Prefetch Error: " + str(failure))
        self.is_prefetching = False

    def next_video(self):
        """Skip to next video in playlist"""
        if not self.playlist or self.is_advancing: return
        
        if self.playlist_index < len(self.playlist) - 1:
            self.is_advancing = True
            self.playlist_index += 1
            print("[SimplySport] Manual Skip Forward to index: {}".format(self.playlist_index))
            from twisted.internet import reactor
            reactor.callLater(0.5, self.play)
    
    def prev_video(self):
        """Go back to previous video"""
        if not self.playlist or self.is_advancing: return
        
        if self.playlist_index > 0:
            self.is_advancing = True
            self.playlist_index -= 1
            print("[SimplySport] Manual Skip Backward to index: {}".format(self.playlist_index))
            from twisted.internet import reactor
            reactor.callLater(0.5, self.play)

    def play(self):
        try:
            self.is_advancing = False
            if self.playlist:
                if self.playlist_index < len(self.playlist):
                    url, title = self.playlist[self.playlist_index]
                    
                    # Add retry counter check
                    current_video_key = "{}".format(self.playlist_index)
                    retries = self.retry_count.get(current_video_key, 0)
                    
                    if retries > 2:
                        print("[SimplySport] Video {} failed after 3 retries, skipping".format(title))
                        self.retry_count[current_video_key] = 0
                        if self.playlist_index < len(self.playlist) - 1:
                            self.playlist_index += 1
                            from twisted.internet import reactor
                            reactor.callLater(0.5, self.play)
                        else:
                            self.close()
                        return
                    
                    self["video_title"].setText("({}/{}) {}".format(
                        self.playlist_index + 1, 
                        len(self.playlist), 
                        title
                    ))
                    self["progress"].setText("Video {}/{}".format(
                        self.playlist_index + 1, 
                        len(self.playlist)
                    ))
                    
                    final_url = url
                    
                    # Detect stream type
                    is_hls = ".m3u8" in url.lower()
                    
                    # Service type based on content
                    if is_hls:
                        # HLS streams use 4097
                        service_type = "4097"
                    else:
                        # MP4/Progressive use 5001 or 4097
                        service_type = "5001" if ".mp4" in url.lower() else "4097"
                    
                    # Construct SREF with proper service type
                    ref = "{}:0:1:0:0:0:0:0:0:0:{}:{}".format(
                        service_type,
                        final_url.replace(":", "%3a"), 
                        title
                    )
                    
                    print("[SimplySport] Playing [{}]: {}".format(service_type, final_url))
                    self.session.nav.playService(eServiceReference(ref))

                    # Record start time for grace period
                    self.start_time = time.time()
                    
                    # Listen for EOF
                    if not self.is_listening:
                        self.session.nav.event.append(self.on_event)
                        self.is_listening = True
                else:
                    self.close()
                    return
            elif self.sref:
                self.session.nav.playService(self.sref)
                self["video_title"].setText("")
        except Exception as e:
            print("[SimplySport] Play error: {}".format(e))
            # Increment retry counter
            current_video_key = "{}".format(self.playlist_index)
            self.retry_count[current_video_key] = self.retry_count.get(current_video_key, 0) + 1
            
            # Retry after delay (2.0s)
            from twisted.internet import reactor
            reactor.callLater(2.0, self.play)

    def on_event(self, event):
        # Enhanced event detection
        # evEOF = 5, evStopped = 8, evUser = 14
        if event in [5, 8]:  # EOF or Stopped
            if self.is_advancing: return
            
            # Grace period: Ignore EOF if within first 5 seconds (buffering)
            if (time.time() - self.start_time) < 5:
                return
            
            print("[SimplySport] Video Finished (Event: {})".format(event))
            
            # Playlist Logic
            if self.playlist:
                self.is_advancing = True
                self.playlist_index += 1
                if self.playlist_index < len(self.playlist):
                    print("[SimplySport] Advancing to index: {}".format(self.playlist_index))
                    from twisted.internet import reactor
                    # Increase delay for stability
                    reactor.callLater(1.2, self.play)
                else:
                    # All videos finished
                    self.close()
            else:
                self.close()

    def close(self, *args, **kwargs):
        try:
            if self.is_listening:
                self.session.nav.event.remove(self.on_event)
                self.is_listening = False
        except: pass
        
        # Cleanup Buffers
        try:
            if hasattr(global_sports_monitor, 'active_prefetch_url'):
                delattr(global_sports_monitor, 'active_prefetch_url')
            if os.path.exists("/tmp/ss_buf_A.mp4"): os.remove("/tmp/ss_buf_A.mp4")
            if os.path.exists("/tmp/ss_buf_B.mp4"): os.remove("/tmp/ss_buf_B.mp4")
        except: pass

        # Restore previous service
        if self.restore_service:
            self.session.nav.playService(self.restore_service)
        else:
            self.session.nav.stopService()
            
        Screen.close(self, *args, **kwargs)


class RacingDriverInfoScreen(Screen):
    def __init__(self, session, driver_data, league_url, event_data):
        Screen.__init__(self, session)
        
        self.driver_data = driver_data
        self.league_url = league_url
        self.event_data = event_data
        
        athlete = driver_data.get('athlete', {})
        self.d_name = athlete.get('displayName', '') or athlete.get('shortName', 'Driver')
        self.d_country = athlete.get('flag', {}).get('alt', '')
        self.d_flag = athlete.get('flag', {}).get('href', '')
        self.d_id = athlete.get('id', '')
        self.t_id = driver_data.get('team', {}).get('id', '')
        self.team_name = driver_data.get('team', {}).get('displayName', '')
        self.rank = driver_data.get('order', '')
        self.points = driver_data.get('score', '')
        self.stats_url = ''
        
        self.skin = (
            u'<screen position="center,center" size="1200,800" title="Driver Profile">'
            u'<widget name="title" position="20,20" size="1160,50" font="Regular;36" foregroundColor="#00FF85" backgroundColor="#000000" transparent="1" halign="center" valign="center" zPosition="1" />'
            u'<widget name="subtitle" position="20,70" size="1160,30" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#000000" transparent="1" halign="center" valign="center" zPosition="1" />'
            u'<widget name="list" position="20,130" size="1160,650" itemHeight="60" scrollbarMode="showOnDemand" zPosition="2" backgroundColor="#000000" transparent="1" />'
            u'</screen>'
        )
        
        self["title"] = Label(self.d_name)
        subtitle_txt = "Position: " + str(self.rank)
        if self.points: subtitle_txt += "  |  Points: " + str(self.points)
        if self.team_name: subtitle_txt += "  |  Team: " + str(self.team_name)
        self["subtitle"] = Label(subtitle_txt)
        
        self.theme = {
            "bg": 0x000000, "sel_bg": 0x000000,
            "text": 0xFFFFFF, "dim": 0xBBBBBB, "accent": 0x00FF85,
            "font": "Regular", "size_base": 24, "size_small": 18
        }
        
        self.full_rows = []
        self["list"] = MenuList([], enableWrapAround=True)
        self["list"].l.setItemHeight(60)
        
        self["actions"] = ActionMap(["OkCancelActions"], {
            "ok": self.close, "cancel": self.close
        }, -1)
        
        self.onLayoutFinish.append(self.start_fetch)

    def start_fetch(self):
        self.full_rows.append(TextListEntry("API DATA LOADING...", self.theme, is_header=True))
        self.update_list()
        
        is_core = "sports.core.api" in self.league_url
        if is_core and self.d_id:
            a_url = self.league_url + "/athletes/" + str(self.d_id)
            getPage(a_url.encode('utf-8')).addCallback(self.on_athlete).addErrback(self.on_error)
        elif self.d_id:
            league = "f1"
            if "nascar" in self.league_url: league = "nascar"
            elif "irl" in self.league_url: league = "irl"
            a_url = "https://site.api.espn.com/apis/common/v3/sports/racing/" + league + "/athletes/" + str(self.d_id)
            getPage(a_url.encode('utf-8')).addCallback(self.on_athlete_site).addErrback(self.on_error)
        else:
            self.full_rows = [TextListEntry("Basic Competitor Info", self.theme, is_header=True)]
            if self.team_name: self.full_rows.append(TextListEntry("Team: " + str(self.team_name), self.theme))
            if self.d_country: self.full_rows.append(TextListEntry("Country: " + str(self.d_country), self.theme))
            self.full_rows.append(TextListEntry("Detailed API profile unavailable.", self.theme))
            self.update_list()

    def on_athlete(self, body):
        self.full_rows = []
        try:
            data = json.loads(body.decode('utf-8', errors='ignore'))
            self.full_rows.append(TextListEntry(u"\U0001F464 DRIVER BIO", self.theme, is_header=True))
            
            f_name = data.get('firstName', '')
            l_name = data.get('lastName', '')
            if f_name and l_name: self.full_rows.append(TextListEntry("Full Name: " + f_name + " " + l_name, self.theme))
            
            dob = data.get('dateOfBirth', '')
            if dob: self.full_rows.append(TextListEntry("Date of Birth: " + dob[:10], self.theme))
            
            b_place = data.get('birthPlace', {})
            b_str = []
            if b_place.get('city'): b_str.append(b_place['city'])
            if b_place.get('state'): b_str.append(b_place['state'])
            if b_place.get('country'): b_str.append(b_place['country'])
            if b_str: self.full_rows.append(TextListEntry("Birth Place: " + ", ".join(b_str), self.theme))
            
            w = data.get('weight', 0)
            h = data.get('height', 0)
            if w: self.full_rows.append(TextListEntry("Weight: " + str(w) + " lbs", self.theme))
            if h: self.full_rows.append(TextListEntry("Height: " + str(h) + " inches", self.theme))
            
            cz = data.get('citizenship', '')
            if cz: self.full_rows.append(TextListEntry("Citizenship: " + cz, self.theme))
            
            stats_ref = data.get('statistics', {}).get('$ref', '')
            if stats_ref:
                self.stats_url = stats_ref
                getPage(stats_ref.encode('utf-8')).addCallback(self.on_stats).addErrback(self.on_error)
            else:
                self.update_list()
        except:
            self.full_rows.append(TextListEntry("Could not parse driver profile.", self.theme))
            self.update_list()

    def on_athlete_site(self, body):
        self.full_rows = []
        try:
            data = json.loads(body.decode('utf-8', errors='ignore')).get('athlete', {})
            self.full_rows.append(TextListEntry(u"\U0001F464 DRIVER BIO", self.theme, is_header=True))
            
            f_name = data.get('firstName', '')
            l_name = data.get('lastName', '')
            if f_name and l_name: self.full_rows.append(TextListEntry("Full Name: " + f_name + " " + l_name, self.theme))
            
            dob = data.get('displayDOB', '')
            if dob: self.full_rows.append(TextListEntry("Date of Birth: " + dob, self.theme))
            
            b_place = data.get('displayBirthPlace', '')
            if b_place: self.full_rows.append(TextListEntry("Birth Place: " + b_place, self.theme))
            
            w = data.get('displayWeight', '')
            h = data.get('displayHeight', '')
            if w: self.full_rows.append(TextListEntry("Weight: " + w, self.theme))
            if h: self.full_rows.append(TextListEntry("Height: " + h, self.theme))
            
            stats = data.get('stats', {}).get('summary', {})
            if stats:
                self.full_rows.append(TextListEntry("", self.theme))
                self.full_rows.append(TextListEntry(u"\U0001F3C6 STATISTICS (CURRENT SEASON)", self.theme, is_header=True))
                # Just add a dummy line, the stats object structure is complex in site API, let's keep it simple
                self.full_rows.append(TextListEntry("Stats available. View online for full details.", self.theme))
            
            self.update_list()
        except:
            self.full_rows.append(TextListEntry("Could not parse driver profile from site.", self.theme))
            self.update_list()

    def on_stats(self, body):
        try:
            data = json.loads(body.decode('utf-8', errors='ignore'))
            self.full_rows.append(TextListEntry("", self.theme))
            self.full_rows.append(TextListEntry(u"\U0001F3C6 STATISTICS (CURRENT SEASON)", self.theme, is_header=True))
            
            splits = data.get('splits', {}).get('categories', [])
            for cat in splits:
                c_name = cat.get('displayName', cat.get('name', ''))
                stats = cat.get('stats', [])
                if stats:
                    self.full_rows.append(TextListEntry(c_name + ":", self.theme, is_header=True))
                    for st in stats:
                        lbl = st.get('displayName', st.get('name', ''))
                        val = st.get('displayValue', '')
                        if lbl and val:
                            self.full_rows.append(TextListEntry(lbl + ": " + val, self.theme))
            self.update_list()
        except:
            self.update_list()

    def on_error(self, error):
        self.update_list()

    def update_list(self):
        self["list"].l.setList(self.full_rows)



class GameInfoScreen(Screen):
    def __init__(self, session, event_id, league_url="", event_data=None):
        Screen.__init__(self, session)
        self.session = session
        self.event_id = event_id
        self.theme = global_sports_monitor.theme_mode
        self.league_url = league_url  # Store for standings screen
        self.fallback_event_data = event_data # Store for fallback if API fails
        self.league_name = ""  # Will be set when parsing data
        self.sport_type = get_sport_type(league_url)  # Detect sport type
        
        self.full_rows = []      
        self.current_page = 0    
        self.items_per_page = 10 
        self.odds_data = []      # Populated by parse_odds from core API
        self.h_team_name = "Home" # Will be set when parsing data
        self.a_team_name = "Away" # Will be set when parsing data
        
        base_url = league_url.split('?')[0]
        
        # Tennis Special Handling: needs tournament_id as event and match_id as competition
        # Tennis Special Handling: needs tournament_id as event and match_id as competition
        if self.sport_type == SPORT_TYPE_TENNIS:
            tournament_id = ""
            competition_id = ""
            api_link = ""
            
            try:
                # Retrieve info from stored event data
                ev_data = global_sports_monitor.event_map.get(str(event_id), {})
                tournament_id = ev_data.get('tournament_id', '')
                competition_id = ev_data.get('competition_id', '')
                
                # Check for direct API link in 'links'
                links = ev_data.get('links', [])
                for link in links:
                     href = link.get('href', '')
                     if "summary" in href and "api.espn.com" in href:
                         api_link = href
                         break
            except: pass
            
            if api_link:
                self.summary_url = api_link
            elif tournament_id and competition_id:
                if "scoreboard" in base_url:
                    self.summary_url = base_url.replace("scoreboard", "summary") + "?event=" + str(tournament_id) + "&competition=" + str(competition_id)
                else:
                    self.summary_url = "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/summary?event=" + str(tournament_id) + "&competition=" + str(competition_id)
            else:
                 # Fallback to just event_id (likely tournament only view)
                 if "scoreboard" in base_url:
                    self.summary_url = base_url.replace("scoreboard", "summary") + "?event=" + str(event_id)
                 else:
                    self.summary_url = "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/summary?event=" + str(event_id)
        else:
            # Standard logic for other sports
            if "scoreboard" in base_url:
                self.summary_url = base_url.replace("scoreboard", "summary") + "?event=" + str(event_id)
            else:
                # Fix: Extract sport/league from URL structure instead of invalid 'all' slug
                sport = 'soccer'
                league = 'eng.1' # Default fallback
                parts = base_url.split('/')
                for i, p in enumerate(parts):
                    if p == 'sports' and i + 2 < len(parts):
                        sport = parts[i+1]
                        league = parts[i+2]
                        break
                self.summary_url = "https://site.api.espn.com/apis/site/v2/sports/{}/{}/summary?event={}".format(sport, league, event_id)

        # Core API odds endpoint (richer data with multiple providers)
        self.odds_url = ""
        self.cdn_url = ""
        try:
            if league_url and event_id:
                url_parts = base_url.rstrip('/').split('/')
                # URL like: .../sports/{sport}/{league}/scoreboard
                # Find sport and league from URL structure
                sport = ''
                league = ''
                for i, part in enumerate(url_parts):
                    if part == 'sports' and i + 2 < len(url_parts):
                        sport = url_parts[i + 1]
                        league = url_parts[i + 2]
                        break
                if sport and league and league != 'scoreboard':
                    self.sport = sport
                    self.league = league
                    # Fix: Extract actual competition ID. In tournaments, it can differ from event_id.
                    competition_id = event_id
                    if self.fallback_event_data:
                        try:
                            comps = self.fallback_event_data.get('competitions', [{}])
                            if comps:
                                competition_id = str(comps[0].get('id', event_id))
                        except: pass
                    
                    self.odds_url = "https://sports.core.api.espn.com/v2/sports/{}/leagues/{}/events/{}/competitions/{}/odds".format(
                        sport, league, event_id, competition_id)
                    self.live_status_url = "https://sports.core.api.espn.com/v2/sports/{}/leagues/{}/events/{}/competitions/{}/status".format(
                        sport, league, event_id, competition_id)
                    
                    # CDN Boxscore Endpoint (Faster for Live Games)
                    # Example: https://cdn.espn.com/core/football/nfl/boxscore?xhr=1&gameId=4000000
                    # This API endpoint is identical to /summary but caches/updates faster than site.api.espn.com
                    self.cdn_url = "https://cdn.espn.com/core/{}/{}/boxscore?xhr=1&gameId={}".format(
                        sport, league, event_id)
        except: pass

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
        elif self.sport_type == SPORT_TYPE_TENNIS:
            # Tennis uses a symmetric layout with detailed scores below stadium
            common_widgets = """
                <widget name="match_title" position="0,5" size="1600,28" font="Regular;26" foregroundColor="{accent}" transparent="1" halign="center" valign="center" text="" zPosition="6" />
                
                <!-- ROW 1: TEAMS (Y=30) -->
                <!-- Home: Left Edge -->
                <widget name="h_logo" position="50,25" size="110,110" alphatest="blend" zPosition="5" scale="1" />
                <widget name="h_name" position="180,45" size="450,70" font="Regular;34" foregroundColor="#ffffff" transparent="1" halign="left" valign="center" zPosition="5" />
                
                <!-- Center: Sets Score -->
                <widget name="h_score" position="650,35" size="120,90" font="Regular;72" foregroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="5" />
                <widget name="score_sep" position="785,50" size="30,60" font="Regular;38" foregroundColor="#888888" transparent="1" halign="center" valign="center" text="-" zPosition="4" />
                <widget name="a_score" position="830,35" size="120,90" font="Regular;72" foregroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="5" />
                
                <!-- Away: Right Edge -->
                <widget name="a_name" position="970,45" size="450,70" font="Regular;34" foregroundColor="#ffffff" transparent="1" halign="right" valign="center" zPosition="5" />
                <widget name="a_logo" position="1440,25" size="110,110" alphatest="blend" zPosition="5" scale="1" />
                
                <!-- ROW 2: STATUS (Y=150) -->
                <widget name="start_time_label" position="500,150" size="600,30" font="Regular;24" foregroundColor="{accent}" transparent="1" halign="center" valign="center" zPosition="5" />
                
                <!-- ROW 3: STADIUM (Y=185) -->
                <widget name="stadium_name" position="0,185" size="1600,28" font="Regular;24" foregroundColor="#aaaaaa" transparent="1" halign="center" valign="center" zPosition="5" />
                
                <!-- ROW 4: DETAILED SCORES (Y=220) - BELOW STADIUM, LARGE FONT -->
                <widget name="countdown_label" position="0,220" size="1600,50" font="Regular;42" foregroundColor="#ffd700" transparent="1" halign="center" valign="center" zPosition="6" />
                
                <!-- LIST (Moved Down to Y=280) -->
                <widget name="info_list" position="0,280" size="1600,580" scrollbarMode="showNever" transparent="1" zPosition="5" />
                
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
            "yellow": self.open_leaderboard,
            "up": self["info_list"].up, "down": self["info_list"].down, "left": self.page_up, "right": self.page_down
        }, -2)
        
        # Add Voting State Variables
        self.device_id = get_device_id()
        self.community_votes = {"home": 0, "away": 0, "draw": 0}
        self.has_voted = self._check_local_vote_status()
        self.fetch_community_votes()

        self.onLayoutFinish.append(self.start_loading)

    def _check_local_vote_status(self):
        """Check if this device already voted for this match locally via centralized ledger."""
        eid = str(self.event_id)
        if global_sports_monitor and global_sports_monitor.ledger:
            # FIX Bug 2: Use {} (not []) as the fallback so that 'in' always performs
            # a key-based dict lookup, matching the dict contract of resolved_bets.
            if eid in global_sports_monitor.ledger.get("pending_bets", {}) or eid in global_sports_monitor.ledger.get("resolved_bets", {}):
                return True
        return False

    def _mark_voted_locally(self):
        """No-op, replaced by centralized ledger in add_pending_bet."""
        pass

    def fetch_community_votes(self):
        url = "{}/matches/{}.json".format(FIREBASE_URL, self.event_id)
        print("[SimplySports] Fetching community votes from:", url)
        getPage(url.encode('utf-8'), timeout=10).addCallback(self.on_votes_received).addErrback(self.on_votes_error)

    def on_votes_received(self, html):
        try:
            # print("[SimplySports] Firebase votes received:", html)
            data = json.loads(html)
            if data is None:
                data = {"home": 0, "away": 0, "draw": 0}
                
            if isinstance(data, dict):
                self.community_votes['home'] = int(data.get('home', 0))
                self.community_votes['away'] = int(data.get('away', 0))
                self.community_votes['draw'] = int(data.get('draw', 0))
                
                # --- REBUILD VOTE ROWS IN MEMORY FOR ASYNC REFRESH ---
                h_votes = self.community_votes.get('home', 0)
                a_votes = self.community_votes.get('away', 0)
                d_votes = self.community_votes.get('draw', 0)
                total_votes = h_votes + a_votes + d_votes
                h_name_vote = getattr(self, 'h_team_name', "Home")
                a_name_vote = getattr(self, 'a_team_name', "Away")
                has_voted = getattr(self, 'has_voted', False)
                
                # ESPN API states: 'pre' (Scheduled), 'in' (Live), 'post' (Finished)
                is_pre_match = (getattr(self, 'game_status', 'pre') == 'pre')
                
                for i, row in enumerate(self.full_rows):
                    if isinstance(row, (list, tuple)) and len(row) > 0 and isinstance(row[0], tuple) and len(row[0]) > 0 and row[0][0] == "VOTE":
                        t_type = row[0][1]
                        if t_type == 'home': t_name = h_name_vote
                        elif t_type == 'away': t_name = a_name_vote
                        else: t_name = "Draw"
                        # ALWAYS pass is_pre_match to ensure correct text rendering even when voting is closed
                        self.full_rows[i] = VoteListEntry(t_type, t_name, self.community_votes.get(t_type, 0), total_votes, getattr(self, 'theme', ''), has_voted, is_pre_match)

                # Re-render the UI with new data
                if hasattr(self, 'update_display'):
                    self.update_display()
        except Exception as e:
            print("[SimplySports] Error parsing Firebase data:", e)

    def on_votes_error(self, error):
        print("[SimplySports] Firebase fetch error:", error)

    def handle_ok(self):
        idx = self["info_list"].getSelectedIndex()
        if idx is None: return

        # Calculate actual index in full_rows based on pagination
        real_idx = (self.current_page * self.items_per_page) + idx
        if real_idx < len(self.full_rows):
            item = self.full_rows[real_idx]
            data = item[0]
            
            if isinstance(data, tuple) and len(data) > 0:
                if data[0] == "VOTE" and len(data) > 2:
                    # Phase 2: Lockout logic
                    # If match has started (status != 'pre') OR user already voted
                    if getattr(self, 'has_voted', False) or getattr(self, 'game_status', 'pre') != 'pre':
                        self.session.open(LeaderboardScreen)
                        return
                    
                    # 1. CAPTURE SELECTION & INCREMENT LOCALLY (optimistic UI update)
                    team_type = data[1] # 'home', 'away', or 'draw'
                    # FIX Bug 5: Only increment the local optimistic counter for the UI.
                    # The absolute value is NO LONGER sent to Firebase (see step 4 below)
                    # so this local bump is purely for immediate visual feedback and does
                    # not participate in the server-side count.
                    current_votes = int(self.community_votes.get(team_type, 0))
                    self.community_votes[team_type] = current_votes + 1
                    
                    self.has_voted = True
                    self._mark_voted_locally()
                    
                    # 2. Add to Local Gamification Ledger
                    sport = getattr(self, 'sport', 'soccer')
                    league = getattr(self, 'league', 'eng.1')
                    # Pass team names so the bet history can show "Arsenal vs Chelsea"
                    # even after the match leaves the live event_map cache.
                    h_nm = getattr(self, 'h_team_name', 'Home')
                    a_nm = getattr(self, 'a_team_name', 'Away')
                    if global_sports_monitor:
                        global_sports_monitor.add_pending_bet(self.event_id, team_type, sport, league, h_nm, a_nm)
                    
                    # 3. --- REBUILD VOTE ROWS IN MEMORY FOR INSTANT REFRESH ---
                    h_votes = self.community_votes.get('home', 0)
                    a_votes = self.community_votes.get('away', 0)
                    d_votes = self.community_votes.get('draw', 0)
                    total_votes = h_votes + a_votes + d_votes
                    h_name_vote = getattr(self, 'h_team_name', "Home")
                    a_name_vote = getattr(self, 'a_team_name', "Away")
                    
                    for i, row in enumerate(self.full_rows):
                        if isinstance(row, (list, tuple)) and len(row) > 0 and isinstance(row[0], tuple) and len(row[0]) > 0 and row[0][0] == "VOTE":
                            t_type = row[0][1]
                            if t_type == 'home': t_name = h_name_vote
                            elif t_type == 'away': t_name = a_name_vote
                            else: t_name = "Draw"
                            self.full_rows[i] = VoteListEntry(t_type, t_name, self.community_votes.get(t_type, 0), total_votes, getattr(self, 'theme', ''), True, True)

                    # 4. BUILD THE PAYLOAD (Using Flat-Paths for efficient PATCH merge)
                    voter_name = getattr(global_sports_monitor, 'voter_name', 'Anonymous')
                    device_id = getattr(self, 'device_id', 'unknown')
                    
                    import json
                    # FIX Bug 3: Slash-containing keys ("voters/id/name") are NOT interpreted
                    # as nested paths by the Firebase REST PATCH endpoint — they are stored as
                    # literal key names.  Use a properly nested dict so Firebase creates the
                    # correct voters → device_id → {name, team} sub-tree.
                    #
                    # FIX Bug 5: RACE CONDITION — previously we read the local cached count,
                    # added 1, and wrote the absolute number back.  Two users voting at the
                    # same moment would both read N, both write N+1, and one vote would be
                    # silently lost.  The fix uses Firebase's server-side atomic increment
                    # ("{'.sv': 'increment'}" with value 1) so the server always adds exactly
                    # +1 to whatever the current true count is, regardless of what any client
                    # cached locally.  The voter record and nested dict structure are unchanged.
                    put_data = json.dumps({
                        team_type: {".sv": {"increment": 1}},
                        "voters": {
                            device_id: {
                                "name": voter_name,
                                "team": team_type
                            }
                        }
                    })
                    
                    # 5. SEND TO FIREBASE (Final Bulletproof helper)
                    url = "{}/matches/{}.json".format(FIREBASE_URL, self.event_id)
                    push_to_firebase_threaded(url, put_data)
                    
                    # 6. FORCE UI REFRESH IMMEDIATELY
                    if hasattr(self, 'update_display'):
                        self.update_display()
                    
                    # Restore focus using the correct Enigma2 MenuList/eListbox methods
                    if hasattr(self["info_list"], 'moveToIndex'):
                        self["info_list"].moveToIndex(idx)
                    elif self["info_list"].instance is not None:
                        # Deep fallback for very old Enigma2 images
                        try: self["info_list"].instance.moveSelectionTo(idx)
                        except: pass
                    
                    self.session.open(MessageBox, "Vote Submitted! Good luck!", MessageBox.TYPE_INFO, timeout=2)
                    return

                elif data[0] == "VIDEO" and len(data) > 3:
                    url = data[3]
                    title = data[2]
                    self.play_video(url, title)
                    return
                elif data[0] == "PLAY ALL":
                    self.play_all_videos()
                    return
                elif data[0] == "PLAYER" and len(data) > 2:
                    ath_id = data[1]
                    clean_name = data[2].replace("[Goal]", "").replace("[YC]", "").replace("[RC]", "").replace("[OG]", "").replace("[Pen]", "").strip()
                    if "(A:" in clean_name: clean_name = clean_name.split("(A:")[0].strip()
                    
                    sport = "soccer"
                    league = "eng.1"
                    try:
                        if "v2/sports/" in self.summary_url:
                            parts = self.summary_url.split("v2/sports/")[1].split("/")
                            sport = parts[0]
                            league = parts[1]
                    except: pass
                    
                    self.session.open(AthleteProfileScreen, ath_id, clean_name, sport, league)
                    return
            
            # Default behavior: Standings
            self.open_standings()

    def open_leaderboard(self):
        """Action handler for Yellow button and has_voted OK press."""
        self.session.open(LeaderboardScreen)

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

    def open_leaderboard(self):
        self.session.open(LeaderboardScreen)

    def update_display(self):
        if not self.full_rows:
            self["info_list"].setList([]); self["page_indicator"].setText(""); return

        total_items = len(self.full_rows)
        start_index = self.current_page * self.items_per_page
        end_index = start_index + self.items_per_page
        page_data = self.full_rows[start_index:end_index]
        self["info_list"].setList(page_data)
        total_pages = int(math.ceil(float(total_items) / float(self.items_per_page)))
        if total_pages > 1: self["page_indicator"].setText("Page {}/{}".format(self.current_page + 1, total_pages))
        else: self["page_indicator"].setText("")

    def page_down(self):
        total_items = len(self.full_rows)
        if total_items > 0:
            max_page = int(math.ceil(float(total_items) / float(self.items_per_page))) - 1
            if self.current_page < max_page: self.current_page += 1; self.update_display()

    def page_up(self):
        if self.current_page > 0: self.current_page -= 1; self.update_display()

    def start_loading(self):
        # PHASE 5: Pre-populate header from snapshot (instant, no HTTP wait)
        snap = global_sports_monitor.match_snapshots.get(str(self.event_id))
        if snap:
            try:
                self["h_name"].setText(snap['h_name'])
                self["a_name"].setText(snap['a_name'])
                self["h_score"].setText(snap['h_score_str'])
                self["a_score"].setText(snap['a_score_str'])
                load_logo_to_widget(self, "h_logo", snap['h_logo_url'], snap['h_logo_id'])
                load_logo_to_widget(self, "a_logo", snap['a_logo_url'], snap['a_logo_id'])
                # Set match title for individual sports
                if snap['sport_type'] in [SPORT_TYPE_RACING, SPORT_TYPE_GOLF, SPORT_TYPE_COMBAT]:
                    self["match_title"].setText(snap['league_name'])
                    self["h_name"].setText(snap['h_name'])
                self.league_name = snap['league_name']
            except: pass

        if not self.summary_url and self.fallback_event_data:
             self.use_fallback_data()
             return

        
        is_live = False
        if snap:
            is_live = snap.get('status', '') in ['in', 'IN_PROGRESS', 'STATUS_IN_PROGRESS']
            if not is_live: is_live = snap.get('state', '') == 'in'
            
        if self.cdn_url and is_live:
            # OPTIMIZATION: Use high-speed CDN endpoint for live matches (avoids 60s ESPN latency)
            getPage(self.cdn_url.encode('utf-8')).addCallback(self.parse_details).addErrback(self.error_cdn)
        elif self.summary_url:
            getPage(self.summary_url.encode('utf-8')).addCallback(self.parse_details).addErrback(self.error_details)
        else:
            self.error_details(None)
            
        if self.summary_url or self.cdn_url:
            # Fire odds fetch in parallel (fire-and-forget, non-blocking)
            if self.odds_url:
                getPage(self.odds_url.encode('utf-8')).addCallback(self.parse_odds).addErrback(lambda e: None)
            # Fire live status fetch for instant score/clock update while summary loads
            if hasattr(self, 'live_status_url') and self.live_status_url and is_live:
                getPage(self.live_status_url.encode('utf-8')).addCallback(self.parse_live_status).addErrback(lambda e: None)

    def error_cdn(self, error):
        """Fallback to standard summary API if the CDN Live Boxscore request fails"""
        print("[SimplySport] CDN Boxscore fetch failed. Falling back to primary summary endpoint.")
        if self.summary_url:
            getPage(self.summary_url.encode('utf-8')).addCallback(self.parse_details).addErrback(self.error_details)
        else:
            self.error_details(error)

    def error_details(self, error):
        if self.fallback_event_data:
            self.use_fallback_data()
        else:
            self["loading"].setText("Error loading details.")

    def parse_odds(self, body):
        """Parse core API odds response (multi-provider: Bet365, ESPN BET, etc)"""
        try:
            data = json.loads(body)
            items = data.get('items', [])
            parsed = []
            for item in items:
                provider = item.get('provider', {})
                pname = provider.get('name', 'Unknown')
                # Skip live odds provider (redundant with ESPN BET)
                if 'Live' in pname:
                    continue
                
                entry = {'provider': pname}
                
                # Home/Away/Draw moneyLine
                h_odds = item.get('homeTeamOdds', {})
                a_odds = item.get('awayTeamOdds', {})
                d_odds = item.get('drawOdds', {})
                
                # Try fractional from bettingOdds first (Bet365), then from current/close
                betting = item.get('bettingOdds', {}).get('teamOdds', {})
                if betting:
                    h_ml = betting.get('preMatchFullTimeResultHome', {}).get('value', '')
                    a_ml = betting.get('preMatchFullTimeResultAway', {}).get('value', '')
                    d_ml = betting.get('preMatchFullTimeResultDraw', {}).get('value', '')
                    entry['home_ml'] = str(h_ml) if h_ml else ''
                    entry['away_ml'] = str(a_ml) if a_ml else ''
                    entry['draw_ml'] = str(d_ml) if d_ml else ''
                else:
                    # Use current moneyLine (American format)
                    cur_h = h_odds.get('current', {}).get('moneyLine', {})
                    cur_a = a_odds.get('current', {}).get('moneyLine', {})
                    h_disp = cur_h.get('alternateDisplayValue', '') if isinstance(cur_h, dict) else ''
                    a_disp = cur_a.get('alternateDisplayValue', '') if isinstance(cur_a, dict) else ''
                    if not h_disp and h_odds.get('moneyLine') is not None:
                        ml = h_odds['moneyLine']
                        h_disp = ('+' + str(ml)) if ml > 0 else str(ml) if ml != 0 else 'EVEN'
                    if not a_disp and a_odds.get('moneyLine') is not None:
                        ml = a_odds['moneyLine']
                        a_disp = ('+' + str(ml)) if ml > 0 else str(ml) if ml != 0 else 'EVEN'
                    d_ml_val = d_odds.get('moneyLine')
                    d_disp = ''
                    if d_ml_val is not None and d_ml_val != 0:
                        d_disp = ('+' + str(int(d_ml_val))) if d_ml_val > 0 else str(int(d_ml_val))
                    entry['home_ml'] = h_disp
                    entry['away_ml'] = a_disp
                    entry['draw_ml'] = d_disp
                
                # Spread
                spread = item.get('spread')
                if spread is not None:
                    entry['spread'] = str(spread)
                    h_sp = h_odds.get('spreadOdds')
                    a_sp = a_odds.get('spreadOdds')
                    entry['spread_detail'] = item.get('details', '')
                    if h_sp is not None:
                        entry['home_spread_odds'] = ('+' + str(int(h_sp))) if h_sp > 0 else str(int(h_sp))
                    if a_sp is not None:
                        entry['away_spread_odds'] = ('+' + str(int(a_sp))) if a_sp > 0 else str(int(a_sp))
                
                # Over/Under
                ou = item.get('overUnder')
                if ou is not None:
                    entry['over_under'] = str(ou)
                    oo = item.get('overOdds')
                    uo = item.get('underOdds')
                    if oo is not None:
                        entry['over_odds'] = ('+' + str(int(oo))) if oo > 0 else str(int(oo))
                    if uo is not None:
                        entry['under_odds'] = ('+' + str(int(uo))) if uo > 0 else str(int(uo))
                
                parsed.append(entry)
            
            self.odds_data = parsed
        except:
            pass

    def parse_live_status(self, body):
        """Fast-path: update header clock/period from core API status (arrives before /summary)"""
        try:
            data = json.loads(body)
            display_clock = data.get('displayClock', '')
            status_type = data.get('type', {})
            detail = status_type.get('detail', '') or status_type.get('shortDetail', '')
            
            if display_clock or detail:
                clock_txt = detail if detail else display_clock
                title = self.league_name if self.league_name else "LIVE"
                self["match_title"].setText("{} - {}".format(title, clock_txt))
        except:
            pass

    def use_fallback_data(self):
        if not self.fallback_event_data:
            self["loading"].setText("No details available.")
            return

        try:
            self["loading"].hide()
            data = self.fallback_event_data
            
            # --- PARSE BASIC INFO ---
            league = data.get('league_name', self.league_name)
            self["match_title"].setText(str(league))
            
            # Venue - check top-level AND inside competitions
            venue = data.get('venue', {})
            if not venue:
                venue = data.get('competitions', [{}])[0].get('venue', {})
            v_text = venue.get('fullName', '')
            city = venue.get('address', {}).get('city', '')
            if city and city not in v_text: v_text += ", " + city
            self["stadium_name"].setText(str(v_text))
            
            # Status
            status = data.get('status', {})
            status_type = status.get('type', {})
            state = status_type.get('state', '')
            detail = status_type.get('detail', '')
            is_postponed = status_type.get('name') == 'STATUS_POSTPONED' or 'postponed' in status_type.get('description', '').lower()
            is_suspended = status_type.get('name') in ['STATUS_SUSPENDED', 'STATUS_DELAYED'] or 'suspended' in status_type.get('description', '').lower() or 'resume' in status_type.get('description', '').lower() or 'delay' in status_type.get('description', '').lower()
            
            # Competitors - check top-level AND inside competitions (tennis uses competitions[0].competitors)
            comps = data.get('competitors', [])
            if not comps:
                comps = data.get('competitions', [{}])[0].get('competitors', [])
            h_team = {}; a_team = {}
            
            # Racing: build driver standings from scoreboard data (summary API often unavailable)
            is_individual = self.sport_type in [SPORT_TYPE_RACING, SPORT_TYPE_GOLF, SPORT_TYPE_COMBAT]
            if is_individual and self.sport_type == SPORT_TYPE_RACING:
                event_name = data.get('shortName', '') or data.get('name', '') or league
                self["h_name"].setText(str(event_name))
                self["a_name"].setText("")
                self["h_score"].setText(""); self["a_score"].setText("")
                try: self["score_sep"].hide()
                except: pass
                
                # Venue
                venue = data.get('competitions', [{}])[0].get('venue', {})
                v_text = venue.get('fullName', '')
                v_city = venue.get('address', {}).get('city', '')
                if v_city and v_city not in v_text: v_text += ", " + v_city
                if v_text: self["stadium_name"].setText(str(v_text))
                
                # Status
                race_status = data.get('status', {}).get('type', {})
                state = race_status.get('state', 'pre')
                status_txt = "Scheduled"
                if is_postponed: status_txt = "Postponed"
                elif is_suspended: status_txt = "Suspended / To be resumed"
                elif state == 'in': status_txt = "LIVE - In Progress"
                elif state == 'post': status_txt = "Finished"
                self.full_rows.append(TextListEntry("STATUS: " + status_txt, self.theme, is_header=True))
                
                # Broadcast
                try:
                    broadcasts = data.get('competitions', [{}])[0].get('broadcasts', [])
                    if broadcasts:
                        channels = []
                        for b in broadcasts:
                            channels.extend(b.get('names', []))
                        if channels:
                            self.full_rows.append(TextListEntry("BROADCAST: " + ", ".join(channels), self.theme))
                except: pass
                self.full_rows.append(TextListEntry("", self.theme))
                
                # Driver Standings from scoreboard competitors
                competitors = data.get('competitions', [{}])[0].get('competitors', [])
                if competitors:
                    if state == 'post':
                        self.full_rows.append(TextListEntry("RACE RESULTS", self.theme, is_header=True))
                    elif state == 'in':
                        self.full_rows.append(TextListEntry("LIVE STANDINGS", self.theme, is_header=True))
                    else:
                        self.full_rows.append(TextListEntry("DRIVER GRID", self.theme, is_header=True))
                    
                    for i, driver in enumerate(competitors[:30]):
                        rank = driver.get('order', i + 1)
                        athlete = driver.get('athlete', {})
                        driver_name = athlete.get('displayName', '') or athlete.get('shortName', 'Driver')
                        flag_info = athlete.get('flag', {})
                        country = flag_info.get('alt', '')
                        is_winner = driver.get('winner', False)
                        
                        line = u"P{} - {}".format(rank, driver_name)
                        if country:
                            line += u" ({})".format(country)
                        if is_winner:
                            line += u" [WINNER]"
                        
                        self.full_rows.append(TextListEntry(line, self.theme))
                else:
                    self.full_rows.append(TextListEntry("No driver data available.", self.theme))
                
                self.update_display()
                return
            elif is_individual:
                event_name = data.get('shortName', '') or data.get('name', '') or league
                self["h_name"].setText(str(event_name))
                self["a_name"].setText("")
                self["h_score"].setText(""); self["a_score"].setText("")
                return
            
            # --- ADD VOTING SECTION (FALLBACK PATH) ---
            self.event_data = data
            self.game_status = state # 'pre', 'in', 'post'
            is_pre_match = (state == 'pre')
            
            h_name_vote = getattr(self, 'h_team_name', "Home")
            a_name_vote = getattr(self, 'a_team_name', "Away")
            h_votes = getattr(self, 'community_votes', {}).get('home', 0)
            a_votes = getattr(self, 'community_votes', {}).get('away', 0)
            d_votes = getattr(self, 'community_votes', {}).get('draw', 0)
            total_votes = h_votes + a_votes + d_votes
            has_voted = getattr(self, 'has_voted', False)

            header_text = "COMMUNITY PREDICTION" if is_pre_match else "COMMUNITY PREDICTION (Closed)"
            self.full_rows.append(TextListEntry(header_text, getattr(self, 'theme', ''), is_header=True))
            self.full_rows.append(VoteListEntry("home", h_name_vote, h_votes, total_votes, getattr(self, 'theme', ''), has_voted, is_pre_match))
            self.full_rows.append(VoteListEntry("draw", "Draw", d_votes, total_votes, getattr(self, 'theme', ''), has_voted, is_pre_match))
            self.full_rows.append(VoteListEntry("away", a_name_vote, a_votes, total_votes, getattr(self, 'theme', ''), has_voted, is_pre_match))
            self.full_rows.append(StatsListEntry("", "", "", getattr(self, 'theme', ''))) # Spacer
            self.fetch_community_votes()

            # Fix: Tennis flags/names reversed in GameInfo. Force index 0=Home, 1=Away to match Main Screen
            if self.sport_type == SPORT_TYPE_TENNIS and len(comps) >= 2:
                h_team = comps[0]
                a_team = comps[1]
            else:
                for c in comps:
                    if c.get('homeAway') == 'home': h_team = c
                    else: a_team = c
                # If no homeAway tags, use positional (tennis often uses index 0=home, 1=away)
                if not h_team and len(comps) > 0: h_team = comps[0]
                if not a_team and len(comps) > 1: a_team = comps[1]
            
            # Names & Logos - Robust Tennis Logic (Doubles Support)
            if self.sport_type == SPORT_TYPE_TENNIS:
                def extract_tennis_info_local(comp):
                    name = ""; flag_url = ""; pid = ""
                    # 1. Try Athlete
                    ath = comp.get('athlete', {})
                    if ath:
                        name = ath.get('shortName') or ath.get('displayName')
                        pid = ath.get('id', '')
                        flag = ath.get('flag', {})
                        flag_url = flag.get('href') or flag.get('alt')
                        if not flag_url and ath.get('flag', {}).get('iso2'):
                            flag_url = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(ath['flag']['iso2'].lower())

                    # 2. Try Roster (Doubles)
                    if not name:
                        ros = comp.get('roster', {})
                        if ros:
                            name = ros.get('shortDisplayName') or ros.get('displayName')
                            entries = comp.get('roster', {}).get('entries', [])
                            if entries:
                                p1 = entries[0].get('athlete', {})
                                if not pid: pid = p1.get('id', '')
                                if not flag_url:
                                    flag = p1.get('flag', {})
                                    flag_url = flag.get('href') or flag.get('alt')
                                    if not flag_url and p1.get('flag', {}).get('iso2'):
                                        flag_url = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(p1['flag']['iso2'].lower())

                    # 3. Fallback
                    if not name: name = comp.get('name') or ""
                    if not flag_url:
                         country = comp.get('country', {})
                         if country.get('iso2'): 
                             flag_url = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(country['iso2'].lower())
                    return name, flag_url

                h_name, h_logo = extract_tennis_info_local(h_team)
                a_name, a_logo = extract_tennis_info_local(a_team)
                
                # Fallback names
                if not h_name: h_name = "Player 1"
                if not a_name: a_name = "Player 2"
                
                self["h_name"].setText(str(h_name))
                self["a_name"].setText(str(a_name))
                try:
                    h_id = h_team.get('athlete', {}).get('id', '')
                    a_id = a_team.get('athlete', {}).get('id', '')
                    prefix = get_sport_id_prefix(self.league_url)
                    self.download_logo(h_logo, "h_logo", prefix + str(h_id) if h_id else None)
                    self.download_logo(a_logo, "a_logo", prefix + str(a_id) if a_id else None)
                except: pass
                
            else:
                # Standard Logic
                h_name = h_team.get('athlete', {}).get('displayName') or h_team.get('team', {}).get('displayName', 'Home')
                a_name = a_team.get('athlete', {}).get('displayName') or a_team.get('team', {}).get('displayName', 'Away')
                self["h_name"].setText(str(h_name))
                self["a_name"].setText(str(a_name))
                
                try:
                    h_id = h_team.get('team', {}).get('id', '') or h_team.get('athlete', {}).get('id', '')
                    a_id = a_team.get('team', {}).get('id', '') or a_team.get('athlete', {}).get('id', '')
                    h_logo = h_team.get('team', {}).get('logo', '') or h_team.get('athlete', {}).get('flag', {}).get('href', '')
                    a_logo = a_team.get('team', {}).get('logo', '') or a_team.get('athlete', {}).get('flag', {}).get('href', '')
                    
                    prefix = get_sport_id_prefix(self.league_url)
                    if h_logo: self.download_logo(h_logo, "h_logo", prefix + str(h_id) if h_id else None)
                    if a_logo: self.download_logo(a_logo, "a_logo", prefix + str(a_id) if a_id else None)
                except: pass

            # SCORES (Tennis Specifics)
            if self.sport_type == SPORT_TYPE_TENNIS:
                # Big Score = Sets Won
                h_sets = 0
                a_sets = 0
                
                # Detailed Score = "6-4 6-2"
                full_score = ""
                
                h_lines = h_team.get('linescores', [])
                a_lines = a_team.get('linescores', [])
                
                count = max(len(h_lines), len(a_lines))
                for i in range(count):
                    h_val = int(h_lines[i].get('value')) if i < len(h_lines) else 0
                    a_val = int(a_lines[i].get('value')) if i < len(a_lines) else 0
                    
                    full_score += "{}-{}  ".format(h_val, a_val)
                    
                    if i < len(h_lines) and h_lines[i].get('winner'): h_sets += 1
                    elif i < len(a_lines) and a_lines[i].get('winner'): a_sets += 1
                    else:
                        if (i + 1) < count:
                            if h_val > a_val: h_sets += 1
                            elif a_val > h_val: a_sets += 1
                        else:
                            if state == 'post':
                                if h_val > a_val: h_sets += 1
                                elif a_val > h_val: a_sets += 1

                self["h_score"].setText(str(h_sets))
                self["a_score"].setText(str(a_sets))
                self["countdown_label"].setText(full_score.strip())
                
                if state == 'pre':
                    date_str = data.get('date', '')
                    self["start_time_label"].setText(str(date_str).replace("T"," ").replace("Z",""))
                else:
                    self["start_time_label"].setText(str(detail))
                
                if state == 'in':
                    if h_team.get('possession'): self["h_name"].setText("* " + self["h_name"].getText())
                    if a_team.get('possession'): self["a_name"].setText("* " + self["a_name"].getText())
                    
            else:
                # Standard Score
                self["h_score"].setText(str(h_team.get('score', '')))
                self["a_score"].setText(str(a_team.get('score', '')))
                
                if state == 'pre':
                    date_str = data.get('date', '')
                    self["start_time_label"].setText(str(date_str).replace("T"," ").replace("Z",""))
                    self["countdown_label"].setText("") 
                else:
                    self["start_time_label"].setText(str(detail))
                    self["countdown_label"].setText("")

        except Exception as e:
            self["loading"].setText("Error parsing fallback: " + str(e))
            print("[SimplySport] Fallback Error: ", e)

    def download_logo(self, url, widget_name, img_id=None):
        """Delegate to shared logo loader (supports HQ URL upgrade for detail screen)"""
        if url and url.startswith("http"):
            hq_url = url.replace("40&h=40", "500&h=500")
            load_logo_to_widget(self, widget_name, hq_url, img_id)

    def thumbnail_ready(self, *args, **kwargs): pass


    def parse_details(self, body):
        try:
            self["loading"].hide()
            json_str = body.decode('utf-8', errors='ignore')
            data = json.loads(json_str)
            
            # --- HEADER ---
            header_comps = data.get('header', {}).get('competitions', [{}])[0].get('competitors', [])
            boxscore_teams = data.get('boxscore', {}).get('teams', [])
            status_type = data.get('header', {}).get('competitions', [{}])[0].get('status', {}).get('type', {})
            game_status = status_type.get('state', 'pre')
            is_postponed = status_type.get('name') == 'STATUS_POSTPONED' or 'postponed' in status_type.get('description', '').lower()
            is_suspended = status_type.get('name') in ['STATUS_SUSPENDED', 'STATUS_DELAYED'] or 'suspended' in status_type.get('description', '').lower() or 'resume' in status_type.get('description', '').lower() or 'delay' in status_type.get('description', '').lower()

            # --- STADIUM ---
            try:
                venue = data.get('gameInfo', {}).get('venue', {})
                v_name = venue.get('fullName', '')
                addr = venue.get('address', {})
                v_city = addr.get('city', '')
                
                capacity = venue.get('capacity', 0)
                attendance = data.get('gameInfo', {}).get('attendance', 0)
                
                parts = [v_name]
                if v_city: parts.append(v_city)
                if attendance: parts.append("Att: {:,}".format(attendance))
                elif capacity: parts.append("Cap: {:,}".format(capacity))
                
                loc_txt = " - ".join(x for x in parts if x)
                self["stadium_name"].setText(loc_txt)
            except: self["stadium_name"].setText("")

            # --- TEAMS ---
            home_team = {}; away_team = {}
            
            # Racing/Individual sports: skip standard h/a header, parse_racing_event sets these
            is_individual_detail = self.sport_type in [SPORT_TYPE_RACING, SPORT_TYPE_GOLF, SPORT_TYPE_COMBAT]
            if not is_individual_detail:
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
                self.h_team_name = get_name(home_team)
                self.a_team_name = get_name(away_team)
            else:
                def get_name(t): return t.get('team', {}).get('shortDisplayName') or t.get('team', {}).get('displayName') or "Team"
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
                
                # Prefer API-provided logo URL (works for all sports including NHL)
                # Fall back to constructed CDN URL only if API doesn't provide one
                h_id = home_team.get('team', {}).get('id', '')
                h_logo = home_team.get('team', {}).get('logo', '')
                if not h_logo and h_id:
                    h_logo = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png".format(sport_cdn, h_id)
                
                prefix = get_sport_id_prefix(self.league_url)
                if h_logo: self.download_logo(h_logo, "h_logo", prefix + str(h_id) if h_id else None)
                
                a_id = away_team.get('team', {}).get('id', '')
                a_logo = away_team.get('team', {}).get('logo', '')
                if not a_logo and a_id:
                    a_logo = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png".format(sport_cdn, a_id)
                if a_logo: self.download_logo(a_logo, "a_logo", prefix + str(a_id) if a_id else None)
            except: pass

            self.full_rows = [] 
            self.game_status = game_status  # Store for handle_ok lockout
            self.event_data = data # Save for external access

            # --- ADD VOTING SECTION FIRST ---
            h_name_vote = getattr(self, 'h_team_name', "Home")
            a_name_vote = getattr(self, 'a_team_name', "Away")
            
            h_votes = getattr(self, 'community_votes', {}).get('home', 0)
            a_votes = getattr(self, 'community_votes', {}).get('away', 0)
            d_votes = getattr(self, 'community_votes', {}).get('draw', 0)
            total_votes = h_votes + a_votes + d_votes
            has_voted = getattr(self, 'has_voted', False)
            
            # ESPN API states: 'pre' (Scheduled), 'in' (Live), 'post' (Finished)
            is_pre_match = (game_status == 'pre')
            
            # ALWAYS show the same structure, VoteListEntry will handle the [VOTING CLOSED] text internally
            header_text = "COMMUNITY PREDICTION" if is_pre_match else "COMMUNITY PREDICTION (Closed)"
            self.full_rows.append(TextListEntry(header_text, getattr(self, 'theme', ''), is_header=True))
            
            self.full_rows.append(VoteListEntry("home", h_name_vote, h_votes, total_votes, getattr(self, 'theme', ''), has_voted, is_pre_match))
            self.full_rows.append(VoteListEntry("draw", "Draw", d_votes, total_votes, getattr(self, 'theme', ''), has_voted, is_pre_match))
            self.full_rows.append(VoteListEntry("away", a_name_vote, a_votes, total_votes, getattr(self, 'theme', ''), has_voted, is_pre_match))
            
            self.full_rows.append(StatsListEntry("", "", "", getattr(self, 'theme', ''))) # Spacer
            # Fetch live votes from Firebase NOW that vote rows exist
            self.fetch_community_votes()
            # ---------------------------------

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

            # Init Lazy Loader for Team Sports
            self.lazy_data = data
            self.lazy_home_team = home_team
            self.lazy_away_team = away_team
            self.lazy_boxscore_teams = boxscore_teams
            self.lazy_game_status = game_status
            
            self.lazy_gen = self._run_lazy_parser()
            self.do_lazy_load()

        except Exception as e:
            self.full_rows.append(TextListEntry("Error: " + str(e), self.theme))
            self.update_display()
            self["loading"].hide()
            print("[SimplySport] Data Error: ", e)

    def do_lazy_load(self):
        if not hasattr(self, 'lazy_gen'): return
        try:
            next(self.lazy_gen)
            from twisted.internet import reactor
            reactor.callLater(0.01, self.do_lazy_load)
        except StopIteration:
            pass
        except Exception as e:
            print("[SimplySport] Lazy Load Error: ", e)

    def _run_lazy_parser(self):
        data = self.lazy_data
        home_team = self.lazy_home_team
        away_team = self.lazy_away_team
        boxscore_teams = self.lazy_boxscore_teams
        game_status = self.lazy_game_status
        league_name = getattr(self, 'league_name', '')
        h_id = str(home_team.get('id', ''))
        a_id = str(away_team.get('id', ''))
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
                        if draw_val > 0.1:
                            txt = "{}: {:.1f}%  |  Draw: {:.1f}%  |  {}: {:.1f}%".format(self.h_team_name, h_val, draw_val, self.a_team_name, a_val)
                        else:
                            txt = "{}: {:.1f}%  |  {}: {:.1f}%".format(self.h_team_name, h_val, self.a_team_name, a_val)
                            
                        self.full_rows.append(TextListEntry(txt, self.theme))
                        # Post Footer

            except: pass

            # 2. Betting Odds (from Core API or pickcenter fallback)
            self.current_page = 0; self.update_display(); yield
            try:
                if self.odds_data:
                    self.full_rows.append(TextListEntry("BETTING ODDS", self.theme, is_header=True))
                    for od in self.odds_data:
                        prov = od.get('provider', 'Odds')
                        h_ml = od.get('home_ml', '')
                        a_ml = od.get('away_ml', '')
                        d_ml = od.get('draw_ml', '')
                        if h_ml or a_ml:
                            if d_ml:
                                ml_txt = "{}: {} {}  |  Draw {}  |  {} {}".format(prov, self.h_team_name, h_ml, d_ml, self.a_team_name, a_ml)
                            else:
                                ml_txt = "{}: {} {}  |  {} {}".format(prov, self.h_team_name, h_ml, self.a_team_name, a_ml)
                            self.full_rows.append(TextListEntry(ml_txt, self.theme))
                        sp = od.get('spread')
                        ou = od.get('over_under')
                        if sp is not None or ou is not None:
                            parts = []
                            if sp is not None:
                                sp_odds = od.get('home_spread_odds', '')
                                parts.append("Spread: {} ({})".format(sp, sp_odds) if sp_odds else "Spread: {}".format(sp))
                            if ou is not None:
                                oo = od.get('over_odds', '')
                                uo = od.get('under_odds', '')
                                ou_str = "O/U: {}".format(ou)
                                if oo and uo:
                                    ou_str += " ({}/{})".format(oo, uo)
                                parts.append(ou_str)
                            if parts:
                                self.full_rows.append(TextListEntry("    " + "  |  ".join(parts), self.theme))
                    self.full_rows.append(TextListEntry("", self.theme))
                else:
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
            self.current_page = 0; self.update_display(); yield
            try:
                news_items = data.get('news', {}).get('articles', [])
                if not news_items: news_items = data.get('articles', [])
                
                if news_items:
                    self.full_rows.append(TextListEntry("LATEST NEWS", self.theme, is_header=True))
                    count = 0
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
                        self.full_rows.append(TextListEntry("WIN PROBABILITY", self.theme, is_header=True))
                        draw_val = max(0.0, 100.0 - h_val - a_val)
                        if draw_val > 0.1:
                            txt = "{}: {:.1f}%  |  Draw: {:.1f}%  |  {}: {:.1f}%".format(self.h_team_name, h_val, draw_val, self.a_team_name, a_val)
                        else:
                            txt = "{}: {:.1f}%  |  {}: {:.1f}%".format(self.h_team_name, h_val, self.a_team_name, a_val)
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
                    
                    # API Boolean Flags (High Priority)
                    is_og = play.get('ownGoal', False)
                    is_pk = play.get('penaltyKick', False)
                    is_yc = play.get('yellowCard', False)
                    is_rc = play.get('redCard', False)

                    # Detect scoring plays: use flags first, fallback to text matching for other sports
                    is_score = play.get('scoringPlay', False) or is_og or is_pk or any(x in text_desc for x in ["goal", "touchdown", "power play", "short-handed", "even strength", "empty net"])
                    is_card = is_yc or is_rc or "card" in text_desc
                    is_sub = "substitution" in text_desc
                    
                    if is_score or is_card or is_sub:
                        goals_found = True
                        clock = play.get('clock', {}).get('displayValue', '')
                        
                        # Get main athlete (scorer/recipient/sub)
                        scorer = ""
                        assist = ""
                        sub_out = ""
                        ath_id = ""
                        athletes = play.get('athletesInvolved', [])
                        
                        if athletes:
                            scorer = athletes[0].get('displayName') or athletes[0].get('shortName') or ''
                            ath_id = str(athletes[0].get('id', ''))
                            if is_score and len(athletes) > 1:
                                assist = athletes[1].get('displayName') or athletes[1].get('shortName') or ''
                            if is_sub and len(athletes) > 1:
                                sub_out = athletes[1].get('displayName') or athletes[1].get('shortName') or ''
                        elif play.get('participants'):
                            participants = play['participants']
                            if participants:
                                p = participants[0].get('athlete', {})
                                scorer = p.get('displayName') or p.get('shortName') or ''
                                ath_id = str(p.get('id', ''))
                                if is_score and len(participants) > 1:
                                    p2 = participants[1].get('athlete', {})
                                    assist = p2.get('displayName') or p2.get('shortName') or ''
                                if is_sub and len(participants) > 1:
                                    p2 = participants[1].get('athlete', {})
                                    sub_out = p2.get('displayName') or p2.get('shortName') or ''
                        else:
                            txt = play.get('type', {}).get('text', '')
                            if " - " in txt: scorer = txt.split(" - ")[-1].strip()
                            elif "Goal" in txt: scorer = txt.replace("Goal", "").strip()
                        
                        if not scorer: scorer = "Event"
                        
                        # Build display text with type badges and colors
                        evt_color = None  # None = default white
                        
                        if is_rc or (is_card and "red" in text_desc):
                            scorer = "[RC] " + scorer
                            evt_color = 0xFF3333  # Red
                        elif is_yc or (is_card and "yellow" in text_desc):
                            scorer = "[YC] " + scorer
                            evt_color = 0xFFD700  # Gold/Yellow
                        elif is_sub:
                            if sub_out:
                                scorer = u"[Sub] {} \u2190 {}".format(scorer, sub_out)
                            else:
                                scorer = "[Sub] " + scorer
                            evt_color = 0xAAAAAA  # Grey for subs
                        elif is_score:
                            # Detect goal type from flags or text fallback
                            if is_pk or "penalty" in text_desc:
                                scorer = "[Pen] " + scorer
                            elif is_og or "own goal" in text_desc:
                                scorer = "[OG] " + scorer
                            else:
                                scorer = "[Goal] " + scorer
                            if assist:
                                scorer += u" (A: {})".format(assist)
                        
                        t_id = str(play.get('team', {}).get('id', ''))
                        h_id_root = str(home_team.get('id', 'h'))
                        
                        home_evt = ""
                        away_evt = ""
                        h_evt_color = None
                        a_evt_color = None
                        if t_id == h_id_root:
                            home_evt = scorer
                            h_evt_color = evt_color
                        else:
                            away_evt = scorer
                            a_evt_color = evt_color
                        
                        
                        payload = None
                        if ath_id:
                            payload = ("PLAYER", ath_id, scorer)
                        
                        # Append to list with per-event colors
                        self.full_rows.append(EventListEntry(clock, home_evt, away_evt, self.theme, h_color=h_evt_color, a_color=a_evt_color, payload=payload))
                
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

        # --- COMMON: STANDINGS & BROADCASTS ---
        try:
            broadcasts = data.get('header', {}).get('competitions', [{}])[0].get('broadcasts', [])
            if broadcasts:
                b_list = []
                for b in broadcasts:
                    net = b.get('media', {}).get('shortName') or b.get('market', {}).get('type')
                    if net and net not in b_list: b_list.append(net)
                if b_list:
                    self.full_rows.append(TextListEntry("BROADCASTS", self.theme, is_header=True))
                    self.full_rows.append(TextListEntry("📺 " + ", ".join(b_list), self.theme))
                    self.full_rows.append(TextListEntry("", self.theme))
        except: pass

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

        self.current_page = 0
        self.update_display()
        
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
            
            # --- CIRCUIT / VENUE INFO ---
            try:
                venue = data.get('gameInfo', {}).get('venue', {})
                track_name = venue.get('fullName', '') or venue.get('name', '')
                addr = venue.get('address', {})
                city = addr.get('city', '')
                country = addr.get('country', '')
                capacity = venue.get('capacity', 0)
                
                parts = [track_name]
                if city: parts.append(city)
                if country: parts.append(country)
                loc_txt = " - ".join(x for x in parts if x)
                if loc_txt:
                    self["stadium_name"].setText(loc_txt)
            except: pass
            
            # Download series logo if available
            try:
                league_info = header.get('league', {})
                logo_url = league_info.get('logos', [{}])[0].get('href', '')
                if logo_url:
                    l_id = league_info.get('id', '')
                    self.download_logo(logo_url, "h_logo", self.sport_type + "_league_" + str(l_id) if l_id else None)
            except: pass
            
            # --- STATUS ---
            status_txt = "Scheduled"
            if is_postponed: status_txt = "Postponed"
            elif is_suspended: status_txt = "Suspended / To be resumed"
            elif game_status == 'in': status_txt = "LIVE - In Progress"
            elif game_status == 'post': status_txt = "Finished"
            self.full_rows.append(TextListEntry("STATUS: " + status_txt, self.theme, is_header=True))
            
            # Circuit capacity
            try:
                if capacity:
                    self.full_rows.append(TextListEntry("Circuit Capacity: {:,}".format(capacity), self.theme))
            except: pass
            self.full_rows.append(TextListEntry("", self.theme))
            
            # --- DRIVER STANDINGS / RESULTS ---
            try:
                competitors = header.get('competitions', [{}])[0].get('competitors', [])
                if competitors:
                    if game_status == 'post':
                        self.full_rows.append(TextListEntry("RACE RESULTS", self.theme, is_header=True))
                    elif game_status == 'in':
                        self.full_rows.append(TextListEntry("LIVE STANDINGS", self.theme, is_header=True))
                    else:
                        self.full_rows.append(TextListEntry("DRIVER GRID", self.theme, is_header=True))
                    
                    for i, driver in enumerate(competitors[:25]):
                        rank = driver.get('rank', i + 1)
                        
                        # Driver name
                        athlete = driver.get('athlete', {})
                        driver_name = athlete.get('displayName', '') or athlete.get('shortName', '')
                        
                        # Team / Constructor name
                        team_info = driver.get('team', {})
                        team_name = team_info.get('displayName', '') or team_info.get('abbreviation', '')
                        
                        # Vehicle number
                        vehicle_num = driver.get('vehicleNumber', '') or athlete.get('jersey', '')
                        
                        # Points
                        points = driver.get('points', driver.get('score', ''))
                        
                        # Status (DNF, DNS, Retired, etc.)
                        d_status = driver.get('status', '')
                        
                        if not driver_name:
                            driver_name = team_name or 'Driver'
                        
                        # Build display line: #1 [Car#44] M. Verstappen (Red Bull) - 26 pts
                        line = u"#{} ".format(rank)
                        if vehicle_num:
                            line += u"[Car#{}] ".format(vehicle_num)
                        line += driver_name
                        if team_name and team_name != driver_name:
                            line += u" ({})".format(team_name)
                        if points:
                            line += u" - {} pts".format(points)
                        if d_status and d_status.lower() not in ['active', 'running', '']:
                            line += u" [{}]".format(d_status.upper())
                        
                        self.full_rows.append(TextListEntry(line, self.theme, align="left"))
                    
                    self.full_rows.append(TextListEntry("", self.theme))
            except: 
                self.full_rows.append(TextListEntry("No driver data available", self.theme))
            
            # --- RACE SCHEDULE / SESSIONS ---
            try:
                schedule = data.get('schedule', [])
                if schedule:
                    self.full_rows.append(TextListEntry("RACE WEEKEND SCHEDULE", self.theme, is_header=True))
                    for sess in schedule[:8]:
                        name = sess.get('name', 'Session')
                        time_str = get_local_time_str(sess.get('date', ''))
                        sess_status = sess.get('status', {}).get('type', {}).get('state', '')
                        tag = ""
                        if sess_status == 'in': tag = " [LIVE]"
                        elif sess_status == 'post': tag = " [Completed]"
                        self.full_rows.append(TextListEntry("{}: {}{}".format(name, time_str, tag), self.theme, align="left"))
                    self.full_rows.append(TextListEntry("", self.theme))
            except: pass

            # --- BROADCASTS ---
            try:
                broadcasts = header.get('competitions', [{}])[0].get('broadcasts', [])
                if broadcasts:
                    b_list = []
                    for b in broadcasts:
                        net = b.get('media', {}).get('shortName') or b.get('market', {}).get('type')
                        if net and net not in b_list: b_list.append(net)
                    if b_list:
                        self.full_rows.append(TextListEntry("BROADCASTS", self.theme, is_header=True))
                        self.full_rows.append(TextListEntry(", ".join(b_list), self.theme))
                        self.full_rows.append(TextListEntry("", self.theme))
            except: pass
            
            # --- NEWS ---
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
                    l_id = league_info.get('id', '')
                    self.download_logo(logo_url, "h_logo", self.sport_type + "_league_" + str(l_id) if l_id else None)
            except: pass
            
            # Status
            status_txt = "Scheduled"
            if is_postponed: status_txt = "Postponed"
            elif is_suspended: status_txt = "Suspended / To be resumed"
            elif game_status == 'in': status_txt = "LIVE - Round in Progress"
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
                    l_id = league_info.get('id', '')
                    self.download_logo(logo_url, "h_logo", SPORT_TYPE_TENNIS + "_league_" + str(l_id) if l_id else None)
            except: pass
            
            if is_match:
                # Head-to-head match display
                # --- ROBUST NAME & FLAG EXTRACTION (Doubles Support) ---
                def extract_tennis_info_detail(comp):
                    name = ""; flag_url = ""
                    # 1. Try Athlete (Singles)
                    ath = comp.get('athlete', {})
                    if ath:
                        name = ath.get('shortName') or ath.get('displayName')
                        flag = ath.get('flag', {})
                        flag_url = flag.get('href') or flag.get('alt')
                        if not flag_url and ath.get('flag', {}).get('iso2'):
                            flag_url = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(ath['flag']['iso2'].lower())
                    # 2. Try Roster (Doubles)
                    if not name:
                        ros = comp.get('roster', {})
                        if ros:
                            name = ros.get('shortDisplayName') or ros.get('displayName')
                            entries = ros.get('entries', [])
                            if entries and not flag_url:
                                p1 = entries[0].get('athlete', {})
                                flag = p1.get('flag', {})
                                flag_url = flag.get('href') or flag.get('alt')
                                if not flag_url and p1.get('flag', {}).get('iso2'):
                                    flag_url = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(p1['flag']['iso2'].lower())
                    # 3. Try team displayName
                    if not name:
                        name = comp.get('team', {}).get('displayName') or comp.get('name', '')
                    # 4. Fallback flag from country
                    if not flag_url:
                        country = comp.get('country', {})
                        if country.get('iso2'):
                            flag_url = "https://a.espncdn.com/i/teamlogos/countries/500/{}.png".format(country['iso2'].lower())
                    return name or "Player", flag_url

                p1 = competitors[0] if len(competitors) > 0 else {}
                p2 = competitors[1] if len(competitors) > 1 else {}
                player1_name, flag1_url = extract_tennis_info_detail(p1)
                player2_name, flag2_url = extract_tennis_info_detail(p2)
                
                self["match_title"].setText(league_name if league_name else "TENNIS MATCH")
                self["h_name"].setText(player1_name)
                self["a_name"].setText(player2_name)
                
                # Download flags
                try:
                    if flag1_url:
                        p1_id = p1.get('athlete', {}).get('id', '') or p1.get('id', '')
                        self.download_logo(flag1_url, "h_logo", SPORT_TYPE_TENNIS + "_" + str(p1_id) if p1_id else None)
                    if flag2_url:
                        p2_id = p2.get('athlete', {}).get('id', '') or p2.get('id', '')
                        self.download_logo(flag2_url, "a_logo", SPORT_TYPE_TENNIS + "_" + str(p2_id) if p2_id else None)
                except: pass
                
                # --- SCORES: Big = Sets Won, Center = Set History ---
                try:
                    h_sets = 0; a_sets = 0
                    full_score = ""
                    linescores1 = p1.get('linescores', [])
                    linescores2 = p2.get('linescores', [])
                    count = max(len(linescores1), len(linescores2))
                    
                    for i in range(count):
                        h_val = int(linescores1[i].get('value', 0)) if i < len(linescores1) else 0
                        a_val = int(linescores2[i].get('value', 0)) if i < len(linescores2) else 0
                        full_score += "{}-{}  ".format(h_val, a_val)
                        
                        # Count sets won
                        if i < len(linescores1) and linescores1[i].get('winner'): h_sets += 1
                        elif i < len(linescores2) and linescores2[i].get('winner'): a_sets += 1
                        else:
                            # Infer from values (skip current set if live)
                            if game_status == 'in' and i == count - 1:
                                pass  # Current set, don't count yet
                            elif h_val > a_val: h_sets += 1
                            elif a_val > h_val: a_sets += 1
                    
                    self["h_score"].setText(str(h_sets))
                    self["a_score"].setText(str(a_sets))
                    self["h_score"].show(); self["a_score"].show(); self["score_sep"].show()
                    self["countdown_label"].setText(full_score.strip())
                    
                    # Venue Logic (Display Stadium/City)
                    try:
                         venue = data.get('gameInfo', {}).get('venue', {})
                         v_name = venue.get('fullName', '')
                         v_city = venue.get('address', {}).get('city', '')
                         loc = v_name
                         if v_city and v_city not in v_name: loc += " - " + v_city
                         if loc: self["stadium_name"].setText(loc)
                    except: pass
                    
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
            
            # Status - display in header widget AND in list
            status_txt = "Scheduled"
            if is_postponed: status_txt = "Postponed"
            elif is_suspended: status_txt = "Suspended / To be resumed"
            elif game_status == 'in': status_txt = "LIVE - In Progress"
            elif game_status == 'post': status_txt = "Completed"
            self["start_time_label"].setText(status_txt)
            self.full_rows.append(TextListEntry(u"\U0001F3BE STATUS: " + status_txt, self.theme, is_header=True))
            self.full_rows.append(TextListEntry("", self.theme))
            
            if is_match and competitors:
                # Match details
                self.full_rows.append(TextListEntry(u"\U0001F3C6 MATCH INFO", self.theme, is_header=True))
                
                for i, comp in enumerate(competitors[:2]):
                    try:
                        detail_name, _ = extract_tennis_info_detail(comp)
                        rank = comp.get('rank', '') or comp.get('athlete', {}).get('rank', '')
                        country = comp.get('athlete', {}).get('flag', {}).get('alt', '')
                        if not country:
                            country = comp.get('country', {}).get('displayName', '')
                        seed = comp.get('seed', '')
                        winner = comp.get('winner', False)
                        
                        player_txt = detail_name
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
                    l_id = league_info.get('id', '')
                    self.download_logo(logo_url, "h_logo", self.sport_type + "_league_" + str(l_id) if l_id else None)
            except: pass
            
            # Status
            status_txt = "Scheduled"
            if is_postponed: status_txt = "Postponed"
            elif is_suspended: status_txt = "Suspended / To be resumed"
            elif game_status == 'in': status_txt = "LIVE - In Progress"
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
                prefix = self.sport_type + "_"
                if h_id: self.download_logo("https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png".format(sport_cdn, h_id), "h_logo", prefix + str(h_id))
                if a_id: self.download_logo("https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png".format(sport_cdn, a_id), "a_logo", prefix + str(a_id))
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
class GoalToast(Screen):
    def __init__(self, session, match_id, score_text, scorer_text, event_type="default", scoring_team=None):
        self.event_type = event_type
        
        # 1. RETRIEVE DATA FROM UNIFIED SNAPSHOT
        snap = global_sports_monitor.match_snapshots.get(str(match_id))
        if snap:
            league_text = snap['league_name']
            home_text   = snap['h_name']
            away_text   = snap['a_name']
            self.l_url  = snap['l_logo_url']
            self.h_url  = snap['h_logo_url']
            self.a_url  = snap['a_logo_url']
            self.l_id   = snap['l_logo_id']
            self.h_id   = snap['h_logo_id']
            self.a_id   = snap['a_logo_id']
        else:
            # Fallback (should not happen in normal flow)
            league_text = "Match Update"
            home_text = "Home"; away_text = "Away"
            self.l_url = self.h_url = self.a_url = ""
            self.l_id = self.h_id = self.a_id = None

        # Ensure all inputs are strings
        def to_str(obj):
            if obj is None: return u""
            try:
                if isinstance(obj, bytes): return obj.decode('utf-8', 'ignore')
                return str(obj)
            except: return u""

        league_text = to_str(league_text)
        home_text   = to_str(home_text)
        away_text   = to_str(away_text)
        score_text  = to_str(score_text)
        scorer_text = to_str(scorer_text)

        # Format Scorer Time "Player 45'" -> "Player (45')"
        if scorer_text and scorer_text.strip().endswith(u"'") and u"(" not in scorer_text:
            try:
                parts = scorer_text.rsplit(u' ', 1)
                if len(parts) == 2:
                    scorer_text = u"{} ({})".format(parts[0], parts[1])
            except: pass

        # ================================================================
        # UCL BROADCAST-STYLE SCOREBOARD (950 x 120)
        # Inspired by Champions League TV overlay
        # ================================================================
        #                   [ Scorer Name ]          <- above band
        # [LOGO]  ═══ HOME NAME ══╣ SCORE ╠══ AWAY NAME ═══  [LOGO]
        #                   [ League Name ]          <- below band
        # ================================================================
        # Band: metallic blue strip with 3-tone depth effect
        # Logos: large (85x85), overlapping band at edges
        # Score: dark center box inside the band
        # ================================================================

        # Event-type accent colors (used for bottom band accent)
        accent_colors = {
            'goal':     '#0000BB55', 
            'red_card': '#00EECC00',
            'start':    '#0000AACC', 
            'end':      '#0000AACC',
            'default':  '#0000BB55'
        }
        border_color = accent_colors.get(event_type, '#0000BB55')

        # Text highlight colors
        h_color = "#00FFFFFF"; a_color = "#00FFFFFF"; score_color = "#00FFFFFF"
        if event_type == 'goal':
            if scoring_team == 'home': h_color = "#0066FF66"
            elif scoring_team == 'away': a_color = "#0066FF66"
        elif event_type in ['start', 'end']:
            score_color = "#0066DDFF"
        elif event_type == 'red_card':
            if scoring_team == 'home': h_color = "#00FF3333"
            elif scoring_team == 'away': a_color = "#00FF3333"
            score_color = "#00FF3333"

        self.duration_ms = 5000

        # Band metallic colors
        band_hi  = "#00506888"   # top bright edge (metallic highlight)
        band_mid = "#002C4060"   # main band body (steel blue)
        band_lo  = "#00162030"   # bottom dark edge (shadow)
        center   = "#00142030"   # score center box (darkest)

        # Enigma2: #FF = fully transparent, #00 = fully opaque
        bg = "#FF000000"         # fully transparent backdrop

        if global_sports_monitor.theme_mode == "ucl":
            scorer_fg = "#00FFFFFF"
            league_fg = "#00FFFFFF"
        else:
            scorer_fg = "#00FFFFFF"
            league_fg = "#00FFFFFF"

        self.skin = (
            u'<screen position="center,50" size="950,120" title="Goal" flags="wfNoBorder" backgroundColor="{bg}">'
            # --- DARK BACKDROP ---
            u'<eLabel position="0,0" size="950,120" backgroundColor="{bg}" zPosition="0" />'

            # --- SCORER TEXT + RED CARD IMAGE (above band, centered) ---
            u'<widget name="scorer" position="200,5" size="550,30" font="Regular;21" '
            u'foregroundColor="{sfg}" backgroundColor="{bg}" transparent="1" valign="center" halign="center" zPosition="3" />'  
            u'<widget name="rc_img" position="375,10" size="18,18" alphatest="blend" scale="1" zPosition="4" />'

            # --- METALLIC BAND (y=40, total band height = 36) ---
            # Top bright edge (metallic highlight)
            u'<eLabel position="0,40" size="950,2" backgroundColor="{bhi}" zPosition="2" />'
            # Main band body (steel blue)
            u'<eLabel position="0,42" size="950,38" backgroundColor="{bmid}" zPosition="2" />'
            # Bottom dark edge (shadow)
            u'<eLabel position="0,80" size="950,2" backgroundColor="{blo}" zPosition="2" />'
            # Bottom accent line (event color)
            u'<eLabel position="0,82" size="950,2" backgroundColor="{bc}" zPosition="3" />'

            # --- SCORE CENTER BOX (dark recessed area in band) ---
            u'<eLabel position="400,42" size="150,38" backgroundColor="{ctr}" zPosition="3" />'
            u'<widget name="score" position="400,42" size="150,38" font="Regular;26" '
            u'foregroundColor="{sc}" backgroundColor="{ctr}" valign="center" halign="center" zPosition="4" />'

            # --- TEAM NAMES (inside the band) ---
            u'<widget name="home" position="100,42" size="290,38" font="Regular;32" '
            u'foregroundColor="{hc}" backgroundColor="{bmid}" valign="center" halign="right" zPosition="4" />'
            u'<widget name="away" position="560,42" size="290,38" font="Regular;32" '
            u'foregroundColor="{ac}" backgroundColor="{bmid}" valign="center" halign="left" zPosition="4" />'

            # --- LARGE LOGOS (overlapping band at edges) ---
            u'<widget name="h_logo" position="5,18" size="85,85" alphatest="blend" scale="1" zPosition="6" />'
            u'<widget name="a_logo" position="860,18" size="85,85" alphatest="blend" scale="1" zPosition="6" />'

            # --- LEAGUE NAME (logo at center of scorebox, name follows) ---
            # Center of toast/scorebox is 475. Logo is 30px wide.
            # Center of logo at 475 -> Start X = 475 - 15 = 460.
            # 10px gap -> Name starts at 460 + 30 + 10 = 500.
            u'<widget name="l_logo" position="460,85" size="30,30" alphatest="blend" scale="1" zPosition="3" />'
            u'<widget name="league" position="500,90" size="300,28" font="Regular;17" '
            u'foregroundColor="{lfg}" backgroundColor="{bg}" transparent="1" valign="center" halign="left" zPosition="3" />'

            u'</screen>'
        ).format(
            bg=bg, bhi=band_hi, bmid=band_mid, blo=band_lo, bc=border_color,
            ctr=center, hc=h_color, ac=a_color, sc=score_color,
            sfg=scorer_fg, lfg=league_fg
        )

        Screen.__init__(self, session)
        # Register with monitor for live basketball updates
        global_sports_monitor.current_toast = self
        self["league"] = Label(league_text)
        self["home"] = Label(home_text)
        self["away"] = Label(away_text)
        self["score"] = Label(score_text)
        self["scorer"] = Label(scorer_text)
        
        self["rc_img"] = Pixmap()
        self["h_logo"] = Pixmap()
        self["a_logo"] = Pixmap()
        self["l_logo"] = Pixmap()
        
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
        self.current_y = -120
        self.target_y = 50
        self.toast_width = 950
        
        # Cache Desktop Centering for performance
        try:
            from enigma import getDesktop
            desktop = getDesktop(0)
            dw = desktop.size().width()
            self.center_x = (dw - self.toast_width) // 2
        except:
            self.center_x = (1280 - 950) // 2 # Safe fallback
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
            "ok": self.close, "cancel": self.close, 
            "red": self.close, "green": self.close, "yellow": self.close, "blue": self.close,
            "up": self.close, "down": self.close, "left": self.close, "right": self.close
        }, -1)
        
        self.onLayoutFinish.append(self.start_animation)
        self.onClose.append(self._stop_timers)

    def _stop_timers(self):
        try:
            if self.anim_timer.isActive(): self.anim_timer.stop()
            if self.timer.isActive(): self.timer.stop()
        except: pass

    def start_animation(self):
        self.force_top()
        self.anim_timer.start(10, False) # Shorter interval for smoothness

    def animate_entry(self):
        # FIX: Preserve horizontal centering while animating Y
        try:
            step = 5 # Smaller step + Shorter interval = Smooth animation
            if self.current_y < self.target_y:
                self.current_y += step
                self.instance.move(ePoint(self.center_x, self.current_y))
            else:
                self.anim_timer.stop()
                if not self.timer.isActive():
                    self.timer.start(self.duration_ms, True)
        except:
            self.anim_timer.stop()
            if not self.timer.isActive():
                self.timer.start(self.duration_ms, True)

    def force_top(self):
        try: self.instance.setZPosition(10)
        except: pass

    def load_logos(self):
        self.load_image(self.h_url, "h_logo", self.h_id)
        self.load_image(self.a_url, "a_logo", self.a_id)
        self.load_image(self.l_url, "l_logo", self.l_id)
        self["rc_img"].hide()
        # Attempt to load and display red card icon
        if "rc_img" in self and hasattr(self, "event_type") and self.event_type == 'red_card':
            try:
                rc_path = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/red.jpg")
                if os.path.exists(rc_path) and LoadPixmap:
                    rc_pixmap = LoadPixmap(cached=True, path=rc_path)
                    if rc_pixmap:
                        self["rc_img"].instance.setPixmap(rc_pixmap)
                        self["rc_img"].instance.setScale(1)
                        self["rc_img"].show()
            except: pass

    def load_image(self, url, widget_name, img_id=None):
        """Delegate to shared logo loader"""
        load_logo_to_widget(self, widget_name, url, img_id)

# ==============================================================================
# ZAP NOTIFICATION SCREEN (Interactive)
# ==============================================================================
class ZapNotificationScreen(Screen):
    def __init__(self, session, match_name, league, h_logo, a_logo, sref, timeout_seconds=30):
        # Calculate Layout similar to GoalToast
        width = 800
        height = 300
        
        # Colors
        c_bg = "#051030"
        c_title = "#00FF85"
        c_text = "#FFFFFF"
        c_dim = "#AAAAAA"
        
        self.sref = sref
        self.timeout_val = timeout_seconds
        
        self.skin = (
            '<screen position="center,center" size="{w},{h}" title="Zap Notification" flags="wfNoBorder" backgroundColor="#00000000">'
            '<eLabel position="0,0" size="{w},{h}" backgroundColor="{bg}" zPosition="0" />'
            '<eLabel position="0,0" size="{w},5" backgroundColor="{title_c}" zPosition="1" />'
            '<widget name="title" position="20,15" size="{w40},40" font="Regular;28" foregroundColor="{title_c}" backgroundColor="{bg}" valign="center" halign="center" transparent="1" zPosition="2" />'
            '<widget name="h_logo" position="50,80" size="100,100" alphatest="blend" zPosition="2" />'
            '<widget name="a_logo" position="{w150},80" size="100,100" alphatest="blend" zPosition="2" />'
            '<widget name="match_name" position="160,80" size="{w320},100" font="Regular;32" foregroundColor="{text_c}" backgroundColor="{bg}" valign="center" halign="center" transparent="1" zPosition="2" />'
            '<widget name="prompt" position="20,200" size="{w40},40" font="Regular;24" foregroundColor="{dim_c}" backgroundColor="{bg}" valign="center" halign="center" transparent="1" zPosition="2" />'
            '<eLabel position="20,260" size="20,20" backgroundColor="#00FF00" zPosition="2" />'
            '<widget name="key_ok" position="50,260" size="150,25" font="Regular;20" foregroundColor="{text_c}" backgroundColor="{bg}" valign="center" halign="left" transparent="1" zPosition="2" />'
            '<eLabel position="{w140},260" size="20,20" backgroundColor="#FF0000" zPosition="2" />'
            '<widget name="key_cancel" position="{w110},260" size="100,25" font="Regular;20" foregroundColor="{text_c}" backgroundColor="{bg}" valign="center" halign="left" transparent="1" zPosition="2" />'
            '<eLabel position="0,{h5}" size="{w},5" backgroundColor="{title_c}" zPosition="1" />'
            '</screen>'
        ).format(
            w=width, h=height, 
            bg=c_bg, title_c=c_title,
            w40=width - 40,
            w150=width - 150,
            w320=width - 320, text_c=c_text,
            dim_c=c_dim,
            w140=width - 140,
            w110=width - 110,
            h5=height - 5
        )
        
        Screen.__init__(self, session)
        
        self["title"] = Label(str(league))
        self["match_name"] = Label(str(match_name))
        self["prompt"] = Label("Match is starting! Zap to channel?")
        self["key_ok"] = Label("Zap Now")
        self["key_cancel"] = Label("Cancel")
        
        self["h_logo"] = Pixmap()
        self["a_logo"] = Pixmap()
        
        # Logo Cache Path
        self.logo_cache_path = "/tmp/simplysports/logos/"
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "ok": self.ok,
            "cancel": self.cancel,
            "green": self.ok,
            "red": self.cancel
        }, -1)
        
        # Timer for auto-action or timeout
        self.timer = eTimer()
        try: self.timer.callback.append(self.timeout_action)
        except AttributeError: self.timer.timeout.get().append(self.timeout_action)
        self.timer.start(self.timeout_val * 1000, True)

        self.onLayoutFinish.append(self.load_logos)
        
        self.h_url = h_logo
        self.a_url = a_logo

    def load_logos(self):
        self.load_image(self.h_url, "h_logo")
        self.load_image(self.a_url, "a_logo")

    def load_image(self, url, widget_name):
        """Delegate to shared logo loader"""
        load_logo_to_widget(self, widget_name, url)

    def ok(self):
        self.close(True)

    def cancel(self):
        self.close(False)

    def timeout_action(self):
        # Default action on timeout: Zap (True)
        self.close(True)

# ==============================================================================
# LEAGUE SELECTOR
# ==============================================================================
class LeagueSelector(Screen):
    # Major leagues that should appear first (exact matches only)
    MAJOR_LEAGUES = [
        "UEFA Champions League", "UEFA Europa League", "UEFA Conference League",
        "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
        "Eredivisie", "Primeira Liga", "MLS", "Liga MX",
        "FA Cup", "Copa del Rey", "Coppa Italia", "DFB Pokal", "Coupe de France",
        "Scottish Premiership", "Championship", "Serie B", "La Liga 2", "Ligue 2",
        "NBA", "NFL", "MLB", "NHL", "NCAA Football", "NCAA Basketball"
    ]
    
    def __init__(self, session, mode="multi"):
        Screen.__init__(self, session)
        self.mode = mode
        if global_sports_monitor.theme_mode == "ucl":
             self.skin = """
            <screen position="center,center" size="950,800" title="Select Leagues" backgroundColor="#00000000" flags="wfNoBorder">
                <eLabel position="0,0" size="950,800" backgroundColor="#0e1e5b" zPosition="-1" />
                <eLabel position="0,0" size="950,4" backgroundColor="#00ffff" zPosition="1" />
                <eLabel position="0,796" size="950,4" backgroundColor="#00ffff" zPosition="1" />
                <eLabel position="0,0" size="4,800" backgroundColor="#00ffff" zPosition="1" />
                <eLabel position="946,0" size="4,800" backgroundColor="#00ffff" zPosition="1" />
                <widget name="header" position="30,20" size="890,50" font="SimplySportFont;38" foregroundColor="#00ffff" backgroundColor="#0e1e5b" transparent="1" halign="center" />
                <eLabel position="30,75" size="890,2" backgroundColor="#182c82" />
                <widget name="list" position="30,90" size="890,620" scrollbarMode="showOnDemand" transparent="1" />
                <eLabel position="30,720" size="890,2" backgroundColor="#182c82" />
                <widget name="key_red" position="30,740" size="200,50" font="SimplySportFont;28" foregroundColor="#FFFFFF" backgroundColor="#F44336" transparent="0" zPosition="1" halign="center" valign="center" />
                <widget name="key_green" position="720,740" size="200,50" font="SimplySportFont;28" foregroundColor="#000000" backgroundColor="#00FF85" transparent="0" zPosition="1" halign="center" valign="center" />
                <widget name="info" position="295,740" size="360,50" font="SimplySportFont;24" foregroundColor="#00ffff" backgroundColor="#0e1e5b" transparent="1" halign="center" valign="center" />
            </screen>
            """
        else:
            self.skin = """
            <screen position="center,center" size="950,800" title="Select Leagues" backgroundColor="#38003C" flags="wfNoBorder">
                <eLabel position="0,0" size="950,800" backgroundColor="#38003C" zPosition="-1" />
                <eLabel position="0,0" size="950,4" backgroundColor="#00FF85" zPosition="1" />
                <eLabel position="0,796" size="950,4" backgroundColor="#00FF85" zPosition="1" />
                <eLabel position="0,0" size="4,800" backgroundColor="#00FF85" zPosition="1" />
                <eLabel position="946,0" size="4,800" backgroundColor="#00FF85" zPosition="1" />
                <widget name="header" position="30,20" size="890,50" font="SimplySportFont;38" foregroundColor="#00FF85" backgroundColor="#38003C" transparent="1" halign="center" />
                <eLabel position="30,75" size="890,2" backgroundColor="#505050" />
                <widget name="list" position="30,90" size="890,620" scrollbarMode="showOnDemand" transparent="1" />
                <eLabel position="30,720" size="890,2" backgroundColor="#505050" />
                <widget name="key_red" position="30,740" size="200,50" font="SimplySportFont;28" foregroundColor="#FFFFFF" backgroundColor="#F44336" transparent="0" zPosition="1" halign="center" valign="center" />
                <widget name="key_green" position="720,740" size="200,50" font="SimplySportFont;28" foregroundColor="#000000" backgroundColor="#00FF85" transparent="0" zPosition="1" halign="center" valign="center" />
                <widget name="info" position="295,740" size="360,50" font="SimplySportFont;24" foregroundColor="#9E9E9E" backgroundColor="#38003C" transparent="1" halign="center" valign="center" />
            </screen>
            """
        
        self["header"] = Label("Select Custom Leagues" if mode == "multi" else "Select League")
        self["list"] = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
        self["list"].l.setFont(0, gFont("SimplySportFont", 28))
        self["list"].l.setItemHeight(50)
        
        self["key_red"] = Label("Cancel")
        self["key_green"] = Label("Save" if mode == "multi" else "")
        self["info"] = Label("Press OK to Toggle" if mode == "multi" else "Press OK to Select")
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
            "cancel": self.cancel,
            "red": self.cancel,
            "green": self.save if mode == "multi" else self.dummy,
            "ok": self.toggle,
            "up": self["list"].up,
            "down": self["list"].down,
        }, -1)
        
        self.selections = []
        self.sorted_indices = []  # Track original indices after sorting
        self.league_logos = {}  # Cache for downloaded league logos
        self.logo_path = "/tmp/simplysports/league_logos/"
        if not os.path.exists(self.logo_path):
            try: os.makedirs(self.logo_path)
            except: pass
        self.onLayoutFinish.append(self.load_list)

    def dummy(self):
        pass

    def cancel(self):
        self.close(None)

    def get_league_priority(self, league_name):
        """Return priority value for sorting (lower = higher priority)"""
        # Use exact matching only to avoid "Premier League" matching "Canadian Premier League"
        for i, major in enumerate(self.MAJOR_LEAGUES):
            if league_name == major:
                return i
        return 1000  # Non-major leagues go last

    # Sport group ordering (lower = higher in the list)
    SPORT_GROUP_ORDER = {
        'soccer': 0, 'basketball': 1, 'football': 2, 'hockey': 3,
        'baseball': 4, 'racing': 5, 'tennis': 6, 'rugby': 7,
        'rugby-league': 8, 'cricket': 9, 'golf': 10,
        'boxing': 11, 'mma': 12, 'lacrosse': 13
    }

    def _get_sport_from_url(self, url):
        """Extract sport name from API URL for grouping."""
        try:
            parts = url.split('/sports/')
            if len(parts) > 1:
                return parts[1].split('/')[0]
        except: pass
        return 'other'

    def _is_women_league(self, name, url):
        """Check if league is a women's league from name or URL."""
        name_lower = name.lower()
        url_lower = url.lower()
        women_markers = ["women", "woman", "wnba", ".w.", ".w/", "wsl", "nwsl", "wchampions"]
        for m in women_markers:
            if m in name_lower or m in url_lower:
                return True
        return False

    def load_list(self):
        current_indices = global_sports_monitor.custom_league_indices
        
        # Create list of (original_idx, name, is_selected, priority, sport, is_women) for sorting
        league_items = []
        for i in range(len(DATA_SOURCES)):
            name = DATA_SOURCES[i][0]
            url = DATA_SOURCES[i][1]
            # In multi mode: filter out racing leagues (they only work in single-league)
            if self.mode == "multi" and get_sport_type(url) == SPORT_TYPE_RACING:
                continue
            is_selected = i in current_indices
            priority = self.get_league_priority(name)
            sport = self._get_sport_from_url(url)
            is_women = self._is_women_league(name, url)
            league_items.append((i, name, is_selected, priority, sport, is_women))
        
        # Sort: sport group order → women last within group → major leagues first → alphabetical
        league_items.sort(key=lambda x: (
            self.SPORT_GROUP_ORDER.get(x[4], 99),  # Sport group order
            1 if x[5] else 0,                       # Women's leagues at end of group
            x[3],                                   # Priority (major leagues first)
            x[1]                                    # Alphabetical name
        ))
        
        # Store sorted order
        self.sorted_indices = [item[0] for item in league_items]
        self.selections = [item[2] for item in league_items]
        # Store sport info for group headers
        self._league_sports = [item[4] for item in league_items]
        self._league_women = [item[5] for item in league_items]
        
        self.download_league_logos()
        self.refresh_list()

    def download_league_logos(self):
        """Download league logos from ESPN API for each league"""
        from twisted.web.client import downloadPage
        for sorted_idx, original_idx in enumerate(self.sorted_indices):
            url = DATA_SOURCES[original_idx][1]
            logo_id = "league_{}".format(original_idx)
            logo_file = self.logo_path + logo_id + ".png"
            
            if os.path.exists(logo_file) and os.path.getsize(logo_file) > 0:
                self.league_logos[sorted_idx] = logo_file
            else:
                # Extract sport info from URL to build logo URL
                try:
                    logo_url = self.get_league_logo_url(url, original_idx)
                    if logo_url:
                        downloadPage(logo_url.encode('utf-8'), logo_file).addCallback(
                            self.logo_downloaded, sorted_idx, logo_file).addErrback(self.logo_error)
                except: pass
    
    def get_league_logo_url(self, api_url, idx):
        """Generate ESPN logo URL from API endpoint"""
        KNOWN_LOGOS = {
            '164205': ('rugby', '164205'),
            '242041': ('rugby', '242041'),
            '267979': ('rugby', '267979'),
            '270557': ('rugby', '270557'),
            '270559': ('rugby', '270559'),
            '271937': ('rugby', '271937'),
            '8604': ('cricket', '8604'),
            '8605': ('cricket', '8605'),
            '8674': ('cricket', '8674'),
            '8676': ('cricket', '8676'),
            'afc.asian.cup': ('soccer', '20219'),
            'afc.champions': ('soccer', '3902'),
            'arg.1': ('soccer', '745'),
            'atp': ('tennis', '851'),
            'aus.1': ('soccer', '3906'),
            'aus.w.1': ('soccer', '18992'),
            'aut.1': ('soccer', '3907'),
            'bel.1': ('soccer', '3901'),
            'bol.1': ('soccer', '620'),
            'bra.1': ('soccer', '630'),
            'bra.2': ('soccer', '4007'),
            'caf.nations': ('soccer', '3908'),
            'campeones.cup': ('soccer', '18771'),
            'chi.1': ('soccer', '640'),
            'chn.1': ('soccer', '8376'),
            'col.1': ('soccer', '650'),
            'college-baseball': ('baseball', '14'),
            'college-football': ('football', '23'),
            'concacaf.champions': ('soccer', '5699'),
            'concacaf.gold': ('soccer', '4004'),
            'concacaf.leagues.cup': ('soccer', '19425'),
            'concacaf.nations.league': ('soccer', '19267'),
            'conmebol.america': ('soccer', '780'),
            'conmebol.libertadores': ('soccer', '783'),
            'conmebol.sudamericana': ('soccer', '5454'),
            'cyp.1': ('soccer', '5346'),
            'cze.1': ('soccer', '5347'),
            'den.1': ('soccer', '3913'),
            'ecu.1': ('soccer', '660'),
            'eng.1': ('soccer', '23'),  # Premier League
            'eng.2': ('soccer', '3914'), # Championship
            'eng.3': ('soccer', '3915'),
            'eng.4': ('soccer', '3916'),
            'eng.5': ('soccer', '3917'),
            'eng.charity': ('soccer', '5329'),
            'eng.fa': ('soccer', '40'),    # FA Cup
            'eng.league_cup': ('soccer', '3920'),
            'eng.trophy': ('soccer', '18481'),
            'eng.w.1': ('soccer', '8097'),
            'eng.w.fa': ('soccer', '20226'),
            'esp.1': ('soccer', '15'),    # La Liga
            'esp.2': ('soccer', '3921'),
            'esp.copa_de_la_reina': ('soccer', '20381'),
            'esp.copa_del_rey': ('soccer', '80'), # Copa del Rey
            'esp.super_cup': ('soccer', '8102'),
            'esp.w.1': ('soccer', '20956'),
            'eur': ('golf', '7002'),
            'fifa.friendly': ('soccer', '3922'),
            'fifa.friendly.w': ('soccer', '3923'),
            'fifa.worldq.afc': ('soccer', '789'),
            'fifa.worldq.caf': ('soccer', '790'),
            'fifa.worldq.concacaf': ('soccer', '788'),
            'fifa.worldq.conmebol': ('soccer', '787'),
            'fifa.worldq.ofc': ('soccer', '792'),
            'fifa.worldq.uefa': ('soccer', '786'),
            'fra.1': ('soccer', '9'),     # Ligue 1
            'fra.2': ('soccer', '3926'),
            'fra.coupe_de_france': ('soccer', '3952'),
            'fra.coupe_de_la_ligue': ('soccer', '3953'),
            'fra.w.1': ('soccer', '20955'),
            'ger.1': ('soccer', '10'),    # Bundesliga
            'ger.2': ('soccer', '3927'),
            'ger.dfb_pokal': ('soccer', '3954'),
            'ger.super_cup': ('soccer', '8101'),
            'gre.1': ('soccer', '3955'),
            'ind.1': ('soccer', '8316'),
            'irl': ('racing', '2040'),
            'irl.1': ('soccer', '3930'),
            'ita.1': ('soccer', '12'),    # Serie A
            'ita.2': ('soccer', '3931'),
            'ita.coppa_italia': ('soccer', '3956'),
            'ita.super_cup': ('soccer', '8103'),
            'jpn.1': ('soccer', '750'),
            'ksa.1': ('soccer', '21231'),
            'ksa.kings.cup': ('soccer', '22057'),
            'lpga': ('golf', '1107'),
            'mens-college-basketball': ('basketball', '41'),
            'mens-college-lacrosse': ('lacrosse', '502'),
            'mex.1': ('soccer', '22'),    # Liga MX
            'mlb': ('baseball', 'mlb'),
            'nascar-premier': ('racing', '2021'),
            'nba': ('basketball', 'nba'),
            'ned.1': ('soccer', '725'),   # Eredivisie
            'ned.2': ('soccer', '3933'),
            'ned.cup': ('soccer', '3957'),
            'ned.supercup': ('soccer', '10749'),
            'nfl': ('football', 'nfl'),
            'nhl': ('hockey', 'nhl'),
            'nor.1': ('soccer', '3960'),
            'par.1': ('soccer', '3934'),
            'per.1': ('soccer', '670'),
            'pga': ('golf', '1106'),
            'por.1': ('soccer', '715'),
            'por.taca.portugal': ('soccer', '20922'),
            'rou.1': ('soccer', '10747'),
            'rsa.1': ('soccer', '3937'),
            'rus.1': ('soccer', '3939'),
            'sco.1': ('soccer', '735'),
            'sco.2': ('soccer', '3940'),
            'sco.3': ('soccer', '3941'),
            'sco.4': ('soccer', '3942'),
            'sco.challenge': ('soccer', '5331'),
            'sco.cis': ('soccer', '5330'),
            'sco.tennents': ('soccer', '3959'),
            'sui.1': ('soccer', '3944'),
            'swe.1': ('soccer', '3945'),
            'tur.1': ('soccer', '3946'),
            'uefa.champions': ('soccer', '2'),  # UCL
            'uefa.euro_u21_qual': ('soccer', '20114'),
            'uefa.europa': ('soccer', '2310'), # Europa League
            'uefa.europa.conf': ('soccer', '20296'),
            'uefa.euroq': ('soccer', '3947'),
            'uefa.nations': ('soccer', '2395'),
            'uefa.super_cup': ('soccer', '5462'),
            'uefa.wchampions': ('soccer', '19483'),
            'ufc': ('mma', '3321'),
            'ufl': ('football', '37'),
            'uru.1': ('soccer', '680'),
            'usa.1': ('soccer', '19'),    # MLS
            'usa.nwsl': ('soccer', '8301'),
            'usa.nwsl.cup': ('soccer', '19868'),
            'usa.open': ('soccer', '5337'),
            'usa.usl.1': ('soccer', '4002'),
            'ven.1': ('soccer', '3949'),
            'wnba': ('basketball', '59'),
            'womens-college-basketball': ('basketball', '54'),
            'womens-college-lacrosse': ('lacrosse', '503'),
            'wta': ('tennis', '900'),
        }
        
        # Sort keys by length DESCENDING to prevent shadowing
        sorted_keys = sorted(KNOWN_LOGOS.keys(), key=len, reverse=True)
        
        for key in sorted_keys:
            if key in api_url:
                sport, lid = KNOWN_LOGOS[key]
                # Refined pattern selection:
                # 1. Standard American leagues (nba, nfl, etc) use teamlogos/leagues path
                # 2. Football/Soccer usually use leaguelogos/soccer path
                if lid in ['nba', 'nfl', 'mlb', 'nhl']:
                     return "https://a.espncdn.com/combiner/i?img=/i/teamlogos/leagues/500/{}.png".format(lid)
                
                # Check for other patterns? Standard default:
                return "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/{}/500/{}.png".format(sport, lid)
        return None
    
    def logo_downloaded(self, result, idx, logo_file):
        self.league_logos[idx] = logo_file
        self.refresh_list()
    
    def logo_error(self, error):
        pass

    # Display names for sport groups
    SPORT_DISPLAY_NAMES = {
        'soccer': 'SOCCER', 'basketball': 'BASKETBALL', 'football': 'AMERICAN FOOTBALL',
        'hockey': 'ICE HOCKEY', 'baseball': 'BASEBALL', 'racing': 'RACING',
        'tennis': 'TENNIS', 'rugby': 'RUGBY UNION', 'rugby-league': 'RUGBY LEAGUE',
        'cricket': 'CRICKET', 'golf': 'GOLF', 'boxing': 'BOXING',
        'mma': 'MMA', 'lacrosse': 'LACROSSE'
    }

    def refresh_list(self):
        list_content = []
        # Map from list index -> sorted_idx (skipping headers for toggle)
        self._list_to_sorted = []
        current_sport = None
        
        theme = global_sports_monitor.theme_mode
        c_header_bg = 0x0e1e5b if theme == 'ucl' else 0x2a0030
        c_header_fg = 0x00ffff if theme == 'ucl' else 0x00FF85
        
        for sorted_idx, original_idx in enumerate(self.sorted_indices):
            # Insert sport group header when sport changes
            sport = self._league_sports[sorted_idx] if hasattr(self, '_league_sports') else None
            if sport and sport != current_sport:
                current_sport = sport
                sport_label = self.SPORT_DISPLAY_NAMES.get(sport, sport.upper())
                # Check if this group also starts women's section
                is_women_start = self._league_women[sorted_idx] if hasattr(self, '_league_women') else False
                if is_women_start:
                    sport_label += u" (WOMEN)"
                # Create header entry (non-selectable)
                header = [('__GROUP__', False)]
                header.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 890, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, "", c_header_bg, c_header_bg, None, None))
                header.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 0, 860, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, u"\u25B6 " + sport_label, c_header_fg, c_header_fg, None, None))
                header.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 46, 860, 4, 0, RT_HALIGN_LEFT, "", c_header_fg, c_header_fg, None, None))
                list_content.append(header)
                self._list_to_sorted.append(-1)  # -1 = header, not selectable
            elif sport == current_sport and hasattr(self, '_league_women'):
                # Check for women transition within same sport
                is_women = self._league_women[sorted_idx]
                prev_women = self._league_women[sorted_idx - 1] if sorted_idx > 0 else False
                if is_women and not prev_women:
                    sport_label = self.SPORT_DISPLAY_NAMES.get(sport, sport.upper()) + u" (WOMEN)"
                    header = [('__GROUP__', False)]
                    header.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 890, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, "", c_header_bg, c_header_bg, None, None))
                    header.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 0, 860, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, u"\u25B6 " + sport_label, c_header_fg, c_header_fg, None, None))
                    header.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 46, 860, 4, 0, RT_HALIGN_LEFT, "", c_header_fg, c_header_fg, None, None))
                    list_content.append(header)
                    self._list_to_sorted.append(-1)
            
            name = DATA_SOURCES[original_idx][0]
            is_selected = self.selections[sorted_idx]
            logo_path = self.league_logos.get(sorted_idx, None)
            list_content.append(SelectionListEntry(name, is_selected, logo_path, mode=self.mode))
            self._list_to_sorted.append(sorted_idx)
        self["list"].setList(list_content)

    def toggle(self):
        list_idx = self["list"].getSelectedIndex()
        if list_idx is None: return
        # Map list index to sorted index (skip group headers)
        if not hasattr(self, '_list_to_sorted') or list_idx >= len(self._list_to_sorted):
            return
        sorted_idx = self._list_to_sorted[list_idx]
        if sorted_idx < 0: return  # Group header, skip
        
        if self.mode == "multi":
            self.selections[sorted_idx] = not self.selections[sorted_idx]
            self.refresh_list()
            # Restore cursor position after refresh
            try: self["list"].moveToIndex(list_idx)
            except: pass
        else:
            # Single mode: immediately return the selected original index
            original_idx = self.sorted_indices[sorted_idx]
            self.close((DATA_SOURCES[original_idx][0], original_idx))

    def save(self):
        if self.mode != "multi": return
        new_indices = []
        for sorted_idx, is_selected in enumerate(self.selections):
            if is_selected:
                # Map back to original DATA_SOURCES index
                original_idx = self.sorted_indices[sorted_idx]
                new_indices.append(original_idx)
        
        if not new_indices:
            self.session.open(MessageBox, "Please select at least one league.", MessageBox.TYPE_ERROR)
        else:
            global_sports_monitor.set_custom_leagues(new_indices)
            self.close(True)

# ==============================================================================
# RACING MINI BAR (Bottom) - Driver Standings Ticker
# ==============================================================================
class RacingMiniBar(Screen):
    """Bottom bar that shows driver standings for a selected racing event."""
    def __init__(self, session, event_data):
        Screen.__init__(self, session)
        self.event_data = event_data
        
        d_size = getDesktop(0).size()
        width = d_size.width(); height = d_size.height()
        
        if width > 1280:
            bar_h = 65; bar_y = height - bar_h + 11
            font_lg = "Regular;25"; font_nm = "Regular;30"; font_sm = "Regular;22"
        else:
            bar_h = 57; bar_y = height - bar_h + 11
            font_lg = "Regular;21"; font_nm = "Regular;26"; font_sm = "Regular;18"
        
        self.skin = """<screen position="0,{y}" size="{w},{h}" title="Racing Standings" backgroundColor="#40000000" flags="wfNoBorder">
            <eLabel position="0,0" size="{w},{h}" backgroundColor="#c0111111" zPosition="0" />
            <eLabel position="0,0" size="5,{h}" backgroundColor="#E90052" zPosition="1" />
            <eLabel position="{rend},0" size="5,{h}" backgroundColor="#F6B900" zPosition="1" />
            <widget name="lbl_league" position="15,0" size="250,{h}" font="{fl}" foregroundColor="#FFD700" transparent="1" halign="left" valign="center" zPosition="2" />
            <widget name="lbl_rank" position="270,0" size="60,{h}" font="{fn}" foregroundColor="#00FF85" transparent="1" halign="center" valign="center" zPosition="2" />
            <widget name="lbl_driver" position="335,0" size="600,{h}" font="{fn}" foregroundColor="#ffffff" transparent="1" halign="left" valign="center" zPosition="2" />
            <widget name="lbl_team" position="940,0" size="250,{h}" font="{fs}" foregroundColor="#cccccc" transparent="1" halign="left" valign="center" zPosition="2" />
            <widget name="lbl_points" position="1200,0" size="200,{h}" font="{fn}" foregroundColor="#FFD700" transparent="1" halign="right" valign="center" zPosition="2" />
            <widget name="lbl_status" position="1410,0" size="200,{h}" font="{fs}" foregroundColor="#aaaaaa" transparent="1" halign="right" valign="center" zPosition="2" />
        </screen>""".format(y=bar_y-6, w=width, h=bar_h, rend=width-5, fl=font_lg, fn=font_nm, fs=font_sm)
        
        self["lbl_league"] = Label("")
        self["lbl_session"] = Label("") # New session label
        self["lbl_rank"] = Label("")
        self["lbl_driver"] = Label("")
        self["lbl_team"] = Label("")
        self["lbl_points"] = Label("")
        self["lbl_status"] = Label("")
        
        self.drivers = []
        self.current_idx = 0
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close,
            "green": self.close,
        }, -1)
        
        self.ticker_timer = eTimer()
        safe_connect(self.ticker_timer, self.show_next_driver)
        self.onLayoutFinish.append(self.start_fetch)
        self.onClose.append(self.cleanup)
    
    def cleanup(self):
        if self.ticker_timer.isActive():
            self.ticker_timer.stop()
    
    def start_fetch(self):
        """Build summary URL and fetch event data for driver standings."""
        event_id = self.event_data.get('id', '')
        league_name = self.event_data.get('league_name', '')
        league_url = ''
        for item in DATA_SOURCES:
            if item[0] == league_name:
                league_url = item[1]
                break
        
        if not league_url or not event_id:
            self.show_from_scoreboard_data()
            return
        
        # Build summary URL
        if "scoreboard" in league_url:
            summary_url = league_url.replace("scoreboard", "summary") + "?event=" + str(event_id)
        else:
            summary_url = league_url + "/summary?event=" + str(event_id)
        
        self["lbl_league"].setText(league_name)
        self["lbl_driver"].setText("Loading standings...")
        
        try:
            getPage(summary_url.encode('utf-8')).addCallback(self.on_data).addErrback(self.on_error)
        except:
            self.show_from_scoreboard_data()
    
    def show_from_scoreboard_data(self):
        """Fallback: parse driver data from the scoreboard event data directly."""
        league_name = self.event_data.get('league_name', '')
        self["lbl_league"].setText(league_name)
        
        all_comps = self.event_data.get('competitions', [])
        self.drivers = []
        
        session_labels = {'FP1': 'Practice 1', 'FP2': 'Practice 2', 'FP3': 'Practice 3', 'Qual': 'Qualifying', 'Race': 'Race', 'SQ': 'Sprint Qual', 'Sprint': 'Sprint'}

        for comp_idx, comp in enumerate(all_comps):
            sess_type = comp.get('type', {}).get('abbreviation', 'S{}'.format(comp_idx+1))
            sess_name = session_labels.get(sess_type, sess_type)
            sess_state = comp.get('status', {}).get('type', {}).get('state', '')
            
            # Usually only show live or finished session results
            if sess_state not in ('in', 'post'): continue
            
            comps_list = comp.get('competitors', [])
            for i, c in enumerate(comps_list):
                athlete = c.get('athlete', {})
                name = athlete.get('displayName', '') or c.get('team', {}).get('displayName', 'Driver')
                country = athlete.get('flag', {}).get('alt', '')
                team = c.get('team', {}).get('displayName', '')
                rank = c.get('order', i + 1)
                is_winner = c.get('winner', False)
                score = c.get('score', '')
                
                display_name = name
                if country: display_name += u" ({})".format(country)
                
                status_txt = 'WINNER' if is_winner else ''
                self.drivers.append({
                    'session': sess_name,
                    'rank': rank, 
                    'name': display_name, 
                    'team': team, 
                    'points': str(score) if score else '', 
                    'status': status_txt
                })
        
        if not self.drivers:
            self["lbl_driver"].setText("No driver data available")
        else:
            self.current_idx = -1
            self.show_next_driver()
            self.ticker_timer.start(4000)
    
    def on_error(self, error):
        self.show_from_scoreboard_data()
    
    def on_data(self, body):
        """Parse summary API response for driver/competitor standings."""
        try:
            json_str = body.decode('utf-8', errors='ignore')
            data = json.loads(json_str)
            
            header = data.get('header', {})
            league_name = header.get('league', {}).get('name', '') or self.event_data.get('league_name', '')
            self["lbl_league"].setText(league_name)
            
            all_comps = data.get('competitions', []) or header.get('competitions', [])
            self.drivers = []
            session_labels = {'FP1': 'Practice 1', 'FP2': 'Practice 2', 'FP3': 'Practice 3', 'Qual': 'Qualifying', 'Race': 'Race', 'SQ': 'Sprint Qual', 'Sprint': 'Sprint'}

            for comp_idx, comp in enumerate(all_comps):
                sess_type = comp.get('type', {}).get('abbreviation', 'S{}'.format(comp_idx+1))
                sess_name = session_labels.get(sess_type, sess_type)
                sess_state = comp.get('status', {}).get('type', {}).get('state', '')
                
                # Standings usually make sense for LIVE or FINISHED
                if sess_state not in ('in', 'post'): continue
                
                competitors = comp.get('competitors', [])
                for i, driver in enumerate(competitors):
                    rank = driver.get('rank', driver.get('order', i + 1))
                    athlete = driver.get('athlete', {})
                    driver_name = athlete.get('displayName', '') or athlete.get('shortName', '')
                    team_info = driver.get('team', {})
                    team_name = team_info.get('displayName', '') or team_info.get('abbreviation', '')
                    vehicle_num = driver.get('vehicleNumber', '') or athlete.get('jersey', '')
                    points = driver.get('points', driver.get('score', ''))
                    d_status = driver.get('status', '')
                    
                    if not driver_name: driver_name = team_name or 'Driver'
                    
                    display_name = driver_name
                    if vehicle_num: display_name = "[#{}] {}".format(vehicle_num, driver_name)
                    
                    status_txt = ''
                    if d_status and d_status.lower() not in ['active', 'running', '']:
                        status_txt = d_status.upper()
                    
                    self.drivers.append({
                        'session': sess_name,
                        'rank': rank,
                        'name': display_name,
                        'team': team_name if team_name != driver_name else '',
                        'points': str(points) + ' pts' if points else '',
                        'status': status_txt
                    })
            
            if not self.drivers:
                self.show_from_scoreboard_data()
            else:
                self.current_idx = -1
                self.show_next_driver()
                self.ticker_timer.start(4000)
        except Exception as e:
            self.show_from_scoreboard_data()
    
    def show_next_driver(self):
        if not self.drivers: return
        self.current_idx = (self.current_idx + 1) % len(self.drivers)
        d = self.drivers[self.current_idx]
        
        # We can repurpose league label OR we update both
        # Let's show "League | Session" in the league label area to save space
        league_name = self.event_data.get('league_name', 'Racing')
        self["lbl_league"].setText("{} | {}".format(league_name, d.get('session', '')))
        
        self["lbl_rank"].setText("P{}".format(d['rank']))
        self["lbl_driver"].setText(str(d['name']))
        self["lbl_team"].setText(str(d['team']))
        self["lbl_points"].setText(str(d['points']))
        self["lbl_status"].setText(str(d['status']))

# ==============================================================================
# MINI BAR 2 (Bottom) - FIXED: Callback Synchronization
# ==============================================================================
class SimpleSportsMiniBar2(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        
        self.logo_path = "/tmp/simplysports/logos/"
        if not os.path.exists(self.logo_path):
            try: os.makedirs(self.logo_path)
            except: pass

        d_size = getDesktop(0).size()
        width = d_size.width(); height = d_size.height()
        
        if width > 1280:
            bar_h = 65; y_sc = 39; bar_y = height - bar_h + 11; font_lg = "Regular;25"; font_nm = "Regular;34"; font_sm = "Regular;22"; font_sc = "Regular;18"; logo_s = 35
            x_l_logo=15; y_l_logo=10; x_league=55; w_league=328; x_home_name=393; w_home_name=467; x_h_logo=875
            x_score=920; w_score=140; x_a_logo=1065; x_away_name=1115; w_away_name=490
            x_status=1615; w_status=90; x_time=1707; w_time=210
            x_h_sc = 543; w_h_sc = 317; x_a_sc = 1115; w_a_sc = 340
            x_h_rc = 393; x_h_rctxt = 415; x_a_rc = 1455; x_a_rctxt = 1475
        else:
            bar_h = 57; y_sc = 33; bar_y = height - bar_h + 11; font_lg = "Regular;21"; font_nm = "Regular;28"; font_sm = "Regular;18"; font_sc = "Regular;16"; logo_s = 30
            x_l_logo=5; y_l_logo=8; x_league=40; w_league=213; x_home_name=263; w_home_name=257; x_h_logo=540
            x_score=580; w_score=100; x_a_logo=685; x_away_name=740; w_away_name=260
            x_status=1010; w_status=80; x_time=1092; w_time=175
            x_h_sc = 363; w_h_sc = 157; x_a_sc = 740; w_a_sc = 160
            x_h_rc = 263; x_h_rctxt = 283; x_a_rc = 905; x_a_rctxt = 925
            
        if global_sports_monitor.theme_mode == "ucl":
            self.skin = """<screen position="0,{y}" size="{w},{h}" title="Sports Ticker Bottom" backgroundColor="#40000000" flags="wfNoBorder"><eLabel position="0,0" size="{w},{h}" backgroundColor="#c00e1e5b" zPosition="0" /><eLabel position="0,0" size="{w},2" backgroundColor="#00ffff" zPosition="1" /><widget name="l_logo" position="{xll},{yll}" size="{ls},{ls}" alphatest="blend" scale="1" zPosition="2" /><widget name="lbl_league" position="{xl},-5" size="{wl},{h}" font="{fl}" foregroundColor="#00ffff" backgroundColor="#c00e1e5b" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_home" position="{xh},0" size="{wh},44" font="{fn}" foregroundColor="#ffffff" backgroundColor="#c00e1e5b" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="lbl_home_sc" position="{xhsc},{ysc}" size="{whsc},24" font="{fsc}" foregroundColor="#cccccc" backgroundColor="#c00e1e5b" transparent="1" halign="right" valign="top" zPosition="2" /><widget name="h_sc_rc" position="{xhrc},39" size="{rcs},{rcs}" alphatest="blend" scale="1" zPosition="3" /><widget name="h_sc_rctxt" position="{xhtxt},36" size="130,24" font="{fsc}" foregroundColor="#ff3333" backgroundColor="#c00e1e5b" transparent="1" halign="left" valign="center" zPosition="3" /><widget name="h_logo" position="{xhl},4" size="{ls},{ls}" alphatest="blend" scale="1" zPosition="2" /><eLabel position="{xs},-5" size="{ws},{h}" backgroundColor="#ffffff" zPosition="1" /><widget name="lbl_score" position="{xs},-5" size="{ws},{h}" font="{fl}" foregroundColor="#0e1e5b" backgroundColor="#ffffff" transparent="1" halign="center" valign="center" zPosition="3" /><widget name="a_logo" position="{xal},4" size="{ls},{ls}" alphatest="blend" scale="1" zPosition="2" /><widget name="lbl_away" position="{xa},0" size="{wa},44" font="{fn}" foregroundColor="#ffffff" backgroundColor="#c00e1e5b" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_away_sc" position="{xasc},{ysc}" size="{wasc},24" font="{fsc}" foregroundColor="#cccccc" backgroundColor="#c00e1e5b" transparent="1" halign="left" valign="top" zPosition="2" /><widget name="a_sc_rc" position="{xarc},39" size="{rcs},{rcs}" alphatest="blend" scale="1" zPosition="3" /><widget name="a_sc_rctxt" position="{xatxt},36" size="130,24" font="{fsc}" foregroundColor="#ff3333" backgroundColor="#c00e1e5b" transparent="1" halign="left" valign="center" zPosition="3" /><widget name="lbl_status" position="{xst},-5" size="{wst},{h}" font="{fs}" foregroundColor="#ffffff" backgroundColor="#c00e1e5b" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="lbl_time" position="{xt},-5" size="{wt},{h}" font="{fs}" foregroundColor="#00ffff" backgroundColor="#c00e1e5b" transparent="1" halign="right" valign="center" zPosition="2" /></screen>""".format(y=bar_y, w=width, h=bar_h, fl=font_lg, fn=font_nm, fs=font_sm, fsc=font_sc, ls=logo_s, xll=x_l_logo, yll=y_l_logo, xl=x_league, wl=w_league, xh=x_home_name, wh=w_home_name, xhl=x_h_logo, xs=x_score, ws=w_score, xst=x_status, wst=w_status, xal=x_a_logo, xa=x_away_name, wa=w_away_name, xt=x_time, wt=w_time, ysc=y_sc-2, xhsc=x_h_sc, whsc=w_h_sc, xasc=x_a_sc, wasc=w_a_sc, xhrc=x_h_rc, xhtxt=x_h_rctxt, xarc=x_a_rc, xatxt=x_a_rctxt, rcs=18)
        else:
            # DEFINE COLORS BASED ON SELECTED MODE
            mode = global_sports_monitor.minibar_color_mode
            
            # Default Colors (Classic)
            c_bg_main = "#c0331900"    # Dark Purple (Transparent)
            c_strip_l = "#E90052"      # Pink
            c_strip_r = "#F6B900"      # Gold
            c_score_bg = "#00FF85"     # Green
            c_score_fg = "#000000"     # Black
            c_text_lg = "#FFD700"      # Gold
            c_text_tm = "#00FF85"      # Green
            
            # BROADCAST ACCURATE COLORS (High Opacity: 1a = ~10% transparent)
            if mode == "pl":
                c_bg_main = "#1a38003c" # PL Purple (Deep)
                c_strip_l = "#e90052"   # PL Pink (Left Accent)
                c_strip_r = "#00ff85"   # PL Green (Right Accent)
                c_score_bg = "#ffffff"  # White
                c_score_fg = "#38003c"  # PL Purple Text
                c_text_lg = "#00ff85"   # PL Green
                c_text_tm = "#ffffff"   # White
            elif mode == "laliga":
                c_bg_main = "#1a111111" # Off Black (Solid)
                c_strip_l = "#ff4b4b"   # LaLiga Red (Coral)
                c_strip_r = "#ff4b4b"   # Red
                c_score_bg = "#ff4b4b"  # Red
                c_score_fg = "#ffffff"  # White
                c_text_lg = "#ffffff"   # White
                c_text_tm = "#ffffff"   # White
            elif mode == "seriea":
                c_bg_main = "#1a02055a" # Serie A Navy (Deep Blue)
                c_strip_l = "#0057ae"   # TIM Blue
                c_strip_r = "#00fff5"   # Cyan Accent
                c_score_bg = "#00fff5"  # Cyan
                c_score_fg = "#02055a"  # Navy Text
                c_text_lg = "#00fff5"   # Cyan
                c_text_tm = "#ffffff"   # White
            elif mode == "ligue1":
                c_bg_main = "#1a091c3e" # Dark Navy/Black
                c_strip_l = "#dbf000"   # L1 Lime Yellow
                c_strip_r = "#ffffff"   # White
                c_score_bg = "#dbf000"  # Lime
                c_score_fg = "#091c3e"  # Dark Text
                c_text_lg = "#dbf000"   # Lime
                c_text_tm = "#ffffff"   # White

            self.skin = """<screen position="0,{y}" size="{w},{h}" title="Sports Ticker Bottom" backgroundColor="#40000000" flags="wfNoBorder"><eLabel position="0,0" size="{w},{h}" backgroundColor="{bg}" zPosition="0" /><eLabel position="0,0" size="5,{h}" backgroundColor="{sl}" zPosition="1" /><eLabel position="{rend},{h}" size="5,{h}" backgroundColor="{sr}" zPosition="1" /><widget name="l_logo" position="{xll},{yll}" size="{ls},{ls}" alphatest="blend" scale="1" zPosition="2" /><widget name="lbl_league" position="{xl},-5" size="{wl},{h}" font="{fl}" foregroundColor="{tlg}" backgroundColor="{bg}" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_home" position="{xh},0" size="{wh},38" font="{fn}" foregroundColor="#FFFFFF" backgroundColor="{bg}" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="lbl_home_sc" position="{xhsc},{ysc}" size="{whsc},24" font="{fsc}" foregroundColor="#cccccc" backgroundColor="{bg}" transparent="1" halign="right" valign="top" zPosition="2" /><widget name="h_sc_rc" position="{xhrc},39" size="{rcs},{rcs}" alphatest="blend" scale="1" zPosition="3" /><widget name="h_sc_rctxt" position="{xhtxt},36" size="130,24" font="{fsc}" foregroundColor="#ff3333" backgroundColor="{bg}" transparent="1" halign="left" valign="center" zPosition="3" /><widget name="h_logo" position="{xhl},4" size="{ls},{ls}" alphatest="blend" scale="1" zPosition="2" /><eLabel position="{xs},-5" size="{ws},{h}" backgroundColor="{sbg}" zPosition="1" /><widget name="lbl_score" position="{xs},-5" size="{ws},{h}" font="{fl}" foregroundColor="{sfg}" backgroundColor="{sbg}" transparent="1" halign="center" valign="center" zPosition="3" /><widget name="a_logo" position="{xal},4" size="{ls},{ls}" alphatest="blend" scale="1" zPosition="2" /><widget name="lbl_away" position="{xa},0" size="{wa},38" font="{fn}" foregroundColor="#FFFFFF" backgroundColor="{bg}" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_away_sc" position="{xasc},{ysc}" size="{wasc},24" font="{fsc}" foregroundColor="#cccccc" backgroundColor="{bg}" transparent="1" halign="left" valign="top" zPosition="2" /><widget name="a_sc_rc" position="{xarc},39" size="{rcs},{rcs}" alphatest="blend" scale="1" zPosition="3" /><widget name="a_sc_rctxt" position="{xatxt},36" size="130,24" font="{fsc}" foregroundColor="#ff3333" backgroundColor="{bg}" transparent="1" halign="left" valign="center" zPosition="3" /><widget name="lbl_status" position="{xst},-5" size="{wst},{h}" font="{fs}" foregroundColor="#FFFFFF" backgroundColor="{bg}" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="lbl_time" position="{xt},-5" size="{wt},{h}" font="{fs}" foregroundColor="{ttm}" backgroundColor="{bg}" transparent="1" halign="right" valign="center" zPosition="2" /></screen>""".format(y=bar_y-6, w=width, h=bar_h, rend=width-5, fl=font_lg, fn=font_nm, fs=font_sm, fsc=font_sc, ls=logo_s, xll=x_l_logo, yll=y_l_logo, xl=x_league, wl=w_league, xh=x_home_name, wh=w_home_name, xhl=x_h_logo, xs=x_score, ws=w_score, xst=x_status, wst=w_status, xal=x_a_logo, xa=x_away_name, wa=w_away_name, xt=x_time, wt=w_time, ysc=y_sc, bg=c_bg_main, sl=c_strip_l, sr=c_strip_r, sbg=c_score_bg, sfg=c_score_fg, tlg=c_text_lg, ttm=c_text_tm, xhsc=x_h_sc, whsc=w_h_sc, xasc=x_a_sc, wasc=w_a_sc, xhrc=x_h_rc, xhtxt=x_h_rctxt, xarc=x_a_rc, xatxt=x_a_rctxt, rcs=18)

        self["lbl_league"] = Label(""); self["lbl_home"] = Label(""); self["lbl_score"] = Label("")
        self["lbl_away"] = Label(""); self["lbl_status"] = Label(""); self["lbl_time"] = Label("")
        self["lbl_home_sc"] = Label(""); self["lbl_away_sc"] = Label("")
        self["h_logo"] = Pixmap(); self["a_logo"] = Pixmap(); self["l_logo"] = Pixmap()
        self["h_sc_rc"] = Pixmap(); self["a_sc_rc"] = Pixmap()
        self["h_sc_rctxt"] = Label(""); self["a_sc_rctxt"] = Label("")
        self["h_logo"].hide(); self["a_logo"].hide(); self["l_logo"].hide()
        self["h_sc_rc"].hide(); self["a_sc_rc"].hide()
        self["h_sc_rctxt"].hide(); self["a_sc_rctxt"].hide()
        self.matches = []; self.current_match_idx = 0
        self.rc_pixmap = None
        try:
            rc_path = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/red.jpg")
            if os.path.exists(rc_path) and LoadPixmap:
                self.rc_pixmap = LoadPixmap(cached=True, path=rc_path)
        except: pass
        self.league_colors = {"ENG": 0x00ff85, "ESP": 0xff4b4b, "ITA": 0x008fd7, "GER": 0xd3010c, "FRA": 0xdae025, "UCL": 0x00ffff, "UEL": 0xff8800, "NBA": 0xC9082A, "NFL": 0x013369}
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {"cancel": self.close, "green": self.close, "yellow": self.toggle_filter_mini}, -1)
        self.ticker_timer = eTimer(); safe_connect(self.ticker_timer, self.show_next_match)
        self.refresh_timer = eTimer(); safe_connect(self.refresh_timer, self.refresh_data)
        global_sports_monitor.register_callback(self.on_data_ready)
        self.onLayoutFinish.append(self.start_all_timers)
        self.onClose.append(self.cleanup)

    def cleanup(self):
        global_sports_monitor.unregister_callback(self.on_data_ready)

    def start_all_timers(self):
        self.parse_json()
        global_sports_monitor.check_goals()
        # ENSURE: single_shot=False (2nd param) for repeating update
        self.refresh_timer.start(60000 + random.randint(0, 15000), False)
        # Also ensure ticker timer is running if matches exist
        if self.matches and not self.ticker_timer.isActive():
            self.ticker_timer.start(5000, False)

    def on_data_ready(self, success, force_refresh=False):
        self.parse_json()

    def toggle_filter_mini(self): 
        global_sports_monitor.toggle_filter()
        self.parse_json()
            
    def refresh_data(self): 
        global_sports_monitor.check_goals(from_ui=True)

    def get_scorers_string(self, event, home_id, away_id):
        h_scorers = []; a_scorers = []
        h_rcs = []; a_rcs = []
        try:
            details = event.get('competitions', [{}])[0].get('details', [])
            if not details: details = event.get('header', {}).get('competitions', [{}])[0].get('details', [])
            if details:
                for play in details:
                    text_desc = play.get('type', {}).get('text', '').lower()
                    
                    is_rc = play.get('redCard', False)
                    if is_rc or ('card' in text_desc and 'red' in text_desc):
                        rc_ath = play.get('athletesInvolved', [])
                        if not rc_ath: rc_ath = play.get('participants', [])
                        if rc_ath:
                            rc_name = rc_ath[0].get('displayName') or rc_ath[0].get('shortName', '')
                            if rc_name:
                                t_id = str(play.get('team', {}).get('id', ''))
                                if t_id == str(home_id): 
                                    if rc_name not in h_rcs: h_rcs.append(rc_name)
                                elif t_id == str(away_id):
                                    if rc_name not in a_rcs: a_rcs.append(rc_name)

                    is_scoring = play.get('scoringPlay', False) or "goal" in text_desc or "score" in text_desc or "touchdown" in text_desc
                    if is_scoring and "disallowed" not in text_desc:
                        scorer = ""
                        athletes = play.get('athletesInvolved', [])
                        if athletes: scorer = athletes[0].get('shortName') or athletes[0].get('displayName')
                        elif play.get('participants'): scorer = play['participants'][0].get('athlete', {}).get('shortName')
                        if not scorer:
                            full_text = play.get('text', '')
                            if full_text:
                                if "Goal by " in full_text: scorer = full_text.split("Goal by ")[1].split("-")[0].strip()
                                elif "Own Goal by " in full_text: scorer = full_text.split("Own Goal by ")[1].split("-")[0].strip()
                                elif " Goal " in full_text or " Goal" in full_text: scorer = full_text.split(" Goal")[0].strip()
                                elif " Penalty " in full_text or " Penalty" in full_text: scorer = full_text.split(" Penalty")[0].strip()
                            
                            if not scorer:
                                clean = play.get('type', {}).get('text', '')
                                if "Goal - " in clean: scorer = clean.split("Goal - ")[1].split('(')[0].strip()
                                elif "Gamewinner - " in clean: scorer = clean.split("Gamewinner - ")[1].split('(')[0].strip()
                                elif "Short Handed Goal - " in clean: scorer = clean.split("Short Handed Goal - ")[1].split('(')[0].strip()
                                elif "Power Play Goal - " in clean: scorer = clean.split("Power Play Goal - ")[1].split('(')[0].strip()
                        if scorer: scorer = scorer.strip()
                        if not scorer:
                            scorer = "Goal"
                            
                        # (G) is redundant, only show (P)enalty or (O)wn Goal
                        g_type = ""
                        if "penalty" in text_desc: g_type = " (P)"
                        elif "own" in text_desc: g_type = " (O)"

                        g_time = play.get('clock', {}).get('displayValue', '')
                        if g_time: 
                            scorer = "{}{}{} {}".format(scorer, g_type, "", g_time).replace("  ", " ")
                        else: 
                            scorer = "{}{}".format(scorer, g_type)
                            
                        t_id = str(play.get('team', {}).get('id', ''))
                        if t_id == str(home_id): h_scorers.append(scorer)
                        elif t_id == str(away_id): a_scorers.append(scorer)
        except: pass
        def format_list(lst, rc_lst):
            if not lst and not rc_lst: return ""
            seen = set(); unique = [x for x in lst if not (x in seen or seen.add(x))]
            final_str = ", ".join(unique)
            if len(final_str) > 35:
                short_list = []
                for n in unique:
                    parts = n.split(' ')
                    if len(parts) >= 2:
                        short_list.append("{} {}".format(parts[-2], parts[-1]))
                    else:
                        short_list.append(n)
                final_str = ", ".join(short_list)
            if rc_lst:
                rc_str = ", ".join(rc_lst)
                if final_str: final_str += " |RC| " + rc_str
                else: final_str = " |RC| " + rc_str
            return final_str
        return format_list(h_scorers, h_rcs), format_list(a_scorers, a_rcs)

    def parse_json(self):
        events = global_sports_monitor.cached_events
        new_matches = []
        if not events:
            # If we already have matches and an update is in progress, keep old matches to avoid flicker
            if self.matches and "Loading" in global_sports_monitor.status_message:
                return
            msg = global_sports_monitor.status_message or "Loading..."
            self.matches = [{'league': "SimplySports", 'color': 0xffffff, 'home': msg, 'away': "", 'score': "", 'status': "", 'time': "", 'h_url': "", 'a_url': "", 'l_url': "", 'h_id': "", 'a_id': "", 'l_id': ""}]
            self.show_next_match()
            return
            
        mode = global_sports_monitor.filter_mode

        # Pre-compute dates once per render pass
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = datetime.datetime.utcfromtimestamp(calendar.timegm(now.timetuple()) + 86400).strftime("%Y-%m-%d")
        yesterday_str = datetime.datetime.utcfromtimestamp(calendar.timegm(now.timetuple()) - 86400).strftime("%Y-%m-%d")

        for event in events:
            snap = global_sports_monitor.match_snapshots.get(str(event.get('id', '')))
            if not snap: continue
            if not snapshot_passes_filter(snap, mode, today_str, tomorrow_str, yesterday_str): continue

            # Racing events (>2 competitors) -- use event shortName
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            if len(comps) > 2:
                race = event.get('shortName', 'Event')
                venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                match_data = {'league': snap['league_name'], 'color': 0xffffff, 'home': race, 'away': venue,
                              'score': "VS", 'status': snap['status_short'], 'time': snap['time_str'],
                              'h_url': snap['h_logo_url'], 'a_url': snap['a_logo_url'], 'l_url': snap['l_logo_url'],
                              'h_id': snap['h_logo_id'], 'a_id': snap['a_logo_id'], 'l_id': snap['l_logo_id']}
            else:
                # League color lookup
                l_color = 0xffffff
                for key, val in self.league_colors.items():
                    if key in snap['league_name'].upper() or key in event.get('shortName', '').upper(): l_color = val; break

                # Build match data from snapshot -- all parsing already done
                match_data = {
                    'league':     snap['league_name'],
                    'color':      l_color,
                    'home':       snap['h_name_short'],
                    'away':       snap['a_name_short'],
                    'score':      snap['score_str'],
                    'status':     snap['status_short'],
                    'time':       snap['time_str'],
                    'h_url':      snap['h_logo_url'],
                    'a_url':      snap['a_logo_url'],
                    'l_url':      snap['l_logo_url'],
                    'h_id':       snap['h_logo_id'],
                    'a_id':       snap['a_logo_id'],
                    'l_id':       snap['l_logo_id'],
                    # MiniBar2 extras for lazy scorer loading
                    'home_clean': snap['h_name_short'],
                    'away_clean': snap['a_name_short'],
                    'h_scorers':  None,
                    'a_scorers':  None,
                    'event_ref':  event,
                    'h_team_id':  snap['h_team_id'],
                    'a_team_id':  snap['a_team_id'],
                    'sport_type': snap['sport_type'],
                    'state':      snap['state'],
                }
            new_matches.append(match_data)
            
        # Handle Filter Empty
        if not new_matches:
            # If we are currently updating, don't show "No Matches Found" yet if we have old data
            if self.matches and ("Loading" in global_sports_monitor.status_message or "Processing" in global_sports_monitor.status_message):
                return
                
            is_stale = (time.time() - global_sports_monitor.last_update) > 300
            msg = "Updating Data..." if is_stale else "No Matches Found"
            sub = "Please Wait" if is_stale else "Check Filters"
            new_matches.append({'league': "SimplySports", 'color': 0xffffff, 'home': msg, 'away': sub, 'score': "", 'status': "", 'time': "", 'h_url': "", 'a_url': "", 'l_url': "", 'h_id': "", 'a_id': "", 'l_id': ""})

        self.matches = new_matches
        if not self.ticker_timer.isActive(): 
            self.show_next_match()
            self.ticker_timer.start(5000, False)

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
            
            # FORMAT LEAGUE & STATUS 
            l_status = str(data.get('status', ''))
            self["lbl_league"].setText(league_name)
            self["lbl_status"].setText(l_status)
            
        except Exception as e:
            print("[SimpleSportsMiniBar] Font adjust error:", e)

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
        self["lbl_away"].setText(str(a_txt))
        # self["lbl_status"] is already set in font adjustment block above
        
        # Red Card / Scorer Parser
        rc_pixmap = self.rc_pixmap

        def render_scorer_rc(widget_sc, widget_rc, widget_rctxt, text):
            if not text:
                widget_sc.setText("")
                widget_rc.hide()
                widget_rctxt.hide()
                return

            if "|RC|" in text:
                parts = text.split("|RC|")
                sc_part = parts[0].strip()
                rc_part = ", ".join([p.strip() for p in parts[1:] if p.strip()])
                
                if sc_part: widget_sc.setText("({})".format(sc_part))
                else: widget_sc.setText("")
                
                if rc_pixmap:
                    try:
                        widget_rc.instance.setPixmap(rc_pixmap)
                        widget_rc.instance.setScale(1)
                    except: pass
                    widget_rc.show()
                else: widget_rc.hide()
                
                widget_rctxt.setText(rc_part)
                widget_rctxt.show()
            else:
                widget_sc.setText("({})".format(text))
                widget_rc.hide()
                widget_rctxt.hide()
                
        render_scorer_rc(self["lbl_home_sc"], self["h_sc_rc"], self["h_sc_rctxt"], h_sc)
        render_scorer_rc(self["lbl_away_sc"], self["a_sc_rc"], self["a_sc_rctxt"], a_sc)
        
        self["lbl_time"].setText(str(data.get('time', '')))
        
        self.load_logo(data.get('h_url'), data.get('h_id'), "h_logo")
        self.load_logo(data.get('a_url'), data.get('a_id'), "a_logo")
        self.load_logo(data.get('l_url'), data.get('l_id'), "l_logo")

    def load_logo(self, url, img_id, widget_name):
        """Delegate to shared logo loader (unified cache + pixmap memory cache)"""
        load_logo_to_widget(self, widget_name, url, img_id)

# ==============================================================================
# ATHLETE PROFILE SCREEN
# ==============================================================================
class AthleteProfileScreen(Screen):
    def __init__(self, session, athlete_id, athlete_name, sport="soccer", league="eng.1"):
        Screen.__init__(self, session)
        self.session = session
        self.athlete_id = str(athlete_id)
        self.athlete_name = athlete_name
        self.sport = sport
        self.league = league
        self.theme = global_sports_monitor.theme_mode
        
        # API URLs
        self.api_url = "https://site.web.api.espn.com/apis/common/v3/sports/{}/{}/athletes/{}/overview".format(sport, league, athlete_id)
        
        # UI State
        self.full_rows = []
        
        if self.theme == "ucl":
            bg_color = "#00000000"; top_bar = "#091442"; accent = "#00ffff"
        else:
            bg_color = "#38003C"; top_bar = "#28002C"; accent = "#00FF85"
            
        common_widgets = """
            <widget name="match_title" position="0,5" size="1600,28" font="Regular;26" foregroundColor="{accent}" transparent="1" halign="center" valign="center" text="PLAYER PROFILE" zPosition="6" />
            
            <!-- Headshot and Logos -->
            <widget name="headshot" position="50,25" size="110,110" alphatest="blend" zPosition="5" scale="1" />
            <widget name="t_logo" position="1440,25" size="110,110" alphatest="blend" zPosition="5" scale="1" />
            
            <!-- Core Info -->
            <widget name="a_name" position="170,35" size="600,55" font="Regular;44" foregroundColor="#ffffff" transparent="1" halign="left" valign="center" zPosition="5" />
            <widget name="a_details" position="170,90" size="800,30" font="Regular;24" foregroundColor="#aaaaaa" transparent="1" halign="left" valign="center" zPosition="5" />
            
            <!-- List -->
            <widget name="info_list" position="0,160" size="1600,700" scrollbarMode="showNever" transparent="1" zPosition="5" />
            <widget name="loading" position="0,400" size="1600,100" font="Regular;32" foregroundColor="{accent}" transparent="1" halign="center" zPosition="10" />
        """.replace("{accent}", accent)
        
        self.skin = f"""<screen position="center,center" size="1600,900" title="Player Profile" flags="wfNoBorder" backgroundColor="{bg_color}"><eLabel position="0,0" size="1600,150" backgroundColor="{top_bar}" zPosition="0" /><eLabel position="0,150" size="1600,4" backgroundColor="{accent}" zPosition="1" />{common_widgets}</screen>"""
        
        self["match_title"] = Label("PLAYER PROFILE")
        self["a_name"] = Label(athlete_name)
        self["a_details"] = Label("")
        self["headshot"] = Pixmap()
        self["t_logo"] = Pixmap()
        self["loading"] = Label("Loading profile...")
        
        self["info_list"] = MenuList([], enableWrapAround=False, content=eListboxPythonMultiContent)
        self["info_list"].l.setFont(0, gFont("Regular", 24))
        self["info_list"].l.setFont(1, gFont("Regular", 20))
        self["info_list"].l.setItemHeight(50)
        
        self["actions"] = ActionMap(["SetupActions", "ColorActions"], {
            "cancel": self.close, "green": self.close, "ok": self.close, "back": self.close,
            "up": self["info_list"].up, "down": self["info_list"].down
        }, -2)
        
        self.onLayoutFinish.append(self.start_loading)

    def start_loading(self):
        # Note: headshot loading uses the common sport name, so typically "soccer" works.
        headshot_url = "https://a.espncdn.com/combiner/i?img=/i/headshots/{}/players/full/{}.png".format(self.sport, self.athlete_id)
        load_logo_to_widget(self, "headshot", headshot_url, "p_" + self.athlete_id)
        
        getPage(self.api_url.encode('utf-8')).addCallback(self.parse_data).addErrback(self.error_data)

    def error_data(self, error):
        self["loading"].setText("Error loading profile.")

    def parse_data(self, body):
        try:
            self["loading"].hide()
            data = json.loads(body.decode('utf-8', errors='ignore'))
            
            athlete = data.get('athlete', {})
            
            # --- HEADER DETAILS ---
            pos = athlete.get('position', {}).get('displayName', '')
            jersey = athlete.get('displayJersey', '')
            height = athlete.get('displayHeight', '')
            weight = athlete.get('displayWeight', '')
            age = str(athlete.get('age', ''))
            citizenship = athlete.get('citizenship', '')
            
            parts = []
            if jersey: parts.append(jersey)
            if pos: parts.append(pos)
            if height and weight: parts.append("{} / {}".format(height, weight))
            if age: parts.append("{} yrs".format(age))
            if citizenship: parts.append(citizenship)
            
            self["a_details"].setText(" | ".join(parts))
            if not self.athlete_name or self.athlete_name == "Player":
                self["a_name"].setText(athlete.get('displayName', 'Player Profile'))
                
            # Team logo
            t_logo = athlete.get('team', {}).get('logos', [{}])[0].get('href', '')
            t_id = athlete.get('team', {}).get('id', '')
            if t_logo:
                load_logo_to_widget(self, "t_logo", t_logo, "t_" + str(t_id))

            self.full_rows = []
            
            # --- SEASON STATS SUMMARY ---
            stats_summary = data.get('statsSummary', {})
            if stats_summary:
                self.full_rows.append(TextListEntry(stats_summary.get('displayName', 'SEASON STATS'), self.theme, is_header=True))
                stats_list = stats_summary.get('statistics', [])
                # Group by 3 for display
                for i in range(0, len(stats_list), 3):
                    chunk = stats_list[i:i+3]
                    row_txt = "  |  ".join(["{}: {}".format(s.get('shortDisplayName', s.get('name', '')), s.get('displayValue', '')) for s in chunk])
                    self.full_rows.append(TextListEntry("    " + row_txt, self.theme))
                self.full_rows.append(TextListEntry("", self.theme))

            # --- SPLITS ---
            stats = data.get('statistics', {})
            if stats:
                self.full_rows.append(TextListEntry("COMPETITION SPLITS", self.theme, is_header=True))
                splits = stats.get('splits', [])
                disp_names = stats.get('displayNames', [])
                
                names = stats.get('names', [])
                key_stats = ['appearances', 'starts', 'totalGoals', 'goalAssists', 'yellowCards', 'redCards', 'cleanSheet', 'saves', 'goalsConceded']
                idx_map = []
                for ks in key_stats:
                    try: idx_map.append((names.index(ks), disp_names[names.index(ks)].replace("Total ", "").replace("Yellow ", "Y").replace("Red ", "R")))
                    except: pass
                
                # Header row
                header_txt = "COMPETITION"
                for idx, name in idx_map: header_txt += " | " + name
                self.full_rows.append(TextListEntry("    " + header_txt, self.theme))
                
                for split in splits:
                    name = split.get('displayName', '')
                    s_vals = split.get('stats', [])
                    row_txt = name
                    for idx, _ in idx_map:
                        val = s_vals[idx] if idx < len(s_vals) else "-"
                        row_txt += " | " + str(val)
                    self.full_rows.append(TextListEntry("    " + row_txt, self.theme))
                self.full_rows.append(TextListEntry("", self.theme))

            # --- GAMELOG ---
            gamelog = data.get('gameLog', {})
            if gamelog:
                self.full_rows.append(TextListEntry(gamelog.get('displayName', 'RECENT MATCHES'), self.theme, is_header=True))
                gl_stats = gamelog.get('statistics', [])
                if gl_stats:
                    g_stat = gl_stats[0]
                    names = g_stat.get('names', [])
                    disp_names = g_stat.get('displayNames', [])
                    events = g_stat.get('events', [])
                    
                    key_stats = ['appearances', 'totalGoals', 'goalAssists', 'yellowCards', 'redCards', 'saves', 'goalsConceded']
                    idx_map = []
                    for ks in key_stats:
                        try: idx_map.append((names.index(ks), disp_names[names.index(ks)].replace("Total ", "").replace("Yellow ", "Y").replace("Red ", "R")))
                        except: pass
                    
                    for ev in events[:5]: # Last 5 matches
                        ev_id = ev.get('eventId')
                        ev_data = gamelog.get('events', {}).get(ev_id, {})
                        if ev_data:
                            date_str = ev_data.get('gameDate', '')[:10]
                            opp = ev_data.get('opponent', {}).get('abbreviation', '')
                            res = ev_data.get('gameResult', '') + " " + ev_data.get('score', '')
                            match_str = "{} vs {} ({})".format(date_str, opp, res)
                            
                            stats_arr = ev.get('stats', [])
                            for idx, name in idx_map:
                                val = stats_arr[idx] if idx < len(stats_arr) else "-"
                                if str(val) not in ["0", "-", "0.0", "Started"]:
                                    match_str += " | {}: {}".format(name, val)
                            
                            self.full_rows.append(TextListEntry("    " + match_str, self.theme))
                self.full_rows.append(TextListEntry("", self.theme))
                
            # --- NEWS ---
            news = data.get('news', [])
            if news:
                self.full_rows.append(TextListEntry("LATEST NEWS", self.theme, is_header=True))
                for n in news[:3]:
                    hl = n.get('headline', '')
                    self.full_rows.append(TextListEntry("    \u2022 " + hl, self.theme, align="left"))

            self["info_list"].setList(self.full_rows)
        except Exception as e:
            self["loading"].setText("Parse Error: " + str(e))
            self["loading"].show()

# ==============================================================================
# MINI BAR 1 (Top Left) - FIXED: Callback Synchronization
# ==============================================================================
class SimpleSportsMiniBar(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        
        # RAM Path
        self.logo_path = "/tmp/simplysports/logos/"
        if not os.path.exists(self.logo_path):
            try: os.makedirs(self.logo_path)
            except: pass

        # UCL Broadcast Band Style (matching GoalToast)
        # Transparent bg, metallic band, large logos at edges
        self.skin = (
            u'<screen position="center,10" size="950,120" title="Sports Ticker" flags="wfNoBorder" backgroundColor="#FF000000">'

            # --- LEAGUE INFO (centered over/under score box) ---
            # Logo centered at top (Score box X=400, Width=150 -> Center=475. Logo=30W -> X=460)
            u'<widget name="l_logo" position="460,5" size="30,30" alphatest="blend" scale="1" zPosition="3" />'
            # League Name after Logo (460 + 30 + 10 = 500)
            u'<widget name="lbl_league" position="500,5" size="400,30" font="Regular;19" '
            u'foregroundColor="#00FFFFFF" backgroundColor="#FF000000" transparent="1" valign="center" halign="left" zPosition="3" />'
            # Status centered under score box (Score box Y=42, Height=38 -> Bottom=80. Under=85?)
            u'<widget name="lbl_status" position="400,85" size="150,30" font="Regular;19" '
            u'foregroundColor="#00E60000" backgroundColor="#FF000000" transparent="1" valign="center" halign="center" zPosition="3" />'

            # --- METALLIC BAND (y=40, total band height = 42) ---
            # Top bright edge (metallic highlight)
            u'<eLabel position="0,40" size="950,2" backgroundColor="#00506888" zPosition="2" />'
            # Main band body (steel blue)
            u'<eLabel position="0,42" size="950,38" backgroundColor="#002C4060" zPosition="2" />'
            # Bottom dark edge (shadow)
            u'<eLabel position="0,80" size="950,2" backgroundColor="#00162030" zPosition="2" />'
            # Bottom accent line
            u'<eLabel position="0,82" size="950,2" backgroundColor="#0000BB55" zPosition="3" />'

            # --- SCORE CENTER BOX (dark recessed area in band) ---
            u'<eLabel position="400,42" size="150,38" backgroundColor="#00142030" zPosition="3" />'
            u'<widget name="lbl_score" position="400,42" size="150,38" font="Regular;26" '
            u'foregroundColor="#00FFFFFF" backgroundColor="#00142030" valign="center" halign="center" zPosition="4" />'

            # --- TEAM NAMES (inside the band) ---
            u'<widget name="lbl_home" position="100,42" size="275,38" font="Regular;32" '
            u'foregroundColor="#00FFFFFF" backgroundColor="#002C4060" valign="center" halign="right" zPosition="4" />'
            u'<widget name="lbl_away" position="572,42" size="278,38" font="Regular;32" '
            u'foregroundColor="#00FFFFFF" backgroundColor="#002C4060" valign="center" halign="left" zPosition="4" />'

            # --- LARGE LOGOS (overlapping band at edges) ---
            u'<widget name="h_logo" position="5,18" size="85,85" alphatest="blend" scale="1" zPosition="6" />'
            u'<widget name="a_logo" position="860,18" size="85,85" alphatest="blend" scale="1" zPosition="6" />'

            # (League and Status moved above band)

            # --- RED CARD INDICATORS (between name and score box) ---
            u'<widget name="h_rc" position="392,50" size="16,22" alphatest="blend" scale="1" zPosition="5" />'
            u'<widget name="h_rc_txt" position="385,50" size="30,22" font="Regular;16" '
            u'foregroundColor="#00FF3333" backgroundColor="#FF000000" transparent="1" valign="center" halign="center" zPosition="5" />'
            u'<widget name="a_rc" position="552,50" size="16,22" alphatest="blend" scale="1" zPosition="5" />'
            u'<widget name="a_rc_txt" position="550,50" size="30,22" font="Regular;16" '
            u'foregroundColor="#00FF3333" backgroundColor="#FF000000" transparent="1" valign="center" halign="center" zPosition="5" />'

            u'</screen>'
        )

        self["lbl_league"] = Label("")
        self["lbl_home"] = Label("")
        self["lbl_score"] = Label("")
        self["lbl_away"] = Label("")
        self["lbl_status"] = Label("")
        
        self["h_rc"] = Pixmap()
        self["h_rc_txt"] = Label("")
        self["a_rc"] = Pixmap()
        self["a_rc_txt"] = Label("")
        self["h_rc"].hide()
        self["h_rc_txt"].hide()
        self["a_rc"].hide()
        self["a_rc_txt"].hide()
        
        self["h_logo"] = Pixmap()
        self["a_logo"] = Pixmap()
        self["l_logo"] = Pixmap()
        self["h_logo"].hide()
        self["a_logo"].hide()
        self["l_logo"].hide()
        
        self.matches = []
        self.current_match_idx = 0
        self.rc_pixmap = None
        try:
            rc_path = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/red.jpg")
            if os.path.exists(rc_path) and LoadPixmap:
                self.rc_pixmap = LoadPixmap(cached=True, path=rc_path)
        except: pass
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close,
            "green": self.switch_to_bottom, 
            "yellow": self.toggle_filter_mini
        }, -1)
        
        self.ticker_timer = eTimer()
        safe_connect(self.ticker_timer, self.show_next_match)
        
        self.refresh_timer = eTimer()
        safe_connect(self.refresh_timer, self.refresh_data)
        
        # 1. Register for Data Updates
        global_sports_monitor.register_callback(self.on_data_ready)
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
        # ENSURE: single_shot=False (2nd param) for repeating update
        self.refresh_timer.start(60000 + random.randint(0, 15000), False)
        # Also ensure ticker timer is running
        if not self.ticker_timer.isActive():
            self.ticker_timer.start(5000, False)

    def on_data_ready(self, success, force_refresh=False):
        # This is called AUTOMATICALLY when Monitor finishes downloading
        self.parse_json()

    def switch_to_bottom(self):
        self.close("next")

    def toggle_filter_mini(self): 
        global_sports_monitor.toggle_filter()
        # Trigger reload to apply filter
        self.parse_json()
            
    def refresh_data(self): 
        global_sports_monitor.check_goals(from_ui=True)

    def get_scorers_string(self, event, home_id, away_id):
        h_el = []; a_el = []
        try:
            details = event.get('competitions', [{}])[0].get('details', [])
            if not details: details = event.get('header', {}).get('competitions', [{}])[0].get('details', [])
            if details:
                for play in details:
                    text_desc = play.get('type', {}).get('text', '').lower()
                    
                    # 1. Check for Red Cards
                    is_rc = play.get('redCard', False) or ('card' in text_desc and 'red' in text_desc)
                    if is_rc:
                        rc_ath = play.get('athletesInvolved', [])
                        if not rc_ath: rc_ath = play.get('participants', [])
                        if rc_ath:
                            rc_name = rc_ath[0].get('shortName') or rc_ath[0].get('displayName', '')
                            if rc_name:
                                t_id = str(play.get('team', {}).get('id', ''))
                                rc_str = "|RC| " + rc_name
                                if t_id == str(home_id) and rc_str not in h_el: h_el.append(rc_str)
                                elif t_id == str(away_id) and rc_str not in a_el: a_el.append(rc_str)

                    # 2. Check for Goals
                    is_scoring = play.get('scoringPlay', False) or "goal" in text_desc or "score" in text_desc or "touchdown" in text_desc
                    if is_scoring and "disallowed" not in text_desc:
                        scorer = ""
                        athletes = play.get('athletesInvolved', [])
                        if athletes: scorer = athletes[0].get('shortName') or athletes[0].get('displayName')
                        elif play.get('participants'): scorer = play['participants'][0].get('athlete', {}).get('shortName')
                        
                        if not scorer:
                            clean = play.get('type', {}).get('text', '')
                            if "Goal - " in clean: scorer = clean.split("Goal - ")[1].split('(')[0].strip()
                            elif "Gamewinner - " in clean: scorer = clean.split("Gamewinner - ")[1].split('(')[0].strip()
                            elif "Short Handed Goal - " in clean: scorer = clean.split("Short Handed Goal - ")[1].split('(')[0].strip()
                            elif "Power Play Goal - " in clean: scorer = clean.split("Power Play Goal - ")[1].split('(')[0].strip()
                        
                        if scorer:
                            # (G) is redundant, only show (P)enalty or (O)wn Goal
                            goal_type = ""
                            if "penalty" in text_desc: goal_type = " (P)"
                            elif "own" in text_desc: goal_type = " (O)"
                            
                            g_time = play.get('clock', {}).get('displayValue', '')
                            if g_time: 
                                scorer = "{}{}{} {}".format(scorer, goal_type, "", g_time).replace("  ", " ")
                            else: 
                                scorer = "{}{}".format(scorer, goal_type)
                            
                            t_id = str(play.get('team', {}).get('id', ''))
                            if t_id == str(home_id): h_el.append(scorer)
                            elif t_id == str(away_id): a_el.append(scorer)
        except: pass
        
        def format_list(lst):
            if not lst: return ""
            goals = [x for x in lst if "|RC|" not in x]
            rcs = [x for x in lst if "|RC|" in x]
            
            seen_g = set(); unique_g = [x for x in goals if not (x in seen_g or seen_g.add(x))]
            g_str = ", ".join(unique_g)
            if len(g_str) > 30: 
                short_g = []
                for n in unique_g:
                    parts = n.split(' ')
                    if len(parts) >= 3:
                        short_g.append("{} {} {}".format(parts[-3], parts[-2], parts[-1]))
                    else: short_g.append(n)
                g_str = ", ".join(short_g)
            
            seen_rc = set(); unique_rc = [x for x in rcs if not (x in seen_rc or seen_rc.add(x))]
            rc_str = " ".join(unique_rc)
            return (g_str + " " + rc_str).strip()

        return format_list(h_el), format_list(a_el)

    def parse_json(self):
        events = global_sports_monitor.cached_events
        new_matches = []
        
        # If Monitor is empty/loading
        if not events:
            # If we already have matches and an update is in progress, keep old matches to avoid flicker
            if self.matches and "Loading" in global_sports_monitor.status_message:
                return
            msg = global_sports_monitor.status_message or "Loading..."
            self.matches = [{'league': "SimplySports", 'color': 0xffffff, 'home': msg, 'away': "", 'score': "", 'status': "", 'h_url': "", 'a_url': "", 'l_url': "", 'h_id': "", 'a_id': "", 'l_id': ""}]
            self.show_next_match()
            return
            
        mode = global_sports_monitor.filter_mode

        # Pre-compute dates once per render pass
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = datetime.datetime.utcfromtimestamp(calendar.timegm(now.timetuple()) + 86400).strftime("%Y-%m-%d")
        yesterday_str = datetime.datetime.utcfromtimestamp(calendar.timegm(now.timetuple()) - 86400).strftime("%Y-%m-%d")

        for event in events:
            snap = global_sports_monitor.match_snapshots.get(str(event.get('id', '')))
            if not snap: continue
            if not snapshot_passes_filter(snap, mode, today_str, tomorrow_str, yesterday_str): continue

            # Racing events (>2 competitors) -- use event shortName
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            if len(comps) > 2:
                race = event.get('shortName', 'Event')
                venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                match_data = {'league': snap['league_name'], 'home': race, 'away': venue,
                              'score': "VS", 'status': snap['status_short'],
                              'h_url': snap['h_logo_url'], 'a_url': snap['a_logo_url'], 'l_url': snap['l_logo_url'],
                              'h_id': snap['h_logo_id'], 'a_id': snap['a_logo_id'], 'l_id': snap['l_logo_id']}
            else:
                # Build match data from snapshot -- all parsing already done
                h_scorer, a_scorer = self.get_scorers_string(event, snap['h_team_id'], snap['a_team_id'])
                match_data = {
                    'league':  snap['league_name'],
                    'home':    snap['h_name_short'],
                    'away':    snap['a_name_short'],
                    'score':   snap['score_str'],
                    'status':  (snap['status_short'] + ' ' + snap['clock']) if snap['is_live'] and snap['clock'] else (snap['status_short'] + ' ' + snap['time_str'] if snap['state'] == 'pre' and snap['time_str'] else snap['status_short']),
                    'h_url':   snap['h_logo_url'],
                    'a_url':   snap['a_logo_url'],
                    'l_url':   snap['l_logo_url'],
                    'h_id':    snap['h_logo_id'],
                    'a_id':    snap['a_logo_id'],
                    'l_id':    snap['l_logo_id'],
                    'h_red_cards': snap.get('h_red_cards', 0),
                    'a_red_cards': snap.get('a_red_cards', 0),
                    'h_scorer': h_scorer,
                    'a_scorer': a_scorer
                }
            new_matches.append(match_data)
            
        # Handle Filter Empty
        if not new_matches:
            # If we are currently updating, don't show "No Matches Found" yet if we have old data
            if self.matches and ("Loading" in global_sports_monitor.status_message or "Processing" in global_sports_monitor.status_message):
                return
                
            is_stale = (time.time() - global_sports_monitor.last_update) > 300
            msg = "Updating Data..." if is_stale else "No Matches Found"
            sub = "Please Wait" if is_stale else "Check Filters"
            new_matches.append({'league': "SimplySports", 'color': 0xffffff, 'home': msg, 'away': sub, 'score': "", 'status': "", 'h_url': "", 'a_url': "", 'l_url': "", 'h_id': "", 'a_id': "", 'l_id': ""})

        self.matches = new_matches
        if not self.ticker_timer.isActive(): 
            self.show_next_match()
            self.ticker_timer.start(5000, False)

    def show_next_match(self):
        if not self.matches: return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matches)
        data = self.matches[self.current_match_idx]
        
        # 1. Prepare status
        status_text = str(data.get('status', ''))
            
        self["lbl_status"].setText(status_text)
        self["lbl_league"].setText(str(data.get('league', '')))
        self["lbl_home"].setText(str(data.get('home', '')))
        self["lbl_score"].setText(str(data.get('score', '')))
        self["lbl_away"].setText(str(data.get('away', '')))
        
        
        self.load_logo(data.get('h_url'), data.get('h_id'), "h_logo")
        self.load_logo(data.get('a_url'), data.get('a_id'), "a_logo")
        self.load_logo(data.get('l_url'), data.get('l_id'), "l_logo")
        
        # Red Card Indicators
        h_rc = data.get('h_red_cards', 0)
        a_rc = data.get('a_red_cards', 0)
        
        # Try to load red card image
        rc_pixmap = self.rc_pixmap
        
        if h_rc > 0:
            if rc_pixmap:
                try:
                    self["h_rc"].instance.setPixmap(rc_pixmap)
                    self["h_rc"].instance.setScale(1)
                except: pass
                self["h_rc"].show()
                self["h_rc_txt"].hide()
            else:
                rc_txt = "RC" if h_rc == 1 else "{}RC".format(h_rc)
                self["h_rc_txt"].setText(rc_txt)
                self["h_rc_txt"].show()
                self["h_rc"].hide()
        else:
            self["h_rc"].hide()
            self["h_rc_txt"].hide()
        
        if a_rc > 0:
            if rc_pixmap:
                try:
                    self["a_rc"].instance.setPixmap(rc_pixmap)
                    self["a_rc"].instance.setScale(1)
                except: pass
                self["a_rc"].show()
                self["a_rc_txt"].hide()
            else:
                rc_txt = "RC" if a_rc == 1 else "{}RC".format(a_rc)
                self["a_rc_txt"].setText(rc_txt)
                self["a_rc_txt"].show()
                self["a_rc"].hide()
        else:
            self["a_rc"].hide()
            self["a_rc_txt"].hide()

        # Scorer & Scorer Red Cards
        h_sc_text = data.get('h_scorer', '')
        a_sc_text = data.get('a_scorer', '')
        
        def render_scorer_rc(widget_sc, widget_rc, widget_rctxt, text):
            if not text:
                widget_sc.setText("")
                widget_rc.hide()
                widget_rctxt.hide()
                return

            if "|RC|" in text:
                parts = text.split("|RC|")
                sc_part = parts[0].strip()
                rc_part = ", ".join([p.strip() for p in parts[1:] if p.strip()])
                widget_sc.setText(sc_part)
                
                if rc_pixmap:
                    try:
                        widget_rc.instance.setPixmap(rc_pixmap)
                        widget_rc.instance.setScale(1)
                    except: pass
                    widget_rc.show()
                else: widget_rc.hide()
                
                widget_rctxt.setText(rc_part)
                widget_rctxt.show()
            else:
                widget_sc.setText(text)
                widget_rc.hide()
                widget_rctxt.hide()
        try:
            render_scorer_rc(self["lbl_home_sc"], self["h_sc_rc"], self["h_sc_rctxt"], h_sc_text)
            render_scorer_rc(self["lbl_away_sc"], self["a_sc_rc"], self["a_sc_rctxt"], a_sc_text)
        except KeyError:
            pass

    def load_logo(self, url, img_id, widget_name):
        """Delegate to shared logo loader (unified cache + pixmap memory cache)"""
        load_logo_to_widget(self, widget_name, url, img_id)





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
    if isinstance(text, bytes):
        try: text = text.decode('utf-8', 'ignore')
        except: text = ""
    
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

class SimpleSportsScreen(Screen):
    @profile_function("SimpleSportsScreen")
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.monitor = global_sports_monitor
        self.logo_path = "/tmp/simplysports/logos/"
        if not os.path.exists(self.logo_path):
            try: os.makedirs(self.logo_path)
            except: pass

        self.active_downloads = set()
        
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
        # Evaluate Theme Mode
        if self.monitor.theme_mode == "ucl":
            bg_base = "0e1e5b"; top_base = "050a2e"
            c_bg = "#" + self.current_alpha + bg_base; c_top = "#" + self.current_alpha + top_base
            bg_widget = '<widget name="main_bg" position="0,0" size="1920,1080" backgroundColor="{c_bg}" zPosition="-1" />'.format(c_bg=c_bg)
            try:
                path_jpg = os.path.join(os.path.dirname(__file__), "ucl.jpg")
                if os.path.exists(path_jpg): 
                    bg_widget = '<ePixmap position="0,0" size="1920,1080" pixmap="{}" zPosition="-1" alphatest="on" scale="1" />'.format(path_jpg)
                else: # Fallback
                    path_jpg = resolveFilename(SCOPE_PLUGINS, "Extensions/SimplySports/ucl.jpg")
                    if os.path.exists(path_jpg): 
                        bg_widget = '<ePixmap position="0,0" size="1920,1080" pixmap="{}" zPosition="-1" alphatest="on" scale="1" />'.format(path_jpg)
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
        
        # Logo Refresh Timer (Batched UI updates)
        self.logo_refresh_timer = eTimer()
        safe_connect(self.logo_refresh_timer, self.refresh_logos_only)
        
        log_dbg("SimpleSportsScreen: Registering ActionMap...")
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "MenuActions", "EPGSelectActions", "InfobarEPGActions", "InfobarActions", "GlobalActions"], 
            {
                "cancel": self.close, 
                "red": self.open_league_menu, 
                "green": self.open_mini_bar, 
                "yellow": self.toggle_filter, 
                "blue": self.toggle_discovery, 
                "ok": self.open_game_info, 
                "menu": self.open_settings_menu, 
                "up": self["list"].up, 
                "down": self["list"].down, 
                "info": self.open_broadcasting, 
                "epg": self.open_broadcasting,
                "guide": self.open_broadcasting,
                "event": self.open_broadcasting,
                "showEventInfo": self.open_broadcasting
            }, -1)
        log_dbg("SimpleSportsScreen: ActionMap Registered")
        
        self.container = eConsoleAppContainer(); self.container.appClosed.append(self.download_finished)
        global_sports_monitor.set_session(session)
        self.monitor.register_callback(self.refresh_ui)
        self.onLayoutFinish.append(self.start_ui); self.onClose.append(self.cleanup)

    def update_clock(self):
        """Update clock display with current time"""
        try:
            from datetime import datetime
            now = datetime.now()
            self["clock"].setText(now.strftime("%H:%M"))
            # log_diag("UPDATE_CLOCK: " + now.strftime("%H:%M"))
        except: pass

    def start_ui(self):
        log_diag("SCREEN.start_ui: is_custom={} filter_mode={} discovery_mode={} active={}".format(
            self.monitor.is_custom_mode, self.monitor.filter_mode, self.monitor.discovery_mode, self.monitor.active))
        self.update_clock()  # Initial clock update
        # ENSURE: single_shot=False (2nd param) for repeating update
        self.clock_timer.start(1000, False)  # Update every second
        # Clear list immediately to prevent stale cache flash from previous session
        self["list"].setList([])
        self["list_title"].setText("Loading...")
        self.update_header(); self.update_filter_button(); self.fetch_data()
    def cleanup(self): 
        self.clock_timer.stop()
        self.logo_refresh_timer.stop()
        self.monitor.unregister_callback(self.refresh_ui)
    
    # ... (Keep Header, Filter, Download helpers unchanged) ...
    def update_header(self):
        if self.monitor.is_custom_mode: self["league_title"].setText("Custom League View")
        else:
            try: item = DATA_SOURCES[self.monitor.current_league_index]; self["league_title"].setText(item[0])
            except: pass
        mode = self.monitor.filter_mode
        if mode == 0: self["list_title"].setText("Yesterday's Matches")
        elif mode == 1: self["list_title"].setText("Live Matches")
        elif mode == 2: self["list_title"].setText("Today's Matches")
        elif mode == 3: self["list_title"].setText("Tomorrow's Matches")
        elif mode == 4: self["list_title"].setText("All Matches")
        # Green button: show 'Driver Position' for racing, 'Mini Bar' otherwise
        try:
            if not self.monitor.is_custom_mode:
                url = DATA_SOURCES[self.monitor.current_league_index][1]
                if get_sport_type(url) == SPORT_TYPE_RACING:
                    self["key_green"].setText("Driver Position")
                else:
                    self["key_green"].setText("Mini Bar")
            else:
                self["key_green"].setText("Mini Bar")
        except: self["key_green"].setText("Mini Bar")
        d_mode = self.monitor.discovery_mode
        if d_mode == 0: self["key_blue"].setText("Goal Alert: OFF")
        elif d_mode == 1: self["key_blue"].setText("Goal Alert: VISUAL")
        elif d_mode == 2: self["key_blue"].setText("Goal Alert: SOUND")
    def update_filter_button(self): 
        mode = self.monitor.filter_mode
        if mode == 0: self["key_yellow"].setText("Live Only")
        elif mode == 1: self["key_yellow"].setText("Show Today")
        elif mode == 2: self["key_yellow"].setText("Show Tomorrow")
        elif mode == 3: self["key_yellow"].setText("Show All")
        elif mode == 4: self["key_yellow"].setText("Yesterday")
        self.update_header()
    def fetch_data(self): self.monitor.check_goals(from_ui=True)
    
    @profile_function("SimpleSportsScreen")
    def get_logo_path(self, url, team_id):
        """Get logo path using team ID naming (aligned with GameInfoScreen approach)"""
        if not url: return None
        
        # Fallback ID generation if missing (e.g. some tennis players)
        if not team_id:
             import hashlib
             # Create a short hash of the URL to use as ID
             team_id = hashlib.md5(url.encode('utf-8')).hexdigest()[:10]
        
        # Fast Success Bypass
        if team_id in self.monitor.logo_path_cache: return self.monitor.logo_path_cache[team_id]
        
        # CRITICAL FIX: Negative Cache bypass. If OS lacks graphic, skip the system call entirely!
        if team_id in self.monitor.missing_logo_cache: return None
        
        target_path = self.logo_path + str(team_id) + ".png"
        
        # Fast Set Bypass
        if target_path in GLOBAL_VALID_LOGO_PATHS:
            self.monitor.logo_path_cache[team_id] = target_path
            return target_path
            
        # The ultimate heavy fallback. Only executes precisely ONE time per missing image!
        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            GLOBAL_VALID_LOGO_PATHS.add(target_path)
            self.monitor.logo_path_cache[team_id] = target_path
            return target_path
        
        # It's officially missing - track it so we never stall checking the disk for it again
        self.monitor.missing_logo_cache.add(team_id)
        
        # Queue download if not cached
        self.queue_download(url, target_path, team_id)
        return None

    def queue_download(self, url, target_path, filename):
        if filename in self.active_downloads or filename in self.monitor.pending_logos: return
        # Check if recently failed
        if hasattr(self, 'failed_downloads') and filename in self.failed_downloads: return
        
        # Limit concurrent downloads to prevent network congestion
        MAX_CONCURRENT = 5
        if len(self.active_downloads) >= MAX_CONCURRENT:
            # Add to pending queue - will be processed when current downloads finish
            if not hasattr(self, 'pending_downloads'): self.pending_downloads = []
            
            # CRITICAL FIX: Prevent duplicate pending entries
            for i in range(len(self.pending_downloads)):
                if self.pending_downloads[i][2] == filename:
                    return # Already pending
            
            self.pending_downloads.append((url, target_path, filename))
            return
        self.active_downloads.add(filename)
        from twisted.web.client import downloadPage
        downloadPage(url.encode('utf-8'), target_path).addCallback(self.download_finished, filename, target_path).addErrback(self.download_failed, filename)

    def download_finished(self, data, filename, target_path):
        self.active_downloads.discard(filename)
        self.monitor.missing_logo_cache.discard(filename)
        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            GLOBAL_VALID_LOGO_PATHS.add(target_path)
            self.monitor.logo_path_cache[filename] = target_path
            # Batch UI updates - wait for more downloads before refreshing
            if not self.logo_refresh_timer.isActive(): self.logo_refresh_timer.start(1500, True)
        # Process pending downloads
        self._process_pending_downloads()

    def download_failed(self, error, filename):
        self.active_downloads.discard(filename)
        # Track failures to prevent infinite retry loops
        # Use a short-lived cache or persistent set? Persistent for session is safest.
        if not hasattr(self, 'failed_downloads'): self.failed_downloads = set()
        self.failed_downloads.add(filename)
        
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
        log_dbg("open_broadcasting called. Forced Event: {}".format(forced_event is not None))
        target_event = forced_event
        selected_id = None
        
        if not target_event:
            idx = self["list"].getSelectedIndex()
            log_dbg("open_broadcasting: List Index = {}".format(idx))
            if idx is None or idx < 0 or idx >= len(self.current_match_ids): 
                log_dbg("open_broadcasting: Invalid Index or ID list empty")
                return
            selected_id = self.current_match_ids[idx]
            log_dbg("open_broadcasting: Selected ID = {}".format(selected_id))

        # Re-find event or process target
        events_to_scan = [target_event] if target_event else self.monitor.cached_events
        log_dbg("open_broadcasting: Scanning {} events...".format(len(events_to_scan)))
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
                # FIX: Check both numeric ID (from API) and name-based MID (legacy/backup)
                ev_id = str(event.get('id', ''))
                if target_event or ev_id == str(selected_id) or mid == selected_id:
                    if not target_event: target_event = event
                    # Extract names and Time for Smart Search
                    log_dbg("open_broadcasting: Match Found. Search Terms: Home='{}', Away='{}'".format(epg_home, epg_away))
                    self.search_and_display_epg(epg_home, epg_away, epg_league, match_time_ts)
                    return
            except: continue
        log_dbg("open_broadcasting: No matching event found in cache for ID: {}".format(selected_id))

    def search_and_display_epg(self, home, away, league, match_time_ts):
        from Screens.MessageBox import MessageBox
        import os
        from enigma import eServiceReference, eEPGCache
        
        epg = eEPGCache.getInstance()
        if not epg: 
            log_dbg("search_and_display_epg: CRITICAL - eEPGCache instance missing")
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
        
        log_dbg("search_and_display_epg: Service Cache Size = {}".format(len(self.service_cache) if self.service_cache else 0))

        if not self.service_cache:
             self.session.open(MessageBox, "No channels found in bouquets.", MessageBox.TYPE_INFO)
             return

        c_count = len(self.service_cache)
        
        # --- DIAGNOSTIC: Safe Probe (Multi-Channel + Time) ---
        probe_result = "Skipped (No valid ch)"
        sys_time_str = "Unknown"
        if c_count > 0:
            try:
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

        from twisted.internet import threads

        def _bg_search(services, m_time, h_words, a_words, l_words):
            bg_results = []
            search_offsets = [900, 0, 3600, -900]
            now = int(time.time())
            use_fallback_now = True
            
            if m_time > (now + 21600):
                use_fallback_now = False

            for sref_str, s_info in services.items():
                sref_raw = s_info[0]
                ch_name = s_info[1]
                try:
                    evt = None
                    sref_obj = eServiceReference(sref_raw)
                    
                    for offset in search_offsets:
                        probe_time = m_time + offset
                        candidate = epg.lookupEventTime(sref_obj, probe_time)
                        if candidate:
                            evt = candidate
                            break
                    
                    if not evt and use_fallback_now:
                         if abs(m_time - now) < 7200:
                             evt = epg.lookupEventTime(sref_obj, now)
                    
                    if not evt and (sref_raw.startswith("4097:") or sref_raw.startswith("5001:")):
                        parts = sref_raw.split(':')
                        if len(parts) > 10:
                            dvb_ref_str = "1:0:1:%s:%s:%s:%s:0:0:0" % (parts[3], parts[4], parts[5], parts[6])
                            dvb_obj = eServiceReference(dvb_ref_str)
                            for offset in search_offsets:
                                probe_time = m_time + offset
                                evt = epg.lookupEventTime(dvb_obj, probe_time)
                                if evt: break
                            if not evt and use_fallback_now and abs(m_time - now) < 7200:
                                evt = epg.lookupEventTime(dvb_obj, now)

                    if evt:
                        title = evt.getEventName() or ""
                        desc = evt.getShortDescription() or ""
                        ext = evt.getExtendedDescription() or "" 
                        
                        blob = normalize_text(title + " " + desc + " " + ext + " " + ch_name)
                        
                        STOP_WORDS = ['al', 'el', 'the', 'fc', 'sc', 'fk', 'sk', 'club', 'sport', 'sports', 'vs', 'live', 'hd', 'fhd', '4k', 'uhd']
                        
                        def match_sig_score(keywords, text_blob, require_all=True):
                            sig = [w for w in keywords if w not in STOP_WORDS and len(w) > 1]
                            if not sig: sig = keywords 
                            
                            found_count = 0
                            for w in sig:
                                if w in text_blob: found_count += 1
                            
                            return found_count, len(sig)

                        h_found, h_total = match_sig_score(h_words, blob)
                        a_found, a_total = match_sig_score(a_words, blob) if a_words else (0, 0)
                        l_found, l_total = match_sig_score(l_words, blob)
                        
                        h_ratio = h_found / float(h_total) if h_total > 0 else 0.0
                        a_ratio = a_found / float(a_total) if a_total > 0 else 0.0
                        l_ratio = l_found / float(l_total) if l_total > 0 else 0.0
                        
                        score = 0.0
                        score += (h_ratio * 40)
                        score += (a_ratio * 40)
                        score += (l_ratio * 20)
                        
                        if h_ratio == 1.0: score += 10
                        if a_ratio == 1.0: score += 10
                        if h_ratio == 1.0 and (a_ratio == 1.0 or not a_words): score += 30
                        score += (h_found + a_found + l_found)

                        try:
                            evt_start = evt.getBeginTime()
                            diff_min = abs(evt_start - m_time) / 60.0
                            
                            if diff_min <= 15: score += 20     
                            elif diff_min <= 45: score += 10   
                            elif diff_min <= 90: score += 5    
                            elif diff_min > 120: score -= 15   
                        except: diff_min = 999
                        
                        valid_match = False
                        if h_ratio == 1.0 and (a_ratio == 1.0 or not a_words): valid_match = True
                        elif h_ratio >= 0.5 and a_ratio >= 0.5: valid_match = True 
                        elif (h_ratio == 1.0 or a_ratio == 1.0) and l_ratio >= 0.5: valid_match = True 
                        
                        if valid_match and score > 40:
                            cat_color = 0xffffff
                            if score >= 100: cat_color = 0x00FF00    
                            elif score >= 80: cat_color = 0xFFFF00   
                            
                            sat_pos = get_sat_position(sref_raw)
                            full_name = ch_name + ((" (" + sat_pos + ")") if sat_pos else "")
                            time_info = "T+0" if diff_min < 1 else "T-%d" % int(diff_min) if evt_start < m_time else "T+%d" % int(diff_min)
                            display_title = "[%d|%s] %s" % (int(score), time_info, title)
                            bg_results.append((sref_raw, full_name, display_title, cat_color, score))
                except: pass

            bg_results.sort(key=lambda x: x[4], reverse=True)
            return [ (r[0], r[1], r[2], r[3]) for r in bg_results[:200] ]

        def _on_search_done(final_list):
            if final_list:
                self.session.open(BroadcastingChannelsScreen, final_list, match_time_ts=match_time_ts)
            else:
                 self.session.open(MessageBox, "No EPG matches found.\n\nChecked for:\n%s\n%s\nIn League: %s" % (home, away, league), MessageBox.TYPE_INFO)

        # Execute heavy loop in background thread to prevent UI lockup
        threads.deferToThread(_bg_search, unique_services, match_time_ts, h_norm, a_norm, l_norm).addCallback(_on_search_done)

    def refresh_logos_only(self):
        """Lightweight redraw of existing list items to pop in newly downloaded logos without rebuilding the list array."""
        if self.shown:
            self["list"].l.invalidate()

    @profile_function("SimpleSportsScreen")
    def refresh_ui(self, success, force_refresh=False):
        log_diag("REFRESH_UI: success={} force={} filter_mode={} is_custom={} cached_events={} status='{}'".format(
            success, force_refresh, self.monitor.filter_mode, self.monitor.is_custom_mode, len(self.monitor.cached_events), self.monitor.status_message))
        # Guard: Don't refresh UI during loading states UNLESS forced
        if not success and not force_refresh:
            log_diag("REFRESH_UI: SKIPPED (not success, not forced)")
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

        if not events:
            # If we already have matches and loading is in progress, keep old list to avoid flicker
            if self.current_match_ids and ("Loading" in self.monitor.status_message or "Fetching" in self.monitor.status_message):
                log_diag("REFRESH_UI: SKIPPED (loading in progress, keeping old data)")
                return
            log_diag("REFRESH_UI: No events - showing '{}'".format(self.monitor.status_message or 'No Matches Found'))
            msg = self.monitor.status_message or "No Matches Found"
            dummy_entry = ("INFO", "", msg, "", "", "", False, "", None, None, 0, 0, False, 0x202020, "")
            if self.monitor.theme_mode == "ucl": self["list"].setList([UCLListEntry(dummy_entry)])
            else: self["list"].setList([SportListEntry(dummy_entry)])
            self.current_match_ids = []
            return
            
        mode = self.monitor.filter_mode
        raw_entries = []  # Store (entry_data, match_id, is_live) for sorting
        
        # Pre-compute dates once per render pass
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = datetime.datetime.utcfromtimestamp(calendar.timegm(now.timetuple()) + 86400).strftime("%Y-%m-%d")
        yesterday_str = datetime.datetime.utcfromtimestamp(calendar.timegm(now.timetuple()) - 86400).strftime("%Y-%m-%d")
    
        for event in events:
            try:
                snap = self.monitor.match_snapshots.get(str(event.get('id', '')))
                if not snap: continue
                if not snapshot_passes_filter(snap, mode, today_str, tomorrow_str, yesterday_str): continue

                # Racing: Only show in single-league mode, skip in custom/multi-league
                if snap['sport_type'] == SPORT_TYPE_RACING and self.monitor.is_custom_mode: continue

                # Logo paths from shared cache
                h_png = self.get_logo_path(snap['h_logo_url'], snap['h_logo_id'])
                a_png = self.get_logo_path(snap['a_logo_url'], snap['a_logo_id'])
                l_png = self.get_logo_path(snap['l_logo_url'], snap['l_logo_id'])

                comps = event.get('competitions', [{}])[0].get('competitors', [])
                is_racing_event = (snap['sport_type'] == SPORT_TYPE_RACING) or (len(comps) > 2)

                if is_racing_event:
                    # Racing: Enhanced row with race name, track, status
                    race_name = event.get('shortName', '') or event.get('name', 'Race')
                    track_info = ''
                    try:
                        circuit = event.get('circuit', {})
                        if circuit:
                            track_name = circuit.get('fullName', '')
                            addr = circuit.get('address', {})
                            city = addr.get('city', '')
                            country = addr.get('country', '')
                            loc_parts = [p for p in [city, country] if p]
                            if track_name and loc_parts:
                                track_info = "{} - {}".format(track_name, ", ".join(loc_parts))
                            elif track_name:
                                track_info = track_name
                            elif loc_parts:
                                track_info = ", ".join(loc_parts)
                        if not track_info:
                            comp_venue = event.get('competitions', [{}])[0].get('venue', {})
                            track_info = comp_venue.get('fullName', '') or comp_venue.get('address', {}).get('city', '')
                    except: pass
                    left_text = race_name
                    right_text = track_info if track_info else 'Event'
                    score_text = ""; goal_side = None; is_live = False
                    display_time = snap['time_str']
                    h_score_int = 0; a_score_int = 0
                    
                    # Determine overall event status from most recent active session
                    all_comps = event.get('competitions', [])
                    has_live_session = False
                    has_finished_session = False
                    for comp in all_comps:
                        comp_state = comp.get('status', {}).get('type', {}).get('state', 'pre')
                        if comp_state == 'in': has_live_session = True
                        elif comp_state == 'post': has_finished_session = True
                    
                    if has_live_session:
                        score_text = "LIVE"; is_live = True; display_time = "LIVE"
                    elif has_finished_session:
                        # Check if all sessions are done or just some
                        all_done = all(c.get('status', {}).get('type', {}).get('state', 'pre') == 'post' for c in all_comps)
                        if all_done:
                            score_text = "FIN"
                        else:
                            score_text = "ONGOING"
                    
                    match_id = snap['event_id']
                else:
                    # Team/Tennis/Combat: Read all data from snapshot
                    def truncate_name(name, max_len=25):
                        if len(name) > max_len: return name[:max_len-2] + ".."
                        return name

                    left_text = truncate_name(snap['h_name'])
                    right_text = truncate_name(snap['a_name'])
                    score_text = snap['score_str']
                    h_score_int = snap['h_score_int']
                    a_score_int = snap['a_score_int']
                    is_live = snap['is_live']
                    display_time = snap['time_str']
                    match_id = snap['event_id']
                    goal_side = self.monitor.goal_flags.get(match_id, {}).get('team')

                status_short = snap['status_short']

                has_epg = False
                # Check for recent goals to create a 'heat' effect on the score box
                c_score_bg = 0x202020 if self.monitor.theme_mode != "ucl" else 0x051030
                if snap['state'] == 'in' and match_id in self.monitor.goal_flags:
                    goal_time = self.monitor.goal_flags[match_id].get('time', 0)
                    time_since_goal = time.time() - goal_time
                    
                    if time_since_goal <= 300: # 5 minutes
                        total_goals = h_score_int + a_score_int
                        
                        # Base color and target hot color sets based on total goals
                        if total_goals >= 5: # Extremely hot (lots of goals)
                            start_color = [204, 51, 0] # #CC3300 (Deep Red-Orange)
                        elif total_goals >= 3: # Hot
                            start_color = [170, 85, 0] # #AA5500 (Orange)
                        else: # Warm (1-2 goals)
                            start_color = [136, 34, 0] # #882200 (Dark Orange)
                            
                        # Fade progress (0.0 = just scored, 1.0 = 5 minutes ago)
                        progress = time_since_goal / 300.0
                        
                        # Target base color (cool)
                        end_color = [32, 32, 32] if self.monitor.theme_mode != "ucl" else [5, 16, 48]
                        
                        # Interpolate
                        r = int(start_color[0] + (end_color[0] - start_color[0]) * progress)
                        g = int(start_color[1] + (end_color[1] - start_color[1]) * progress)
                        b = int(start_color[2] + (end_color[2] - start_color[2]) * progress)
                        
                        # Convert back to hex
                        c_score_bg = (r << 16) | (g << 8) | b

                entry_data = (status_short, get_league_abbr(snap['league_name']), str(left_text), str(score_text), str(right_text), str(display_time), goal_side, is_live, h_png, a_png, h_score_int, a_score_int, has_epg, c_score_bg, l_png, snap.get('h_red_cards', 0), snap.get('a_red_cards', 0))

                # Store raw data for sorting (include event for excitement calculation)
                raw_entries.append((entry_data, match_id, is_live, event))
            except Exception as e:
                with open("/tmp/simplysport_render_error.log", "a") as err_log:
                    err_log.write("Error in refresh_ui loop at %s: %s\n" % (datetime.datetime.now(), str(e)))
                continue
        # Sort: LIVE matches by excitement (highest first), then FIN, then SCH
        # AND Priority for SOCCER within each group
        def sort_key(item):
            entry_data, match_id, is_live, event = item
            status = entry_data[0] # status_short is index 0
            
            # Football Priority: 0=Soccer, 1=Others
            l_url = event.get('league_url', '')
            sport_prio = 0 if 'soccer' in l_url else 1
            
            if status == "LIVE":
                excitement = self.monitor.calculate_excitement(event)
                return (0, sport_prio, -excitement)
            elif status == "FIN":
                return (1, sport_prio, 0)
            else:
                return (2, sport_prio, 0) # SCH
        
        raw_entries.sort(key=sort_key)
        
        # Convert to list entries after sorting
        list_content = []
        new_match_ids = []
        for entry_data, match_id, is_live, event in raw_entries:
            # Use RacingListEntry for racing events
            ev_url = event.get('league_url', '')
            if get_sport_type(ev_url) == SPORT_TYPE_RACING:
                # Header row (event name + circuit + overall status)
                list_content.append(RacingListEntry(entry_data, self.monitor.theme_mode))
                new_match_ids.append(match_id)
                
                # Iterate ALL sessions (FP1, FP2, FP3, Qual, Race, Sprint etc.)
                all_competitions = event.get('competitions', [])
                for comp_idx, comp in enumerate(all_competitions):
                    sess_type = comp.get('type', {}).get('abbreviation', 'Session {}'.format(comp_idx + 1))
                    sess_state = comp.get('status', {}).get('type', {}).get('state', 'pre')
                    sess_broadcast = comp.get('broadcast', '')
                    sess_start = comp.get('startDate', '')
                    
                    # Status label for session
                    if sess_state == 'in': sess_status = 'LIVE'
                    elif sess_state == 'post': sess_status = 'FIN'
                    else: sess_status = 'SCH'
                    
                    # Time display
                    sess_time = get_local_time_str(sess_start) if sess_start else ''
                    
                    # Session sub-header row
                    sess_row = RacingSessionRow(sess_type, sess_status, sess_broadcast, sess_time, self.monitor.theme_mode)
                    if sess_row:
                        list_content.append(sess_row)
                        new_match_ids.append(match_id + '_ses_' + str(comp_idx))
                    
                    # For LIVE/FINISHED sessions: expand driver result rows
                    if sess_state in ('in', 'post'):
                        comps_list = comp.get('competitors', [])
                        for drv in comps_list:
                            athlete = drv.get('athlete', {})
                            d_name = athlete.get('displayName', '') or athlete.get('shortName', 'Driver')
                            d_country = athlete.get('flag', {}).get('alt', '')
                            d_winner = drv.get('winner', False)
                            d_rank = drv.get('order', 0)
                            # Get team logo path (cached via get_logo_path mechanism)
                            d_team_logo = None
                            team_obj = drv.get('team', {})
                            team_logo_url = team_obj.get('logo', '')
                            team_id = team_obj.get('id', '')
                            if team_logo_url and team_id:
                                sport_prefix = get_sport_id_prefix(ev_url)
                                d_team_logo = self.get_logo_path(team_logo_url, sport_prefix + str(team_id))
                            row = RacingDriverRow(d_rank, d_name, d_country, d_winner, d_team_logo, self.monitor.theme_mode)
                            if row:
                                list_content.append(row)
                                new_match_ids.append(match_id + '_ses_' + str(comp_idx) + '_drv_' + str(d_rank))
            elif self.monitor.theme_mode == "ucl":
                list_content.append(UCLListEntry(entry_data))
                new_match_ids.append(match_id)
            else:
                list_content.append(SportListEntry(entry_data))
                new_match_ids.append(match_id)
            
        if not list_content: 
            msg = self.monitor.status_message or "No Matches Found"
            dummy_entry = ("INFO", "", msg, "", "", "", False, "", None, None, 0, 0)
            if self.monitor.theme_mode == "ucl": self["list"].setList([UCLListEntry(dummy_entry)])
            else: self["list"].setList([SportListEntry(dummy_entry)])
            self.current_match_ids = []
        else: 
            if getattr(self["list"], "list", None) is not None and self.current_match_ids == new_match_ids and len(self["list"].list) == len(list_content):
                # Optimization: In-place update prevents cursor jumping and UI flickering
                for i in range(len(list_content)):
                    self["list"].list[i] = list_content[i]
                self["list"].l.invalidate()
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
        menu_options = [
            ("Check for Updates", "update"), 
            ("Change Interface Theme", "theme"), 
            ("Mini Bar Style (Default Theme only)", "minibar_color"),
            ("Main Screen Transparency (Default Theme only)", "transparency"), 
            ("Show Plugin in Main Menu: " + in_menu_txt, "toggle_menu"),
            ("Set Voter Name: " + self.monitor.voter_name, "voter_name")
        ]
        self.session.openWithCallback(self.settings_menu_callback, ChoiceBox, title="Settings & Tools", list=menu_options)
    def settings_menu_callback(self, selection):
        if selection:
            action = selection[1]
            if action == "update": self.check_for_updates()
            elif action == "theme": self.open_theme_selector()
            elif action == "minibar_color": self.open_minibar_color_selector()
            elif action == "transparency": self.open_transparency_selector()
            elif action == "toggle_menu":
                self.monitor.show_in_menu = not self.monitor.show_in_menu
                self.monitor.save_config()
                self.session.open(MessageBox, "Setting saved.\nYou must Restart GUI for menu changes to take effect.", MessageBox.TYPE_INFO)
            elif action == "voter_name": self.open_voter_name_input()
    
    def open_voter_name_input(self):
        try:
            from Screens.VirtualKeyBoard import VirtualKeyBoard
            self.session.openWithCallback(self.voter_name_entered, VirtualKeyBoard, title="Enter your SS-Voter name:", text=self.monitor.voter_name)
        except Exception:
            self.session.open(MessageBox, "VirtualKeyBoard not available on this image.", MessageBox.TYPE_ERROR, timeout=3)
    def voter_name_entered(self, text=None):
        if text is not None:
            self.monitor.voter_name = text.strip() or "Anonymous"
            self.monitor.save_config()
            self.session.open(MessageBox, "Voter name saved: " + self.monitor.voter_name, MessageBox.TYPE_INFO, timeout=3)

    def open_minibar_color_selector(self):
        c_options = [
            ("Default", "default"), 
            ("Premier League (Purple/Green)", "pl"), 
            ("Spanish League (Red/Gold)", "laliga"), 
            ("Serie A (Blue/Cyan)", "seriea"),
            ("French League (Dark/Yellow)", "ligue1")
        ]
        self.session.openWithCallback(self.minibar_color_selected, ChoiceBox, title="Select Mini Bar Style (Default Theme Only)", list=c_options)

    def minibar_color_selected(self, selection):
        if selection:
            self.monitor.minibar_color_mode = selection[1]
            self.monitor.save_config()
            self.session.open(MessageBox, "Mini Bar color saved.", MessageBox.TYPE_INFO)
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
        self.session.openWithCallback(self.single_league_selected, LeagueSelector, mode="single")
    def single_league_selected(self, selection=None):
        if selection:
            # Handle both ChoiceBox tuple format or our custom format
            idx = selection[1] if isinstance(selection, tuple) else selection
            self.monitor.set_league(idx)
            # Re-open screen to apply new skin/theme (F1 background etc)
            self.session.open(SimpleSportsScreen)
            self.close()
    def open_mini_bar(self):
        # Racing mode: open RacingMiniBar with selected event
        if not self.monitor.is_custom_mode:
            try:
                url = DATA_SOURCES[self.monitor.current_league_index][1]
                if get_sport_type(url) == SPORT_TYPE_RACING:
                    # Get selected event from main screen list
                    idx = self["list"].getSelectedIndex()
                    event = None
                    if idx is not None and 0 <= idx < len(self.current_match_ids):
                        match_id = self.current_match_ids[idx]
                        event = self.monitor.event_map.get(match_id)
                        if not event:
                            for ev in self.monitor.cached_events:
                                if ev.get('id') == match_id:
                                    event = ev
                                    break
                    if event:
                        self.session.open(RacingMiniBar, event)
                    else:
                        self.session.open(MessageBox, "No racing event selected!", MessageBox.TYPE_INFO, timeout=5)
                    return
            except: pass
        self.session.openWithCallback(self.mini_bar_callback, SimpleSportsMiniBar)
    def mini_bar_callback(self, result=None):
        if result == "next": 
            self.session.openWithCallback(self.on_minibar_closed, SimpleSportsMiniBar2)
        else:
            self.on_minibar_closed(result)

    def on_minibar_closed(self, result=None):
        # Determine if we need to refresh (Filter might have changed in MiniBar)
        self.update_filter_button()
        self.update_header()
        # Force refresh list with new filter through debounced trigger
        self.monitor._trigger_callbacks(True, force_refresh=True)
    def open_game_info(self):
        idx = self["list"].getSelectedIndex()
        if idx is None or not self.current_match_ids: return
        
        # Use valid index from current_match_ids to ensure WE OPEN THE CORRECT MATCH
        event = None
        if 0 <= idx < len(self.current_match_ids):
            match_id = self.current_match_ids[idx]
            
            # Find the event object
            # First check event_map (fastest)
            event = self.monitor.event_map.get(match_id)
            
            # Fallback: Search in cached_events if not found by ID directly
            if not event:
                 for ev in self.monitor.cached_events:
                     # Check connection
                     ev_id = ev.get('id', '')
                     if ev_id == match_id:
                         event = ev
                         break
            
        if event:
            selected_event = event
            self.selected_event_for_reminder = selected_event
            
            # Check if this is a driver sub-row selection
            if '_drv_' in match_id:
                try:
                    rank_str = match_id.split('_drv_')[1]
                    rank = int(rank_str)
                    comps = selected_event.get('competitions', [{}])[0].get('competitors', [])
                    driver_data = None
                    for c in comps:
                        if c.get('order', 0) == rank:
                            driver_data = c
                            break
                    if driver_data:
                        league_name = selected_event.get('league_name', '')
                        url = ""
                        for item in DATA_SOURCES:
                            if item[0] == league_name: url = item[1]; break
                        self.session.open(RacingDriverInfoScreen, driver_data, url, selected_event)
                        return
                except:
                    pass
            
            state = selected_event.get('status', {}).get('type', {}).get('state', 'pre')
            if state == 'pre':
                options = [("Game Info / Details", "info"), ("Find Broadcasting Channel", "broadcast_search"), ("Remind me 12 hours before", 720), ("Remind me 9 hours before", 540), ("Remind me 6 hours before", 360), ("Remind me 3 hours before", 180), ("Remind me 2 hours before", 120), ("Remind me 1 hour before", 60), ("Remind me 15 minutes before", 15), ("Remind me 5 minutes before", 5), ("Delete Reminder", -1), ("Cancel", 0)]
                self.session.openWithCallback(self.reminder_selected, ChoiceBox, title="Game Options", list=options)
            else:
                event_id = selected_event.get('id'); league_name = selected_event.get('league_name', ''); url = ""
                for item in DATA_SOURCES:
                    if item[0] == league_name: url = item[1]; break
                if event_id and url: self.session.open(GameInfoScreen, event_id, url, event_data=selected_event)
    def reminder_selected(self, selection):
        if not selection or selection[1] == 0: return
        val = selection[1]
        event = self.selected_event_for_reminder
        log_dbg("reminder_selected: Value={} Event={}".format(val, event.get('id')))

        if val == "info":
            event_id = event.get('id'); league_name = event.get('league_name', ''); url = ""
            for item in DATA_SOURCES:
                if item[0] == league_name: url = item[1]; break
            if event_id and url: self.session.open(GameInfoScreen, event_id, url, event_data=event)
            return
        if val == "broadcast_search":
            self.open_broadcasting(forced_event=event)
            return

        try:
            # Name Construction
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            home = "Home"; away = "Away"
            
            # Robust Name & ID Extraction
            team_h = next((t for t in comps if t.get('homeAway') == 'home'), comps[0] if comps else None)
            team_a = next((t for t in comps if t.get('homeAway') == 'away'), comps[1] if len(comps)>1 else None)
            
            h_id = team_h.get('id') if team_h else None
            a_id = team_a.get('id') if team_a else None
            
            if team_h:
                if 'athlete' in team_h: home = team_h.get('athlete', {}).get('shortName') or team_h.get('athlete', {}).get('displayName')
                else: home = team_h.get('team', {}).get('displayName', 'Home')
            if team_a:
                if 'athlete' in team_a: away = team_a.get('athlete', {}).get('shortName') or team_a.get('athlete', {}).get('displayName')
                else: away = team_a.get('team', {}).get('displayName', 'Away')
                
            match_name = home + " vs " + away
            log_dbg("reminder_selected: Match Name = " + match_name)

            if val == -1:
                if self.monitor.remove_reminder(match_name): 
                    self.session.open(MessageBox, "Reminder removed.", MessageBox.TYPE_INFO, timeout=2)
                else: 
                    self.session.open(MessageBox, "No active reminder found for: " + match_name, MessageBox.TYPE_ERROR, timeout=2)
                return

            # Robust Date Parsing
            date_str = event.get('date', '')
            match_time_ts = 0
            if date_str:
                clean_date = date_str.replace("Z", "").replace("T", " ")
                if "." in clean_date: clean_date = clean_date.split(".")[0]
                dt = None
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                    try:
                        dt = datetime.datetime.strptime(clean_date, fmt)
                        break
                    except ValueError: continue
                if dt: match_time_ts = calendar.timegm(dt.timetuple())
            
            if match_time_ts == 0:
                 self.session.open(MessageBox, "Invalid Date Error. Cannot set reminder.", MessageBox.TYPE_ERROR)
                 return

            trigger_time = match_time_ts - (val * 60)
            now = time.time()
            if now >= trigger_time:
                time_left = match_time_ts - now
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
            
            # Zap Feature: If event has a service ref (from channel mapping), store it
            # This requires us to know call open_broadcasting logic or similar?
            # For now, just store generic data
            
            self.monitor.add_reminder(match_name, trigger_time, league_name, h_logo, a_logo, label, h_id=h_id, a_id=a_id)
            self.session.open(MessageBox, "Reminder set for:\n" + match_name, MessageBox.TYPE_INFO, timeout=3)
        
        except Exception as e:
            log_dbg("reminder_selected ERROR: " + str(e))
            self.session.open(MessageBox, "Error setting reminder: " + str(e), MessageBox.TYPE_ERROR)
    def toggle_discovery(self):
        if time.time() - self.last_key_time < 0.5: return
        self.last_key_time = time.time()
        log_diag("BUTTON_BLUE: toggle_discovery pressed. is_custom={} filter_mode={}".format(self.monitor.is_custom_mode, self.monitor.filter_mode))
        self.monitor.cycle_discovery_mode(); self.update_header()
    def toggle_filter(self): 
        if time.time() - self.last_key_time < 0.5: return
        self.last_key_time = time.time()
        log_diag("BUTTON_YELLOW: toggle_filter pressed. is_custom={} discovery_mode={}".format(self.monitor.is_custom_mode, self.monitor.discovery_mode))
        self.monitor.toggle_filter(); self.update_filter_button(); self.monitor._trigger_callbacks(True, force_refresh=True)
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
GLOBAL_PICON_PATH_CACHE = {}

def get_picon(service_ref):
    if not service_ref: return None
    
    # Convert Service Reference to Picon Filename Format
    # 1:0:19:2B66:3F:1:C00000:0:0:0: -> 1_0_19_2B66_3F_1_C00000_0_0_0
    sname = str(service_ref).strip().replace(':', '_').rstrip('_')
    
    if sname in GLOBAL_PICON_PATH_CACHE:
        cached_path = GLOBAL_PICON_PATH_CACHE[sname]
        return loadPNG(cached_path) if cached_path else None
    
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
            GLOBAL_PICON_PATH_CACHE[sname] = png_file
            return loadPNG(png_file)
            
    # Try alternate name format (remove last 0 if trailing)
    if sname.endswith("_0"):
        sname_alt = sname[:-2]
        for path in search_paths:
            png_file = path + sname_alt + ".png"
            if os.path.exists(png_file):
                GLOBAL_PICON_PATH_CACHE[sname] = png_file
                return loadPNG(png_file)
                
    GLOBAL_PICON_PATH_CACHE[sname] = None
    return None

# ==============================================================================
# BROADCASTING CHANNELS SCREEN
# ==============================================================================
class BroadcastingChannelsScreen(Screen):
    def __init__(self, session, channels, match_time_ts=0):
        Screen.__init__(self, session)
        self.session = session
        self.channels = channels 
        self.match_time_ts = match_time_ts
        self.theme = global_sports_monitor.theme_mode
        
        # --- SKIN: Copied & Adapted from LEAGUE SELECTOR ---
        if self.theme == "ucl":
             self.skin = """
            <screen position="center,center" size="950,800" title="Match Broadcasts" backgroundColor="#00000000" flags="wfNoBorder">
                <eLabel position="0,0" size="950,800" backgroundColor="#0e1e5b" zPosition="-1" />
                <eLabel position="0,0" size="950,4" backgroundColor="#00ffff" zPosition="1" />
                <eLabel position="0,796" size="950,4" backgroundColor="#00ffff" zPosition="1" />
                <eLabel position="0,0" size="4,800" backgroundColor="#00ffff" zPosition="1" />
                <eLabel position="946,0" size="4,800" backgroundColor="#00ffff" zPosition="1" />
                <widget name="title" position="30,20" size="890,50" font="SimplySportFont;38" foregroundColor="#00ffff" backgroundColor="#0e1e5b" transparent="1" halign="center" />
                <eLabel position="30,75" size="890,2" backgroundColor="#182c82" />
                <widget name="list" position="30,90" size="890,620" scrollbarMode="showOnDemand" transparent="1" />
                <eLabel position="30,720" size="890,2" backgroundColor="#182c82" />
                <widget name="key_red" position="30,740" size="200,50" font="SimplySportFont;28" foregroundColor="#FFFFFF" backgroundColor="#F44336" transparent="0" zPosition="1" halign="center" valign="center" />
                <widget name="key_green" position="240,740" size="200,50" font="SimplySportFont;28" foregroundColor="#000000" backgroundColor="#00FF85" transparent="0" zPosition="1" halign="center" valign="center" />
                <widget name="key_yellow" position="450,740" size="200,50" font="SimplySportFont;28" foregroundColor="#FFFFFF" backgroundColor="#FFA000" transparent="0" zPosition="1" halign="center" valign="center" />
                <widget name="hint" position="680,740" size="240,50" font="SimplySportFont;24" foregroundColor="#00ffff" backgroundColor="#0e1e5b" transparent="1" halign="center" valign="center" />
            </screen>
            """
        else:
            self.skin = """
            <screen position="center,center" size="950,800" title="Match Broadcasts" backgroundColor="#38003C" flags="wfNoBorder">
                <eLabel position="0,0" size="950,800" backgroundColor="#38003C" zPosition="-1" />
                <eLabel position="0,0" size="950,4" backgroundColor="#00FF85" zPosition="1" />
                <eLabel position="0,796" size="950,4" backgroundColor="#00FF85" zPosition="1" />
                <eLabel position="0,0" size="4,800" backgroundColor="#00FF85" zPosition="1" />
                <eLabel position="946,0" size="4,800" backgroundColor="#00FF85" zPosition="1" />
                <widget name="title" position="30,20" size="890,50" font="SimplySportFont;38" foregroundColor="#00FF85" backgroundColor="#38003C" transparent="1" halign="center" />
                <eLabel position="30,75" size="890,2" backgroundColor="#505050" />
                <widget name="list" position="30,90" size="890,620" scrollbarMode="showOnDemand" transparent="1" />
                <eLabel position="30,720" size="890,2" backgroundColor="#505050" />
                <widget name="key_red" position="30,740" size="200,50" font="SimplySportFont;28" foregroundColor="#FFFFFF" backgroundColor="#F44336" transparent="0" zPosition="1" halign="center" valign="center" />
                <widget name="key_green" position="240,740" size="200,50" font="SimplySportFont;28" foregroundColor="#000000" backgroundColor="#00FF85" transparent="0" zPosition="1" halign="center" valign="center" />
                <widget name="key_yellow" position="450,740" size="200,50" font="SimplySportFont;28" foregroundColor="#FFFFFF" backgroundColor="#FFA000" transparent="0" zPosition="1" halign="center" valign="center" />
                <widget name="hint" position="680,740" size="240,50" font="SimplySportFont;24" foregroundColor="#9E9E9E" backgroundColor="#38003C" transparent="1" halign="center" valign="center" />
            </screen>
            """
        
        self["title"] = Label("MATCH BROADCASTS")
        self["hint"] = Label("Select Channel to Zap")
        self["key_red"] = Label("Cancel")
        self["key_green"] = Label("Up")
        self["key_yellow"] = Label("Down")
        
        self["list"] = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
        # Match Fonts to LeagueSelector
        self["list"].l.setFont(0, gFont("SimplySportFont", 28)) 
        self["list"].l.setFont(1, gFont("SimplySportFont", 22)) 
        self["list"].l.setItemHeight(60) 
        
        # Priority -1: Standard Screen Priority
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
            "ok": self.zap_to_channel,
            "cancel": self.close,
            "back": self.close,
            "red": self.close,
            "up": self["list"].up,
            "down": self["list"].down,
            "green": self["list"].up,
            "yellow": self["list"].down,
            "left": self["list"].pageUp,
            "right": self["list"].pageDown
        }, -1)
        
        self.onLayoutFinish.append(self.start_list)

    def start_list(self):
        self.show_channels()
        # Explicit focus and selection visibility
        try:
            self["list"].selectionEnabled(1)
            self["list"].instance.setSelectionEnable(1)
            self["list"].instance.setShowSelection(True)
        except: pass

    def show_channels(self):
        res = []
        for item in self.channels:
            if len(item) == 4:
                (sref, sname, event_name, cat_color) = item
            elif len(item) == 3:
                (sref, sname, event_name) = item
                cat_color = 0x00FF00
            else: continue
            res.append(self.build_entry(sref, sname, event_name, cat_color))
        self["list"].setList(res)
        
        if res:
             self["list"].moveToIndex(0)

    def build_entry(self, sref, sname, event_name, cat_color):
        c_text = 0xffffff; c_dim = 0xaaaaaa; c_sel = 0x00FF85 if self.theme != "ucl" else 0x00ffff
        
        picon = get_picon(sref)
        
        # BT_SCALE (0x80) | BT_KEEP_ASPECT_RATIO (0x40)
        # Use existing align constants + scale flag
        # Standard E2 flags: HALIGN=1, VALIGN=4. BT_SCALE usually 0x80 or implied by definition in some skins.
        # But safest is passing the flag directly if eListboxPythonMultiContent supports it (most modern do).
        BT_SCALE = 0x80
        BT_KEEP_ASPECT_RATIO = 0x40
            
        # FIX: Provide valid data payload instead of None to ensure selectability
        res = [(sref, sname, event_name, cat_color)]
        
        # Adjusted layout to fit new width (890px)
        # 1. Color Strip
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 5, 5, 8, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, "", 0x000000, cat_color))
        
        # 2. Picon - Scaled
        if picon:
            # Add scaling flags to alignment
            scale_flags = RT_HALIGN_CENTER | RT_VALIGN_CENTER | BT_SCALE | BT_KEEP_ASPECT_RATIO
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 5, 100, 50, picon, 0, 0, scale_flags))
        
        # 3. Text
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 130, 2, 750, 30, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, sname, c_text, c_sel))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 130, 32, 750, 25, 1, RT_HALIGN_LEFT|RT_VALIGN_CENTER, event_name, c_dim, c_sel))
        return res

    def zap_to_channel(self):
        idx = self["list"].getSelectedIndex()
        if idx is not None:
             # Get valid data tuple (sref, sname, event_name, cat_color)
             item = self["list"].list[idx][0]
             sref = item[0]
             sname = item[1]
             event_name = item[2]
             
             if sref:
                # Check if match is in the future (> 5 mins from now)
                now = int(time.time())
                if self.match_time_ts > now + 300:
                    self.session.openWithCallback(self.zap_callback, ChoiceBox, title="Future Match Selected", list=[("Zap Now (Check Channel)", "zap"), ("Remind & Zap (When starts)", "remind_zap")])
                else:
                    self.real_zap(sref)

    def zap_callback(self, answer):
        if not answer: return
        action = answer[1]
        
        idx = self["list"].getSelectedIndex()
        if idx is None: return
        item = self["list"].list[idx][0]
        sref = item[0]
        sname = item[1]
        event_name = item[2] # This is "Team A vs Team B" usually or Title

        if action == "zap":
            self.real_zap(sref)
        elif action == "remind_zap":
            # Add Zap Reminder
            # Use event_name as match name
            # Trigger time = match_time_ts (exact start)
            # Use channel name as league/label fallback
            try:
                trigger = self.match_time_ts
                # Label for reminder list
                label = "Zap Reminder"
                
                # Check for duplicate
                global_sports_monitor.add_reminder(event_name, trigger, "SimplySports", "", "", label, sref=sref)
                self.session.open(MessageBox, "Zap Reminder Set!\nYou will be asked to zap when the match starts.", MessageBox.TYPE_INFO, timeout=5)
            except Exception as e:
                self.session.open(MessageBox, "Error setting reminder: " + str(e), MessageBox.TYPE_ERROR)

    def real_zap(self, sref):
        self.session.nav.playService(eServiceReference(sref))
        self.close()

    def add_timer(self):
        idx = self["list"].getSelectedIndex()
        if idx is None: return
        item = self.channels[idx]
        sref = item[0]
        # Channels item: (sref, full_name, display_title, color, score)
        # display_title is "[100] Event Name"
        
        try:
            from Screens.TimerEntry import TimerEntry
            from RecordTimer import RecordTimerEntry
            from enigma import eServiceReference
            
            # Create a basic timer entry
            # Type 1 = Zap (RecordTimer.one_shot) - usually Zap is handled specifically or type 1
            # Actually RecordTimerEntry(service_ref, begin, end, name, description, eit, disabled, justplay, afterEvent, dirname, tags)
            # justplay=1 means Zap Timer
            
            begin = self.match_time_ts
            end = begin + 7200 # Default 2 hours
            
            # Clean name
            name = "Match"
            desc = ""
            if len(item) >= 3:
                raw_name = item[2]
                # Remove score prefix [100]
                if "]" in raw_name: name = raw_name.split(']', 1)[1].strip()
                else: name = raw_name
            
            # Create Timer Entry
            timer = RecordTimerEntry(eServiceReference(sref), begin, end, name, desc, None, False, True, 0)
            
            self.session.open(TimerEntry, timer)
        except Exception as e:
            self.session.open(MessageBox, "Error creating timer: " + str(e), MessageBox.TYPE_ERROR)
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
# GAMIFICATION BADGE / RANK SYSTEM
# ==============================================================================
def get_rank_badge(score, accuracy):
    """Returns a dynamic title badge based on score and accuracy.

    Tiers are evaluated from highest to lowest; the first match wins.
    Each tier has a base badge (score-only) and an optional accuracy-bonus
    badge that unlocks a prestige title at the same score level.

    Tier map:
        500+ pts  & acc > 80% -> Prophet   (elite + surgical)
        500+ pts               -> Legend    (elite volume)
        300+ pts  & acc > 75% -> Visionary (master + razor-sharp)
        300+ pts               -> Master    (high volume)
        150+ pts  & acc > 70% -> Strategist(expert + sharp)
        150+ pts               -> Expert    (solid volume)
         75+ pts  & acc > 65% -> Tactician (veteran + precise)
         75+ pts               -> Veteran   (solid volume)
         50+ pts  & acc > 60% -> Oracle    (early accuracy reward, as specified)
         11-49 pts             -> Scout
          0-10 pts             -> Rookie
    """
    score = int(score)
    accuracy = float(accuracy)

    if score >= 500 and accuracy > 80:  return "Prophet"
    if score >= 500:                    return "Legend"
    if score >= 300 and accuracy > 75:  return "Visionary"
    if score >= 300:                    return "Master"
    if score >= 150 and accuracy > 70:  return "Strategist"
    if score >= 150:                    return "Expert"
    if score >= 75  and accuracy > 65:  return "Tactician"
    if score >= 75:                     return "Veteran"
    if score >= 50  and accuracy > 60:  return "Oracle"
    if score >= 11:                     return "Scout"
    return "Rookie"

# Badge tier → hex colour (used by both leaderboard and profile entry builders)
BADGE_COLORS = {
    "Prophet":    0xFFFFAA,   # near-white gold
    "Legend":     0xFFD700,   # gold
    "Visionary":  0xFF44AA,   # pink
    "Master":     0xFF6633,   # orange-red
    "Strategist": 0xAA88FF,   # soft purple
    "Expert":     0xFFAA00,   # amber
    "Tactician":  0x00DDBB,   # bright teal
    "Veteran":    0x00AAAA,   # teal
    "Oracle":     0x00CC66,   # green
    "Scout":      0x4488FF,   # blue
    "Rookie":     0x888888,   # dim gray
}

def get_badge_color(badge):
    return BADGE_COLORS.get(badge, 0x888888)

def LeaderboardListEntry(rank, name, badge, score, accuracy, total_bets, theme_mode="default"):
    """One coloured row for the global leaderboard list.

    Column layout (1600 px wide, item height 74 px):
      x=0   w=70   rank number / medal symbol
      x=70  w=4    thin accent bar
      x=90  w=460  player name (bold)
      x=570 w=210  badge title (tier colour)
      x=800 w=140  score  label + value
      x=960 w=220  accuracy bar + value
      x=1200 w=200 total bets
      x=1570 w=2   right border
    """
    try:
        # ── Palette ────────────────────────────────────────────────────────────
        if theme_mode == "ucl":
            c_bg   = 0x091442;  c_sel  = 0x00ffff;  c_accent = 0x00ffff
            c_dim  = 0x7799cc;  c_text = 0xeeeeff;  c_gold   = 0x00ffff
        else:
            c_bg   = 0x111118;  c_sel  = 0x00FF85;  c_accent = 0x00FF85
            c_dim  = 0x778899;  c_text = 0xffffff;  c_gold   = 0xFFD700

        c_silver  = 0xC0C0C0
        c_bronze  = 0xCD7F32
        c_won     = 0x33DD77
        c_lost    = 0xFF4455

        # Medal colour for top 3
        if   rank == 1: rank_color = c_gold
        elif rank == 2: rank_color = c_silver
        elif rank == 3: rank_color = c_bronze
        else:           rank_color = c_dim

        badge_color = get_badge_color(badge)

        h    = 74
        # rank symbol
        rank_txt = u"#{:d}".format(rank) if rank > 3 else [u"1st", u"2nd", u"3rd"][rank - 1]

        entry_data = ("LB", rank, name, badge, score, accuracy, total_bets, theme_mode)
        res = [entry_data]

        # ── Rank ──
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    0, 0, 70, h, 1,
                    RT_HALIGN_CENTER | RT_VALIGN_CENTER,
                    rank_txt, rank_color, c_sel))

        # ── Thin accent bar (left edge of name column) ──
        bar_color = rank_color if rank <= 3 else c_accent
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    71, 8, 4, h - 16, 0,
                    RT_HALIGN_CENTER,
                    u"", bar_color, bar_color))

        # ── Player name ──
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    84, 0, 470, h, 1,
                    RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                    name, c_text, c_sel))

        # ── Badge title ──
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    570, 0, 210, h, 0,
                    RT_HALIGN_CENTER | RT_VALIGN_CENTER,
                    u"[{}]".format(badge), badge_color, c_sel))

        # ── Score ──
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    800, 0, 60, h, 0,
                    RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                    u"Pts", c_dim, c_sel))
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    845, 0, 120, h, 1,
                    RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                    str(score), c_won if score > 0 else c_dim, c_sel))

        # ── Accuracy ──
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    990, 0, 60, h, 0,
                    RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                    u"Acc", c_dim, c_sel))
        acc_color = c_won if accuracy >= 60 else c_lost if accuracy > 0 else c_dim
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    1038, 0, 160, h, 1,
                    RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                    u"{:.1f}%".format(accuracy), acc_color, c_sel))

        # ── Total bets ──
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    1215, 0, 70, h, 0,
                    RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                    u"Bets", c_dim, c_sel))
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    1265, 0, 120, h, 1,
                    RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                    str(total_bets), c_text, c_sel))

        # ── Bottom separator ──
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    0, h - 2, 1590, 2, 0,
                    RT_HALIGN_CENTER,
                    u"", 0x222230, 0x222230))

        return res
    except Exception as e:
        print("[LB Entry] Error:", e)
        return []


def ProfileListEntry(outcome, h_name, a_name, picked, score_str, date_str, theme_mode="default"):
    """One coloured row for the Personal Profile bet history.

    outcome: "WON", "LOST", or "PENDING"
    Column layout (1600 px wide, item height 74 px):
      x=0   w=4    accent bar (green/red/yellow)
      x=12  w=130  outcome tag  [WON] / [LOST] / [PENDING]
      x=155 w=530  match name   Arsenal vs Chelsea
      x=700 w=80   "Picked:" label
      x=790 w=280  picked team
      x=1085 w=60  "FT:" label  (hidden for PENDING)
      x=1155 w=180 score        (hidden for PENDING)
      x=1390 w=180 date
    """
    try:
        if theme_mode == "ucl":
            c_bg   = 0x091442;  c_sel  = 0x00ffff;  c_accent = 0x00ffff
            c_dim  = 0x7799cc;  c_text = 0xeeeeff
        else:
            c_bg   = 0x111118;  c_sel  = 0x00FF85;  c_accent = 0x00FF85
            c_dim  = 0x778899;  c_text = 0xffffff

        c_won     = 0x33DD77
        c_lost    = 0xFF4455
        c_pending = 0xFFAA00

        if outcome == "WON":
            bar_color = c_won;     tag_color = c_won;     tag_txt = u"[WON]"
        elif outcome == "LOST":
            bar_color = c_lost;    tag_color = c_lost;    tag_txt = u"[LOST]"
        else:
            bar_color = c_pending; tag_color = c_pending; tag_txt = u"[PENDING]"

        match_txt = u"{} vs {}".format(h_name, a_name)

        h = 74
        entry_data = ("PF", outcome, h_name, a_name, picked, score_str, date_str, theme_mode)
        res = [entry_data]

        # Accent bar
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    0, 8, 4, h - 16, 0,
                    RT_HALIGN_CENTER,
                    u"", bar_color, bar_color))

        # Outcome tag
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    12, 0, 130, h, 1,
                    RT_HALIGN_CENTER | RT_VALIGN_CENTER,
                    tag_txt, tag_color, c_sel))

        # Match name
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    155, 0, 530, h, 1,
                    RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                    match_txt, c_text, c_sel))

        # "Picked:" label
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    700, 0, 80, h, 0,
                    RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                    u"Picked:", c_dim, c_sel))

        # Picked team
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    792, 0, 280, h, 1,
                    RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                    picked, c_text, c_sel))

        # FT + score (resolved only)
        if outcome != "PENDING":
            res.append((eListboxPythonMultiContent.TYPE_TEXT,
                        1085, 0, 50, h, 0,
                        RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                        u"FT:", c_dim, c_sel))
            res.append((eListboxPythonMultiContent.TYPE_TEXT,
                        1140, 0, 180, h, 1,
                        RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                        score_str, c_text, c_sel))

        # Date
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    1390, 0, 190, h, 0,
                    RT_HALIGN_RIGHT | RT_VALIGN_CENTER,
                    date_str, c_dim, c_sel))

        # Bottom separator
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    12, h - 2, 1570, 2, 0,
                    RT_HALIGN_CENTER,
                    u"", 0x222230, 0x222230))

        return res
    except Exception as e:
        print("[Profile Entry] Error:", e)
        return []


def ProfileSectionHeader(title, theme_mode="default"):
    """A dim section divider row (e.g. '-- Pending bets --')."""
    try:
        if theme_mode == "ucl":
            c_bg = 0x091442; c_accent = 0x00ffff; c_dim = 0x7799cc
        else:
            c_bg = 0x0d0d15; c_accent = 0x00FF85; c_dim = 0x556677
        h = 40
        entry_data = ("PH", title, theme_mode)
        res = [entry_data]
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    0, 0, 1590, h - 2, 0,
                    RT_HALIGN_CENTER,
                    u"", c_bg, c_bg))
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    20, 0, 1560, h, 0,
                    RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                    title, c_dim, c_accent))
        res.append((eListboxPythonMultiContent.TYPE_TEXT,
                    0, h - 2, 1590, 2, 0,
                    RT_HALIGN_CENTER,
                    u"", 0x222230, 0x222230))
        return res
    except Exception as e:
        print("[Profile Header] Error:", e)
        return []

class LeaderboardScreen(Screen):

    def __init__(self, session):
        Screen.__init__(self, session)
        self.setTitle("SimplySports: Global Leaderboard")

        theme = getattr(global_sports_monitor, "theme_mode", "default") if global_sports_monitor else "default"
        if theme == "ucl":
            bg       = "#00091442";  top_bar  = "#091442"
            accent   = "#00ffff";    dim      = "#7799cc"
        else:
            bg       = "#00111118";  top_bar  = "#0d0d20"
            accent   = "#00FF85";    dim      = "#556677"

        self.skin = (
            u'<screen name="LeaderboardScreen" position="center,center" '
            u'size="1600,900" flags="wfNoBorder" backgroundColor="{bg}">'
            # ── Top bar ──
            u'<eLabel position="0,0"    size="1600,90"  backgroundColor="{top}" zPosition="0"/>'
            u'<eLabel position="0,90"   size="1600,3"   backgroundColor="{acc}" zPosition="1"/>'
            # ── Title + sport filter label ──
            u'<widget name="title_lbl"  position="0,20" size="1600,50" font="Regular;30" '
            u'foregroundColor="{acc}" halign="center" valign="center" transparent="1" zPosition="5"/>'
            u'<widget name="sport_label" position="0,96" size="1600,28" font="Regular;20" '
            u'foregroundColor="{dim}" halign="center" valign="center" transparent="1" zPosition="5"/>'
            # ── Column header labels ──
            u'<eLabel position="0,124"  size="1600,30"  backgroundColor="#0a0a16" zPosition="2"/>'
            u'<widget name="col_rank"   position="0,124"   size="70,30"  font="Regular;16" foregroundColor="{dim}" halign="center" valign="center" transparent="1" zPosition="5"/>'
            u'<widget name="col_name"   position="84,124"  size="470,30" font="Regular;16" foregroundColor="{dim}" halign="left"   valign="center" transparent="1" zPosition="5"/>'
            u'<widget name="col_badge"  position="570,124" size="210,30" font="Regular;16" foregroundColor="{dim}" halign="center" valign="center" transparent="1" zPosition="5"/>'
            u'<widget name="col_score"  position="800,124" size="170,30" font="Regular;16" foregroundColor="{dim}" halign="left"   valign="center" transparent="1" zPosition="5"/>'
            u'<widget name="col_acc"    position="990,124" size="210,30" font="Regular;16" foregroundColor="{dim}" halign="left"   valign="center" transparent="1" zPosition="5"/>'
            u'<widget name="col_bets"   position="1215,124" size="200,30" font="Regular;16" foregroundColor="{dim}" halign="left"  valign="center" transparent="1" zPosition="5"/>'
            # ── List ──
            u'<widget name="list" position="0,154" size="1600,666" scrollbarMode="showNever" '
            u'transparent="1" zPosition="5"/>'
            # ── Loading label (shown before data arrives) ──
            u'<widget name="loading" position="0,400" size="1600,60" font="Regular;28" '
            u'foregroundColor="{acc}" halign="center" transparent="1" zPosition="8"/>'
            # ── Button bar ──
            u'<eLabel position="0,820" size="1600,3"   backgroundColor="{acc}" zPosition="1"/>'
            u'<eLabel position="0,823" size="1600,77"  backgroundColor="{top}" zPosition="0"/>'
            u'<ePixmap pixmap="skin_default/buttons/green.png"  position="30,848"  size="35,25" alphatest="on" zPosition="5"/>'
            u'<widget name="key_green"  position="75,843"  size="260,35" font="Regular;22" foregroundColor="{acc}" halign="left" valign="center" transparent="1" zPosition="5"/>'
            u'<ePixmap pixmap="skin_default/buttons/yellow.png" position="430,848" size="35,25" alphatest="on" zPosition="5"/>'
            u'<widget name="key_yellow" position="475,843" size="280,35" font="Regular;22" foregroundColor="#FFEE00" halign="left" valign="center" transparent="1" zPosition="5"/>'
            u'<ePixmap pixmap="skin_default/buttons/blue.png"   position="860,848" size="35,25" alphatest="on" zPosition="5"/>'
            u'<widget name="key_blue"   position="905,843" size="260,35" font="Regular;22" foregroundColor="#44AAFF" halign="left" valign="center" transparent="1" zPosition="5"/>'
            u'<widget name="hint"       position="1200,848" size="380,35" font="Regular;18" foregroundColor="{dim}" halign="right" valign="center" transparent="1" zPosition="5"/>'
            u'</screen>'
        ).format(bg=bg, top=top_bar, acc=accent, dim=dim)

        # ── Widgets ──
        self["title_lbl"]  = Label("GLOBAL LEADERBOARD")
        self["sport_label"] = Label("")
        self["loading"]    = Label("Fetching leaderboard...")
        self["key_green"]  = Label("Score Rank")
        self["key_yellow"] = Label("Accuracy Rank")
        self["key_blue"]   = Label("My Profile")
        self["hint"]       = Label(u"◄ ►  Change Sport")
        # Column headers
        self["col_rank"]  = Label("#")
        self["col_name"]  = Label("Player")
        self["col_badge"] = Label("Badge")
        self["col_score"] = Label("Pts")
        self["col_acc"]   = Label("Accuracy")
        self["col_bets"]  = Label("Bets")

        self["list"] = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)

        self.users_data      = []
        self.available_sports = ["Global"]
        self.current_sport_idx = 0
        self.current_sort    = "score"
        self._theme          = theme

        self["actions"] = ActionMap(
            ["SetupActions", "ColorActions", "DirectionActions"], {
                "cancel": self.close,
                "ok":     self.close,
                "green":  self.sort_by_score,
                "yellow": self.sort_by_accuracy,
                "blue":   self.open_profile,
                "left":   self.prev_sport,
                "right":  self.next_sport,
                "up":     self.cursor_up,
                "down":   self.cursor_down,
            }, -1)

        self.onLayoutFinish.append(self._setup_list)
        self.fetch_leaderboard()

    def _setup_list(self):
        self["list"].l.setFont(0, gFont("Regular", 22))
        self["list"].l.setFont(1, gFont("Regular", 24))
        self["list"].l.setItemHeight(74)

    def cursor_up(self):
        self["list"].up()

    def cursor_down(self):
        self["list"].down()

    def open_profile(self):
        self.session.open(PersonalProfileScreen)
        
    def fetch_leaderboard(self):
        import threading
        import time
        url = "{}/leaderboard.json?r={}".format(FIREBASE_URL, int(time.time()))
        
        def _fetch():
            try:
                try:
                    import urllib2 as request_module
                except ImportError:
                    import urllib.request as request_module
                
                req = request_module.Request(url)
                response = request_module.urlopen(req, timeout=5)
                html = response.read()
                
                from twisted.internet import reactor
                reactor.callFromThread(self.on_data_received, html)
            except Exception as e:
                print("[SimplySports] Leaderboard fetch failed:", e)
                
        threading.Thread(target=_fetch).start()
        
    def on_data_received(self, html):
        import json
        try:
            if isinstance(html, bytes): html = html.decode('utf-8')
            if not html or html.strip() == "null":
                self["loading"].setText("No scores recorded yet.")
                return
                
            data = json.loads(html)
            self.users_data = []
            sports_set = set() # Automatically find all sports the community has voted on
            
            if isinstance(data, dict):
                for device_id, info in data.items():
                    user_sports = info.get("sports", {})
                    for s in user_sports.keys():
                        sports_set.add(s)

                    stored_score    = int(info.get("score", 0))
                    stored_accuracy = float(info.get("accuracy", 0.0))

                    # Use the badge stored by the remote client if present;
                    # otherwise compute it live so older clients that pre-date
                    # the badge feature still get a correct title.
                    stored_badge = info.get("badge")
                    if not stored_badge:
                        stored_badge = get_rank_badge(stored_score, stored_accuracy)

                    self.users_data.append({
                        "name": info.get("name", "Anonymous"),
                        "score": stored_score,
                        "accuracy": stored_accuracy,
                        "total_bets": int(info.get("total_bets", 0)),
                        "sports": user_sports,
                        "badge": stored_badge
                    })
            
            # Build the navigation list
            self.available_sports = ["Global"] + sorted(list(sports_set))
            self.apply_sort()
            
        except Exception as e:
            print("[SimplySports] Parse error:", e)

    # --- NAVIGATION METHODS ---
    def next_sport(self):
        self.current_sport_idx = (self.current_sport_idx + 1) % len(self.available_sports)
        self.apply_sort()

    def prev_sport(self):
        self.current_sport_idx = (self.current_sport_idx - 1) % len(self.available_sports)
        self.apply_sort()

    def sort_by_score(self):
        self.current_sort = "score"
        self.apply_sort()

    def sort_by_accuracy(self):
        self.current_sort = "accuracy"
        self.apply_sort()

    # --- CORE FILTERING AND SORTING ENGINE ---
    def extract_stats(self, user, sport):
        """Extracts either Global stats or specific Sport stats for the math"""
        if sport == "Global":
            return user['score'], user['accuracy'], user['total_bets']
        else:
            sd = user['sports'].get(sport, {})
            sc = sd.get("score", 0)
            tot = sd.get("total", 0)
            cor = sd.get("correct", 0)
            acc = (float(cor) / tot * 100.0) if tot > 0 else 0.0
            return sc, acc, tot

    def apply_sort(self):
        if not self.users_data: return

        current_sport = self.available_sports[self.current_sport_idx]

        # 1. Sport filter label
        if current_sport == "Global":
            self["sport_label"].setText(u"◄  Global Ranking  ►")
        else:
            self["sport_label"].setText(
                u"◄  {} Only  ►".format(current_sport.upper()))

        # 2. Filter
        filtered_users = [
            u for u in self.users_data
            if current_sport == "Global" or current_sport in u['sports']
        ]

        # 3. Sort
        if self.current_sort == "score":
            sorted_users = sorted(
                filtered_users,
                key=lambda k: (self.extract_stats(k, current_sport)[0],
                               self.extract_stats(k, current_sport)[1]),
                reverse=True)
        else:
            sorted_users = sorted(
                filtered_users,
                key=lambda k: (self.extract_stats(k, current_sport)[1],
                               self.extract_stats(k, current_sport)[0]),
                reverse=True)

        # 4. Render with coloured multiContent rows
        rows = []
        for idx, user in enumerate(sorted_users):
            rank = idx + 1
            sc, acc, tot = self.extract_stats(user, current_sport)
            badge = get_rank_badge(sc, acc)
            row = LeaderboardListEntry(
                rank, user['name'], badge, sc, acc, tot, self._theme)
            if row:
                rows.append(row)

        if not rows:
            rows.append(([("EMPTY",)],))

        self["list"].setList(rows)
        # Hide the loading label once data is rendered
        try:
            self["loading"].setText("")
        except Exception:
            pass

# ==============================================================================
# PERSONAL PROFILE / BET HISTORY SCREEN
# ==============================================================================
class PersonalProfileScreen(Screen):
    """Personal stats header + scrollable bet history.

    Layout: 1600x900, same visual language as LeaderboardScreen.
    Navigation: up/down cursor + page up/down.
    Data source: global_sports_monitor.ledger (100% local, no network call).
    """

    MAX_HISTORY = 20

    def __init__(self, session):
        Screen.__init__(self, session)
        self.setTitle("SimplySports: My Profile")

        theme = getattr(global_sports_monitor, "theme_mode", "default") if global_sports_monitor else "default"
        self._theme = theme

        if theme == "ucl":
            bg      = "#00091442"; top_bar = "#091442"
            accent  = "#00ffff";   dim     = "#7799cc"
        else:
            bg      = "#00111118"; top_bar = "#0d0d20"
            accent  = "#00FF85";   dim     = "#556677"

        self.skin = (
            u'<screen name="PersonalProfileScreen" position="center,center" '
            u'size="1600,900" flags="wfNoBorder" backgroundColor="{bg}">'
            # Top bar
            u'<eLabel position="0,0"    size="1600,90"  backgroundColor="{top}" zPosition="0"/>'
            u'<eLabel position="0,90"   size="1600,3"   backgroundColor="{acc}" zPosition="1"/>'
            # Name + badge (large, centred)
            u'<widget name="header_name"  position="0,12" size="1600,46" font="Regular;32" '
            u'foregroundColor="{acc}" halign="center" valign="center" transparent="1" zPosition="5"/>'
            # Stats strip
            u'<widget name="header_stats" position="0,55" size="1600,28" font="Regular;20" '
            u'foregroundColor="{dim}" halign="center" valign="center" transparent="1" zPosition="5"/>'
            # Column headers
            u'<eLabel position="0,93" size="1600,30" backgroundColor="#0a0a16" zPosition="2"/>'
            u'<widget name="col_outcome" position="12,93"   size="130,30" font="Regular;16" foregroundColor="{dim}" halign="center" valign="center" transparent="1" zPosition="5"/>'
            u'<widget name="col_match"   position="155,93"  size="530,30" font="Regular;16" foregroundColor="{dim}" halign="left"   valign="center" transparent="1" zPosition="5"/>'
            u'<widget name="col_picked"  position="700,93"  size="360,30" font="Regular;16" foregroundColor="{dim}" halign="left"   valign="center" transparent="1" zPosition="5"/>'
            u'<widget name="col_score"   position="1085,93" size="290,30" font="Regular;16" foregroundColor="{dim}" halign="left"   valign="center" transparent="1" zPosition="5"/>'
            u'<widget name="col_date"    position="1390,93" size="190,30" font="Regular;16" foregroundColor="{dim}" halign="right"  valign="center" transparent="1" zPosition="5"/>'
            # List
            u'<widget name="list" position="0,123" size="1600,617" scrollbarMode="showNever" '
            u'transparent="1" zPosition="5"/>'
            # Button bar
            u'<eLabel position="0,740" size="1600,3"  backgroundColor="{acc}" zPosition="1"/>'
            u'<eLabel position="0,743" size="1600,77" backgroundColor="{top}" zPosition="0"/>'
            u'<ePixmap pixmap="skin_default/buttons/red.png" position="30,768" size="35,25" alphatest="on" zPosition="5"/>'
            u'<widget name="key_red"    position="75,763"  size="200,35" font="Regular;22" foregroundColor="#FF4455" halign="left" valign="center" transparent="1" zPosition="5"/>'
            u'<widget name="hint"       position="1200,763" size="380,35" font="Regular;18" foregroundColor="{dim}" halign="right" valign="center" transparent="1" zPosition="5"/>'
            u'</screen>'
        ).format(bg=bg, top=top_bar, acc=accent, dim=dim)

        self["header_name"]  = Label("")
        self["header_stats"] = Label("")
        self["key_red"]      = Label("Close")
        self["hint"]         = Label(u"▲ ▼  Navigate")
        self["col_outcome"]  = Label("Result")
        self["col_match"]    = Label("Match")
        self["col_picked"]   = Label("Your Pick")
        self["col_score"]    = Label("Final Score")
        self["col_date"]     = Label("Date")

        self["list"] = MenuList([], enableWrapAround=False, content=eListboxPythonMultiContent)

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions", "DirectionActions"], {
                "cancel":  self.close,
                "ok":      self.close,
                "red":     self.close,
                "up":      self.cursor_up,
                "down":    self.cursor_down,
                "left":    self.page_up,
                "right":   self.page_down,
            }, -1)

        self.onLayoutFinish.append(self._setup_and_populate)

    def _setup_and_populate(self):
        self["list"].l.setFont(0, gFont("Regular", 20))
        self["list"].l.setFont(1, gFont("Regular", 22))
        self._populate()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def cursor_up(self):
        self["list"].up()

    def cursor_down(self):
        self["list"].down()

    def page_up(self):
        self["list"].pageUp()

    def page_down(self):
        self["list"].pageDown()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _prediction_label(prediction, h_name, a_name):
        if prediction == "home": return h_name
        if prediction == "away": return a_name
        return "Draw"

    @staticmethod
    def _format_timestamp(ts):
        try:
            import time as _time
            return _time.strftime("%d %b", _time.localtime(int(ts)))
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Main render
    # ------------------------------------------------------------------

    def _populate(self):
        if not global_sports_monitor:
            return

        ledger = global_sports_monitor.ledger
        voter_name    = getattr(global_sports_monitor, "voter_name", "Anonymous")
        total_score   = int(ledger.get("total_score", 0))
        total_preds   = int(ledger.get("total_predictions", 0))
        correct_preds = int(ledger.get("correct_predictions", 0))
        accuracy      = (float(correct_preds) / total_preds * 100.0) if total_preds > 0 else 0.0
        badge         = get_rank_badge(total_score, accuracy)

        # Header widgets
        self["header_name"].setText(
            u"{name}   [{badge}]".format(name=voter_name, badge=badge))
        self["header_stats"].setText(
            u"Score: {sc}   •   Accuracy: {acc:.1f}%   •   Total Bets: {tot}   •   Correct: {cor}".format(
                sc=total_score, acc=accuracy, tot=total_preds, cor=correct_preds))

        # ── Resolved bets (newest first, capped) ──
        resolved = ledger.get("resolved_bets", {})
        sorted_resolved = []
        if isinstance(resolved, dict):
            sorted_resolved = sorted(
                [(eid, bet) for eid, bet in resolved.items()
                 if isinstance(bet, dict) and not bet.get("legacy")],
                key=lambda x: int(x[1].get("timestamp", 0)),
                reverse=True
            )[:self.MAX_HISTORY]

        rows = []

        if not sorted_resolved:
            rows.append(ProfileSectionHeader(
                "  No resolved bets yet  —  vote on a match to start!", self._theme))
        else:
            for _eid, bet in sorted_resolved:
                prediction  = bet.get("prediction", "?")
                result      = bet.get("result", "?")
                score_str   = bet.get("score", "?-?")
                h_name      = bet.get("h_name", "Home")
                a_name      = bet.get("a_name", "Away")
                ts          = bet.get("timestamp", 0)
                outcome     = "WON" if prediction == result else "LOST"
                picked_lbl  = self._prediction_label(prediction, h_name, a_name)
                date_lbl    = self._format_timestamp(ts)
                row = ProfileListEntry(
                    outcome, h_name, a_name, picked_lbl,
                    score_str, date_lbl, self._theme)
                if row:
                    rows.append(row)

        # ── Pending bets ──
        pending = ledger.get("pending_bets", {})
        if isinstance(pending, dict) and pending:
            rows.append(ProfileSectionHeader(
                u"  ⏳  Awaiting results  —  {} pending".format(len(pending)),
                self._theme))
            for _eid, bet in sorted(pending.items(),
                                    key=lambda x: int(x[1].get("timestamp", 0)),
                                    reverse=True):
                prediction = bet.get("prediction", "?")
                h_name     = bet.get("h_name", "Home")
                a_name     = bet.get("a_name", "Away")
                picked_lbl = self._prediction_label(prediction, h_name, a_name)
                row = ProfileListEntry(
                    "PENDING", h_name, a_name, picked_lbl, "", "", self._theme)
                if row:
                    rows.append(row)

        self["list"].setList(rows)
        self["list"].l.setItemHeight(74)


# ==============================================================================
# PLUGIN REGISTRATION
# ==============================================================================
def menu(menuid, **kwargs):
    if menuid == "mainmenu":
        return [("SimplySports", main, "simply_sports", 44)]
    return []

def Plugins(**kwargs):
    list = [
        PluginDescriptor(
            name="SimplySports",
            description="Live Sports Scores, Alerts, Predictions, and EPG by reali22",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="picon.png",
            fnc=main
        ),
        PluginDescriptor(
            name="SimplySports",
            description="Live Sports Scores, Alerts, Predictions, and EPG by reali22",
            where=PluginDescriptor.WHERE_EXTENSIONSMENU,
            fnc=main
        ),
        # CRITICAL: Set session at boot so background notifications work
        # without needing to open the plugin screen first
        PluginDescriptor(
            name="SimplySports Monitor",
            where=PluginDescriptor.WHERE_SESSIONSTART,
            fnc=lambda session, **kwargs: global_sports_monitor.set_session(session)
        )
    ]
    if global_sports_monitor and global_sports_monitor.show_in_menu:
        list.append(PluginDescriptor(
            name="SimplySports",
            description="Live Sports Scores, Alerts, Predictions, and EPG by reali22",
            where=PluginDescriptor.WHERE_MENU,
            fnc=menu
        ))
    return list
