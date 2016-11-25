import getter as hgg 
import json
import numpy as np

def makeTile(zoomLevel,x_pos,y_pos,dset):
	info = dset[1]
	divisor = 2 ** zoomLevel
	start1 = x_pos * info['max_width'] / divisor
	end1 = (x_pos + 1) * info['max_width'] / divisor
	start2 = y_pos * info['max_width'] / divisor
	end2 = (y_pos + 1) * info['max_width'] / divisor
	data = hgg.getData3(dset[0],zoomLevel,start1,end1-1,start2,end2-1)	
	df = data[data['genome_start'] >= start1]
        binsize = 2 ** (info['max_zoom'] - zoomLevel) * 1000
        j = (df['genome_start'].values - start1) // binsize
        i = (df['genome_end'].values - start2) // binsize
        v = np.nan_to_num(df['balanced'].values)
        m = (end1 - start1) // binsize
        n =  (end2 - start2) // binsize
        zi = zip(zip(i,j),v)
        tile_bins = dict(zi)
	denseOutputArray = []
	for i in range(0,256):
		for j in range(0,256):
			if tile_bins.has_key((i,j)):
				denseOutputArray.append(tile_bins[(i,j)])
			else:
				denseOutputArray.append(0)
	return np.array(denseOutputArray, dtype=np.float32)
