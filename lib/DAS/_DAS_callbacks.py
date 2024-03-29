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

# This file holds all callback functions for radio receivers.
#
# Callbacks must append data to self.audiostream (and remove data from the beginning 
#   of the buffer for AXBTs only) and write incoming data to the wav file


import wave #WAV file writing
import pyaudio
from traceback import print_exc as trace_error

from ctypes import (Structure, pointer, c_int, c_ulong, c_char, c_uint32,
c_char_p, c_void_p, POINTER, c_int16, cast, CFUNCTYPE)






# =============================================================================
#                      WINRADIO CALLBACK FUNCTIONS
# =============================================================================


def define_callbacks(self, probetype, sourcetype):
    
    
    if sourcetype == 'WR': #WiNRADIO receiver callbacks by probe type 
        
        if probetype == "AXBT": #audio buffer tail is moved by the callback function

            #AXBT
            @CFUNCTYPE(None, c_void_p, c_void_p, c_ulong, c_ulong)
            def receiver_callback(streampointer_int, bufferpointer_int, size, samplerate):
                
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
                    
                    
        
        elif probetype == "AXCTD" or probetype == "AXCP": #audio buffer tail is moved by the DAS thread
            
            #AXCTD
            @CFUNCTYPE(None, c_void_p, c_void_p, c_ulong, c_ulong)
            def receiver_callback(streampointer_int, bufferpointer_int, size, samplerate):
                
                try:
                    self.numcontacts += 1 #note that the buffer has been pulled again
                    bufferlength = int(size / 2)
                    bufferpointer = cast(bufferpointer_int, POINTER(c_int16 * bufferlength))
                    bufferdata = bufferpointer.contents
                    self.f_s = samplerate
                    self.nframes += bufferlength
                    self.audiostream.extend(bufferdata[:]) #append data to end
                    #dont delete data from start, the AXCTD Processor thread will handle this as it is processed
                    
                    #recording to wav file: this terminates if the file exceeds a certain length
                    if self.isrecordingaudio and self.nframes > self.maxsavedframes:
                        self.isrecordingaudio = False
                        self.killaudiorecording()
                    elif self.isrecordingaudio:
                        wave.Wave_write.writeframes(self.wavfile,bytearray(bufferdata))
                        
                except Exception: #error handling for callback
                    trace_error()  
                    self.kill(10)
    
        else: #probe type not recognized
            receiver_callback = None
            
            
            
    elif sourcetype == 'PA': #PyAudio- pulling audio from a computer microphone or other connected audio source
        
        if probetype == "AXBT": #audio buffer tail is moved by the callback function
                
            def receiver_callback(bufferdata_bytes, nframes, time_info, status):
                try:                    
                    #bytearray to signed int16 buffer
                    bufferdata = [int.from_bytes(bufferdata_bytes[i:i+2],"little")-32767 for i in range(0,len(bufferdata_bytes),2)]
                    
                    self.audiostream.extend(bufferdata[:]) #append data to end
                    del self.audiostream[:nframes] #remove data from start
                    returntype = pyaudio.paContinue
                    
                    #recording to wav file: this terminates if the file exceeds a certain length
                    if self.isrecordingaudio and self.nframes > self.maxsavedframes:
                        self.isrecordingaudio = False
                        self.killaudiorecording()
                    elif self.isrecordingaudio:
                        wave.Wave_write.writeframes(self.wavfile,bytearray(bufferdata_bytes))
                            
                except Exception:
                    trace_error()  
                    self.kill(10)
                    returntype = pyaudio.paAbort
                finally:
                    return (None, returntype)
                #end of callback function
                
        
        elif probetype == "AXCTD" or probetype == "AXCP": #audio buffer tail is moved by the DAS thread
                
            def receiver_callback(bufferdata_bytes, nframes, time_info, status):
                try:
                    #bytearray to signed int16 buffer
                    bufferdata = [int.from_bytes(bufferdata_bytes[i:i+2],"little")-32767 for i in range(0,len(bufferdata_bytes),2)]
                    
                    self.audiostream.extend(bufferdata[:]) #append data to end
                    returntype = pyaudio.paContinue
                                            
                    #recording to wav file: this terminates if the file exceeds a certain length
                    if self.isrecordingaudio and self.nframes > self.maxsavedframes:
                        self.isrecordingaudio = False
                        self.killaudiorecording()
                    elif self.isrecordingaudio:
                        wave.Wave_write.writeframes(self.wavfile,bytearray(bufferdata_bytes))
                            
                except Exception:
                    trace_error()  
                    self.kill(10)
                    returntype = pyaudio.paAbort
                finally:
                    return (None, returntype)
                    #end of callback function
            
        
        else: #probe type not recognized
            receiver_callback = None
        
            
    else: #not a recognized receiver (test, audio, or error)
        receiver_callback = None
        
    return receiver_callback
        
    
    
        
# if probetype == "AXBT": #audio buffer tail is moved by the callback function
# elif probetype == "AXCTD" or probetype == "AXCP": #audio buffer tail is moved by the DAS thread
# else: #probe type not recognized
# receiver_callback = None
        
        