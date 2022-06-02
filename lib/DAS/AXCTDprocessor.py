



    


    
    
# =============================================================================
#  AXCTD Processor class
# =============================================================================


class AXCTD_Processor:

                
        
    def run(self):
        
        
        # setting up thread while loop- terminates when user clicks "STOP" or audio file finishes processing
        self.status = 0
        
        #initializing audio buffer: self.pcmind = index of first point, demod_buffer contains numpy array of pcm data waiting to be demodulated
        self.bufferstartind = 0
        
        
        #MAIN PROCESSOR LOOP
        while self.keepgoing:    
            
            #calculating end of next slice of PCM data for signal level calcuation and demodulation
            e = self.demodbufferstartind + self.pointsperloop
            
            if self.numpoints - self.demodbufferstartind < self.fs: #within 1 second of file end
                self.keepgoing = False
                return
            elif e >= self.numpoints: #terminate loop if at end of file
                e = self.numpoints - 1
            
            #add next round of PCM data to buffer for signal calculation and demodulation
            # self.demod_buffer = np.append(self.demod_buffer, self.audiostream[self.demodbufferstartind:e])
            self.demod_buffer = self.audiostream[self.demodbufferstartind:e]
            
            
            
            
                                    
            


        
        
        