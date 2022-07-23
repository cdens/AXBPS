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

# This file contains functions that are used by all DAS threads but are not methods
# within that thread's class itself, e.g. general radio receiver controls.
#
# Functions that are common methods of AXBTProcessor/AXCTDProcessor/etc. thread
# classes go in processor_functions.py
# instead, except for radio receiver-specific functions which go in either DAS_callback.py 
# (if it is a callback function to update the audio PCM data buffer for the thread) or 
# a separate radio reciver file e.g. winradio_functions.py, which is called by the radio receiver
# methods in common_DAS_functions.py

import numpy as np
from scipy.io import wavfile #for wav file reading
import wave #WAV file writing

import lib.DAS.winradio_functions as wr
from traceback import print_exc as trace_error

from PyQt5.QtCore import QObject, pyqtSignal

        
# =============================================================================
# GENERAL FUNCTIONS
# =============================================================================

#table lookup for VHF channels and frequencies
def channelandfrequencylookup(value,direction):
    
    #list of frequencies
    allfreqs = np.arange(136,173.51,0.375)
    allfreqs = np.delete(allfreqs,np.where(allfreqs == 161.5)[0][0])
    allfreqs = np.delete(allfreqs,np.where(allfreqs == 161.875)[0][0])
    
    #liwst of corresponding channels
    allchannels = np.arange(32,99.1,1)
    cha = np.arange(1,16.1,1)
    chb = np.arange(17,31.1,1)
    for i in range(len(chb)):
        allchannels = np.append(allchannels,cha[i])
        allchannels = np.append(allchannels,chb[i])
    allchannels = np.append(allchannels,cha[15])

    if direction == 'findfrequency': #find frequency given channel
        try:
            outval = allfreqs[np.where(allchannels == value)[0][0]]
            correctedval = value
        except:
            correctedval = allchannels[np.argmin(abs(allchannels-value))]
            outval = allfreqs[np.where(allchannels == correctedval)[0][0]]
            
    elif direction == 'findchannel': #find channel given frequency
        try:
            outval = allchannels[np.where(allfreqs == value)[0][0]]
            correctedval = value
        except:
            correctedval = allfreqs[np.argmin(abs(allfreqs-value))]
            outval = allchannels[np.where(allfreqs == correctedval)[0][0]]

    else: #incorrect option
        print("Incorrect channel/frequency lookup selection!")
        outval = 0
        correctedval = 0
    
    return outval,correctedval
        
        
        
def read_audio_file(audiofile, chselect, maxsavedframes):
    
    #initializing values to return
    audiostream = [0]*10000
    f_s = 44100
    startthread = 0
    
    #checking file length- wont process files with more frames than max size
    try: #exception if unable to read audio file if it doesn't exist or isn't WAV formatted
        file_info = wave.open(audiofile)
    except:
        startthread = 11
    
    if not startthread:
        if file_info.getnframes() > maxsavedframes:
            startthread = 9
    
    if not startthread:
        f_s, snd = wavfile.read(audiofile) #reading file
    
    #if multiple channels, sum them together
    if not startthread:
        sndshape = np.shape(snd) #array size (tuple)
        ndims = len(sndshape) #number of dimensions
        if ndims == 1: #if one channel, use that
            audiostream = snd
            
        elif ndims == 2: #if multiple channels, pick selected channel or sum across
            if chselect >= 1:
                audiostream = snd[:,chselect-1]
            else:
                audiostream = np.sum(snd,axis=1)
                
        else:
            startthread = 11 #more than 2D = improper format
            
    return audiostream, f_s, startthread
    
    

    
    
#conversion: coefficients=C,  D_out = C[0] + C[1]*D_in + C[2]*D_in^2 + C[3]*D_in^3 + ...
def dataconvert(data_in,coefficients):
    
    datatype = 1 #integer or float
    if type(data_in) == list:
        datatype = 2
    elif type(data_in) == np.ndarray: #numpy array
        dataype = 3
        
    if datatype == 1:
        data_in = [data_in]
        
    output = []
    for cur_data_in in data_in:
        cur_output = 0
        for (i,c) in enumerate(coefficients):
            cur_output += c*cur_data_in**i
        output.append(cur_output)
        
    if datatype == 1: #convert back from list to int/float
        output = output[0]
    elif datatype == 3: #convert to np array
        output = np.asarray(output)
            
    return output
        
    
    
# =============================================================================
# PyQt Signals for processor threads
# =============================================================================
class ProcessorSignals(QObject): 
    iterated = pyqtSignal(int,list) #signal to add another entry to raw data arrays
    triggered = pyqtSignal(int,int,float) #signal that the first tone has been detected
    terminated = pyqtSignal(int) #signal that the loop has been terminated (by user input or program error)
    failed = pyqtSignal(int,int)
    updateprogress = pyqtSignal(int,int) #signal to update audio file progress bar
    emit_profile_update = pyqtSignal(int,list) #replace all profile data with updated info (AXCP only)
    
    
    
    
    
# =============================================================================
# RADIO RECEIVER RELATED FUNCTIONS
# =============================================================================

#custom error if receiver type is not recognized
class ReceiverTypeNotRecognized(Exception):
    def __init__(self, rtype):
        self.message = f"Receiver type {rtype} not recognized"
        super().__init__(self.message)
    
        
        
def list_receivers(dll): #get a list of all radio receivers
    
    receivers = []
    rtypes = []
    
    #add winradio receivers if DLL loaded (windows environment)
    if 'WR' in dll.keys():
        wr_receivers = wr.list_radios(dll['WR'])
        receivers.extend(wr_receivers)
        rtypes.extend(['WR' for _ in wr_receivers])
    
    return receivers,rtypes
    
    
def get_fs(dll,rtype): #identify sampling frequency of demodulated data from receiver by type
    if rtype == 'WR': 
        f_s = 64000  #WiNRADIO sampling frequency is always 64 kHz
    else:
        raise ReceiverTypeNotRecognized(rtype)
    return f_s
    
    
def activate_receiver(dll,rtype,serial,vhffreq): #power on/configure radio receiver
    if rtype == 'WR':
        hradio,status = wr.activate_receiver(dll['WR'], serial, vhffreq,)
    else:
        raise ReceiverTypeNotRecognized(rtype)
        
    return hradio,status
    
    
    
def change_receiver_freq(dll,rtype,hradio,freq): #switch VHF frequency being demodulated
    if rtype == 'WR':
        status = wr.change_receiver_freq(dll['WR'],hradio,freq)
    else:
        raise ReceiverTypeNotRecognized(rtype)
    
    return status
    
    
def check_connected(dll,rtype,hradio): #verify that specified receiver is actively connected/on
    if rtype == 'WR':
        status = wr.check_receiver_connected(dll['WR'],hradio)
    else:
        raise ReceiverTypeNotRecognized(rtype)
    
    return status
    
        
    
def stop_receiver(dll,rtype,hradio): #redirect audio stream/callback to null and stop/power off receiver
    if rtype == 'WR':
        wr.stop_receiver(dll['WR'],hradio)
    else:
        raise ReceiverTypeNotRecognized(rtype)
    
                
    
def initialize_receiver_callback(dll, rtype, hradio, destination, tabID): #specify callback function for audio stream 
    if rtype == 'WR':
        status = wr.setup_receiver_stream(dll['WR'],hradio,destination,tabID)
    else:
        raise ReceiverTypeNotRecognized(rtype)
    return status
    
    
    
    

    