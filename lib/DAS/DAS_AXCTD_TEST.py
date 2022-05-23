
# =============================================================================
#   THIS IS A TEST FILE USED TO DEVELOP THE AXCTD GUI SLOTS/TRIGGERS. IT DOES
#   NOT PROCESS ACTUAL AXCTD AUDIO DATA
# =============================================================================



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
            
                
            # setting up thread while loop- terminates when user clicks "STOP" or audio file finishes processing
            i = -1
            ctime = 0
            
            oldtriggerstatus = self.triggerstatus
            
            #MAIN PROCESSOR LOOP
            while self.keepgoing:
                
                #READ LINES FROM TEST AXCTD DEBUG FILE
                r400 = []
                r7500 = []
                ctimes = []
                cdepths = []
                ctemps = []
                cconds = []
                for _ in range(self.linesperquartersec):
                    cline = self.f.readline().strip().split()
                    if len(cline) < 6:
                        self.f.close()
                        break
                    else:
                        
                        i += 1
                        
                        if len(cline) <= 10:
                            if cline[1] == "000000":
                                self.triggerstatus = 0
                            elif cline[1] == "ffffff":
                                self.triggerstatus = 1 
                        else:
                            if cline[9] != '//':
                                self.triggerstatus = 2
                            else:
                                self.triggerstatus = 1
                        
                        
                        ctimes.append(np.round(i/24,2))
                        if self.triggerstatus <= 1:
                            cdepths.append(np.NaN)
                            ctemps.append(np.NaN)
                            cconds.append(np.NaN)
                            if self.triggerstatus == 0:
                                r400.append(0.93)
                                r7500.append(0.97)
                        if self.triggerstatus >= 1:
                            r400.append(2.23)
                            r7500.append(1.78)
                            if self.triggerstatus == 2:
                                cdepths.append(np.round(float(cline[12]),2))
                                ctemps.append(np.round(float(cline[17]),2))
                                cconds.append(np.round(float(cline[20]),2))                          
                            
                        if oldtriggerstatus != self.triggerstatus:
                            if self.triggerstatus == 1:
                                self.firstpulsetime = ctimes[-1]
                            elif self.triggerstatus == 2:
                                self.firstpointtime = ctimes[-1]
                                
                            self.signals.triggered.emit(self.tabID, self.triggerstatus, ctimes[-1])
                            oldtriggerstatus = self.triggerstatus
    
                        #TODO: WHAT CURRENT DATA TO PULL
                        #r400, r7500, ctimes, cdepths, ctemps, cconds, triggersatus
                        #r400 threshold is 2.0, r7500 threshold is 1.5

                    
                    
                    
                #TODO: SIGNAL CALCULATIONS, DEMODULATE DATA
                
                #TODO: DETERMINE IF VALID SIGNAL RECEIVED YET (modify triggerstatus) **returns r400, r7500
                # if oldtriggerstatus != self.triggerstatus:
                #     self.signals.triggered.emit(self.tabID, self.triggerstatus, ctriggertime)
                
                if self.triggerstatus:
                    pass

                    #TODO: UPDATE FOR AXCTD
                    #writing raw data to sigdata file (ASCII) for current thread
                    # if self.keepgoing: #only writes if thread hasn't been stopped since start of current segment
                        # self.txtfile.write(f"{ctime},{fp},{Sp},{Rp}\n")
                        
                    #TODO: frame parsing here: return ctimes, cdepths, ctemps, cconds (rounded to 2 decimal places)
                    #update triggerstatus
                
                
                #UPDATE DATA TO EMIT
                if self.triggerstatus == 2:
                    cframe = [self.triggerstatus, ctimes, r400, r7500, cdepths, ctemps, cconds]
                
                elif len(ctimes) > 0: #triggerstatus is 1 (400 Hz pulses transmitting but 7500 Hz profile tone not detected)
                    cframe = [self.triggerstatus, [ctimes[-1]], [r400[-1]], [r7500[-1]], [np.NaN], [np.NaN], [np.NaN]]
                else:
                    cframe = [] #dont pass any info
                
                    
                #TODO: ADD TRIGGERED SIGNAL RELEASE WITH NECESSARY TIMES
                    
                if self.keepgoing and len(cframe) > 0: #won't send if keepgoing stopped since current iteration began
                    self.signals.iterated.emit(self.tabID, cframe)

                    
                timemodule.sleep(0.22)  #every iteration for test should take a quarter second
                    
                    
            #outside while loop
            self.f.close()

        except Exception: #if the thread encounters an error, terminate
            trace_error()  # if there is an error, terminates processing
            if self.keepgoing:
                self.kill(10)
                self.f.close()
                
        while self.waittoterminate: #waits for kill process to complete to avoid race conditions with audio buffer callback
            timemodule.sleep(0.1)
            
            
        

        
        


    