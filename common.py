from __future__ import absolute_import, division, print_function
import shutil
import os
import threading
import time
import ssl
import hashlib
import sys
import json
import datetime
import calendar
from datetime import datetime as dt_datetime
from functools import partial

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

# Twisted Imports
from twisted.internet import reactor, defer
try:
    from twisted.internet import ssl as twisted_ssl
except ImportError:
    twisted_ssl = None
    
from twisted.web.client import Agent, readBody, getPage, downloadPage
from twisted.web.http_headers import Headers

from enigma import eTimer, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, getDesktop, eConsoleAppContainer, gRGB, addFont, eEPGCache, eServiceReference, iServiceInformation, eServiceCenter, ePoint
from Components.Sources.StaticText import StaticText

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
CURRENT_VERSION = "3.9"
GITHUB_BASE_URL = "https://raw.githubusercontent.com/Ahmed-Mohammed-Abbas/SimplySports/main/"
CONFIG_FILE = "/etc/enigma2/simply_sports.json"
LOGO_CACHE_DIR = "/tmp/simplysports_logos"

# ==============================================================================
# FONT FALLBACK
# ==============================================================================
def load_fallback_font():
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

load_fallback_font()

# ==============================================================================
# DATA SOURCES
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
    ("Rugby - Six Nations", "https://site.api.espn.com/apis/site/v2/sports/rugby/270557/scoreboard"),
    ("Rugby - World Cup", "https://site.api.espn.com/apis/site/v2/sports/rugby/164205/scoreboard"),
    ("Rugby - Super Rugby", "https://site.api.espn.com/apis/site/v2/sports/rugby/242041/scoreboard"),
    ("Rugby - Premiership", "https://site.api.espn.com/apis/site/v2/sports/rugby/267979/scoreboard"),
    ("Rugby - Pro14", "https://site.api.espn.com/apis/site/v2/sports/rugby/270559/scoreboard"),
    ("Rugby - Top 14", "https://site.api.espn.com/apis/site/v2/sports/rugby/270560/scoreboard"),
    ("Rugby - Champions Cup", "https://site.api.espn.com/apis/site/v2/sports/rugby/271937/scoreboard"),
    ("Rugby League - NRL", "https://site.api.espn.com/apis/site/v2/sports/rugby-league/nrl/scoreboard"),
    ("Rugby League - Super League", "https://site.api.espn.com/apis/site/v2/sports/rugby-league/super-league/scoreboard"),
    ("Cricket - IPL", "https://site.api.espn.com/apis/site/v2/sports/cricket/ipl/scoreboard"),
    ("Cricket - T20 World Cup", "https://site.api.espn.com/apis/site/v2/sports/cricket/8604/scoreboard"),
    ("Cricket - ODI World Cup", "https://site.api.espn.com/apis/site/v2/sports/cricket/8605/scoreboard"),
    ("Cricket - Test Matches", "https://site.api.espn.com/apis/site/v2/sports/cricket/1/scoreboard"),
    ("Cricket - ODI", "https://site.api.espn.com/apis/site/v2/sports/cricket/2/scoreboard"),
    ("Cricket - T20I", "https://site.api.espn.com/apis/site/v2/sports/cricket/3/scoreboard"),
    ("Cricket - Big Bash", "https://site.api.espn.com/apis/site/v2/sports/cricket/8251/scoreboard"),
    ("Cricket - The Hundred", "https://site.api.espn.com/apis/site/v2/sports/cricket/8676/scoreboard"),
    ("Cricket - PSL", "https://site.api.espn.com/apis/site/v2/sports/cricket/8674/scoreboard"),
    ("Lacrosse - PLL", "https://site.api.espn.com/apis/site/v2/sports/lacrosse/pll/scoreboard"),
    ("Lacrosse - NCAA Men", "https://site.api.espn.com/apis/site/v2/sports/lacrosse/mens-college-lacrosse/scoreboard"),
    ("Lacrosse - NCAA Women", "https://site.api.espn.com/apis/site/v2/sports/lacrosse/womens-college-lacrosse/scoreboard"),
    ("MotoGP", "https://site.api.espn.com/apis/site/v2/sports/racing/motogp/scoreboard"),
    ("Formula E", "https://site.api.espn.com/apis/site/v2/sports/racing/frmle/scoreboard"),
    ("NASCAR Xfinity", "https://site.api.espn.com/apis/site/v2/sports/racing/nascar-xfinity/scoreboard"),
    ("NASCAR Trucks", "https://site.api.espn.com/apis/site/v2/sports/racing/nascar-trucks/scoreboard"),
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
SPORT_TYPE_TEAM = "team_vs"
SPORT_TYPE_RACING = "racing"
SPORT_TYPE_GOLF = "golf"
SPORT_TYPE_TENNIS = "tennis"
SPORT_TYPE_COMBAT = "combat"
SPORT_TYPE_CRICKET = "cricket"
SPORT_TYPE_RUGBY = "rugby"

def get_sport_type(league_url):
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
    elif "/rugby" in url_lower:
        return SPORT_TYPE_RUGBY
    else:
        return SPORT_TYPE_TEAM

def calculate_tennis_scores(competitors, state):
    s1, s2 = 0, 0
    try:
        if len(competitors) < 2: return "0", "0"
        c1, c2 = competitors[0], competitors[1]
        sc1 = c1.get('score', '')
        sc2 = c2.get('score', '')
        has_linescores = c1.get('linescores') or c2.get('linescores')
        trust_api = (sc1 and sc1 != '0') or (sc2 and sc2 != '0')
        if trust_api:
            return sc1 or '0', sc2 or '0'
        ls1 = c1.get('linescores', [])
        ls2 = c2.get('linescores', [])
        count = min(len(ls1), len(ls2))
        for i in range(count):
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
    names = {
        SPORT_TYPE_TEAM: "Match",
        SPORT_TYPE_RACING: "Race",
        SPORT_TYPE_GOLF: "Tournament",
        SPORT_TYPE_TENNIS: "Match",
        SPORT_TYPE_COMBAT: "Fight"
    }
    return names.get(sport_type, "Event")

def get_local_time_str(utc_date_str):
    try:
        if 'T' in utc_date_str:
            date_part, time_part = utc_date_str.split('T')
            y, m, d = map(int, date_part.split('-'))
            time_part = time_part.replace('Z', '')
            H, M = map(int, time_part.split(':')[:2])
            dt_utc = dt_datetime(y, m, d, H, M)
            timestamp = calendar.timegm(dt_utc.timetuple())
            local_dt = dt_datetime.fromtimestamp(timestamp)
            now = dt_datetime.now()
            time_str = "{:02d}:{:02d}".format(local_dt.hour, local_dt.minute)
            if local_dt.date() == now.date(): return str(time_str)
            else: return local_dt.strftime("%a %d/%m") + " " + time_str
    except:
        return "--:--"

def get_league_abbr(full_name):
    if not full_name: return ""
    return full_name[:3].upper()

def safe_connect(timer_obj, func):
    if hasattr(timer_obj, 'callback'):
        timer_obj.callback.append(func)
    else:
        try:
            timer_obj.timeout.get().append(func)
        except AttributeError:
            timer_obj.timeout.append(func)

def get_scaled_pixmap(path, width, height):
    if not path or not LoadPixmap: return None
    try:
        from enigma import ePicLoad, eSize
        sc = ePicLoad()
        sc.setPara((width, height, 1, 1, 0, 1, "#00000000"))
        if sc.startDecode(path, 0, 0, False) == 0:
            ptr = sc.getData()
            return ptr
    except: pass
    try:
        return LoadPixmap(cached=True, path=path)
    except: return None

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
        font_h = 2; font_a = 2
        if len(left_text) > 27: font_h = 0 
        elif len(left_text) > 23: font_h = 1 
        if len(right_text) > 27: font_a = 0 
        elif len(right_text) > 23: font_a = 1 
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 30, 0, 80, h-12, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, status, c_status, c_sel))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 110, 0, 80, h-12, 1, RT_HALIGN_CENTER|RT_VALIGN_CENTER, league_short, c_dim, c_sel))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 195, 0, 575, h-12, font_h, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, left_text, c_h_name, c_sel))
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
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 940, -10, 40, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "-", c_dim, c_sel))
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 980, 15, 80, 45, font_idx, RT_HALIGN_CENTER|RT_VALIGN_CENTER, s2, c_a_score, c_sel, c_box, c_box))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 860, 0, 200, h-12, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, c_dim, c_sel))
        if a_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 1080, 5, 60, 60, get_scaled_pixmap(a_png, 60, 60)))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1150, 0, 520, h-12, font_a, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, c_a_name, c_sel))
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
        font_h = 2; font_a = 2
        if len(left_text) > 27: font_h = 0 
        elif len(left_text) > 23: font_h = 1 
        if len(right_text) > 27: font_a = 0 
        elif len(right_text) > 23: font_a = 1 
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
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 940, -10, 40, h, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "-", c_dim, c_sel))
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 980, 15, 80, 45, font_idx, RT_HALIGN_CENTER|RT_VALIGN_CENTER, s2, c_a_score, c_sel, c_box, c_box))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 860, 0, 200, h-12, 2, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, c_dim, c_sel))
        if a_png: res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 1080, 5, 60, 60, get_scaled_pixmap(a_png, 60, 60)))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1150, 0, 520, h-12, font_a, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, c_a_name, c_sel))
        if has_epg:
             res.append((eListboxPythonMultiContent.TYPE_TEXT, 1670, 0, 35, h, 1, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "EPG", c_accent, c_sel))
        font_time = 3 
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 1710, 0, 180, h, font_time, RT_HALIGN_CENTER|RT_VALIGN_CENTER, time_str, c_dim, c_sel))
        if goal_side == 'home': res.append((eListboxPythonMultiContent.TYPE_TEXT, 785, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "<", c_accent, c_accent))
        elif goal_side == 'away': res.append((eListboxPythonMultiContent.TYPE_TEXT, 1115, 22, 20, 30, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, ">", c_accent, c_accent))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 88, 1880, 2, 0, RT_HALIGN_CENTER, "", 0x22182c82, 0x22182c82))
        return res
    except: return []

def InfoListEntry(entry):
    col_text = 0xffffff 
    col_none = None
    text_align = RT_HALIGN_LEFT | RT_VALIGN_CENTER
    res = [
        entry,
        (eListboxPythonMultiContent.TYPE_TEXT, 140, 0, 190, 40, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, entry[0], col_text, col_none)
    ]
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 340, 0, 50, 40, 0, RT_HALIGN_CENTER | RT_VALIGN_CENTER, entry[1], col_text, col_none))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 400, 0, 1200, 40, 0, text_align, entry[2], col_text, col_none))
    return res

def SelectionListEntry(name, is_selected, logo_path=None):
    check_mark = "[x]" if is_selected else "[ ]"
    col_sel = 0x00FF85 if is_selected else 0x9E9E9E
    text_col = 0xFFFFFF if is_selected else 0x9E9E9E
    res = [(name, is_selected)]
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 5, 40, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, check_mark, col_sel, col_sel, None, None))
    text_x = 70
    if logo_path and os.path.exists(logo_path) and os.path.getsize(logo_path) > 0:
        try:
            pixmap = get_scaled_pixmap(logo_path, 35, 35)
            if pixmap:
                res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 70, 7, 35, 35, pixmap))
                text_x = 115
        except: pass
    res.append((eListboxPythonMultiContent.TYPE_TEXT, text_x, 5, 700 - (text_x - 70), 40, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, name, text_col, text_col, None, None))
    return res
