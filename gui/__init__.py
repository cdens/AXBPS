# =============================================================================
#     Author: Casey R. Densmore, 12FEB2022
#
#    This file is part of the Airborne eXpendable Buoy Processing System (AXBPS)
#
#    AXBPS is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    AXBPS is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with AXBPS.  If not, see <https://www.gnu.org/licenses/>.
# =============================================================================


from PyQt5.QtWidgets import QMainWindow
from traceback import print_exc as trace_error

class RunProgram(QMainWindow):
    
    #importing methods from other files
    from ._DASfunctions import (makenewprocessortab, prep_graph_and_table, config_graph_ticks_lims, datasourcerefresh, probetypechange, datasourcechange, changefrequencytomatchchannel, changechanneltomatchfrequency, changechannelandfrequency, updateDASsettings, startprocessor, prepprocessor, runprocessor, stopprocessor, gettabnumfromID, triggerUI, updateUIinfo, update_AXBT_DAS, update_AXCTD_DAS, updateUIfinal, failedWRmessage, updateaudioprogressbar, AudioWindow, AudioWindowSignals, audioWindowClosed, processprofile)
    from ._PEfunctions import (makenewproftab, selectdatafile, checkdatainputs_editorinput, continuetoqc, runqc, applychanges, updateprofeditplots, generateprofiledescription, get_open_subfigure, addpoint, removepoint, removerange, on_press_spike, on_release, toggleclimooverlay, CustomToolbar)
    from ._GUIfunctions import (initUI, loaddata, buildmenu, configureGuiFont, changeGuiFont, openpreferencesthread, updatesettings, settingsclosed, updateGPSdata, updateGPSsettings)
    from ._globalfunctions import (addnewtab, whatTab, renametab, add_asterisk, remove_asterisk, setnewtabcolor, closecurrenttab, postwarning, posterror, postwarning_option, closeEvent, parsestringinputs, savedataincurtab, check_filename, saveDASfiles, savePEfiles)
    
    
    # INITIALIZE WINDOW, INTERFACE
    def __init__(self):
        super().__init__()
        
        try:
            self.initUI() #creates GUI window
            self.buildmenu() #Creates interactive menu, options to create tabs and run ARES systems
            self.loaddata() #loads climo and bathy data into program first if using the full datasets
            self.makenewprocessortab() # opens a data acquisition tab on startup
            
        except Exception:
            trace_error()
            self.posterror("Failed to initialize the program.")
            
            

    
    
