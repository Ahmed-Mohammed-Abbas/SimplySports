import os
from ..common import *
from ..globals import global_sports_monitor

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


