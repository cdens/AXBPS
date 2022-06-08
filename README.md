# **Airborne eXpendable Buoy Processing System (AXBPS)**


**Author: Casey Densmore (cdensmore101@gmail.com)**

![Icon](lib/dropicon.png)


## Overview <a id="overview"></a>
The Airborne eXpendable Buoy Processing System (AXBPS) is a software/hardware system capable of receiving and quality controlling Airborne eXpendable BathyThermograph (AXBT) and Airborne eXpendable Conductivity Temperature Depth (AXCTD) profiles. AXBPS is composed of two independent subsystems: the Data Acquisition System, which receives telemetered temperature-depth (AXBT) or temperature- and conductivity- depth (AXCTD) profiles with no external hardware other than a VHF radio receiver, and the AXBPS Profile Editing System, which quality controls telemetered profiles.

The Airborne eXpendable Buoy Processing System (AXBPS) Data Acquisition System is designed to receive pulse code modulated (PCM) audio data containing an airborne expendable buoy's signal and decode the telemetered data from the transmission. AXBPS is compatible with WiNRADIO software-defined radio receivers, which demodulate a VHF signal transmitted from an air-launched probe and export the resulting PCM data to AXBPS for processing. Additionally, previously recorded WAV files can be imported into AXBPS to generate the telemetered profile(s). AXBPS integrates the signal processing capabilities of the MK-21 or similar hardware and audio recorders as software-defined functions, reducing the equipment necessary to launch and process data from AXBTs and AXCTDs. 

The Airborne eXpendable Buoy Processing System (AXBPS) Profile Editing System is meant to enable users to quality control AXBT temperature-depth profiles and AXCTD temperature- and salinity-depth profiles, guided by an automated quality control algorithm and further aided by climatology and bathymetry data for the region of interest to reduce the background oceanographic knowledge necessary on the part of the user. 


## Platform Support
AXBPS is currently only fully functional in Windows as there is currently
no driver support for WiNRADIO G39WSBE Receivers in Linux or MacOS. All functionalities other than realtime data processing (e.g. audio file reprocessing, profile quality control) are available for Windows, Linux, and MacOS.

To obtain full (including realtime processing) support in Linux or MacOS, AXBPS can be installed on a Windows 10 virtual machine. AXBPS has been successfully tested for realtime processing in both VirtualBox and VMWare virtual machines with Windows 10 guest and Linux or MacOS host.


## Python requirements/dependencies
This program was developed in Python 3.8, with the GUI built using PyQt5.

	
### Installing Dependencies:
Windows: `pip install -r requirements.txt`  
Linux/MacOs: `pip3 install -r requirements.txt`

NOTE: You may need to install the libgeos library (e.g. *brew install libgeos* on MacOS) for Shapely to work, as well as the Proj library (e.g. *brew install proj* on MacOS) for Cartopy. On Windows, python modules with all dependencies can be installed from wheel files downloadable at https://www.lfd.uci.edu/~gohlke/pythonlibs

Using the Shapely module as an example, the file should be named Shapely-1.6.4.post2-cp3x-cp3xm-win(32 or _amd64).whl depending on Python version and windows type (e.g. Shapely-1.6.4.post2-cp37-cp37m-win_amd64.whl for Python v3.7, Windows x64-bit). After downloading the correct file, install following the syntax below:

```
pip install Shapely-1.6.4.post2-cp3x-cp3xm-win(32 or _amd64).whl 
```




## Data Dependencies and Additional Information

AXBPS also requires driver and data files in the data folder and test files in the testdata folder. Due to size constraints, these are not included in the repository. They will soon be available at an updated webpage for AXBPS, which is coming soon!

This website also hosts a the user manual with details on where to move these folders within the AXBPS repository, how to use the AXBPS, operating principles, and a bundled version of AXBPS (with PyInstaller) and executable installer file for Windows 10 x64. 
