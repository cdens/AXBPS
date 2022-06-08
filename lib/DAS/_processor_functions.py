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

# This file contains functions that are common to the processor threads for all
# types of expendable floats. Functions here handle basic tasks like initizlizing 
# radio receivers, opening audio files, initializing common variables and stopping
# the processing thread.
#
# The functions in this file are all methods of AXBTProcessor/AXCTDProcessor/etc. thread
# classes, any functions that are not methods in those classes go in common_DAS_functions.py
# instead, except for radio receiver-specific functions which go in either DAS_callback.py 
# (if it is a callback function to update the audio PCM data buffer for the thread) or 
# a separate radio reciver file e.g. winradio_functions.py, which is called by the radio receiver
# methods in common_DAS_functions.py


import numpy as np
import wave #WAV file writing

from PyQt5.QtCore import pyqtSlot

import time as timemodule

from traceback import print_exc as trace_error

from shutil import copy as shcopy

import lib.DAS.common_DAS_functions as cdf




        
# =============================================================================
#         INITIALIZES VARIABLES, ACTIVATES RECEIVER OR OPENS AUDIO FILE
# =============================================================================        
        
#initialize variables common to all DAS tabs (AXCTD,AXBT,etc)
def initialize_common_vars(self,tempdir,slash,tabID,dll,settings,datasource,vhffreq,probetype):
    
    self.common_vars_init = False #prevents AXCTD settings update function from running until necessary variables are initialized
    self.probetype = probetype
    
    self.dll = dll # saves DLL/API library
    self.tabID = tabID #keeps track of which tab in GUI this thread corresponds to
    
    self.keepgoing = True  # signal connections
    self.waittoterminate = False #whether to pause on termination of run loop for kill process to complete
    
    #settings
    self.settings = {}
    self.update_settings(settings)

    #output file names
    self.txtfilename = tempdir + slash + "sigdata_" + str(self.tabID) + '.txt'
    self.txtfile = open(self.txtfilename, 'w')
    self.wavfilename = tempdir + slash +  "tempwav_" + str(self.tabID) + '.WAV'
    
    #to prevent ARES from consuming all computer's resources- this limits the size of WAV files used by the signal processor to a number of PCM datapoints corresponding to 1 hour of audio @ fs=64 kHz, that would produce a wav file of ~0.5 GB for 16-bit PCM data
    self.maxsavedframes = 2.5E8
    self.isrecordingaudio = True #initialized to True for all cases (RF, test, and audio) but only matters in the callback function assigned for RF receivers

    # identifying whether tab is audio, test, or other format
    self.isfromaudio = False
    self.isfromtest = False
    
    self.audiofile = 'none' #replaced with path to WAV file if used
    self.serial = 'none' #replaced with radio receiver identifier if used
    
    #initializing variables to check if receiver remains connected (unused for audio/test threads)
    self.disconnectcount = 0
    self.numcontacts = 0
    self.lastcontacts = 0
    self.nframes = 0
    
    self.sourcetype = datasource[:2] #AA for audio, TT for test, other two characters for receiver types
    
    if self.sourcetype == 'AA': #source is audio file
        self.chselect = int(datasource[2:7])
        self.audiofile = datasource[7:]
        self.isfromaudio = True
        
    elif self.sourcetype == 'TT': #test run- use included audio file
        self.chselect = 0 #sum over multiple channels
        if probetype == 'AXBT':
            self.audiofile = 'data/testdata/AXBT_sample.WAV'
        elif probetype == 'AXCTD':
            self.audiofile = 'data/testdata/AXCTD_sample.WAV'
        self.isfromtest = True
    
    
    if self.isfromtest or self.isfromaudio: #either way, data comes from test file
        self.audiostream, self.f_s, self.threadstatus = cdf.read_audio_file(self.audiofile, self.chselect, self.maxsavedframes)
        shcopy(self.audiofile, self.wavfilename) #copying audio file if datasource = Test or Audio
        
    else: #thread is to be connected to a radio receiver
    
        #pull receiver serial number, activate current receiver/establish contact
        self.serial = datasource[2:]
        self.hradio, self.threadstatus = cdf.activate_receiver(self.dll,self.sourcetype,self.serial,vhffreq)
        
        # initialize audio stream data variables
        self.fs = cdf.get_fs(self.dll, self.sourcetype) #f_s depends on type of receiver connected
        self.audiostream = [0] * 2 * self.f_s #initializes the buffer with 2 seconds of zeros

        #setup WAV file to write (if audio or test, source file is copied instead)
        self.wavfile = wave.open(self.wavfilename,'wb')
        wave.Wave_write.setnchannels(self.wavfile,1)
        wave.Wave_write.setsampwidth(self.wavfile,2)
        wave.Wave_write.setframerate(self.wavfile,self.f_s)
        wave.Wave_write.writeframes(self.wavfile,bytearray(self.audiostream))
    
        
    
    self.common_vars_init = True
    
        
        
def wait_to_run(self):
    #barrier to prevent signal processor loop from starting before __init__ finishes
    counts = 0
    while self.threadstatus != 100:
        counts += 1
        if counts > 100 or not self.keepgoing: #give up and terminate after 10 seconds waiting for __init__
            self.kill(12)
            return
        elif self.threadstatus != 0 and self.threadstatus != 100: #if the audio file couldn't be read in properly
            self.kill(self.threadstatus) #waits to run kill commands due to errors raised in __init__ until run() since slots+signals may not be connected to parent thread during init
            return
        timemodule.sleep(0.1)
        #if the Run() method gets this far, __init__ has completed successfully (and set self.threadstatus = 100)


# =============================================================================
#         OTHER COMMON METHODS USED BY PROCESSOR
# =============================================================================    


def kill(self,reason): #stop current thread
    #NOTE: function contains 0.3 seconds of sleep to prevent race conditions between the processor loop, callback function and main GUI event loop
    try:
        self.waittoterminate = True #keeps run method from terminating until kill process completes
        self.keepgoing = False  # kills while loop
        tabID = self.tabID
        
        timemodule.sleep(0.3) #gives thread 0.1 seconds to finish current segment
        
        if reason != 0: #notify event loop that processor failed if non-zero exit code provided
            self.signals.failed.emit(self.tabID, reason)
        
        self.isrecordingaudio = False
        if not self.isfromaudio and not self.isfromtest:
            cdf.stop_receiver(self.dll,self.sourcetype,self.hradio)
            wave.Wave_write.close(self.wavfile)
            
        self.signals.terminated.emit(tabID)  # emits signal that processor has been terminated
        self.txtfile.close()
        
    except Exception:
        trace_error()
        self.signals.failed.emit(self.tabID, 10)
        
    self.waittoterminate = False #allow run method to terminate
    
    
#terminate the audio file recording (for WINRADIO processor tabs) if it exceeds a certain length set by maxframenum
def killaudiorecording(self):
    try:
        self.isrecordingaudio = False
        wave.Wave_write.close(self.wavfile) #close WAV file
        self.signals.failed.emit(self.tabID, 13) #pass warning message back to GUI
    except Exception:
        trace_error()
        self.kill(10)
    
    
@pyqtSlot()
def abort(self): #executed when user selects "Stop" button (passed via pyqtSlot)
    self.kill(0) #tell processor to terminate with 0 (success) exit code
    
    
@pyqtSlot(float) #called from the DAS GUI via a pyqtSlot
def changecurrentfrequency(self, newfreq): #update VHF frequency for radio receiver
    # change frequency- kill if failed
    try:
        status = self.change_receiver_freq(self.dll,self.sourcetype,self.hradio,newfreq)
        if not status:
            self.kill(4)
            
    except Exception:
        trace_error()
        self.kill(4)
        

@pyqtSlot(dict)
def changethresholds(self, settings): #update data thresholds for FFT
    self.update_settings(settings)  
    
    
#updating the settings for the current tab: this will write all settings sent from AXBPS to the DAS processor, which are defined by the settingstopull variable in gui/_DASfunctions.py
def update_settings(self,settings):
    for key in settings.keys(): 
        self.settings[key] = settings[key]
    if "fftwindow" in settings.keys(): #limit FFT window setting to 1 second
        self.settings['fftwindow'] = np.min([self.settings['fftwindow'], 1])
    if self.probetype == 'AXCTD' and self.common_vars_init:
        self.load_AXCTD_settings() #refresh variables for all AXCTD settings
    
    
    
    
    