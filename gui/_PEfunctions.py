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
#    along with ARES.  If not, see <https://www.gnu.org/licenses/>.
# =============================================================================


from os import path
from traceback import print_exc as trace_error

from PyQt5.QtWidgets import (QApplication, QLineEdit, QLabel, QSpinBox, QCheckBox, QPushButton, QWidget, 
    QFileDialog, QComboBox, QTextEdit, QGridLayout)
from PyQt5.QtCore import QObjectCleanupHandler, Qt


from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

import time as timemodule
import numpy as np
from datetime import datetime

#autoQC-specific modules
import lib.fileinteraction as io
import lib.make_profile_plots as profplot
import lib.autoqc as qc
import lib.ocean_climatology_interaction as oci

from ._globalfunctions import (addnewtab, whatTab, renametab, setnewtabcolor, closecurrenttab, savedataincurtab, postwarning, posterror, postwarning_option, closeEvent, parsestringinputs, CustomToolbar)


      
# =============================================================================
#    TAB TO LOAD EXISTING DATA FILE INTO EDITOR
# =============================================================================
def makenewproftab(self):
    try:
        #tab indexing update
        opentab,tabID = self.addnewtab()

        self.alltabdata[opentab] = {"tab":QWidget(),"tablayout":QGridLayout(),"tabtype":"PE_u", "saved":True, "isprocessing":False, "datasource":None, "profileSaved":True, "probetype":'unknown'} #isprocessing and datasource are only relevant for processor tabs
        self.alltabdata[opentab]["tablayout"].setSpacing(10)
        
        self.setnewtabcolor(self.alltabdata[opentab]["tab"])

        self.tabWidget.addTab(self.alltabdata[opentab]["tab"],'New Tab') #self.tabWidget.addTab(self.currenttab,'New Tab')
        self.tabWidget.setCurrentIndex(opentab)
        self.tabWidget.setTabText(opentab,"Tab #" + str(opentab+1))
        self.alltabdata[opentab]["tabnum"] = tabID #assigning unique, unchanging number to current tab
        
        #Create widgets for UI
        self.alltabdata[opentab]["tabwidgets"] = {}
        self.alltabdata[opentab]["tabwidgets"]["title"] = QLabel('Enter Probe Drop Information:')
        self.alltabdata[opentab]["tabwidgets"]["probetitle"] = QLabel('Probe Type:')
        self.alltabdata[opentab]["tabwidgets"]["probetype"] = QComboBox()
        for p in self.probetypes:
            self.alltabdata[opentab]["tabwidgets"]["probetype"].addItem(p)
        self.alltabdata[opentab]["tabwidgets"]["probetype"].setCurrentIndex(self.probetypes.index(self.defaultprobe)) #set option to default probe
        self.alltabdata[opentab]["tabwidgets"]["lattitle"] = QLabel('Latitude (N>0): ')
        self.alltabdata[opentab]["tabwidgets"]["lattitle"] = QLabel('Latitude (N>0): ')
        self.alltabdata[opentab]["tabwidgets"]["latedit"] = QLineEdit('XX.XXX')
        self.alltabdata[opentab]["tabwidgets"]["lontitle"] = QLabel('Longitude (E>0): ')
        self.alltabdata[opentab]["tabwidgets"]["lonedit"] = QLineEdit('XX.XXX')
        self.alltabdata[opentab]["tabwidgets"]["datetitle"] = QLabel('Date: ')
        self.alltabdata[opentab]["tabwidgets"]["dateedit"] = QLineEdit('YYYYMMDD')
        self.alltabdata[opentab]["tabwidgets"]["timetitle"] = QLabel('Time (UTC): ')
        self.alltabdata[opentab]["tabwidgets"]["timeedit"] = QLineEdit('HHMM')
        self.alltabdata[opentab]["tabwidgets"]["idtitle"] = QLabel('Platform ID/Tail#: ')
        self.alltabdata[opentab]["tabwidgets"]["idedit"] = QLineEdit(self.settingsdict['platformid'])
        self.alltabdata[opentab]["tabwidgets"]["logtitle"] = QLabel('Select Source File: ')
        self.alltabdata[opentab]["tabwidgets"]["logbutton"] = QPushButton('Browse')
        self.alltabdata[opentab]["tabwidgets"]["logedit"] = QTextEdit('filepath/LOGXXXXX.DTA')
        self.alltabdata[opentab]["tabwidgets"]["logedit"].setMaximumHeight(100)
        self.alltabdata[opentab]["tabwidgets"]["logbutton"].clicked.connect(self.selectdatafile)
        self.alltabdata[opentab]["tabwidgets"]["submitbutton"] = QPushButton('PROCESS PROFILE')
        self.alltabdata[opentab]["tabwidgets"]["submitbutton"].clicked.connect(self.checkdatainputs_editorinput)
        
        #formatting widgets
        self.alltabdata[opentab]["tabwidgets"]["title"].setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["lattitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["lontitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["datetitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["timetitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["idtitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["logtitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        #should be 15 entries
        widgetorder = ["title", "probetitle", "probetype", "lattitle", "latedit", "lontitle", "lonedit", "datetitle", "dateedit", "timetitle", "timeedit", "idtitle", "idedit", "logtitle", "logedit", "logbutton", "submitbutton"]
        wrows     = [1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,10]
        wcols     = [1,1,2,1,2,1,2,1,2,1,2,1,2,1,2,1,1]
        wrext     = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
        wcolext   = [2,1,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2]    
        
        
        #adding user inputs
        for i,r,c,re,ce in zip(widgetorder,wrows,wcols,wrext,wcolext):
            self.alltabdata[opentab]["tabwidgets"][i].setFont(self.labelfont)
            self.alltabdata[opentab]["tablayout"].addWidget(self.alltabdata[opentab]["tabwidgets"][i],r,c,re,ce)
        
        #forces grid info to top/center of window
        self.alltabdata[opentab]["tablayout"].setRowStretch(11,1)
        self.alltabdata[opentab]["tablayout"].setColumnStretch(0,1)
        self.alltabdata[opentab]["tablayout"].setColumnStretch(3,1)

        #applying layout
        self.alltabdata[opentab]["tab"].setLayout(self.alltabdata[opentab]["tablayout"]) 

    except Exception:
        trace_error()
        self.posterror("Failed to build editor input tab!")

        
        
#browse for raw data file to QC
def selectdatafile(self):
    try:
        fname,ok = QFileDialog.getOpenFileName(self, 'Open file',self.defaultfilereaddir,
        "Source Data Files (*.DTA *.Dta *.dta *.EDF *.Edf *.edf *.edf *.NVO *.Nvo *.nvo *.FIN *.Fin *.fin *.JJVV *.Jjvv *.jjvv *.TXT *.Txt *.txt)","",self.fileoptions)
         
        if ok:
            opentab = self.whatTab()
            self.alltabdata[opentab]["tabwidgets"]["logedit"].setText(fname)
            
            #getting file directory
            if fname != "":
                splitpath = path.split(fname)
                self.defaultfilereaddir = splitpath[0]
                
    except Exception:
        trace_error()
        self.posterror("Failed to select file- please try again or manually enter full path to file in box below.")

        
        
#Pull data, check to make sure it is valid before proceeding
def checkdatainputs_editorinput(self):
    opentab = self.whatTab()
    
    success = True
    errormsg = ''
    warningmsg = ''
        
    #pulling data from inputs
    probetype = self.alltabdata[opentab]["tabwidgets"]["probetype"].currentText()
    latstr = self.alltabdata[opentab]["tabwidgets"]["latedit"].text()
    lonstr = self.alltabdata[opentab]["tabwidgets"]["lonedit"].text()
    identifier = self.alltabdata[opentab]["tabwidgets"]["idedit"].text()
    profdatestr = self.alltabdata[opentab]["tabwidgets"]["dateedit"].text()
    timestr = self.alltabdata[opentab]["tabwidgets"]["timeedit"].text()
    logfile = self.alltabdata[opentab]["tabwidgets"]["logedit"].toPlainText()
    
    if probetype.upper() == "AXCTD":
        hasSal = True
    else:
        hasSal = False
    
    #identify file type
    ftype = 0
    if not path.isfile(logfile): #check that logfile exists
        success = False
        warningmsg = 'Selected Data File Does Not Exist!'
        
    else:
        #determine file type (1 = LOG, 2 = EDF, 3 = FIN/NVO, 4 = JJVV, 0 = invalid)
        if logfile[-4:].lower() == '.dta':
            ftype = 1
        elif logfile[-4:].lower() == '.edf':
            ftype = 2
        elif logfile[-4:].lower() in ['.fin','.nvo','.txt']: #assumes .txt are fin/nvo format
            ftype = 3
        elif logfile[-5:].lower() == '.jjvv':
            ftype = 4
            
    if not ftype:
        success = False
        warningmsg = 'Invalid Data File Format (must be .dta,.edf,.nvo,.fin, or .jjvv)!'
        
    elif hasSal and ftype in [1,4]: #can't process AXCTD data from LOG or JJVV files
        success = False
        warningmsg = 'AXCTD profiles cannot be LOG or JJVV format!'

        
    #initializing lat/lon/datetime variables    
    lon = np.NaN
    lat = np.NaN
    dropdatetime = False
    flat = np.NaN
    flon = np.NaN
    fdropdatetime = False
        
        
    #read profile data
    try:
        #if LOG.DTA file, read profile data and get datetime/position from user
        if ftype == 1:
            rawtemperature,rawdepth = io.readlogfile(logfile)
            
        #EDF/FIN/JJVV includes logic to handle partially missing data fields (e.g. lat/lon)
        elif ftype == 2:
            data,fdropdatetime,flat,flon = io.readedffile(logfile)
            
        elif ftype == 3: #assumes .txt are fin/nvo format
            data,fdropdatetime,flat,flon,_ = io.readfinfile(logfile,hasSal=hasSal)
            
        elif ftype == 4:
            try: #year is important if jjvv file
                year = int(profdatestr[:4])
            except:
                year = datetime.utcnow().year #defaults to current year if date not input in UI
            rawtemperature,rawdepth,fdropdatetime,flat,flon,identifier = io.readjjvvfile(logfile)
            
        if ftype in [2,3]: #pulling z/T/S(?) from file output for EDF/FIN/NVO files
            rawtemperature = data["temperature"]
            rawdepth = data["depth"]
            if hasSal:
                rawsalinity = data["salinity"]
                                
        #finding and removing NaNs from profile
        if ftype > 0:
            if hasSal:
                notnanind = ~np.isnan(rawtemperature*rawdepth*rawsalinity)
            else:
                notnanind = ~np.isnan(rawtemperature*rawdepth)
                
            rawdata = {'depth':rawdepth[notnanind], 'temperature':rawtemperature[notnanind]}
            if hasSal:
                rawdata['salinity'] = rawsalinity[notnanind]
                
            if len(rawdata['depth']) == 0:
                success = False
                warningmsg = 'This file does not contain any valid profile data. Please select a different file!'
            
    except Exception:
        trace_error()
        success = False
        errormsg = 'Failed to read selected data file!'
            
    if ftype and success:
            
        try:
            ilat,ilon,idropdatetime,identifier = self.parsestringinputs(latstr, lonstr, profdatestr, timestr, identifier, True, True, True)
        
            if np.isnan(flat*flon):
                lat = ilat
                lon = ilon
            else:
                lat = flat
                lon = flon
                
            if not fdropdatetime:
                dropdatetime = idropdatetime
            else:
                dropdatetime = fdropdatetime
                
        except:
            success = False
            errormsg = "Failed to parse user input!"
        
    #if the read failed, stop spinning cursor and post appropriate message to screen
    if not success:
        QApplication.restoreOverrideCursor()
        if errormsg:
            self.posterror(errormsg)
        elif warningmsg:
            self.postwarning(errormsg)
        return
        
        
    #only gets here if all inputs are good- this function switches the tab to profile editor view
    self.defaultprobe = probetype #switch default probe type to whatever was just processed
    self.continuetoqc(opentab, rawdata, lat, lon, dropdatetime, identifier, probetype)
    
    
    
    
    
# =============================================================================
#         PROFILE EDITOR TAB
# =============================================================================
def continuetoqc(self, opentab, rawdata, lat, lon, dropdatetime, identifier, probetype):
    try:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        dtg = datetime.strftime(dropdatetime,'%Y%m%d%H%M')
        
        #concatenates profile if depths stop increasing
        negind = np.argwhere(np.diff(rawdepth) < 0)
        if len(negind) > 0: #if depths do decrease at some point, truncate the profile there
            cutoff = negind[0][0] + 1
            rawtemperature = rawtemperature[:cutoff]
            rawdepth = rawdepth[:cutoff]

        # pull ocean depth from ETOPO1 Grid-Registered Ice Sheet based global relief dataset
        # Data source: NOAA-NGDC: https://www.ngdc.noaa.gov/mgg/global/global.html
        try:
            oceandepth, exportlat, exportlon, exportrelief = oci.getoceandepth(lat, lon, 6, self.bathymetrydata)
        except:
            trace_error()
            oceandepth = np.NaN
            exportlat = exportlon = np.array([0,1])
            exportrelief = np.NaN*np.ones((2,2))
            self.posterror("Unable to find/load bathymetry data for profile location!")
        
        #getting climatology
        try:
            [climotemps,climopsals,climodepths,climotempfill,climopsalfill,climodepthfill] = oci.getclimatologyprofile(lat,lon,dropdatetime.month,self.climodata)
        except:
            climopsals = climotemps = climodepths = np.array([np.NaN,np.NaN])
            climopsalfill = climotempfill = climodepthfill = np.array([np.NaN,np.NaN,np.NaN,np.NaN])
            self.posterror("Unable to find/load climatology data for profile location!")
        
        self.alltabdata[opentab]["probetype"] = probetype
        self.alltabdata[opentab]["profileSaved"] = False #profile hasn't been saved yet
        self.alltabdata[opentab]["profdata"] = {"temperature_raw": rawdata['temperature'], "depth_raw": rawdata['depth'],"lat": lat, "lon": lon, "dropdatetime": dropdatetime, "climotemp": climotemps, "climopsal":climopsals, "climodepth": climodepths, "climotempfill": climotempfill, "climopsalfill": climopsalfill, "climodepthfill": climodepthfill, "ID": identifier, "oceandepth": oceandepth}
        if probetype == 'AXCTD':
            self.alltabdata[opentab]["profdata"]['salinity_raw'] = rawdata['salinity']
        
        #deleting old buttons and inputs
        for i in self.alltabdata[opentab]["tabwidgets"]:
            try:
                self.alltabdata[opentab]["tabwidgets"][i].deleteLater()
            except:
                self.alltabdata[opentab]["tabwidgets"][i] = 1 #bs variable- overwrites spacer item
                            
        if self.settingsdict["renametabstodtg"]:
            curtab = self.tabWidget.currentIndex()
            self.tabWidget.setTabText(curtab,dtg)  
            
        #now delete widget entries
        del self.alltabdata[opentab]["tabwidgets"]
        QObjectCleanupHandler().add(self.alltabdata[opentab]["tablayout"])
        
        self.alltabdata[opentab]["tablayout"] = QGridLayout()
        self.alltabdata[opentab]["tab"].setLayout(self.alltabdata[opentab]["tablayout"]) 
        self.alltabdata[opentab]["tablayout"].setSpacing(10)
        
        #ADDING FIGURES AND AXES TO GRID LAYOUT (row column rowext colext)
        self.alltabdata[opentab]["ProfFig"] = plt.figure()
        self.alltabdata[opentab]["ProfCanvas"] = FigureCanvas(self.alltabdata[opentab]["ProfFig"]) 
        self.alltabdata[opentab]["tablayout"].addWidget(self.alltabdata[opentab]["ProfCanvas"],0,0,14,1)
        self.alltabdata[opentab]["ProfCanvas"].setStyleSheet("background-color:transparent;")
        self.alltabdata[opentab]["ProfFig"].patch.set_facecolor('None')
        self.alltabdata[opentab]["ProfAx"] = plt.axes()
        self.alltabdata[opentab]["LocFig"] = plt.figure()
        self.alltabdata[opentab]["LocCanvas"] = FigureCanvas(self.alltabdata[opentab]["LocFig"]) 
        self.alltabdata[opentab]["tablayout"].addWidget(self.alltabdata[opentab]["LocCanvas"],11,2,1,5)
        self.alltabdata[opentab]["LocCanvas"].setStyleSheet("background-color:transparent;")
        self.alltabdata[opentab]["LocFig"].patch.set_facecolor('None')
        self.alltabdata[opentab]["LocAx"] = plt.axes()

        #adding toolbar for profile editor
        self.alltabdata[opentab]["ProfToolbar"] = CustomToolbar(self.alltabdata[opentab]["ProfCanvas"], self) 
        self.alltabdata[opentab]["tablayout"].addWidget(self.alltabdata[opentab]["ProfToolbar"],2,2,1,2)
        
        #adding toolbar for location
        self.alltabdata[opentab]["LocToolbar"] = CustomToolbar(self.alltabdata[opentab]["LocCanvas"], self) 
        self.alltabdata[opentab]["tablayout"].addWidget(self.alltabdata[opentab]["LocToolbar"],12,3,1,3)

        #Create widgets for UI populated with test example
        self.alltabdata[opentab]["tabwidgets"] = {}
        
        #first column: profile editor functions:
        self.alltabdata[opentab]["tabwidgets"]["toggleclimooverlay"] = QPushButton('Overlay Climatology') #1
        self.alltabdata[opentab]["tabwidgets"]["toggleclimooverlay"].setCheckable(True)
        self.alltabdata[opentab]["tabwidgets"]["toggleclimooverlay"].setChecked(True)
        self.alltabdata[opentab]["tabwidgets"]["toggleclimooverlay"].clicked.connect(self.toggleclimooverlay) 
        
        self.alltabdata[opentab]["tabwidgets"]["addpoint"] = QPushButton('Add Point') #2
        self.alltabdata[opentab]["tabwidgets"]["addpoint"].clicked.connect(self.addpoint)
        self.alltabdata[opentab]["tabwidgets"]["addpoint"].setToolTip("After clicking, select a single point to add")
        
        self.alltabdata[opentab]["tabwidgets"]["removepoint"] = QPushButton('Remove Point') #3
        self.alltabdata[opentab]["tabwidgets"]["removepoint"].clicked.connect(self.removepoint)
        self.alltabdata[opentab]["tabwidgets"]["removepoint"].setToolTip("After clicking, select a single point to remove")

        self.alltabdata[opentab]["tabwidgets"]["removerange"] = QPushButton('Remove Range') #4
        self.alltabdata[opentab]["tabwidgets"]["removerange"].clicked.connect(self.removerange)
        self.alltabdata[opentab]["tabwidgets"]["removerange"].setToolTip("After clicking, click and drag over a (vertical) range of points to remove")
        
        self.alltabdata[opentab]["tabwidgets"]["sfccorrectiontitle"] = QLabel('Isothermal Layer (m):') #5
        self.alltabdata[opentab]["tabwidgets"]["sfccorrection"] = QSpinBox() #6
        self.alltabdata[opentab]["tabwidgets"]["sfccorrection"].setRange(0, int(np.max(rawdepth+200)))
        self.alltabdata[opentab]["tabwidgets"]["sfccorrection"].setSingleStep(1)
        self.alltabdata[opentab]["tabwidgets"]["sfccorrection"].setValue(0)
        
        self.alltabdata[opentab]["tabwidgets"]["maxdepthtitle"] = QLabel('Maximum Depth (m):') #7
        self.alltabdata[opentab]["tabwidgets"]["maxdepth"] = QSpinBox() #8
        self.alltabdata[opentab]["tabwidgets"]["maxdepth"].setRange(0, int(np.round(np.max(rawdepth+200),-2)))
        self.alltabdata[opentab]["tabwidgets"]["maxdepth"].setSingleStep(1)
        # self.alltabdata[opentab]["tabwidgets"]["maxdepth"].setValue(int(np.round(maxdepth)))
        self.alltabdata[opentab]["tabwidgets"]["maxdepth"].setValue(int(np.round(1000)))
        
        self.alltabdata[opentab]["tabwidgets"]["depthdelaytitle"] = QLabel('Depth Delay (m):') #9
        self.alltabdata[opentab]["tabwidgets"]["depthdelay"] = QSpinBox() #10
        self.alltabdata[opentab]["tabwidgets"]["depthdelay"].setRange(0, int(np.round(np.max(rawdepth+200),-2)))
        self.alltabdata[opentab]["tabwidgets"]["depthdelay"].setSingleStep(1)
        self.alltabdata[opentab]["tabwidgets"]["depthdelay"].setValue(0)

        self.alltabdata[opentab]["tabwidgets"]["runqc"] = QPushButton('Re-QC Profile (Reset)') #11
        self.alltabdata[opentab]["tabwidgets"]["runqc"].clicked.connect(self.runqc) 
        
        
        #Second column: profile information
        self.alltabdata[opentab]["tabwidgets"]["proftxt"] = QLabel(' ')#12
        self.alltabdata[opentab]["tabwidgets"]["isbottomstrike"] = QCheckBox('Bottom Strike?') #13
        self.alltabdata[opentab]["tabwidgets"]["rcodetitle"] = QLabel('Profile Quality:') #14
        self.alltabdata[opentab]["tabwidgets"]["rcode"] = QComboBox() #15
        for rcodestr in self.reason_code_strings:
            self.alltabdata[opentab]["tabwidgets"]["rcode"].addItem(rcodestr)
        
        #profile save button
        self.alltabdata[opentab]["tabwidgets"]["saveprof"] = QPushButton('Save Profile') #11
        self.alltabdata[opentab]["tabwidgets"]["saveprof"].clicked.connect(self.savedataincurtab)    
        
            
        #formatting widgets
        self.alltabdata[opentab]["tabwidgets"]["proftxt"].setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["rcodetitle"].setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["depthdelaytitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["sfccorrectiontitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alltabdata[opentab]["tabwidgets"]["maxdepthtitle"].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        
        #should be 15 entries
        widgetorder = ["toggleclimooverlay", "addpoint", "removepoint", "removerange", "sfccorrectiontitle", "sfccorrection", "maxdepthtitle", "maxdepth", "depthdelaytitle", "depthdelay", "runqc", "proftxt", "isbottomstrike", "rcodetitle", "rcode", "saveprof"]
        
        wrows     = [3,4,4,5,6,6,7,7,8,8,9,5,3,3,4,9]
        wcols     = [2,2,3,2,2,3,2,3,2,3,2,5,6,5,5,5]
        wrext     = [1,1,1,1,1,1,1,1,1,1,1,4,1,1,1,1]
        wcolext   = [2,1,1,2,1,1,1,1,1,1,2,2,1,1,2,2]
        
        #adding user inputs
        for i,r,c,re,ce in zip(widgetorder,wrows,wcols,wrext,wcolext):
            self.alltabdata[opentab]["tabwidgets"][i].setFont(self.labelfont)
            self.alltabdata[opentab]["tablayout"].addWidget(self.alltabdata[opentab]["tabwidgets"][i],r,c,re,ce)
            

        #adjusting stretch factors for all rows/columns
        colstretch = [13,1,1,1,1,1,1,1,1]
        for col,cstr in zip(range(0,len(colstretch)),colstretch):
            self.alltabdata[opentab]["tablayout"].setColumnStretch(col,cstr)
        rowstretch = [0,1,1,1,1,1,1,1,0,1,1,9,1]
        for row,rstr in zip(range(0,len(rowstretch)),rowstretch):
            self.alltabdata[opentab]["tablayout"].setRowStretch(row,rstr)

        #run autoQC code, pull variables from self.alltabdata dict
        self.alltabdata[opentab]["hasbeenprocessed"] = False
        
        if self.runqc(): #only executes following code if autoQC runs sucessfully
            depth = self.alltabdata[opentab]["profdata"]["depth_plot"]
            temperature = self.alltabdata[opentab]["profdata"]["temperature_plot"]
            matchclimo = self.alltabdata[opentab]["profdata"]["matchclimo"]

            # plot data, refresh plots on window
            self.alltabdata[opentab]["climohandle"] = profplot.makeprofileplot(self.alltabdata[opentab]["ProfAx"], rawtemperature, rawdepth, temperature, depth, dtg, climodatafill=climotempfill, climodepthfill=climodepthfill, datacolor='r', datalabel = 'Temperature ($^\circ$C)', matchclimo=matchclimo, axlimtype=1)
            
            profplot.makelocationplot(self.alltabdata[opentab]["LocFig"],self.alltabdata[opentab]["LocAx"],lat,lon,dtg,exportlon,exportlat,exportrelief,6)
            self.alltabdata[opentab]["ProfCanvas"].draw() #update figure canvases
            self.alltabdata[opentab]["LocCanvas"].draw()
            self.alltabdata[opentab]["pt_type"] = 0  # sets that none of the point selector buttons have been pushed
            self.alltabdata[opentab]["hasbeenprocessed"] = True #note that the autoQC driver has run at least once

            #configure spinboxes to run "applychanges" function after being changed
            self.alltabdata[opentab]["tabwidgets"]["sfccorrection"].valueChanged.connect(self.applychanges)
            self.alltabdata[opentab]["tabwidgets"]["maxdepth"].valueChanged.connect(self.applychanges)
            self.alltabdata[opentab]["tabwidgets"]["depthdelay"].valueChanged.connect(self.applychanges)

            self.alltabdata[opentab]["tabtype"] = "PE_p"
    except Exception:
        trace_error()
        self.posterror("Failed to build profile editor tab!")
    finally:
        QApplication.restoreOverrideCursor()
        
        
        
        

# =============================================================================
#         AUTOQC DRIVER CODE
# =============================================================================

def runqc(self):
    try:
        opentab = self.whatTab()

        # getting necessary data for QC from dictionary
        rawtemperature = self.alltabdata[opentab]["profdata"]["temp_raw"]
        rawdepth = self.alltabdata[opentab]["profdata"]["depth_raw"]
        climotemps = self.alltabdata[opentab]["profdata"]["climotemp"]
        climodepths = self.alltabdata[opentab]["profdata"]["climodepth"]
        climotempfill = self.alltabdata[opentab]["profdata"]["climotempfill"]
        climodepthfill = self.alltabdata[opentab]["profdata"]["climodepthfill"]
        oceandepth = self.alltabdata[opentab]["profdata"]["oceandepth"]
        

        # TODO: Integrate this into the settings window
        self.settingsdict["maxstdev"] = 1

        try:
            # running QC, comparing to climo
            temperature, depth = qc.autoqc(rawtemperature, rawdepth, self.settingsdict["smoothlev"],self.settingsdict["profres"], self.settingsdict["maxstdev"], self.settingsdict["checkforgaps"])
            if self.settingsdict["comparetoclimo"] and climodepths.size != 0:
                matchclimo, climobottomcutoff = oci.comparetoclimo(temperature, depth, climotemps, climodepths,climotempfill,climodepthfill)
            else:
                matchclimo = True
                climobottomcutoff = np.NaN
                
        except Exception:
            temperature = np.array([np.NaN])
            depth = np.array([0])
            matchclimo = climobottomcutoff = 0
            trace_error()
            self.posterror("Error raised in automatic profile QC")
        
            
        #saving QC profile first (before truncating depth due to ID'd bottom strikes)
        self.alltabdata[opentab]["profdata"]["depth_qc"] = depth.copy() #using copy method so further edits made won't be reflected in these stored versions of the QC'ed profile
        self.alltabdata[opentab]["profdata"]["temp_qc"] = temperature.copy()
        

        # limit profile depth by climatology cutoff, ocean depth cutoff
        maxdepth = np.ceil(np.max(depth))
        isbottomstrike = 0
        if self.settingsdict["useoceanbottom"] and np.isnan(oceandepth) == 0 and oceandepth <= maxdepth:
            maxdepth = oceandepth
            isbottomstrike = 1
        if self.settingsdict["useclimobottom"] and np.isnan(climobottomcutoff) == 0 and climobottomcutoff <= maxdepth:
            isbottomstrike = 1
            maxdepth = climobottomcutoff
        isbelowmaxdepth = np.less_equal(depth, maxdepth)
        temperature = temperature[isbelowmaxdepth]
        depth = depth[isbelowmaxdepth]

        # writing values to alltabs structure: prof temps, and matchclimo
        self.alltabdata[opentab]["profdata"]["depth_plot"] = depth
        self.alltabdata[opentab]["profdata"]["temperature_plot"] = temperature
        self.alltabdata[opentab]["profdata"]["matchclimo"] = matchclimo

        # resetting depth correction QSpinBoxes
        self.alltabdata[opentab]["tabwidgets"]["maxdepth"].setValue(int(np.round(maxdepth)))
        self.alltabdata[opentab]["tabwidgets"]["depthdelay"].setValue(0)
        self.alltabdata[opentab]["tabwidgets"]["sfccorrection"].setValue(0)

        # adjusting bottom strike checkbox as necessary
        if isbottomstrike == 1:
            self.alltabdata[opentab]["tabwidgets"]["isbottomstrike"].setChecked(True)
        else:
            self.alltabdata[opentab]["tabwidgets"]["isbottomstrike"].setChecked(False)

        self.updateprofeditplots() #update profile plot, data on window
        
        return True #return true if autoQC runs successfully

    except Exception:
        trace_error()
        self.posterror("Failed to run autoQC")
        
        return False #return false if autoQC fails



    
# =============================================================================
#         PROFILE EDITING FUNCTION CALLS
# =============================================================================
#apply changes from sfc correction/max depth/depth delay spin boxes
def applychanges(self):
    try:
        opentab = self.whatTab()
        #current t/d profile
        tempplot = self.alltabdata[opentab]["profdata"]["temp_qc"].copy()
        depthplot = self.alltabdata[opentab]["profdata"]["depth_qc"].copy()
        
        if len(tempplot) > 0 and len(depthplot) > 0:

            #new depth correction settings
            sfcdepth = self.alltabdata[opentab]["tabwidgets"]["sfccorrection"].value()
            maxdepth = self.alltabdata[opentab]["tabwidgets"]["maxdepth"].value()
            depthdelay = self.alltabdata[opentab]["tabwidgets"]["depthdelay"].value()

            if depthdelay > 0: #shifitng entire profile up if necessary
                depthplot = depthplot - depthdelay
                ind = depthplot >= 0
                depthplot = depthplot[ind]
                tempplot = tempplot[ind]

            if sfcdepth > 0: #replacing surface temperatures
                sfctemp = np.interp(sfcdepth,depthplot,tempplot)
                ind = depthplot <= sfcdepth
                tempplot[ind] = sfctemp

            if maxdepth < np.max(depthplot): #truncating base of profile
                ind = depthplot <= maxdepth
                tempplot = tempplot[ind]
                depthplot = depthplot[ind]

            #replacing t/d profile values
            self.alltabdata[opentab]["profdata"]["temperature_plot"] = tempplot
            self.alltabdata[opentab]["profdata"]["depth_plot"] = depthplot

            #re-plotting, updating text
            self.updateprofeditplots()
            
    except Exception:
        trace_error()
        self.posterror("Failed to update profile!")
        

        
def updateprofeditplots(self):
    opentab = self.whatTab()

    try:
        tempplot = self.alltabdata[opentab]["profdata"]["temperature_plot"]
        depthplot = self.alltabdata[opentab]["profdata"]["depth_plot"]
        
        # Replace drop info
        proftxt = self.generateprofiledescription(opentab,len(tempplot))
        self.alltabdata[opentab]["tabwidgets"]["proftxt"].setText(proftxt)

        # re-plotting (if not first pass through editor)
        if self.alltabdata[opentab]["hasbeenprocessed"]:
            del self.alltabdata[opentab]["ProfAx"].lines[-1]
            self.alltabdata[opentab]["ProfAx"].plot(tempplot, depthplot, 'r', linewidth=2, label='QC')
            self.alltabdata[opentab]["ProfCanvas"].draw()
            
        self.alltabdata[opentab]["profileSaved"] = False
        self.add_asterisk(opentab)

    except Exception:
        trace_error()
        self.posterror("Failed to update profile editor plots!")

        
        
def generateprofiledescription(self,opentab,numpoints):
    try:
        sfcdepth = self.alltabdata[opentab]["tabwidgets"]["sfccorrection"].value()
        maxdepth = self.alltabdata[opentab]["tabwidgets"]["maxdepth"].value()
        depthdelay = self.alltabdata[opentab]["tabwidgets"]["depthdelay"].value()
        
        lon = self.alltabdata[opentab]["profdata"]["lon"]
        lat = self.alltabdata[opentab]["profdata"]["lat"]
        oceandepth = self.alltabdata[opentab]["profdata"]["oceandepth"]
        
        if lon >= 0: #prepping coordinate string
            ewhem = ' \xB0E'
        else:
            ewhem = ' \xB0W'
        if lat >= 0:
            nshem = ' \xB0N'
        else:
            nshem = ' \xB0S'
        
        #generating text string
        proftxt = ("Profile Data: \n" #header
           + f"{abs(round(lon, 3))}{ewhem}, {abs(round(lat, 3))}{nshem} \n" #lat/lon
           + f"Ocean Depth: {np.round(oceandepth,1)} m\n" #ocean depth
           + f"QC Profile Depth: {np.round(maxdepth,1)} m\n" #profile depth
           + f"QC SFC Correction: {sfcdepth} m\n" #user-specified surface correction
           + f"QC Depth Delay: {depthdelay} m\n" #user-added depth delay
           + f"# Datapoints: {numpoints}")
        
        return proftxt
    
    except Exception:
        trace_error()
        self.posterror("Failed to update profile!")
        return "Unable to\ngenerate text!"


        
#add point on profile
def addpoint(self):
    opentab = self.whatTab()
    if self.alltabdata[opentab]["pt_type"] == 0:
        try:
            QApplication.setOverrideCursor(Qt.CrossCursor)
            opentab = self.whatTab()
            self.alltabdata[opentab]["pt_type"] = 1
            self.alltabdata[opentab]["pt"] = self.alltabdata[opentab]["ProfCanvas"].mpl_connect('button_release_event', self.on_release)
        except Exception:
            trace_error()
            self.posterror("Failed to add point")
            
            
        
#remove point on profile
def removepoint(self):
    opentab = self.whatTab()
    if self.alltabdata[opentab]["pt_type"] == 0:
        try:
            QApplication.setOverrideCursor(Qt.CrossCursor)
            opentab = self.whatTab()
            self.alltabdata[opentab]["pt_type"] = 2
            self.alltabdata[opentab]["pt"] = self.alltabdata[opentab]["ProfCanvas"].mpl_connect('button_release_event', self.on_release)
        except Exception:
            trace_error()
            self.posterror("Failed to remove point")
            
            

#remove range of points (e.g. profile spike)
def removerange(self):
    opentab = self.whatTab()
    if self.alltabdata[opentab]["pt_type"] == 0:
        try:
            QApplication.setOverrideCursor(Qt.CrossCursor)
            opentab = self.whatTab()
            self.alltabdata[opentab]["pt_type"] = 3
            self.alltabdata[opentab]["ptspike"] = self.alltabdata[opentab]["ProfCanvas"].mpl_connect('button_press_event', self.on_press_spike)
            self.alltabdata[opentab]["pt"] = self.alltabdata[opentab]["ProfCanvas"].mpl_connect('button_release_event', self.on_release)
        except Exception:
            trace_error()
            self.posterror("Failed to remove range")
            
            

def on_press_spike(self,event):
    self.y1_spike = event.ydata #gets first depth argument
    
    
        
#update profile with selected point to add or remove
def on_release(self,event):

    opentab = self.whatTab()
    try:
        xx = event.xdata #selected x and y points
        yy = event.ydata
        
        #retrieve and update values
        tempplot = self.alltabdata[opentab]["profdata"]["temp_qc"]
        depthplot = self.alltabdata[opentab]["profdata"]["depth_qc"]
        
        #ADD A POINT
        if self.alltabdata[opentab]["pt_type"] == 1:
            rawt = self.alltabdata[opentab]["profdata"]["temp_raw"]
            rawd = self.alltabdata[opentab]["profdata"]["depth_raw"]
            pt = np.argmin(abs(rawt-xx)**2 + abs(rawd-yy)**2)
            addtemp = rawt[pt]
            adddepth = rawd[pt]
            if not adddepth in depthplot:
                try: #if np array
                    ind = np.where(adddepth > depthplot)
                    ind = ind[0][-1]+1 #index to add
                    depthplot = np.insert(depthplot,ind,adddepth)
                    tempplot = np.insert(tempplot,ind,addtemp)
                except: #if list
                    i = 0
                    for i,cdepth in enumerate(depthplot):
                        if cdepth > adddepth:
                            break
                    depthplot.insert(i,adddepth)
                    tempplot.insert(i,addtemp)
                    
        #REMOVE A POINT
        elif self.alltabdata[opentab]["pt_type"] == 2:
            pt = np.argmin(abs(tempplot-xx)**2 + abs(depthplot-yy)**2)
            try: #if its an array
                tempplot = np.delete(tempplot,pt)
                depthplot = np.delete(depthplot,pt)
            except: #if its a list
                tempplot.pop(pt)
                depthplot.pop(pt)

        #REMOVE A SPIKE
        elif self.alltabdata[opentab]["pt_type"] == 3:
            y1 = np.min([self.y1_spike,yy])
            y2 = np.max([self.y1_spike,yy])
            goodvals = (depthplot < y1) | (depthplot > y2)
            tempplot = tempplot[goodvals]
            depthplot = depthplot[goodvals]
                
        #replace values in profile
        self.alltabdata[opentab]["profdata"]["depth_qc"] = depthplot
        self.alltabdata[opentab]["profdata"]["temp_qc"] = tempplot
        
        #applying user corrections
        self.applychanges()


    except Exception:
        trace_error()
        self.posterror("Failed to select profile point!")

    finally:
        #restore cursor type, delete current indices, reset for next correction
        QApplication.restoreOverrideCursor()
        self.alltabdata[opentab]["ProfCanvas"].mpl_disconnect(self.alltabdata[opentab]["pt"])
        del self.alltabdata[opentab]["pt"]
        if self.alltabdata[opentab]["pt_type"] == 3: #if spike selection, remove additional mpl connection
            self.alltabdata[opentab]["ProfCanvas"].mpl_disconnect(self.alltabdata[opentab]["ptspike"])
            del self.alltabdata[opentab]["ptspike"]
        self.alltabdata[opentab]["pt_type"] = 0 #reset

        
        
        
#toggle visibility of climatology profile
def toggleclimooverlay(self,pressed):
    try:
        opentab = self.whatTab()
        if pressed:
            self.alltabdata[opentab]["climohandle"].set_visible(True)     
        else:
            self.alltabdata[opentab]["climohandle"].set_visible(False)
        self.alltabdata[opentab]["ProfCanvas"].draw()
    except Exception:
        trace_error()
        self.posterror("Failed to toggle climatology overlay")
        
        
        
        
        
            