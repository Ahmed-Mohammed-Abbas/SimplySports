import os
import json
import time
import calendar
import datetime
from .common import *
from .LogoCacheManager import LogoCacheManager
from .Screens.GoalToast import GoalToast
from .Screens.ZapNotificationScreen import ZapNotificationScreen

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
        self.has_changes = True  # Track if data changed since last UI refresh
        
        self.logo_cache = LogoCacheManager()
        self.last_update = 0
        self.cache_file = "/tmp/simplysports/cache.json"
        
        # Optimization: Persistent Agent & Request Management
        self.agent = Agent(reactor)
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
        self.batch_timer = eTimer()
        safe_connect(self.batch_timer, self.finalize_batch)
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
                    self.menu_section = data.get("menu_section", "all")
                    self.show_in_menu = bool(data.get("show_in_menu", True))
                    if self.active: self.timer.start(60000, False)
                    # FIX: Ensure timer runs if reminders exist, even if active is False
                    self.ensure_timer_state()
            except: self.defaults()
        else: self.defaults()

    def defaults(self):
        self.filter_mode = 0; self.theme_mode = "default"; self.transparency = "59"
        self.discovery_mode = 0; self.reminders = []; self.menu_section = "all"
        self.show_in_menu = True

    def save_config(self):
        data = {
            "league_index": self.current_league_index, "filter_mode": self.filter_mode,
            "theme_mode": self.theme_mode, "transparency": self.transparency,
            "discovery_mode": self.discovery_mode, "active": self.active,
            "custom_indices": self.custom_league_indices, "is_custom_mode": self.is_custom_mode,
            "reminders": self.reminders, "menu_section": self.menu_section,
            "show_in_menu": self.show_in_menu
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
        
        # FIX: active flag only controlled by mode, but timer checks reminders too
        self.active = (self.discovery_mode > 0)
        
        # FIX: Clear pending notifications immediately when toggling OFF
        # This prevents queued notifications from showing after disabling Goal Alert
        if self.discovery_mode == 0:
            self.notification_queue = []
            self.notification_active = False
        
        self.ensure_timer_state()
        
        self.save_config(); return self.discovery_mode

    def toggle_activity(self): return self.cycle_discovery_mode()

    def ensure_timer_state(self):
        # Timer should run if: 
        # 1. Active (Discovery Mode ON)
        # 2. OR Reminders exist
        should_run = self.active or (len(self.reminders) > 0)
        
        if should_run:
            if not self.timer.isActive():
                self.timer.start(60000, False)
                # If we just started, run a check immediately
                self.check_goals()
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
        if self.batch_timer.isActive(): self.batch_timer.stop()
        self.batch_queue = []
        self.active_requests.clear() # Cancel/Ignore pending requests

        if index >= 0 and index < len(DATA_SOURCES):
            self.current_league_index = index; self.last_scores = {}; self.save_config(); self.check_goals()
    def set_custom_leagues(self, indices):
        self.custom_league_indices = indices; self.is_custom_mode = True; self.last_scores = {}; self.save_config(); self.check_goals()
    def add_reminder(self, match_name, trigger_time, league_name, h_logo, a_logo, label, sref=None):
        new_rem = {"match": match_name, "trigger": trigger_time, "league": league_name, "h_logo": h_logo, "a_logo": a_logo, "label": label, "sref": sref}
        for r in self.reminders:
            if r["match"] == match_name and r["trigger"] == trigger_time: return
        
        # FIX: Prefetch logos immediately so they are ready when notification triggers
        if h_logo: self.prefetch_logo(h_logo)
        if a_logo: self.prefetch_logo(a_logo)

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
    def check_goals(self):
        self.check_reminders()
        
        # FIX: GUARD - If not active and not custom mode, do not fetch data
        # This allows the timer to run solely for reminders without wasting bandwidth
        if not self.active and not self.is_custom_mode:
            return

        # ✅ INSTANT UI UPDATE - Show cached data FIRST
        if self.cached_events:
            self.status_message = "Updating..."
            self._trigger_callbacks(True)  # UI updates immediately
        else:
            self.status_message = "Loading Data..."
            self._trigger_callbacks(False)  # Show loading state
        # Use persistent agent
        if not self.is_custom_mode:
            try:
                name, url = DATA_SOURCES[self.current_league_index]
                if url not in self.active_requests:
                    self.active_requests.add(url)
                    d = self.agent.request(b'GET', url.encode('utf-8'))
                    d.addCallback(readBody)
                    d.addCallback(self.parse_single_json, name, url) 
                    d.addErrback(self.handle_error)
                    # Cleanup request from active set in callbacks (implicitly handled if logic allows, 
                    # but for single mode we might rely on simple timeout or next cycle clearing if not robust.
                    # For now, simplistic approach or add specific cleanup callback)
                    d.addBoth(lambda x: self.active_requests.discard(url)) 
            except: pass
            

        else:
            if not self.custom_league_indices:
                self.status_message = "No Leagues Selected"
                self.cached_events = []
                self._trigger_callbacks(True)
                return
            


            # Start Batching
            # ✅ INCREMENTAL BATCH PROCESSING
            self.status_message = "Loading..."
            self.batch_queue = []
            selected_indices = [idx for idx in self.custom_league_indices if idx < len(DATA_SOURCES)]
            self.batch_remaining = len(selected_indices)
            
            # ✅ Reduce timeout to 7 seconds
            self.batch_timer.start(7000, True)
            
            # ✅ Track when first response arrives
            self.batch_first_response = None
            
            for idx in selected_indices:
                name, url = DATA_SOURCES[idx]
                if url in self.active_requests:
                    self.batch_remaining -= 1
                    print("[SportsMonitor] Skipping duplicate request:", url)
                    continue
                
                self.active_requests.add(url)
                d = self.agent.request(b'GET', url.encode('utf-8'))
                d.addCallback(readBody)
                d.addCallback(self.collect_batch_response_incremental, name, url)  # ✅ NEW
                d.addErrback(self.collect_batch_error, url) 
                d.addBoth(lambda x, u=url: self.active_requests.discard(u))

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

    def collect_batch_response(self, body, name, url):
        # GUARD: If we switched to single mode, discard this batch
        if not self.is_custom_mode: return

        self.active_requests.discard(url)
        self.batch_queue.append((body, name, url))
        self.batch_remaining -= 1
        if self.batch_remaining <= 0:
            self.finalize_batch()

    def collect_batch_error(self, failure, url=None):
        if url: self.active_requests.discard(url)
        self.batch_remaining -= 1
        if self.batch_remaining <= 0:
            self.finalize_batch()

    def collect_batch_response_incremental(self, body, name, url):
        """Process each response immediately (streaming updates)"""
        if not self.is_custom_mode: 
            self.active_requests.discard(url)
            return
        
        # ✅ PROCESS IMMEDIATELY - Don't wait for all
        import time
        if self.batch_first_response is None:
            self.batch_first_response = time.time()
        
        self.active_requests.discard(url)
        
        # Process this league's data right away
        try:
            self.process_events_data([(body, name, url)], append_mode=True)
            # UI updates after EACH league loads - handled by process_events_data probably calling callbacks? 
            # If process_events_data doesn't call callbacks, we might need to add it here.
            # User's snippet says "UI updates after EACH league loads", assuming process_events_data handles it or we rely on the implementation.
            # However, looking at parse_single_json, it just calls process_events_data.
            # Let's assume process_events_data updates the UI or callbacks.
        except Exception as e:
            print("[SportsMonitor] Error processing {}: {}".format(name, e))
        
        self.batch_remaining -= 1
        
        # ✅ SMART COMPLETION - Don't wait for stragglers
        if self.batch_remaining <= 0:
            self.finalize_batch()
        elif self.batch_remaining <= 2 and time.time() - self.batch_first_response > 3:
            # If 2 or fewer left and we've waited 3s, finalize early
            print("[SportsMonitor] Early finalize - {} stragglers".format(self.batch_remaining))
            self.finalize_batch()

    def finalize_batch(self):
        """Cleanup after batch processing"""
        if not self.is_custom_mode: return
        
        if self.batch_timer.isActive():
            self.batch_timer.stop()
        
        # ✅ No extra processing needed - data already processed incrementally
        self.status_message = ""
        self.batch_queue = []
        self.batch_remaining = 0
        self.batch_first_response = None
        
        # ✅ Final save
        self.save_cache()
        
        # One final callback to ensure UI is synced
        self._trigger_callbacks(True)

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
    def queue_notification(self, league, home, away, score, scorer, l_url, h_url, a_url, event_type="default", scoring_team=None):
        if self.discovery_mode == 0: return
        
        notification = (league, home, away, score, scorer, l_url, h_url, a_url, event_type, scoring_team)
        
        # PRIORITY SYSTEM: Soccer notifications take priority over other sports
        # Insert soccer at front of queue, others at back
        sport_type = self.get_sport_type(league)
        if sport_type == 'soccer':
            # Insert at front (high priority)
            self.notification_queue.insert(0, notification)
        else:
            # Append at back (lower priority)
            self.notification_queue.append(notification)
        
        self.process_queue()
        
    def process_queue(self):
        # Double-check discovery mode - stop processing if Goal Alert is OFF
        if self.discovery_mode == 0:
            self.notification_queue = []  # Clear any remaining items
            return
        if self.notification_active or not self.notification_queue: return
        
        # FIX: Robustness - Wrap in try/except to ensure notification_active is reset
        try:
            item = self.notification_queue.pop(0)
            league, home, away, score, scorer, l_url, h_url, a_url, event_type, scoring_team = item
            self.notification_active = True
            if self.session: 
                try:
                    self.session.openWithCallback(
                        self.on_toast_closed, GoalToast, 
                        league, home, away, score, scorer, l_url, h_url, a_url, event_type, scoring_team
                    )
                except Exception as e:
                    print("[SimplySport] Error opening notification: {}".format(e))
                    self.notification_active = False
                    # Process next after short delay
                    from twisted.internet import reactor
                    reactor.callLater(2, self.process_queue)
            else:
                self.notification_active = False
                # Try next item if session not ready yet
                if self.notification_queue:
                    from twisted.internet import reactor
                    reactor.callLater(5, self.process_queue)
        except Exception as e:
            print("[SimplySport] Critical error in process_queue: {}".format(e))
            self.notification_active = False
            if self.notification_queue:
                from twisted.internet import reactor
                reactor.callLater(2, self.process_queue)

    def on_toast_closed(self, *args):
        self.notification_active = False
        # Small delay before next to prevent UI flicker/overlap
        from twisted.internet import reactor
        reactor.callLater(0.5, self.process_queue)

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
                
                # Helper to safely extract name
                def extract_tennis_name(comp):
                    return comp.get('athlete', {}).get('shortName') or \
                           comp.get('athlete', {}).get('displayName') or \
                           comp.get('name') or ""

                # Create a flattened event for each match
                match_event = {
                    'id': match_id,
                    'uid': match.get('uid', match_id),
                    'date': match.get('date', ev.get('date', '')),
                    'status': match.get('status', {}),
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
                
                # Enhanced Name Extraction for Tennis
                comps = match.get('competitors', [])
                p1_name = "Player 1"
                p2_name = "Player 2"
                
                if len(comps) >= 2:
                    p1_name = extract_tennis_name(comps[0])
                    p2_name = extract_tennis_name(comps[1])
                    
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
                    
                    # Update the competitor objects
                    if not comps[0].get('athlete'): comps[0]['athlete'] = {}
                    if not comps[0]['athlete'].get('shortName'): comps[0]['athlete']['shortName'] = p1_name
                    if not comps[0].get('name'): comps[0]['name'] = p1_name
                    
                    if not comps[1].get('athlete'): comps[1]['athlete'] = {}
                    if not comps[1]['athlete'].get('shortName'): comps[1]['athlete']['shortName'] = p2_name
                    if not comps[1].get('name'): comps[1]['name'] = p2_name

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
                                team_h = next((t for t in comps if t.get('homeAway') == 'home'), None)
                                team_a = next((t for t in comps if t.get('homeAway') == 'away'), None)
                                if not team_h and len(comps) > 0: team_h = comps[0]
                                if not team_a and len(comps) > 1: team_a = comps[1]
                                
                                h_id, h_logo = '', ''
                                a_id, a_logo = '', ''
                                
                                if team_h:
                                    if 'athlete' in team_h:
                                        h_logo = team_h.get('athlete', {}).get('flag', {}).get('href') or ''
                                    else:
                                        h_id = team_h.get('team', {}).get('id', '')
                                        if h_id: h_logo = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png".format(sport_cdn, h_id)
                                
                                if team_a:
                                    if 'athlete' in team_a:
                                        a_logo = team_a.get('athlete', {}).get('flag', {}).get('href') or ''
                                    else:
                                        a_id = team_a.get('team', {}).get('id', '')
                                        if a_id: a_logo = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/{}/500/{}.png".format(sport_cdn, a_id)
                                
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
            
            # --- STABLE SORT: STATUS + DATE + LEAGUE + ID ---
            # Priority: 1) Live matches first 2) Date 3) League grouping 4) ID
            def get_sort_key(ev):
                status = ev.get('status', {})
                state = status.get('type', {}).get('state', 'pre')
                if state == 'post': status_priority = 0
                elif state == 'pre': status_priority = 1
                else: status_priority = 2  # 'in'
                return (status_priority, ev.get('date', ''), ev.get('league_name', ''), ev.get('id', ''))
            
            unique_list.sort(key=get_sort_key)
            self.cached_events = unique_list
            
            # Only set status message if there's an actual issue (no matches)
            # Skip "Data Updated" as it's rarely displayed and can interfere with flicker prevention
            if len(self.cached_events) == 0: self.status_message = "No Matches Found"
            
            # Set flag for UI to know if it needs to rebuild
            self.has_changes = has_changes

            # --- PROCESS ONLY CHANGED EVENTS used to be full Loop ---
            # But goal checks depend on self.last_states which is stateful.
            # We must run logic but we can iterate over changed_events for efficiency
            # However, for 'last_states' consistency, we should check logic.
            # Given we have 'changed_events', let's use that optimization.
            
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
                        # Queue: league, home, away, score, scorer, l_url, h_url, a_url, type, scoring_team
                        self.queue_notification(league_name, home, away, score_fmt, "MATCH STARTED", "", h_logo, a_logo, "start", None)
                        if should_play_stend: self.play_stend_sound()
                    elif state == 'post' and prev_state == 'in':
                        self.queue_notification(league_name, home, away, score_fmt, "FULL TIME", "", h_logo, a_logo, "end", None)
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
                                
                                # Re-format score display "1-0" NO SPACES
                                score_display = "{}-{}".format(h_score, a_score)
                                
                                if diff_h > 0 or diff_a > 0:
                                    # RETRY LOGIC for API LAG
                                    # BASKETBALL SPECIAL HANDLING: No Scorer Name, Visual Only, "Smart Score"
                                    if sport_type == 'basketball':
                                        should_play_sound = False # Visual only
                                        points = max(diff_h, diff_a)
                                        scorer_text = "+{} POINTS".format(points)
                                    elif sport_type == 'football':
                                        # NFL SPECIAL HANDLING: Contextual Text, Instant Update
                                        should_play_sound = True
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
                                        self.queue_notification(league_name, home, away, score_display, scorer_text, "", h_logo, a_logo, "goal", "home")
                                        if sport_type != 'basketball': should_play_sound = True # Explicit check
                                        self.goal_flags[match_id] = {'time': time.time(), 'team': 'home'}
                                    
                                    if diff_a > 0:
                                        self.queue_notification(league_name, home, away, score_display, scorer_text, "", h_logo, a_logo, "goal", "away")
                                        if sport_type != 'basketball': should_play_sound = True # Explicit check
                                        self.goal_flags[match_id] = {'time': time.time(), 'team': 'away'}
                                
                                if should_play_sound and self.discovery_mode == 2:
                                    self.play_sound()
                            except: pass
                    # Update score ONLY if we didn't 'continue' above
                    self.last_scores[match_id] = score_str

            # ADAPTIVE POLLING: 15s for Live, 60s for others
            if self.active:
                new_interval = 15000 if live_count > 0 else 60000
                self.timer.start(new_interval, False)

            for cb in self.callbacks: cb(True)
        except:
            self.status_message = "JSON Parse Error"
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
