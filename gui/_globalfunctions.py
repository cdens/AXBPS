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

import lib.fileinteraction as tfio
import lib.make_profile_plots as tplot
import lib.ocean_climatology_interaction as oci




    
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
        
        
        
            
#save data in open tab        
def savedataincurtab(self):
    
    successval = True #changes to False if error is raised
    
    try:
        #getting directory to save files from QFileDialog
        try:
            outdir = str(QFileDialog.getExistingDirectory(self, "Select Directory to Save File(s)",self.defaultfilewritedir,QFileDialog.DontUseNativeDialog))
        except Exception:
            trace_error()
            return False
                            
        #checking directory validity
        if outdir == '':
            QApplication.restoreOverrideCursor()
            return False
        else:
            self.defaultfilewritedir = outdir
                            
    except:
        self.posterror("Error raised in directory selection")
        return

    try:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        #pulling all relevant data
        opentab = self.whatTab()
        
        if self.alltabdata[opentab]["tabtype"] == "PE_p":
            try:
                rawtemperature = self.alltabdata[opentab]["profdata"]["temp_raw"]
                rawdepth = self.alltabdata[opentab]["profdata"]["depth_raw"]
                climotempfill = self.alltabdata[opentab]["profdata"]["climotempfill"]
                climodepthfill = self.alltabdata[opentab]["profdata"]["climodepthfill"]
                temperature = self.alltabdata[opentab]["profdata"]["temp_plot"]
                depth = self.alltabdata[opentab]["profdata"]["depth_plot"]
                day = self.alltabdata[opentab]["profdata"]["day"]
                month = self.alltabdata[opentab]["profdata"]["month"]
                year = self.alltabdata[opentab]["profdata"]["year"]
                time = self.alltabdata[opentab]["profdata"]["time"]
                lat = self.alltabdata[opentab]["profdata"]["lat"]
                lon = self.alltabdata[opentab]["profdata"]["lon"]
                identifier = self.alltabdata[opentab]["profdata"]["ID"]
                num = 99 #placeholder- dont have drop number here currently!!
                
                dtg = str(year) + str(month).zfill(2) + str(day).zfill(2) + str(time).zfill(4)
                curtab = self.tabWidget.currentIndex()
                filename = self.check_filename(dtg)
                
                if self.settingsdict["overlayclimo"]:
                    matchclimo = self.alltabdata[opentab]["profdata"]["matchclimo"]
                else:
                    matchclimo = 1

            except:
                self.posterror("Failed to retrieve profile information")
                QApplication.restoreOverrideCursor()
                return False

            if self.settingsdict["savefin"]:
                try:
                    depth1m = np.arange(0,np.floor(depth[-1]))
                    temperature1m = np.interp(depth1m,depth,temperature)
                    tfio.writefinfile(outdir + slash + filename + '.fin',temperature1m,depth1m,day,month,year,time,lat,lon,num)
                except Exception:
                    trace_error()
                    self.posterror("Failed to save FIN file")
            if self.settingsdict["savejjvv"]:
                isbtmstrike = self.alltabdata[opentab]["tabwidgets"]["isbottomstrike"].isChecked()
                try:
                    tfio.writejjvvfile(outdir + slash + filename + '.jjvv', temperature, depth, day, month, year, time, lat, lon, identifier, isbtmstrike)
                except Exception:
                    trace_error()
                    self.posterror("Failed to save JJVV file")
            if self.settingsdict["savebufr"]:
                try:
                    tfio.writebufrfile(outdir + slash + filename + '.bufr',temperature,depth,year,month,day,time,lon,lat,identifier,self.settingsdict["originatingcenter"],False,b'\0')
                except Exception:
                    trace_error()
                    self.posterror("Failed to save BUFR file")
            if self.settingsdict["saveprof"]:
                try:
                    fig1 = plt.figure()
                    fig1.clear()
                    ax1 = fig1.add_axes([0.1,0.1,0.85,0.85])
                    climohandle = tplot.makeprofileplot(ax1,rawtemperature,rawdepth,temperature,depth,climotempfill,climodepthfill,dtg,matchclimo)
                    if self.settingsdict["overlayclimo"] == 0:
                        climohandle.set_visible(False)
                    fig1.savefig(outdir + slash + filename + '_prof.png',format='png')
                except Exception:
                    trace_error()
                    self.posterror("Failed to save profile image")
                finally:
                    plt.close('fig1')

            if self.settingsdict["saveloc"]:
                try:
                    fig2 = plt.figure()
                    fig2.clear()
                    ax2 = fig2.add_axes([0.1,0.1,0.85,0.85])
                    _,exportlat,exportlon,exportrelief = oci.getoceandepth(lat,lon,6,self.bathymetrydata)
                    tplot.makelocationplot(fig2,ax2,lat,lon,dtg,exportlon,exportlat,exportrelief,6)
                    fig2.savefig(outdir + slash + filename + '_loc.png',format='png')
                except Exception:
                    trace_error()
                    self.posterror("Failed to save location image")
                finally:
                    plt.close('fig2')

                
        elif self.alltabdata[opentab]["tabtype"] == "DAS_p":
            
            if self.alltabdata[opentab]["isprocessing"]:
                self.postwarning('You must stop processing the current tab before saving data!')

            else:

                try:
                    #pulling prof data
                    rawtemperature = self.alltabdata[opentab]["rawdata"]["temperature"]
                    rawdepth = self.alltabdata[opentab]["rawdata"]["depth"]
                    frequency = self.alltabdata[opentab]["rawdata"]["frequency"]
                    timefromstart = self.alltabdata[opentab]["rawdata"]["time"]

                    #pulling profile metadata if necessary
                    try:
                        lat = self.alltabdata[opentab]["rawdata"]["lat"]
                        lon = self.alltabdata[opentab]["rawdata"]["lon"]
                        year = self.alltabdata[opentab]["rawdata"]["year"]
                        month = self.alltabdata[opentab]["rawdata"]["month"]
                        day = self.alltabdata[opentab]["rawdata"]["day"]
                        time = self.alltabdata[opentab]["rawdata"]["droptime"]
                        hour = self.alltabdata[opentab]["rawdata"]["hour"]
                        minute = self.alltabdata[opentab]["rawdata"]["minute"]
                    except:
                        # pulling data from inputs
                        latstr = self.alltabdata[opentab]["tabwidgets"]["latedit"].text()
                        lonstr = self.alltabdata[opentab]["tabwidgets"]["lonedit"].text()
                        profdatestr = self.alltabdata[opentab]["tabwidgets"]["dateedit"].text()
                        timestr = self.alltabdata[opentab]["tabwidgets"]["timeedit"].text()
    
                        
                        #flags for capability of saving data
                        edfcapable = True
                        logcapable = True
                        wavcapable = True
                        sigcapable = True
                        
                        #check validity of data
                        #try edf data
                        try:
                            lat, lon, year, month, day, time, hour, minute, _ = self.parsestringinputs(latstr, lonstr,profdatestr,timestr, 'omit', True, True, False)
                        except:
                            edfcapable = False
                            self.postwarning('Cannot save edf file!')
                        #try other data
                        try:
                            _, _, year, month, day, time, hour, minute, _ = self.parsestringinputs(latstr, lonstr,profdatestr,timestr, 'omit', False, True, False)
                        except:
                            logcapable = False, 
                            wavcapable = False
                            sigcapable = False
                            self.postwarning("Failed to save raw data files!")
                            QApplication.restoreOverrideCursor()
                    
                except Exception:
                    trace_error()
                    self.posterror("Failed to pull raw profile data")
                    QApplication.restoreOverrideCursor()
                    return False

                #date and time strings for LOG file
                initdatestr = str(year) + '/' + str(month).zfill(2) + '/' + str(day).zfill(2)
                inittimestr = str(hour).zfill(2) + ':' + str(minute).zfill(2) + ':00'
                
                filename = self.check_filename(str(year) + str(month).zfill(2) + str(day).zfill(2) + str(time).zfill(4))


                
                if self.settingsdict["savelog"] and logcapable:
                    try:
                        tfio.writelogfile(outdir + slash + filename + '.DTA',initdatestr,inittimestr,timefromstart,rawdepth,frequency,rawtemperature)
                    except Exception:
                        trace_error()
                        self.posterror("Failed to save LOG file")
                if self.settingsdict["saveedf"] and edfcapable:
                    try:
                        #creating comment for data source:
                        cdatasource = self.alltabdata[opentab]["tabwidgets"]["datasource"].currentText()
                        comments = "//Data source: " + cdatasource
                        if cdatasource.lower() not in ["audio","test"]:
                            comments += f", VHF Ch. {self.alltabdata[opentab]['tabwidgets']['vhfchannel'].value()} ({self.alltabdata[opentab]['tabwidgets']['vhffreq'].value()} MHz)"
                        tfio.writeedffile(outdir + slash + filename + '.edf',rawtemperature,rawdepth,year,month,day,hour,minute,0,lat,lon, self.settingsdict["tcoeff"], self.settingsdict["zcoeff"],comments) #lat/lon only parsed if self.settingsdict["saveedf"] is True
                    except Exception:
                        trace_error()
                        self.posterror("Failed to save EDF file")

                if self.settingsdict["savewav"] and wavcapable:
                    try:
                        oldfile = self.tempdir + slash + 'tempwav_' + str(self.alltabdata[opentab]["tabnum"]) + '.WAV'
                        newfile = outdir + slash + filename + '.WAV'

                        if path.exists(oldfile) and path.exists(newfile) and oldfile != newfile: #if file already exists
                            remove(newfile)

                        shcopy(oldfile,newfile)
                    except Exception:
                        trace_error()
                        self.posterror("Failed to save WAV file")

                if self.settingsdict["savesig"] and sigcapable:
                    try:
                        oldfile = self.tempdir + slash + 'sigdata_' + str(self.alltabdata[opentab]["tabnum"]) + '.txt'
                        newfile = outdir + slash + filename + '.sigdata'

                        if path.exists(oldfile) and path.exists(newfile) and oldfile != newfile:
                            remove(newfile)

                        shcopy(oldfile, newfile)
                    except Exception:
                        trace_error()
        
        elif self.alltabdata[opentab]["tabtype"] == "MissionPlotter":
            filename = str(self.tabWidget.tabText(self.tabWidget.currentIndex())) #filename is name of tab
            self.alltabdata[opentab]["MissionFig"].savefig(outdir + slash + filename + '.png',format='png')
        
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
    
    if successval:
        self.alltabdata[opentab]["profileSaved"] = True
        self.remove_asterisk(opentab)
        
    return successval
    

    
#check filename for existing file (avoid overwriting)
def check_filename(self,originalfilename):
    new_file_num = 0
    filename = originalfilename
    while path.exists(filename):
        new_file_num += 1
        filename = f"{originalfilename}_{new_file_num}"
    
    return filename

        
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

        
        

# =============================================================================
#    PARSE STRING INPUTS/CHECK VALIDITY WHEN TRANSITIONING TO PROFILE EDITOR
# =============================================================================
def parsestringinputs(self,latstr,lonstr,profdatestr,timestr,identifier,checkcoords,checktime, checkid):
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
                return

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
                return

            if lon < -180 or lon > 180:
                self.postwarning('Longitude must be between -180 and 180')
            elif lat < -90 or lat > 90:
                self.postwarning('Latitude must be between -90 and 90')

            lon = round(lon,3)
            lat = round(lat,3)

        else:
            lon = np.NaN
            lat = np.NaN


        if checktime: #checking time
            if len(timestr) != 4:
                self.postwarning('Invalid Time Format (must be HHMM)!')
                return
            elif len(profdatestr) != 8:
                self.postwarning('Invalid Date Format (must be YYYYMMDD)!')
                return

            try: #checking date
                year = int(profdatestr[:4])
                month = int(profdatestr[4:6])
                day = int(profdatestr[6:])
            except:
                self.postwarning('Invalid (non-numeric) Date Entered!')
                return
            try:
                time = int(timestr)
                hour = int(timestr[:2])
                minute = int(timestr[2:4])
            except:
                self.postwarning('Invalid (non-numeric) Time Entered!')
                return

            if year < 1938 or year > 3000: #year the bathythermograph was invented and the year by which it was probably made obsolete
                self.postwarning('Invalid Year Entered (< 1938 AD or > 3000 AD)!')
                return
            elif month <= 0 or month > 12:
                self.postwarning("Invalid Month Entered (must be between 1 and 12)")
                return
            elif hour > 23 or hour < 0:
                self.postwarning('Invalid Time Entered (hour must be between 0 and 23')
                return
            elif minute >= 60 or minute < 0:
                self.postwarning('Invalid Time Entered (minute must be between 0 and 59')
                return
            
            #figuring out number of days in month   
            monthnames = ['January','February','March','April','May','June','July','August','September','October','November','December'] 
            if month in [1,3,5,7,8,10,12]:
                maxdays = 31
            elif month in [4,6,9,11]:
                maxdays = 30
            elif month == 2 and year%4 == 0:
                maxdays = 29
            elif month == 2:
                maxdays = 28
            else:
                self.postwarning('Invalid month entered!')
                
            #checking to make sure days are in valid range
            if day <= 0 or day > maxdays:
                self.postwarning(f"Invalid Day Entered (must be between 1 and {maxdays} for {monthnames[month-1]})")
                return
            

            #making sure the profile is within 12 hours and not in the future, warning if otherwise
            curtime = timemodule.gmtime()
            deltat = dt.datetime(curtime[0],curtime[1],curtime[2],curtime[3],curtime[4],curtime[5]) - dt.datetime(year,month,day,hour,minute,0)
            option = ''
            if self.settingsdict["dtgwarn"]:
                if deltat.days < 0:
                    option = self.postwarning_option("Drop time appears to be after the current time. Continue anyways?")
                elif deltat.days > 1 or (deltat.days == 0 and deltat.seconds > 12*3600):
                    option = self.postwarning_option("Drop time appears to be more than 12 hours ago. Continue anyways?")
                if option == 'cancel':
                    return
        else:
            year = np.NaN
            month = np.NaN
            day = np.NaN
            time = np.NaN
            hour = np.NaN
            minute = np.NaN

        #check length of identifier
        if checkid and len(identifier) != 5:
            option = self.postwarning_option("Identifier is not 5 characters! Continue anyways?")
            if option == 'cancel':
                return

        return lat,lon,year,month,day,time,hour,minute,identifier
    except Exception:
        trace_error()
        self.posterror("Unspecified error in reading profile information!")
        return
            
        
        
        
        
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
            
            
            
            