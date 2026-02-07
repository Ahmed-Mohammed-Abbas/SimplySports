import os
from ..common import *
from ..globals import global_sports_monitor

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
