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

# This file contains functions specific to operating a WiNRADIO G39WSB receiver. See common_DAS_functions
# or processor_functions.py for an explanation of where all other functions are saved

# To add functionality for another radio receiver, create a new file with the same functionality 
#   as this one, including the following functions:
#   list_radios, activate_receiver, change_receiver_freq, setup_receiver_stream, and stop_receiver,
#   and integrate those functions into the common_DAS_functions.py code, assigning a unique 2-letter 
#   string identifier for that type of radio (cannot be AA, TT, or any receiver identifiers like WR)
#   Additionally, add callback functions that will update self.audiostream in the DAS_callbacks.py file


from sys import getsizeof
from ctypes import (Structure, pointer, c_int, c_ulong, c_char, c_uint32,
                    c_char_p, c_void_p, POINTER, c_int16, cast, CFUNCTYPE)
                    
import time as timemodule

from traceback import print_exc as trace_error
    

#!!!!!!!!!!!!!!!!!!          README FOR INFO ON WINRADIO FUNCTIONS:             !!!!!!!!!!!!!!!!!!!!!!!!!
#Any functions called below from the winradio DLL (e.g. wrdll.GetRadioList, wrdll.IsDeviceConnected, etc.)
#are outlined in the WiNRADIO software development kit at https://winradio.com/home/g39wsb_sdk.htm
#This includes the function names and their inputs and outputs. The input and output variables are C type
#variables, which require the python ctypes module (imported above) to be initialized properly.


# =============================================================================
# LIST ALL CONNECTED WINRADIO RECEIVERS
# =============================================================================


# initialize radioinfo structure
class Features(Structure):
    _pack_ = 1
    _fields_ = [("ExtRef", c_uint32), ("FMWEnabled", c_uint32), ("Reserved", c_uint32)]
class RADIO_INFO2(Structure):
    _pack_ = 1
    _fields_ = [("bLength", c_uint32), ("szSerNum", c_char*9), ("szProdName", c_char*9), ("MinFreq", c_uint32),("MaxFreq", c_uint32), ("Features", Features)]
    
    

#gets list of current winradios
def list_radios(wrdll):

    # creating array of RADIO_INFO2 structures to load info from GetRadioList() command
    radiolistarray = (RADIO_INFO2 * 50)()
    radiolistpointer = pointer(radiolistarray)
    # radiolistsize = getsizeof(radiolistarray)
    radiolistsize = 1000 #fix for serial issue
    radiolistinfosize = c_int(0)
    radiolistinfosizepointer = pointer(radiolistinfosize)

    # getting list of all connected winradio info
    winradioserials = []
    numradios = wrdll.GetRadioList(radiolistpointer, radiolistsize, radiolistinfosizepointer)
    lenradiolist = radiolistarray.__len__()
    if numradios > lenradiolist:
        numradios = lenradiolist
        print("Warning: Buffered array has insufficient size to return information for all winradios")
    for i in range(numradios):
        currentserial = radiolistarray[i].szSerNum.decode('utf-8')
        winradioserials.append(currentserial)

    #TEST- print autopopulated info for all receivers
    #for i,cradio in enumerate(radiolistarray):
    #    print(f"#{i}: serial={cradio.szSerNum}, product={cradio.szProdName}, size={cradio.bLength}")
        
    return winradioserials

    
    
    
# =============================================================================
# CONTROL CONNECTED WINRADIO RECEIVERS
# =============================================================================
def activate_receiver(wrdll,serial,vhffreq): #turn on radio receiver
    
    startthread = 0
    hradio = 0
    
    #opening receiver
    serialnum_2WR = c_char_p(serial.encode('utf-8'))
    hradio = wrdll.Open(serialnum_2WR)
    if hradio == 0:
        startthread = 1
        
    else:
        try:
            # power on- kill if failed
            if wrdll.SetPower(hradio, True) == 0:
                startthread = 2
                
            # initialize demodulator- kill if failed
            if wrdll.InitializeDemodulator(hradio) == 0:
                startthread = 3
                
            # set frequency- kill if failed
            if change_receiver_freq(wrdll,hradio,vhffreq) == 0:
                startthread = 4
                
            # set volume- kill if failed
            if wrdll.SetVolume(hradio, 31) == 0:
                startthread = 5
                
        except Exception: #if any WiNRADIO comms/initialization attempts failed, terminate thread
            trace_error()
            startthread = 6
            
            
    #shut down the receiver if it was powered on but had a subsequent error
    if hradio > 0 and startthread > 0:
        stop_receiver(wrdll,hradio)
            
    return hradio, startthread
    
    
    
def check_receiver_connected(wrdll,hradio): #verify the device is connected
    return wrdll.IsDeviceConnected(hradio)
    
def change_receiver_freq(wrdll,hradio,vhffreq): #change VHF frequency for demodulation
    vhffreq_2WR = c_ulong(int(vhffreq * 1E6))
    status = wrdll.SetFrequency(hradio, vhffreq_2WR)
    return status
    
    
def setup_receiver_stream(wrdll,hradio,destination,tabID): #direct demodulated PCM data to a destination callback function
    status = wrdll.SetupStreams(hradio, None, None, destination, c_int(tabID))
    return status
    
    
def stop_receiver(wrdll,hradio): #power off/disconnect receiver
    wrdll.SetupStreams(hradio, None, None, None, None)
    timemodule.sleep(0.3) #additional time after stream directed to null before finishing function and allowing DAS to close audio file
    wrdll.CloseRadioDevice(hradio)
    
    
    
    