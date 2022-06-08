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


import scipy.io as sio
import numpy as np
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
import scipy.interpolate as sint



#apply a box smoothing filter to dataset with specified window length
def runningsmooth(data,halfwindow): 
    
    #if the running filter is longer than the dataset, return an array with same length as dataset containing dataset mean
    if halfwindow*2+1 >= len(data): 
        smoothdata = np.ones(len(data))*np.mean(data)
        
    #otherwise apply smoothing filter
    else:
        smoothdata = np.array([])
        for i in range(len(data)):
            if i <= halfwindow:
                smoothdata = np.append(smoothdata,np.mean(data[:i+halfwindow]))
            elif i >= len(data) - halfwindow:
                smoothdata = np.append(smoothdata,np.mean(data[i-halfwindow:]))
            else:
                smoothdata = np.append(smoothdata,np.mean(data[i-halfwindow:i+halfwindow]))
            
    return smoothdata
    



#pulling climatology profile, creating polygon for shaded "climo match" region
def getclimatologyprofile(lat,lon,month,climodata):
    
    #convert profile longitude from degW<0 to degW>180 to match climo arrangement
    if lon < 0:
        lon = 360 + lon
        
    #id relevant lon/lat
    flon = np.floor(lon/10)*10
    flat = np.floor(lat/10)*10
    
    #read file
    curclimodata = sio.loadmat(f"data/climo/c_M{int(month)}_N{int(flat)}_E{int(flon)}.mat")
    
    #accessing climatology grid data
    clon = flon + climodata['vals']
    clat = flat + climodata['vals']
    depth = np.float64(climodata["depth"])
    
    #conversions:
    # T_int = 1000*(T_act + 6)   --> uint16, fill 66535   range -5-35
    # S_int = 1000*S_act         --> uint16, fill 66535   range 0-45
    # S/T_int stdev = 50*act.    --> uint8,  fill 255,    max 5
    
    #pulling current month's temperatures + stdevs, converting to int64, correcting scale
    #TODO: add lat/lon indexing so it only pulls a small spatial subset to reduce size
    cmonthtemps = curclimodata["temp"].astype('int64')/1000 - 6
    cmonthpsals = curclimodata["psal"].astype('int64')/1000
    cmonthtdevs = curclimodata["tstdev"].astype('int64')/50
    cmonthsdevs = curclimodata["sstdev"].astype('int64')/50
    
    #correting fill values to NaN
    cmonthtemps[cmonthtemps >= 45] = np.NaN
    cmonthpsals[cmonthpsals >= 55] = np.NaN
    cmonthtdevs[cmonthtdevs > 5.01] = np.NaN
    cmonthsdevs[cmonthsdevs > 5.01] = np.NaN

    #interpolate to current latitude/longitude
    climotemps = sint.interpn((depth,clat, clon), cmonthtemps, (depth,lat, lon))
    climopsals = sint.interpn((depth,clat, clon), cmonthpsals, (depth,lat, lon))
    
    #error margin for shading is +/- 1 standard deviation
    climotemperrors = sint.interpn((depth,clat, clon), cmonthtdevs, (depth,lat, lon))
    climopsalerrors = sint.interpn((depth,clat, clon), cmonthsdevs, (depth,lat, lon))
    
    #find/remove NaNs
    notnanind = ~np.isnan(climotemps*climotemperrors*climopsals*climopsalerrors*depth)
    climotemps = climotemps[notnanind]
    climotemperrors = climotemperrors[notnanind]
    climopsals = climopsals[notnanind]
    climopsalerrors = climopsalerrors[notnanind]
    depth = depth[notnanind]
    
    #generating fill vectors
    tempfill = np.append(climotemps-climotemperrors,np.flip(climotemps+climotemperrors))
    psalfill = np.append(climopsals-climopsalerrors,np.flip(climopsals+climopsalerrors))
    depthfill = np.append(depth,np.flip(depth))
    
    return [climotemps,climopsals,depth,tempfill,psalfill,depthfill]
        
    
    
    

#comparing current profile to climatology
def comparetoclimo(data,depth,climodatas,climodepths,climodatafill,climodepthfill):
    
    climodatas[np.less_equal(climodatas,-8)] = np.nan
    
    #interpolating climatology to match profile depths
    intclimodata = np.interp(depth,climodepths,climodatas)
    
    #identifying and removing NaNs from dataset
    isnandata = np.isnan(intclimodata*data)
    
    if sum(isnandata) != len(isnandata): #if there are non-NaN datapoints
        data = data[isnandata == 0]
        intclimodata = intclimodata[isnandata == 0]
        depth = depth[isnandata == 0]
        
        #determining profile slopes
        climoslope = np.diff(intclimodata)/np.diff(depth)
        profslope = np.diff(data)/np.diff(depth)
        slopedepths = 0.5*depth[1:] + 0.5*depth[:-1]
        
        #comparing slopes:
        threshold = 0.1
        ismismatch = abs(runningsmooth(climoslope-profslope, 50)) >= threshold
        
        #determining if there is a max depth
        if sum(ismismatch) != 0:
            climobottomcutoff = np.max(slopedepths[ismismatch])
            isabovecutoff = np.less_equal(depth,climobottomcutoff)
            data = data[isabovecutoff == 1]
            depth = depth[isabovecutoff == 1]
        else:
            climobottomcutoff = np.nan

        #max depth for climo comparison (if a bottom strike is detected, consider that when comparing profile to climatology)
        if np.isnan(climobottomcutoff):
            maxd = 1E10
        else:
            maxd = climobottomcutoff
        
        #check to see if climatology generally matches profile (is 90% of profile within climatology fill window?)
        isinclimo = []
        climopolylist = []
        for i in range(len(climodatafill)):
            climopolylist.append([climodatafill[i],climodepthfill[i]])
        climopolygon = Polygon(climopolylist)    
        
        depth[0] = 0.1
        for i in range(len(data)):
            if depth[i] <= maxd:
                curpoint = Point(data[i], depth[i])
                isinclimo.append(int(climopolygon.contains(curpoint)))
            
        minpctmatch = 0.5 #checks if prof matches climo: more than (minpctmatch*100) percent of profile must be within +/1 one standard deviation of climatology profile to be considered a match (0 <= minpctmatch <= 1)
        if sum(isinclimo)/len(isinclimo) >= minpctmatch: 
            matchclimo = 1
        else:
            matchclimo = 0
    
    else: #if no valid datapoints- say that the climatology matches (because we can't tell otherwise)
        matchclimo = 1
        climobottomcutoff = np.nan
        
        
    return matchclimo,climobottomcutoff
        


    
    

#pull ocean depth from ETOPO1 Grid-Registered Ice Sheet based global relief dataset 
#Data source: NOAA-NGDC: https://www.ngdc.noaa.gov/mgg/global/global.html
def getoceandepth(lat,lon,dcoord,bathydata):

    #get longitudes and latitudes to pull- the +/- adds a little leeway so no white space appears on the plot after it is resized to correct for latitudinal contraction + plot aspect ratio
    
    roundlon = int(np.round(lon))
    roundlat = int(np.round(lat))
    lonstopull = [d+roundlon for d in range(-dcoord-4,dcoord+4+1)]
    latstopull = [d+roundlat for d in range(-dcoord-1,dcoord+1+1)]
    
    exportlon,exportlat,exportrelief = getbathydata(latstopull,lonstopull, bathydata)
    
    #interpolate maximum ocean depth
    maxoceandepth = -sint.interpn((exportlon,exportlat),exportrelief,(lon,lat))
    maxoceandepth = maxoceandepth[0]
    
    num = 4 #adjust this to pull every n elements for topographic data
    exportlat = exportlat[::num]
    exportlon = exportlon[::num]
    exportrelief = exportrelief[::num,::num]
    exportrelief = exportrelief.transpose() #transpose matrix
    
    return maxoceandepth,exportlat,exportlon,exportrelief
    
    
def getbathydata(latstopull,lonstopull, bathydata):
    
    #generate exportlon and exportlat
    exportlon = []
    for clon in lonstopull:
        exportlon.extend(clon + bathydata["vals"])
    exportlat = []
    for clat in latstopull:
        exportlat.extend(clat + bathydata["vals"])
    
    #generate exportrelief
    nv = len(bathydata["vals"])
    exportrelief = np.NaN*np.ones((nv*len(lonstopull),nv*len(latstopull))) #preallocate with NaN
    
    for (i,clon) in enumerate(lonstopull):
        if clon >= 180:
            clon = clon - 360
        elif clon < -180:
            clon = clon + 360
        
        for (j,clat) in enumerate(latstopull):
            if clat >= -90 and clat < 90:
                curbathydata = sio.loadmat(f"data/bathy/b_N{int(clat)}_E{int(clon)}.mat")
                exportrelief[i*nv:(i+1)*nv,j*nv:(j+1)*nv] = curbathydata["z"].astype('float64') #int16 -> float64
                
    return exportlon,exportlat,exportrelief
    
    
    