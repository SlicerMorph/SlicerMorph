#This is a sample script that will read a raw landmark file, skip header, and import fiducials into Slicer

# Create a markups node for imported points
fiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
fiducialNode.SetName("importedLandmarks")
slicer.mrmlScene.AddNode(fiducialNode)
fiducialNode.CreateDefaultDisplayNodes()

# set landmark filename and length of header
landmarkFileName = "D:/SlicerWorkspace/SampleData/Ggg2F1400landmarks.pts"
header = 2  #number of lines in the header

# read landmarks
landmarkFile = open(landmarkFileName, "r")
lines = landmarkFile.readlines()
landmarkFile.close()

#iterate through list of and place in markups node
for i in range(header,len(lines)-1):
  # in this file format, lines contain [name, x-coordinate, y-coordinate, z-coordinate]
  # by default, split command splits by whitespace
  lineData = lines[i].split()
  if len(lineData) == 4:
    coordinates = [float(lineData[1]), float(lineData[2]), float(lineData[3])]
    name = lineData[0]
    fiducialNode.AddFiducialFromArray(coordinates, name)
  else: 
    print "error" 

