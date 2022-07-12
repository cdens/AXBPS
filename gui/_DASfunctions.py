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

from os import path
from traceback import print_exc as trace_error

from PyQt5.QtWidgets import (QLineEdit, QLabel, QSpinBox, QPushButton, QWidget, QFileDialog, QComboBox, QGridLayout, QDoubleSpinBox, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QApplication, QMessageBox, QVBoxLayout)
from PyQt5.QtCore import QObjectCleanupHandler, Qt, pyqtSlot, pyqtSignal, QObject
from PyQt5.QtGui import QColor

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

import time as timemodule
import datetime as dt
import numpy as np
import wave

from gsw import SP_from_C #conductivity-to-salinity conversion

import lib.DAS.DAS_AXBT as das_axbt 
import lib.DAS.DAS_AXCTD as das_axctd
from lib.DAS.common_DAS_functions import channelandfrequencylookup, list_receivers
import lib.GPS_COM_interaction as gps

from ._globalfunctions import (addnewtab, whatTab, renametab, setnewtabcolor, closecurrenttab, savedataincurtab, postwarning, posterror, postwarning_option, closeEvent, parsestringinputs)
from ._PEfunctions import continuetoqc

            
# =============================================================================
#     DATA ACQUISITION SYSTEM TAB AND INPUTS HERE
# =============================================================================
def makenewprocessortab(self):     
    try:
        
        opentab,tabID = self.addnewtab()

        #also creates proffig and locfig so they will both be ready to go when the tab transitions from signal processor to profile editor
        self.alltabdata[opentab] = {"tab":QWidget(), "tablayout":QGridLayout(), "ProcessorFig":plt.figure(), "profileSaved":True, "tabtype":"DAS_u", "isprocessing":False, "datasource":"INIT", "sourcetype":"NONE", "probetype":'unknown', "date_plot_updated":dt.datetime.utcnow()}

        self.setnewtabcolor(self.alltabdata[opentab]["tab"])
        
        #initializing raw data storage
        self.alltabdata[opentab]["rawdata"] = {"temperature":np.array([]), "depth":np.array([]), "conductivity":np.array([]), "salinity":np.array([]), "frequency":np.array([]), "time":np.array([]), "frame":[], "starttime":0, "istriggered":False, "firstpointtime":0, "firstpulsetime":0}
        
        self.alltabdata[opentab]["tablayout"].setSpacing(10)

        #creating new tab, assigning basic info
        self.tabWidget.addTab(self.alltabdata[opentab]["tab"],'New Tab') 
        self.tabWidget.setCurrentIndex(opentab)
        self.tabWidget.setTabText(opentab, "New Drop #" + str(self.totaltabs)) 
        self.alltabdata[opentab]["tabnum"] = tabID #assigning unique, unchanging number to current tab
        self.alltabdata[opentab]["tablayout"].setSpacing(10)
        
        #ADDING FIGURE TO GRID LAYOUT
        self.alltabdata[opentab]["ProcessorCanvas"] = FigureCanvas(self.alltabdata[opentab]["ProcessorFig"]) 
        self.alltabdata[opentab]["tablayout"].addWidget(self.alltabdata[opentab]["ProcessorCanvas"],0,0,11,1)
        self.alltabdata[opentab]["ProcessorCanvas"].setStyleSheet("background-color:transparent;")
        self.alltabdata[opentab]["ProcessorFig"].patch.set_facecolor('None')

        #making profile processing result plots
        self.alltabdata[opentab]["ProcAxes"] = [plt.axes()]
        self.alltabdata[opentab]["ProcAxes"].append(self.alltabdata[opentab]["ProcAxes"][0].twiny())
        
        #and add new buttons and other widgets
        self.alltabdata[opentab]["tabwidgets"] = {}
                
        #making widgets
        self.alltabdata[opentab]["tabwidgets"]["datasourcetitle"] = QLabel('Data Source:') #1
        self.alltabdata[opentab]["tabwidgets"]["refreshdataoptions"] = QPushButton('Refresh')  # 2
        self.alltabdata[opentab]["tabwidgets"]["refreshdataoptions"].clicked.connect(self.datasourcerefresh)
        self.alltabdata[opentab]["tabwidgets"]["datasource"] = QComboBox() #3
        
        #updating datasource dropbox
        self.datasourcerefresh()
        
        #connect datasource dropdown to changer function, pull current datasource
        self.alltabdata[opentab]["tabwidgets"]["datasource"].currentIndexChanged.connect(self.datasourcechange)
        self.alltabdata[opentab]["datasource"] = self.alltabdata[opentab]["tabwidgets"]["datasource"].currentText()
        
        self.alltabdata[opentab]["tabwidgets"]["probetitle"] = QLabel('Probe Type:')
        self.alltabdata[opentab]["tabwidgets"]["probetype"] = QComboBox()
        for p in self.probetypes:
            self.alltabdata[opentab]["tabwidgets"]["probetype"].addItem(p)
        self.alltabdata[opentab]["tabwidgets"]["probetype"].setCurrentIndex(self.probetypes.index(self.defaultprobe)) #set option to default probe
        self.alltabdata[opentab]["probetype"] = self.alltabdata[opentab]["tabwidgets"]["probetype"].currentText()
        self.alltabdata[opentab]["tabwidgets"]["probetype"].currentIndexChanged.connect(self.probetypechange)
        
        self.alltabdata[opentab]["tabwidgets"]["channeltitle"] = QLabel('Channel:') #4
        self.alltabdata[opentab]["tabwidgets"]["freqtitle"] = QLabel('Frequency (MHz):') #5
        
        self.alltabdata[opentab]["tabwidgets"]["vhfchannel"] = QSpinBox() #6
        self.alltabdata[opentab]["tabwidgets"]["vhfchannel"].setRange(1,99)
        self.alltabdata[opentab]["tabwidgets"]["vhfchannel"].setSingleStep(1)
        self.alltabdata[opentab]["tabwidgets"]["vhfchannel"].setValue(12)
        self.alltabdata[opentab]["tabwidgets"]["vhfchannel"].valueChanged.connect(self.changefrequencytomatchchannel)
        
        self.alltabdata[opentab]["tabwidgets"]["vhffreq"] = QDoubleSpinBox() #7
        self.alltabdata[opentab]["tabwidgets"]["vhffreq"].setRange(136, 173.5)
        self.alltabdata[opentab]["tabwidgets"]["vhffreq"].setSingleStep(0.375)
        self.alltabdata[opentab]["tabwidgets"]["vhffreq"].setDecimals(3)
        self.alltabdata[opentab]["tabwidgets"]["vhffreq"].setValue(170.5)
        self.alltabdata[opentab]["tabwidgets"]["vhffreq"].valueChanged.connect(self.changechanneltomatchfrequency)
        
        self.alltabdata[opentab]["tabwidgets"]["startprocessing"] = QPushButton('Start') #8
        self.alltabdata[opentab]["tabwidgets"]["startprocessing"].clicked.connect(self.startprocessor)
        self.alltabdata[opentab]["tabwidgets"]["stopprocessing"] = QPushButton('Stop') #9
        self.alltabdata[opentab]["tabwidgets"]["stopprocessing"].clicked.connect(self.stopprocessor)
        self.alltabdata[opentab]["tabwidgets"]["processprofile"] = QPushButton('Process Profile') #10
        self.alltabdata[opentab]["tabwidgets"]["processprofile"].clicked.connect(self.processprofile)
        self.alltabdata[opentab]["tabwidgets"]["saveprofile"] = QPushButton('Save Profile') #21
        self.alltabdata[opentab]["tabwidgets"]["saveprofile"].clicked.connect(self.savedataincurtab)
        
        self.alltabdata[opentab]["tabwidgets"]["datetitle"] = QLabel('Date: ') #11
        self.alltabdata[opentab]["tabwidgets"]["dateedit"] = QLineEdit('YYYYMMDD') #12
        self.alltabdata[opentab]["tabwidgets"]["timetitle"] = QLabel('Time (UTC): ') #13
        self.alltabdata[opentab]["tabwidgets"]["timeedit"] = QLineEdit('HHMM') #14
        self.alltabdata[opentab]["tabwidgets"]["lattitle"] = QLabel('Latitude (N>0): ') #15
        self.alltabdata[opentab]["tabwidgets"]["latedit"] = QLineEdit('XX.XXX') #16
        self.alltabdata[opentab]["tabwidgets"]["lontitle"] = QLabel('Longitude (E>0): ') #17
        self.alltabdata[opentab]["tabwidgets"]["lonedit"] = QLineEdit('XX.XXX') #18
        self.alltabdata[opentab]["tabwidgets"]["idtitle"] = QLabel('Platform ID/Tail#: ') #19
        self.alltabdata[opentab]["tabwidgets"]["idedit"] = QLineEdit(self.settingsdict["platformid"]) #20
        
        #formatting widgets
        self.alltabdata[opentab]["tabwidgets"]["channeltitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["freqtitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["lattitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["lontitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["datetitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["timetitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["idtitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        #should be 19 entries 
        widgetorder = ["datasourcetitle", "refreshdataoptions", "datasource", "probetitle", "probetype", "channeltitle", "freqtitle", "vhfchannel", "vhffreq", "startprocessing", "stopprocessing", "processprofile", "saveprofile", "datetitle", "dateedit", "timetitle", "timeedit", "lattitle", "latedit", "lontitle", "lonedit", "idtitle", "idedit"]
        wrows     = [1,1,2,3,3,4,5,4,5,6,6,7,6,1,1,2,2,3,3,4,4,5,5]
        wcols     = [3,4,3,3,4,3,3,4,4,3,4,6,6,6,7,6,7,6,7,6,7,6,7]
        wrext     = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
        wcolext   = [1,1,2,1,1,1,1,1,1,1,1,2,2,1,1,1,1,1,1,1,1,1,1]
        

        #adding widgets to assigned positions
        for i,r,c,re,ce in zip(widgetorder,wrows,wcols,wrext,wcolext):
            self.alltabdata[opentab]["tabwidgets"][i].setFont(self.labelfont)
            self.alltabdata[opentab]["tablayout"].addWidget(self.alltabdata[opentab]["tabwidgets"][i],r,c,re,ce)
        
        #adding table widget after all other buttons populated
        self.alltabdata[opentab]["tabwidgets"]["table"] = QTableWidget() #19
        self.alltabdata[opentab]["tablayout"].addWidget(self.alltabdata[opentab]["tabwidgets"]["table"],9,2,2,7)
        self.alltabdata[opentab]["tabwidgets"]["tableheader"] = self.alltabdata[opentab]["tabwidgets"]["table"].horizontalHeader() 
        self.alltabdata[opentab]["tabwidgets"]["tableheader"].setFont(self.labelfont)
    
        #calling function to format graph and table based on probe type #TODO
        self.prep_graph_and_table(self.alltabdata[opentab]["probetype"], opentab)

        #adjusting stretch factors for all rows/columns
        colstretch = [8,0,1,1,1,1,1,1,1]
        for col,cstr in enumerate(colstretch):
            self.alltabdata[opentab]["tablayout"].setColumnStretch(col,cstr)
        rowstretch = [1,1,1,1,1,1,1,1,1,10]
        for row,rstr in enumerate(rowstretch):
            self.alltabdata[opentab]["tablayout"].setRowStretch(row,rstr)

        #making the current layout for the tab
        self.alltabdata[opentab]["tab"].setLayout(self.alltabdata[opentab]["tablayout"])

    except Exception: #if something breaks
        trace_error()
        self.posterror("Failed to build new processor tab")
    
    
#switching the probe type in the dropdown also adjusts the graph and table contents
def probetypechange(self):
    opentab = self.whatTab()
    probetype = self.alltabdata[opentab]["tabwidgets"]["probetype"].currentText()
    self.alltabdata[opentab]["probetype"] = probetype
    self.prep_graph_and_table(probetype, opentab)
        
    
#configure graph and table based on current probe type
def prep_graph_and_table(self, probetype, plottabnum):
    
    #prep window to plot data
    self.alltabdata[plottabnum]["ProcAxes"][0].set_xlabel('Temperature ($^\circ$C)', fontsize=12)
    self.alltabdata[plottabnum]["ProcAxes"][0].set_ylabel('Depth (m)', fontsize=12)
    self.alltabdata[plottabnum]["ProcAxes"][0].set_title('Data Received',fontweight="bold", fontsize=14)
    
    if probetype == "AXCTD": #AXCTD temperature and salinity plots
        self.alltabdata[plottabnum]["ProcAxes"][1].set_xlabel('Salinity (PSU)', fontsize=12)
        self.alltabdata[plottabnum]["ProcAxes"][1].set_visible(True)
        self.alltabdata[plottabnum]["ProcAxes"][0].xaxis.label.set_color("red") #temperature axis red
        self.alltabdata[plottabnum]["ProcAxes"][0].tick_params(axis='x', colors='red')
        self.alltabdata[plottabnum]["ProcAxes"][1].xaxis.label.set_color("blue") #conductivity axis blue
        self.alltabdata[plottabnum]["ProcAxes"][1].tick_params(axis='x', colors='blue')
        
    else: #AXBT temperature plot only
        self.alltabdata[plottabnum]["ProcAxes"][0].xaxis.label.set_color("black") #temperature axis black
        self.alltabdata[plottabnum]["ProcAxes"][0].tick_params(axis='x', colors='black')
        self.alltabdata[plottabnum]["ProcAxes"][1].set_visible(False)
        
    self.config_graph_ticks_lims(plottabnum, probetype)
    self.alltabdata[plottabnum]["ProcessorFig"].set_tight_layout(True)
    self.alltabdata[plottabnum]["ProcessorCanvas"].draw() #refresh plots on window
        
    
    self.alltabdata[plottabnum]["tabwidgets"]["table"].setColumnCount(6)
    self.alltabdata[plottabnum]["tabwidgets"]["table"].setRowCount(0) 
    self.alltabdata[plottabnum]["tabwidgets"]["table"].setFont(self.labelfont)
    self.alltabdata[plottabnum]["tabwidgets"]["table"].verticalHeader().setVisible(False)
    self.alltabdata[plottabnum]["tabwidgets"]["table"].setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) #removes scroll bars
    
    #table columns
    if probetype == "AXBT":
        self.alltabdata[plottabnum]["tabwidgets"]["table"].setHorizontalHeaderLabels(('Time (s)', 'Fp (Hz)', 'Sp (dB)', 'Rp (%)' ,'Depth (m)','Temp (C)'))
    elif probetype == "AXCTD":
        self.alltabdata[plottabnum]["tabwidgets"]["table"].setHorizontalHeaderLabels(('Time (s)', 'R-400 Hz', 'R-7500 Hz', 'Depth (m)','Temp. (C)', 'Sal. (PSU)'))
        
    
    for ii in range(0,6): #building table
        self.alltabdata[plottabnum]["tabwidgets"]["tableheader"].setSectionResizeMode(ii, QHeaderView.Stretch)  
        self.alltabdata[plottabnum]["tabwidgets"]["table"].setEditTriggers(QTableWidget.NoEditTriggers)
        
        
        
#determining ideal axis limits and configuring limits/grids for data
def config_graph_ticks_lims(self, plottabnum, probetype):
    
    #hard-coded graph settings
    depthlims = [-5,1000] #axis default limits
    templims = [-2,32]
    psallims = [25,40]
    depthint = 50 #intervals at which to extend axis limits
    tsint = 2
        
    cdepths = np.array([0])
    ctemps = np.array([26])
    cpsal = np.array([27])
    if len(self.alltabdata[plottabnum]["rawdata"]["depth"]) > 0:
        cdepths = self.alltabdata[plottabnum]["rawdata"]["depth"]
        ctemps = self.alltabdata[plottabnum]["rawdata"]["temperature"]
        if probetype == "AXCTD":
            cpsal = self.alltabdata[plottabnum]["rawdata"]["salinity"]
    
    #determining best axis limits and applying them
    if np.max(cdepths) > depthlims[1]:
        depthlims[1] = np.ceil(np.max(cdepths)/depthint)*depthint
    if np.min(ctemps) < templims[0]:
        templims[0] = np.floor(np.min(ctemps)/tsint)*tsint
    if np.max(ctemps) > templims[1]:
        templims[1] = np.ceil(np.max(ctemps)/tsint)*tsint
    
    #setting axis limits for temperature, depth
    self.alltabdata[plottabnum]["ProcAxes"][0].set_xlim(templims)
    self.alltabdata[plottabnum]["ProcAxes"][0].set_ylim(depthlims)
    self.alltabdata[plottabnum]["ProcAxes"][0].grid(visible=True, which='major', axis='both')
    self.alltabdata[plottabnum]["ProcAxes"][0].invert_yaxis() 
    
    if probetype == "AXCTD": #determining/setting axis limits for salinity as well for AXCTDs only
        if np.min(cpsal) < psallims[0]:
            psallims[0] = np.floor(np.min(cpsal)/tsint)*tsint
        if np.max(cpsal) > psallims[1]:
            psallims[1] = np.ceil(np.max(cpsal)/tsint)*tsint
                        
        self.alltabdata[plottabnum]["ProcAxes"][1].set_xlim(psallims)
        self.alltabdata[plottabnum]["ProcAxes"][1].set_ylim(depthlims)
        self.alltabdata[plottabnum]["ProcAxes"][1].invert_yaxis() 
        self.alltabdata[plottabnum]["ProcAxes"][1].grid(visible=False, which='major', axis='both')
        self.alltabdata[plottabnum]["ProcAxes"][0].grid(visible=True, which='major', axis='both')
        
    
    
    
    
# =============================================================================
#         BUTTONS FOR PROCESSOR TAB
# =============================================================================

#refresh list of available receivers
def datasourcerefresh(self): 
    try:
        opentab = self.whatTab()
        # only lets you change the WINRADIO if the current tab isn't already processing
        if not self.alltabdata[opentab]["isprocessing"]:
            self.alltabdata[opentab]["tabwidgets"]["datasource"].clear()
            
            # Getting necessary data
            if self.dll != 0:
                receiver_options, rtypes = list_receivers(self.dll)
            else:
                receiver_options = rtypes = []
            
            self.alltabdata[opentab]["datasource_options"] = ['Test','Audio']
            self.alltabdata[opentab]["sourcetypes"] = ['TT','AA']
            for op,rtype in zip(receiver_options,rtypes):
                self.alltabdata[opentab]["datasource_options"].append(op)
                self.alltabdata[opentab]["sourcetypes"].append(rtype)
            
            for op in self.alltabdata[opentab]["datasource_options"]: #add all options (test, audio, receivers)
                self.alltabdata[opentab]["tabwidgets"]["datasource"].addItem(op) 
                
            
            #default receiver selection if 1+ receivers are connected and not actively processing
            if len(receiver_options) > 0:
                isnotbusy = [True]*len(receiver_options)
                for iii,serialnum in enumerate(receiver_options):
                    for ctab,_ in enumerate(self.alltabdata):
                        if ctab != opentab and  self.alltabdata[ctab]["isprocessing"] and self.alltabdata[ctab]["datasource"] == serialnum:
                            isnotbusy[iii] = False
                if sum(isnotbusy) > 0:
                    self.alltabdata[opentab]["tabwidgets"]["datasource"].setCurrentIndex(np.where(isnotbusy)[0][0]+2)
                    
                    
            self.alltabdata[opentab]["datasource"] = self.alltabdata[opentab]["tabwidgets"]["datasource"].currentText()
            
        else:
            self.postwarning("You cannot refresh input devices while processing. Please click STOP to discontinue processing before refreshing device list")
    except Exception:
        trace_error()
        self.posterror("Failed to refresh available receivers")
        
        
        
        
        
        
        
#triggered whenever user selects a new datasource (verifies if it is a receiver it isn't actively processing data)
def datasourcechange(self):
    try:
        #only lets you change the data source if it isn't currently processing
        opentab = self.whatTab()
        index = self.alltabdata[opentab]["tabwidgets"]["datasource"].findText(self.alltabdata[opentab]["datasource"], Qt.MatchFixedString)
        
        isbusy = False

        #checks to see if selection is busy
        woption = self.alltabdata[opentab]["tabwidgets"]["datasource"].currentText()
        if woption != "Audio" and woption != "Test":
            for ctab,_ in enumerate(self.alltabdata):
                if ctab != opentab and  self.alltabdata[ctab]["isprocessing"] and self.alltabdata[ctab]["datasource"] == woption:
                    isbusy = True

        if isbusy:
            self.posterror("This WINRADIO appears to currently be in use! Please stop any other active tabs using this device before proceeding.")
            if index >= 0:
                self.alltabdata[opentab]["tabwidgets"]["datasource"].setCurrentIndex(index)
            return
 
        #only lets you change the WINRADIO if the current tab isn't already processing
        if not self.alltabdata[opentab]["isprocessing"]:
            self.alltabdata[opentab]["datasource"] = woption
        elif self.alltabdata[opentab]["datasource"] != woption:
            if index >= 0:
                 self.alltabdata[opentab]["tabwidgets"]["datasource"].setCurrentIndex(index)
            self.postwarning("You cannot change input devices while processing. Please click STOP to discontinue processing before switching devices")
    except Exception:
        trace_error()
        self.posterror("Failed to change selected WiNRADIO receiver for current tab.")
        
        
        
#called when user changes channel and the frequency needs to be updated   
#these options use a lookup table for VHF channel vs frequency
def changefrequencytomatchchannel(self,newchannel):
    try:
        if self.changechannelunlocked: #to prevent recursion
            self.changechannelunlocked = False 
            
            opentab = self.whatTab()
            newfrequency,newchannel = channelandfrequencylookup(newchannel,'findfrequency')
            self.changechannelandfrequency(newchannel,newfrequency,opentab)
            self.changechannelunlocked = True 
        
    except Exception:
        trace_error()
        self.posterror("Frequency/channel mismatch (changing frequency to match channel)!")
        
        
#called when the user changes the VHF frequency and the channel needs to be updated
#these options use a lookup table for VHF channel vs frequency
def changechanneltomatchfrequency(self,newfrequency):
    try:
        if self.changechannelunlocked: #to prevent recursion
            self.changechannelunlocked = False 
            
            opentab = self.whatTab()
            #special step to skip invalid frequencies!
            if newfrequency == 161.5 or newfrequency == 161.875:
                oldchannel = self.alltabdata[opentab]["tabwidgets"]["vhfchannel"].value()
                oldfrequency,_ = channelandfrequencylookup(oldchannel,'findfrequency')
                if oldfrequency >= 161.6:
                    newfrequency = 161.125
                else:
                    newfrequency = 162.25
                    
            newchannel,newfrequency = channelandfrequencylookup(newfrequency,'findchannel')
            self.changechannelandfrequency(newchannel,newfrequency,opentab)
            self.changechannelunlocked = True 
        
    except Exception:
        trace_error()
        self.posterror("Frequency/channel mismatch (changing channel to match frequency)!")
        
        
#called regardless of channel or frequency being called, makes sure both values are correct
#sends command to update radio receiver frequency if it's actively processing data
def changechannelandfrequency(self,newchannel,newfrequency,opentab):
    try:

        curdatasource = self.alltabdata[opentab]["datasource"]
        
        # sets all tabs with the current receiver to the same channel/freq
        for ctab,_ in enumerate(self.alltabdata):
            #changes channel+frequency values for all tabs set to current data source
            if self.alltabdata[ctab]["datasource"] == curdatasource:
                self.alltabdata[ctab]["tabwidgets"]["vhfchannel"].setValue(int(newchannel))
                self.alltabdata[ctab]["tabwidgets"]["vhffreq"].setValue(newfrequency)
                
                #sends signal to processor thread to change demodulation VHF frequency for any actively processing non-test/non-audio tabs
                if self.alltabdata[ctab]["isprocessing"] and curdatasource != 'Audio' and curdatasource != 'Test':
                    self.alltabdata[opentab]["processor"].changecurrentfrequency(newfrequency)
            
    except Exception:
        trace_error()
        self.posterror("Frequency/channel update error!")
        
        

#update DAS settings for actively processing profile threads
def updateDASsettings(self):
    try:
        
        #pulling settings from settingsdict into specialized dicts to be passed to DAS threads
        newaxbtsettings = {}
        axbtsettingstopull = ["fftwindow", "minfftratio", "minsiglev", "triggerfftratio", "triggersiglev", "tcoeff_axbt", "zcoeff_axbt", "flims_axbt"]
        newaxctdsettings = {}
        axctdsettingstopull = ["minr400", "mindr7500", "deadfreq", "refreshrate", "mark_space_freqs", "usebandpass", "zcoeff_axctd", "tcoeff_axctd", "ccoeff_axctd", "tlims_axctd", "slims_axctd"]
        
        for csetting in axbtsettingstopull:
            newaxbtsettings[csetting] = self.settingsdict[csetting]
        for csetting in axctdsettingstopull:
            newaxctdsettings[csetting] = self.settingsdict[csetting]
            
        
        #updates DAS settings for any active tabs
        for ctab in range(len(self.alltabdata)): #dont want to iterate over tabs, need to edit alltabdata list
            if self.alltabdata[ctab]["isprocessing"]: 
                if self.alltabdata[ctab]['probetype'] == 'AXBT':
                    self.alltabdata[ctab]["processor"].changethresholds(newaxbtsettings)
                elif self.alltabdata[ctab]['probetype'] == 'AXCTD':
                    self.alltabdata[ctab]["processor"].changethresholds(newaxctdsettings)
                    
                
    except Exception:
        trace_error()
        self.posterror("Error updating DAS settings!")
        
        
        
#starting a DAS thread (triggered when user selects the start button)
def startprocessor(self):
    try:
        opentab = self.whatTab()
        if not self.alltabdata[opentab]["isprocessing"]: #button wont do anything if the tab is already processing data
            
            #get the datasource, and call runprocessor to initialize the thread if the datasource is good
            status, datasource, newsource = self.prepprocessor(opentab) 
            
            if status: #initialize/run the probe processor thread
                self.runprocessor(opentab, datasource, newsource)
                self.alltabdata[opentab]["profileSaved"] = False
                self.add_asterisk(opentab)
                
    except Exception:
        trace_error()
        self.posterror("Failed to start processor!")
        
        
        
#prepprocessor gets the datasource to be used for processing. If the datasource is test or a receiver, it returns status=True and the program proceeds directly to initializing the processing thread. If it is an audio file, the function prompts the user to select the file and identifies the number of audio channels. If it is a single channel- status=True and runprocessor is called immediately. If there are multiple channels, status=False, runprocessor is not called, and a window is opened with a spinbox for the user to select which channel to process. Once the user has selected the channel and okay, that process will call the runprocessor function and initialize the DAS processing thread    
def prepprocessor(self, opentab):
    datasource = self.alltabdata[opentab]["datasource"]
    #running processor here
    
    #if too many signal processor threads are already running
    if self.threadpool.activeThreadCount() + 1 > self.threadpool.maxThreadCount():
        self.postwarning("The maximum number of simultaneous processing threads has been exceeded. This processor will automatically begin collecting data when STOP is selected on another tab.")
        return False,"No","No"
        
    #source type to be passed to processor thread (audio vs. test vs. receiver type)
    sourceind = self.alltabdata[opentab]["tabwidgets"]["datasource"].currentIndex()
    sourcetype = self.alltabdata[opentab]["sourcetypes"][sourceind]
    
    
    if sourcetype == 'AA': #gets audio file to process
        try:
            # getting filename
            fname, ok = QFileDialog.getOpenFileName(self, 'Open file',self.defaultfilereaddir,"Source Data Files (*.WAV *.Wav *.wav *PCM *Pcm *pcm *MP3 *Mp3 *mp3)","",self.fileoptions)
            if not ok or fname == "":
                self.alltabdata[opentab]["isprocessing"] = False
                return False,"No","No"
            else:
                splitpath = path.split(fname)
                self.defaultfilereaddir = splitpath[0]
                
            #determining which channel to use
            #selec-2=no box opened, -1 = box opened, 0 = box closed w/t selection, > 0 = selected channel
            try:
                file_info = wave.open(fname)
            except:
                self.postwarning("Unable to read audio file")
                return False,"No","No"
                
            nchannels = file_info.getnchannels()
            if nchannels == 1:
                datasource = f"AA-0001{fname}" #only one channel, don't need to prompt user for channel number
            else:
                if self.selectedChannel >= -1: #active tab already opened, warn user and terminate function
                    self.postwarning("An audio channel selector dialog box has already been opened in another tab. Please close that box before processing an audio file with multiple channels in this tab.")
                    return False,"No","No"
                    
                else: #create a dialog box for the user to select the channel to process
                    self.audioChannelSelector = AudioWindow(nchannels, opentab, fname) #creating and connecting window
                    self.audioChannelSelector.signals.closed.connect(self.audioWindowClosed)
                    self.audioChannelSelector.show() #bring window to front
                    self.audioChannelSelector.raise_()
                    self.audioChannelSelector.activateWindow()
                    
                    return False,"No","No"
            
        except Exception:
            self.posterror("Failed to execute audio processor!")
            trace_error()

    elif sourcetype != "TT": #radio receiver selected as datasource
        
        #checks to make sure current receiver isn't busy
        for ctab,_ in enumerate(self.alltabdata):
            if ctab != opentab and self.alltabdata[ctab]["isprocessing"] and self.alltabdata[ctab]["datasource"] == datasource:
                self.posterror("This WINRADIO appears to currently be in use! Please stop any other active tabs using this device before proceeding.")
                return False,"No","No"
    
    #success            
    return True, datasource, sourcetype
    
    
    
#initialize DAS processor thread depending on selected probetype, start processor
def runprocessor(self, opentab, datasource, sourcetype):
                
    #gets current tab number
    tabID = self.alltabdata[opentab]["tabnum"]
    
    #getting probe type
    probetype = self.alltabdata[opentab]["tabwidgets"]["probetype"].currentText()
    self.defaultprobe = probetype #default probe to display for DAS and PE tabs
    self.alltabdata[opentab]["probetype"] = probetype
    
    #disabling datasource and probetype dropdown boxes (once you start processing data you can't change these)
    self.alltabdata[opentab]["tabwidgets"]["datasource"].setEnabled(False)
    self.alltabdata[opentab]["tabwidgets"]["probetype"].setEnabled(False)
    
    #gets rid of scroll bar on table
    self.alltabdata[opentab]["tabwidgets"]["table"].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    
    autopopulate = False #tracking whether to autopopulate fields (waits until after thread has been started to prevent from hanging on GPS stream)

    #saving start time for current drop
    if self.alltabdata[opentab]["rawdata"]["starttime"] == 0:
        starttime = dt.datetime.utcnow()
        self.alltabdata[opentab]["rawdata"]["starttime"] = starttime
        
        #autopopulating selected fields
        if sourcetype != 'AA': #but not if reprocessing from audio file
            autopopulate = True
    
    else: #start time already exists- the processor has been previously started and stopped. Recover old start time
        starttime = self.alltabdata[opentab]["rawdata"]["starttime"]
        
            
    #add gps coordinates if a good gps fix is available
    if self.goodPosition == True:
        self.alltabdata[opentab]['tabwidgets']['latedit'].setText(str(round(self.lat, 3)))
        self.alltabdata[opentab]['tabwidgets']['lonedit'].setText(str(round(self.lon, 3)))
                
        
        
    #this should never happen (if there is no DLL loaded there shouldn't be any receivers detected), but just in case
    if self.dll == 0 and sourcetype not in ['AA','TT']:
        self.postwarning("No receiver drivers were successfully loaded! Please restart the program in order to initiate a processing tab with a connected receiver")
        return
    elif sourcetype == 'AA': #build audio progress bar
        self.alltabdata[opentab]["tabwidgets"]["audioprogressbar"] = QProgressBar()
        self.alltabdata[opentab]["tablayout"].addWidget(
            self.alltabdata[opentab]["tabwidgets"]["audioprogressbar"], 8, 2, 1, 7)
        self.alltabdata[opentab]["tabwidgets"]["audioprogressbar"].setValue(0)
        QApplication.processEvents()
        
        #disable start button (once you stop reprocessing from audio file you can't restart)
        self.alltabdata[opentab]["tabwidgets"]["startprocessing"].setEnabled(False)
        
        
    #initializing thread, connecting signals/slots
    self.alltabdata[opentab]["sourcetype"] = sourcetype #assign current source as processor if previously unassigned (no restarting in this tab beyond this point)
    vhffreq = self.alltabdata[opentab]["tabwidgets"]["vhffreq"].value()
    
    #adjusting name of datasource to send to thread:
    #'AAxxxxxfull/path/to/file' for audio, where xxxxx is the channel number and the full path to the audio file is given (this is set by the AudioWindow class)
    #'TT' for test
    #'WRNNNNNN' for radio receiver, where NNNNNN is the serial/ID for the reciever, and the first two characters are the receiver type (WR = WiNRADIO G39WSB sonobuoy receiver)
    if sourcetype == 'TT':
        datasource_toThread = 'TT'
    elif sourcetype == 'AA':
        datasource_toThread = datasource #set by the AudioWindow
    else:
        datasource_toThread = sourcetype + datasource #append receiver ID (2 characters) and serial number
    
    
    settings = {} #pulling settings required for processor thread, dependent on probe type
    if probetype == 'AXBT':
        settingstopull = ["fftwindow", "minfftratio", "minsiglev", "triggerfftratio", "triggersiglev", "tcoeff_axbt", "zcoeff_axbt", "flims_axbt"]
    elif probetype == 'AXCTD':
        settingstopull = ["minr400", "mindr7500", "deadfreq", "refreshrate", "mark_space_freqs", "usebandpass", "zcoeff_axctd", "tcoeff_axctd", "ccoeff_axctd", "tlims_axctd", "slims_axctd"]
        
    for csetting in settingstopull:
        settings[csetting] = self.settingsdict[csetting]
    
    #initializing processor, connecting signals/slots to GUI thread
    if probetype == "AXBT":
        self.alltabdata[opentab]["processor"] = das_axbt.AXBTProcessor(self.dll, datasource_toThread, vhffreq, tabID,  starttime, self.alltabdata[opentab]["rawdata"]["istriggered"], self.alltabdata[opentab]["rawdata"]["firstpointtime"], settings, self.slash, self.tempdir)
    elif probetype == "AXCTD":
        self.alltabdata[opentab]["processor"] = das_axctd.AXCTDProcessor(self.dll, datasource_toThread, vhffreq, tabID,  starttime, self.alltabdata[opentab]["rawdata"]["istriggered"], self.alltabdata[opentab]["rawdata"]["firstpointtime"], self.alltabdata[opentab]["rawdata"]["firstpulsetime"], settings, self.slash, self.tempdir)
        
    
        #connecting signals to GUI functions (e.g. updating the graph and table with new data)
    self.alltabdata[opentab]["processor"].signals.failed.connect(self.failedWRmessage) #this signal only for actual processing tabs (not example tabs)
    self.alltabdata[opentab]["processor"].signals.iterated.connect(self.updateUIinfo)
    self.alltabdata[opentab]["processor"].signals.triggered.connect(self.triggerUI)
    self.alltabdata[opentab]["processor"].signals.terminated.connect(self.updateUIfinal)

    #connecting audio file-specific signal (to update progress bar on GUI)
    if sourcetype == 'AA':
        self.alltabdata[opentab]["processor"].signals.updateprogress.connect(self.updateaudioprogressbar)
    
    #starting the current thread and noting that the current tab is processing data
    self.threadpool.start(self.alltabdata[opentab]["processor"])
    self.alltabdata[opentab]["isprocessing"] = True
    
    #the code is still running but data collection has at least been initialized. This allows self.savecurrenttab() to save raw data files
    self.alltabdata[opentab]["tabtype"] = "DAS_p"
    
    #autopopulating date/time/position/tail number fields if necessary
    if autopopulate:
        if self.settingsdict["autodtg"]:#populates date and time if requested
            curdatestr = str(starttime.year) + str(starttime.month).zfill(2) + str(starttime.day).zfill(2)
            self.alltabdata[opentab]["tabwidgets"]["dateedit"].setText(curdatestr)
            curtimestr = str(starttime.hour).zfill(2) + str(starttime.minute).zfill(2)
            self.alltabdata[opentab]["tabwidgets"]["timeedit"].setText(curtimestr)
        if self.settingsdict["autolocation"] and self.settingsdict["comport"] != 'n':
            if abs((self.datetime - starttime).total_seconds()) <= 30: #GPS ob within 30 seconds
                self.alltabdata[opentab]["tabwidgets"]["latedit"].setText(str(round(self.lat,3)))
                self.alltabdata[opentab]["tabwidgets"]["lonedit"].setText(str(round(self.lon,3)))
            else:
                self.postwarning("Last GPS fix expired (> 30 seconds old) \n No Lat/Lon provided")
        if self.settingsdict["autoid"]:
            self.alltabdata[opentab]["tabwidgets"]["idedit"].setText(self.settingsdict["platformid"])
            
    
        
#aborting processor (triggered when user selects the STOP button)
def stopprocessor(self):
    try:
        opentab = self.whatTab()
        if self.alltabdata[opentab]["isprocessing"]:
            opentab = self.whatTab()
            datasource = self.alltabdata[opentab]["datasource"]
            
            self.alltabdata[opentab]["isprocessing"] = False #processing is done
            self.alltabdata[opentab]["processor"].abort()
            self.alltabdata[opentab]["tabwidgets"]["table"].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
                
    except Exception:
        trace_error()
        self.posterror("Failed to stop processor!")
            



# =============================================================================
#        POPUP WINDOW FOR AUDIO CHANNEL SELECTION
# =============================================================================

class AudioWindow(QWidget):
    
    def __init__(self, nchannels, opentab, fname):
        super(AudioWindow, self).__init__()
        
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        self.selectedChannel = 1
        self.wasClosed = False
        self.nchannels = nchannels
        self.fname = fname
        self.opentab = opentab
        
        self.signals = AudioWindowSignals()
        
        self.title = QLabel("Select channel to read\n(for 2-channel WAV files,\nCh1 = left and Ch2 = right):")
        self.spinbox = QSpinBox()
        self.spinbox.setMinimum(1)
        self.spinbox.setMaximum(self.nchannels)
        self.spinbox.setSingleStep(1)
        self.spinbox.setValue(self.selectedChannel)
        self.finish = QPushButton("Select Channel")
        self.finish.clicked.connect(self.selectChannel)
        
        self.layout.addWidget(self.title)
        self.layout.addWidget(self.spinbox)
        self.layout.addWidget(self.finish)
        
        self.show()
                
        
    def selectChannel(self):
        self.selectedChannel = self.spinbox.value()
        
        #format is Audio<channel#><filename> e.g. AA00002/My/File.WAV
        #allowing for 5-digit channels since WAV file channel is a 16-bit integer, can go to 65,536
        self.datasource = f"AA{self.selectedChannel:05d}{self.fname}" 
        
        #emit signal
        self.signals.closed.emit(True, self.opentab, self.datasource)
        
        #close dialogue box
        self.wasClosed = True
        self.close()
        
        
    # add warning message on exit
    def closeEvent(self, event):
        event.accept()
        if not self.wasClosed:
            self.signals.closed.emit(False, 0, "none")
            self.wasClosed = True
            
#initializing signals for data to be passed back to main loop
class AudioWindowSignals(QObject): 
    closed = pyqtSignal(int, int, str)


#slot in main program to close window (only one channel selector window can be open at a time)
@pyqtSlot(int, int, str)
def audioWindowClosed(self, wasGood, opentab, datasource):
    if wasGood:
        self.runprocessor(opentab, datasource, "AA")
    
    



    
# =============================================================================
#        SIGNAL PROCESSOR SLOTS AND OTHER CODE
# =============================================================================
#getting tab string (self.alltabdata key for specified tab) from tab number
def gettabnumfromID(self,tabID):
    return self.tabIDs.index(tabID)

            
            
#slot to notify main GUI that the thread has been triggered with AXBT data
#event is only used for probes where there are multiple triggers (e.g. AXCTDs with 400 Hz pulses, 7.5 kHz pulse)
@pyqtSlot(int,int,float)
def triggerUI(self,tabID,event,eventtime):
    try:
        plottabnum = self.gettabnumfromID(tabID)
        probetype = self.alltabdata[plottabnum]["probetype"]
        
        if probetype == "AXBT":
            self.alltabdata[plottabnum]["rawdata"]["firstpointtime"] = eventtime
            self.alltabdata[plottabnum]["rawdata"]["istriggered"] = True
        
        elif probetype == "AXCTD":
            self.alltabdata[plottabnum]["rawdata"]["istriggered"] = event
            
            if event == 1: #triggerstatus 1: 400 Hz pulse received
                self.alltabdata[plottabnum]["rawdata"]["firstpulsetime"] = eventtime
            else: #profile collection initiated
                self.alltabdata[plottabnum]["rawdata"]["firstpointtime"] = eventtime
            
            
    except Exception:
        self.posterror("Failed to trigger temperature/depth profile in GUI!")
        trace_error()

        
        
#slot to pass AXBT data from thread to main GUI
@pyqtSlot(int,list)
def updateUIinfo(self,tabID,data):
    try:        
        
        plottabnum = self.gettabnumfromID(tabID)
        
        if self.alltabdata[plottabnum]["isprocessing"]:
            
            probetype = self.alltabdata[plottabnum]["probetype"]
            
            #appending data to current tab's list, plotting, generating table entries (probe type dependent)
            if probetype == "AXBT":
                curcolors, table_data = self.update_AXBT_DAS(plottabnum, data, False)
            elif probetype == "AXCTD":
                curcolors, table_data = self.update_AXCTD_DAS(plottabnum, data, False)
                
            #updating table
            table = self.alltabdata[plottabnum]["tabwidgets"]["table"]
            
            for curcolor,current_row_data in zip(curcolors,table_data):
                crow = table.rowCount()
                table.insertRow(crow)
                
                for cind,cdata in enumerate(current_row_data):
                    curtableobject = QTableWidgetItem(str(cdata))
                    curtableobject.setBackground(curcolor)
                    table.setItem(crow, cind, curtableobject)
                    
            table.scrollToBottom()
            #        if crow > 20: #uncomment to remove old rows
            #            table.removeRow(0)
            
    except Exception:
        trace_error()
    
        
        
def update_AXBT_DAS(self, plottabnum, data, interval_override):
    
    #pulling data from list- organized as [temperature, depth, frequency, Sp, Rp, time]
    ctemp = data[0]
    cdepth = data[1]
    cfreq = data[2]
    cact = data[3]
    cratio = data[4]
    ctime = data[5]
    
    #defaults so the last depth will be different unless otherwise explicitly stored (z > 0 here)
    lastdepth = -1
    if len(self.alltabdata[plottabnum]["rawdata"]["depth"]) > 0:
        lastdepth = self.alltabdata[plottabnum]["rawdata"]["depth"][-1]
        
    
    #initialize in case depths match
    curcolor = []
    table_data = []
        
    #only appending a datapoint if depths are different
    if cdepth != lastdepth or interval_override:
        #writing data to tab dictionary
        self.alltabdata[plottabnum]["rawdata"]["time"] = np.append(self.alltabdata[plottabnum]["rawdata"]["time"],ctime)
        self.alltabdata[plottabnum]["rawdata"]["depth"] = np.append(self.alltabdata[plottabnum]["rawdata"]["depth"],cdepth)
        self.alltabdata[plottabnum]["rawdata"]["frequency"] = np.append(self.alltabdata[plottabnum]["rawdata"]["frequency"],cfreq)
        self.alltabdata[plottabnum]["rawdata"]["temperature"] = np.append(self.alltabdata[plottabnum]["rawdata"]["temperature"],ctemp)

        #plot the most recent point
        cdt = dt.datetime.utcnow()
        if self.alltabdata[plottabnum]["rawdata"]["istriggered"] and ((cdt - self.alltabdata[plottabnum]["date_plot_updated"]).total_seconds() >= 5 or interval_override):
            try:
                del self.alltabdata[plottabnum]["ProcAxes"][0].lines[-1]
            except IndexError:
                pass
                
            self.alltabdata[plottabnum]["ProcAxes"][0].plot(self.alltabdata[plottabnum]["rawdata"]["temperature"],self.alltabdata[plottabnum]["rawdata"]["depth"],color='k')
            self.alltabdata[plottabnum]["ProcessorCanvas"].draw()
            self.alltabdata[plottabnum]["date_plot_updated"] = cdt
            
            
        #coloring new cell based on whether or not it has good data
        if np.isnan(cdepth):
            ctemp = cdepth = cfreq = '------'
            curcolor.append(QColor(200, 200, 200)) #light gray
        else:
            curcolor.append(QColor(204, 255, 220)) #light green
            
        table_data.append([ctime,cfreq, cact, cratio, cdepth, ctemp])
        
        
    return curcolor, table_data
    
    
    
    
def update_AXCTD_DAS(self, plottabnum, data, interval_override):
    
    #data organization: [self.triggerstatus, ctimes, r400, r7500, cdepths, ctemps, cconds, cpsals, cframes]
    
    #pulling data from list
    triggerstatus = data[0]
    newtime = data[1]
    newr400 = data[2]
    newr7500 = data[3]
    newdepth = data[4]
    newtemp = data[5]
    newcond = data[6]
    newpsal = data[7] #calculated in AXCTD Processor thread using GSW toolbox TEOS-10 equations
    newframe = data[8]
        
    
    #defaults so the last depth will be different unless otherwise explicitly stored (z > 0 here)
    lastdepth = -1
    if len(self.alltabdata[plottabnum]["rawdata"]["depth"]) > 0:
        lastdepth = self.alltabdata[plottabnum]["rawdata"]["depth"][-1]
        
    
    #only appending a datapoint if depths are different
    if self.alltabdata[plottabnum]["rawdata"]["istriggered"] == 2:
        #writing data to tab dictionary
        self.alltabdata[plottabnum]["rawdata"]["time"] = np.append(self.alltabdata[plottabnum]["rawdata"]["time"], newtime)
        self.alltabdata[plottabnum]["rawdata"]["depth"] = np.append(self.alltabdata[plottabnum]["rawdata"]["depth"], newdepth)
        self.alltabdata[plottabnum]["rawdata"]["temperature"] = np.append(self.alltabdata[plottabnum]["rawdata"]["temperature"], newtemp)
        self.alltabdata[plottabnum]["rawdata"]["conductivity"] = np.append(self.alltabdata[plottabnum]["rawdata"]["conductivity"], newcond)
        self.alltabdata[plottabnum]["rawdata"]["salinity"] = np.append(self.alltabdata[plottabnum]["rawdata"]["salinity"], newpsal)
        self.alltabdata[plottabnum]["rawdata"]["frame"].extend(newframe)
        

        #plot the most recent point
        cdt = dt.datetime.utcnow()
        if (cdt - self.alltabdata[plottabnum]["date_plot_updated"]).total_seconds() >= 5 or interval_override:
            try:
                del self.alltabdata[plottabnum]["ProcAxes"][0].lines[-1]
                del self.alltabdata[plottabnum]["ProcAxes"][1].lines[-1]
            except IndexError: #if nothing has been plotted, trying to delete the lines from the plot raises IndexError
                pass
                
            #plotting and updating
            self.alltabdata[plottabnum]["ProcAxes"][0].plot(self.alltabdata[plottabnum]["rawdata"]["temperature"],self.alltabdata[plottabnum]["rawdata"]["depth"],color='r')
            self.alltabdata[plottabnum]["ProcAxes"][1].plot(self.alltabdata[plottabnum]["rawdata"]["salinity"],self.alltabdata[plottabnum]["rawdata"]["depth"],color='b')
            self.alltabdata[plottabnum]["ProcessorCanvas"].draw()
            self.alltabdata[plottabnum]["date_plot_updated"] = cdt
            

    #coloring new cells based on whether or not it has good data, prepping data to append to table
    curcolor = []
    table_data = []
    for (ctime, cr400, cr7500, cdepth, ctemp, cpsal) in zip(newtime, newr400, newr7500, newdepth, newtemp, newpsal):
        if triggerstatus <= 1 or np.isnan(ctemp*cpsal):
            ctemp = cpsal = cdepth = '------'
            if triggerstatus == 1: #must = 1, therefore in 400 Hz pulse detection phase
                curcolor.append(QColor(204, 220, 255)) #light blue
            else: #nothing detected yet
                curcolor.append(QColor(200, 200, 200)) #light gray (less than 1 or greater than 1 with interference)
        else: #active profile collection
            curcolor.append(QColor(204, 255, 220)) #light green
        
        table_data.append([ctime, cr400, cr7500, cdepth, ctemp, cpsal])
    
    return curcolor, table_data
  
        
        
        
#final update from thread after being aborted- restoring scroll bar, other info
@pyqtSlot(int)
def updateUIfinal(self,tabID):
    try:
        plottabnum = self.gettabnumfromID(tabID)
        self.alltabdata[plottabnum]["isprocessing"] = False
        timemodule.sleep(0.25)
        self.alltabdata[plottabnum]["tabwidgets"]["table"].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        #updating UI with interval_override=True so the plot will be updated to include the full profile
        #blank lists means that no new data will be appended but existing data will be plotted
        probetype = self.alltabdata[plottabnum]["probetype"]
        if probetype == 'AXBT':
            self.update_AXBT_DAS(plottabnum, [[],[],[],[],[],[]], True)
        elif probetype == 'AXCTD':
            self.update_AXCTD_DAS(plottabnum, [[],[],[],[],[],[],[],[],[]], True)
            
        if "audioprogressbar" in self.alltabdata[plottabnum]["tabwidgets"]: #delete the audio progress bar if it exists
            self.alltabdata[plottabnum]["tabwidgets"]["audioprogressbar"].deleteLater()

    except Exception:
        self.posterror("Failed to complete final UI update!")
        trace_error()

        
        
#posts message in main GUI if thread processor fails for some reason
@pyqtSlot(int,int)
def failedWRmessage(self,tabID,messagenum):
    try:
        plottabnum = self.gettabnumfromID(tabID)
        if messagenum == 1:
            self.posterror("Failed to connect to specified radio receiver!")
        elif messagenum == 2:
            self.posterror("Failed to power on specified radio receiver!")
        elif messagenum == 3:
            self.posterror("Failed to initialize demodulator for specified radio receiver!")
        elif messagenum == 4:
            self.posterror("Failed to set VHF frequency for specified radio receiver!")
        elif messagenum == 5:
            self.postwarning("Failed to adjust volume on the specified radio receiver!")
        elif messagenum == 6:
            self.posterror("Error configuring the current radio receiver!")
        elif messagenum == 7:
            self.posterror("Failed to configure the radio receiver audio stream!")
        elif messagenum == 8:
            self.posterror("Contact lost with receiver! Please ensure device is connected and powered on!")
        elif messagenum == 9:
            self.posterror("Selected audio file is too large! Please trim the audio file before processing")
        elif messagenum == 10:
            self.posterror("Unspecified processing error raised during DAS processing")
        elif messagenum == 11:
            self.posterror("Unable to read audio file")
        elif messagenum == 12:
            self.posterror("Failed to initialize the signal processor thread")
        elif messagenum == 13:
            self.postwarning("ARES has stopped audio recording as the WAV file has exceeded maximum allowed length. Please start a new processing tab to continue recording AXBT signal to a WAV file.")
            
        #reset data source if signal processor failed to start
        if messagenum in [1,2,3,4,5,6,7,9,11,12]:
            self.alltabdata[plottabnum]["sourcetype"] = "NONE"
    
    except Exception:
        trace_error()
        self.posterror("Error in signal processor thread triggered secondary error in handling!")

        
        
#updates on screen progress bar if thread is processing audio data
@pyqtSlot(int,int)
def updateaudioprogressbar(self,tabID,newprogress):
    try:
        plottabnum = self.gettabnumfromID(tabID)
        self.alltabdata[plottabnum]["tabwidgets"]["audioprogressbar"].setValue(newprogress)
    except Exception:
        trace_error()


        
# =============================================================================
#         CHECKS/PREPS TAB TO TRANSITION TO PROFILE EDITOR MODE
# =============================================================================
def processprofile(self): 
    try:
        #pulling and checking file input data
        opentab = self.whatTab()
        
        if self.alltabdata[opentab]["isprocessing"]:
            self.postwarning("You cannot proceed to the Profile Editor while the tab is actively processing. Please select 'Stop' before continuing!")
            return
        
        #pulling data from inputs
        probetype = self.alltabdata[opentab]["probetype"]
        latstr = self.alltabdata[opentab]["tabwidgets"]["latedit"].text()
        lonstr = self.alltabdata[opentab]["tabwidgets"]["lonedit"].text()
        identifier = self.alltabdata[opentab]["tabwidgets"]["idedit"].text()
        profdatestr = self.alltabdata[opentab]["tabwidgets"]["dateedit"].text()
        timestr = self.alltabdata[opentab]["tabwidgets"]["timeedit"].text()
            
        #check and correct inputs
        try:
            isgood,lat,lon,dropdatetime,identifier = self.parsestringinputs(latstr, lonstr, profdatestr, timestr, identifier, True, True, True)
        except:
            return
            
        if not isgood:
            return
        
        #saving profile metadata inputs
        self.alltabdata[opentab]["rawdata"]["lat"] = lat
        self.alltabdata[opentab]["rawdata"]["lon"] = lon
        self.alltabdata[opentab]["rawdata"]["dropdatetime"] = dropdatetime
        self.alltabdata[opentab]["rawdata"]["ID"] = identifier
        
        #pulling raw t-d profile
        rawtemperature = self.alltabdata[opentab]["rawdata"]["temperature"]
        rawdepth = self.alltabdata[opentab]["rawdata"]["depth"]
        
        #identifying and removing NaNs
        if probetype == "AXCTD":
            rawconductivity = self.alltabdata[opentab]["rawdata"]["conductivity"]
            notnanind = ~np.isnan(rawtemperature*rawdepth*rawconductivity) #removing NaNs
            rawconductivity = rawconductivity[notnanind]
            rawsalinity = self.alltabdata[opentab]["rawdata"]["salinity"]
            rawsalinity = rawsalinity[notnanind]
        else:
            notnanind = ~np.isnan(rawtemperature*rawdepth) #removing NaNs
        
        rawtemperature = rawtemperature[notnanind]
        rawdepth = rawdepth[notnanind]
                
        #raw data structure to be passed to QC tab
        rawdata = {'temperature':rawtemperature, 'depth':rawdepth}
        
        if probetype == "AXCTD": #calculating salinity (AXCTD only)
            rawdata['salinity'] = rawsalinity
            
        #saves profile if necessary
        if not self.alltabdata[opentab]["profileSaved"]: #only if it hasn't been saved
            if self.settingsdict["autosave"]:
                if not self.savedataincurtab(): #try to save profile, terminate function if failed
                    return
            else:
                reply = QMessageBox.question(self, 'Save Raw Data?',
                "Would you like to save the raw data file? \n Filetype options can be adjusted in File>Raw Data File Types \n All unsaved work will be lost!", 
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Cancel)
                if reply == QMessageBox.Yes:
                    if not self.savedataincurtab(): #try to save profile, terminate function if failed
                        return
                elif reply == QMessageBox.Cancel:
                    return
                
        #prevent processor from continuing if there is no data
        if len(rawdepth) == 0:
            self.postwarning("No valid signal was identified in this profile! Please reprocess from the .wav file with lower minimum signal thresholds to generate a valid profile.")
            return
        
        #delete Processor profile canvas (widget with the profile plot) since it isn't in the tabwidgets sub-dict
        self.alltabdata[opentab]["ProcessorCanvas"].deleteLater()
        
        
    except Exception:
        trace_error()
        self.posterror("Failed to read profile data")
        return
        
    
    self.continuetoqc(opentab, rawdata, lat, lon, dropdatetime, identifier, probetype)
        
    