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
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
from shapefile import Reader as shread
import matplotlib.ticker as mticker


#adjusts geographic axis limits to accomplish 1:1 scaling at the plot center for a Mercator projection
def setgeoaxes(fig,ax,xrange,yrange,changeaxis):
    
    # set initial x and y axis limits
    ax.set_xlim(xrange)
    ax.set_ylim(yrange)
    
    # determine plot aspect ratio
    wfig,hfig = fig.get_size_inches()
    _, _, wax, hax = ax.get_position().bounds
    yoverxratio = hax/wax*(hfig/wfig)
    
    # solve coordinate information
    dlonold = np.diff(xrange)/2
    dlatold = np.diff(yrange)/2
    meanlon = np.mean(xrange)
    meanlat = np.mean(yrange)
    
    # find correct contraction ratio as a function of latitude
    lonoverlatratio = np.cos(meanlat*np.pi/180)
    
    # find new dlat and dlon such that the other is conserved and the aspect ratio is accurate
    dlatnew = dlonold/lonoverlatratio*yoverxratio
    dlonnew = dlatold*lonoverlatratio/yoverxratio
    
    # corrected axes limits, depending on which axis is changed
    latrangenew = [meanlat-dlatnew,meanlat+dlatnew]
    lonrangenew = [meanlon-dlonnew,meanlon+dlonnew]
    
    # set new axis limits for the axis specified by "changeaxis"
    if changeaxis.lower() == 'x':
        ax.set_xlim(lonrangenew)
    elif changeaxis.lower() == 'y':
        ax.set_ylim(latrangenew)


        
#function formatters add degrees E/W/N/S for axis labels of location plots
@mticker.FuncFormatter
def major_lon_formatter(x, pos):
    if x >= 0 and x <= 180: #eastern hemisphere
        hem = 'E'
    elif x < 0 and x > -180: #western hemisphere
        hem = 'W'
        x = abs(x)
    elif x <= -180: #WH plot overlap into EH
        x += 360
        hem = 'E'
    elif x > 180: #EH plot overlap into WH
        x = abs(x - 360)
        hem = 'W'
        
    return f"{x}$^\circ${hem}" # set current tick label
        
@mticker.FuncFormatter
def major_lat_formatter(y, pos):
    if y >= 0: #N hemisphere
        hem = 'N'
    elif y < 0: #S hemisphere
        hem = 'S'
        
    return f"{y}$^\circ${hem}" # set current tick label    


#apply function formatters for latitude and longitude to say degrees E/W/N/S
def setgeotick(ax):
    # ax.xaxis.set_major_locator(ticker.LogLocator(base=10, numticks=5))
    ax.xaxis.set_major_formatter(major_lon_formatter)
    ax.yaxis.set_major_formatter(major_lat_formatter)
    


    
    
# determine ocean basin, localized region from latitude/longitude
# region data from Natural Earth Physical Labels dataset
# https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-physical-labels/
def getoceanregion(lon,lat):
    
    #set point, initialize region output
    droppoint = Point(lon, lat)
    region = False
    
    #load shape file data
    regioninput = shread("data/regions/World_Seas_IHO_v3.shp")
    shapes = regioninput.shapes()
    
    #reading in list of first NANs
    nanind = []
    f_in = open('data/regions/IHO_seas.txt','r')
    for line in f_in:
        nanind.append(int(line.strip()))

    #searching for region containing lat/lon point, overwriting "region" variable if found
    for i in range(len(shapes)):
        if Polygon(shapes[i].points[:nanind[i]]).contains(droppoint):
            region = regioninput.record(i).NAME
            
    #if point wasn't in any seas distinguished by the shape file, logic to determine ocean basin
    if not region: 
        if lat >= 66.5:
            region = "Arctic Ocean"
        elif lat <= -60:
            region = "Southern Ocean"
        else:
            indianocn = Polygon([(20, -60), (20, 31), (100, 31), (100, 0), (146.817, 0), (146.817, -60)])
            pacificeh = Polygon([(146.817, -60), (146.817, 0), (100, 0), (100, 66.5), (180, 66.5), (180, -60)])
            pacificwh = Polygon([(-180, -60), (-180, 66.5), (-100, 66.5), (-100, 18), (-90, 18), (-90, 14), (-84, 14), (-84, 9), (-70, 9), (-70, -60)])
            
            if indianocn.contains(droppoint):
                region = "Indian Ocean"
                
            elif pacificeh.contains(droppoint) or pacificwh.contains(droppoint):
                if lat >= 0:
                    region = "Northern Pacific Ocean"
                else:
                    region = "Southern Pacific Ocean"
                    
            else: #only remaining option is atlantic
                if lat >= 0:
                    region = "Northern Atlantic Ocean"
                else:
                    region = "Southern Atlantic Ocean"
        
    return region
