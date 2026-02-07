import os
import time
from .common import LOGO_CACHE_DIR, profile_function, eTimer

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
