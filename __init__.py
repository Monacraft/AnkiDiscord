from anki.hooks import addHook
from aqt import mw
from aqt.utils import showInfo
from aqt.qt import * 
from . import rpc
import time

# Rich presence connection
client_id = '583084701510533126'
# Check if discord is running, prevent error message
connected = True
try:
    rpc_obj = rpc.DiscordIpcClient.for_platform(client_id)
except:
    connected = False
    pass

# Start time to show elapsed time
start_time = round(time.time())

# Globals
dueMessage = ""
skipEdit = 0
skipAnswer = 0



##### UPDATE: Changes the RPC status
# state is N. of cards due
# details is current activity
# pic is for mini-icon related to current activity
#
def update(state, details, pic):
    activity = {
            "state": state,
            "details": details,
            "timestamps": {
                "start": start_time
            },
            "assets": {
                "small_text": "Flashcards",
                "small_image": pic,
                "large_text": "Anki",
                "large_image": "anki"
            }
        }

    # send to server:
    rpc_obj.set_activity(activity)



##### DUETODAY: Calculates reviews due
# Stored in global variable 'dueMessage'
# Don't call before Anki has loaded
#
def dueToday():
    # Globals and reset variables
    global dueMessage
    dueCount = 0

    # Loop through deckDueTree to find cards due
    for i in mw.col.sched.deckDueTree():
        name, did, due, lrn, new, children = i
        dueCount += due + lrn + new

    # Correct for single or no cards
    if dueCount == 0:
        dueMessage = "No cards left"
    elif dueCount == 1:
        dueMessage = "(" + str(dueCount) + " card left)"
    else:
        dueMessage = "(" + str(dueCount) + " cards left)"        



##### ONSTATE: Updates with state of anki
# Takes current state and oldState from hook
# If opening browse, skips 'edit' hook
# List of base STATES:
#  - deckBrowser
#  - review
#  - overview (ignored)
#
def onState(state, oldState):
    global skipEdit

    # Check if connected
    if connected:
        # Update numbe due
        dueToday()

        # debug for states
        #showInfo(state + ", " + oldState)

        # Check states:
        if state == "deckBrowser":
            update(dueMessage, "Chilling in the menus", "zzz")
        if state == "review":
            update(dueMessage, "Daily reviews", "tick-dark")
        if state == "browse":
            skipEdit = 1
            update(dueMessage, "Browsing decks", "search")
        if state == "edit":
            update(dueMessage, "Adding cards", "ellipsis-dark")



##### Simulated states
## onBrowse --> when loading browser menu
#
def onBrowse(x):
    onState("browse", "dummy")
#
#
## onEdit --> when loading editor
#
def onEditor(x, y):
    global skipEdit

    # if skipEdit 1, opening browse
    if skipEdit == 0:
        onState("edit", "dummy")

    # reset
    skipEdit = 0
#
#
## onAnswer --> new answer (update cards left)
#
def onAnswer():
    global skipAnswer
    
    # Skip every 3 cards, unneccesary load
    if skipAnswer >= 2:
        onState("review", "review")
        skipAnswer = 0
    skipAnswer += 1



##### Adding Hooks
# afterStateChange --> base states
# browser.setupMenus --> loading browser
# setupEditorShortcuts --> editor (in browser and add)
# showAnswer --> new answer
# AddCards.onHistory --> opening browser via Add Cards
# (Note: Decided to remove last one since obsolete)
#
addHook("afterStateChange", onState)
addHook("browser.setupMenus", onBrowse)
addHook("setupEditorShortcuts", onEditor)
addHook("showAnswer", onAnswer)
#addHook("AddCards.onHistory", onEditor)
