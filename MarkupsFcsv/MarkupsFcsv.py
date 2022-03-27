import logging
import slicer

class MarkupsFcsv:
  def __init__(self, parent):
    parent.title = "Markups Fcsv File Writer"
    parent.categories = ["Utilities"]
    parent.dependencies = []
    parent.contributors = ["Steve Pieper, Isomics, Inc."]
    parent.helpText = """This is a file writer to allow Markups control points in Fcsv format"""
    parent.acknowledgementText = """
This module was developed by Steve Pieper for SlicerMorph. SlicerMorph was originally supported by an NSF/DBI grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 3D Morphology From Digital Biological Collections"
      awarded to Murat Maga (1759883), Adam Summers (1759637), and Douglas Boyer (1759839).
      https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false
""" # replace with organization, grant and thanks.
    parent.hidden = True
    self.parent = parent


class MarkupsFcsvFileWriter:
    def __init__(self, parent):
        self.parent = parent

    def description(self):
        return 'Markup points as fcsv'

    def fileType(self):
        return 'MarkupsFile'

    def canWriteObject(self, obj):
        return isinstance(obj, slicer.vtkMRMLMarkupsNode)

    def extensions(self, obj):
        return ['Fiducial csv (*.fcsv)']

    def write(self, properties):
        print("parent", self.parent)
        print("Write", properties)

        if (not "nodeID" in properties
                or not "fileName" in properties):
            logging.error("Bad properties passed to MarkupsFcsvFileWriter.write")
            return False
        markupNode = slicer.mrmlScene.GetNodeByID(properties["nodeID"])
        if not markupNode or not self.canWriteObject(markupNode):
            logging.error("Bad MarkupNode passed to MarkupsFcsvFileWriter.write")
            return False
        storageNode = slicer.vtkMRMLMarkupsFiducialStorageNode()
        slicer.mrmlScene.AddNode(storageNode)
        fileName = properties["fileName"]
        if fileName.endswith(".fcsv.fcsv"):
            fileName = fileName[:-5]
        properties["fileName"] = fileName
        storageNode.SetFileName(fileName)
        storageNode.SetURI(None)
        result = storageNode.WriteData(markupNode)
        if result:
            self.parent.writtenNodes = [markupNode.GetID()]
        return bool(result)
