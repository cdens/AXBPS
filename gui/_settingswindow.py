# =============================================================================
#     Author: LTJG Casey R. Densmore, 12FEB2022
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



# =============================================================================
#   CALL NECESSARY MODULES HERE
# =============================================================================
from traceback import print_exc as trace_error
import numpy as np
from os import remove, path

from PyQt5.QtWidgets import (QMainWindow, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton,
    QMessageBox, QWidget, QTabWidget, QGridLayout, QSlider, QComboBox, QLineEdit)
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QObject
from PyQt5.QtGui import QIcon, QColor, QPalette, QBrush, QLinearGradient, QFont

import lib.GPS_COM_interaction as gps
import lib.DAS.common_DAS_functions as cdf #for temperature conversion for flims_axbt

from platform import system as cursys
if cursys() == 'Windows':
    from ctypes import windll
    
    
    

# =============================================================================
#   INITIALIZE/READ/WRITE AXBPS SETTINGS
# =============================================================================
    

#Default settings for program
def setdefaultsettings():
    
    settingsdict = {}
    
    # processor preferences
    settingsdict["autodtg"] = True  # auto determine profile date/time as system date/time on clicking "START"
    settingsdict["autolocation"] = True #auto determine location with GPS
    settingsdict["autoid"] = True #autopopulate platform ID
    settingsdict["platformid"] = 'NNNNN'
    settingsdict["savenvo_raw"] = False
    settingsdict["saveedf_raw"] = True
    settingsdict["savewav_raw"] = True
    settingsdict["savesig_raw"] = False
    settingsdict["dtgwarn"] = True  # warn user if entered dtg is more than 12 hours old or after current system time (in future)
    settingsdict["renametabstodtg"] = True  # auto rename tab to dtg when loading profile editor
    settingsdict["autosave"] = False  # automatically save raw data before opening profile editor (otherwise brings up prompt asking if want to save)
    settingsdict["fftwindow"] = 0.3  # window to run FFT (in seconds)
    settingsdict["minfftratio"] = 0.42  # minimum signal to noise ratio to ID data
    settingsdict["minsiglev"] = 58.  # minimum total signal level to receive data

    settingsdict["triggerfftratio"] = 0.8  # minimum signal to noise ratio to ID data
    settingsdict["triggersiglev"] = 70.  # minimum total signal level to receive data
    
    settingsdict["tcoeff_axbt"] = [-40,0.02778,0,0] #temperature conversion coefficients
    settingsdict["zcoeff_axbt"] = [0,1.524,0,0] #depth conversion coefficients
    settingsdict["flims_axbt"] = [1300, 2800] #valid frequency range limits
    
    settingsdict["zcoeff_axctd"] = [0.72, 2.76124, -0.000238007, 0]
    settingsdict["tcoeff_axctd"] = [-5.5387245882, 0.0107164443, 0,0]
    settingsdict["ccoeff_axctd"] = [-0.0622192776, 0.0153199220, 0,0]
    
    #profeditorpreferences
    settingsdict["useclimobottom"] = True  # use climatology to ID bottom strikes
    settingsdict["overlayclimo"] = True  # overlay the climatology on the plot
    settingsdict["comparetoclimo"] = True  # check for climatology mismatch and display result on plot
    settingsdict["savefin_qc"] = True  # file types to save
    settingsdict["saveedf_qc"] = True
    settingsdict["savejjvv_qc"] = True
    settingsdict["savebufr_qc"] = True
    settingsdict["saveprof_qc"] = True
    settingsdict["saveloc_qc"] = True
    settingsdict["useoceanbottom"] = True  # use NTOPO1 bathymetry data to ID bottom strikes
    settingsdict["checkforgaps"] = True  # look for/correct gaps in profile due to false starts from VHF interference
    settingsdict["smoothlev"] = 8.  # Smoothing Window size (m)
    settingsdict["profres"] = 1. #profile minimum vertical resolution (m)
    settingsdict["maxstdev"] = 1.5 #profile standard deviation coefficient for despiker (autoQC)
    settingsdict["originatingcenter"] = 62 #BUFR table code for NAVO

    settingsdict["comport"] = 'n' #default com port is none
    settingsdict["gpsbaud"] = 4800 #baud rate for GPS- default to 4800
    
    settingsdict["fontsize"] = 14 #font size for general UI
    
    return settingsdict


#lists of settings broken down by data type (for settings file reading/writing)
strsettings = ["platformid", "comport"] #settings saved as strings
listsettings = ["tcoeff_axbt", "zcoeff_axbt", "flims_axbt", "zcoeff_axctd", "tcoeff_axctd", "ccoeff_axctd"] #saved as lists of coefficients/parameters (each element is a float)
floatsettings = ["fftwindow", "minsiglev", "minfftratio", "triggersiglev", "triggerfftratio", "smoothlev", "profres", "maxstdev"] #saved as floats
intsettings = ["originatingcenter", "gpsbaud", "fontsize"] #saved as ints
boolsettings = ["autodtg", "autolocation", "autoid", "savenvo_raw", "saveedf_raw", "savewav_raw", "savesig_raw", "dtgwarn", "renametabstodtg", "autosave", "useclimobottom", "overlayclimo", "comparetoclimo", "savefin_qc", "savejjvv_qc", "saveedf_qc", "savebufr_qc", "saveprof_qc", "saveloc_qc", "useoceanbottom", "checkforgaps", ] #saved as boolean


class SettingNotRecognized(Exception):
    def __init__(self, csetting, cvalue):
        self.message = f"AXBPS setting {csetting} (requested value = {cvalue}) not found"
        super().__init__(self.message)

#Read settings from txt file
def readsettings(filename):
    try:
        settingsdict = {}
        isgood = True
        
        with open(filename) as file: #read settings from file
            for cline in file.readlines(): #read each line
                line = cline.strip().split(':') #pulling setting name and value for each line
                csetting = line[0]
                cvalue = line[1]
                
                if csetting in strsettings:
                    cdata = cvalue.strip() #string, remove white space leading/trailing
                elif csetting in listsettings: #multiple values per setting, forward slash delimited
                    cdata = []
                    for val in cvalue.split('/'): 
                        cdata.append(float(val))
                elif csetting in floatsettings:
                    cdata = float(cvalue) #float
                elif csetting in intsettings: #integer
                    cdata = int(cvalue) 
                elif csetting in boolsettings: #boolean
                    cdata = bool(int(cvalue))
                else:
                    raise SettingNotRecognized(csetting, cvalue)
                
                settingsdict[csetting] = cdata #adding current setting to dict storing all settings
                
    #if settings file doesn't exist or is invalid, rewrites file with default settings
    except:
        isgood = False
        trace_error() #report issue
        
    
    #verifying that all settings are present and have the correct type, overwriting bad settings with default values
    setting_fields = [strsettings,listsettings,floatsettings,intsettings,boolsettings]
    setting_types = [str,list,float,int,bool]
    defaultsettingsdict = setdefaultsettings()
    for (cfieldlist,ctype) in zip(setting_fields,setting_types):
        for cfield in cfieldlist:
            needsreplaced = False
            if not cfield in settingsdict.keys():
                needsreplaced = True
            elif type(settingsdict[cfield]) != ctype:
                needsreplaced = True
            if needsreplaced:
                isgood = False
                settingsdict[cfield] = defaultsettingsdict[cfield]
    
    if not isgood: #update settings file if it had to be corrected
        writesettings(filename, settingsdict)
        
    return settingsdict

    
    
#Write settings from txt file
def writesettings(filename,settingsdict):
    
    #overwrites file by deleting if it exists
    if path.exists(filename):
        remove(filename)

    #writes settings to file
    with open(filename,'w') as file:
        
        try:
            for csetting in strsettings: #string settings
                file.write(f'{csetting}: {settingsdict[csetting]}\n')
            for csetting in listsettings: #list settings
                file.write(f'{csetting}: {"/".join([str(cd) for cd in settingsdict[csetting]])}\n')
            for csetting in floatsettings: #float settings
                file.write(f'{csetting}: {float(settingsdict[csetting])}\n')
            for csetting in intsettings: #int settings
                file.write(f'{csetting}: {int(settingsdict[csetting])}\n')
            for csetting in boolsettings: #bool settings
                file.write(f'{csetting}: {int(settingsdict[csetting])}\n') #stores bool settings as 1 or 0
                
        except KeyError:
            trace_error()
            return False
    
    return True
            
            

# =============================================================================
#   SETTINGS WINDOW PROGRAM
# =============================================================================  
    


#   DEFINE CLASS FOR SETTINGS (TO BE CALLED IN THREAD)
class RunSettings(QMainWindow):

    # =============================================================================
    #   INITIALIZE WINDOW, INTERFACE
    # =============================================================================
    def __init__(self,settingsdict):
        super().__init__()

        try:
            self.initUI()

            self.signals = SettingsSignals()

            #records current settings received from main loop
            self.settingsdict = settingsdict
            
            #defining constants for labels called from multiple points
            self.defineconstants()

            #building window/tabs
            self.buildcentertable()
            self.makeprocessorsettingstab()  # processor settings
            self.makeaxbtconvertsettingstab() #temperature/depth conversion eqn settings
            self.makeprofileeditorsettingstab() #profile editor tab
            self.makegpssettingstab() #add GPS settings

        except Exception:
            trace_error()
            self.posterror("Failed to initialize the settings menu.")

            
            
    def initUI(self):

        # setting title/icon, background color
        self.setWindowTitle('AXBPS Settings')
        self.setWindowIcon(QIcon('lib/dropicon.png'))
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(255, 255, 255))
        self.setPalette(p)

        if cursys() == 'Windows':
            myappid = 'AXBPS_v' + vstr  # arbitrary string
            windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        # changing font size
        font = QFont()
        font.setPointSize(11)
        font.setFamily("Arial")
        self.setFont(font)

        # prepping to include tabs
        self.mainWidget = QWidget()
        self.setCentralWidget(self.mainWidget)
        self.mainLayout = QGridLayout()
        self.mainWidget.setLayout(self.mainLayout)
        self.tabWidget = QTabWidget()

        #adding widgets to main tab, setting spacing
        self.mainLayout.addWidget(self.tabWidget,1,1,1,5)
        self.applysettings = QPushButton('Apply Changes')
        self.applysettings.clicked.connect(self.applychanges)
        self.resetchanges = QPushButton('Reset Defaults')
        self.resetchanges.clicked.connect(self.resetdefaults)
        self.mainLayout.addWidget(self.applysettings,2,2,1,1)
        self.mainLayout.addWidget(self.resetchanges,2,4,1,1)
        colstretches = [3,1,1,1,1,1,3]
        rowstretches = [3,1,1,3]
        for i,r in enumerate(rowstretches):
            self.mainLayout.setRowStretch(i,r)
        for i,c in enumerate(colstretches):
            self.mainLayout.setColumnStretch(i,c)
        self.show()
        
    
    def defineconstants(self):
        #defining constants for labels called from multiple points
        self.label_fftwindow = "FFT Window (s): "
        self.label_minsiglev = "Minimum Signal Level (dB): "
        self.label_minsigrat = "Minimum Signal Ratio (%): "
        self.label_trigsiglev = "Trigger Signal Level (dB): "
        self.label_trigsigrat = "Trigger Signal Ratio (%): "
        self.fixtypes = ["Not Valid", "GPS", "DGPS", "PPS", "RTK", "Float RTK", "Estimated", "Manual Input", "Simulation"]
        
        
        
    # =============================================================================
    #   FUNCTIONS TO UPDATE/EXPORT/RESET SETTINGS
    # =============================================================================
    def applychanges(self):
        self.updatepreferences()
        self.signals.exported.emit(self.settingsdict)

        

    def resetdefaults(self):
        
        #pull default settings, but preserve selected serial port (for GPS) and list of available ports
        comport = self.settingsdict["comport"] #selected port
        comports = self.settingsdict["comports"] #list of available ports
        comportdetails = self.settingsdict["comportdetails"] #list of available port details
        self.settingsdict = setdefaultsettings()
        self.settingsdict["comport"] = comport
        self.settingsdict["comports"] = comports
        self.settingsdict["comportdetails"] = comportdetails
        
        
        self.processortabwidgets["autodtg"].setChecked(self.settingsdict["autodtg"])
        self.processortabwidgets["autolocation"].setChecked(self.settingsdict["autolocation"])
        self.processortabwidgets["autoID"].setChecked(self.settingsdict["autoid"])

        self.processortabwidgets["savenvo_raw"].setChecked(self.settingsdict["savenvo_raw"])
        self.processortabwidgets["saveedf_raw"].setChecked(self.settingsdict["saveedf_raw"])
        self.processortabwidgets["savewav_raw"].setChecked(self.settingsdict["savewav_raw"])
        self.processortabwidgets["savesig_raw"].setChecked(self.settingsdict["savesig_raw"])

        self.processortabwidgets["dtgwarn"].setChecked(self.settingsdict["dtgwarn"])
        self.processortabwidgets["renametab"].setChecked(self.settingsdict["renametabstodtg"])
        self.processortabwidgets["autosave"].setChecked(self.settingsdict["autosave"])

        self.processortabwidgets["fftwindowlabel"].setText(self.label_fftwindow + str(self.settingsdict["fftwindow"]))  # 15
        self.processortabwidgets["fftwindow"].setValue(int(self.settingsdict["fftwindow"] * 100))

        self.processortabwidgets["fftsiglevlabel"].setText(self.label_minsiglev + str(np.round(self.settingsdict["minsiglev"], 2)).ljust(4, '0'))  # 17
        self.processortabwidgets["fftsiglev"].setValue(int(self.settingsdict["minsiglev"]*10))

        self.processortabwidgets["fftratiolabel"].setText(self.label_minsigrat + str(np.round(self.settingsdict["minfftratio"] * 100)))  # 19
        self.processortabwidgets["fftratio"].setValue(int(self.settingsdict["minfftratio"] * 100))

        self.processortabwidgets["triggersiglevlabel"].setText(
            self.label_trigsiglev + str(np.round(self.settingsdict["triggersiglev"], 2)).ljust(4, '0'))  # 17
        self.processortabwidgets["triggersiglev"].setValue(int(self.settingsdict["triggersiglev"]*10))

        self.processortabwidgets["triggerratiolabel"].setText(
            self.label_trigsigrat + str(np.round(self.settingsdict["triggerfftratio"] * 100)))  # 19
        self.processortabwidgets["triggerratio"].setValue(int(self.settingsdict["triggerfftratio"] * 100))
        
        tc = self.settingsdict["tcoeff_axbt"]
        self.axbtconverttabwidgets["F2Tb0"].setText(str(tc[0]))
        self.axbtconverttabwidgets["F2Tb1"].setText(str(tc[1]))
        self.axbtconverttabwidgets["F2Tb2"].setText(str(tc[2]))
        self.axbtconverttabwidgets["F2Tb3"].setText(str(tc[3]))
        self.updateF2Teqn()
        
        zc = self.settingsdict["zcoeff_axbt"]
        self.axbtconverttabwidgets["t2zb0"].setText(str(zc[0]))
        self.axbtconverttabwidgets["t2zb1"].setText(str(zc[1]))
        self.axbtconverttabwidgets["t2zb2"].setText(str(zc[2]))
        self.axbtconverttabwidgets["t2zb3"].setText(str(zc[3]))
        self.updatet2zeqn()
        
        flims_axbt = self.settingsdict["flims_axbt"]
        self.axbtconverttabwidgets["flow"].setValue(flims_axbt[0])
        self.axbtconverttabwidgets["fhigh"].setValue(flims_axbt[1])
        self.updateflims_axbt()

        self.profeditortabwidgets["useclimobottom"].setChecked(self.settingsdict["useclimobottom"])
        self.profeditortabwidgets["comparetoclimo"].setChecked(self.settingsdict["comparetoclimo"])
        self.profeditortabwidgets["overlayclimo"].setChecked(self.settingsdict["overlayclimo"])

        self.profeditortabwidgets["savefin_qc"].setChecked(self.settingsdict["savefin_qc"])
        self.profeditortabwidgets["saveedf_qc"].setChecked(self.settingsdict["saveedf_qc"])
        self.profeditortabwidgets["savejjvv_qc"].setChecked(self.settingsdict["savejjvv_qc"])
        self.profeditortabwidgets["savebufr_qc"].setChecked(self.settingsdict["savebufr_qc"])
        self.profeditortabwidgets["saveprof_qc"].setChecked(self.settingsdict["saveprof_qc"])
        self.profeditortabwidgets["saveloc_qc"].setChecked(self.settingsdict["saveloc_qc"])

        self.profeditortabwidgets["useoceanbottom"].setChecked(self.settingsdict["useoceanbottom"])
        self.profeditortabwidgets["checkforgaps"].setChecked(self.settingsdict["checkforgaps"])
        
        self.profeditortabwidgets["profres"].setValue(self.settingsdict["profres"])
        self.profeditortabwidgets["smoothlev"].setValue(self.settingsdict["smoothlev"])
        self.profeditortabwidgets["maxstdev"].setValue(self.settingsdict["maxstdev"])

        self.profeditortabwidgets["originatingcenter"].setValue(self.settingsdict["originatingcenter"])
        self.updateoriginatingcenter()
        


    def updatepreferences(self): #records current configuration before exporting to main loop

        self.settingsdict["autodtg"] = self.processortabwidgets["autodtg"].isChecked()
        self.settingsdict["autolocation"] = self.processortabwidgets["autolocation"].isChecked()
        self.settingsdict["autoid"] = self.processortabwidgets["autoID"].isChecked()

        self.settingsdict["savenvo_raw"] = self.processortabwidgets["savenvo_raw"].isChecked()
        self.settingsdict["saveedf_raw"] = self.processortabwidgets["saveedf_raw"].isChecked()
        self.settingsdict["savewav_raw"] = self.processortabwidgets["savewav_raw"].isChecked()
        self.settingsdict["savesig_raw"] = self.processortabwidgets["savesig_raw"].isChecked()

        self.settingsdict["dtgwarn"] = self.processortabwidgets["dtgwarn"].isChecked()
        self.settingsdict["renametabstodtg"] = self.processortabwidgets["renametab"].isChecked()
        self.settingsdict["autosave"] = self.processortabwidgets["autosave"].isChecked()

        self.settingsdict["fftwindow"] = float(self.processortabwidgets["fftwindow"].value())/100
        self.settingsdict["minsiglev"] = float(self.processortabwidgets["fftsiglev"].value())/10
        self.settingsdict["minfftratio"] = float(self.processortabwidgets["fftratio"].value())/100

        self.settingsdict["triggersiglev"] = float(self.processortabwidgets["triggersiglev"].value())/10
        self.settingsdict["triggerfftratio"] = float(self.processortabwidgets["triggerratio"].value())/100
        
        #T/Z coefficients and frequency ranges are recorded on every update to their respective fields

        self.settingsdict["platformid"] = self.processortabwidgets["IDedit"].text()

        self.settingsdict["useclimobottom"] = self.profeditortabwidgets["useclimobottom"].isChecked()
        self.settingsdict["comparetoclimo"] =  self.profeditortabwidgets["comparetoclimo"].isChecked()
        self.settingsdict["overlayclimo"] = self.profeditortabwidgets["overlayclimo"].isChecked()

        self.settingsdict["savefin_qc"] = self.profeditortabwidgets["savefin_qc"].isChecked()
        self.settingsdict["saveedf_qc"] = self.profeditortabwidgets["saveedf_qc"].isChecked()
        self.settingsdict["savejjvv_qc"] = self.profeditortabwidgets["savejjvv_qc"].isChecked()
        self.settingsdict["savebufr_qc"] = self.profeditortabwidgets["savebufr_qc"].isChecked()
        self.settingsdict["saveprof_qc"] = self.profeditortabwidgets["saveprof_qc"].isChecked()
        self.settingsdict["saveloc_qc"] = self.profeditortabwidgets["saveloc_qc"].isChecked()

        self.settingsdict["useoceanbottom"] = self.profeditortabwidgets["useoceanbottom"].isChecked()
        self.settingsdict["checkforgaps"] = self.profeditortabwidgets["checkforgaps"].isChecked()

        self.settingsdict["profres"] = self.profeditortabwidgets["profres"].value()
        self.settingsdict["smoothlev"] = self.profeditortabwidgets["smoothlev"].value()
        self.settingsdict["maxstdev"] = self.profeditortabwidgets["maxstdev"].value()

        self.updateoriginatingcenter()
        
        #NOTE: GPS thread is not updated from here since it is configured to autoupdate every time port or baud rate are changed        
    
    

    # =============================================================================
    #     SIGNAL PROCESSOR TAB AND INPUTS HERE
    # =============================================================================
    def makeprocessorsettingstab(self):
        try:

            self.processortab = QWidget()
            self.processortablayout = QGridLayout()
            self.setnewtabcolor(self.processortab)

            self.processortablayout.setSpacing(10)

            self.tabWidget.addTab(self.processortab,'Data Acquisition System Settings')
            self.tabWidget.setCurrentIndex(0)

            # and add new buttons and other widgets
            self.processortabwidgets = {}

            # making widgets
            self.processortabwidgets["autopopulatetitle"] = QLabel('Autopopulate Drop Entries:') #1
            self.processortabwidgets["autodtg"] = QCheckBox('Autopopulate DTG (UTC)') #2
            self.processortabwidgets["autodtg"].setChecked(self.settingsdict["autodtg"])
            self.processortabwidgets["autolocation"] = QCheckBox('Autopopulate Location') #3
            self.processortabwidgets["autolocation"].setChecked(self.settingsdict["autolocation"])
            self.processortabwidgets["autoID"] = QCheckBox('Autopopulate Platform Identifier') #4
            self.processortabwidgets["autoID"].setChecked(self.settingsdict["autoid"])
            self.processortabwidgets["IDlabel"] = QLabel('Platform Identifier:') #5
            self.processortabwidgets["IDedit"] = QLineEdit(self.settingsdict["platformid"]) #6

            self.processortabwidgets["filesavetypes"] = QLabel('Filetypes to save:       ') #7
            self.processortabwidgets["savenvo_raw"] = QCheckBox('NVO File') #8
            self.processortabwidgets["savenvo_raw"].setChecked(self.settingsdict["savenvo_raw"])
            self.processortabwidgets["saveedf_raw"] = QCheckBox('EDF File') #9
            self.processortabwidgets["saveedf_raw"].setChecked(self.settingsdict["saveedf_raw"])
            self.processortabwidgets["savewav_raw"] = QCheckBox('WAV File') #10
            self.processortabwidgets["savewav_raw"].setChecked(self.settingsdict["savewav_raw"])
            self.processortabwidgets["savesig_raw"] = QCheckBox('Signal Data') #11
            self.processortabwidgets["savesig_raw"].setChecked(self.settingsdict["savesig_raw"])

            self.processortabwidgets["dtgwarn"] = QCheckBox('Warn if DTG is not within past 12 hours') #12
            self.processortabwidgets["dtgwarn"].setChecked(self.settingsdict["dtgwarn"])
            self.processortabwidgets["renametab"] = QCheckBox('Auto-rename tab to DTG on transition to profile editor') #13
            self.processortabwidgets["renametab"].setChecked(self.settingsdict["renametabstodtg"])
            self.processortabwidgets["autosave"] = QCheckBox('Autosave raw data files when transitioning to profile editor') #14
            self.processortabwidgets["autosave"].setChecked(self.settingsdict["autosave"])
            
            self.processortabwidgets["axbtsiglabel"] = QLabel("AXBT Signal Settings")
            self.processortabwidgets["fftwindowlabel"] = QLabel(self.label_fftwindow +str(self.settingsdict["fftwindow"]).ljust(4,'0')) #15
            self.processortabwidgets["fftwindow"] = QSlider(Qt.Horizontal) #16
            self.processortabwidgets["fftwindow"].setValue(int(self.settingsdict["fftwindow"] * 100))
            self.processortabwidgets["fftwindow"].setMinimum(10)
            self.processortabwidgets["fftwindow"].setMaximum(100)
            self.processortabwidgets["fftwindow"].valueChanged[int].connect(self.changefftwindow)

            self.processortabwidgets["fftsiglevlabel"] = QLabel(self.label_minsiglev + str(np.round(self.settingsdict["minsiglev"],2)).ljust(4,'0'))  # 17
            self.processortabwidgets["fftsiglev"] = QSlider(Qt.Horizontal)  # 18
            self.processortabwidgets["fftsiglev"].setMinimum(400)
            self.processortabwidgets["fftsiglev"].setMaximum(900)
            self.processortabwidgets["fftsiglev"].setValue(int(self.settingsdict["minsiglev"] * 10))
            self.processortabwidgets["fftsiglev"].valueChanged[int].connect(self.changefftsiglev)

            self.processortabwidgets["fftratiolabel"] = QLabel(self.label_minsigrat + str(np.round(self.settingsdict["minfftratio"]*100)).ljust(4,'0'))  # 19
            self.processortabwidgets["fftratio"] = QSlider(Qt.Horizontal)  # 20
            self.processortabwidgets["fftratio"].setValue(int(self.settingsdict["minfftratio"] * 100))
            self.processortabwidgets["fftratio"].setMinimum(0)
            self.processortabwidgets["fftratio"].setMaximum(100)
            self.processortabwidgets["fftratio"].valueChanged[int].connect(self.changefftratio)

            self.processortabwidgets["triggersiglevlabel"] = QLabel(
                self.label_trigsiglev + str(np.round(self.settingsdict["triggersiglev"], 2)).ljust(4, '0'))  # 17
            self.processortabwidgets["triggersiglev"] = QSlider(Qt.Horizontal)  # 18
            self.processortabwidgets["triggersiglev"].setMinimum(400)
            self.processortabwidgets["triggersiglev"].setMaximum(900)
            self.processortabwidgets["triggersiglev"].setValue(int(self.settingsdict["triggersiglev"] * 10))
            self.processortabwidgets["triggersiglev"].valueChanged[int].connect(self.changetriggersiglev)

            self.processortabwidgets["triggerratiolabel"] = QLabel(
                self.label_trigsigrat + str(np.round(self.settingsdict["triggerfftratio"] * 100)).ljust(4, '0'))  # 19
            self.processortabwidgets["triggerratio"] = QSlider(Qt.Horizontal)  # 20
            self.processortabwidgets["triggerratio"].setValue(int(self.settingsdict["triggerfftratio"] * 100))
            self.processortabwidgets["triggerratio"].setMinimum(0)
            self.processortabwidgets["triggerratio"].setMaximum(100)
            self.processortabwidgets["triggerratio"].valueChanged[int].connect(self.changetriggerratio)

            # formatting widgets
            self.processortabwidgets["IDlabel"].setAlignment(Qt.AlignCenter | Qt.AlignVCenter)

            # should be 24 entries
            widgetorder = ["autopopulatetitle", "autodtg", "autolocation", "autoID", "IDlabel",
                           "IDedit", "filesavetypes", "savenvo_raw", "saveedf_raw","savewav_raw", "savesig_raw",
                           "dtgwarn", "renametab", "autosave", "axbtsiglabel", "fftwindowlabel", "fftwindow",
                           "fftsiglevlabel", "fftsiglev", "fftratiolabel","fftratio", "triggersiglevlabel",
                           "triggersiglev","triggerratiolabel","triggerratio"]

            wcols   = [1, 1, 1, 1, 1, 2, 4, 4, 4, 4, 4, 1, 1, 1, 5, 5, 5, 5, 5, 5, 5, 5, 5,  5,  5]
            wrows   = [1, 2, 3, 4, 5, 5, 1, 2, 3, 4, 5, 7, 8, 9, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
            wrext   = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  1,  1]
            wcolext = [2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 4, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1,  1,  1]

            # adding user inputs
            for i, r, c, re, ce in zip(widgetorder, wrows, wcols, wrext, wcolext):
                self.processortablayout.addWidget(self.processortabwidgets[i], r, c, re, ce)

            # Applying spacing preferences to grid layout
            self.processortablayout.setColumnStretch(0, 0)
            self.processortablayout.setColumnStretch(1, 1)
            self.processortablayout.setColumnStretch(2, 1)
            self.processortablayout.setColumnStretch(3, 2)
            self.processortablayout.setColumnStretch(4, 3)
            for i in range(0,12):
                self.processortablayout.setRowStretch(i, 1)
            self.processortablayout.setRowStretch(13, 4)

            # applying the current layout for the tab
            self.processortab.setLayout(self.processortablayout)

        except Exception:
            trace_error()
            self.posterror("Failed to build new processor tab")
            
            
            
            
            
    # =============================================================================
    #     TEMPERATURE-DEPTH CONVERSION EQNS + LIMITATIONS HERE
    # =============================================================================
    def makeaxbtconvertsettingstab(self):
        try:

            self.tzconverttab = QWidget()
            self.tzconverttablayout = QGridLayout()
            self.setnewtabcolor(self.tzconverttab)

            self.tzconverttablayout.setSpacing(10)

            self.tabWidget.addTab(self.tzconverttab,'AXBT Conversions')
            self.tabWidget.setCurrentIndex(0)

            # and add new buttons and other widgets
            self.axbtconverttabwidgets = {}

            # making widgets
            tc = self.settingsdict["tcoeff_axbt"]
            self.axbtconverttabwidgets["F2Tlabel"] = QLabel('Frequency to Temperature Conversion:') #1
            self.axbtconverttabwidgets["F2Teqn"] = QLabel(f"T = {tc[0]} + {tc[1]}*f + {tc[2]}*f<sup>2</sup> + {tc[3]}*f<sup>3</sup>") #2
            self.axbtconverttabwidgets["F2Tb0"] = QLineEdit(str(tc[0])) #3
            self.axbtconverttabwidgets["F2Tb0"].textChanged.connect(self.updateF2Teqn)
            self.axbtconverttabwidgets["F2Tb1"] = QLineEdit(str(tc[1])) #4
            self.axbtconverttabwidgets["F2Tb1"].textChanged.connect(self.updateF2Teqn)
            self.axbtconverttabwidgets["F2Tb2"] = QLineEdit(str(tc[2])) #5
            self.axbtconverttabwidgets["F2Tb2"].textChanged.connect(self.updateF2Teqn)
            self.axbtconverttabwidgets["F2Tb3"] = QLineEdit(str(tc[3])) #6
            self.axbtconverttabwidgets["F2Tb3"].textChanged.connect(self.updateF2Teqn)
            self.axbtconverttabwidgets["F2Ts0"] = QLabel(" + ") #7
            self.axbtconverttabwidgets["F2Ts1"] = QLabel("* f + ") #8
            self.axbtconverttabwidgets["F2Ts2"] = QLabel("* f<sup>2</sup> + ") #9
            self.axbtconverttabwidgets["F2Ts3"] = QLabel("* f<sup>3</sup> ") #10
            
            zc = self.settingsdict["zcoeff_axbt"]
            self.axbtconverttabwidgets["t2zlabel"] = QLabel('Time Elapsed to Depth Conversion:') #11
            self.axbtconverttabwidgets["t2zeqn"] = QLabel(f"z = {zc[0]} + {zc[1]}*t + {zc[2]}*t<sup>2</sup> + {zc[3]}*t<sup>3</sup>") #12
            self.axbtconverttabwidgets["t2zb0"] = QLineEdit(str(zc[0])) #13
            self.axbtconverttabwidgets["t2zb0"].textChanged.connect(self.updatet2zeqn)
            self.axbtconverttabwidgets["t2zb1"] = QLineEdit(str(zc[1])) #14
            self.axbtconverttabwidgets["t2zb1"].textChanged.connect(self.updatet2zeqn)
            self.axbtconverttabwidgets["t2zb2"] = QLineEdit(str(zc[2])) #15
            self.axbtconverttabwidgets["t2zb2"].textChanged.connect(self.updatet2zeqn)
            self.axbtconverttabwidgets["t2zb3"] = QLineEdit(str(zc[3])) #16
            self.axbtconverttabwidgets["t2zb3"].textChanged.connect(self.updatet2zeqn)
            self.axbtconverttabwidgets["t2zs0"] = QLabel(" + ") #17
            self.axbtconverttabwidgets["t2zs1"] = QLabel("* t + ") #18
            self.axbtconverttabwidgets["t2zs2"] = QLabel("* t<sup>2</sup> + ") #19
            self.axbtconverttabwidgets["t2zs3"] = QLabel("* t<sup>3</sup> ") #20
            
            flims_axbt = self.settingsdict["flims_axbt"]
            self.axbtconverttabwidgets["flimlabel"] = QLabel('Valid Frequency/Temperature Limits:') #21
            self.axbtconverttabwidgets["flowlabel"] = QLabel('Minimum Valid Frequency (Hz):') #22
            self.axbtconverttabwidgets["fhighlabel"] = QLabel('Maximum Valid Frequency (Hz):') #23
            
            self.axbtconverttabwidgets["flow"] = QSpinBox() #24
            self.axbtconverttabwidgets["flow"].setMinimum(0)
            self.axbtconverttabwidgets["flow"].setMaximum(5000)
            self.axbtconverttabwidgets["flow"].setSingleStep(1)
            self.axbtconverttabwidgets["flow"].setValue(flims_axbt[0])
            self.axbtconverttabwidgets["flow"].valueChanged.connect(self.updateflims_axbt)
            self.axbtconverttabwidgets["fhigh"] = QSpinBox() #25
            self.axbtconverttabwidgets["fhigh"].setMinimum(0)
            self.axbtconverttabwidgets["fhigh"].setMaximum(5000)
            self.axbtconverttabwidgets["fhigh"].setSingleStep(1)
            self.axbtconverttabwidgets["fhigh"].setValue(flims_axbt[1])
            self.axbtconverttabwidgets["fhigh"].valueChanged.connect(self.updateflims_axbt)
            
            self.axbtconverttabwidgets["Tlowlabel"]  = QLabel(f"Minimum Valid Temperature (\xB0C): {cdf.dataconvert(flims_axbt[0],tc):5.2f}") #26
            self.axbtconverttabwidgets["Thighlabel"] = QLabel(f"Maximum Valid Temperature (\xB0C): {cdf.dataconvert(flims_axbt[1],tc):5.2f}") #27
            
            
            # formatting widgets 
            self.axbtconverttabwidgets["F2Tlabel"].setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.axbtconverttabwidgets["t2zlabel"].setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.axbtconverttabwidgets["flimlabel"].setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.axbtconverttabwidgets["flowlabel"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.axbtconverttabwidgets["fhighlabel"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            

            # should be XX entries
            widgetorder = ["F2Tlabel", "F2Teqn", "F2Tb0", "F2Tb1", "F2Tb2", "F2Tb3", "F2Ts0", "F2Ts1", "F2Ts2", "F2Ts3", "t2zlabel", "t2zeqn", "t2zb0","t2zb1", "t2zb2", "t2zb3", "t2zs0", "t2zs1", "t2zs2", "t2zs3", "flimlabel", "flowlabel", "fhighlabel", "flow", "fhigh", "Tlowlabel", "Thighlabel"]

            wcols = [1,1,1,1,1,1,2,2,2,2,4,4,4,4,4,4,5,5,5,5,1,0,0,2,2,4,4]
            wrows = [1,2,3,4,5,6,3,4,5,6,1,2,3,4,5,6,3,4,5,6,9,10,11,10,11,10,11]

            wrext = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
            wcolext = [2,2,1,1,1,1,1,1,1,1,2,2,1,1,1,1,1,1,1,1,5,2,2,1,1,2,2]

            # adding user inputs
            for i, r, c, re, ce in zip(widgetorder, wrows, wcols, wrext, wcolext):
                self.tzconverttablayout.addWidget(self.axbtconverttabwidgets[i], r, c, re, ce)

            # Applying spacing preferences to grid layout
            colstretches = [1,2,1,1,2,1,1]
            for i,s in enumerate(colstretches):
                self.tzconverttablayout.setColumnStretch(i, s)
            for i in range(12):
                self.tzconverttablayout.setRowStretch(i, 1)
                
            # applying the current layout for the tab
            self.tzconverttab.setLayout(self.tzconverttablayout)

        except Exception:
            trace_error()
            self.posterror("Failed to build new temperature/depth conversion settings tab")
            
            
            
            
            
            
    def updateF2Teqn(self):
        
        try: #only updates if the values are numeric
            tc = [float(self.axbtconverttabwidgets["F2Tb0"].text()), float(self.axbtconverttabwidgets["F2Tb1"].text()), float(self.axbtconverttabwidgets["F2Tb2"].text()), float(self.axbtconverttabwidgets["F2Tb3"].text())]
            self.axbtconverttabwidgets["F2Teqn"].setText(f"T = {tc[0]} + {tc[1]}*f + {tc[2]}*f<sup>2</sup> + {tc[3]}*f<sup>3</sup>")
            self.settingsdict["tcoeff_axbt"] = tc
        except ValueError:
            pass

       
    def updatet2zeqn(self):
        
        try: #only updates if the values are numeric
            zc = [float(self.axbtconverttabwidgets["t2zb0"].text()), float(self.axbtconverttabwidgets["t2zb1"].text()), float(self.axbtconverttabwidgets["t2zb2"].text()), float(self.axbtconverttabwidgets["t2zb3"].text())]
            self.axbtconverttabwidgets["t2zeqn"].setText(f"z = {zc[0]} + {zc[1]}*t + {zc[2]}*t<sup>2</sup> + {zc[3]}*t<sup>3</sup>")
            self.settingsdict["zcoeff_axbt"] = zc
        except ValueError:
            pass
            
            
    def updateflims_axbt(self):
        
        flims_axbt = [self.axbtconverttabwidgets["flow"].value(), self.axbtconverttabwidgets["fhigh"].value()]
        tc = self.settingsdict["tcoeff_axbt"]
        
        if flims_axbt[1] > flims_axbt[0]: #valid min frequency must be less than valid max frequency
            self.axbtconverttabwidgets["Tlowlabel"].setText(f"Minimum Valid Temperature (\xB0C): {cdf.dataconvert(flims_axbt[0],tc):5.2f}")
            self.axbtconverttabwidgets["Thighlabel"].setText(f"Maximum Valid Temperature (\xB0C): {cdf.dataconvert(flims_axbt[1],tc):5.2f}")
            
            self.settingsdict["flims_axbt"] = flims_axbt
            
        #else: #reset previous setting
        #    self.postwarning("Minimum valid frequency must be less than maximum valid frequency!")
        #    self.axbtconverttabwidgets["flow"].setValue(self.settingsdict["flims_axbt"][0])
        #    self.axbtconverttabwidgets["fhigh"].setValue(self.settingsdict["flims_axbt"][1])
            
            
        
        
            
            

    # =============================================================================
    #     GPS COM PORT SELECTION TAB AND INPUTS HERE
    # =============================================================================

    def makegpssettingstab(self):
        try:

            self.gpstab = QWidget()
            self.gpstablayout = QGridLayout()
            self.setnewtabcolor(self.gpstab)

            self.gpstablayout.setSpacing(10)

            self.tabWidget.addTab(self.gpstab, 'GPS COM Selection')
            self.tabWidget.setCurrentIndex(0)

            # and add new buttons and other widgets
            self.gpstabwidgets = {}

            # making widgets
            self.gpstabwidgets["updateports"] = QPushButton("Update COM Port List") # 1
            self.gpstabwidgets["updateports"].clicked.connect(self.updategpslist)

            # self.gpstabwidgets["refreshgpsdata"] = QPushButton("Refresh GPS Info") # 2
            # self.gpstabwidgets["refreshgpsdata"].clicked.connect(self.refreshgpsdata)

            self.gpstabwidgets["gpsdate"] = QLabel("Date/Time: ") # 2
            self.gpstabwidgets["gpslat"] = QLabel("Latitude: ") # 3
            self.gpstabwidgets["gpslon"] = QLabel("Longitude: ") # 4
            self.gpstabwidgets["gpsnsat"] = QLabel("Connected Satellites:") #5
            self.gpstabwidgets["gpsqual"] = QLabel("Fix Type:") #6
            self.gpstabwidgets["gpsalt"] = QLabel("GPS Altitude:") #7
            
            #creating drop-down selection menu for available serial connections
            self.gpstabwidgets["comporttitle"] = QLabel('Available Serial Connections:')  # 8
            self.gpstabwidgets["comport"] = QComboBox()  # 9
            self.gpstabwidgets["comport"].clear()
            self.gpstabwidgets["comport"].addItem('No Serial Connection Selected')
            for cport in self.settingsdict["comportdetails"]: #adding previously detected ports
                self.gpstabwidgets["comport"].addItem(cport)
                
            #includes comport from settings on list if it isn't 'None selected'
            if self.settingsdict["comport"] != 'n':
                #if the listed receiver is connected, keep setting and set dropdown box to select that receiver
                if self.settingsdict["comport"] in self.settingsdict["comports"]: 
                    self.gpstabwidgets["comport"].setCurrentIndex(self.settingsdict["comports"].index(self.settingsdict["comport"])+1)
                #if the listed receiver is not connected, set setting and current index to N/A
                else:
                    self.settingsdict["comport"] = 'n'    
            #if no receiver is selected, set current index to top
            else:
                self.gpstabwidgets["comport"].setCurrentIndex(0)
                
                
            self.gpstabwidgets["baudtitle"] = QLabel('GPS BAUD Rate:')  # 10
            self.gpstabwidgets["baudrate"] = QComboBox()  # 11
            self.gpstabwidgets["baudrate"].clear()
            
            self.baudrates = [110, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 128000, 256000]
            for rate in self.baudrates: #adding previously detected ports
                self.gpstabwidgets["baudrate"].addItem(str(rate))
            if not self.settingsdict["gpsbaud"] in self.baudrates:
                self.settingsdict["gpsbaud"] = 4800
            self.gpstabwidgets["baudrate"].setCurrentIndex(self.baudrates.index(self.settingsdict["gpsbaud"]))
            
            #connect comport change to function
            self.gpstabwidgets["comport"].currentIndexChanged.connect(self.updateportandbaud)
            self.gpstabwidgets["baudrate"].currentIndexChanged.connect(self.updateportandbaud)
            
            # should be 7 entries
            widgetorder = ["updateports", "gpsdate", "gpslat", "gpslon", "gpsnsat", "gpsqual", "gpsalt", "comporttitle","comport", "baudtitle", "baudrate"]

            wcols = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2]
            wrows = [1, 6, 7, 8, 9, 10, 11, 2, 3, 4, 4]
            wrext = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
            wcolext = [1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1]

            # adding user inputs
            for i, r, c, re, ce in zip(widgetorder, wrows, wcols, wrext, wcolext):
                self.gpstablayout.addWidget(self.gpstabwidgets[i], r, c, re, ce)

            # Applying spacing preferences to grid layout
            self.gpstablayout.setRowStretch(0,4)
            self.gpstablayout.setRowStretch(5,4)
            self.gpstablayout.setRowStretch(9,4)
            self.gpstablayout.setColumnStretch(0,4)
            self.gpstablayout.setColumnStretch(3,4)

            # making the current layout for the tab
            self.gpstab.setLayout(self.gpstablayout)

        except Exception:
            trace_error()
            self.posterror("Failed to build new GPS tab")

            
            
    #updating the selected COM port and baud rate from the menu
    def updateportandbaud(self):
        curcomnum = self.gpstabwidgets["comport"].currentIndex()
        if curcomnum > 0:
            self.settingsdict["comport"] = self.settingsdict["comports"][curcomnum - 1]
        else:
            self.settingsdict["comport"] = 'n'
            
        self.settingsdict['gpsbaud'] = self.baudrates[self.gpstabwidgets["baudrate"].currentIndex()]
            
        self.signals.updateGPS.emit(self.settingsdict["comport"], self.settingsdict["gpsbaud"])
            
            

    #refreshing the list of available COM ports
    def updategpslist(self):
        cport = self.settingsdict["comport"]
        self.gpstabwidgets["comport"].currentIndexChanged.disconnect()
        self.gpstabwidgets["comport"].clear()
        self.gpstabwidgets["comport"].addItem('No COM Port Selected')
        self.settingsdict["comports"],self.settingsdict["comportdetails"] = gps.listcomports()
        for curport in self.settingsdict["comportdetails"]:
            self.gpstabwidgets["comport"].addItem(curport)
            
        self.gpstabwidgets["comport"].currentIndexChanged.connect(self.updateportandbaud) #reconnecting update function
            
        #sets current datasource as active item in list if it can, otherwise resets back to no data
        try:
            self.gpstabwidgets["comport"].setCurrentIndex(self.settingsdict["comports"].index(cport)+1)
        except ValueError: #ValueError raised if set comport isn't in list of available ports
            self.gpstabwidgets["comport"].setCurrentIndex(0)
            self.updateportandbaud()            
            
            

    #attempt to refresh GPS data with currently selected COM port
    def refreshgpsdata(self, isgood, lat, lon, curdate, nsat, qual, alt):
        if isgood:
            if lat > 0:
                latsign = 'N'
            else:
                latsign = 'S'
            if lon > 0:
                lonsign = 'E'
            else:
                lonsign = 'W'
            self.gpstabwidgets["gpsdate"].setText("Date/Time: {} UTC".format(curdate.strftime("%Y-%m-%d %H:%M:%S")))
            self.gpstabwidgets["gpslat"].setText("Latitude: {}{}".format(abs(round(lat,3)),latsign))
            self.gpstabwidgets["gpslon"].setText("Longitude: {}{}".format(abs(round(lon,3)),lonsign))
            if nsat >= 0:
                self.gpstabwidgets["gpsnsat"].setText(f"Connected Satellites: {nsat}")
            if qual >= 0:
                self.gpstabwidgets["gpsqual"].setText(f"Fix Type: {self.fixtypes[qual]}")
            if alt > -1E7:
                self.gpstabwidgets["gpsalt"].setText(f"GPS Altitude: {alt} m")
            
        else:
            self.gpstabwidgets["gpsdate"].setText("Date/Time:")
            self.gpstabwidgets["gpslat"].setText("Latitude:")
            self.gpstabwidgets["gpslon"].setText("Longitude:")
            self.gpstabwidgets["gpsnsat"].setText("Connected Satellites:")
            self.gpstabwidgets["gpsqual"].setText("Fix Type:")
            self.gpstabwidgets["gpsalt"].setText("GPS Altitude:")
            
    
    #receive warning message about GPS connection     
    def postGPSissue(self,flag):
        if flag == 1:
            self.posterror("GPS request timed out!")
        elif flag == 2: #passes error message, refreshes list of ports and sets list to 'no port selected'
            self.updategpslist()
            self.gpstabwidgets["comport"].setCurrentIndex(0) #leave both setCurrentIndex commands (with one after posterror)- necessary for the function to work properly for some reason
            self.posterror("Unable to communicate with specified COM port!")
            self.gpstabwidgets["comport"].setCurrentIndex(0)
    


    # =============================================================================
    #         PROFILE EDITOR TAB
    # =============================================================================
    def makeprofileeditorsettingstab(self):
        try:

            self.profeditortab = QWidget()
            self.profeditortablayout = QGridLayout()
            self.setnewtabcolor(self.profeditortab)

            self.profeditortablayout.setSpacing(10)

            self.tabWidget.addTab(self.profeditortab, 'Profile Editor Settings')
            self.tabWidget.setCurrentIndex(0)

            # and add new buttons and other widgets
            self.profeditortabwidgets = {}

            # making widgets
            self.profeditortabwidgets["climotitle"] = QLabel('Climatology Options:')  # 1
            self.profeditortabwidgets["useclimobottom"] = QCheckBox('Use climatology to detect bottom strikes')  # 2
            self.profeditortabwidgets["useclimobottom"].setChecked(self.settingsdict["useclimobottom"])
            self.profeditortabwidgets["comparetoclimo"] = QCheckBox('Autocompare profile to climatology')  # 3
            self.profeditortabwidgets["comparetoclimo"].setChecked(self.settingsdict["comparetoclimo"])
            self.profeditortabwidgets["overlayclimo"] = QCheckBox('Overlay climatology in saved plots')  # 4
            self.profeditortabwidgets["overlayclimo"].setChecked(self.settingsdict["overlayclimo"])

            self.profeditortabwidgets["filesavetypes"] = QLabel('Filetypes to save:     ')  # 5
            self.profeditortabwidgets["savefin_qc"] = QCheckBox('FIN File')  # 6
            self.profeditortabwidgets["savefin_qc"].setChecked(self.settingsdict["savefin_qc"])
            self.profeditortabwidgets["saveedf_qc"] = QCheckBox('EDF File')  # 6
            self.profeditortabwidgets["saveedf_qc"].setChecked(self.settingsdict["saveedf_qc"])
            self.profeditortabwidgets["savejjvv_qc"] = QCheckBox('JJVV File')  # 7
            self.profeditortabwidgets["savejjvv_qc"].setChecked(self.settingsdict["savejjvv_qc"])
            self.profeditortabwidgets["savebufr_qc"] = QCheckBox('BUFR File')  # 8
            self.profeditortabwidgets["savebufr_qc"].setChecked(self.settingsdict["savebufr_qc"])
            self.profeditortabwidgets["saveprof_qc"] = QCheckBox('Profile PNG')  # 9
            self.profeditortabwidgets["saveprof_qc"].setChecked(self.settingsdict["saveprof_qc"])
            self.profeditortabwidgets["saveloc_qc"] = QCheckBox('Location PNG')  # 10
            self.profeditortabwidgets["saveloc_qc"].setChecked(self.settingsdict["saveloc_qc"])

            self.profeditortabwidgets["othertitle"] = QLabel('Additional Options:')  #fix count
            self.profeditortabwidgets["useoceanbottom"] = QCheckBox(
                'ID bottom strikes with NOAA bathymetry')  # 11
            self.profeditortabwidgets["useoceanbottom"].setChecked(self.settingsdict["useoceanbottom"])
            self.profeditortabwidgets["checkforgaps"] = QCheckBox('ID AXBT false starts')  # 12
            self.profeditortabwidgets["checkforgaps"].setChecked(self.settingsdict["checkforgaps"])

            self.settingsdict["profres"] = float(self.settingsdict["profres"])
            if self.settingsdict["profres"]%0.25 != 0:
                self.settingsdict["profres"] = np.round(self.settingsdict["profres"]*4)/4
            self.profeditortabwidgets["profreslabel"] = QLabel("Minimum Profile Resolution (m)")  # 13
            self.profeditortabwidgets["profres"] = QDoubleSpinBox()  # 14
            self.profeditortabwidgets["profres"].setMinimum(0)
            self.profeditortabwidgets["profres"].setMaximum(50)
            self.profeditortabwidgets["profres"].setSingleStep(0.25)
            self.profeditortabwidgets["profres"].setValue(self.settingsdict["profres"])

            if self.settingsdict["smoothlev"]%0.25 != 0:
                self.settingsdict["smoothlev"] = np.round(self.settingsdict["smoothlev"]*4)/4
            self.profeditortabwidgets["smoothlevlabel"] = QLabel("Smoothing Window (m)")  # 15
            self.profeditortabwidgets["smoothlev"] = QDoubleSpinBox()  # 16
            self.profeditortabwidgets["smoothlev"].setMinimum(0)
            self.profeditortabwidgets["smoothlev"].setMaximum(100)
            self.profeditortabwidgets["smoothlev"].setSingleStep(0.25)
            self.profeditortabwidgets["smoothlev"].setValue(self.settingsdict["smoothlev"])

            if self.settingsdict["maxstdev"]%0.1 != 0:
                self.settingsdict["maxstdev"] = np.round(self.settingsdict["maxstdev"]*10)/10
            self.profeditortabwidgets["maxstdevlabel"] = QLabel("Despiking Coefficient")  # 17
            self.profeditortabwidgets["maxstdev"] = QDoubleSpinBox()  # 18
            self.profeditortabwidgets["maxstdev"].setMinimum(0)
            self.profeditortabwidgets["maxstdev"].setMaximum(2)
            self.profeditortabwidgets["maxstdev"].setSingleStep(0.05)
            self.profeditortabwidgets["maxstdev"].setValue(self.settingsdict["maxstdev"])


            self.profeditortabwidgets["originatingcentername"] = QLabel("")  # 19
            self.profeditortabwidgets["originatingcenter"] = QSpinBox()  # 20
            self.profeditortabwidgets["originatingcenter"].setMinimum(0)
            self.profeditortabwidgets["originatingcenter"].setMaximum(255)
            self.profeditortabwidgets["originatingcenter"].setSingleStep(1)
            self.profeditortabwidgets["originatingcenter"].setValue(self.settingsdict["originatingcenter"])
            self.profeditortabwidgets["originatingcenter"].valueChanged[int].connect(self.updateoriginatingcenter)
            
            try:
                curcentername = self.allcenters[str(self.settingsdict["originatingcenter"]).zfill(3)]
            except:
                curcentername = "Center ID not recognized!"
            self.profeditortabwidgets["originatingcentername"].setText("Center "+str(self.settingsdict["originatingcenter"]).zfill(3)+": "+curcentername)

            # should be 18 entries
            widgetorder = ["climotitle", "useclimobottom", "comparetoclimo", "overlayclimo", "filesavetypes", "savefin_qc", "saveedf_qc", "savejjvv_qc", "savebufr_qc", "saveprof_qc", "saveloc_qc", "othertitle", "useoceanbottom", "checkforgaps", "profreslabel", "profres","smoothlevlabel", "smoothlev", "maxstdevlabel", "maxstdev", "originatingcentername","originatingcenter"]

            wcols   = [1, 1, 1, 1, 4, 4, 4, 4, 4, 4, 4, 1, 1, 1, 5, 5, 5, 5, 5, 5,   1,  1]
            wrows   = [1, 2, 3, 4, 1, 2, 3, 4, 5, 6, 7, 7, 8, 9, 2, 3, 5, 6, 9, 10, 11, 12]
            wrext   = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,   1,  1]
            wcolext = [2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 1, 1, 1, 1, 1, 1,   4,  4]

            # adding user inputs
            for i, r, c, re, ce in zip(widgetorder, wrows, wcols, wrext, wcolext):
                self.profeditortablayout.addWidget(self.profeditortabwidgets[i], r, c, re, ce)

            # Applying spacing preferences to grid layout
            self.profeditortablayout.setColumnStretch(0, 0)
            self.profeditortablayout.setColumnStretch(1, 1)
            self.profeditortablayout.setColumnStretch(2, 1)
            self.profeditortablayout.setColumnStretch(3, 2)
            self.profeditortablayout.setColumnStretch(4, 3)
            for i in range(0, 14):
                self.profeditortablayout.setRowStretch(i, 1)
            self.profeditortablayout.setRowStretch(12, 4)

            # making the current layout for the tab
            self.profeditortab.setLayout(self.profeditortablayout)

        except Exception:
            trace_error()
            self.posterror("Failed to build profile editor tab!")

    
    
    
    # =============================================================================
    #         UPDATE BUFR FORMAT ORIGINATING CENTER ACCORDING TO TABLE
    # =============================================================================
    def updateoriginatingcenter(self):
        self.settingsdict["originatingcenter"] = int(self.profeditortabwidgets["originatingcenter"].value())
        ctrkey = str(self.settingsdict["originatingcenter"]).zfill(3)
        if ctrkey in self.allcenters:
            curcentername = self.allcenters[ctrkey]
        else:
            curcentername = self.allcenters["xxx"]
        self.profeditortabwidgets["originatingcentername"].setText("Center " + ctrkey + ": " + curcentername)
        
        

    #lookup table for originating centers
    def buildcentertable(self):
        self.allcenters = {"000":"       WMO Secretariat               ",
                           "007":"       US NWS: NCEP                  ",
                           "008":"       US NWS: NWSTG                 ",
                           "009":"       US NWS: Other                 ",
                           "051":"       Miami (RSMC)                  ",
                           "052":"       Miami (RSMC) NHC              ",
                           "053":"       MSC Monitoring                ",
                           "054":"       Montreal (RSMC)               ",
                           "055":"       San Francisco                 ",
                           "056":"       ARINC Center                  ",
                           "057":"       USAF: Global Weather Central  ",
                           "058":"       USN: FNMOC                    ",
                           "059":"       NOAA FSL                      ",
                           "060":"       NCAR                          ",
                           "061":"       Service ARGOS- Landover       ",
                           "062":"       USN: NAVO                     ",
                           "063":"       IRI: Climate and Society      ",
                           "xxx":"       Center ID not recognized!     "}


                           


    # =============================================================================
    #         SLIDER CHANGE FUNCTION CALLS
    # =============================================================================
    def changefftwindow(self, value):
        self.settingsdict["fftwindow"] = float(value) / 100
        self.processortabwidgets["fftwindowlabel"].setText(self.label_fftwindow +str(self.settingsdict["fftwindow"]).ljust(4,'0'))
        

    def changefftsiglev(self, value):
        self.settingsdict["minsiglev"] = float(value) / 10
        self.processortabwidgets["fftsiglevlabel"].setText(self.label_minsiglev + str(np.round(self.settingsdict["minsiglev"],2)).ljust(4,'0'))

        
    def changefftratio(self, value):
        self.settingsdict["minfftratio"] = float(value) / 100
        self.processortabwidgets["fftratiolabel"].setText(self.label_minsigrat + str(np.round(self.settingsdict["minfftratio"]*100)).ljust(4,'0'))
        

    def changetriggersiglev(self, value):
        self.settingsdict["triggersiglev"] = float(value) / 10
        self.processortabwidgets["triggersiglevlabel"].setText(self.label_trigsiglev + str(np.round(self.settingsdict["triggersiglev"],2)).ljust(4,'0'))

        
    def changetriggerratio(self, value):
        self.settingsdict["triggerfftratio"] = float(value) / 100
        self.processortabwidgets["triggerratiolabel"].setText(self.label_trigsigrat + str(np.round(self.settingsdict["triggerfftratio"]*100)).ljust(4,'0'))
        

    
        

    # =============================================================================
    #     TAB MANIPULATION OPTIONS, OTHER GENERAL FUNCTIONS
    # =============================================================================
    def whatTab(self):
        currentIndex = self.tabWidget.currentIndex()
        return currentIndex
        

    @staticmethod
    def setnewtabcolor(tab):
        p = QPalette()
        gradient = QLinearGradient(0, 0, 0, 400)
        gradient.setColorAt(0.0, QColor(255, 255, 255))
        gradient.setColorAt(1.0, QColor(248, 248, 255))
        p.setBrush(QPalette.Window, QBrush(gradient))
        tab.setAutoFillBackground(True)
        tab.setPalette(p)
        

    # add warning message on exit
    def closeEvent(self, event):
        event.accept()
        self.signals.closed.emit(True)
        

    @staticmethod
    def posterror(errortext):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText(errortext)
        msg.setWindowTitle("Error")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

        
        

# SIGNAL SETUP HERE
class SettingsSignals(QObject):
    exported = pyqtSignal(dict)
    closed = pyqtSignal(bool)
    updateGPS = pyqtSignal(str,int)
    
    
    
            
            
            