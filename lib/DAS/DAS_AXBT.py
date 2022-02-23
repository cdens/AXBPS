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
from scipy.signal import tukey #taper generation (AXBT-specific)

from PyQt5.QtCore import pyqtSlot #run slot
from PyQt5.Qt import QRunnable #base for Processor class

import time as timemodule
import datetime as dt

from traceback import print_exc as trace_error

import lib.DAS.common_DAS_functions as cdf




class AXBTProcessor(QRunnable):
    
    #importing methods common to all AXBT/AXCTD processing threads
    from ._processor_functions import (intialize_common_vars, wait_to_run, kill, killaudiorecording, abort, changecurrentfrequency, changethresholds, update_settings)
    #kill: terminates the thread and emits an error message if necessary
    #killaudiorecording: stops appending PCM data to the audio file (if the file is too large)
    #abort: pyqtslot for the GUI (user STOP button) to terminate the process
    #changecurrentfrequency: slot for the user to switch the VHF channel being demodulated/processed (receiver threads only- not audio/test threads)
    #changethresholds- pyqtslot that changes the settings for the processor if a user adjusts the settings while a thread is active
    #update_settings- updates the settings from an input dict to the processor thread, called during initialization and when changethresholds is called
    

    #initializing current thread (saving variables, reading audio data or contacting/configuring receiver)
    #AXBT settings: fftwindow, minfftratio, minsiglev, triggerfftratio, triggersiglev, tcoeff, zcoeff, flims
    def __init__(self, dll, datasource, vhffreq, tabID, starttime, istriggered, firstpointtime, 
        settings, slash, tempdir, *args,**kwargs):
        super(ThreadProcessor, self).__init__()

        #prevents Run() method from starting before init is finished (value must be changed to 100 at end of __init__)
        self.threadstatus = 0
        
        #AXBT specific variables
        self.starttime = starttime
        self.istriggered = istriggered
        self.firstpointtime = firstpointtime
        
        #initializing variables for taper and frequencies for FFT
        self.taper = []
        self.freqs = []
        
        #initializing non probe-specific variables and accessing receiver or opening audio file
        self.initialize_common_vars(self,tempdir,slash,tabID,dll)
        
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
                from lib.DAS._DAS_callbacks import wr_axbt_callback as updateaudiobuffer
                
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
                self.sampletimes = np.arange(0.1,self.maxtime-0.1,0.1)
    
                
            # setting up thread while loop- terminates when user clicks "STOP" or audio file finishes processing
            i = -1
                
            #MAIN PROCESSOR LOOP
            while self.keepgoing:
                i += 1

                # finds time from profile start in seconds
                curtime = dt.datetime.utcnow()  # current time
                deltat = curtime - self.starttime
                ctime = deltat.total_seconds()

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

                    # listens to current frequency, gets sound level, set audio stream, and corresponding time
                    currentdata = self.audiostream[-int(self.f_s * self.settings["fftwindow"]):]
                    
                else:
                    #kill test/audio threads once time exceeds the max time of the audio file
                    #NOTE: need to do this on the cycle before hitting the max time when processing from audio because the WAV file processes faster than the thread can kill itself
                    if (self.isfromtest and ctime >= self.maxtime - self.settings["fftwindow"]) or (self.isfromaudio and i >= len(self.sampletimes)-1):
                        self.keepgoing = False
                        self.kill(0)
                        return
                        
                    #getting current time to sample from audio file
                    if self.isfromaudio:
                        ctime = self.sampletimes[i]
                        if i % 10 == 0: #updates progress every 10 data points
                            self.signals.updateprogress.emit(self.tabID,int(ctime / self.maxtime * 100))

                    #getting current data to sample from audio file- using indices like this is much more efficient than calculating times and using logical arrays
                    ctrind = int(np.round(ctime*self.f_s))
                    pmind = int(np.min([np.round(self.f_s*self.settings["fftwindow"]/2),ctrind,self.lensignal-ctrind-1])) #uses minimum value so no overflow
                    currentdata = self.audiostream[ctrind-pmind:ctrind+pmind]
                    

                #identifying peak frequence + signal level/SNR from current PCM chunk
                fp,Sp,Rp = self.dofft(currentdata)        
        
                #rounding before comparisons happen
                ctime = np.round(ctime, 1)
                fp = np.round(fp, 2)
                Sp = np.round(Sp, 2)
                Rp = np.round(Rp, 3)        
                

                #writing raw data to sigdata file (ASCII) for current thread- before correcting for minratio/minsiglev
                if self.keepgoing: #only writes if thread hasn't been stopped since start of current segment
                    self.txtfile.write(f"{ctime},{fp},{Sp},{Rp}\n")
                    
                #logic to determine whether or not profile is triggered
                if not self.istriggered and Sp >= self.settings["triggersiglev"] and Rp >= self.settings["triggerfftratio"]:
                    self.istriggered = True
                    self.firstpointtime = ctime
                    if self.keepgoing: #won't send if keepgoing stopped since current iteration began
                        self.signals.triggered.emit(self.tabID, 1, ctime) 
                        
                #logic to determine whether or not point is valid
                if self.istriggered and Sp >= self.settings["minsiglev"] and Rp >= self.settings["minfftratio"]:
                    cdepth = cdf.dataconvert(ctime - self.firstpointtime, self.settings["zcoeff"])
                    ctemp = cdf.dataconvert(fp, self.settings["tcoeff"])
                
                else:
                    fp = 0
                    ctemp = cdepth = np.NaN
                

                # tells GUI to update data structure, plot, and table
                ctemp = np.round(ctemp, 2)
                cdepth = np.round(cdepth, 1)
                if self.keepgoing: #won't send if keepgoing stopped since current iteration began
                    self.signals.iterated.emit(self.tabID, [ctemp, cdepth, fp, Sp, np.round(100*Rp,1), ctime, i])

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
            
            
    #run fft on a chunk of AXBT PCM data, determine peak frequency/signal level/ratio
    def dofft(self, pcmdata):
        
        N = len(pcmdata)
        
        # apply taper- alpha=0.25
        if len(self.taper) != N: #rebuild if different length of data included
            taper = tukey(len(pcmdata), alpha=0.25)
        pcmdata = taper * pcmdata
    
        # calculating fft, converting to power
        fftdata = np.abs(np.fft.fft(pcmdata))
    
        #building corresponding frequency array
        if len(self.freqs) != N: #rebuild if different length of data included
            T = N/self.fs
            df = 1 / T
            self.freqs = np.array([df * n if n < N / 2 else df * (n - N) for n in range(N)])
    
        #constraining peak frequency options to frequencies in specified band
        ind = np.all((np.greater_equal(self.freqs, self.settings["flims"][0]), np.less_equal(self.freqs,self.settings["flims"][1])), axis=0)
        self.freqs = self.freqs[ind]
        
        #frequency of max signal within band (AXBT-transmitted frequency)
        fp = self.freqs[np.argmax(fftdata[ind])] 
        
        #maximum signal strength in band
        Sp = 10*np.log10(np.max(fftdata[ind]))
    
        #ratio of maximum signal in band to max signal total (SNR)
        Rp = np.max(fftdata[ind])/np.max(fftdata) 
            
        return fp, Sp, Rp
    
        

        
        


    