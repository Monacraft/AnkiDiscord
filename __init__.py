from anki.hooks import addHook
from aqt import mw
from aqt.utils import showInfo
from aqt.qt import *
import time
import threading
from datetime import datetime, timedelta
import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "pypresence"))

try:
    from .pypresence import Presence
    PYPRESENCE_AVAILABLE = True
except ImportError:
    PYPRESENCE_AVAILABLE = False
    with open(os.path.join(os.path.dirname(__file__), "test.txt"), "w") as file:
        file.write("not available")
        
    print("pypresence not available. Please install it with: pip install pypresence")

# Rich presence configuration
CLIENT_ID = '583084701510533126'

class DiscordRichPresence:
    def __init__(self):
        self.rpc = None
        self.connected = False
        self.start_time = int(time.time())
        self.last_update_time = 0
        self.update_cooldown = 2  # Minimum seconds between updates
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        self.retry_delay = 5  # seconds
        self.last_connection_attempt = 0
        
        # State tracking
        self.current_state = ""
        self.current_details = ""
        self.due_message = ""
        self.cards_done_today = 0
        
        # Skip counters for performance
        self.skip_edit = 0
        self.skip_answer = 0
        
        # Initialize connection
        if PYPRESENCE_AVAILABLE:
            self._connect_with_retry()
    
    def _connect_with_retry(self):
        """Attempt to connect to Discord with retry logic"""
        current_time = time.time()
        
        # Don't retry too frequently
        if current_time - self.last_connection_attempt < self.retry_delay:
            return False
            
        if self.connection_attempts >= self.max_connection_attempts:
            return False
            
        self.last_connection_attempt = current_time
        
        try:
            if self.rpc:
                try:
                    self.rpc.close()
                except:
                    pass
            
            self.rpc = Presence(CLIENT_ID)
            self.rpc.connect()
            self.connected = True
            self.connection_attempts = 0
            print("Discord Rich Presence connected successfully")
            return True
            
        except Exception as e:
            self.connected = False
            self.connection_attempts += 1
            print(f"Failed to connect to Discord (attempt {self.connection_attempts}): {e}")
            
            # Schedule retry in background
            if self.connection_attempts < self.max_connection_attempts:
                timer = threading.Timer(self.retry_delay, self._connect_with_retry)
                timer.daemon = True
                timer.start()
            
            return False
    
    def _calculate_cards_done_today(self):
        """Calculate how many cards were reviewed today"""
        if not mw.col:
            return 0
            
        try:
            # Get today's date in the format Anki uses
            today = mw.col.sched.today
            
            # Query the revlog for today's reviews
            reviews_today = mw.col.db.scalar(
                "SELECT COUNT(*) FROM revlog WHERE id > ?",
                int(time.time() * 1000) - (86400 * 1000)
            ) or 0
            
            return reviews_today
        except:
            return 0
    
    def _calculate_due_cards(self):
        """Calculate cards due and update due message"""
        if not mw.col:
            self.due_message = "Loading..."
            return
            
        try:
            due_count = 0
            
            # Loop through deckDueTree to find cards due
            for deck_info in mw.col.sched.deckDueTree():
                name, did, due, lrn, new, children = deck_info
                due_count += due + lrn + new
            
            # Update cards done today
            self.cards_done_today = self._calculate_cards_done_today()
            
            # Format the due message
            if due_count == 0:
                self.due_message = f"Done for today! ({self.cards_done_today} cards completed)"
            elif due_count == 1:
                self.due_message = f"1 card left ({self.cards_done_today} done today)"
            else:
                self.due_message = f"{due_count} cards left ({self.cards_done_today} done today)"
                
        except Exception as e:
            self.due_message = "Error calculating cards"
            print(f"Error calculating due cards: {e}")
    
    def update_presence(self, state, details, small_image="tick-dark", force_update=False):
        """Update Discord Rich Presence with rate limiting and error handling"""
        current_time = time.time()
        
        # Rate limiting - don't update too frequently unless forced
        if not force_update and current_time - self.last_update_time < self.update_cooldown:
            return
        
        # Don't update if nothing changed
        if not force_update and state == self.current_state and details == self.current_details:
            return
        
        # Update card counts
        self._calculate_due_cards()
        
        # Try to connect if not connected
        if not self.connected:
            if not self._connect_with_retry():
                return
        
        try:
            activity = {
                "state": state or self.due_message,
                "details": details,
                "start": self.start_time,
                "small_image": small_image,
                "small_text": "Anki Flashcards",
                "large_image": "anki_final",
                "large_text": "Anki - Spaced Repetition"
            }
            
            self.rpc.update(**activity)
            
            # Update tracking variables
            self.current_state = state
            self.current_details = details
            self.last_update_time = current_time
            
        except Exception as e:
            print(f"Failed to update Discord presence: {e}")
            self.connected = False
            
            # Try to reconnect in background
            timer = threading.Timer(1.0, self._connect_with_retry)
            timer.daemon = True
            timer.start()
    
    def close(self):
        """Clean up Discord connection"""
        if self.rpc and self.connected:
            try:
                self.rpc.close()
            except:
                pass
        self.connected = False

# Global instance
discord_rpc = DiscordRichPresence()

def on_state_change(state, old_state):
    """Handle Anki state changes"""
    global discord_rpc
    
    if not PYPRESENCE_AVAILABLE or not discord_rpc:
        return
    
    # Skip certain state transitions
    if state == "overview":
        return
    
    try:
        # Map states to Discord presence
        if state == "deckBrowser":
            discord_rpc.update_presence(
                discord_rpc.due_message, 
                "Chilling in the menus", 
                "zzz"
            )
        elif state == "review":
            discord_rpc.update_presence(
                discord_rpc.due_message, 
                "Daily reviews", 
                "tick-dark"
            )
        elif state == "browse":
            discord_rpc.skip_edit = 1
            discord_rpc.update_presence(
                discord_rpc.due_message, 
                "Browsing decks", 
                "search"
            )
        elif state == "edit":
            discord_rpc.update_presence(
                discord_rpc.due_message, 
                "Adding cards", 
                "ellipsis-dark"
            )
            
    except Exception as e:
        print(f"Error in state change handler: {e}")

def on_browse_opened(browser):
    """Handle browser window opening"""
    discord_rpc.update_presence(
        discord_rpc.due_message, 
        "Browsing decks", 
        "search"
    )

def on_editor_opened(editor, note=None):
    """Handle editor opening"""
    global discord_rpc
    
    # Skip if we just opened browser
    if discord_rpc.skip_edit == 0:
        discord_rpc.update_presence(
            discord_rpc.due_message, 
            "Adding cards", 
            "ellipsis-dark"
        )
    
    discord_rpc.skip_edit = 0

def on_answer_shown():
    """Handle answer being shown - update card counts periodically"""
    global discord_rpc
    
    # Only update every few cards to avoid excessive API calls
    if discord_rpc.skip_answer >= 3:
        discord_rpc.update_presence(
            discord_rpc.due_message, 
            "Daily reviews", 
            "tick-dark",
            force_update=True  # Force update to refresh card counts
        )
        discord_rpc.skip_answer = 0
    else:
        discord_rpc.skip_answer += 1

def on_collection_loaded():
    """Handle collection being loaded - good time to update counts"""
    discord_rpc.update_presence(
        discord_rpc.due_message, 
        "Chilling in the menus", 
        "zzz",
        force_update=True
    )

def cleanup_on_close():
    """Clean up when Anki closes"""
    if discord_rpc:
        discord_rpc.close()

# Register hooks
if PYPRESENCE_AVAILABLE:
    addHook("afterStateChange", on_state_change)
    addHook("browser.setupMenus", on_browse_opened)
    addHook("setupEditorShortcuts", on_editor_opened)
    addHook("showAnswer", on_answer_shown)
    addHook("profileLoaded", on_collection_loaded)
    addHook("unloadProfile", cleanup_on_close)
    
    # Ensure cleanup on exit
    import atexit
    atexit.register(cleanup_on_close)