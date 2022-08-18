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

# This file contains functions specific to computer audio device inputs. See common_DAS_functions
# or processor_functions.py for an explanation of where all other functions are saved

# To add functionality for another radio receiver, create a new file with the same functionality 
#   as this one, including the following functions:
#   list_radios, activate_receiver, change_receiver_freq, setup_receiver_stream, and stop_receiver,
#   and integrate those functions into the common_DAS_functions.py code, assigning a unique 2-letter 
#   string identifier for that type of radio (cannot be AA, TT, or any receiver identifiers like WR)
#   Additionally, add callback functions that will update self.audiostream in the DAS_callbacks.py file


                    
import time as timemodule
import pyaudio
from sys import platform
from traceback import print_exc as trace_error
import numpy as np



# =============================================================================
# LIST ALL CONNECTED AUDIO DEVICES
# =============================================================================

#p is a pyaudio instance
def listaudiodevices(p):
    miclist = []
    for i in range(p.get_device_count()):
        try:
            if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                curmic = p.get_device_info_by_index(i).get('name')
                curindex = i
                miclist.append(f"{curmic} ({i})")
        except OSError:
            pass
    
    return miclist

    
    
    
# =============================================================================
# CONTROL CONNECTED SOURCES
# =============================================================================
def activate_receiver(p,devicename): #no need to turn on 
    
    startthread = 1
    hradio = -1
    
    try:
        hradio = int(devicename.replace(')','(').split('(')[-2])
        startthread = 0
    except: #any issue with parsing the device index from the name means there is a problem
        pass
    
    
    return hradio, startthread
    
    
    
def check_receiver_connected(p,hradio): #verify the device is connected
    try:
        curmic = p.get_device_info_by_index(hradio).get('name')
        return True
    except:
        return False
    
        
#not required for PyAudio devices
# def change_receiver_freq(wrdll,hradio,vhffreq): #change VHF frequency for demodulation
#     return status
    
    
def setup_receiver_stream(p, hradio, destination, tabID):
    f_s = int(np.round(p.get_device_info_by_index(hradio)['defaultSampleRate']))
    frametype = pyaudio.paInt16
    
    status = None
    if platform.lower() == "darwin": #MacOS specific stream info input
        status = pyaudio.Stream(p, f_s, 1, frametype, input=True, output=False, input_device_index=hradio, start=True, stream_callback=destination, input_host_api_specific_stream_info= pyaudio.PaMacCoreStreamInfo())
    else: #windows or linux
        status = pyaudio.Stream(p, f_s, 1, frametype, input=True, output=False, input_device_index=hradio, start=True, stream_callback=destination)
        
    return status
    
    
def stop_receiver(stream): #stop audio stream
    stream.stop_stream()
    stream.close()
    
    
    
    