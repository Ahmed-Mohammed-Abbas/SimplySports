import os
from ..common import *
from ..globals import global_sports_monitor

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
