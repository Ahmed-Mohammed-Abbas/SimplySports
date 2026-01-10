# -*- coding: utf-8 -*-
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
from enigma import eTimer, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, getDesktop
import json
import datetime
import time
import calendar
import os

# ==============================================================================
# CONFIGURATION
# ==============================================================================
CURRENT_VERSION = "1.2"
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
# LIST RENDERERS
# ==============================================================================
def SportListEntry(entry):
    # Standard Match List Entry
    try:
        if len(entry) == 8:
             status, left_text, score_text, right_text, time_str, goal_side, is_live, league_name = entry
        else:
             status, left_text, score_text, right_text, time_str, goal_side, is_live = entry
             league_name = ""

        status = str(status); left_text = str(left_text); score_text = str(score_text); right_text = str(right_text); time_str = str(time_str)
        league_short = get_league_abbr(league_name)

        left_col = C_WHITE
        right_col = C_WHITE
        if goal_side == 'home': 
            left_text = "> " + left_text
            left_col = C_PL_GREEN
        elif goal_side == 'away': 
            right_text = right_text + " <"
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
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 10, 12, 70, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, status, status_col, status_col, status_bg, status_bg, 0, 5))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 85, 12, 75, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, league_short, C_GOLD))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 170, 5, 340, 55, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, left_text, left_col))
        if score_bg:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 520, 12, 110, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, score_fg, score_fg, score_bg, score_bg, 0, 0))
        else:
            res.append((eListboxPythonMultiContent.TYPE_TEXT, 520, 12, 110, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, score_text, score_fg))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 640, 5, 340, 55, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, right_text, right_col))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 990, 5, 200, 55, 0, RT_HALIGN_RIGHT|RT_VALIGN_CENTER, time_str, time_col))
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 63, 1180, 1, 0, RT_HALIGN_CENTER, "", C_DARK_GREY, C_DARK_GREY, C_DARK_GREY, C_DARK_GREY))
        return res
    except: return []

def GameInfoEntry(label, val_home, val_away, is_header=False):
    # Specialized Entry for Game Info Screen (Table Rows)
    # Format:  Label  |  Home Val  |  Away Val
    col_text = C_WHITE
    col_bg = None
    font_size = 28
    
    if is_header:
        col_text = C_GOLD
        col_bg = C_BLUE_HEADER
        font_size = 30

    res = [None]
    # Background for header
    if col_bg:
        res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 0, 1200, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, "", None, None, col_bg, col_bg))
    
    # Column 1: Label (Left/Center)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 0, 500, 50, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, label, col_text, col_text, None, None, 0, 0, font_size))
    
    # Column 2: Home Value (Center)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 550, 0, 300, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, val_home, C_PL_GREEN if not is_header else C_WHITE, C_PL_GREEN, None, None, 0, 0, font_size))
    
    # Column 3: Away Value (Center)
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 880, 0, 300, 50, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, val_away, C_PL_GREEN if not is_header else C_WHITE, C_PL_GREEN, None, None, 0, 0, font_size))
    
    # Bottom separator line
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 0, 48, 1200, 2, 0, RT_HALIGN_CENTER, "", C_DARK_GREY, C_DARK_GREY, C_DARK_GREY, C_DARK_GREY))
    
    return res

def SelectionListEntry(name, is_selected):
    check_mark = "[x]" if is_selected else "[ ]"
    col_sel = C_PL_GREEN if is_selected else C_GREY
    text_col = C_WHITE if is_selected else C_GREY
    res = [(name, is_selected)]
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 15, 5, 40, 40, 0, RT_HALIGN_CENTER|RT_VALIGN_CENTER, check_mark, col_sel))
    res.append((eListboxPythonMultiContent.TYPE_TEXT, 70, 5, 700, 40, 0, RT_HALIGN_LEFT|RT_VALIGN_CENTER, name, text_col))
    return res

# ==============================================================================
# SPORTS MONITOR (BACKGROUND)
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
                # SAFE UNPACKING (Since all are 2 items now)
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
                    # SAFE UNPACKING HERE TOO
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

    def process_events_data(self, bodies_list, single_league_name=""):
        all_events = []
        try:
            for body in bodies_list:
                try:
                    json_str = body.decode('utf-8', errors='ignore')
                    data = json.loads(json_str)
                    
                    if single_league_name:
                        league_name = single_league_name
                    else:
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
        except Exception as e:
            self.status_message = "JSON Parse Error"
            for cb in self.callbacks: cb(True)

if global_sports_monitor is None:
    global_sports_monitor = SportsMonitor()

# ==============================================================================
# GAME INFO SCREEN (NEW FEATURE)
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
        
        # Added WizardActions for standard Up/Down scrolling
        self["actions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions", "WizardActions"], {
            "cancel": self.close,
            "green": self.close,
            "ok": self.close,
            "up": self.scroll_up,
            "down": self.scroll_down,
            "pageUp": self.page_up,
            "pageDown": self.page_down,
            "left": self.page_up,
            "right": self.page_down
        }, -1)
        
        self.event_id = event_id
        # Construct summary URL from the scoreboard URL
        # Scoreboard: .../soccer/eng.1/scoreboard
        # Summary:    .../soccer/eng.1/summary?event=ID
        self.summary_url = league_url.replace("scoreboard", "summary") + "?event=" + str(event_id)
        
        self.onLayoutFinish.append(self.fetch_details)

    def scroll_up(self):
        self["info_list"].up()
        
    def scroll_down(self):
        self["info_list"].down()
        
    def page_up(self):
        self["info_list"].pageUp()
        
    def page_down(self):
        self["info_list"].pageDown()

    def fetch_details(self):
        # Force list to have focus for scrolling
        try:
            self["info_list"].instance.setSelectionEnable(1)
        except: pass
        
        Agent(reactor).request(b'GET', self.summary_url.encode('utf-8')).addCallback(readBody).addCallback(self.parse_details).addErrback(self.error_details)

    def error_details(self, error):
        self["loading"].setText("Error loading details.")

    def parse_details(self, body):
        try:
            self["loading"].hide()
            json_str = body.decode('utf-8', errors='ignore')
            data = json.loads(json_str)
            
            # --- 1. Basic Match Info ---
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
            
            self["match_title"].setText("{} {} - {} {}  ({})".format(h_name, h_score, a_score, a_name, status_desc))
            
            list_items = []
            
            # --- 2. Venue Info ---
            list_items.append(GameInfoEntry("VENUE", venue_str, "", is_header=True))
            
            # --- 3. Goals / Scoring Plays ---
            scoring_plays = data.get('scoringPlays', [])
            
            # Safe int conversion for score check
            try:
                hs = int(h_score)
                as_score = int(a_score)
            except:
                hs, as_score = 0, 0
                
            has_goals = (hs + as_score) > 0
            
            if scoring_plays:
                list_items.append(GameInfoEntry("GOALS", h_name, a_name, is_header=True))
                for play in scoring_plays:
                    clock = play.get('clock', {}).get('displayValue', '')
                    # ESPN data varies. Try team ID at root, or nested
                    team_id = play.get('team', {}).get('id')
                    if not team_id: # Try participants
                        parts = play.get('participants', [])
                        if parts: team_id = parts[0].get('teamId')

                    type_text = play.get('type', {}).get('text', 'Goal')
                    players = play.get('participants', [])
                    player_name = players[0].get('athlete', {}).get('displayName', 'Unknown') if players else ""
                    
                    # Convert IDs to string for safe comparison
                    # Compare against both root ID and team object ID
                    h_id_root = str(home_team.get('id', 'h'))
                    h_id_team = str(home_team.get('team', {}).get('id', 'h'))
                    
                    t_id_str = str(team_id)
                    
                    if t_id_str == h_id_root or t_id_str == h_id_team:
                        home_txt = player_name + " (" + clock + ")"
                        away_txt = ""
                    else:
                        home_txt = ""
                        away_txt = player_name + " (" + clock + ")"
                    
                    list_items.append(GameInfoEntry(type_text, home_txt, away_txt))
            elif has_goals:
                # Score is not 0-0 but no details found
                list_items.append(GameInfoEntry("GOALS", "Goal details", "unavailable", is_header=True))
            else:
                list_items.append(GameInfoEntry("GOALS", "No Goals", "", is_header=True))

            # --- 4. Game Stats (Boxscore) ---
            boxscore = data.get('boxscore', {})
            teams_box = boxscore.get('teams', [])
            if teams_box:
                # Find stats section
                h_stats = next((t['statistics'] for t in teams_box if str(t['team']['id']) == str(home_team.get('id'))), [])
                a_stats = next((t['statistics'] for t in teams_box if str(t['team']['id']) == str(away_team.get('id'))), [])
                
                if h_stats:
                    list_items.append(GameInfoEntry("MATCH STATS", h_name, a_name, is_header=True))
                    # Map stats by label to align them
                    a_stats_map = {s['label']: s['displayValue'] for s in a_stats}
                    
                    for stat in h_stats:
                        label = stat['label']
                        h_val = stat['displayValue']
                        a_val = a_stats_map.get(label, "-")
                        list_items.append(GameInfoEntry(label, h_val, a_val))

            # --- 5. Rosters / Lineups ---
            # Rosters are deep in boxscore -> teams -> roster
            if teams_box:
                list_items.append(GameInfoEntry("STARTING XI", h_name, a_name, is_header=True))
                
                h_roster = next((t.get('roster', []) for t in teams_box if str(t['team']['id']) == str(home_team.get('id'))), [])
                a_roster = next((t.get('roster', []) for t in teams_box if str(t['team']['id']) == str(away_team.get('id'))), [])
                
                # Filter for starters only
                h_starters = [p for p in h_roster if p.get('starter')]
                a_starters = [p for p in a_roster if p.get('starter')]
                
                max_len = max(len(h_starters), len(a_starters))
                for i in range(max_len):
                    h_p = h_starters[i]['athlete']['displayName'] if i < len(h_starters) else ""
                    a_p = a_starters[i]['athlete']['displayName'] if i < len(a_starters) else ""
                    # Optional: Add jersey number
                    h_n = h_starters[i]['jersey'] if i < len(h_starters) else ""
                    a_n = a_starters[i]['jersey'] if i < len(a_starters) else ""
                    
                    h_txt = "{} {}".format(h_n, h_p).strip()
                    a_txt = "{} {}".format(a_n, a_p).strip()
                    list_items.append(GameInfoEntry("", h_txt, a_txt))

            self["info_list"].setList(list_items)

        except Exception as e:
            self["loading"].setText("Error parsing data")
            print("[SimplySports] Info Error: ", e)

# ==============================================================================
# CUSTOM LEAGUE SELECTOR
# ==============================================================================
class LeagueSelector(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        
        # Dynamic Skinning for 720p vs 1080p
        # Uses standard HD layout (1280x720) which scales up fine on most images
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
            # Safe access normalized to 2 items
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
# MINI BAR (DYNAMIC POSITION)
# ==============================================================================
class SimpleSportsMiniBar(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        
        # Dynamic Skinning for 720p vs 1080p
        # Uses getDesktop to determine screen height and place bar at the bottom
        d_width = getDesktop(0).size().width()
        d_height = getDesktop(0).size().height()
        
        if d_width > 1280:
            # 1080p Layout
            width = 1920
            height = 100
            pos_y = d_height - height
            font_size = 36
            filter_w = 300
            info_w = width - filter_w - 40
        else:
            # 720p Layout
            width = 1280
            height = 80
            pos_y = d_height - height
            font_size = 28
            filter_w = 280
            info_w = width - filter_w - 40
            
        self.skin = """<screen position="0,%d" size="%d,%d" title="Sports Ticker" backgroundColor="#00000000" flags="wfNoBorder">
            <eLabel position="0,0" size="%d,%d" backgroundColor="#38003C" zPosition="-1" />
            <eLabel position="0,0" size="%d,4" backgroundColor="#00FF85" zPosition="1" />
            <widget name="match_info" position="20,10" size="%d,%d" font="Regular;%d" foregroundColor="#FFFFFF" backgroundColor="#38003C" transparent="1" valign="center" halign="left" />
            <widget name="filter_status" position="%d,10" size="%d,%d" font="Regular;%d" foregroundColor="#FF004C" backgroundColor="#38003C" transparent="1" valign="center" halign="right" />
        </screen>""" % (pos_y, width, height, width, height, width, info_w, height-20, font_size, width-filter_w-20, filter_w, height-20, font_size-4)

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
            local_time = get_local_time_str(event.get('date', ''))
            league_name = event.get('league_name', '')
            
            if global_sports_monitor.live_only_filter and state != 'in': 
                continue
                
            comps = event.get('competitions', [{}])[0].get('competitors', [])
            if len(comps) > 2:
                race = event.get('shortName', 'Race')
                venue = event.get('competitions', [{}])[0].get('venue', {}).get('fullName', '')
                txt = "{} :: {} @ {}".format(league_name, race, venue)
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
                goal_flag = " GOAL" if match_id in global_sports_monitor.goal_flags else ""
                
                if state == 'in': 
                    txt = "{} :: LIVE {}'  {} {} - {} {} {}".format(league_name, clock, home, h_score, a_score, away, goal_flag)
                elif state == 'post': 
                    txt = "{} :: FT  {} {} - {} {}".format(league_name, home, h_score, a_score, away)
                else: 
                    txt = "{} :: {}  {} vs {}".format(league_name, local_time, home, away)
                    
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
            "ok": self.open_game_info,  # <--- CHANGED HERE
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
            except: 
                pass
        
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
            dummy_entry = ("INFO", "Status:", "No Live Games", "", "", "", False, "")
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
