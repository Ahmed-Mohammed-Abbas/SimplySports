from __future__ import absolute_import, division, print_function
import shutil
import os
import threading
import time
import ssl
import hashlib
import sys
from datetime import datetime


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
CURRENT_VERSION = "4.1" # A new style for the notification toast and the Mini bar1.
GITHUB_BASE_URL = "https://raw.githubusercontent.com/Ahmed-Mohammed-Abbas/SimplySports/main/"
CONFIG_FILE = "/etc/enigma2/simply_sports.json"
LOGO_CACHE_DIR = "/tmp/simplysports_logos"

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

def log_dbg(msg):
    try:
        with open(DEBUG_LOG_FILE, "a") as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write("[{}] {}\n".format(ts, msg))
    except:
        pass

# ==============================================================================
# DIAGNOSTIC LOGGING (Verbose - for debugging loading issues)
# ==============================================================================
DIAG_LOG_FILE = "/tmp/simplysport_diag.log"

def log_diag(msg):
    """Verbose diagnostic log with millisecond timestamps for tracing API/UI flow."""
    try:
        import time as _t
        ms = int((_t.time() % 1) * 1000)
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        with open(DIAG_LOG_FILE, "a") as f:
            f.write("[{}.{:03d}] {}\n".format(ts, ms, msg))
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

def get_scaled_pixmap(path, width, height):
    """Load and return a scaled pixmap from file path"""
    if not path or not LoadPixmap: return None
    try:
        return LoadPixmap(cached=True, path=path)
    except: return None

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

            res.append((eListboxPythonMultiContent.TYPE_TEXT, 860, 15, 80, 45, font_idx, RT_HALIGN_CENTER|RT_VALIGN_CENTER, s1, c_h_score, c_sel, c_box, c_box))
            # Hyphen Y=-10
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 940, -10, 40, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "-", c_dim, c_sel))
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 980, 15, 80, 45, font_idx, RT_HALIGN_CENTER|RT_VALIGN_CENTER, s2, c_a_score, c_sel, c_box, c_box))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 860, 0, 200, h-12, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, c_dim, c_sel))

        # Away Logo: 1080 (was 1060) -> 20px gap from 1060.
        if a_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 1080, 5, 60, 60, get_scaled_pixmap(a_png, 60, 60)))
        
        # Away Name: 1150 (was 1130), 520 (Reduced for Time move)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1150, 0, 520, h-12, font_a, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, c_a_name, c_sel))
        
        # Time: 1710, 180 (Ends 1890 -> 30px safe margin)
        font_time = 3 
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1710, 0, 180, h-12, font_time, RT_HALIGN_CENTER|RT_VALIGN_CENTER, time_str, c_dim, c_sel))

        if goal_side == 'home': res.append((eListboxPythonMultiContent.TYPE_TEXT, 785, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "<", c_accent, c_accent))
        elif goal_side == 'away': res.append((eListboxPythonMultiContent.TYPE_TEXT, 1115, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, ">", c_accent, c_accent))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 88, 1880, 2, 0, RT_HALIGN_CENTER, "", 0x303030, 0x303030))
        return res
    except: return []

def UCLListEntry(entry):
    try:
        if len(entry) >= 12:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png, h_score_int, a_score_int = entry[:12]
             has_epg = entry[12] if len(entry) > 12 else False
        else: return []

        if h_png and (not os.path.exists(h_png) or os.path.getsize(h_png) == 0): h_png = None
        if a_png and (not os.path.exists(a_png) or os.path.getsize(a_png) == 0): a_png = None

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

            res.append((eListboxPythonMultiContent.TYPE_TEXT, 860, 15, 80, 45, font_idx, RT_HALIGN_CENTER|RT_VALIGN_CENTER, s1, c_h_score, c_sel, c_box, c_box))
            # Hyphen lifted to -10
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 940, -10, 40, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "-", c_dim, c_sel))
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 980, 15, 80, 45, font_idx, RT_HALIGN_CENTER|RT_VALIGN_CENTER, s2, c_a_score, c_sel, c_box, c_box))
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

        if goal_side == 'home': res.append((eListboxPythonMultiContent.TYPE_TEXT, 785, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "<", c_accent, c_accent))
        elif goal_side == 'away': res.append((eListboxPythonMultiContent.TYPE_TEXT, 1115, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, ">", c_accent, c_accent))
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


# Helper for resizing images
def get_scaled_pixmap(path, width, height):
    try:
        from enigma import ePicLoad, eSize
        sc = ePicLoad()
        # setPara: (width, height, aspectRatioWidth, aspectRatioHeight, useAlpha, rescaleMode, color)
        # Use 1, 1 for aspectRatio to maintain aspect ratio during decode
        sc.setPara((width, height, 1, 1, 0, 1, "#00000000"))
        if sc.startDecode(path, 0, 0, False) == 0:
            ptr = sc.getData()
            return ptr
            return ptr
    except: pass
    return LoadPixmap(path)

def SelectionListEntry(name, is_selected, logo_path=None):
    check_mark = "[x]" if is_selected else "[ ]"
    col_sel = 0x00FF85 if is_selected else 0x9E9E9E
    text_col = 0xFFFFFF if is_selected else 0x9E9E9E
    res = [(name, is_selected)]
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 5, 40, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, check_mark, col_sel, col_sel, None, None))
    
    # Add logo if available
    text_x = 70
    if logo_path and os.path.exists(logo_path) and os.path.getsize(logo_path) > 0:
        try:
            # Resize image to fit 35x35
            pixmap = get_scaled_pixmap(logo_path, 35, 35)
            if pixmap:
                res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 70, 7, 35, 35, pixmap))
                text_x = 115  # Shift text after logo
        except:
            pass
    
    res.append((eListboxPythonMultiContent.TYPE_TEXT, text_x, 5, 700 - (text_x - 70), 40, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, name, text_col, text_col, None, None))
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
        # Track pending goals for scorer details: {match_id: retry_count}
        self.goal_retries = {}
        self.last_states = {}
        self.notified_events = set()  # Track fired notifications: {(match_id, event_type)}
        self.filter_mode = 0 
        self.theme_mode = "default"
        self.transparency = "59"
        
        self.logo_path_cache = {} 
        self.missing_logo_cache = [] 
        self.pending_logos = set()
        self.reminders = [] 
        
        self.timer = eTimer()
        safe_connect(self.timer, self.check_goals)
            
        self.session = None
        self.cached_events = [] 
        self.callbacks = []
        self.status_message = "Initializing..."
        self.notification_queue = []
        self.notification_active = False
        self.current_toast = None  # Reference to active GoalToast for live updates
        self.current_toast_match = None  # (home, away) tuple of active toast
        self.has_changes = True  # Track if data changed since last UI refresh
        
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
        
        self.load_cache()
        
        self.load_config()
        
        self.boot_timer = eTimer()
        
        # Batching variables
        self.batch_queue = []
        self.batch_remaining = 0
        self.batch_is_active = False
        self.batch_timer = eTimer()
        safe_connect(self.batch_timer, self.finalize_batch)
        try: self.boot_timer.callback.append(self.check_goals)
        except AttributeError: self.boot_timer.timeout.get().append(self.check_goals)
        self.boot_timer.start(5000, True)

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
                    self.menu_section = data.get("menu_section", "all")
                    self.show_in_menu = bool(data.get("show_in_menu", True))
                    self.minibar_color_mode = data.get("minibar_color_mode", "default")
                    if self.active: self.timer.start(self._get_timer_interval(), False)
                    # FIX: Ensure timer runs if reminders exist, even if active is False
                    self.ensure_timer_state()
            except: self.defaults()
        else: self.defaults()

    def defaults(self):
        self.filter_mode = 0; self.theme_mode = "default"; self.transparency = "59"
        self.discovery_mode = 0; self.reminders = []; self.menu_section = "all"
        self.show_in_menu = True; self.minibar_color_mode = "default"

    def save_config(self):
        data = {
            "league_index": self.current_league_index, "filter_mode": self.filter_mode,
            "theme_mode": self.theme_mode, "transparency": self.transparency,
            "discovery_mode": self.discovery_mode, "active": self.active,
            "custom_indices": self.custom_league_indices, "is_custom_mode": self.is_custom_mode,
            "reminders": self.reminders, "menu_section": self.menu_section,
            "show_in_menu": self.show_in_menu, "minibar_color_mode": self.minibar_color_mode
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
        old = self.filter_mode
        self.filter_mode = (self.filter_mode + 1) % 4
        log_diag("MONITOR.toggle_filter: {} -> {} (0=Live,1=All,2=Today,3=Tomorrow)".format(old, self.filter_mode))
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
        
        self.save_config(); return self.discovery_mode

    def toggle_activity(self): return self.cycle_discovery_mode()

    def _get_timer_interval(self):
        """Return timer interval in ms: 180s for custom mode (67 leagues), 60s for single league."""
        return 180000 if self.is_custom_mode else 60000

    def ensure_timer_state(self):
        # Timer should run if: 
        # 1. Active (Discovery Mode ON)
        # 2. OR Reminders exist
        should_run = self.active or (len(self.reminders) > 0)
        
        if should_run:
            if not self.timer.isActive():
                self.timer.start(self._get_timer_interval(), False)
                # If we just started, run a check immediately
                self.check_goals()
            else:
                # Timer already running - update interval if mode changed
                pass
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
            self.current_league_index = index; self.last_scores = {}; self.last_states = {}; self.notified_events = set()
            # FIX: Clear cache to remove old events from previous selection
            self.event_map = {}; self.cached_events = []
            self.save_config()
            # Restart timer with single-league interval (60s)
            if self.timer.isActive(): self.timer.start(self._get_timer_interval(), False)
            self.check_goals()
    def set_custom_leagues(self, indices):
        self.custom_league_indices = indices; self.is_custom_mode = True; self.last_scores = {}; self.last_states = {}; self.notified_events = set()
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
                    self.queue_notification(rem["league"], rem["match"], "", rem["label"], "Reminder", "", rem["h_logo"], rem["a_logo"])
                    self.play_stend_sound()
                reminders_triggered = True
            else: active_reminders.append(rem)
        if reminders_triggered: self.reminders = active_reminders; self.save_config()

    def trigger_zap_alert(self, rem):
        if self.session:
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

    def zap_confirmation_callback(self, answer, domain=None):
        if answer and domain:
            try:
                sref = domain[0]
                from enigma import eServiceReference
                self.session.nav.playService(eServiceReference(sref))
            except: pass

    @profile_function("SportsMonitor")
    def check_goals(self, from_ui=False):
        log_diag("CHECK_GOALS: ENTER from_ui={} active={} is_custom={} discovery_mode={} filter_mode={} cached_events={} batch_remaining={} active_requests={}".format(
            from_ui, self.active, self.is_custom_mode, self.discovery_mode, self.filter_mode, len(self.cached_events), self.batch_remaining, len(self.active_requests)))
        self.check_reminders()

        # Guard: When Goal Alert is OFF, only fetch data if explicitly requested by the UI.
        # Timer-driven calls (for reminders) should NOT trigger data fetching to avoid
        # resetting batch state and wasting bandwidth.
        if not self.active and not from_ui:
            log_diag("CHECK_GOALS: SKIPPED (not active, not from_ui)")
            return

        # Show cached data or loading state - but NOT during an active batch
        # (batch processing shows data via finalize_batch at the end)
        if not self.batch_is_active:
            if self.cached_events:
                self.status_message = "Updating..."
                self._trigger_callbacks(True)
            else:
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
            
            # GUARD: Don't start new batch if one is already running
            if self.batch_is_active:
                log_diag("CHECK_GOALS: CUSTOM MODE - SKIPPED (batch already active, remaining={})".format(self.batch_remaining))
                return
            
            # Clear stale data from previous batch
            self.event_map = {}
            self.cached_events = []
            
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
                if url in self.active_requests:
                    self.batch_remaining -= 1
                    skipped += 1
                    continue
                
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

    def save_cache(self):
        # Optimization: Write Coalescing (Max once every 2 mins)
        if time.time() - self.last_cache_save < 120 and self.cached_events:
            return

        try:
            self.last_cache_save = time.time()
            cache_dir = os.path.dirname(self.cache_file)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            
            data = {
                'timestamp': self.last_update,
                'events': self.cached_events
            }
            with open(self.cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print("[SportsMonitor] Cache Save Error: ", e)

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
        log_diag("BATCH_ERROR: url={} error={} batch_remaining={}".format(url, str(failure)[:100], self.batch_remaining - 1))
        if url: self.active_requests.discard(url)
        self.batch_remaining -= 1
        if self.batch_remaining == 0:
            self.finalize_batch()

    def collect_batch_response_incremental(self, body, name, url):
        """Process each response immediately. MUST NEVER RAISE to prevent double-decrement."""
        try:
            if not self.batch_is_active or not self.is_custom_mode:
                self.active_requests.discard(url)
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
            
            if self.batch_remaining == 0:
                self.finalize_batch()
        except Exception as e:
            # Never let exceptions propagate to the deferred chain
            log_diag("BATCH_RESPONSE: UNEXPECTED ERROR in '{}': {}".format(name, e))
            self.active_requests.discard(url)
            self.batch_remaining -= 1
            if self.batch_remaining == 0:
                self.finalize_batch()

    def finalize_batch(self):
        """Cleanup after batch processing"""
        if not self.is_custom_mode:
            return
        
        if self.batch_timer.isActive():
            self.batch_timer.stop()
        
        self.status_message = ""
        self.batch_queue = []
        self.batch_remaining = 0
        self.batch_first_response = None
        
        self.save_cache()
        
        # Clear active flag BEFORE triggering callbacks
        self.batch_is_active = False
        
        log_diag("FINALIZE_BATCH: DONE cached_events={}".format(len(self.cached_events)))
        reactor.callLater(0, self._trigger_callbacks, True)

    def handle_error(self, failure):
        self.status_message = "Connection Error"
        # FIX: Do not wipe cache on transient error
        if not self.cached_events:
            self.cached_events = []
        self._trigger_callbacks(True)
    def handle_error_silent(self, failure): pass

    def _trigger_callbacks(self, data_ready=True):
        """
        Debounced callback triggering
        Only fires once per 300ms to prevent UI flicker
        """
        import time
        now = time.time()
        
        # If less than 300ms since last callback, schedule delayed
        if now - self.last_callback_time < 0.3:
            self.pending_callback = data_ready
            if not self.callback_debounce_timer.isActive():
                self.callback_debounce_timer.start(300, True)
            return
        
        # Execute immediately
        self.last_callback_time = now
        for cb in self.callbacks: 
            cb(data_ready)

    def _execute_pending_callback(self):
        """Execute the pending debounced callback"""
        if self.pending_callback is not None:
            import time
            self.last_callback_time = time.time()
            for cb in self.callbacks:
                cb(self.pending_callback)
            self.pending_callback = None

    @profile_function("SportsMonitor")
    def parse_single_json(self, body, league_name_fixed="", league_url=""): 
        self.process_events_data([(body, league_name_fixed, league_url)], append_mode=False)
        
    @profile_function("SportsMonitor")
    def parse_incremental_json(self, body, league_name_fixed, league_url):
        self.process_events_data([(body, league_name_fixed, league_url)], append_mode=True)

    def parse_multi_json(self, bodies_list): 
        self.process_events_data(bodies_list)

    # queue_notification updated to handle split components
    def queue_notification(self, league, home, away, score, scorer, l_url, h_url, a_url, event_type="default", scoring_team=None, sound_type=None):
        if self.discovery_mode == 0: return
        
        sport_type = self.get_sport_type(league)
        notification = (league, home, away, score, scorer, l_url, h_url, a_url, event_type, scoring_team, sound_type)
        match_key = (home, away)  # identity key for same match
        
        # BASKETBALL MERGE: If same basketball match already in queue, merge scorer text
        if sport_type == 'basketball' and event_type == 'goal':
            for i, existing in enumerate(self.notification_queue):
                ex_match = (existing[1], existing[2])  # home, away
                ex_league_sport = self.get_sport_type(existing[0])
                if ex_match == match_key and ex_league_sport == 'basketball' and existing[8] == 'goal':
                    # Merge: append new scorer text to existing
                    merged_scorer = u"{}  |  {}".format(existing[4], scorer)
                    # Update score to latest and merge scorer
                    self.notification_queue[i] = (
                        existing[0], existing[1], existing[2], score, merged_scorer,
                        existing[5], existing[6], existing[7], existing[8], existing[9], existing[10]
                    )
                    return  # Merged, no new entry needed
            
            # LIVE UPDATE: If current active toast is for the same basketball match, update it
            if self.notification_active and self.current_toast and self.current_toast_match == match_key:
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
        dedup_key = (home, away, score, event_type)
        for existing in self.notification_queue:
            existing_key = (existing[1], existing[2], existing[3], existing[8])
            if existing_key == dedup_key:
                return
        
        # PRIORITY: Soccer first, others after (FIFO within each tier)
        if sport_type == 'soccer':
            # Insert after any existing soccer entries but before non-soccer
            insert_pos = 0
            for i, existing in enumerate(self.notification_queue):
                if self.get_sport_type(existing[0]) == 'soccer':
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
            league, home, away, score, scorer, l_url, h_url, a_url, event_type, scoring_team = item[:10]
            sound_type = item[10] if len(item) > 10 else None
            self.notification_active = True
            self.current_toast_match = (home, away)  # Track for live basketball updates
            if self.session: 
                try:
                    # SYNC: Play sound RIGHT when toast opens
                    if sound_type == 'goal' and self.discovery_mode == 2:
                        self.play_sound()
                    elif sound_type == 'stend' and self.discovery_mode == 2:
                        self.play_stend_sound()
                    
                    self.session.openWithCallback(
                        self.on_toast_closed, GoalToast, 
                        league, home, away, score, scorer, l_url, h_url, a_url, event_type, scoring_team
                    )
                except Exception as e:
                    print("[SimplySport] Error opening notification: {}".format(e))
                    self.notification_active = False
                    self.current_toast = None
                    from twisted.internet import reactor
                    reactor.callLater(2, self.process_queue)
            else:
                self.notification_active = False
                self.current_toast = None
                if self.notification_queue:
                    from twisted.internet import reactor
                    reactor.callLater(5, self.process_queue)
        except Exception as e:
            print("[SimplySport] Critical error in process_queue: {}".format(e))
            self.notification_active = False
            self.current_toast = None
            if self.notification_queue:
                from twisted.internet import reactor
                reactor.callLater(2, self.process_queue)

    def on_toast_closed(self, *args):
        self.notification_active = False
        self.current_toast = None
        self.current_toast_match = None
        from twisted.internet import reactor
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
    def get_scorer_text(self, event, allow_pending=False):
        try:
            # 1. Get Actual Total Score
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            if len(comps) >= 2:
                s1 = int(comps[0].get('score', '0'))
                s2 = int(comps[1].get('score', '0'))
                total_score = s1 + s2
            else: return ""

            details = event.get('competitions', [{}])[0].get('details', [])
            if details:
                # 2. Find all scoring plays
                scoring_plays = []
                for play in details:
                    is_scoring = play.get('scoringPlay', False)
                    text_desc = play.get('type', {}).get('text', '').lower()
                    if is_scoring or "goal" in text_desc:
                        scoring_plays.append(play)

                # 3. Check for Stale Data (API Lag)
                # If we have fewer scoring details than actual goals, the latest goal detail is missing.
                if len(scoring_plays) < total_score:
                    if allow_pending: return None # Signal to wait
                    return "Goal!" 

                # 4. Get Latest Scorer
                if scoring_plays:
                    last_play = scoring_plays[-1]
                    clock = last_play.get('clock', {}).get('displayValue', '')
                    athletes = last_play.get('athletesInvolved', [])
                    if not athletes: athletes = last_play.get('participants', [])
                    
                    if athletes:
                        p_name = athletes[0].get('displayName') or athletes[0].get('shortName')
                        # Format: "Haaland 45'"
                        return "{} {}".format(p_name, clock)
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
                    self.pending_logos.discard(team_id)
                    return data
                
                def on_download_error(err):
                    self.pending_logos.discard(team_id)
                    return None

                self.agent.request(b'GET', url.encode('utf-8')) \
                    .addCallback(readBody) \
                    .addCallback(on_download_success) \
                    .addErrback(on_download_error)
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

    @profile_function("SportsMonitor")
    def process_events_data(self, data_list, single_league_name="", append_mode=False):
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
                    if l_name: league_name = l_name
                    else: league_name = league_obj.get('name') or league_obj.get('shortName') or ""
                    events = data.get('events', [])
                    
                    sport_type = get_sport_type(l_url)
                    
                    for ev in events:
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
                            
                            # Check for changes
                            old_ev = self.event_map.get(eid)
                            
                            # Simple change detection: status or score or clock
                            # For robust diffing, we might need deep compare, but status/score is usually enough
                            is_changed = True
                            if old_ev:
                                old_status = old_ev.get('status', {}).get('type', {}).get('state')
                                new_status = processed_ev.get('status', {}).get('type', {}).get('state')
                                
                                old_comps = old_ev.get('competitions', [{}])[0].get('competitors', [])
                                new_comps = processed_ev.get('competitions', [{}])[0].get('competitors', [])
                                
                                if old_status == new_status and len(old_comps) == len(new_comps):
                                     # Check scores
                                     scores_match = True
                                     for i in range(len(old_comps)):
                                         if old_comps[i].get('score') != new_comps[i].get('score'):
                                             scores_match = False; break
                                     if scores_match: is_changed = False
                            
                            # =====================================================
                            # LOGO URL/ID CONSTRUCTION - RUN FOR ALL EVENTS
                            # This ensures every event has logo data, not just changed ones
                            # =====================================================
                            comps = processed_ev.get('competitions', [{}])[0].get('competitors', [])
                            league_name = processed_ev.get('league_name', '')
                            league_url = processed_ev.get('league_url', '')
                            sport_cdn = self.get_cdn_sport_name(league_name)
                            event_sport_type = get_sport_type(league_url)
                            
                            # Skip logo construction for racing/golf/combat (no team logos)
                            if len(comps) >= 2 and event_sport_type not in [SPORT_TYPE_RACING, SPORT_TYPE_GOLF, SPORT_TYPE_COMBAT]:
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
                                
                                processed_ev['h_logo_url'] = h_logo
                                processed_ev['a_logo_url'] = a_logo
                                processed_ev['h_logo_id'] = str(h_id) if h_id else ''
                                processed_ev['a_logo_id'] = str(a_id) if a_id else ''
                                
                                # Pre-fetch logos for all events (cache warmup)
                                if h_logo and h_id: self.prefetch_logo(h_logo, h_id)
                                if a_logo and a_id: self.prefetch_logo(a_logo, a_id)
                            
                            self.event_map[eid] = processed_ev
                            if is_changed: 
                                changed_events.append(processed_ev)
                                has_changes = True
                                
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
            
            # Only set status message if there's an actual issue (no matches)
            if len(self.cached_events) == 0: self.status_message = "No Matches Found"
            
            # Set flag for UI to know if it needs to rebuild
            self.has_changes = has_changes

            # Determine loop for notifications
            loop_events = changed_events if changed_events else unique_list
            
            live_count = 0
            
            # Cleanup old flags
            now = time.time()
            keys_to_del = [mid for mid, info in self.goal_flags.items() if now - info['time'] > 60]
            for k in keys_to_del: del self.goal_flags[k]

            for event in unique_list:
                status = event.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                if state == 'in': live_count += 1
                
                # OPTIMIZATION: If event didn't change, we don't need to check for goals/notifications
                # unless we want to ensure eventual consistency. 
                # Strict check: id in changed_events
                # But 'changed_events' contains full objects.
                # Let's map IDs for fast lookup
                # (Note: For very first run, everything is changed)
                
            # Process notifications only for changed events (or all if first run/append)
            # Actually, `last_states` handles the "diff" logic for notifications natively.
            # So passing all events is fine, but iterating 200 events is cheap in Python usually.
            # The real cost was the parsing above.
            # We will stick to iterating `changed_events` for the heavy logic if possible, 
            # BUT `process_queue` etc need to run.
            # Let's keep the loop over `changed_events` for notifications to save cycles.
            
            for event in changed_events:
                status = event.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                if len(comps) < 2: continue 
                league_name = event.get('league_name', '')
                league_url = event.get('league_url', '')
                
                # Skip individual sports EXCEPT Tennis (we want flags)
                event_sport_type = get_sport_type(league_url)
                if event_sport_type in [SPORT_TYPE_RACING, SPORT_TYPE_GOLF, SPORT_TYPE_COMBAT]:
                    continue
                
                # Fix: Tennis flags reversed. Force index 0=Home, 1=Away to match process_events_data/MiniBar
                if event_sport_type == SPORT_TYPE_TENNIS:
                    team_h = comps[0]
                    team_a = comps[1]
                else:
                    team_h = next((t for t in comps if t.get('homeAway') == 'home'), None)
                    team_a = next((t for t in comps if t.get('homeAway') == 'away'), None)
                    if not team_h and len(comps) > 0: team_h = comps[0]
                    if not team_a and len(comps) > 1: team_a = comps[1]

                # Extract team names for notifications
                home = "Home"
                if team_h:
                    if 'athlete' in team_h:
                        ath = team_h.get('athlete', {})
                        home = ath.get('shortName') or ath.get('displayName') or "Player 1"
                    else:
                        home = team_h.get('team', {}).get('shortDisplayName') or "Home"

                away = "Away"
                if team_a:
                    if 'athlete' in team_a:
                        ath = team_a.get('athlete', {})
                        away = ath.get('shortName') or ath.get('displayName') or "Player 2"
                    else:
                        away = team_a.get('team', {}).get('shortDisplayName') or "Away"
                
                # Read logo data (already set in main event processing loop)
                h_logo = event.get('h_logo_url', '')
                a_logo = event.get('a_logo_url', '')

                # FIX: For Tennis, use Sets Won (calculated) instead of points/games
                if event_sport_type == SPORT_TYPE_TENNIS:
                    # Calculate sets won
                    ts1, ts2 = calculate_tennis_scores(comps, state)
                    # For notifications, we want the Sets count
                    h_score = int(ts1)
                    a_score = int(ts2)
                else:
                    h_score = int(team_h.get('score', '0')) if team_h else 0
                    a_score = int(team_a.get('score', '0')) if team_a else 0

                # Use STABLE ID for tracking, not names
                match_id = event.get('id', home + "_" + away)
                score_str = str(h_score) + "-" + str(a_score)

                prev_state = self.last_states.get(match_id)
                if self.active and self.session and prev_state:
                    should_play_stend = (self.discovery_mode == 2 and self.get_sport_type(league_name) == 'soccer')
                    
                    # Ensure score string is "1-0" not "1 - 0"
                    score_fmt = "{}-{}".format(h_score, a_score)
                    
                    if state == 'in' and prev_state == 'pre':
                        # DEDUP: Only fire start notification once per match
                        if (match_id, 'start') not in self.notified_events:
                            event_sport_type = get_sport_type(league_url)
                            if event_sport_type != SPORT_TYPE_TENNIS:
                                 self.notified_events.add((match_id, 'start'))
                                 stend_sound = 'stend' if should_play_stend else None
                                 self.queue_notification(league_name, home, away, score_fmt, "MATCH STARTED", "", h_logo, a_logo, "start", None, sound_type=stend_sound)
                    elif state == 'post' and prev_state == 'in':
                        # DEDUP: Only fire end notification once per match
                        if (match_id, 'end') not in self.notified_events:
                            self.notified_events.add((match_id, 'end'))
                            stend_sound = 'stend' if should_play_stend else None
                            self.queue_notification(league_name, home, away, score_fmt, "FULL TIME", "", h_logo, a_logo, "end", None, sound_type=stend_sound)

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
                                    # RETRY LOGIC for API LAG
                                    # BASKETBALL SPECIAL HANDLING: No Scorer Name, Visual Only, "Smart Score"
                                    if sport_type == 'basketball':
                                        points = max(diff_h, diff_a)
                                        scorer_text = "+{} POINTS".format(points)
                                    elif sport_type == 'football':
                                        # NFL SPECIAL HANDLING: Contextual Text, Instant Update
                                        points = max(diff_h, diff_a)
                                        if points == 6: scorer_text = "TOUCHDOWN!"
                                        elif points == 3: scorer_text = "FIELD GOAL"
                                        elif points == 1: scorer_text = "EXTRA POINT"
                                        elif points == 2: scorer_text = "SAFETY / 2PT"
                                        else: scorer_text = "SCORE (+{})".format(points)
                                    else:
                                        scorer_text = self.get_scorer_text(event, allow_pending=True)
                                        
                                        if scorer_text is None:
                                            # Data is stale, wait for next cycle
                                            retries = self.goal_retries.get(match_id, 0)
                                            if retries < 4: # Wait up to ~1 min (4 * 15s)
                                                self.goal_retries[match_id] = retries + 1
                                                continue # SKIP notification & SKIP updating last_scores
                                            else:
                                                # Max retries reached, fallback to "Goal"
                                                scorer_text = self.get_scorer_text(event, allow_pending=False)
                                                if match_id in self.goal_retries: del self.goal_retries[match_id]
                                        else:
                                            # Success, clear retry
                                            if match_id in self.goal_retries: del self.goal_retries[match_id]

                                    if diff_h > 0:
                                        goal_sound = 'goal' if sport_type != 'basketball' else None
                                        self.queue_notification(league_name, home, away, score_display, scorer_text, "", h_logo, a_logo, "goal", "home", sound_type=goal_sound)
                                        self.goal_flags[match_id] = {'time': time.time(), 'team': 'home'}
                                    
                                    if diff_a > 0:
                                        goal_sound = 'goal' if sport_type != 'basketball' else None
                                        self.queue_notification(league_name, home, away, score_display, scorer_text, "", h_logo, a_logo, "goal", "away", sound_type=goal_sound)
                                        self.goal_flags[match_id] = {'time': time.time(), 'team': 'away'}
                            except: pass
                    # Update score ONLY if we didn't 'continue' above
                    self.last_scores[match_id] = score_str

            # ADAPTIVE POLLING: 15s for Live, 60s for others (single league only)
            if self.active and not self.batch_is_active:
                new_interval = 15000 if live_count > 0 else self._get_timer_interval()
                self.timer.start(new_interval, False)

            # Only trigger UI callbacks if NOT in batch mode
            # (batch mode triggers a single callback in finalize_batch)
            if not self.batch_is_active:
                for cb in self.callbacks: cb(True)
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
    if theme_mode == "ucl": col_label, col_val, col_bg = 0x00ffff, 0xffffff, 0x0e1e5b
    else: col_label, col_val, col_bg = 0x00FF85, 0xFFFFFF, 0x33190028
    # Layout: Centered Block. Total width ~1320px
    # Home (400) | Label (520) | Away (400)
    h_x, h_w = 140, 400; l_x, l_w = 540, 520; a_x, a_w = 1060, 400
    res = [None]
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 100, 48, 1400, 2, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, 1))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, l_x, 0, l_w, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(label).upper(), col_label, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, h_x, 0, h_w, 50, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, str(home_val), col_val, 0xFFFFFF))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, a_x, 0, a_w, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(away_val), col_val, 0xFFFFFF))
    return res

def EventListEntry(label, home_val, away_val, theme_mode):
    """3-Column Layout for Events (Goals/Cards) - Optimized for 1600px Width"""
    if theme_mode == "ucl": col_label, col_val, col_bg = 0x00ffff, 0xffffff, 0x0e1e5b
    else: col_label, col_val, col_bg = 0x00FF85, 0xFFFFFF, 0x33190028
    
    # Centered Layout for 1600px width: Center column at 800
    l_x, l_w = 740, 120   # Time label centered (740 + 60 = 800 center)
    h_x, h_w = 90, 640    # Home events on left, right-aligned towards center
    a_x, a_w = 870, 640   # Away events on right, left-aligned from center

    res = [None]
    # Background line
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 48, 1550, 2, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, 1))
    # Time/Label (Center)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, l_x, 0, l_w, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, str(label), col_label, 0xFFFFFF))
    # Home Event (Right)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, h_x, 0, h_w, 50, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, str(home_val), col_val, 0xFFFFFF))
    # Away Event (Left)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, a_x, 0, a_w, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, str(away_val), col_val, 0xFFFFFF))
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
    else: 
        col_text = 0x00FF85 if is_header else 0xFFFFFF
        col_bg = 0x33190028 if is_header else None
    
    flags = RT_HALIGN_CENTER | RT_VALIGN_CENTER
    if align == "left": flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER
    
    res = [None]
    # Background line if header
    if is_header:
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 40, 0, 1520, 50, 0, RT_HALIGN_CENTER, "", col_bg, col_bg, 1))
    
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 40, 0, 1520, 50, 0, flags, str(text), col_text, 0xFFFFFF))
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
            
            # Helper to clean number strings
            def clean_num(val):
                try:
                    f = float(val)
                    if f == int(f): return str(int(f))
                    return str(val)
                except: return str(val)

            # Helper to parse a list of entries and return sorted list
            def parse_entries(entry_list):
                parsed = []
                for entry in entry_list:
                    try:
                        team_data = entry.get('team', {})
                        team_name = team_data.get('displayName', '') or team_data.get('shortDisplayName', '') or team_data.get('name', 'Unknown')
                        
                        stats = entry.get('stats', [])
                        stats_map = {}
                        for stat in stats:
                            stat_name = stat.get('name', '') or stat.get('abbreviation', '')
                            stats_map[stat_name.lower()] = stat.get('value', stat.get('displayValue', '0'))
                        
                        # Get explicit rank if available, else 999
                        rank_val = 999
                        try: rank_val = int(stats_map.get('rank', stats_map.get('position', 999)))
                        except: pass

                        # Get win pct for sorting
                        win_pct = 0.0
                        try: win_pct = float(stats_map.get('winpercent', stats_map.get('pct', 0)))
                        except: pass
                        
                        # Also get wins for tie-breaking
                        wins = 0
                        try: wins = int(stats_map.get('wins', stats_map.get('w', 0)))
                        except: pass

                        pos = str(rank_val)
                        played = clean_num(stats_map.get('gamesplayed', stats_map.get('played', stats_map.get('p', '-'))))
                        won = clean_num(stats_map.get('wins', stats_map.get('w', '-')))
                        draw = clean_num(stats_map.get('ties', stats_map.get('draws', stats_map.get('d', '-'))))
                        lost = clean_num(stats_map.get('losses', stats_map.get('l', '-')))
                        gd = clean_num(stats_map.get('pointdifferential', stats_map.get('goaldifference', stats_map.get('gd', '-'))))
                        pts = clean_num(stats_map.get('points', stats_map.get('pts', '-')))
                        
                        # Fallback for position
                        if pos == '999':
                            pos = stats_map.get('playoffseeed', stats_map.get('overall rank', '-'))

                        parsed.append({
                            'pos': pos, 'team': team_name, 'p': played, 'w': won, 'd': draw, 'l': lost, 'gd': gd, 'pts': pts,
                            'sort_rank': rank_val, 'sort_pct': win_pct, 'sort_wins': wins, 'raw': entry
                        })
                    except: continue
                
                # Sort by Rank Ascending (if valid rank exists), otherwise by Win% Descending
                parsed.sort(key=lambda x: x['sort_rank'] if x['sort_rank'] != 999 else (-x['sort_pct'], -x['sort_wins']))
                return parsed

            # Clear existing rows
            self.standings_rows = []

            # --- NBA SPECIAL HANDLING ---
            # NBA data usually comes as 'children' (Conferences) -> 'standings' -> 'entries'
            is_nba = False
            if self.league_url: 
                 if "nba" in self.league_url.lower() or "basketball" in self.league_url.lower():
                     is_nba = True # Broader check for basketball leagues behaving like NBA
            
            children = data.get('children', [])
            
            # If we have children structure and it's likely NBA-like
            if is_nba and children:
                all_entries_flat = []
                
                # 1. Gather all data
                for child in children:
                    conf_name = child.get('name', 'Conference').upper()
                    standings_node = child.get('standings', {})
                    entries = standings_node.get('entries', [])
                    if not entries: entries = child.get('entries', [])
                    
                    parsed_conf = parse_entries(entries)
                    
                    # Add to master list
                    all_entries_flat.extend(parsed_conf)
                    
                    # Store for conference display
                    child['parsed_entries'] = parsed_conf
                    child['conf_name'] = conf_name
                
                # 2. OVERALL TABLE (Only if we successfully parsed entries)
                if all_entries_flat:
                    self.standings_rows.append(StandingTableEntry("", "OVERALL STANDINGS", "", "", "", "", "", "", self.theme, is_header=True))
                    self.standings_rows.append(StandingTableEntry("#", "TEAM", "P", "W", "D", "L", "GD", "PTS", self.theme, is_header=True))
                    
                    # Re-sort flat list by win pct descending for overall
                    all_entries_flat.sort(key=lambda x: (-x['sort_pct'], -x['sort_wins']))
                    
                    for idx, item in enumerate(all_entries_flat):
                        rank = str(idx + 1)
                        self.standings_rows.append(StandingTableEntry(rank, item['team'], item['p'], item['w'], item['d'], item['l'], item['gd'], item['pts'], self.theme))
                    
                    self.standings_rows.append(StandingTableEntry("", "", "", "", "", "", "", "", self.theme)) # Spacer

                # 3. CONFERENCES
                for child in children:
                    if 'parsed_entries' not in child: continue
                    conf_name = child.get('conf_name', 'CONFERENCE')
                    entries = child['parsed_entries']
                    
                    self.standings_rows.append(StandingTableEntry("", conf_name, "", "", "", "", "", "", self.theme, is_header=True))
                    self.standings_rows.append(StandingTableEntry("#", "TEAM", "P", "W", "D", "L", "GD", "PTS", self.theme, is_header=True))
                    
                    for item in entries:
                        self.standings_rows.append(StandingTableEntry(item['pos'], item['team'], item['p'], item['w'], item['d'], item['l'], item['gd'], item['pts'], self.theme))
                    
                    self.standings_rows.append(StandingTableEntry("", "", "", "", "", "", "", "", self.theme)) # Spacer

            else:
                # --- STANDARD / SOCCER HANDLING ---
                raw_entries = []
                standings_data = data.get('standings', [])
                if isinstance(standings_data, list):
                     for group in standings_data:
                        if isinstance(group, dict):
                            raw_entries.extend(group.get('entries', []))
                
                if not raw_entries:
                    raw_entries = data.get('entries', [])
                    if not raw_entries and children:
                        # flatten children if not NBA but has children
                        for child in children:
                            raw_entries.extend(child.get('standings', {}).get('entries', []))
                
                parsed = parse_entries(raw_entries)
                
                self.standings_rows.append(StandingTableEntry("#", "TEAM", "P", "W", "D", "L", "GD", "PTS", self.theme, is_header=True))
                
                for item in parsed:
                     self.standings_rows.append(StandingTableEntry(item['pos'], item['team'], item['p'], item['w'], item['d'], item['l'], item['gd'], item['pts'], self.theme))

            if len(self.standings_rows) <= 1:
                self.standings_rows.append(StandingTableEntry("-", "No standings data available", "-", "-", "-", "-", "-", "-", self.theme))
            
            self.current_page = 0
            self.update_display()
            
        except Exception as e:
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
                    import time
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
            import time
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
        if not self.summary_url and self.fallback_event_data:
             self.use_fallback_data()
             return

        from twisted.web.client import getPage
        if self.summary_url:
            getPage(self.summary_url.encode('utf-8')).addCallback(self.parse_details).addErrback(self.error_details)
        else:
            self.error_details(None)

    def error_details(self, error):
        if self.fallback_event_data:
            self.use_fallback_data()
        else:
            self["loading"].setText("Error loading details.")

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
            state = status.get('type', {}).get('state', '')
            detail = status.get('type', {}).get('detail', '')
            
            # Competitors - check top-level AND inside competitions (tennis uses competitions[0].competitors)
            comps = data.get('competitors', [])
            if not comps:
                comps = data.get('competitions', [{}])[0].get('competitors', [])
            h_team = {}; a_team = {}
            
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
                    self.download_logo(h_logo, "h_logo")
                    self.download_logo(a_logo, "a_logo")
                except: pass
                
            else:
                # Standard Logic
                h_name = h_team.get('athlete', {}).get('displayName') or h_team.get('team', {}).get('displayName', 'Home')
                a_name = a_team.get('athlete', {}).get('displayName') or a_team.get('team', {}).get('displayName', 'Away')
                self["h_name"].setText(str(h_name))
                self["a_name"].setText(str(a_name))
                
                try:
                    h_logo = h_team.get('team', {}).get('logo', '') or h_team.get('athlete', {}).get('flag', {}).get('href', '')
                    a_logo = a_team.get('team', {}).get('logo', '') or a_team.get('athlete', {}).get('flag', {}).get('href', '')
                    self.download_logo(h_logo, "h_logo")
                    self.download_logo(a_logo, "a_logo")
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
                    if flag1_url: self.download_logo(flag1_url, "h_logo")
                    if flag2_url: self.download_logo(flag2_url, "a_logo")
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
            if game_status == 'in': status_txt = "LIVE - In Progress"
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
class GoalToast(Screen):
    def __init__(self, session, league_text, home_text, away_text, score_text, scorer_text, l_url, h_url, a_url, event_type="default", scoring_team=None):
        # Cache Directory
        self.logo_cache_path = "/tmp/simplysports/logos/"
        if not os.path.exists(self.logo_cache_path):
            try: os.makedirs(self.logo_cache_path)
            except: pass

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
            'goal':   '#0000BB55', 'card':  '#00EECC00',
            'start':  '#0000AACC', 'end':   '#0000AACC',
            'default':'#0000BB55'
        }
        border_color = accent_colors.get(event_type, '#0000BB55')

        # Text highlight colors
        h_color = "#00FFFFFF"; a_color = "#00FFFFFF"; score_color = "#00FFFFFF"
        if event_type == 'goal':
            if scoring_team == 'home': h_color = "#0066FF66"
            elif scoring_team == 'away': a_color = "#0066FF66"
        elif event_type in ['start', 'end']:
            score_color = "#0066DDFF"

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

            # --- SCORER TEXT (above band, centered) ---
            u'<widget name="scorer" position="200,5" size="550,30" font="Regular;21" '
            u'foregroundColor="{sfg}" backgroundColor="{bg}" transparent="1" valign="center" halign="center" zPosition="3" />'  

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

            # --- LEAGUE NAME (below band, centered) ---
            u'<widget name="league" position="200,90" size="550,28" font="Regular;17" '
            u'foregroundColor="{lfg}" backgroundColor="{bg}" transparent="1" valign="center" halign="center" zPosition="3" />'

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
        
        self["h_logo"] = Pixmap()
        self["a_logo"] = Pixmap()
        
        self.h_url = h_url
        self.a_url = a_url
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
        self.current_y = -100
        self.target_y = 10
        self.toast_width = 950
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
            "ok": self.close, "cancel": self.close, 
            "red": self.close, "green": self.close, "yellow": self.close, "blue": self.close,
            "up": self.close, "down": self.close, "left": self.close, "right": self.close
        }, -1)
        
        self.onLayoutFinish.append(self.start_animation)

    def start_animation(self):
        self.force_top()
        self.anim_timer.start(20, False)

    def animate_entry(self):
        # FIX: Preserve horizontal centering while animating Y
        try:
            step = 10
            if self.current_y < self.target_y:
                self.current_y += step
                from enigma import getDesktop
                desktop = getDesktop(0)
                dw = desktop.size().width()
                # Center X: (DesktopWidth - ToastWidth) / 2
                center_x = (dw - self.toast_width) // 2
                self.instance.move(ePoint(center_x, self.current_y))
            else:
                self.anim_timer.stop()
                self.timer.start(self.duration_ms, True)
        except:
            self.anim_timer.stop()
            self.timer.start(self.duration_ms, True)

    def force_top(self):
        try: self.instance.setZPosition(10)
        except: pass

    def load_logos(self):
        self.load_image(self.h_url, "h_logo")
        self.load_image(self.a_url, "a_logo")

    def load_image(self, url, widget_name):
        if not url:
            self[widget_name].hide()
            return

        try:
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            target_path = self.logo_cache_path + url_hash + ".png"
            
            # Use 100 bytes as minimum for a valid PNG (prevents 1-byte corrupt files from being hits)
            if os.path.exists(target_path) and os.path.getsize(target_path) > 100:
                if self[widget_name].instance:
                    self[widget_name].instance.setPixmapFromFile(target_path)
                    self[widget_name].instance.setScale(1) # Robustness
                    self[widget_name].show()
            else:
                downloadPage(url.encode('utf-8'), target_path).addCallback(
                    self.image_downloaded, widget_name, target_path
                ).addErrback(self.image_error)
        except:
             self[widget_name].hide()

    def image_downloaded(self, data, widget_name, target_path):
        if self[widget_name].instance:
            self[widget_name].instance.setPixmapFromFile(target_path)
            self[widget_name].instance.setScale(1) # Robustness
            self[widget_name].show()

    def image_error(self, error): pass

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
        if not url: return
        try:
            import hashlib
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            target_path = self.logo_cache_path + url_hash + ".png"
            
            # Use 100 bytes minimum
            if os.path.exists(target_path) and os.path.getsize(target_path) > 100:
                if self[widget_name].instance:
                    self[widget_name].instance.setPixmapFromFile(target_path)
                    self[widget_name].instance.setScale(1) 
                    self[widget_name].show()
            else:
                downloadPage(url.encode('utf-8'), target_path).addCallback(
                    self.image_downloaded, widget_name, target_path
                ).addErrback(self.image_error)
        except: pass

    def image_downloaded(self, data, widget_name, target_path):
        if self[widget_name].instance:
            self[widget_name].instance.setPixmapFromFile(target_path)
            self[widget_name].instance.setScale(1)
            self[widget_name].show()

    def image_error(self, error): pass

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
    
    def __init__(self, session):
        Screen.__init__(self, session)
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
        
        self["header"] = Label("Select Custom Leagues")
        self["list"] = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
        self["list"].l.setFont(0, gFont("SimplySportFont", 28))
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
        self.sorted_indices = []  # Track original indices after sorting
        self.league_logos = {}  # Cache for downloaded league logos
        self.logo_path = "/tmp/simplysports/league_logos/"
        if not os.path.exists(self.logo_path):
            try: os.makedirs(self.logo_path)
            except: pass
        self.onLayoutFinish.append(self.load_list)

    def get_league_priority(self, league_name):
        """Return priority value for sorting (lower = higher priority)"""
        # Use exact matching only to avoid "Premier League" matching "Canadian Premier League"
        for i, major in enumerate(self.MAJOR_LEAGUES):
            if league_name == major:
                return i
        return 1000  # Non-major leagues go last

    def load_list(self):
        current_indices = global_sports_monitor.custom_league_indices
        
        # Create list of (original_idx, name, is_selected, priority) for sorting
        league_items = []
        for i in range(len(DATA_SOURCES)):
            name = DATA_SOURCES[i][0]
            is_selected = i in current_indices
            priority = self.get_league_priority(name)
            league_items.append((i, name, is_selected, priority))
        
        # Sort by priority (major leagues first), then by name
        league_items.sort(key=lambda x: (x[3], x[1]))
        
        # Store sorted order
        self.sorted_indices = [item[0] for item in league_items]
        self.selections = [item[2] for item in league_items]
        
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
        # ESPN league logos follow pattern: https://a.espncdn.com/i/leaguelogos/{sport}/500/{league_id}.png
        # For common leagues, use known IDs
        KNOWN_LOGOS = {
            "eng.1": ("soccer", "23"),   # Premier League
            "esp.1": ("soccer", "15"),   # La Liga
            "ita.1": ("soccer", "12"),   # Serie A
            "ger.1": ("soccer", "10"),   # Bundesliga
            "fra.1": ("soccer", "9"),    # Ligue 1
            "uefa.champions": ("soccer", "2"),
            "uefa.europa": ("soccer", "35"),
            "nba": ("nba", "500"),
            "nfl": ("nfl", "500"),
            "nhl": ("nhl", "500"),
            "mlb": ("mlb", "500"),
        }
        for key, (sport, lid) in KNOWN_LOGOS.items():
            if key in api_url:
                return "https://a.espncdn.com/i/leaguelogos/{}/500/{}.png".format(sport, lid)
        return None
    
    def logo_downloaded(self, result, idx, logo_file):
        self.league_logos[idx] = logo_file
        self.refresh_list()
    
    def logo_error(self, error):
        pass

    def refresh_list(self):
        list_content = []
        for sorted_idx, original_idx in enumerate(self.sorted_indices):
            name = DATA_SOURCES[original_idx][0]
            is_selected = self.selections[sorted_idx]
            logo_path = self.league_logos.get(sorted_idx, None)
            list_content.append(SelectionListEntry(name, is_selected, logo_path))
        self["list"].setList(list_content)

    def toggle(self):
        idx = self["list"].getSelectedIndex()
        if idx is not None and 0 <= idx < len(self.selections):
            self.selections[idx] = not self.selections[idx]
            self.refresh_list()

    def save(self):
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

            self.skin = """<screen position="0,{y}" size="{w},{h}" title="Sports Ticker Bottom" backgroundColor="#40000000" flags="wfNoBorder"><eLabel position="0,0" size="{w},{h}" backgroundColor="{bg}" zPosition="0" /><eLabel position="0,0" size="5,{h}" backgroundColor="{sl}" zPosition="1" /><eLabel position="{rend},{h}" size="5,{h}" backgroundColor="{sr}" zPosition="1" /><widget name="lbl_league" position="{xl},0" size="{wl},{h}" font="{fl}" foregroundColor="{tlg}" backgroundColor="{bg}" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_home" position="{xh},0" size="{wh},38" font="{fn}" foregroundColor="#FFFFFF" backgroundColor="{bg}" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="lbl_home_sc" position="{xh},{ysc}" size="{wh},24" font="{fsc}" foregroundColor="#cccccc" backgroundColor="{bg}" transparent="1" halign="right" valign="top" zPosition="2" /><widget name="h_logo" position="{xhl},4" size="{ls},{ls}" alphatest="blend" scale="1" zPosition="2" /><eLabel position="{xs},0" size="{ws},{h}" backgroundColor="{sbg}" zPosition="1" /><widget name="lbl_score" position="{xs},0" size="{ws},{h}" font="{fl}" foregroundColor="{sfg}" backgroundColor="{sbg}" transparent="1" halign="center" valign="center" zPosition="3" /><widget name="a_logo" position="{xal},4" size="{ls},{ls}" alphatest="blend" scale="1" zPosition="2" /><widget name="lbl_away" position="{xa},0" size="{wa},38" font="{fn}" foregroundColor="#FFFFFF" backgroundColor="{bg}" transparent="1" halign="left" valign="center" zPosition="2" /><widget name="lbl_away_sc" position="{xa},{ysc}" size="{wa},24" font="{fsc}" foregroundColor="#cccccc" backgroundColor="{bg}" transparent="1" halign="left" valign="top" zPosition="2" /><widget name="lbl_status" position="{xst},0" size="{wst},{h}" font="{fs}" foregroundColor="#FFFFFF" backgroundColor="{bg}" transparent="1" halign="right" valign="center" zPosition="2" /><widget name="lbl_time" position="{xt},0" size="{wt},{h}" font="{fs}" foregroundColor="{ttm}" backgroundColor="{bg}" transparent="1" halign="right" valign="center" zPosition="2" /></screen>""".format(y=bar_y-6, w=width, h=bar_h, rend=width-5, fl=font_lg, fn=font_nm, fs=font_sm, fsc=font_sc, ls=logo_s, xl=x_league, wl=w_league, xh=x_home_name, wh=w_home_name, xhl=x_h_logo, xs=x_score, ws=w_score, xst=x_status, wst=w_status, xal=x_a_logo, xa=x_away_name, wa=w_away_name, xt=x_time, wt=w_time, ysc=y_sc, bg=c_bg_main, sl=c_strip_l, sr=c_strip_r, sbg=c_score_bg, sfg=c_score_fg, tlg=c_text_lg, ttm=c_text_tm)

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
        global_sports_monitor.check_goals(from_ui=True)

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
        if not url: self[widget_name].hide(); return

        # Fallback for missing ID
        if not img_id or img_id == '0' or img_id == '':
            import hashlib
            img_id = hashlib.md5(url.encode('utf-8')).hexdigest()[:10]
        
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

        # UCL Broadcast Band Style (matching GoalToast)
        # Transparent bg, metallic band, large logos at edges
        self.skin = (
            u'<screen position="center,10" size="950,120" title="Sports Ticker" flags="wfNoBorder" backgroundColor="#FF000000">'

            # --- SCORER/STATUS TEXT (above band, centered) ---
            u'<widget name="lbl_status" position="200,5" size="550,30" font="Regular;21" '
            u'foregroundColor="#00FFFFFF" backgroundColor="#FF000000" transparent="1" valign="center" halign="center" zPosition="3" />'

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
            u'<widget name="lbl_home" position="100,42" size="290,38" font="Regular;32" '
            u'foregroundColor="#00FFFFFF" backgroundColor="#002C4060" valign="center" halign="right" zPosition="4" />'
            u'<widget name="lbl_away" position="560,42" size="290,38" font="Regular;32" '
            u'foregroundColor="#00FFFFFF" backgroundColor="#002C4060" valign="center" halign="left" zPosition="4" />'

            # --- LARGE LOGOS (overlapping band at edges) ---
            u'<widget name="h_logo" position="5,18" size="85,85" alphatest="blend" scale="1" zPosition="6" />'
            u'<widget name="a_logo" position="860,18" size="85,85" alphatest="blend" scale="1" zPosition="6" />'

            # --- LEAGUE NAME (below band, centered) ---
            u'<widget name="lbl_league" position="200,90" size="550,28" font="Regular;17" '
            u'foregroundColor="#00FFFFFF" backgroundColor="#FF000000" transparent="1" valign="center" halign="center" zPosition="3" />'

            u'</screen>'
        )

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
        global_sports_monitor.check_goals(from_ui=True)

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
        if not url: self[widget_name].hide(); return
        
        # Fallback for missing ID
        if not img_id or img_id == '0' or img_id == '':
            import hashlib
            img_id = hashlib.md5(url.encode('utf-8')).hexdigest()[:10]
        
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
        
        # Logo Refresh Timer (Batched UI updates)
        self.logo_refresh_timer = eTimer()
        safe_connect(self.logo_refresh_timer, lambda: self.refresh_ui(True))
        
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
        self.onLayoutFinish.append(self.start_ui); self.onClose.append(self.cleanup)

    def update_clock(self):
        """Update clock display with current time"""
        try:
            now = datetime.datetime.now()
            self["clock"].setText(now.strftime("%H:%M"))
        except: pass

    def start_ui(self):
        log_diag("SCREEN.start_ui: is_custom={} filter_mode={} discovery_mode={} active={}".format(
            self.monitor.is_custom_mode, self.monitor.filter_mode, self.monitor.discovery_mode, self.monitor.active))
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
        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
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

        # Skip rebuild if no changes and we already have data (unless forced)
        if not force_refresh and not self.monitor.has_changes and self.current_match_ids and events:
            log_diag("REFRESH_UI: SKIPPED (no changes, has data)")
            return
        
        if not events:
            # If we already have matches and loading is in progress, keep old list to avoid flicker
            if self.current_match_ids and ("Loading" in self.monitor.status_message or "Fetching" in self.monitor.status_message):
                log_diag("REFRESH_UI: SKIPPED (loading in progress, keeping old data)")
                return
            log_diag("REFRESH_UI: No events - showing '{}'".format(self.monitor.status_message or 'No Matches Found'))
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
                # --- OPTIMIZATION: FILTER FIRST ---
                # Check filter conditions BEFORE processing heavy logic (date/status)
                status = event.get('status', {}); state = status.get('type', {}).get('state', 'pre')
                ev_date = event.get('date', '')[:10]
                mode = self.monitor.filter_mode
                
                # Filter Logic
                if mode == 0 and state != 'in': continue        # Live Only
                if mode == 2 and ev_date != today_str: continue # Today
                if mode == 3 and ev_date != tom_str: continue   # Tomorrow
                
                # Special Request: Exclude Tennis from "All Matches" (Mode 1) due to volume
                if mode == 1:
                    l_url_chk = event.get('league_url', '')
                    if get_sport_type(l_url_chk) == SPORT_TYPE_TENNIS:
                        continue
                
                # If we passed filters, proceed with processing
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

                    # FIX: Tennis Flags Reversed in Main Screen
                    # Override selection if Tennis: Force index 0=Home, 1=Away (Same as SportsMonitor/MiniBar)
                    league_url = event.get('league_url', '')
                    if get_sport_type(league_url) == SPORT_TYPE_TENNIS and len(comps) >= 2:
                        team_h = comps[0]
                        team_a = comps[1]
                    
                    # Handle different sport types
                    league_url = event.get('league_url', '')
                    sport_type = event.get('sport_type', 'soccer')
                    is_tennis = 'athlete' in (team_h or {}) or 'athlete' in (team_a or {})
                    
                    if team_h:
                        if 'athlete' in team_h:
                            athlete = team_h.get('athlete', {})
                            home = athlete.get('shortName') or athlete.get('displayName') or athlete.get('fullName') or athlete.get('name') or team_h.get('team', {}).get('displayName') or 'Player 1'
                        else:
                            home = team_h.get('team', {}).get('displayName', team_h.get('team', {}).get('name', 'Home'))
                        
                        if is_tennis:
                            t_s1, t_s2 = calculate_tennis_scores(comps, state)
                            h_score = t_s1 if team_h == comps[0] else t_s2
                        else:
                            h_score = team_h.get('score', '0') or '0'
                    
                    if team_a:
                        if 'athlete' in team_a:
                            athlete = team_a.get('athlete', {})
                            away = athlete.get('shortName') or athlete.get('displayName') or athlete.get('fullName') or athlete.get('name') or team_a.get('team', {}).get('displayName') or 'Player 2'
                        else:
                            away = team_a.get('team', {}).get('displayName', team_a.get('team', {}).get('name', 'Away'))
                        
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
                
                # Removed redundant late filtering
                
                has_epg = self.check_epg_availability(home, away) if state == 'pre' or is_live else False
                entry_data = (status_short, get_league_abbr(league_prefix), str(left_text), str(score_text), str(right_text), str(display_time), goal_side, is_live, h_png, a_png, h_score_int, a_score_int, has_epg)
                
                # Store raw data for sorting (include event for excitement calculation)
                # FIX: Use actual Event ID for tracking so open_game_info works
                real_match_id = event.get('id', match_id)
                raw_entries.append((entry_data, real_match_id, is_live, event))
                
            except: continue
        
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
        menu_options = [
            ("Check for Updates", "update"), 
            ("Change Interface Theme", "theme"), 
            ("Mini Bar Style (Default Theme only)", "minibar_color"),
            ("Main Screen Transparency (Default Theme only)", "transparency"), 
            ("Show Plugin in Main Menu: " + in_menu_txt, "toggle_menu")
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
        options = []
        for idx, item in enumerate(DATA_SOURCES): options.append((item[0], idx))
        self.session.openWithCallback(self.single_league_selected, ChoiceBox, title="Select Single League", list=options)
    def single_league_selected(self, selection):
        if selection: self.monitor.set_league(selection[1]); self.update_header(); self.fetch_data()
    def open_mini_bar(self): self.session.openWithCallback(self.mini_bar_callback, SimpleSportsMiniBar)
    def mini_bar_callback(self, result=None):
        if result == "next": 
            self.session.openWithCallback(self.on_minibar_closed, SimpleSportsMiniBar2)
        else:
            self.on_minibar_closed(result)

    def on_minibar_closed(self, result=None):
        # Determine if we need to refresh (Filter might have changed in MiniBar)
        self.update_filter_button()
        self.update_header()
        # Force refresh list with new filter
        self.refresh_ui(True, force_refresh=True)
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
        self.monitor.toggle_filter(); self.update_filter_button(); self.refresh_ui(True, force_refresh=True)
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
                import time
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
            description="Live Sports Scores, Alerts, and EPG by reali22",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="picon.png",
            fnc=main
        ),
        PluginDescriptor(
            name="SimplySports",
            description="Live Sports Scores, Alerts, and EPG by reali22",
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
            description="Live Sports Scores, Alerts, and EPG by reali22",
            where=PluginDescriptor.WHERE_MENU,
            fnc=menu
        ))
    return list