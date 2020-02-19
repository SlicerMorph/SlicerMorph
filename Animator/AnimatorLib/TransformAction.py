
import numpy

"""

This is a placeholder for Animator plugins
for transforms.

For testing:

import os
pathPrefix = "/Users/pieper/slicer/latest/Slicer"
moduleName = "Animator"

modulePath = os.path.join(pathPrefix+moduleName, moduleName, moduleName+".py")

factoryManager = slicer.app.moduleManager().factoryManager()

factoryManager.registerModule(qt.QFileInfo(modulePath))

factoryManager.loadModules([moduleName,])

slicer.util.selectModule(moduleName)

"""

class animateThinPlate(object):

    def __init__(self):
        self.name = "preduraUS_resampledTointraopUS_reseampled-ThinPlate"

        self.transformNode = slicer.util.getNode(self.name)

        self.transform = self.transformNode.GetTransformToParent()

        self.sourcePoints = self.transform.GetSourceLandmarks()
        self.targetPoints = self.transform.GetTargetLandmarks()

        self.sourceArray = vtk.util.numpy_support.vtk_to_numpy(self.sourcePoints.GetData())
        self.targetArray = vtk.util.numpy_support.vtk_to_numpy(self.targetPoints.GetData())
        self.originalTargetArray = numpy.array(self.targetArray)
        self.deltaArray = self.targetArray - self.sourceArray

    def animationFrame(self):
      if self.frame <= self.frames:
        interpolation = self.frame / (self.frames * 1.)
        multiplier = math.cos(2. * math.pi * interpolation)
        self.targetArray[:] = self.sourceArray + multiplier * self.deltaArray
        self.targetPoints.GetData().Modified()
        self.transformNode.Modified()
        self.transformNode.InvokeCustomModifiedEvent(slicer.vtkMRMLTransformableNode.TransformModifiedEvent)
        qt.QTimer.singleShot(20, self.animationFrame)
      self.frame += 1

    def animate(self):
        self.frames = 20
        self.frame = 0
        self.animationFrame()

try:
    a = animateThinPlate()
    a.animate()
except Exception:
    pass

