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

# This file holds all callback functions for radio receivers.
#
# Callbacks must append data to self.audiostream (and remove data from the beginning 
#   of the buffer for AXBTs only) and write to the 


import wave #WAV file writing
from traceback import print_exc as trace_error

from ctypes import (Structure, pointer, c_int, c_ulong, c_char, c_uint32,
c_char_p, c_void_p, POINTER, c_int16, cast, CFUNCTYPE)


# =============================================================================
#                      WINRADIO CALLBACK FUNCTIONS
# =============================================================================

#AXBT
@CFUNCTYPE(None, c_void_p, c_void_p, c_ulong, c_ulong)
def wr_axbt_callback(streampointer_int, bufferpointer_int, size, samplerate):
    
    try:
        self.numcontacts += 1 #note that the buffer has been pulled again
        bufferlength = int(size / 2)
        bufferpointer = cast(bufferpointer_int, POINTER(c_int16 * bufferlength))
        bufferdata = bufferpointer.contents
        self.f_s = samplerate
        self.nframes += bufferlength
        self.audiostream.extend(bufferdata[:]) #append data to end
        del self.audiostream[:bufferlength] #remove data from start
        
        #recording to wav file: this terminates if the file exceeds a certain length
        if self.isrecordingaudio and self.nframes > self.maxsavedframes:
            self.isrecordingaudio = False
            self.killaudiorecording()
        elif self.isrecordingaudio:
            wave.Wave_write.writeframes(self.wavfile,bytearray(bufferdata))
            
    except Exception: #error handling for callback
        trace_error()  
        self.kill(10)
    
        
        
#AXCTD
@CFUNCTYPE(None, c_void_p, c_void_p, c_ulong, c_ulong)
def wr_axctd_callback(streampointer_int, bufferpointer_int, size, samplerate):
    
    try:
        self.numcontacts += 1 #note that the buffer has been pulled again
        bufferlength = int(size / 2)
        bufferpointer = cast(bufferpointer_int, POINTER(c_int16 * bufferlength))
        bufferdata = bufferpointer.contents
        self.f_s = samplerate
        self.nframes += bufferlength
        self.audiostream.extend(bufferdata[:]) #append data to end
        #dont delete data from start, the AXCTDProcessor thread will handle this as it is processed
        
        #recording to wav file: this terminates if the file exceeds a certain length
        if self.isrecordingaudio and self.nframes > self.maxsavedframes:
            self.isrecordingaudio = False
            self.killaudiorecording()
        elif self.isrecordingaudio:
            wave.Wave_write.writeframes(self.wavfile,bytearray(bufferdata))
            
    except Exception: #error handling for callback
        trace_error()  
        self.kill(10)
        
        
        
        
        
        