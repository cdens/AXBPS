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

from platform import system as cursys

from struct import calcsize
from os import remove, path, listdir
from traceback import print_exc as trace_error
from datetime import datetime

if cursys() == 'Windows':
    import ctypes
    
import pyaudio
    
from tempfile import gettempdir

from PyQt5.QtWidgets import (QAction, QWidget, QFileDialog, QTabWidget, QVBoxLayout, QDesktopWidget, 
    QStyle, QStyleOptionTitleBar, QMenu, QActionGroup)
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QIcon, QFont, QColor
from PyQt5.Qt import QThreadPool

import numpy as np
import scipy.io as sio
from cartopy.io import shapereader

import lib.GPS_COM_interaction as gps
import gui._settingswindow as swin


from ._globalfunctions import (addnewtab, whatTab, renametab, setnewtabcolor, closecurrenttab, savedataincurtab, postwarning, posterror, postwarning_option, closeEvent, parsestringinputs)



#initializing the UI, setting default file paths, initializing the threadpool, and loading receiver DLL files
def initUI(self):

    #setting window size
    cursize = QDesktopWidget().availableGeometry(self).size()
    titleBarHeight = self.style().pixelMetric(QStyle.PM_TitleBarHeight, QStyleOptionTitleBar(), self)
    self.resize(cursize.width(), cursize.height()-titleBarHeight)
    
    vstr = open('version.txt').read().strip()

    # setting title/icon, background color
    self.setWindowTitle('Airborne eXpendable Buoy Processing System v'+vstr)
    self.setWindowIcon(QIcon('lib/dropicon.png'))
    p = self.palette()
    p.setColor(self.backgroundRole(), QColor(255,255,255))
    self.setPalette(p)

    #setting slash dependent on OS
    if cursys() == 'Windows':
        self.slash = '\\'
    else:
        self.slash = '/'

    #getting temporary directory for files
    self.systempdir = gettempdir()
    self.tempdir = self.systempdir
    
    #settings file source- places dotfile in user's home directory
    self.settingsfile = path.expanduser("~") + self.slash + ".AXBPS_settings"
    
    #setting up file dialog options
    self.fileoptions = QFileDialog.Options()
    self.fileoptions |= QFileDialog.DontUseNativeDialog
    defaultpath = path.expanduser("~")
    if path.exists(path.join(defaultpath,"Documents")): #default to Documents directory if it exists, otherwise home directory
        defaultpath = path.join(defaultpath,"Documents")
    self.defaultfilereaddir = defaultpath
    self.defaultfilewritedir = defaultpath

    #setting up list to store data for each tab
    self.tabIDs = []
    self.alltabdata = []
    
    #tab tracking
    self.totaltabs = -1
    
    #probe options
    self.probetypes = ["AXBT","AXCTD", "AXCP"]
    self.defaultprobe = "AXBT"
    
    #loading default program settings
    self.settingsdict = swin.readsettings(self.settingsfile)
    self.settingsdict["comports"],self.settingsdict["comportdetails"] = gps.listcomports() #pulling available port info from OS
            
    #changes default com port to 'none' if previous default from settings isn't detected
    if not self.settingsdict["comport"] in self.settingsdict["comports"]:
        self.settingsdict["comport"] = 'n'
        
        
    
    if cursys() == 'Windows':
        myappid = 'AXBPS_v' + vstr  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        
    # prepping main window/widget, configuring tab widget
    mainWidget = QWidget()
    self.setCentralWidget(mainWidget)
    mainLayout = QVBoxLayout()
    mainWidget.setLayout(mainLayout)
    self.tabWidget = QTabWidget()
    mainLayout.addWidget(self.tabWidget)
    self.vBoxLayout = QVBoxLayout()
    self.tabWidget.setLayout(self.vBoxLayout)
    self.show()
    
    #changing default font appearance for program- REPLACE WITH SETFONT FUNCTION
    self.configureGuiFont()

    #track whether preferences tab is opened
    self.preferencesopened = False
    
    
    # creating threadpool
    self.threadpool = QThreadPool()
    self.threadpool.setMaxThreadCount(7)
    
    # variable to prevent recursion errors when updating VHF channel/frequency across multiple tabs
    self.changechannelunlocked = True
    self.selectedChannel = -2 #-2=no box opened, -1 = box opened, 0 = box closed w/t selection, > 0 = selected channel

    # delete all temporary files
    allfilesanddirs = listdir(self.systempdir)
    for cfile in allfilesanddirs:
        if len(cfile) >= 5:
            cfilestart = cfile[:4]
            cfileext = cfile[-3:]
            if (cfilestart.lower() == 'temp' and cfileext.lower() == 'wav') or (cfilestart.lower() == 'sigd' and cfileext.lower() == 'txt'):
                remove(self.systempdir + self.slash + cfile)
    
    #initialize the gps log that is used in the mission plotter
    self.latlog = []
    self.lonlog = []
    self.altlog = []
    
    #initializing GPS thread
    self.goodPosition = False
    self.lat = 0. #position
    self.lon = 0.
    self.datetime = datetime(1,1,1) #default date- January 1st, 0001 so default GPS time is outside valid window for use
    self.bearing = 0. #bearing calculated from previous positions
    self.qual = -1 #GPS fix quality
    self.nsat = -1 #number of satellites in contact
    self.alt = 0. #altitude
    self.sendGPS2settings = False #true when settings tab is open and a GPS is connected
    self.GPSthread = gps.GPSthread(self.settingsdict["comport"],self.settingsdict['gpsbaud'])
    self.GPSthread.signals.update.connect(self.updateGPSdata) #function located in this file after settingswindow update
    self.threadpool.start(self.GPSthread)
    
    #reason codes for profiles that don't have good data
    self.reason_code_strings = ["Good Profile", "No Signal", "Spotty/Intermittent", "Hung Probe/Early Start", "Isothermal", "Late Start", "Slow Falling", "Bottom Strike", "Climatology Mismatch", "Action Required/Reprocess"]


    # loading all radio receiver library files
    self.dll = {}
    self.dll['PA'] = pyaudio.PyAudio()
    if cursys() == 'Windows': #radio receivers with windows DLLs to load
        try:
            if calcsize("P")*8 == 32: #32-bit
                self.dll['WR'] = ctypes.WinDLL("data/WRG39WSBAPI_32.dll")#, winmode=ctypes.RTLD_GLOBAL) #32-bit
            elif calcsize("P")*8 == 64: #64-bit
                self.dll['WR'] = ctypes.WinDLL("data/WRG39WSBAPI_64.dll")#, winmode=ctypes.RTLD_GLOBAL) #64-bit
            else:
                self.postwarning("WiNRADIO driver not loaded (unrecognized system architecture: "+str(calcsize("P")*8)+")!")
        except:
            self.postwarning("Failed to load WiNRADIO driver!")
            trace_error()
    else:
        self.postwarning("WiNRADIO communications only supported with Windows! Processing and editing from audio/ASCII files is still available.")
        


        
        
        
# =============================================================================
#    LOAD DATA, BUILD MENU, GENERAL SETTINGS 
# =============================================================================

#saves a tiny amount of time by loading climatology and bathymetry data indices once each on initialization
def loaddata(self):
    self.climodata = {}
    self.bathymetrydata = {}
    
    # Climatology data are broken up into 6deg x 6deg 3D cubes per month and topography/bathymetry data are broken up into 1deg x 1deg 2D squares
    #   > data/climo/Z.txt holds the depths associated with each climatology file
    # The vals.txt files for climo and bathy data hold the lat/lon offets (in degrees) for each square. For example,
    #    if bathy/vals.txt contains the values [0,0.25,0.5,0.75], then a bathymetry file for 38N,72E would have latitude
    #    indices of [38,38.25,38.5,38.75] and longitude indices of [72,72.25,72.5,72.75] 
    
    #loading climatology indices
    try: 
        self.climodata["vals"] = np.array([float(i) for i in open('data/climo/latlonoffsets.txt').read().strip().split(',') if i != ''])
        self.climodata["depth"] = np.array([float(i) for i in open('data/climo/Z.txt').read().strip().split(',') if i != ''])
    except:
        self.posterror("Unable to find/load climatology data")
    
    #loading bathymetry indices
    try: 
        self.bathymetrydata["vals"] = np.array([float(i) for i in open('data/bathy/vals.txt').read().strip().split(',') if i != ''])
    except:
        self.posterror("Unable to find/load bathymetry data")  
    
    #loading regions shape file to identify name of ocean/sea/water where a profile was collected (for location plots)      
    try: 
        self.landshp = shapereader.Reader('data/regions/GSHHS_i_L1.shp')
    except:
        self.posterror("Unable to read land area shape file (GSHHS_i_L1.shp)")
        
        
    
#builds file menu for GUI
def buildmenu(self):
    #setting up primary menu bar
    menubar = self.menuBar()
    FileMenu = menubar.addMenu('Options')
    
    #File>New Signal Processor (Mk21) Tab
    newsigtab = QAction('&New Data Acquisition System Tab',self)
    newsigtab.setShortcut('Ctrl+N')
    newsigtab.triggered.connect(self.makenewprocessortab)
    FileMenu.addAction(newsigtab)
    
    #File>New Profile Editor Tab
    newptab = QAction('&New Profile Editor',self)
    newptab.setShortcut('Ctrl+P')
    newptab.triggered.connect(self.makenewproftab)
    FileMenu.addAction(newptab)
        
    #File>Rename Current Tab
    renametab = QAction('&Rename Current Tab',self)
    renametab.setShortcut('Ctrl+R')
    renametab.triggered.connect(self.renametab)
    FileMenu.addAction(renametab)
    
    #File>Close Current Tab
    closetab = QAction('&Close Current Tab',self)
    closetab.setShortcut('Ctrl+X')
    closetab.triggered.connect(self.closecurrenttab)
    FileMenu.addAction(closetab)
    
    #File>Save Files
    savedataintab = QAction('&Save Profile',self)
    savedataintab.setShortcut('Ctrl+S')
    savedataintab.triggered.connect(self.savedataincurtab)
    FileMenu.addAction(savedataintab)

    #File> Open Settings
    openpreferences = QAction('&Preferences', self)
    openpreferences.setShortcut('Ctrl+T')
    openpreferences.triggered.connect(self.openpreferencesthread)
    FileMenu.addAction(openpreferences)
    
    #GUI font size control- !! this requires that self.configureGuiFont() has already been run to set self.fontoptions, self.fonttitles, and self.fontindex
    self.fontMenu = QMenu("Font Size") #making menu, action group
    self.fontMenuActionGroup = QActionGroup(self)
    self.fontMenuActionGroup.setExclusive(True)
    
    try: #getting current option (defaults to size=14 if option fails)
        self.fontindex = self.fontoptions.index(self.settingsdict["fontsize"])
    except:
        self.fontindex = 2
        self.settingsdict["fontsize"] = 14
        self.labelfont = QFont()
        self.labelfont.setFamily("Arial")
        self.labelfont.setPointSize(self.settingsdict["fontsize"])
        self.setFont(self.labelfont)
    
    #adding options to menu bar, checking current option
    for i,option in enumerate(self.fonttitles):
        curaction = self.fontMenuActionGroup.addAction(QAction(option, self, checkable=True))
        self.fontMenu.addAction(curaction)
        if i == self.fontindex:
            curaction.setChecked(True)
        
    self.fontMenuActionGroup.triggered.connect(self.changeGuiFont) #connect function to change font if user selects it
    FileMenu.addMenu(self.fontMenu)
    
    
        
        
        
# =============================================================================
#    ARES FONT SIZE CONTROL
# =============================================================================
        
        
def configureGuiFont(self):
    
    #font options and corresponding menu entires (options saved to self for later access)
    self.fontoptions = [8,12,14,16,20] 
    self.fonttitles = ["Very Small (8)", "Small (12)", "Medium (14)", "Large (16)", "Very Large (20)"]
    
    #initializing font
    self.labelfont = QFont()
    self.labelfont.setFamily("Arial")
    
    #getting current option (defaults to size=14 if option fails)
    try: 
        self.fontindex = self.fontoptions.index(self.settingsdict["fontsize"])
        
    except: #if error- set default font size to 14 !!Must also change this in settingswindow.setdefaultsettings()
        self.fontindex = 2
        self.settingsdict["fontsize"] = self.fontoptions[self.fontindex] 
                
    #applying font size to general font
    self.labelfont.setPointSize(self.settingsdict["fontsize"])        
    
    #list of widgets to be updated for each type:
    daswidgets = ["datasourcetitle", "refreshdataoptions", "datasource", "probetitle", "probetype", "channeltitle", "freqtitle", "vhfchannel", "vhffreq", "startprocessing", "stopprocessing","processprofile", "saveprofile", "datetitle", "dateedit", "timetitle", "timeedit", "lattitle", "latedit", "lontitle","lonedit", "idtitle","idedit", "table", "tableheader"] #signal processor (data acquisition system)
    peinputwidgets = ["title", "probetitle", "probetype", "lattitle", "latedit", "lontitle", "lonedit", "datetitle", "dateedit", "timetitle", "timeedit", "idtitle", "idedit", "logtitle", "logedit", "logbutton", "submitbutton"]
    pewidgets = ["toggleclimooverlay", "addpoint", "removepoint", "removerange", "sfccorrectiontitle", "sfccorrection", "maxdepthtitle", "maxdepth", "depthdelaytitle", "depthdelay", "runqc", "proftxt", "isbottomstrike", "rcodetitle", "rcode"]
    self.tabWidget.setFont(self.labelfont)
    
    #applying updates to all tabs- method dependent on which type each tab is
    for ctab,_ in enumerate(self.alltabdata):
        ctabtype = self.alltabdata[ctab]["tabtype"]
        
        if ctabtype[:3] == "DAS": #data acquisition
            curwidgets = daswidgets
        elif ctabtype == "PE_u": #prompt to select ASCII file
            curwidgets = peinputwidgets
        elif ctabtype == "PE_p": #profile editor
            curwidgets = pewidgets
        else:
            self.posterror(f"Unable to identify tab type when updating font: {ctabtype}")
            curwidgets = []
            
        #updating font sizes for tab and all widgets
        for widget in curwidgets:
            self.alltabdata[ctab]["tabwidgets"][widget].setFont(self.labelfont)
            
            
            
def changeGuiFont(self): 
    try:
        curind = self.fontoptions.index(self.settingsdict["fontsize"])
        for i,action in enumerate(self.fontMenuActionGroup.actions()):
            if action.isChecked():
                curind = i
                
        self.settingsdict["fontsize"] = self.fontoptions[curind]
        self.configureGuiFont()
        
        #save new font to settings file
        swin.writesettings(self.settingsfile, self.settingsdict)
    
    except Exception:
        trace_error()
        self.posterror("Failed to update GUI font!")
        
        
        
        

# =============================================================================
#     PREFERENCES THREAD CONNECTION AND SLOT
# =============================================================================

#opening advanced preferences window (selected from top menu)
def openpreferencesthread(self):
    if not self.preferencesopened: #if the window isn't opened in background- create a new window
        self.preferencesopened = True
        
        self.settingsthread = swin.RunSettings(self.settingsdict)
        self.settingsthread.signals.exported.connect(self.updatesettings)
        self.settingsthread.signals.closed.connect(self.settingsclosed)
        self.settingsthread.signals.updateGPS.connect(self.updateGPSsettings)
        
    else: #window is opened in background- bring to front
        self.settingsthread.show()
        self.settingsthread.raise_()
        self.settingsthread.activateWindow()

        
#slot to receive/update changed settings from advanced preferences window
@pyqtSlot(dict)
def updatesettings(self,settingsdict):

    #save settings to class
    self.settingsdict = settingsdict

    #save settings to file
    swin.writesettings(self.settingsfile, self.settingsdict)
    
    #update DAS settings for actively processing tabs
    self.updateDASsettings()
    

#slot to update main GUI loop if the preferences window has been closed
@pyqtSlot(bool)
def settingsclosed(self,isclosed):
    if isclosed:
        self.preferencesopened = False
        self.sendGPS2settings = False #don't try to send GPS position to settings if window is closed
        
        
#function to receive request for GPS update from settings window
@pyqtSlot(str,int)
def updateGPSsettings(self,comport,baudrate):
    self.GPSthread.changeConfig(comport,baudrate)
    self.settingsdict['comport'] = comport
    self.settingsdict['gpsbaud'] = baudrate
    self.sendGPS2settings = True
    
        
#slot to receive (and immediately update) GPS port and baud rate
@pyqtSlot(int,float,float,datetime,int,int,float)
def updateGPSdata(self,isGood,lat,lon,gpsdatetime,nsat,qual,alt):
    
    if isGood == 0: #data contains a valid GPS fix
        dlat = lat - self.lat #for bearing
        dlon = lon - self.lon
        
        self.lat = lat
        self.lon = lon
        self.datetime = gpsdatetime
        self.nsat = nsat
        self.qual = qual
        self.alt = alt
        self.goodPosition = True
        
        #add to the position log
        self.latlog.append(lat)
        self.lonlog.append(lon)
        self.altlog.append(alt)
        
        self.sendGPS2settings = True #start sending GPS to settings again if its good
        
        if dlat != 0. or dlon != 0.: #only update bearing if position changed
            self.bearing = 90 - np.arctan2(dlat,dlon)*180/np.pi #oversimplified- doesn't account for cosine contraction
            if self.bearing < 0:
                self.bearing += 360
        
        if self.preferencesopened: #only send GPS data to settings window if it's open
            self.settingsthread.refreshgpsdata(True, lat, lon, gpsdatetime, nsat, qual, alt)
            
    else: #data received doesn't contain a valid GPS fix
        self.goodPosition = False
        if self.preferencesopened and self.sendGPS2settings:
            self.settingsthread.refreshgpsdata(False, 0., 0., datetime(1,1,1), 0, 0, 0.)
            self.sendGPS2settings = False #stop sending GPS data to settings if the data is bad
            self.settingsthread.postGPSissue(isGood) #opens a message in the settings window with cause of GPS issue
            

        
