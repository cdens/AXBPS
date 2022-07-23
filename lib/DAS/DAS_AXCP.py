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


import numpy as np
from scipy import signal

from PyQt5.QtCore import pyqtSlot #run slot
from PyQt5.Qt import QRunnable #base for Processor class

import time as timemodule
import datetime as dt

from traceback import print_exc as trace_error

import lib.DAS.common_DAS_functions as cdf

import lib.DAS.geomag_axbps as gm





class AXCPProcessor(QRunnable):
    
    #importing methods common to all AXBT/AXCTD/AXCP processing threads
    from ._processor_functions import (initialize_common_vars, wait_to_run, kill, killaudiorecording, abort, changecurrentfrequency, changethresholds, update_settings)
    from ._DAS_callbacks import define_callbacks
    
    #importing AXCP specific functions
    from ._AXCP_decode_fxns import (init_AXCP_settings, initialize_AXCP_vars, init_fft_window, dofft, init_filters, init_constants, first_subsample, second_subsample, calc_current_datapoint, iterate_AXCP_process, refine_spindown_prof, calculate_true_velocities)
    from ._AXCP_convert_fxns import (calc_temp_from_freq, calc_vel_components, calc_currents)
    
    #kill: terminates the thread and emits an error message if necessary
    #killaudiorecording: stops appending PCM data to the audio file (if the file is too large)
    #abort: pyqtslot for the GUI (user STOP button) to terminate the process
    #changecurrentfrequency: slot for the user to switch the VHF channel being demodulated/processed (receiver threads only- not audio/test threads)
    #changethresholds- pyqtslot that changes the settings for the processor if a user adjusts the settings while a thread is active
    #update_settings- updates the settings from an input dict to the processor thread, called during initialization and when changethresholds is called
    

    #initializing current thread (saving variables, reading audio data or contacting/configuring receiver)
    #AXBT settings: fftwindow, minfftratio, minsiglev, triggerfftratio, triggersiglev, tcoeff, zcoeff, flims
    def __init__(self, dll, datasource, vhffreq, tabID, starttime=dt.datetime.utcnow(), status=0, triggertime=-1, lat=20, lon=-80, dropdate=dt.date.today(), settings={}, tempdir='', *args, **kwargs):
        
        super(AXCPProcessor, self).__init__()

        #prevents Run() method from starting before init is finished (value must be changed to 100 at end of __init__)
        self.threadstatus = 0
        
        self.probetype = "AXCP"
        
        self.processing_active = False #this is true whenever a chunk of data is being processed
        self.lock_processing = False #change this to true to pause data processing
        
        #AXCP specific variables
        self.starttime = starttime
        self.triggertime = triggertime
        
        self.status = status
        
        #updating position, magnetic field components/declination
        self.gm = gm.GeoMag(wmm_filename= 'lib/DAS/WMM.COF') #this must be initialized first
        self.update_position(lat, lon, dropdate)
        
        
        #initializing non probe-specific variables and accessing receiver or opening audio file
        self.initialize_common_vars(tempdir,tabID,dll,settings,datasource,vhffreq,'AXCP')
        
        #initialize default settings, override user-specified ones
        self.init_AXCP_settings(settings)     
        
        #initializing AXCP processor specific vars, as well as filter and conversion coefficients and output profile arrays
        self.initialize_AXCP_vars()
        
        #connecting signals to thread
        self.signals = cdf.ProcessorSignals()
        
                
        if self.threadstatus: 
            self.keepgoing = False
        else: #if it's still 0, intialization was successful
            self.threadstatus = 100 #send signal to start running data acquisition thread
            
            
            
    def update_position(self, lat, lon, dropdate):
        self.lat = lat
        self.lon = lon
        self.dropdate = dropdate
        self.magvar = self.gm.get_params(dlat=self.lat, dlon=self.lon, time=self.dropdate)
        self.fh = self.magvar.bh #always positive
        self.fz = -self.magvar.bz #switches convention so positive is up
        self.dec = self.magvar.dec #positive is East
            
            
    def update_position_profile(self,lat,lon,dropdate ): #TODO- pyqt slot
        while self.processing_active: #wait for current segment to finish
            timemodule.sleep(0.1)
        self.lock_processing = True #prevent AXCP DAS from processing new chunks of data until this is complete
        
        self.update_position(lat,lon,dropdate) #updates position/date, mag parameters
        self.initialize_AXCP_vars() #needed to recalculate magvar related parameters
        
        #reprocesses profile U and V (mag/true) from mag params
        self.reprocess_profdata()
        
        self.signals.emit_profile_update.emit(self.tabID, [self.U_MAG, self.V_MAG, self.U_TRUE, self.V_TRUE]) #sends all profile info back to main slot
        
        timemodule.sleep(0.2) #make the DAS wait for the GUI to receive/update the profiles 
        self.lock_processing = False #prevent AXCP DAS from processing new chunks of data until this is complete
        
        
    #reprocessing U and V with updated position/time/magnetic parameters
    def reprocess_profdata(self):
        
        self.U_MAG = np.array([])
        self.V_MAG = np.array([])
        self.VERR = np.array([])
        self.AREA = np.array([])
        self.AERR = np.array([])
        for (rotfavg, fccr, fefr, vc0a, vc0p, ve0a, ve0p, gcca, gefa, nindep, w) in zip(self.ROTF, self.FCCR, self.FEFR, self.VC0A, self.VC0P, self.VE0A, self.VE0P, self.GCCA, self.GEFA, self.NINDEP, self.W):
            area, aerr, umag, vmag, verr = self.calc_currents(self, rotfavg, fccr, fefr, vc0a, vc0p, ve0a, ve0p, gcca, gefa, nindep, w)
                
            self.U_MAG = np.append(self.U_MAG, umag)
            self.V_MAG = np.append(self.V_MAG, vmag)
            self.VERR = np.append(self.VERR, verr)
            self.AREA = np.append(self.AREA, area)
            self.AERR = np.append(self.AERR, aerr)
                
        self.U_TRUE, self.V_TRUE = self.calculate_true_velocities(self.U_MAG, self.V_MAG)
        
    
    #this function is called by self.kill(), which is called any time the profile stops processing:
    #   for errors, when the user hits stop, when an audio file reaches its end, or when realtime spindown
    #   detect identifies that the probe has spun down and auto-stops processing (AXCP specific)
    #after finishing entire profile, refine the spindown point, correct amean, and adjust the profile
    def on_axcp_terminate(self):
        if self.tspinup >= 0 and len(self.TIME) > 0: #spinup detected, valid profile points recorded
            self.refine_spindown_prof()            
        
    @pyqtSlot()
    def run(self):
        
        #waits for self.threadstatus to change to 100 (indicating __init__ finished) before proceeding
        self.wait_to_run()
        
        #defining radio receiver callbacks within scope with access to self variable
        receiver_callback = self.define_callbacks("AXCP", self.sourcetype)
        
        #writing basic info about source to sigdata file
        if self.isfromaudio or self.isfromtest:
            cursource = self.audiofile
        else:
            cursource = self.serial
        self.txtfile.write(f"AXCP Processor initialized : source={self.sourcetype} ({cursource}), fs={self.f_s} Hz\n")

        
        try:
            
            #Declaring the callbuck function to update the audio buffer (importing from DAS_callbacks)
            if self.sourcetype == 'WR': #callback for winradio
                # from lib.DAS._DAS_callbacks import wr_axctd_callback as updateaudiobuffer
                
                # initializes audio callback function
                status = cdf.initialize_receiver_callback(self.dll, self.sourcetype, self.hradio, receiver_callback, self.tabID)
                if status:
                    timemodule.sleep(0.3)  # gives the buffer time to populate
                else:
                    self.kill(7)
    
                    
            elif self.isfromaudio or self.isfromtest: #if source is an audio file
                #configuring sample times for the audio file
                self.lensignal = len(self.audiostream)
                self.maxtime = self.lensignal/self.f_s
                
                
                
            # setting up thread while loop- terminates when user clicks "STOP" or audio file finishes processing
            i = -1
            
            self.status = 0
            
            #initialize self.demodbufferstartind
            self.demodbufferstartind = 0
            if not self.isfromaudio: #can stop/restart test or realtime processing tabs only (not audio)
                self.demodbufferstartind = int(self.f_s * (dt.datetime.utcnow()-self.starttime).total_seconds())
                #start index is based on current time for realtime/test
                
            #MAIN PROCESSOR LOOP
            while self.keepgoing:
                
                if not self.lock_processing:
                    
                    self.processing_active = True
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
                            
                        #pulling data from audio buffer
                        lenbuffer = len(self.audiostream)
                        if lenbuffer >= self.minpointsperloop:
                            self.demod_buffer = np.append(self.demod_buffer, self.audiostream[:lenbuffer])
                            del self.audiostream[:lenbuffer] #pull data from receiver buffer to demodulation buffer, remove data from head of receiver buffer
                            e = self.demodbufferstartind + lenbuffer #won't use the entire array
                        else:
                            e = self.demodbufferstartind #start index = end index, causes processor to skip this iteration and add more points to the buffer
                        
                        
                        
                    else:
                        #kill test/audio threads once time exceeds the max time of the audio file
                        #NOTE: need to do this on the cycle before hitting the max time when processing from audio because the WAV file processes faster than the thread can kill itself
                        
                        #calculating end of next slice of PCM data for signal level calcuation and demodulation
                        e = self.demodbufferstartind + self.minpointsperloop
                        
                        if self.numpoints - self.demodbufferstartind < self.minpointsperloop: #kill process at file end
                            self.kill(0)
                        
                        elif e >= self.numpoints: #terminate loop if at end of file
                            e = self.numpoints - 1
                            
                        
                        #updates progress every iteration
                        if self.isfromaudio:
                            self.signals.updateprogress.emit(self.tabID, int(self.demodbufferstartind / self.numpoints * 100))
                        
                        #add next round of PCM data to buffer for signal calculation and demodulation
                        # self.demod_buffer = np.append(self.demod_buffer, self.audiostream[self.demodbufferstartind:e])
                        self.demod_buffer = self.audiostream[self.demodbufferstartind:e]
                        
    
                        
                    
                    if e >= self.demodbufferstartind + self.minpointsperloop and self.keepgoing: #only process buffer if there is enough data
                    
                        
                        #demodulating and parsing current batch of AXCTD PCM data
                        oldstatus = self.status
                        data = self.iterate_AXCP_process(e)
                        if self.status and not oldstatus: #profile collection triggered
                            #release signal indicating probe triggered
                            self.signals.triggered.emit(self.tabID, self.status, self.tspinup)
                        
                        
                        #won't send if keepgoing stopped since current iteration began
                        if self.keepgoing and len(data) > 0: 
                            self.signals.iterated.emit(self.tabID, data) #updating data in GUI loop
                                
                        #increment demod buffer index forward
                        self.demodbufferstartind = e 
                        
                self.processing_active = False
                
                #sleeping until ready to process more data (sleep length is datasource-dependent)
                if self.isfromtest: #sleep until real time catches up to number of demodulated points
                    ctimeinaudio = self.demodbufferstartind/self.f_s
                    while (dt.datetime.utcnow() - self.starttime).total_seconds() < ctimeinaudio:
                        timemodule.sleep(0.01)
                elif self.isfromaudio: 
                    timemodule.sleep(0.001) #slight pause to free some resources when processing from audio
                else: 
                    timemodule.sleep(0.1) #realtime processing- wait 0.1 sec for buffer to refill
                    

        except Exception: #if the thread encounters an error, terminate
            trace_error()  # if there is an error, terminates processing
            if self.keepgoing:
                self.kill(10)
                
        while self.waittoterminate: #waits for kill process to complete to avoid race conditions with audio buffer callback
            timemodule.sleep(0.1)
            
        


    