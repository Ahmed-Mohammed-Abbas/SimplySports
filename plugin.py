# -*- coding: utf-8 -*-
import shutil
import os
import threading
import time
import ssl
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
from enigma import eTimer, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, getDesktop
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
CURRENT_VERSION = 2.0"
GITHUB_BASE_URL = "https://raw.githubusercontent.com/Ahmed-Mohammed-Abbas/SimplySports/main/"
CONFIG_FILE = "/etc/enigma2/simply_sports.json"

# ==============================================================================
# STYLING
# ==============================================================================
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

# ==============================================================================
# LIST RENDERERS (Fix: Draw Text First, Images Last)
# ==============================================================================
def SportListEntry(entry):
    try:
        # Unpack entry
        if len(entry) >= 10:
             status, league_short, left_text, score_text, right_text, time_str, goal_side, is_live, h_png, a_png = entry[:10]
        else:
             status, left_text, score_text, right_text, time_str, goal_side, is_live, league_name = entry[:8]
             league_short = get_league_abbr(league_name)
             h_png, a_png = None, None

        # --- SAFETY CHECK ---
        # FIXED: Allow even tiny files (size > 0). Do NOT delete them.
        if h_png and (not os.path.exists(h_png) or os.path.getsize(h_png) == 0): h_png = None
        if a_png and (not os.path.exists(a_png) or os.path.getsize(a_png) == 0): a_png = None

        left_col = C_WHITE
        right_col = C_WHITE
        if goal_side == 'home': 
            left_col = C_PL_GREEN
        elif goal_side == 'away': 
            right_col = C_PL_GREEN
        
        status_col = C_WHITE
        status_bg = C_GREY
        if status == "LIVE": 
            status_col = C_WHITE
            status_bg = C_PL_PINK
        elif status == "FIN": 
            status_col = C_BLACK
            status_bg = C_PL_GREEN
        
        time_col = C_GREY
        if is_live: time_col = C_PL_GREEN
        elif "/" in time_str: time_col = C_WHITE
        
        score_bg = C_WHITE if (status == "LIVE" or status == "FIN") else None
        score_fg = C_PL_PURPLE if (status == "LIVE" or status == "FIN") else C_WHITE

        res = [entry]

        # --- STEP 1: DRAW ALL TEXT FIRST (So it never disappears) ---
        
        # Status Box
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 12, 70, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, status, status_col, status_col, status_bg, status_bg, 0, 5))
        
        # League Name
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 85, 12, 75, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, league_short, C_GOLD))
        
        # Home Team Name
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 170, 5, 300, 55, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, left_text, left_col))

        # Score (Now guaranteed to draw)
        if score_bg:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 530, 12, 90, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, score_fg, score_fg, score_bg, score_bg, 0, 0))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 530, 12, 90, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, score_fg))

        # Away Team Name (Now guaranteed to draw)
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 680, 5, 300, 55, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, right_col))
        
        # Time
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 990, 5, 200, 55, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, time_str, time_col))

        # --- STEP 2: DRAW IMAGES LAST (If they fail, only the logo is missing) ---
        
        # Home Logo
        if h_png:
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 480, 12, 40, 40, LoadPixmap(h_png)))
            
        # Away Logo
        if a_png:
            res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 630, 12, 40, 40, LoadPixmap(a_png)))
            
        # Divider Line
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 63, 1180, 1, 0, RT_HALIGN_CENTER, "", C_DARK_GREY, C_DARK_GREY, C_DARK_GREY, C_DARK_GREY))
        return res
    except: return []

def GameInfoEntry(label, val_home, val_away, is_header=False):
    col_text = C_WHITE
    col_bg = None
    font_size = 28
    
    if is_header:
        col_text = C_GOLD
        col_bg = C_BLUE_HEADER
        font_size = 30

    res = ["entry"]
    
    if col_bg:
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1200, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "", None, None, col_bg, col_bg))
    
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 0, 500, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, label, col_text, col_text, None, None, 0, 0, font_size))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 550, 0, 300, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, val_home, C_PL_GREEN if not is_header else C_WHITE, C_PL_GREEN, None, None, 0, 0, font_size))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 880, 0, 300, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, val_away, C_PL_GREEN if not is_header else C_WHITE, C_PL_GREEN, None, None, 0, 0, font_size))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 48, 1200, 2, 0, RT_HALIGN_CENTER, "", C_DARK_GREY, C_DARK_GREY, C_DARK_GREY, C_DARK_GREY))
    return res

def SelectionListEntry(name, is_selected):
    check_mark = "[x]" if is_selected else "[ ]"
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
        
        # DESIGN:
        # Position: 40,10 (Matches Mini Bar)
        # Size: 620 x 140 (Matches Mini Bar width, slightly taller for info)
        # Colors: Same transparent "Glass" theme
        
        self.skin = """
            <screen position="40,10" size="620,140" title="Goal Notification" flags="wfNoBorder" backgroundColor="#00000000">
                
                <eLabel position="0,0" size="620,30" backgroundColor="#E6000000" zPosition="0" />
                <widget name="league" position="0,0" size="620,30" font="Regular;22" foregroundColor="#FFD700" backgroundColor="#E6000000" valign="center" halign="center" transparent="1" zPosition="1" />
                
                <eLabel position="0,30" size="620,110" backgroundColor="#33190028" zPosition="0" />
                
                <eLabel position="0,30" size="5,110" backgroundColor="#E90052" zPosition="1" /> <eLabel position="615,30" size="5,110" backgroundColor="#F6B900" zPosition="1" /> <widget name="h_logo" position="20,40" size="50,50" alphatest="blend" zPosition="2" />
                <widget name="a_logo" position="550,40" size="50,50" alphatest="blend" zPosition="2" />
                
                <widget name="match" position="80,35" size="460,45" font="Regular;30" foregroundColor="#FFFFFF" backgroundColor="#33190028" valign="center" halign="center" transparent="1" zPosition="2" />
                
                <eLabel position="100,85" size="420,1" backgroundColor="#505050" zPosition="1" />
                
                <widget name="scorer" position="80,90" size="460,30" font="Regular;24" foregroundColor="#00FF85" backgroundColor="#33190028" valign="center" halign="center" transparent="1" zPosition="2" />
                
                <eLabel position="0,138" size="620,2" backgroundColor="#00FF85" zPosition="2" />
            </screen>
        """

        Screen.__init__(self, session)
        self["league"] = Label(str(league_text))
        self["match"] = Label(str(match_text))
        self["scorer"] = Label(str(scorer_text))
        
        self["l_logo"] = Pixmap()
        self["h_logo"] = Pixmap()
        self["a_logo"] = Pixmap()
        
        # Download images (Using Twisted directly as it works reliably for notifications)
        self.download_image(l_url, "l_logo", "/tmp/ss_l_logo.png")
        self.download_image(h_url, "h_logo", "/tmp/ss_h_logo.png")
        self.download_image(a_url, "a_logo", "/tmp/ss_a_logo.png")

        self.timer = eTimer()
        self.timer.callback.append(self.close)
        self.timer.start(8000, True)

        self["actions"] = ActionMap(["SetupActions", "ColorActions"], {
            "ok": self.close, "cancel": self.close
        }, -1)

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
# SPORTS MONITOR
# ==============================================================================
class SportsMonitor:
    def __init__(self):
        self.active = False
        self.current_league_index = 0
        self.custom_league_indices = []
        self.is_custom_mode = False
        self.last_scores = {}
        self.goal_flags = {}
        self.last_states = {} 
        self.live_only_filter = False
        self.timer = eTimer()
        self.timer.callback.append(self.check_goals)
        self.session = None
        self.cached_events = [] 
        self.callbacks = []
        self.status_message = "Initializing..."
        self.notification_queue = []
        self.notification_active = False
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
                d.addCallback(self.parse_single_json, name) 
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

    def parse_single_json(self, body, league_name_fixed=""): 
        self.process_events_data([body], league_name_fixed)
        
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
                latest = details[-1]
                clock = latest.get('clock', {}).get('displayValue', '')
                parts = latest.get('participants', [])
                if parts:
                    p_name = parts[0].get('athlete', {}).get('shortName', '')
                    if not p_name: p_name = parts[0].get('athlete', {}).get('displayName', '')
                    if p_name: return "{}  ( {} )".format(p_name, clock)
        except: pass
        return ""

    def process_events_data(self, bodies_list, single_league_name=""):
        all_events = []
        try:
            for body in bodies_list:
                try:
                    json_str = body.decode('utf-8', errors='ignore')
                    data = json.loads(json_str)
                    
                    league_obj = data.get('leagues', [{}])[0]
                    if single_league_name:
                        league_name = single_league_name
                    else:
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
                
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                if len(comps) > 2: continue 
                
                league_name = event.get('league_name', '')
                sport_cdn = self.get_cdn_sport_name(league_name)
                
                home, away, h_score, a_score = "Home", "Away", 0, 0
                h_logo, a_logo = "", ""
                
                # --- AUTO-CONSTRUCT LOGO URLS ---
                for team in comps:
                    name = team.get('team', {}).get('shortDisplayName', 'Tm')
                    sc = int(team.get('score', '0'))
                    t_id = team.get('team', {}).get('id', '')
                    
                    if t_id:
                        logo_url = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png&w=40&h=40&transparent=true".format(sport_cdn, t_id)
                    else:
                        logo_url = ""

                    if team.get('homeAway') == 'home': 
                        home, h_score, h_logo = name, sc, logo_url
                    else: 
                        away, a_score, a_logo = name, sc, logo_url

                event['h_logo_url'] = h_logo
                event['a_logo_url'] = a_logo

                l_logo = "" 
                match_id = home + "_" + away
                
                score_str = str(h_score) + "-" + str(a_score)

                prev_state = self.last_states.get(match_id)
                if self.active and self.session and prev_state:
                    if state == 'in' and prev_state == 'pre':
                        self.queue_notification(league_name, "MATCH STARTED", "{} vs {}".format(home, away), l_logo, h_logo, a_logo)
                    elif state == 'post' and prev_state == 'in':
                        final_txt = "FT: {} {} - {} {}".format(home, h_score, a_score, away)
                        self.queue_notification(league_name, final_txt, "FULL TIME", l_logo, h_logo, a_logo)

                self.last_states[match_id] = state

                if state == 'in':
                    if match_id in self.last_scores:
                        if self.last_scores[match_id] != score_str:
                            try:
                                prev_h, prev_a = map(int, self.last_scores[match_id].split('-'))
                                diff_h = h_score - prev_h
                                diff_a = a_score - prev_a
                                sport_type = self.get_sport_type(league_name)

                                if diff_h != 0:
                                    if diff_h > 0: self.goal_flags[match_id] = {'side': 'home', 'time': time.time()}
                                    if self.active and self.session:
                                        prefix = self.get_score_prefix(sport_type, diff_h)
                                        match_txt = "{} >> {} {} - {} {}".format(prefix, home, h_score, a_score, away)
                                        scorer_txt = self.get_scorer_text(event)
                                        self.queue_notification(league_name, match_txt, scorer_txt, l_logo, h_logo, a_logo)

                                if diff_a != 0:
                                    if diff_a > 0: self.goal_flags[match_id] = {'side': 'away', 'time': time.time()}
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
# GAME INFO SCREEN
# ==============================================================================
class GameInfoScreen(Screen):
    skin = """
        <screen position="center,center" size="1280,720" title="Game Details" flags="wfNoBorder" backgroundColor="#38003C">
            <eLabel position="0,0" size="1280,80" backgroundColor="#28002C" zPosition="0" />
            <eLabel position="0,80" size="1280,4" backgroundColor="#00FF85" zPosition="1" />
            
            <widget name="match_title" position="0,10" size="1280,60" font="Regular;34" foregroundColor="#FFFFFF" backgroundColor="#28002C" transparent="1" halign="center" valign="center" />
            
            <widget name="info_list" position="40,100" size="1200,600" scrollbarMode="showOnDemand" transparent="1" zPosition="1" />
            
            <widget name="loading" position="0,300" size="1280,100" font="Regular;32" foregroundColor="#9E9E9E" backgroundColor="#38003C" transparent="1" halign="center" />
        </screen>
    """

    def __init__(self, session, event_id, league_url):
        Screen.__init__(self, session)
        self["match_title"] = Label("Loading Game Details...")
        self["loading"] = Label("Fetching Data...")
        
        self["info_list"] = MenuList([], enableWrapAround=False, content=eListboxPythonMultiContent)
        self["info_list"].l.setFont(0, gFont("Regular", 28))
        self["info_list"].l.setItemHeight(50)
        
        self["actions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions"], {
            "cancel": self.close,
            "green": self.close,
            "ok": self.close,
            "up": self["info_list"].up,
            "down": self["info_list"].down,
            "left": self["info_list"].pageUp,
            "right": self["info_list"].pageDown
        }, -1)
        
        self.event_id = event_id
        self.summary_url = league_url.replace("scoreboard", "summary") + "?event=" + str(event_id)
        self.onLayoutFinish.append(self.start_loading)

    def start_loading(self):
        try: self["info_list"].instance.setSelectionEnable(1)
        except: pass
        self.fetch_details()

    def fetch_details(self):
        Agent(reactor).request(b'GET', self.summary_url.encode('utf-8')).addCallback(readBody).addCallback(self.parse_details).addErrback(self.error_details)

    def error_details(self, error):
        self["loading"].setText("Error loading details.")

    def parse_details(self, body):
        try:
            self["loading"].hide()
            json_str = body.decode('utf-8', errors='ignore')
            data = json.loads(json_str)
            
            header_obj = data.get('header', {})
            competitions = header_obj.get('competitions', [{}])[0]
            
            venue = data.get('gameInfo', {}).get('venue', {})
            venue_str = venue.get('fullName', 'Unknown Stadium')
            if 'address' in venue:
                venue_str += ", " + venue['address'].get('city', '')
            
            home_team = next((t for t in competitions['competitors'] if t['homeAway'] == 'home'), {})
            away_team = next((t for t in competitions['competitors'] if t['homeAway'] == 'away'), {})
            
            h_name = home_team.get('team', {}).get('shortDisplayName', 'Home')
            a_name = away_team.get('team', {}).get('shortDisplayName', 'Away')
            h_score = home_team.get('score', '0')
            a_score = away_team.get('score', '0')
            status_desc = header_obj.get('status', {}).get('type', {}).get('description', '')
            
            self["match_title"].setText("{} {} - {} {}   ({})".format(h_name, h_score, a_score, a_name, status_desc))
            
            full_list = []
            full_list.append(GameInfoEntry("MATCH SUMMARY", venue_str, "", is_header=True))
            
            scoring_plays = data.get('scoringPlays', [])
            try: hs, as_score = int(h_score), int(a_score)
            except: hs, as_score = 0, 0
            has_goals = (hs + as_score) > 0
            
            if scoring_plays:
                for play in scoring_plays:
                    clock = play.get('clock', {}).get('displayValue', '')
                    team_id = play.get('team', {}).get('id')
                    if not team_id: 
                        parts = play.get('participants', [])
                        if parts: team_id = parts[0].get('teamId')

                    type_text = play.get('type', {}).get('text', 'Goal')
                    players = play.get('participants', [])
                    player_name = players[0].get('athlete', {}).get('displayName', 'Unknown') if players else ""
                    
                    h_id_root = str(home_team.get('id', 'h'))
                    h_id_team = str(home_team.get('team', {}).get('id', 'h'))
                    t_id_str = str(team_id)
                    
                    if t_id_str == h_id_root or t_id_str == h_id_team:
                        home_txt = player_name + " (" + clock + ")"
                        away_txt = ""
                    else:
                        home_txt = ""
                        away_txt = player_name + " (" + clock + ")"
                    full_list.append(GameInfoEntry(type_text, home_txt, away_txt))
            elif has_goals:
                full_list.append(GameInfoEntry("Note", "Scoring details not available", ""))
            else:
                full_list.append(GameInfoEntry("Note", "No scores yet", ""))
            
            full_list.append(GameInfoEntry("", "", ""))

            boxscore = data.get('boxscore', {})
            teams_box = boxscore.get('teams', [])
            
            if teams_box:
                h_stats = next((t['statistics'] for t in teams_box if str(t['team']['id']) == str(home_team.get('id'))), [])
                a_stats = next((t['statistics'] for t in teams_box if str(t['team']['id']) == str(away_team.get('id'))), [])
                
                if h_stats:
                    full_list.append(GameInfoEntry("MATCH STATISTICS", h_name, a_name, is_header=True))
                    a_stats_map = {s['label']: s['displayValue'] for s in a_stats}
                    for stat in h_stats:
                        label = stat['label']
                        h_val = stat['displayValue']
                        a_val = a_stats_map.get(label, "-")
                        full_list.append(GameInfoEntry(label, h_val, a_val))
                    full_list.append(GameInfoEntry("", "", ""))

            if teams_box:
                h_roster = next((t.get('roster', []) for t in teams_box if str(t['team']['id']) == str(home_team.get('id'))), [])
                a_roster = next((t.get('roster', []) for t in teams_box if str(t['team']['id']) == str(away_team.get('id'))), [])
                h_starters = [p for p in h_roster if p.get('starter')]
                a_starters = [p for p in a_roster if p.get('starter')]
                
                if h_starters or a_starters:
                    full_list.append(GameInfoEntry("STARTING LINEUPS", h_name, a_name, is_header=True))
                    max_len = max(len(h_starters), len(a_starters))
                    for i in range(max_len):
                        h_p = h_starters[i]['athlete']['displayName'] if i < len(h_starters) else ""
                        a_p = a_starters[i]['athlete']['displayName'] if i < len(a_starters) else ""
                        h_n = h_starters[i]['jersey'] if i < len(h_starters) else ""
                        a_n = a_starters[i]['jersey'] if i < len(a_starters) else ""
                        
                        h_txt = "{} {}".format(h_n, h_p).strip()
                        a_txt = "{} {}".format(a_n, a_p).strip()
                        full_list.append(GameInfoEntry("", h_txt, a_txt))

            self["info_list"].setList(full_list)
            self["info_list"].moveToIndex(0)

        except Exception as e:
            self["loading"].setText("Error parsing data")

# ==============================================================================
# LEAGUE SELECTOR
# ==============================================================================
class LeagueSelector(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
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
# MINI BAR (Premier League Style - Slimmer & Transparent)
# ==============================================================================
class SimpleSportsMiniBar(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        
        # Redesigned Skin: 
        # - Top-Left Position (40,10)
        # - 90% Transparent League Header
        # - 20% Transparent Team Bars
        # - Reduced Height (90px -> 70px)
        
        self.skin = """
            <screen position="40,10" size="620,100" title="Sports Ticker" backgroundColor="#00000000" flags="wfNoBorder">
                
                <widget name="lbl_league" position="0,0" size="620,30" font="Regular;24" foregroundColor="#FFFFFF" backgroundColor="#E6000000" transparent="0" halign="center" valign="center" />
                
                <eLabel position="0,30" size="5,70" backgroundColor="#E90052" zPosition="1" /> <eLabel position="5,30" size="235,70" backgroundColor="#33190028" zPosition="1" />
                
                <widget name="h_logo" position="15,35" size="60,60" alphatest="blend" zPosition="2" />
                
                <widget name="lbl_home" position="80,30" size="155,70" font="Regular;26" foregroundColor="#FFFFFF" backgroundColor="#33190028" transparent="1" halign="right" valign="center" zPosition="2" />
                
                <eLabel position="240,30" size="140,70" backgroundColor="#00FF85" zPosition="1" /> <widget name="lbl_score" position="240,30" size="140,40" font="Regular;34" foregroundColor="#000000" backgroundColor="#00FF85" transparent="1" halign="center" valign="center" zPosition="2" />
                
                <eLabel position="240,70" size="140,30" backgroundColor="#FFFFFF" zPosition="2" />
                <widget name="lbl_status" position="240,70" size="140,30" font="Regular;24" foregroundColor="#000000" backgroundColor="#FFFFFF" transparent="1" halign="center" valign="center" zPosition="3" />
                
                <eLabel position="380,30" size="235,70" backgroundColor="#33190028" zPosition="1" /> 
                
                <widget name="lbl_away" position="385,30" size="155,70" font="Regular;26" foregroundColor="#FFFFFF" backgroundColor="#33190028" transparent="1" halign="left" valign="center" zPosition="2" />
                
                <widget name="a_logo" position="545,35" size="60,60" alphatest="blend" zPosition="2" />
                
                <eLabel position="615,30" size="5,70" backgroundColor="#F6B900" zPosition="1" /> </screen>
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
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {"cancel": self.close, "green": self.close, "yellow": self.toggle_filter_mini}, -1)
        
        self.ticker_timer = eTimer()
        self.ticker_timer.callback.append(self.show_next_match)
        self.refresh_timer = eTimer()
        self.refresh_timer.callback.append(self.load_data)
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

    def parse_json(self):
        events = global_sports_monitor.cached_events
        self.matches = []
        
        if not events:
            self.matches.append({
                'league': "SimplySports", 'home': global_sports_monitor.status_message, 
                'away': "", 'score': "", 'status': "", 'h_png': None, 'a_png': None
            })
            return
            
        # Define Paths
        tmp_path = "/tmp/simplysports/logos/"
        if os.path.exists("/media/hdd/"):
            hdd_path = "/media/hdd/simplysports/logos/"
        elif os.path.exists("/hdd/"):
            hdd_path = "/hdd/simplysports/logos/"
        elif os.path.exists("/media/usb/"):
            hdd_path = "/media/usb/simplysports/logos/"
        else:
            hdd_path = "/tmp/simplysports/logos/"

        for event in events:
            status = event.get('status', {})
            state = status.get('type', {}).get('state', 'pre')
            clock = status.get('displayClock', '00:00')
            local_time = get_local_time_str(event.get('date', ''))
            league_name = event.get('league_name', '')
            
            if global_sports_monitor.live_only_filter and state != 'in': 
                continue

            # --- LOGO PATH LOGIC ---
            h_url = event.get('h_logo_url', '')
            a_url = event.get('a_logo_url', '')
            
            try: h_id = h_url.split('500/')[-1].split('.png')[0]
            except: h_id = '0'
            try: a_id = a_url.split('500/')[-1].split('.png')[0]
            except: a_id = '0'
            
            # Check HDD first, then TMP
            h_png = hdd_path + h_id + ".png"
            if not os.path.exists(h_png) or os.path.getsize(h_png) == 0:
                h_png = tmp_path + h_id + ".png"
                if not os.path.exists(h_png) or os.path.getsize(h_png) == 0:
                    h_png = None
            
            a_png = hdd_path + a_id + ".png"
            if not os.path.exists(a_png) or os.path.getsize(a_png) == 0:
                a_png = tmp_path + a_id + ".png"
                if not os.path.exists(a_png) or os.path.getsize(a_png) == 0:
                    a_png = None

            comps = event.get('competitions', [{}])[0].get('competitors', [])
            
            if len(comps) > 2:
                race = event.get('shortName', 'Event')
                venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                match_data = {
                    'league': league_name,
                    'home': race,
                    'away': venue,
                    'score': "VS",
                    'status': local_time,
                    'h_png': None, 'a_png': None
                }
            else:
                home, away, h_score, a_score = "Home", "Away", "0", "0"
                for team in comps:
                    name = team.get('team', {}).get('displayName', 'Team') # Full Name
                    sc = team.get('score', '0')
                    if team.get('homeAway') == 'home': home, h_score = name, sc
                    else: away, a_score = name, sc
                
                score_str = "VS"
                status_str = local_time
                
                if state == 'in':
                    score_str = "{} - {}".format(h_score, a_score)
                    status_str = clock + "'" if ":" not in clock else clock
                elif state == 'post':
                    score_str = "{} - {}".format(h_score, a_score)
                    status_str = "FT"
                
                match_data = {
                    'league': league_name,
                    'home': home,
                    'away': away,
                    'score': score_str,
                    'status': status_str,
                    'h_png': h_png,
                    'a_png': a_png
                }
                
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
        else:
            self["h_logo"].hide()

        if data.get('a_png'):
            self["a_logo"].instance.setPixmapFromFile(data['a_png'])
            self["a_logo"].show()
        else:
            self["a_logo"].hide()


# ==============================================================================
# MAIN GUI (OPTIMIZED: Background Copy + Memory Caching)
# ==============================================================================
from enigma import eConsoleAppContainer

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
            <widget name="head_home" position="170,115" size="300,35" font="Regular;22" foregroundColor="#00FF85" backgroundColor="#28002C" transparent="1" halign="right" valign="center" zPosition="1" />
            <widget name="head_score" position="530,115" size="90,35" font="Regular;22" foregroundColor="#00FF85" backgroundColor="#28002C" transparent="1" halign="center" valign="center" zPosition="1" />
            <widget name="head_away" position="680,115" size="300,35" font="Regular;22" foregroundColor="#00FF85" backgroundColor="#28002C" transparent="1" halign="left" valign="center" zPosition="1" />
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
        
        # --- UI REFRESH TIMER ---
        self.logo_timer = eTimer()
        self.logo_timer.callback.append(lambda: self.refresh_ui(True))
        self.logo_timer.start(5000, False) 
        
        # --- OPTIMIZATION: Memory Cache ---
        # Remembers where valid logos are so we don't check HDD every 5 seconds
        self.path_cache = {} 
        
        # --- DOWNLOAD QUEUE ---
        self.download_queue = []          
        self.is_downloading = False       
        self.current_download_key = None
        
        self.container = eConsoleAppContainer()
        self.container.appClosed.append(self.download_finished)
        
        self.tmp_path = "/tmp/simplysports/logos/"
        
        if os.path.exists("/media/hdd/"):
            self.hdd_path = "/media/hdd/simplysports/logos/"
        elif os.path.exists("/hdd/"):
            self.hdd_path = "/hdd/simplysports/logos/"
        elif os.path.exists("/media/usb/"):
            self.hdd_path = "/media/usb/simplysports/logos/"
        else:
            self.hdd_path = "/tmp/simplysports/logos/"
            
        for path in [self.tmp_path, self.hdd_path]:
            if not os.path.exists(path):
                try: os.makedirs(path)
                except: pass
        
        self["top_title"] = Label("SimplySports Score Center")
        self["league_title"] = Label("LOADING...")
        self["credit"] = Label("reali22 (v" + CURRENT_VERSION + ")")
        
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
            "ok": self.open_game_info,
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
             self["league_title"].setText("Custom League View")
        else:
            try: 
                item = DATA_SOURCES[self.monitor.current_league_index]
                self["league_title"].setText(item[0])
            except: pass
        
        if self.monitor.active:
            self["key_blue"].setText("Discovery: ON")
        else:
            self["key_blue"].setText("Discovery: OFF")

    def update_filter_button(self): 
        if self.monitor.live_only_filter:
            self["key_yellow"].setText("Show All")
        else:
            self["key_yellow"].setText("Live Only")
            
    def fetch_data(self): 
        self.monitor.check_goals()
        
    # ==========================================================================
    # OPTIMIZED DOWNLOAD MANAGER
    # ==========================================================================
    def get_logo_path(self, url, filename):
        if not url: return None
        
        # 1. Check Memory Cache (Fastest - No Lag)
        if filename in self.path_cache:
            return self.path_cache[filename]
            
        file_png = filename + ".png"
        target_tmp = self.tmp_path + file_png
        target_hdd = self.hdd_path + file_png
        
        # 2. Check Disk
        final_path = None
        
        # Check HDD first
        if os.path.exists(target_hdd) and os.path.getsize(target_hdd) > 0:
            final_path = target_hdd
        # Fallback to TMP
        elif os.path.exists(target_tmp) and os.path.getsize(target_tmp) > 0:
            final_path = target_tmp
        else:
            # Need to download
            self.queue_download(url, target_tmp, target_hdd, filename)
            return None # Return None for now, will update next refresh

        # Save to Cache
        if final_path:
            self.path_cache[filename] = final_path
            return final_path
            
        return None

    def queue_download(self, url, tmp_path, hdd_path, filename):
        # Prevent duplicate queuing
        for q in self.download_queue:
            if q[3] == filename: return
        if self.current_download_key == filename: return

        self.download_queue.append((url, tmp_path, hdd_path, filename))
        self.process_queue()

    def process_queue(self):
        if self.is_downloading or not self.download_queue:
            return

        url, tmp_path, hdd_path, filename = self.download_queue.pop(0)
        
        self.is_downloading = True
        self.current_download_key = filename
        
        # THE FIX: Chain commands in background.
        # "wget to TMP" AND THEN "cp to HDD"
        # This happens in the console, so GUI doesn't freeze waiting for HDD spin-up.
        cmd = 'wget -U "Mozilla/5.0" --no-check-certificate -q -O "{}" "{}" && cp -f "{}" "{}"'.format(tmp_path, url, tmp_path, hdd_path)
        self.container.execute(cmd)

    def download_finished(self, retval):
        # Only clear the cache for this item to force a re-check
        if self.current_download_key:
            # If the file exists now, next get_logo_path call will find it and cache it
            pass
        
        self.is_downloading = False
        self.current_download_key = None
        self.process_queue()

    # ==========================================================================
    # REST OF LOGIC
    # ==========================================================================
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
        for idx, item in enumerate(DATA_SOURCES): 
            options.append((item[0], idx))
        self.session.openWithCallback(self.single_league_selected, ChoiceBox, title="Select Single League", list=options)

    def single_league_selected(self, selection):
        if selection:
            self.monitor.set_league(selection[1])
            self.update_header()
            self.fetch_data()

    def open_mini_bar(self): 
        self.session.open(SimpleSportsMiniBar)

    def open_game_info(self):
        idx = self["list"].getSelectedIndex()
        if idx is None or not self.monitor.cached_events:
            return
            
        events = []
        for event in self.monitor.cached_events:
            status = event.get('status', {})
            state = status.get('type', {}).get('state', 'pre')
            if self.monitor.live_only_filter and state != 'in':
                continue
            events.append(event)
            
        if 0 <= idx < len(events):
            selected_event = events[idx]
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
                
            if event_id and url:
                self.session.open(GameInfoScreen, event_id, url)

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
            dummy_entry = ("INFO", "Status:", "No Live Games", "", "", "", False, "", None, None)
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
                comps = event.get('competitions', [{}])[0].get('competitors', [])
                league_prefix = event.get('league_name', '')
                
                h_url = event.get('h_logo_url', '')
                a_url = event.get('a_logo_url', '')
                
                try: h_id = h_url.split('500/')[-1].split('.png')[0]
                except: h_id = '0'
                try: a_id = a_url.split('500/')[-1].split('.png')[0]
                except: a_id = '0'
                
                # --- OPTIMIZED REQUEST ---
                # This uses the new memory cache to prevent heavy disk I/O
                h_png = self.get_logo_path(h_url, h_id)
                a_png = self.get_logo_path(a_url, a_id)

                is_live = False
                display_time = local_time
                
                if len(comps) > 2:
                    left_text = event.get('shortName', 'Race')
                    right_text = "Event"
                    score_text = ""
                    goal_side = None
                    if state == 'in': 
                        score_text = "LIVE"
                        is_live = True
                    elif state == 'post':
                        score_text = "FIN"
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
                if state == 'in': status_short = "LIVE"
                elif state == 'post': status_short = "FIN"

                if self.monitor.live_only_filter and state != 'in': 
                    continue
                
                list_content.append(SportListEntry((status_short, get_league_abbr(league_prefix), str(left_text), str(score_text), str(right_text), str(display_time), goal_side, is_live, h_png, a_png)))
            except Exception as e: 
                continue
        
        if not list_content: 
            self["list"].setList([SportListEntry(("INFO", "", "No Live Games", "", "", "", False, "", None, None))])
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