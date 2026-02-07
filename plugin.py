from .common import *
from .SportsMonitor import SportsMonitor
from .Screens.SimpleSportsScreen import SimpleSportsScreen
import SimplySports.globals as globals_mod

def init_monitor():
    if globals_mod.global_sports_monitor is None:
        globals_mod.global_sports_monitor = SportsMonitor()

init_monitor()
from .globals import global_sports_monitor

# ==============================================================================
# MAIN LAUNCHER
# ==============================================================================
def main(session, **kwargs):
    def callback(result=None):
        if result is True:
            session.openWithCallback(callback, SimpleSportsScreen)
            
    session.openWithCallback(callback, SimpleSportsScreen)

# ==============================================================================
# PLUGIN REGISTRATION
# ==============================================================================
def menu(menuid, **kwargs):
    if menuid == "mainmenu":
        return [("SimplySports", main, "simply_sports", 44)]
    return []

def Plugins(**kwargs):
    lst = [
        PluginDescriptor(
            name="SimplySports",
            description="Live Sports Scores, Alerts, and EPG by reali22",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="picon.png",
            fnc=main
        ),
        PluginDescriptor(
            name="SimplySports",
            description="Live Sports Scores, Alerts, and EPG by reali22",
            where=PluginDescriptor.WHERE_EXTENSIONSMENU,
            fnc=main
        )
    ]
    if global_sports_monitor and global_sports_monitor.show_in_menu:
        lst.append(PluginDescriptor(
            name="SimplySports",
            description="Live Sports Scores, Alerts, and EPG by reali22",
            where=PluginDescriptor.WHERE_MENU,
            fnc=menu
        ))
    return lst
