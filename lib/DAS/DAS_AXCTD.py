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

import lib.DAS.demodulate as demodulate
import lib.DAS.parseAXCTD as parse




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
        settings, slash, tempdir, minR400=2.0, mindR7500=1.5, deadfreq=3000, minpointsperloop=22050, triggerrange=[30,-1], mark_space_freqs=[400,800], bitrate=800, bit_inset=1, phase_error=25, use_bandpass=False, *args,**kwargs):
        
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
                
        #initializing non probe-specific variables and accessing receiver or opening audio file
        self.initialize_common_vars(tempdir,slash,tabID,dll,settings,datasource,'AXCTD')
        
        #initializing AXCTD processor specific vars
        self.initialize_AXCTD_vars(minR400, mindR7500, deadfreq, minpointsperloop, triggerrange, mark_space_freqs, bitrate, bit_inset, phase_error, use_bandpass)
        
        #connecting signals to thread
        self.signals = cdf.ProcessorSignals()
                
        if self.threadstatus: 
            self.keepgoing = False
        else: #if it's still 0, intialization was successful
            self.threadstatus = 100 #send signal to start running data acquisition thread
            
            
            
    def initialize_AXCTD_vars(self,minR400, mindR7500, deadfreq, minpointsperloop, triggerrange, mark_space_freqs, bitrate, bit_inset, phase_error, use_bandpass):
        #prevents Run() method from starting before init is finished (value must be changed to 100 at end of __init__)        
        self.keepgoing = True  # signal connections
        self.waittoterminate = False #whether to pause on termination of run loop for kill process to complete
        
        self.audiofile = audiofile
        
        self.minR400 = minR400 #threshold to ID first 400 Hz pulse
        self.mindR7500 = mindR7500 #threshold to ID profile start by 7.5 kHz tone
        self.deadfreq = deadfreq #frequency to use as "data-less" control to normalize signal levels
        self.minpointsperloop = minpointsperloop #how many PCM datapoints AXCTDprocessor handles per loop
        
        #index 0: earliest time AXBT will trigger after 400 Hz pulse in seconds (default 30 sec)
        #index 1: time AXCTD will autotrigger without 7.5kHz signal (set to -1 to never trigger profile)
        self.triggerrange = triggerrange
        
        self.past_headers = False #when false, program may try to read header data
        self.header1_read = False #notes when each header has been successfully read, to stop trying
        self.header2_read = False
        self.header3_read = False
        
        #temperature lookup table, calibration coefficients
        self.metadata = parse.initialize_axctd_metadata()
        self.metadata['counter_found_2'] = [False] * 72
        self.metadata['counter_found_3'] = [False] * 72
        self.tempLUT = parse.read_temp_LUT('lib/DAS/temp_LUT.txt')
        self.tcoeff = self.metadata['tcoeff_default']
        self.ccoeff = self.metadata['ccoeff_default']
        self.zcoeff = self.metadata['zcoeff_default']
        
        #store powers at different frequencies used to ID profile start
        self.p400 = np.array([])
        self.p7500 = np.array([])
        self.pdead = np.array([])
        self.r400 = np.array([])
        self.r7500 = np.array([])
        self.power_inds = []
        
        
        self.demodbufferstartind = 0
        self.firstpulse400 = -1 #will store r400 index corresponding to first 400 Hz pulse
        self.profstartind = -1
        self.lastdemodind = -1 #set to -1 to indicate no demodulation has occurred
        self.curpulse = 0
        
        #updating status info (400 Hz pulse/trigger times, status variable) if processor is being restarted
        if self.firstpulsetime > 0:
            self.firstpulse400 = int(self.fs * self.firstpulsetime)
            self.curpulse = 1
            self.status = 1
            if self.firstpointtime > 0:
                self.firstpulseind = int(self.fs * self.firstpointtime)
                self.status = 2
                        
        self.mean7500pwr = np.NaN
        

        if self.isfromaudio:            
            self.numpoints = len(self.audiostream)
        
        #constant settings for analysis
        self.fs_power = 25 #check 25 times per second aka once per frame
        self.N_power = int(self.fs/10) #each power calculation is for 0.1 seconds of PCM data
        self.power_smooth_window = 5
        self.d_pcm = int(np.round(self.fs/self.fs_power)) #how many points apart to sample power
        
        self.demod_buffer = np.array([]) #buffer (list) for demodulating PCM data
        self.demod_Npad = 50 #how many points to pad on either side of demodulation window (must be larger than window length for low-pass filter in demodulation function)
        
        #demodulator configuration
        self.f1 = mark_space_freqs[0] # bit 1 (mark) = 400 Hz
        self.f2 = mark_space_freqs[1] # bit 0 (space) = 800 Hz
        self.bitrate = bitrate #symbol rate = 800 Hz
        self.bit_inset = bit_inset #number of points after/before zero crossing where bit identification starts/ends
        self.phase_error = phase_error
        N = int(np.round(self.fs/self.bitrate*(1 - self.phase_error/100))) #length of PCM for bit power test
        self.Npcm = N - 2*self.bit_inset
        self.trig1 = 2*np.pi*np.arange(0,self.Npcm)/self.fs*self.f1 #trig term for power calculation
        self.trig2 = 2*np.pi*np.arange(0,self.Npcm)/self.fs*self.f2
        
        #filter to be applied to PCM data before demodulation
        if use_bandpass:
            self.sos_filter = signal.butter(6, [100,1200], btype='bandpass', fs=self.fs, output='sos') #low pass
        else:
            self.sos_filter = signal.butter(6, 1200, btype='lowpass', fs=self.fs, output='sos') #low pass
    
        
        self.high_bit_scale = 1.5 #scale factor for high frequency bit to correct for higher power at low frequencies (will be adjusted to optimize demodulation after reading first header data)
        
        self.binary_buffer = [] #buffer for demodulated binary data not organized into frames
        self.binary_buffer_inds = [] #pcm indices for each bit start point (used to calculate observation times during frame parsing)
        self.binary_buffer_conf = [] #confidence ratios: used for demodulation debugging/improvement
        self.r7500_buffer = [] #holds 7500 Hz sig lev ratios corresponding to each bit
        
        
        #trig terms for power calculations
        self.theta400 = 2*np.pi*np.arange(0,self.N_power)/self.fs*400 #400 Hz (main pulse)
        self.theta7500 = 2*np.pi*np.arange(0,self.N_power)/self.fs*7500 #400 Hz (main pulse)
        self.thetadead = 2*np.pi*np.arange(0,self.N_power)/self.fs*self.deadfreq #400 Hz (main pulse)
        
        #-1: not processing, 0: no pulses, 1: found pulse, 2: active profile parsing
        self.status = -1 
            
            
            
        
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
    
                    
            elif self.isfromaudio or self.isfromtest: #if source is an audio file
                #configuring sample times for the audio file
                self.lensignal = len(self.audiostream)
                self.maxtime = self.lensignal/self.f_s
                
                self.bufferstartind = 0
                    
                
            # setting up thread while loop- terminates when user clicks "STOP" or audio file finishes processing
            i = -1
            
            self.status = 0
            #self.demodbufferstartind is initialized in self.initialize_AXCTD_vars()
                
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
                        
                    #TODO: pulling data from audio buffer
                    
                    
                else:
                    #TODO: UPDATE BUFFER OVERFLOW PREVENTION FOR AXCTD/PULL FROM AXCTDPROCESSOR
                    #kill test/audio threads once time exceeds the max time of the audio file
                    #NOTE: need to do this on the cycle before hitting the max time when processing from audio because the WAV file processes faster than the thread can kill itself
                    if self.isfromaudio and i >= len(self.sampletimes)-1:
                        self.kill(0)
                        return
                        
                    #updates progress every iteration
                    if self.isfromaudio:
                        self.signals.updateprogress.emit(self.tabID, int(self.demodbufferstartind / self.numpoints * 100))

                    #TODO: WHAT CURRENT DATA TO PULL
                    

                #TODO: SIGNAL CALCULATIONS, DEMODULATE DATA
                
                #TODO: DETERMINE IF VALID SIGNAL RECEIVED YET (modify triggerstatus)
                
                
                    
                    
                oldstatus = self.status
                data = self.iterate_AXCTD_process(e)
                
                if self.status != oldstatus: #status updated = profile or 400 Hz pulses triggered
                    if self.status == 1:
                        triggertime = self.firstpulsetime
                    elif self.status == 2:
                        triggertime = self.firstpointtime
                    
                    #release signal indicating probe triggered
                    self.signals.triggered.emit(self.tabID, self.status, triggertime) 
                    
                    
                #won't send if keepgoing stopped since current iteration began
                if self.keepgoing and len(data) > 0: 
                    self.signals.iterated.emit(self.tabID, data) #updating data in GUI loop
                        
                        
                #increment demod buffer index forward
                if self.status > 0: #if active demodulation occuring, increment to start of next bit, corrected for padding
                    if next_demod_ind > self.demod_Npad:
                        self.demodbufferstartind += next_demod_ind - self.demod_Npad
                    else:
                        self.demodbufferstartind += self.fs/self.bitrate #skip one bit, keep going
                else: #signal level calcs only, increment buffer by pointsperloop
                    self.demodbufferstartind += e  
                        
                        
                    
                if self.isfromtest: #sleep until real time catches up to number of demodulated points
                    ctimeinaudio = self.demodbufferstartind/self.fs
                    while (dt.datetime.utcnow() - self.starttime).total_seconds() < ctimeinaudio:
                        timemodule.sleep(0.01)
                elif self.isfromaudio: 
                    timemodule.sleep(0.001) #slight pause to free some resources when processing from audio
                else: 
                    timemodule.sleep(0.2) #realtime processing- wait 0.2 sec for buffer to refill
                    

        except Exception: #if the thread encounters an error, terminate
            trace_error()  # if there is an error, terminates processing
            if self.keepgoing:
                self.kill(10)
                
        while self.waittoterminate: #waits for kill process to complete to avoid race conditions with audio buffer callback
            timemodule.sleep(0.1)
            
            
    
    
    def iterate_AXCTD_process(self, e):

        #getting signal levels at 400 Hz, 7500 Hz, and dead frequency
        #we don't have to calculate all three every time but need to calculate at least two of them every
        #time and the logic/code complexity to save computing an unnecessary one isn't worth the computing
        #power saved
        #sampling interval = sampling frequency / power sampling frequency
        #calculating signal levels at 400 Hz, 7500 Hz, and dead frequency (default 3000 Hz)
        
        pstartind = len(self.power_inds)
        
        self.power_inds.extend([ind for ind in range(self.demodbufferstartind, e-self.N_power, self.d_pcm)])
        for cind in self.power_inds[pstartind:]:
            bufferind = cind - self.demodbufferstartind
            cdata = self.demod_buffer[bufferind:bufferind+self.N_power]
            self.p400 = np.append(self.p400, np.abs(np.sum(cdata*np.cos(self.theta400) + 1j*cdata*np.sin(self.theta400))))
            self.p7500 = np.append(self.p7500, np.abs(np.sum(cdata*np.cos(self.theta7500) + 1j*cdata*np.sin(self.theta7500))))
            self.pdead = np.append(self.pdead, np.abs(np.sum(cdata*np.cos(self.thetadead) + 1j*cdata*np.sin(self.thetadead))))
                    
        #smoothing signal levels, calculating R400/R7500
        self.p400 = demodulate.boxsmooth_lag(self.p400, self.power_smooth_window, pstartind)
        self.p7500 = demodulate.boxsmooth_lag(self.p7500, self.power_smooth_window, pstartind)
        self.pdead = demodulate.boxsmooth_lag(self.pdead, self.power_smooth_window, pstartind)
        self.r400 = np.append(self.r400, np.log10(self.p400[pstartind:]/self.pdead[pstartind:]))
        self.r7500 = np.append(self.r7500, np.log10(self.p7500[pstartind:]/self.pdead[pstartind:]))
        
        
        #look for 400 Hz pulse if it hasn't been discovered yet
        if self.status == 0:
            matchpoints = np.where(self.r400[pstartind:] >= self.minR400)
            if len(matchpoints[0]) > 0: #found a match!
                self.firstpulse400 = self.power_inds[pstartind:][matchpoints[0][0]] #getting index in original PCM data
                self.firstpulsetime = self.firstpulse400/self.fs
                self.status = 1
            
        
        #if pulse discovered, demodulate data to bitstream AND check 7500 Hz power
        if self.status >= 1:
            
            #calculate 7500 Hz lower power (in range 4.5-5.5 seconds after first 400 Hz pulse start)
            #last power index is at least 5.5 seconds after 400 Hz pulse detected
            if self.power_inds[-1] >= self.firstpulse400 + int(self.fs*5.5) and np.isnan(self.mean7500pwr): 
                #mean signal level at 7500 Hz between 4.5 and 5.5 sec after 400 Hz pulse
                pwr_ind_array = np.asarray(self.power_inds)
                s7500ind = np.argmin(np.abs(self.firstpulse400 + int(self.fs*4.5) - pwr_ind_array))
                e7500ind = np.argmin(np.abs(self.firstpulse400 + int(self.fs*5.5) - pwr_ind_array))
                self.mean7500pwr = np.nanmean(self.r7500[s7500ind:e7500ind])
            
            #get 7500 Hz power and update status (and bitstream) as necessary 
            #(only bother if time since 400 Hz pulse exceeds the minimum time for profile start)
            if self.power_inds[-1] > self.firstpulse400 + int(self.triggerrange[0]*self.fs):
                if not np.isnan(self.mean7500pwr) and self.status == 1:
                    matchpoints = np.where(self.r7500[pstartind:] - self.mean7500pwr >= self.mindR7500)
                    if len(matchpoints[0]) > 0: #if power threshold is exceeded
                        self.profstartind = self.power_inds[pstartind:][matchpoints[0][0]]
                        self.status = 2
                #if the latest trigger time setting has been exceeded
                elif self.triggerrange[1] > 0 and self.power_inds[-1] >= self.firstpulse400 + int(self.fs*self.triggerrange[1]):
                    self.profstartind = self.firstpulse400 + int(self.fs*self.triggerrange[1])
                    self.status = 2
                if self.profstartind > 0 and self.firstpointtime <= 0:
                    self.firstpointtime = self.profstartind/self.fs
            
            #demodulate to bitstream and append bits to buffer
            curbits, conf, bit_edges, next_demod_ind = demodulate.demodulate_axctd(self.demod_buffer, self.fs, self.demod_Npad, self.sos_filter, self.bitrate, self.f1, self.f2, self.trig1, self.trig2, self.Npcm, self.bit_inset, self.phase_error, self.high_bit_scale)
            
            self.binary_buffer.extend(curbits) #buffer for demodulated binary data not organized into frames
            
            new_bit_inds = [be + self.demodbufferstartind for be in bit_edges]
            self.binary_buffer_inds.extend(new_bit_inds)
            
            self.binary_buffer_conf.extend(conf)
            
            
            #TODO: WRITE WAV FILE AND SIGDATA FILE INFO
            #array of profile signal levels to go with other data 
            recent_r7500 = self.r7500[pstartind:]
            recent_pwrinds = self.power_inds[pstartind:]
            new_r7500 = [recent_r7500[np.argmin(np.abs(recent_pwrinds - ci))]-self.mean7500pwr for ci in new_bit_inds]
            self.r7500_buffer.extend(new_r7500)
            
            
        #attempting to read headers for conversion coefficients and AXCTD metadata
        if self.status >= 1 and not self.past_headers:
        
            #seeing if enough time has passed since first pulse to contain 2nd or 3rd header data
            #pulse length: 1.8 sec, header length: 2.88 sec, gap period (first 2 pulses): 5 sec
            #total pulse cycle ~= 9.68 sec (assume 9-10 sec)
            
            headerdata = [None,None]
            
            firstbin = self.binary_buffer_inds[0]
            lastbin = self.binary_buffer_inds[-1]
            cbufferindarray = np.asarray(self.binary_buffer_inds)
            
            #first header should start around 1.8 sec and end around 3.7 seconds
            #only processing a small margin within that to be sure we are only capturing 1 sec of header
            p1headerstartpcm = self.firstpulse400 + int(self.fs*2.3)
            p1headerendpcm = self.firstpulse400 + int(self.fs*3.3)
            
            #second header should start around 11.48 sec and end around 14.36 seconds
            p2headerstartpcm = self.firstpulse400 + int(self.fs*10.5) #capture 1 sec of pulse
            p2headerendpcm = self.firstpulse400 + int(self.fs*14.8) #~half second margin on backend
            
            #third header should start around 21.16 sec and end around 24.04 seconds
            p3headerstartpcm = self.firstpulse400 + int(self.fs*20) #same margins as header 2
            p3headerendpcm =  self.firstpulse400 + int(self.fs*24.5)
            
            #establishing signal amplitudes based on first header to improve demodulation
            if firstbin <= p1headerstartpcm and lastbin >= p1headerendpcm and not self.header1_read: 
                
                #determining binary data start/end index (adding extra 0.5 sec of data if available)
                p1startind = np.where(cbufferindarray >= p1headerstartpcm - int(self.fs*0.5))[0][0]
                p1endind = np.where(cbufferindarray <= p1headerendpcm + int(self.fs*0.5))[0][-1]
                
                #pulling confidence ratios from the header and recalculating optimal high bit scale
                header_confs = self.binary_buffer_conf[p1startind:p1endind]
                self.high_bit_scale = demodulate.adjust_scale_factor(header_confs, self.high_bit_scale)
                self.header1_read = True
                
            
            #trying to process second header
            if firstbin <= p2headerstartpcm and lastbin >= p2headerendpcm and not self.header2_read: 
                
                #determining binary data start/end index (adding extra 0.5 sec of data if available)
                p2startind = np.where(cbufferindarray >= p2headerstartpcm - int(self.fs*0.5))[0][0]
                p2endind = np.where(cbufferindarray <= p2headerendpcm + int(self.fs*0.5))[0][-1]
                
                #pulling header data from pulse
                header_bindata = parse.trim_header(self.binary_buffer[p2startind:p2endind])
                
                if len(header_bindata) >= 72*32: #must contain full header
                
                    #parsing and converting header information
                    headerdata[0] = parse.parse_header(header_bindata)
                    self.header2_read = True #read complete for 2nd header transmission
                    
            #trying to process third header
            if firstbin <= p3headerstartpcm and lastbin >= p3headerendpcm and not self.header3_read: 
                
                #determining binary data start/end index (adding extra 0.5 sec of data if available)
                p3startind = np.where(cbufferindarray >= p3headerstartpcm - int(self.fs*0.5))[0][0]
                p3endind = np.where(cbufferindarray <= p3headerendpcm + int(self.fs*0.5))[0][-1]
                
                #pulling header data from pulse
                header_bindata = parse.trim_header(self.binary_buffer[p3startind:p3endind])
                
                if len(header_bindata) >= 72*32: #must contain full header
                
                    #parsing and converting header information
                    headerdata[1] = parse.parse_header(header_bindata)
                    self.header3_read = True #read complete for 3rd header transmission
                    
                    
                
            #incorporating AXCTD header info into profile metadata
            coeffs = ['t','c','z']
            other_data = ['serial_no','probe_code','max_depth','misc']
            for i,header in enumerate(headerdata):
                
                if header is not None:
                    
                    self.metadata[f'frame_data_{i+2}'] = header['frame_data']
                    self.metadata[f'counter_found_{i+2}'] = header['counter_found']
                    
                    for coeff in coeffs: #incorporating coefficients (coeff, coeff_valid, coeff_hex)
                        for ci in range(4):
                            if header[coeff + 'coeff_valid'][ci]:
                                self.metadata[coeff + 'coeff'][ci] = header[coeff + 'coeff'][ci]
                                self.metadata[coeff + 'coeff_hex'][ci] = header[coeff + 'coeff_hex'][ci]
                                self.metadata[coeff + 'coeff_valid'][ci] = True
                    
                    for key in other_data: #incorporating other profile metadata
                        if header[key] is not None and self.metadata[key] is None:
                            self.metadata[key] = header[key]
                            
            
            #if updated headers included, then try to update coefficients
            if headerdata[0] is not None or headerdata[1] is not None: 
                if sum(self.metadata['tcoeff_valid']) == 4:
                    self.tcoeff = self.metadata['tcoeff']
                if sum(self.metadata['ccoeff_valid']) == 4:
                    self.ccoeff = self.metadata['ccoeff']
                if sum(self.metadata['tcoeff_valid']) == 4:
                    self.zcoeff = self.metadata['zcoeff']
            
                    
        #getting 
            
        if self.status == 2: #parsing bitstream into frames and calculating updated profile data
            
            self.past_headers = True
            
            #cutting off all data before profile initiation
            if self.binary_buffer_inds[0] <= self.profstartind:
                firstind = np.where(np.asarray(self.binary_buffer_inds) > self.profstartind)[0][0]
                self.binary_buffer = self.binary_buffer[firstind:]
                self.binary_buffer_inds = self.binary_buffer_inds[firstind:]
                self.binary_buffer_conf = self.binary_buffer_conf[firstind:]
                self.r7500_buffer = self.r7500_buffer[firstind:]
            
            #calculting times corresponding to each bit
            binbufftimes = (np.asarray(self.binary_buffer_inds) - self.profstartind)/self.fs
                
            #parsing data into frames
            hexframes,times,depths,temps,conds,psals,next_buffer_ind = parse.parse_bitstream_to_profile(self.binary_buffer, binbufftimes, self.r7500_buffer, self.tempLUT, self.tcoeff, self.ccoeff, self.zcoeff)
            
            #rounding data and appending to lists #TODO SWITCH TO SIGNAL SEND
            times = np.round(times,2)
            depths = np.round(depths,2)
            temps = np.round(temps,2)
            conds = np.round(conds,2)
            psals = np.round(psals,2)
            r7500 = np.round(self.r7500_buffer,2)
            
            #removing parsed data from binary buffer
            self.binary_buffer = self.binary_buffer[next_buffer_ind:]
            self.binary_buffer_inds = self.binary_buffer_inds[next_buffer_ind:]
            self.r7500_buffer = self.r7500_buffer[next_buffer_ind:]
            
            
        else:
            
            times = [np.round(self.power_inds[-1]/self.fs,2)]
            r400 = [np.round(self.r400[-1],2)]
            r7500 = [np.round(self.r7500[-1],2)]
            depths = [np.NaN]
            temps = [np.NaN]
            conds = [np.NaN]
            hexframes = ['00000000']
                
                
                
        data = [self.status, times, r400, r7500, depths, temps, conds, hexframes] #what to send to AXCTD GUI loop   
        return data


    