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

import numpy as np

from PyQt5.QtCore import pyqtSlot #run slot
from PyQt5.Qt import QRunnable #base for Processor class

import time as timemodule
import datetime as dt

from traceback import print_exc as trace_error

import lib.DAS.common_DAS_functions as cdf




class AXCTDProcessor(QRunnable):
    
    #importing methods common to all AXBT/AXCTD processing threads
    from ._processor_functions import (initialize_common_vars, wait_to_run, kill, killaudiorecording, abort, changecurrentfrequency, changethresholds, update_settings)
    #kill: terminates the thread and emits an error message if necessary
    #killaudiorecording: stops appending PCM data to the audio file (if the file is too large)
    #abort: pyqtslot for the GUI (user STOP button) to terminate the process
    #changecurrentfrequency: slot for the user to switch the VHF channel being demodulated/processed (receiver threads only- not audio/test threads)
    #changethresholds- pyqtslot that changes the settings for the processor if a user adjusts the settings while a thread is active
    #update_settings- updates the settings from an input dict to the processor thread, called during initialization and when changethresholds is called
    

    #initializing current thread (saving variables, reading audio data or contacting/configuring receiver)
    #AXBT settings: fftwindow, minfftratio, minsiglev, triggerfftratio, triggersiglev, tcoeff, zcoeff, flims
    def __init__(self, dll, datasource, vhffreq, tabID, starttime, triggerstatus, firstpointtime, firstpulsetime,
        settings, slash, tempdir, *args,**kwargs):
        super(AXCTDProcessor, self).__init__()

        #prevents Run() method from starting before init is finished (value must be changed to 100 at end of __init__)
        self.threadstatus = 0
        
        #AXCTD specific variables
        self.starttime = starttime
        self.firstpointtime = firstpointtime
        self.firstpulsetime = firstpulsetime
        
        if firstpointtime > 0:
            self.triggerstatus = 2
        elif firstpulsetime > 0:
            self.triggerstatus = 1
        else:
            self.triggerstatus = 0 #0=nothing, 1 = 400 Hz pulses, 2 = 7.5kHz tone
        
        self.linesperquartersec = 6
        
        self.f = open('data/testdata/AXCTD_sample.axctd_debug')
                
        #initializing non probe-specific variables and accessing receiver or opening audio file
        self.initialize_common_vars(tempdir,slash,tabID,dll,settings,datasource)
        
        #connecting signals to thread
        self.signals = cdf.ProcessorSignals()
                
        if self.threadstatus: 
            self.keepgoing = False
        else: #if it's still 0, intialization was successful
            self.threadstatus = 100 #send signal to start running data acquisition thread
            
            
            
    @pyqtSlot()
    def run(self):
        
        #waits for self.threadstatus to change to 100 (indicating __init__ finished) before proceeding
        self.wait_to_run()

        
        try:
            
            #Declaring the callbuck function to update the audio buffer (importing from DAS_callbacks)
            if self.sourcetype == 'WR': #callback for winradio
                from lib.DAS._DAS_callbacks import wr_axctd_callback as updateaudiobuffer
                
                # initializes audio callback function
                status = initialize_receiver_callback(rtype, hradio, destination, tabID)
                if status:
                    timemodule.sleep(0.3)  # gives the buffer time to populate
                else:
                    self.kill(7)
    
                    
            else: #if source is an audio file
                #configuring sample times for the audio file
                self.lensignal = len(self.audiostream)
                self.maxtime = self.lensignal/self.f_s
                    
                
            # setting up thread while loop- terminates when user clicks "STOP" or audio file finishes processing
            i = -1
            ctime = 0
                
            #MAIN PROCESSOR LOOP
            while self.keepgoing:
                i += 1


                if not self.isfromaudio and not self.isfromtest:

                    #protocal to kill thread if connection with WiNRADIO is lost
                    if self.numcontacts == self.lastcontacts: #checks if the audio stream is receiving new data
                        self.disconnectcount += 1
                    else:
                        self.disconnectcount = 0
                        self.lastcontacts = self.numcontacts

                    #if the audio stream hasn't received new data for several iterations and checking device connection fails
                    if self.disconnectcount >= 30 and not cdf.check_connected(self.dll, self.sourcetype, self.hradio):
                        self.kill(8)
                        
                    #TODO: WHAT CURRENT DATA TO PULL
                    
                else:
                    #TODO: UPDATE BUFFER OVERFLOW PREVENTION FOR AXCTD/PULL FROM AXCTDPROCESSOR
                    #kill test/audio threads once time exceeds the max time of the audio file
                    #NOTE: need to do this on the cycle before hitting the max time when processing from audio because the WAV file processes faster than the thread can kill itself
                    # if (self.isfromtest and ctime >= self.maxtime - self.settings["fftwindow"]) or (self.isfromaudio and i >= len(self.sampletimes)-1):
                    #     self.keepgoing = False
                    #     self.kill(0)
                    #     return
                        
                    # #getting current time to sample from audio file
                    # if self.isfromaudio:
                    #     ctime += self.maxtime/1000 #TODO: FIX
                    #     if i % 10 == 0: #updates progress every 10 data points
                    #         self.signals.updateprogress.emit(self.tabID,int(ctime / self.maxtime * 100))

                    #TODO: WHAT CURRENT DATA TO PULL
                    

                #TODO: SIGNAL CALCULATIONS, DEMODULATE DATA
                
                #TODO: DETERMINE IF VALID SIGNAL RECEIVED YET (modify triggerstatus)
                
                
                if self.triggerstatus:
                    pass

                    #TODO: UPDATE FOR AXCTD
                    #writing raw data to sigdata file (ASCII) for current thread
                    # if self.keepgoing: #only writes if thread hasn't been stopped since start of current segment
                        # self.txtfile.write(f"{ctime},{fp},{Sp},{Rp}\n")
                        
                        
                    #TODO: frame parsing here: return ctimes, cdepths, ctemps, cconds (rounded to 2 decimal places)
                    
                    
                    
                    
                    
    
                #UPDATE DATA TO EMIT
                if self.triggerstatus == 2:
                    data = [self.triggerstatus, ctimes, r400, r7500, cdepths, ctemps, cconds, cframes]
                
                elif len(ctimes) > 0: #triggerstatus is 1 (400 Hz pulses transmitting but 7500 Hz profile tone not detected)
                    data = [self.triggerstatus, [ctimes[-1]], [r400[-1]], [r7500[-1]], [np.NaN], [np.NaN], [np.NaN], [cframes[-1]]]
                else:
                    data = [] #dont pass any info
                
                    
                #TODO: ADD TRIGGERED SIGNAL RELEASE WITH NECESSARY TIMES
                    
                if self.keepgoing and len(data) > 0: #won't send if keepgoing stopped since current iteration began
                self.signals.iterated.emit(self.tabID, data)
                        
                        
                        
                        
                        
                if not self.isfromaudio: 
                    timemodule.sleep(0.1)  #pauses when processing in realtime (fs ~ 10 Hz)
                else:
                    timemodule.sleep(0.001) #slight pause to free some resources when processing from audio

        except Exception: #if the thread encounters an error, terminate
            trace_error()  # if there is an error, terminates processing
            if self.keepgoing:
                self.kill(10)
                
        while self.waittoterminate: #waits for kill process to complete to avoid race conditions with audio buffer callback
            timemodule.sleep(0.1)
            
            
        

        
        


    