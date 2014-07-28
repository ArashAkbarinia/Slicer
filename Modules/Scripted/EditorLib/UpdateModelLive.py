import os
import re
import math
from __main__ import qt
from __main__ import ctk
from __main__ import vtk
import vtkITK
from __main__ import slicer
import ColorBox
import EditUtil

#########################################################
#
#
comment = """

  UpdateModelLive handles the functionality of building
  model from the degmented images.

# TODO :
"""
#
#########################################################

class UpdateModelLive(object):
  """helper box class"""

  def __init__(self, EditUtil, IsBuildLive = False, IsThreeVolumes = False):
    """the initi function"""
    self.editUtil = EditUtil

    # mrml volume node instances
    self.mergeAxi = None
    self.mergeSag = None
    self.mergeCor = None
    # pairs of (node instance, observer tag number)
    self.observerTags = []

    # filters
    self.ExtractVoi = vtk.vtkExtractVOI()
    self.ImageThresholdFilter = vtk.vtkImageThreshold()
    self.ExternalContourFilter = vtkITK.vtkITKExternalContourFilter()

    self.IsBuildLive = IsBuildLive
    self.IsThreeVolumes = IsThreeVolumes
    self.initialise()

  def cleanup(self):
    """what to do on exit"""
    for tagpair in self.observerTags:
      tagpair[0].RemoveObserver(tagpair[1])
    self.initialise()

  def getRealScalarRange(self, Image):
    if not Image:
      return []
    AbsScalarRange = Image.GetImageData().GetScalarRange()
    thresholder = vtk.vtkImageThreshold()
    thresholder.SetNumberOfThreads(1)
    RealScalarRange = []
    for i in xrange(int(AbsScalarRange[0]), int(AbsScalarRange[1]) + 1):
      if vtk.VTK_MAJOR_VERSION <= 5:
        thresholder.SetInput(Image.GetImageData())
      else:
        thresholder.SetInputConnection(Image.GetImageDataConnection())
      thresholder.SetInValue(i)
      thresholder.SetInValue(i)
      thresholder.SetOutValue(0)
      thresholder.ReplaceInOn()
      thresholder.ReplaceOutOn()
      thresholder.ThresholdBetween(i, i)
      thresholder.SetOutputScalarType(Image.GetImageData().GetScalarType())
      thresholder.Update()
      if thresholder.GetOutput().GetScalarRange() != (0.0, 0.0):
        RealScalarRange.append(i)
    return RealScalarRange

  def setMerge(self, merge, layoutName):
    """setter for merge volume"""
    if layoutName == 'Red':
      self.mergeAxi = merge
    if layoutName == 'Yellow':
      self.mergeSag = merge
    if layoutName == 'Green':
      self.mergeCor = merge

    if layoutName == 'Red':
      if self.mergeAxi:
        tag = self.mergeAxi.AddObserver(vtk.vtkCommand.ModifiedEvent, self.mergeAxiUpdated)
        self.observerTags.append((self.mergeAxi, tag))
        ScalarRange = self.mergeAxi.GetImageData().GetScalarRange()
        self.ScalarRangeAxi = int(ScalarRange[1])
        self.initialiseContoursAxi()
        if self.IsBuildLive:
          self.IsOriginalAxiContoursExtracted = True
          RealAxiRange = self.getRealScalarRange(self.mergeAxi)
          for i in RealAxiRange:
            self.updateModelFromAxi(i)
    if layoutName == 'Yellow':
      if self.mergeSag:
        tag = self.mergeSag.AddObserver(vtk.vtkCommand.ModifiedEvent, self.mergeSagUpdated)
        self.observerTags.append((self.mergeSag, tag))
        ScalarRange = self.mergeSag.GetImageData().GetScalarRange()
        self.ScalarRangeSag = int(ScalarRange[1])
        self.initialiseContoursSag()
        if self.IsBuildLive:
          self.IsOriginalSagContoursExtracted = True
          RealSagRange = self.getRealScalarRange(self.mergeSag)
          for i in RealSagRange:
            self.updateModelFromSag(i)
    if layoutName == 'Green':
      if self.mergeCor:
        tag = self.mergeCor.AddObserver(vtk.vtkCommand.ModifiedEvent, self.mergeCorUpdated)
        self.observerTags.append((self.mergeCor, tag))
        ScalarRange = self.mergeCor.GetImageData().GetScalarRange()
        self.ScalarRangeCor = int(ScalarRange[1])
        self.initialiseContoursCor()
        if self.IsBuildLive:
          self.IsOriginalCorContoursExtracted = True
          RealCorRange = self.getRealScalarRange(self.mergeCor)
          for i in RealCorRange:
            self.updateModelFromCor(i)

  def onBuildStrucures(self):
    """merging the segmentation into point cloud"""
    rows = self.structures.rowCount()
    FinishedLabels = []
    for i in range(rows):
      LabelNumber = int(self.structures.item(i, 0).text())
      if LabelNumber not in FinishedLabels:
        FinishedLabels.append(LabelNumber)
        VolumeNames = self.GetSelectedStructuresByLabel(LabelNumber)
        VolumeNodes = []

        for VolumeName in VolumeNames:
          Nodes = slicer.mrmlScene.GetNodesByName(VolumeName)
          if Nodes.GetNumberOfItems() == 1:
            VolumeNode = Nodes.GetItemAsObject(0)
            if VolumeNode:
              VolumeNodes.append(VolumeNode)
          else:
            print("WARNING: The node %s for creating model not one, it's %s" % (VolumeName, str(Nodes.GetNumberOfItems())))

        self.buildAddedModels(LabelNumber, VolumeNodes)

  def getContourPoints2D(self, image, LabelNumber, SliceNumber):
    """extracting the 2D contours"""
    #print('getContourPoints2D', LabelNumber)
    if vtk.VTK_MAJOR_VERSION <= 5:
      self.ImageThresholdFilter.SetInput(image)
    else:
      self.ImageThresholdFilter.SetInputData(image)
    self.ImageThresholdFilter.ThresholdBetween(LabelNumber, LabelNumber)
    self.ImageThresholdFilter.SetInValue(1)
    self.ImageThresholdFilter.SetOutValue(0)
    self.ImageThresholdFilter.Update()
    ThresholdedImage = vtk.vtkImageData()
    ThresholdedImage.DeepCopy(self.ImageThresholdFilter.GetOutput())

    # NOTE: in case of one image for multiple structures, there is ambiguity when a structure is inside another onEnter
    # and it touches the border. It's not possible to fill the holes. For medical reasons it's better to have multiple images.
    if vtk.VTK_MAJOR_VERSION <= 5:
      self.ExternalContourFilter.SetInput(ThresholdedImage)
    else:
      self.ExternalContourFilter.SetInputData(ThresholdedImage)
    self.ExternalContourFilter.SetSliceNumber(SliceNumber)
    self.ExternalContourFilter.Update()

    ContourPixels = vtk.vtkPoints()
    ContourPixels.DeepCopy(self.ExternalContourFilter.GetOutput().GetPoints())
    return ContourPixels

  def getNumberOfContourPixels(self, ContourPixels, dim, exc = -1):
    """computes the number pixels in the list of contour pixels"""
    nPixels = 0
    for i in range(exc) + range(exc + 1, dim):
      nPixels = nPixels + ContourPixels[i].GetNumberOfPoints()
    return nPixels

  def getContourPoints3D(self, volume, ContourPoints, ContourPixels, LabelNumber, CurrentSlice = -1):
    """attaching the 2D contours in a 3D volume"""
    #print('getContourPoints3D', LabelNumber)
    volumeImageData = volume.GetImageData()
    dim = volumeImageData.GetDimensions()
    imageOrigin = volume.GetOrigin()
    imageSpacing = volume.GetSpacing()

    if vtk.VTK_MAJOR_VERSION <= 5:
      self.ExtractVoi.SetInput(volumeImageData)
    else:
      self.ExtractVoi.SetInputData(volumeImageData)

    if CurrentSlice == -1:
      SlicesRange = range(dim[2])
      nPixels = 0
    else:
      SlicesRange = range(CurrentSlice, CurrentSlice + 1)
      nPixels = self.getNumberOfContourPixels(ContourPixels.get(LabelNumber), dim[2], CurrentSlice)
    for i in SlicesRange:
      self.ExtractVoi.SetVOI(0, dim[0], 0, dim[1], i, i)
      self.ExtractVoi.Update()
      currentSlice = vtk.vtkImageData()
      currentSlice.DeepCopy(self.ExtractVoi.GetOutput())
      ContourPixels.get(LabelNumber)[i] = self.getContourPoints2D(currentSlice, LabelNumber, i)
      nPixels = nPixels + ContourPixels.get(LabelNumber)[i].GetNumberOfPoints()

    AllContourPixels = vtk.vtkPoints()
    AllContourPixels.SetNumberOfPoints(nPixels)
    j = 0
    for i in range(dim[2]):
      AllContourPixels = self.appendPoints(AllContourPixels, ContourPixels.get(LabelNumber)[i], j)
      j = j + ContourPixels.get(LabelNumber)[i].GetNumberOfPoints()

    ContourPoints.update({LabelNumber : vtk.vtkPoints()})
    IJKToRASMat = vtk.vtkMatrix4x4()
    volume.GetIJKToRASMatrix(IJKToRASMat)
    IJKToRASTransform = vtk.vtkTransform()
    IJKToRASTransform.SetMatrix(IJKToRASMat)
    IJKToRASTransform.TransformPoints(AllContourPixels, ContourPoints.get(LabelNumber))

    return [ContourPoints, ContourPixels]

  def appendPoints(self, ContourPoints, AppendPoints, CurrentIndex):
    """append one vtkPoints to another one"""
    for j in range(AppendPoints.GetNumberOfPoints()):
      ContourPoints.InsertPoint(CurrentIndex, AppendPoints.GetPoint(j))
      CurrentIndex = CurrentIndex + 1
    return ContourPoints

  def copyViewPointsInAll(self, LabelNumber, ContourPoints):
    """copies all the contour points to one vtkPoints"""
    NumberOfPoints = 0
    for ContourPoint in ContourPoints:
      CurrentPoints = ContourPoint.get(LabelNumber)
      if CurrentPoints == None:
        CurrentPoints = vtk.vtkPoints()
      NumberOfPoints = NumberOfPoints + CurrentPoints.GetNumberOfPoints()

    ContourPointsAll = vtk.vtkPoints()
    ContourPointsAll.SetNumberOfPoints(NumberOfPoints)
    CurrentIndex = 0
    for ContourPoint in ContourPoints:
      CurrentPoints = ContourPoint.get(LabelNumber)
      if CurrentPoints == None:
        CurrentPoints = vtk.vtkPoints()
      ContourPointsAll = self.appendPoints(ContourPointsAll, CurrentPoints, CurrentIndex)
      CurrentIndex = CurrentIndex + CurrentPoints.GetNumberOfPoints()

    return ContourPointsAll

  def findActiveSlice(self):
    """checks all the three layouts to find the correct active slice"""
    dims = self.mergeAxi.GetImageData().GetDimensions()
    for LayoutName in {'Red', 'Yellow', 'Green'}:
      BackgroundLayer = slicer.app.layoutManager().sliceWidget(LayoutName).sliceLogic().GetBackgroundLayer()
      xyToIJK = BackgroundLayer.GetXYToIJKTransform()
      ijk = xyToIJK.TransformDoublePoint((0, 0, 0))
      print  ijk, 'there'
      activeSlice = int(round(ijk[2]))
      if activeSlice >= 0 and activeSlice < dims[2]:
        return activeSlice

  def getActiveSlice(self, LayoutName):
    if not self.IsThreeVolumes:
      activeSlice = self.findActiveSlice()
    else:
      BackgroundLayer = slicer.app.layoutManager().sliceWidget(LayoutName).sliceLogic().GetBackgroundLayer()
      xyToIJK = BackgroundLayer.GetXYToIJKTransform()
      ijk = xyToIJK.TransformDoublePoint((0, 0, 0))
      print ijk, 'here'
      activeSlice = int(round(ijk[2]))
    return activeSlice

  def initialiseLabel(self, LabelNumber, ArePixelsChanged = False):
    if LabelNumber not in self.AddedLabels:
      self.AddedLabels.append(LabelNumber)
    if self.mergeAxi and self.ContourPixelsAxi0n.get(LabelNumber) == None:
      dim = self.mergeAxi.GetImageData().GetDimensions()
      self.ContourPixelsAxi0n.update({LabelNumber : [vtk.vtkPoints()] * dim[2]})
      self.ContourPointsAxi.update({LabelNumber : vtk.vtkPoints()})
      self.ContourPointsAxiChanged.update({LabelNumber : ArePixelsChanged})
    if self.mergeSag and self.ContourPixelsSag0n.get(LabelNumber) == None:
      dim = self.mergeSag.GetImageData().GetDimensions()
      self.ContourPixelsSag0n.update({LabelNumber : [vtk.vtkPoints()] * dim[2]})
      self.ContourPointsSag.update({LabelNumber : vtk.vtkPoints()})
      self.ContourPointsSagChanged.update({LabelNumber : ArePixelsChanged})
    if self.mergeCor and self.ContourPixelsCor0n.get(LabelNumber) == None:
      dim = self.mergeCor.GetImageData().GetDimensions()
      self.ContourPixelsCor0n.update({LabelNumber : [vtk.vtkPoints()] * dim[2]})
      self.ContourPointsCor.update({LabelNumber : vtk.vtkPoints()})
      self.ContourPointsCorChanged.update({LabelNumber : ArePixelsChanged})

  def mergeAxiUpdated(self, caller, event):
    CurrentLabelNumber = self.editUtil.getLabel()
    CurrentSlice = self.getActiveSlice('Red')
    self.updateModelFromAxi(CurrentLabelNumber, CurrentSlice)

  def mergeSagUpdated(self, caller, event):
    CurrentLabelNumber = self.editUtil.getLabel()
    CurrentSlice = self.getActiveSlice('Yellow')
    self.updateModelFromSag(CurrentLabelNumber, CurrentSlice)

  def mergeCorUpdated(self, caller, event):
    CurrentLabelNumber = self.editUtil.getLabel()
    CurrentSlice = self.getActiveSlice('Green')
    self.updateModelFromCor(CurrentLabelNumber, CurrentSlice)

  def updateDefaultMerges(self, LabelNumber):
    """updates the models of the current merges"""
    print 'updateDefaultMerges'
    ContourPointsAll = self.copyViewPointsInAll(LabelNumber, [self.ContourPointsAxi, self.ContourPointsSag, self.ContourPointsCor])
    self.updateModel(ContourPointsAll, LabelNumber)

  def updateModelFromAxi(self, CurrentLabelNumber, CurrentSlice = -1):
    """updates the model based on the changes in axial view"""
    print 'updateModelFromAxi'
    if CurrentLabelNumber == 0:
      LabelRange = self.ContourPixelsAxi0n.iterkeys()
    else:
      LabelRange = range(CurrentLabelNumber, CurrentLabelNumber + 1)
    for LabelNumber in LabelRange:
      self.initialiseLabel(LabelNumber)
      self.ContourPointsAxiChanged.update({LabelNumber : True})
      if self.IsBuildLive:
        self.ContourPointsAxi, self.ContourPixelsAxi0n = self.getContourPoints3D(self.mergeAxi, self.ContourPointsAxi, self.ContourPixelsAxi0n, LabelNumber, CurrentSlice)
        self.updateDefaultMerges(LabelNumber)

  def updateModelFromSag(self, CurrentLabelNumber, CurrentSlice = -1):
    """updates the model based on the changes in sagittal view"""
    print 'updateModelFromSag'
    if CurrentLabelNumber == 0:
      LabelRange = self.ContourPixelsSag0n.iterkeys()
    else:
      LabelRange = range(CurrentLabelNumber, CurrentLabelNumber + 1)
    for LabelNumber in LabelRange:
      self.initialiseLabel(LabelNumber)
      self.ContourPointsSagChanged.update({LabelNumber : True})
      if self.IsBuildLive:
        self.ContourPointsSag, self.ContourPixelsSag0n = self.getContourPoints3D(self.mergeSag, self.ContourPointsSag, self.ContourPixelsSag0n, LabelNumber, CurrentSlice)
        self.updateDefaultMerges(LabelNumber)

  def updateModelFromCor(self, CurrentLabelNumber, CurrentSlice = -1):
    """updates the model based on the changes in coronal view"""
    print 'updateModelFromCor'
    if CurrentLabelNumber == 0:
      LabelRange = self.ContourPixelsCor0n.iterkeys()
    else:
      LabelRange = range(CurrentLabelNumber, CurrentLabelNumber + 1)
    for LabelNumber in LabelRange:
      self.initialiseLabel(LabelNumber)
      self.ContourPointsCorChanged.update({LabelNumber : True})
      if self.IsBuildLive:
        self.ContourPointsCor, self.ContourPixelsCor0n = self.getContourPoints3D(self.mergeCor, self.ContourPointsCor, self.ContourPixelsCor0n, LabelNumber, CurrentSlice)
        self.updateDefaultMerges(LabelNumber)

  def addToAddedLabels(self, NewLabels):
    print 'addToAddedLabels'
    for LabelNumber in NewLabels:
      if LabelNumber not in self.AddedLabels:
        self.initialiseLabel(LabelNumber, True)

  def buildModelForAllLabels(self):
    print 'buildModelForAllLabels'
    if not self.IsOriginalAxiContoursExtracted:
      RealAxiRange = self.getRealScalarRange(self.mergeAxi)
      self.addToAddedLabels(RealAxiRange)
      self.IsOriginalAxiContoursExtracted = True
    if not self.IsOriginalSagContoursExtracted:
      RealSagRange = self.getRealScalarRange(self.mergeSag)
      self.addToAddedLabels(RealSagRange)
      self.IsOriginalSagContoursExtracted = True
    if not self.IsOriginalCorContoursExtracted:
      RealCorRange = self.getRealScalarRange(self.mergeCor)
      self.addToAddedLabels(RealCorRange)
      self.IsOriginalCorContoursExtracted = True
    for LabelNumber in self.AddedLabels:
      self.buildModelFromScratch(LabelNumber, self.mergeAxi, self.mergeSag, self.mergeCor)

  def buildModelFromScratch(self, LabelNumber, VolumeAxi, VolumeSag, VolumeCor):
    """building the model based on all the segmentations"""
    print 'buildModelFromScratch'
    self.initialiseLabel(LabelNumber)
    UpdateTheModel = False
    if self.ContourPointsAxiChanged.get(LabelNumber) and VolumeAxi:
      self.ContourPointsAxi, self.ContourPixelsAxi0n = self.getContourPoints3D(VolumeAxi, self.ContourPointsAxi, self.ContourPixelsAxi0n, LabelNumber)
      UpdateTheModel = True
    if self.ContourPointsSagChanged.get(LabelNumber) and VolumeSag:
      self.ContourPointsSag, self.ContourPixelsSag0n = self.getContourPoints3D(VolumeSag, self.ContourPointsSag, self.ContourPixelsSag0n, LabelNumber)
      UpdateTheModel = True
    if self.ContourPointsCorChanged.get(LabelNumber) and VolumeCor:
      self.ContourPointsCor, self.ContourPixelsCor0n = self.getContourPoints3D(VolumeCor, self.ContourPointsCor, self.ContourPixelsCor0n, LabelNumber)
      UpdateTheModel = True
    if UpdateTheModel:
      self.updateDefaultMerges(LabelNumber)

  def buildAddedModels(self, LabelNumber, VolumeNodes):
    """builds a model for all the added models into the pre-structure section"""
    ContourPoints = []
    for VolumeNode in VolumeNodes:
      dim = VolumeNode.GetImageData().GetDimensions()
      NodeContourPixels = {LabelNumber : [vtk.vtkPoints()] * dim[2]}
      NodeContourPoints = {LabelNumber : vtk.vtkPoints()}
      NodeContourPoints, NodeContourPixels = self.getContourPoints3D(VolumeNode, NodeContourPoints, NodeContourPixels, LabelNumber)
      ContourPoints.append(NodeContourPoints)
    ContourPointsAll = self.copyViewPointsInAll(LabelNumber, ContourPoints)
    self.updateModel(ContourPointsAll, LabelNumber)

  def updateModel(self, ContourPointsAll, LabelNumber):
    """updates the model"""
    print 'updateModel'
    self.ContourPointsAxiChanged.update({LabelNumber : False})
    self.ContourPointsSagChanged.update({LabelNumber : False})
    self.ContourPointsCorChanged.update({LabelNumber : False})

    if ContourPointsAll.GetNumberOfPoints() > 0:
      self.statusText("updating model for label %d with %d points" % (LabelNumber, ContourPointsAll.GetNumberOfPoints(),))
      ContourPoly = vtk.vtkPolyData()
      ContourPoly.SetPoints(ContourPointsAll)

      PlyWriter = vtk.vtkPLYWriter()
      if vtk.VTK_MAJOR_VERSION <= 5:
        PlyWriter.SetInput(ContourPoly)
      else:
        PlyWriter.SetInputData(ContourPoly)
      PlyWriter.SetFileName('polydata_' + str(LabelNumber) + '.ply')
      PlyWriter.Write()

      #ContourPolyAxi = vtk.vtkPolyData()
      #ContourPolyAxi.SetPoints(self.ContourPointsAxi.get(LabelNumber))
      #PlyWriter.SetInput(ContourPolyAxi)
      #PlyWriter.SetFileName('polydata_axi_' + str(LabelNumber) + '.ply')
      #PlyWriter.Write()

      #ContourPolySag = vtk.vtkPolyData()
      #ContourPolySag.SetPoints(self.ContourPointsSag.get(LabelNumber))
      #PlyWriter.SetInput(ContourPolySag)
      #PlyWriter.SetFileName('polydata_sag_' + str(LabelNumber) + '.ply')
      #PlyWriter.Write()

      #ContourPolyCor = vtk.vtkPolyData()
      #ContourPolyCor.SetPoints(self.ContourPointsCor.get(LabelNumber))
      #PlyWriter.SetInput(ContourPolyCor)
      #PlyWriter.SetFileName('polydata_cor_' + str(LabelNumber) + '.ply')
      #PlyWriter.Write()

      print 'Starting the reconstruction filter'
      self.statusText("Starting to reconstruct the surface")
      ReconstructionFilter = slicer.vtkPowerCrustSurfaceReconstruction()
      if vtk.VTK_MAJOR_VERSION <= 5:
        ReconstructionFilter.SetInput(ContourPoly)
      else:
        ReconstructionFilter.SetInputData(ContourPoly)
      ReconstructionFilter.Update()
      self.statusText('Finishing the reconstruction filter')
      print 'Finishing the reconstruction filter'

      CurrentModelPoly = vtk.vtkPolyData()
      CurrentModelPoly.DeepCopy(ReconstructionFilter.GetOutput())

      self.ModelPoly.update({LabelNumber : CurrentModelPoly})
      self.createModel(CurrentModelPoly, LabelNumber)

  def createModel(self, ModelPoly, LabelNumber):
    """initiate the master model"""
    mnode = self.mnode.get(LabelNumber)
    if mnode == None:
      NodeName = 'SegmentationModel_' + str(LabelNumber)
      mnode = self.getNodeByName(NodeName)
      if mnode == None:
        dnode = slicer.vtkMRMLModelDisplayNode()
        dnode.SetColor(self.editUtil.getLabelColorByIndex(LabelNumber)[:3])
        dnode.SetVisibility(1)
        dnode.SetOpacity(0.5)
        slicer.mrmlScene.AddNode(dnode)

        mnode = slicer.vtkMRMLModelNode()
        mnode.SetName(NodeName)
        mnode.SetAndObserveDisplayNodeID(dnode.GetID())
        mnode.SetScene(slicer.mrmlScene)
        slicer.mrmlScene.AddNode(mnode)
      self.mnode.update({LabelNumber : mnode})

    mnode.SetAndObservePolyData(ModelPoly)

  def GetSelectedStructures(self):
    VolumeNames = []
    rows = self.structures.rowCount()
    for i in range(rows):
      if self.structures.item(i, 0).checkState() == 2:
        VolumeNames.append(self.structures.item(i, 2).text())
    return VolumeNames

  def GetSelectedStructuresByDirection(self, LayoutName):
    if not self.IsThreeVolumes:
      return self.GetSelectedStructures()
    VolumeNames = []
    rows = self.structures.rowCount()
    for i in range(rows):
      LayoutNameI = self.structures.item(i, 4).text()
      if LayoutNameI == LayoutName and self.structures.item(i, 0).checkState() == 2:
        VolumeNames.append(self.structures.item(i, 2).text())
    return VolumeNames

  def GetSelectedStructuresByLabel(self, LabelNumber):
    VolumeNames = []
    rows = self.structures.rowCount()
    for i in range(rows):
      LabelNumberI = int(self.structures.item(i, 0).text())
      if LabelNumber == LabelNumberI and self.structures.item(i, 0).checkState() == 2:
        VolumeNames.append(self.structures.item(i, 2).text())
    return VolumeNames

  def initialise(self):
    """reinitialises the class variables"""
    self.setMerge(None, 'Red')
    self.setMerge(None, 'Yellow')
    self.setMerge(None, 'Green')
    # models
    self.ModelPoly = {}
    self.mnode = {}
    self.AddedLabels = []
    self.ScalarRangeAxi = 0
    self.ScalarRangeSag = 0
    self.ScalarRangeCor = 0
    self.initialiseContoursAxi()
    self.initialiseContoursSag()
    self.initialiseContoursCor()

  def removeUnusedLabels(self):
    MaxScalarRange = max(self.ScalarRangeAxi, self.ScalarRangeSag, self.ScalarRangeCor)
    for LabelNumber in self.AddedLabels:
      if LabelNumber > MaxScalarRange:
        self.AddedLabels.remove(LabelNumber)

  def initialiseContoursAxi(self):
    self.IsOriginalAxiContoursExtracted = False
    self.ContourPixelsAxi0n = {}
    self.ContourPointsAxi = {}
    self.ContourPointsAxiChanged = {}
    self.removeUnusedLabels()

  def initialiseContoursSag(self):
    self.IsOriginalSagContoursExtracted = False
    self.ContourPixelsSag0n = {}
    self.ContourPointsSag = {}
    self.ContourPointsSagChanged = {}
    self.removeUnusedLabels()

  def initialiseContoursCor(self):
    self.IsOriginalCorContoursExtracted = False
    self.ContourPixelsCor0n = {}
    self.ContourPointsCor = {}
    self.ContourPointsCorChanged = {}
    self.removeUnusedLabels()

  def getNodeByName(self, name):
    """get the first MRML node that has the given name
    - use a regular expression to match names post-pended with numbers"""

    slicer.mrmlScene.InitTraversal()
    node = slicer.mrmlScene.GetNextNode()
    while node:
      try:
        nodeName = node.GetName()
        if nodeName.find(name) == 0:
          # prefix matches, is the rest all numbers?
          if nodeName == name or nodeName[len(name):].isdigit():
            return node
      except:
        pass
      node = slicer.mrmlScene.GetNextNode()
    return None

  def errorDialog(self, message):
    self.dialog = qt.QErrorMessage()
    self.dialog.setWindowTitle("Editor")
    self.dialog.showMessage(message)

  def confirmDialog(self, message):
    result = qt.QMessageBox.question(slicer.util.mainWindow(), 'Editor', message, qt.QMessageBox.Ok, qt.QMessageBox.Cancel)
    return result == qt.QMessageBox.Ok

  def statusText(self, text):
    slicer.util.showStatusMessage(text, 100)