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

from platform import system as cursys

global slash
if cursys() == 'Windows':
    slash = '\\'
else:
    slash = '/'

from os import remove, path, listdir
from traceback import print_exc as trace_error
from shutil import copy as shcopy

from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog, QLineEdit
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette, QBrush, QLinearGradient

from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

import re
import time as timemodule
import datetime as dt
import numpy as np
import matplotlib.pyplot as plt

import lib.fileinteraction as io
import lib.PE.make_profile_plots as profplot
import lib.PE.ocean_climatology_interaction as oci




    
# =============================================================================
#     TAB MANIPULATION OPTIONS, OTHER GENERAL FUNCTIONS
# =============================================================================

#handles tab indexing
def addnewtab(self):
    #creating numeric ID for newly opened tab
    self.totaltabs += 1
    self.tabIDs.append(self.totaltabs) #tracks unique ID for each tab (for updating from separate threads)
    self.alltabdata.append({}) #append an empty dict to tab data to be overwritten with info
    opentab = self.tabWidget.count()
    return opentab, self.totaltabs
    
    

#gets index of open tab in GUI
def whatTab(self):
    return self.tabWidget.currentIndex()
    

#renames tab (only user-visible name, not self.alltabdata dict key)
def renametab(self):
    try:
        opentab = self.whatTab()
        badcharlist = "[@!#$%^&*()<>?/\|}{~:]"
        strcheck = re.compile(badcharlist)
        name, ok = QInputDialog.getText(self, 'Rename Current Tab', 'Enter new tab name:',QLineEdit.Normal,str(self.tabWidget.tabText(opentab)))
        if ok:
            if strcheck.search("name") == None:
                self.tabWidget.setTabText(opentab,name)
                if not self.alltabdata[opentab]["profileSaved"]: #add an asterisk if profile is unsaved
                    self.add_asterisk(opentab)
            else:
                self.postwarning("Tab names cannot include the following: " + badcharlist)
    except Exception:
        trace_error()
        self.posterror("Failed to rename the current tab")
        
        
        

#adds asterisk to tab name when data is unsaved or profile is adjusted
def add_asterisk(self,curtab):
    try:
        name = self.tabWidget.tabText(curtab)
        if not self.alltabdata[curtab]["profileSaved"] and name[-1] != '*':
            self.tabWidget.setTabText(curtab,name+'*')
    except Exception:
        trace_error()
        self.posterror("Failed to add unsave asterisk to tab name")
    

#removes asterisk from tab name when data is saved successfully
def remove_asterisk(self,curtab):
    try:
        name = self.tabWidget.tabText(curtab)
        if self.alltabdata[curtab]["profileSaved"] and name[-1] == '*':
            self.tabWidget.setTabText(curtab,name[:-1])
    except Exception:
        trace_error()
        self.posterror("Failed to remove unsave asterisk from tab name")


#sets default color scheme for tabs
@staticmethod
def setnewtabcolor(tab):
    p = QPalette()
    gradient = QLinearGradient(0, 0, 0, 400)
    gradient.setColorAt(0.0, QColor(253,253,255))
    #gradient.setColorAt(1.0, QColor(248, 248, 255))
    gradient.setColorAt(1.0, QColor(225, 225, 255))
    p.setBrush(QPalette.Window, QBrush(gradient))
    tab.setAutoFillBackground(True)
    tab.setPalette(p)
    
    
        
#closes a tab
def closecurrenttab(self):
    try:
        opentab = self.whatTab()
        
        reply = QMessageBox.question(self, 'Message',
            "Are you sure to close the current tab?", QMessageBox.Yes | 
            QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:

            #getting tab to close
            indextoclose = self.tabWidget.currentIndex()
            
            #check to make sure there isn't a corresponding processor thread, close if there is
            if self.alltabdata[opentab]["isprocessing"]:
                reply = QMessageBox.question(self, 'Message',
                    "Closing this tab will terminate the current profile and discard the data. Continue?", QMessageBox.Yes | 
                    QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return
                else:
                    self.alltabdata[opentab]["processor"].abort()

            #closing open figures in tab to prevent memory leak
            if self.alltabdata[opentab]["tabtype"] == "ProfileEditor":
                plt.close(self.alltabdata[opentab]["ProfFig"])
                plt.close(self.alltabdata[opentab]["LocFig"])

            elif self.alltabdata[opentab]["tabtype"] == 'SignalProcessor_incomplete' or self.alltabdata[opentab]["tabtype"] == 'SignalProcessor_completed':
                plt.close(self.alltabdata[opentab]["ProcessorFig"])

            #closing tab
            self.tabWidget.removeTab(indextoclose)

            #removing current tab data from the self.alltabdata dict, correcting tabnumbers variable
            self.alltabdata.pop(indextoclose)
            self.tabIDs.pop(indextoclose)

    except Exception:
        trace_error()
        self.posterror("Failed to close the current tab")
        
        
        
#warning message
@staticmethod
def postwarning(warningtext):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setText(warningtext)
    msg.setWindowTitle("Warning")
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()
    
    
    
#error message
@staticmethod
def posterror(errortext):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setText(errortext)
    msg.setWindowTitle("Error")
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()
    
    

#warning message with options (Okay or Cancel)
@staticmethod
def postwarning_option(warningtext):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setText(warningtext)
    msg.setWindowTitle("Warning")
    msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    outval = msg.exec_()
    option = 'unknown'
    if outval == 1024:
        option = 'okay'
    elif outval == 4194304:
        option = 'cancel'
    return option

    
    
#add warning message before closing GUI
def closeEvent(self, event):
    reply = QMessageBox.question(self, 'Message',
        "Are you sure to close the application? \n All unsaved work will be lost!", QMessageBox.Yes | 
        QMessageBox.No, QMessageBox.No)
    if reply == QMessageBox.Yes:

        if self.preferencesopened:
            self.settingsthread.close()

        #explicitly closing figures to clean up memory (should be redundant here but just in case)
        for ctab,_ in enumerate(self.alltabdata):
            if self.alltabdata[ctab]["tabtype"][:2] == "PE":
                plt.close(self.alltabdata[ctab]["ProfFig"])
                plt.close(self.alltabdata[ctab]["LocFig"])

            elif self.alltabdata[ctab]["tabtype"][:3] == 'DAS':
                plt.close(self.alltabdata[ctab]["ProcessorFig"])

                #aborting all threads
                if self.alltabdata[ctab]["isprocessing"]:
                    self.alltabdata[ctab]["processor"].abort()

        event.accept()
        # delete all temporary files
        allfilesanddirs = listdir(self.systempdir)
        for cfile in allfilesanddirs:
            if len(cfile) >= 5:
                cfilestart = cfile[:4]
                cfileext = cfile[-3:]
                if (cfilestart.lower() == 'temp' and cfileext.lower() == 'wav') or (cfilestart.lower() == 'sigd' and cfileext.lower() == 'txt'):
                    remove(self.systempdir + slash + cfile)
    else:
        event.ignore() 

                
        
        
        
        
        
#class to customize nagivation toolbar in profile editor tab
class CustomToolbar(NavigationToolbar):
    def __init__(self,canvas_,parent_):
        self.toolitems = (
            ('Home', 'Reset Original View', 'home', 'home'),
            ('Back', 'Go To Previous View', 'back', 'back'),
            ('Forward', 'Return to Next View', 'forward', 'forward'),
            (None, None, None, None),
            ('Pan', 'Click and Drag to Pan', 'move', 'pan'),
            ('Zoom', 'Select Region to Zoon', 'zoom_to_rect', 'zoom'),)
        NavigationToolbar.__init__(self,canvas_,parent_)
        
        
        
        

# =============================================================================
#    PARSE STRING INPUTS/CHECK VALIDITY WHEN TRANSITIONING TO PROFILE EDITOR
# =============================================================================
def parsestringinputs(self,latstr,lonstr,profdatestr,timestr,identifier,checkcoords,checktime,checkid):
    isgood = True
    lon = np.NaN
    lat = np.NaN
    dropdatetime = dt.datetime(1,1,1)
    identifier = 'none'
    
    try:
        #parsing and checking data
        if checkcoords:
            try:
                #checking latitude validity
                latstr = latstr.split(',')
                latsign = np.sign(float(latstr[0]))
                if len(latstr) == 3:
                    lat = float(latstr[0]) + latsign*float(latstr[1])/60 + latsign*float(latstr[2])/3600
                elif len(latstr) == 2:
                    lat = float(latstr[0]) + latsign*float(latstr[1])/60
                else:
                    lat = float(latstr[0])
            except:
                self.postwarning('Invalid Latitude Entered!')
                isgood = False

            try:
                #checking longitude validity
                lonstr = lonstr.split(',')
                lonsign = np.sign(float(lonstr[0]))
                if len(lonstr) == 3:
                    lon = float(lonstr[0]) + lonsign*float(lonstr[1])/60 + lonsign*float(lonstr[2])/3600
                elif len(lonstr) == 2:
                    lon = float(lonstr[0]) + lonsign*float(lonstr[1])/60
                else:
                    lon = float(lonstr[0])
            except:
                self.postwarning('Invalid Longitude Entered!')
                isgood = False

            if lon < -180 or lon > 180:
                self.postwarning('Longitude must be between -180 and 180')
                isgood = False
            elif lat < -90 or lat > 90:
                self.postwarning('Latitude must be between -90 and 90')
                isgood = False

            lon = round(lon,3)
            lat = round(lat,3)



        if checktime: #checking time
            if len(timestr) != 4:
                self.postwarning('Invalid Time Format (must be HHMM)!')
                isgood = False
            elif len(profdatestr) != 8:
                self.postwarning('Invalid Date Format (must be YYYYMMDD)!')
                isgood = False

            try: #checking date
                year = int(profdatestr[:4])
                month = int(profdatestr[4:6])
                day = int(profdatestr[6:])
            except:
                self.postwarning('Invalid (non-numeric) Date Entered!')
                isgood = False
            try:
                hour = int(timestr[:2])
                minute = int(timestr[2:4])
            except:
                self.postwarning('Invalid (non-numeric) Time Entered!')
                isgood = False

            if year < 1938 or year > 3000: #year the bathythermograph was invented and the year by which it was probably made obsolete
                self.postwarning('Invalid Year Entered (< 1938 AD or > 3000 AD)!')
                isgood = False
            elif month <= 0 or month > 12:
                self.postwarning("Invalid Month Entered (must be between 1 and 12)")
                isgood = False
            elif hour > 23 or hour < 0:
                self.postwarning('Invalid Time Entered (hour must be between 0 and 23')
                isgood = False
            elif minute >= 60 or minute < 0:
                self.postwarning('Invalid Time Entered (minute must be between 0 and 59')
                isgood = False
            
            #figuring out number of days in month   
            monthnames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'] 
            if month in [1,3,5,7,8,10,12]:
                maxdays = 31
            elif month in [4,6,9,11]:
                maxdays = 30
            elif month == 2 and year%4 == 0:
                maxdays = 29
            elif month == 2:
                maxdays = 28
            else:
                maxdays = 31
                isgood = False
                self.postwarning('Invalid month entered!')
                
            #checking to make sure days are in valid range
            if isgood and (day <= 0 or day > maxdays):
                self.postwarning(f"Invalid Day Entered (must be between 1 and {maxdays} for {monthnames[month-1]})")
                isgood = False
            
            #getting datetime for drop
            if isgood:
                dropdatetime = dt.datetime(year,month,day,hour,minute,0)

                #making sure the profile is within 12 hours and not in the future, warning if otherwise
                curtime = timemodule.gmtime()
                deltat = dt.datetime(curtime[0],curtime[1],curtime[2],curtime[3],curtime[4],curtime[5]) - dropdatetime
                option = ''
                if self.settingsdict["dtgwarn"]:
                    if deltat.days < 0:
                        option = self.postwarning_option("Drop time appears to be after the current time. Continue anyways?")
                    elif deltat.days > 1 or (deltat.days == 0 and deltat.seconds > 12*3600):
                        option = self.postwarning_option("Drop time appears to be more than 12 hours ago. Continue anyways?")
                    if option == 'cancel':
                        isgood = False
                        

        #check length of identifier
        if checkid and len(identifier) != 5:
            option = self.postwarning_option("Identifier is not 5 characters! Continue anyways?")
            if option == 'cancel':
                isgood = False
        
    except Exception:
        trace_error()
        self.posterror("Unspecified error in parsing profile information!")
        isgood = False
    
    finally:
        return isgood, lat, lon, dropdatetime, identifier
        
            
        
    
    
    

# =============================================================================
#                       SAVING FILES FOR DATA IN OPEN TAB
# =============================================================================            
        
            
#save data in open tab        
def savedataincurtab(self):
    
    opentab = self.whatTab()
    successval = True #changes to False if error is raised
    
    #pulling probe type to determine what data to access
    #this will be 'unknown' if the tab hasn't been processed but another check will prevent the function from trying to save a profile from an unprocessed tab
    probetype = self.alltabdata[opentab]["probetype"]
    
    #getting directory to save files from QFileDialog
    try:
        outdir = str(QFileDialog.getExistingDirectory(self, "Select Directory to Save File(s)",self.defaultfilewritedir,QFileDialog.DontUseNativeDialog))
        
        if outdir == '': #checking directory validity
            QApplication.restoreOverrideCursor()
            return False
        else:
            self.defaultfilewritedir = outdir
    except Exception:
        trace_error()
        self.posterror("Error raised in directory selection")
        return False

        
    #saving files depending on tab type, switching cursor to loading option
    try:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        if self.alltabdata[opentab]["tabtype"] == "PE_p":
            self.savePEfiles(opentab,outdir,probetype)
        elif self.alltabdata[opentab]["tabtype"] == "DAS_p":
            if self.alltabdata[opentab]["isprocessing"]:
                self.postwarning('You must stop processing the current tab before saving data!')
            else:
                self.saveDASfiles(opentab,outdir,probetype)
        else:
            self.postwarning('You must process a profile before attempting to save data!')
            
    except Exception:
        QApplication.restoreOverrideCursor() #restore cursor here as extra measure
        trace_error() #if something else in the file save code broke
        self.posterror("Failed to save files")
        successval = False #notes that process failed
    finally:
        QApplication.restoreOverrideCursor() #restore cursor here
        self.alltabdata[opentab]["profileSaved"] = True #note that profile has been saved
    
    if successval: #removing asterisk from tab title since file was saved
        self.alltabdata[opentab]["profileSaved"] = True
        self.remove_asterisk(opentab)
        
    return successval
    

    
    
#check filename for existing files with same header (avoid overwriting)
def check_filename(self,originalfilenameheader):
    new_file_num = 0
    pathname, originalfilename = path.split(originalfilenameheader) #split into file header and file path
    filename = originalfilename
    fileheadersindir = [cf.split('.')[0] for cf in listdir(pathname)] #returns file headers (not inc. extension)
    while any([filename == cf for cf in fileheadersindir]):
        new_file_num += 1
        filename = f"{originalfilenameheader}_{new_file_num}"
    
    return pathname + self.slash + filename
    
    
    
    
    
    
#save files from DAS in specified tab
def saveDASfiles(self,opentab,outdir,probetype):
    
    if probetype.upper() == 'AXCTD':
        hasSal = True
        rawdata = {'depth':self.alltabdata[opentab]["rawdata"]["depth"], 'temperature': self.alltabdata[opentab]["rawdata"]["temperature"], 'salinity':self.alltabdata[opentab]["rawdata"]["salinity"]}
        edf_data = {'Time (s)': self.alltabdata[opentab]["rawdata"]["time"], 'Frame (hex)': self.alltabdata[opentab]["rawdata"]["frame"], 'Depth (m)':self.alltabdata[opentab]["rawdata"]["depth"],'Temperature (degC)':self.alltabdata[opentab]["rawdata"]["temperature"],'Conductivity (mS/cm)':self.alltabdata[opentab]["rawdata"]["conductivity"], 'Salinity (PSU)':self.alltabdata[opentab]["rawdata"]["Salinity"]}
        zcoeff = self.settingsdict["zcoeff_axctd"]
        tcoeff = self.settingsdict["tcoeff_axctd"]
        ccoeff = self.settingsdict["ccoeff_axctd"]
        edf_comments = f"""Probe Type       :  AXCTD
    Terminal Depth   :  850 m
    Depth Coeff. 1   :  {zcoeff[0]}
    Depth Coeff. 2   :  {zcoeff[1]}
    Depth Coeff. 3   :  {zcoeff[2]}
    Depth Coeff. 4   :  {zcoeff[3]}
    Pressure Pt Correction:  N/A
    Temp. Coeff. 1   :  {tcoeff[0]}
    Temp. Coeff. 2   :  {tcoeff[1]}
    Temp. Coeff. 3   :  {tcoeff[2]}
    Temp. Coeff. 4   :  {tcoeff[3]}
    Cond. Coeff. 1   :  {ccoeff[0]}
    Cond. Coeff. 2   :  {ccoeff[1]}
    Cond. Coeff. 3   :  {ccoeff[2]}
    Cond. Coeff. 4   :  {ccoeff[3]}"""
    
    else:
        hasSal = False
        rawdata = {'depth':self.alltabdata[opentab]["rawdata"]["depth"], 'temperature':self.alltabdata[opentab]["rawdata"]["temperature"], 'salinity':None}
        edf_data = {'Time (s)': self.alltabdata[opentab]["rawdata"]["time"], 'Frequency (Hz):': self.alltabdata[opentab]["rawdata"]["frequency"], 'Depth (m)':self.alltabdata[opentab]["rawdata"]["depth"],'Temperature (degC)':self.alltabdata[opentab]["rawdata"]["temperature"]}
        zcoeff = self.settingsdict["zcoeff_axbt"]
        tcoeff = self.settingsdict["tcoeff_axbt"]
        edf_comments = f"""Probe Type       :  AXBT
    Terminal Depth   :  850 m
    Depth Coeff. 1   :  {zcoeff[0]}
    Depth Coeff. 2   :  {zcoeff[1]}
    Depth Coeff. 3   :  {zcoeff[2]}
    Depth Coeff. 4   :  {zcoeff[3]}
    Pressure Pt Correction:  N/A
    Temp. Coeff. 1   :  {tcoeff[0]}
    Temp. Coeff. 2   :  {tcoeff[1]}
    Temp. Coeff. 3   :  {tcoeff[2]}
    Temp. Coeff. 4   :  {tcoeff[3]}"""


    # pulling data from inputs
    latstr = self.alltabdata[opentab]["tabwidgets"]["latedit"].text()
    lonstr = self.alltabdata[opentab]["tabwidgets"]["lonedit"].text()
    profdatestr = self.alltabdata[opentab]["tabwidgets"]["dateedit"].text()
    timestr = self.alltabdata[opentab]["tabwidgets"]["timeedit"].text()
    
    #parse inputs to valid data (ignore identifier)
    isgood, lat, lon, dropdatetime, _ = self.parsestringinputs(latstr, lonstr, profdatestr, timestr, 'no-ID', True, True, False)
        
    #creating file header to save, taking care not to overwrite files and note if good position/time exists
    if not isgood:
        goodmetadata = False
        csavedtg = dt.datetime.strftime(dt.datetime.utcnow(),'%Y%m%d%H%M')
        filename = self.check_filename(outdir + self.slash + f"output_savedAt_{csavedtg}")
        self.postwarning("Bad date/time or position: cannot save NVO or EDF files if requested!")
    else:
        goodmetadata = True
        filename = self.check_filename(outdir + self.slash + dt.datetime.strftime(dropdatetime,'%Y%m%d%H%M'))
        
    
    if self.settingsdict["savenvo_raw"] and goodmetadata:
        try:
            io.writefinfile(filename+'.nvo', dropdatetime, lat, lon, 99, rawdata['depth'], rawdata['temperature'], salinity=rawdata['salinity'])
        except Exception:
            trace_error()
            self.posterror("Failed to save NVO file")
            
    if self.settingsdict["saveedf_raw"] and goodmetadata:
        try:
            #creating comment for data source and VHF channel/frequency (if applicable) used
            cdatasource = self.alltabdata[opentab]["tabwidgets"]["datasource"].currentText()
            edf_comments += "\n//Data source: " + cdatasource
            if cdatasource.lower() not in ["audio","test"]:
                edf_comments += f", VHF Ch. {self.alltabdata[opentab]['tabwidgets']['vhfchannel'].value()} ({self.alltabdata[opentab]['tabwidgets']['vhffreq'].value()} MHz)"
                
            io.writeedffile(filename+'.edf', dropdatetime, lat, lon, edf_data, edf_comments, QC=False)
        except Exception:
            trace_error()
            self.posterror("Failed to save EDF file")

    if self.settingsdict["savewav_raw"]:
        try:
            oldfile = self.tempdir + slash + 'tempwav_' + str(self.alltabdata[opentab]["tabnum"]) + '.WAV'
            newfile = filename + '.WAV'
            
            copyfile = True
            if path.exists(oldfile) and path.exists(newfile) and oldfile != newfile: #if file already exists
                option = self.postwarning_option(f"{newfile} already exists- overwrite?")
                if option == 'okay':
                    remove(newfile)
                else:
                    copyfile = False
            elif not path.exists(oldfile):
                copyfile = False
                self.postwarning(f'Unable to save WAV file: {oldfile} not found')
            if copyfile:
                shcopy(oldfile,newfile)
            
        except Exception:
            trace_error()
            self.posterror("Failed to save WAV file")

    if self.settingsdict["savesig_raw"]:
        try:
            oldfile = self.tempdir + slash + 'sigdata_' + str(self.alltabdata[opentab]["tabnum"]) + '.txt'
            newfile = filename + '.sigdata'
            
            print(oldfile)
            print(newfile)
            print(self.tempdir)
            
            copyfile = True
            if path.exists(oldfile) and path.exists(newfile) and oldfile != newfile: #if file already exists
                option = self.postwarning_option(f"{newfile} already exists- overwrite?")
                if option == 'okay':
                    remove(newfile)
                else:
                    copyfile = False
            elif not path.exists(oldfile):
                copyfile = False
                self.postwarning(f'Unable to save signal data file: {oldfile} not found')
            if copyfile:
                shcopy(oldfile,newfile)

        except Exception:
            trace_error()
            self.posterror("Failed to save signal data file")
        
        
        
        
#save files in profile editor tab
def savePEfiles(self,opentab,outdir,probetype):
    
    if probetype.upper() == 'AXCTD':
        hasSal = True
    else:
        hasSal = False
    
    #profile metadata
    dropdatetime = self.alltabdata[opentab]["profdata"]["dropdatetime"]
    lat = self.alltabdata[opentab]["profdata"]["lat"]
    lon = self.alltabdata[opentab]["profdata"]["lon"]
    identifier = self.alltabdata[opentab]["profdata"]["ID"]
    
    #temperature/depth data
    rawdepth = self.alltabdata[opentab]["profdata"]["depth_raw"]
    rawtemperature = self.alltabdata[opentab]["profdata"]["temperature_raw"]
    climodepthfill = self.alltabdata[opentab]["profdata"]["climodepthfill"]
    climotempfill = self.alltabdata[opentab]["profdata"]["climotempfill"]
    depthT = self.alltabdata[opentab]["profdata"]["depthT_plot"]
    temperature = self.alltabdata[opentab]["profdata"]["temperature_plot"]
    depth1m = np.arange(0,np.floor(depthT[-1]))
    temperature1m = np.interp(depth1m,depthT,temperature)
    
    #pulling salinity data if AXCTD
    if hasSal:
        rawsalinity = self.alltabdata[opentab]["profdata"]["salinity_raw"]
        climopsalfill = self.alltabdata[opentab]["profdata"]["climotempfill"]
        depthS = self.alltabdata[opentab]["profdata"]["depthS_plot"]
        salinity = self.alltabdata[opentab]["profdata"]["salinity_plot"]
        salinity1m = np.interp(depth1m,depth,salinity)
        edf_data = {'Depth (m)':depth1m, 'Temperature (degC)':temperature1m, 'Salinity (PSU)':salinity1m}
    else:
        salinity = None
        salinity1m = None
        edf_data = {'Depth (m)':depth1m, 'Temperature (degC)':temperature1m}
        
    ocean_depth = self.alltabdata[opentab]["profdata"]['oceandepth']
    isbtmstrike = self.alltabdata[opentab]["tabwidgets"]["isbottomstrike"].isChecked()
    if isbtmstrike:
        btmstrikestr = 'yes'
    else:
        btmstrikestr = 'no'
    if self.alltabdata[opentab]["profdata"]["matchclimo"]:
        match_climo_string = 'yes'
    else:
        match_climo_string = 'no'
    rcnum = self.alltabdata[opentab]["tabwidgets"]["rcode"].currentIndex()
    edf_comments = f"""Probe Type       :  {probetype}
// Ocean depth at drop position: {ocean_depth:6.1f} m
// Bottom strike? {btmstrikestr} 
// Climatology match? {match_climo_string}
// QC Code: {rcnum} ({self.reason_code_strings[rcnum]})
// Data interpolated to 1-meter interval"""
    
    dtg = dt.datetime.strftime(dropdatetime,'%Y%m%d%H%M')
    filename = self.check_filename(outdir + self.slash + dtg)
    
    if self.settingsdict["saveedf_qc"]:
        try:
            io.writeedffile(filename+'.edf', dropdatetime, lat, lon, edf_data, edf_comments, QC=True)
        except Exception:
            trace_error()
            self.posterror("Failed to save EDF file")
    
    if self.settingsdict["savefin_qc"]:
        try:
            writefinfile(filename+'.fin', dropdatetime, lat, lon, 99, depth=depth1m, temperature=temperature1m, salinity=salinity1m)
        except Exception:
            trace_error()
            self.posterror("Failed to save FIN file")
            
    if self.settingsdict["savejjvv_qc"]:
        try:
            io.writejjvvfile(filename+'.jjvv',temperature, depthT, dropdatetime, lat, lon, identifier, isbtmstrike)
        except Exception:
            trace_error()
            self.posterror("Failed to save JJVV file")
            
    if self.settingsdict["savebufr_qc"]:
        try:
            io.writebufrfile(filename+'.bufr', dropdatetime, lon, lat, identifier, self.settingsdict["originatingcenter"], depth=depth1m, temperature=temperature1m, salinity=salinity1m)
        except Exception:
            trace_error()
            self.posterror("Failed to save BUFR file")
            
    if self.settingsdict["saveprof_qc"]:
        try:
            #initializing both figures first so they will exist/can be closed if plotting code throws an error
            figT = plt.figure() 
            figS = plt.figure()
            
            if self.settingsdict["overlayclimo"]:
                matchclimo = self.alltabdata[opentab]["profdata"]["matchclimo"]
            else:
                matchclimo = 1
                
            figT.clear()
            axT = figT.add_axes([0.1,0.1,0.85,0.85])
            climohandleT = profplot.makeprofileplot(axT, rawtemperature, rawdepth, temperature, depthT, dtg, climodatafill=climotempfill, climodepthfill=climodepthfill, datacolor='r', datalabel = 'Temperature ($^\circ$C)', matchclimo=matchclimo, axlimtype=0)
            if self.settingsdict["overlayclimo"] == 0:
                climohandleT.set_visible(False)
            figT.savefig(filename+'_prof_temp.png',format='png')
            
            if hasSal:
                figS.clear()
                axS = figS.add_axes([0.1,0.1,0.85,0.85])
                climohandleS = profplot.makeprofileplot(axS, rawsalinity, rawdepth, salinity, depthS, dtg, climodatafill=climopsalfill, climodepthfill=climodepthfill, datacolor='g', datalabel = 'Salinity (PSU)', matchclimo=matchclimo, axlimtype=0)
                if self.settingsdict["overlayclimo"] == 0:
                    climohandleS.set_visible(False)
                figS.savefig(filename+'_prof_psal.png',format='png')
                
        except Exception:
            trace_error()
            self.posterror("Failed to save profile image")
        finally:
            plt.close('figT')
            plt.close('figS')

    if self.settingsdict["saveloc_qc"]:
        try:
            figL = plt.figure()
            figL.clear()
            axL = figL.add_axes([0.1,0.1,0.85,0.85])
            _,exportlat,exportlon,exportrelief = oci.getoceandepth(lat,lon,6,self.bathymetrydata)
            profplot.makelocationplot(figL, axL, lat, lon, dtg, exportlon, exportlat, exportrelief, 6)
            fig2.savefig(filename + '_loc.png',format='png')
        except Exception:
            trace_error()
            self.posterror("Failed to save location image")
        finally:
            plt.close('figL')
                    
            