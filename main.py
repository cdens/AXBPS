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
#

#import and run splash screen
from sys import exit

from platform import system as cursys

#add splash screen on Windows because of SLOW import speed due to drivers
if cursys() == 'Windows':
    
    #basic Qt5 bindings for app + splash screen
    from PyQt5.QtWidgets import QApplication, QSplashScreen
    from PyQt5.QtGui import QPixmap
    from PyQt5.QtCore import QCoreApplication, Qt
    
    #fixing QtWebEngine plugin issue
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    
    #making splash screen
    app = QApplication([])
    splash = QSplashScreen(QPixmap("lib/dropicon.png"))
    splash.show()
    
    #Imports necessary for main program
    import gui 
    
    #creates main program instance
    ex = gui.RunProgram()
    
    #kill splash screen
    splash.close()
    
else:
    #Qt5 binding for app only
    from PyQt5.QtWidgets import QApplication
        
    #Imports necessary for main program
    import gui 
    
    #creates main program instance
    app = QApplication([])
    ex = gui.RunProgram()


#executes main program (identical regardless of splash screen)
exit(app.exec_())


