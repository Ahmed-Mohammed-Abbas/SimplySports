import os
from ..common import *
from ..globals import global_sports_monitor

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
