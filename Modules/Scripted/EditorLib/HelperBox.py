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

  HelperBox is a wrapper around a set of Qt widgets and other
  structures to manage the slicer3 segmentation helper box.

# TODO :
"""
#
#########################################################

class HelperBox(object):
  """helper box class"""

  def __init__(self, parent=None, IsThreeVolume = False):
    """the initi function"""
    self.editUtil = EditUtil.EditUtil()

    # mrml volume node instances
    self.masterAxi = None
    self.masterSag = None
    self.masterCor = None
    self.mergeAxi = None
    self.mergeSag = None
    self.mergeCor = None
    # pairs of (node instance, observer tag number)
    self.observerTags = []
    # slicer helper class
    self.applicationLogic = slicer.app.applicationLogic()
    self.volumesLogic = slicer.modules.volumes.logic()
    self.colorLogic = slicer.modules.colors.logic()
    # pseudo signals 
    # - python callable that gets True or False
    self.mergeValidCommand = None
    self.selectCommand = None

    self.IsThreeVolume = IsThreeVolume

    if not parent:
      self.parent = slicer.qMRMLWidget()
      self.parent.setLayout(qt.QVBoxLayout())
      self.parent.setMRMLScene(slicer.mrmlScene)
      self.create()
      self.parent.show()
    else:
      self.parent = parent
      self.create()

    self.threeVolumesCBoxChanged()

  def onEnter(self):
    """on enter what to do"""
    self.initialiseMasterAndMerge()

    # new scene, node added or removed events
    tag = slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.EndImportEvent, self.HadndleImportEvent)
    self.observerTags.append( (slicer.mrmlScene, tag) )
    tag = slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.EndCloseEvent, self.HandleCloseEvent)
    self.observerTags.append( (slicer.mrmlScene, tag) )
    return

  def HadndleImportEvent(self, caller, event):
    self.initialiseMasterAndMerge()

  def HandleCloseEvent(self, caller, event):
    self.initialise()

  def initialiseMasterAndMerge(self):
    if self.threeVolumesCBox.checked:
      if not self.masterAxi:
        self.masterAxiSelector.setCurrentNode(self.selectInitialMaster('ax'))
      else:
        self.updateViewBackground('Red')
      if not self.mergeAxi:
        self.checkAndSetMerge('Red')
      else:
        self.updateViewLabel('Red')

      if not self.masterSag:
        self.masterSagSelector.setCurrentNode(self.selectInitialMaster('sag'))
      else:
        self.updateViewBackground('Yellow')
      if not self.mergeSag:
        self.checkAndSetMerge('Yellow')
      else:
        self.updateViewLabel('Yellow')

      if not self.masterCor:
        self.masterCorSelector.setCurrentNode(self.selectInitialMaster('cor'))
      else:
        self.updateViewBackground('Green')
      if not self.mergeCor:
        self.checkAndSetMerge('Green')
      else:
        self.updateViewLabel('Green')

    else:
      if not self.masterAxi:
        self.masterAxiSelector.setCurrentNode(self.selectInitialMaster(''))
      else:
        self.updateViewBackground('Red')
      if not self.mergeAxi:
        self.checkAndSetMerge('Red')
      else:
        self.updateViewLabel('Red')

  def onExit(self):
    """what to do on exit"""
    for tagpair in self.observerTags:
      tagpair[0].RemoveObserver(tagpair[1])

  def cleanup(self):
    """cleanign up the resources"""
    # TODO: do we need a better cleaning up?
    self.onExit()
    if self.colorBox:
      self.colorBox.cleanup()

  def createMerge(self, layoutName):
    """create a merge volume for the current master"""
    if not self.getMaster(layoutName):
      # should never happen
      self.errorDialog( "Cannot create merge volume without master" )
      return

    mergeName = self.mergeLineEdit.text

    merge = self.volumesLogic.CreateAndAddLabelVolume(slicer.mrmlScene, self.getMaster(layoutName), mergeName)
    merge.GetDisplayNode().SetAndObserveColorNodeID(self.colorSelector.currentNodeID)

    self.setMerge(merge, layoutName)

    # FIXME: I think it potentially can mix up the label selectors?
    if self.labelSelector:
      self.labelSelector.setCurrentNode(self.getMerge(layoutName))
    # TODO: is this necessary?
    self.notifyOtherModules()

  def checkForMasterErrors(self, master):
    """Verify that master volume is all right. Returns warning text of empty string if none."""
    if not master:
      return "Missing master volume"
    if not master.GetImageData():
      return "Missing image data"
    return ""

  def checkForMergeErrors(self, merge):
    """Verify that merge volume is all right. Returns warning text of empty string if none."""
    if not merge:
      return "Missing merge volume"
    if not merge.GetImageData():
      return "Missing image data"
    if merge.GetClassName() != "vtkMRMLScalarVolumeNode" or not merge.GetLabelMap():
      return "Selected merge label volume is not a label volume"
    return ""

  def getMasterSelector(self, layoutName):
    if layoutName == 'Red':
      return self.masterAxiSelector
    if layoutName == 'Yellow':
      return self.masterSagSelector
    if layoutName == 'Green':
      return self.masterCorSelector

  def setMaster(self, master, layoutName):
    """setter for merge volume"""
    if layoutName == 'Red':
      self.masterAxi = master
    elif layoutName == 'Yellow':
      self.masterSag = master
    elif layoutName == 'Green':
      self.masterCor = master
    self.updateViewBackground(layoutName)
    self.updateMergeButtons()

  def getMaster(self, layoutName):
    """getter for master volume"""
    if layoutName == 'Red':
      return self.masterAxi
    if layoutName == 'Yellow':
      return self.masterSag
    if layoutName == 'Green':
      return self.masterCor

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
    self.updateViewLabel(layoutName)
    self.updateMergeNames(layoutName)
    self.updateMergeButtons()

  def getMerge(self, layoutName):
    """getter for merge volume"""
    if layoutName == 'Red':
      return self.mergeAxi
    if layoutName == 'Yellow':
      return self.mergeSag
    if layoutName == 'Green':
      return self.mergeCor

  def updateMergeButtons(self):
    """update the set buttons based existence of master image"""
    self.buildMergesButton.setDisabled(not self.mergeAxi and not self.mergeSag and not self.mergeCor)
    self.setMergeAxiButton.setDisabled(not self.masterAxi)
    self.setMergeSagButton.setDisabled(not self.masterSag)
    self.setMergeCorButton.setDisabled(not self.masterCor)
    self.addMergeAxiButton.setDisabled(not self.masterAxi)
    self.addMergeSagButton.setDisabled(not self.masterSag)
    self.addMergeCorButton.setDisabled(not self.masterCor)
    self.splitMergeAxiButton.setDisabled(not self.masterAxi)
    self.splitMergeSagButton.setDisabled(not self.masterSag)
    self.splitMergeCorButton.setDisabled(not self.masterCor)

  def updatePrestructureButtons(self):
    """updates the states of buttons related to prestructure frame"""
    rows = self.structures.rowCount()
    self.deleteStructuresButton.setDisabled(rows == 0)
    self.mergeStructuresButton.setDisabled(rows == 0)
    self.buildStructuresButton.setDisabled(rows == 0)
    self.replaceModels.setDisabled(rows == 0)
    self.selectAllModelsCBox.setDisabled(rows == 0)

    if rows == 0:
      self.replaceModels.setChecked(False)
      self.selectAllModelsCBox.setChecked(False)

  def updateMergeNames(self, layoutName):
    """update the merge label names"""
    mergeVolume = self.getMerge(layoutName)
    if mergeVolume:
      mergeText = mergeVolume.GetName()
    else:
      mergeText = "None"
    if layoutName == 'Red':
      self.mergeAxiName.setText(mergeText)
    elif layoutName == 'Yellow':
      self.mergeSagName.setText(mergeText)
    elif layoutName == 'Green':
      self.mergeCorName.setText(mergeText)

  def updateViewBackground(self, layoutName):
    """updating the background view"""
    masterVolume = self.getMaster(layoutName)
    if masterVolume:
      masterVolumeId = masterVolume.GetID()
    else:
      masterVolumeId = None
    if not self.threeVolumesCBox.checked:
      compNode = self.editUtil.getCompositeNode('Red')
      compNode.SetBackgroundVolumeID(masterVolumeId)
      compNode = self.editUtil.getCompositeNode('Green')
      compNode.SetBackgroundVolumeID(masterVolumeId)
      compNode = self.editUtil.getCompositeNode('Yellow')
      compNode.SetBackgroundVolumeID(masterVolumeId)
    else:
      compNode = self.editUtil.getCompositeNode(layoutName)
      compNode.SetBackgroundVolumeID(masterVolumeId)

  def updateViewLabel(self, layoutName):
    """updating the label view"""
    mergeVolume = self.getMerge(layoutName)
    if mergeVolume:
      mergeVolumeId = mergeVolume.GetID()
    else:
      mergeVolumeId = None
    if not self.threeVolumesCBox.checked:
      compNode = self.editUtil.getCompositeNode('Red')
      compNode.SetLabelVolumeID(mergeVolumeId)
      compNode = self.editUtil.getCompositeNode('Green')
      compNode.SetLabelVolumeID(mergeVolumeId)
      compNode = self.editUtil.getCompositeNode('Yellow')
      compNode.SetLabelVolumeID(mergeVolumeId)
    else:
      compNode = self.editUtil.getCompositeNode(layoutName)
      compNode.SetLabelVolumeID(mergeVolumeId)

  def setMergeVolume(self, layoutName):
    if self.labelSelector:
      merge = self.labelSelector.currentNode()
      warnings = self.volumesLogic.CheckForLabelVolumeValidity(self.getMaster(layoutName), merge)
      if warnings != "":
        self.errorDialog("Warning: %s" % warnings)
      else:
        self.setMerge(merge, layoutName)
    # TODO: is this necessary?
    self.notifyOtherModules()

  def checkAndSetMerge(self, layoutName):
    self.setMerge(None, layoutName)
    merge = self.selectInitialMerge(self.getMaster(layoutName))
    if not merge:
      mergeText = "None"
      # the master exists, but there is no merge volume yet
      # bring up dialog to create a merge with a user-selected color node
      #self.colorSelectDialog(layoutName)
    else:
      warnings = self.volumesLogic.CheckForLabelVolumeValidity(self.getMaster(layoutName), merge)
      if warnings != "":
        self.errorDialog("Warning: %s" % warnings)
      else:
        self.setMerge(merge, layoutName)

  def select(self, layoutName):
    """select master volume - load merge volume if one with the correct name exists"""
    masterSelector = self.getMasterSelector(layoutName)
    newlySelectedMaster = masterSelector.currentNode()
    masterErrors = self.checkForMasterErrors(newlySelectedMaster)

    if masterErrors != "":
      print(masterErrors)
      #self.errorDialog("Error: %s" % masterErrors)
      #return
    #else:
    self.setMaster(newlySelectedMaster, layoutName)

    self.checkAndSetMerge(layoutName)

    # TODO: is this necessary?
    self.notifyOtherModules()

  def onSelectAxi(self, node):
    self.select('Red')

  def onSelectSag(self, node):
    self.select('Yellow')

  def onSelectCor(self, node):
    self.select('Green')

  def notifyOtherModules(self):
    """notify other modules"""
    # trigger a modified event on the parameter node so that other parts of the GUI
    # (such as the EditColor) will know to update and enable themselves
    # FIXME: I got no clue what it is
    self.editUtil.getParameterNode().Modified()
    if self.selectCommand:
      self.selectCommand()

  def promptStructure(self, LayoutName):
    """ask user which label to create"""
    merge = self.getMerge(LayoutName)
    if not merge:
      return
    colorNode = merge.GetDisplayNode().GetColorNode()

    if colorNode == "":
      self.errorDialog( "No color node selected" )
      return

    if not self.colorBox == "":
      self.colorBox = ColorBox.ColorBox(colorNode = colorNode)
      self.colorBox.selectCommand = self.addStructure
    else:
      self.colorBox.colorNode = colorNode
      self.colorBox.parent.populate()
      self.colorBox.parent.show()
      self.colorBox.parent.raise_()

  def addMergeAxiAction(self):
    self.AddStructureLayoutName = 'Red'
    self.addStructure()

  def addMergeSagAction(self):
    self.AddStructureLayoutName = 'Yellow'
    self.addStructure()

  def addMergeCorAction(self):
    self.AddStructureLayoutName = 'Green'
    self.addStructure()

  def splitMergeAxiAction(self):
    self.splitMerge('Red')

  def splitMergeSagAction(self):
    self.splitMerge('Yellow')

  def splitMergeCorAction(self):
    self.splitMerge('Green')

  def addStructure(self, Label = None, Structure = None):
    """create the segmentation helper box"""
    if not Structure:
      Structure = self.getMerge(self.AddStructureLayoutName)
    if not Structure:
      return

    if not Label:
      # if no label given, prompt the user.  The selectCommand of the colorBox will
      # then re-invoke this method with the label value set and we will continue
      Label = self.promptStructure(self.AddStructureLayoutName)
      return

    """re-build the Structures frame"""
    if slicer.mrmlScene.IsBatchProcessing():
      return

    if self.mergeValidCommand:
      # will be passed current
      self.mergeValidCommand(Structure)

    colorNode = Structure.GetDisplayNode().GetColorNode()
    lut = colorNode.GetLookupTable()

    structureColor = lut.GetTableValue(Label)[0:3]
    color = qt.QColor()
    color.setRgb(structureColor[0] * 255, structureColor[1] * 255, structureColor[2] * 255)

    if not self.IsMergeAlreadyAdded(Structure.GetName()):
      RowItems = []
      # label index
      item = qt.QStandardItem()
      item.setEditable(False)
      item.setText(str(Label))
      item.setCheckable(True)
      if self.selectAllModelsCBox.checked:
        item.setCheckState(2)
      RowItems.append(item)
      # label color
      item = qt.QStandardItem()
      item.setEditable(False)
      item.setData(color, 1)
      RowItems.append(item)
      # volumeName name
      item = qt.QStandardItem()
      item.setEditable(False)
      item.setText(Structure.GetName())
      RowItems.append(item)
      # sort order
      item = qt.QStandardItem()
      item.setEditable(True)
      item.setText("")
      RowItems.append(item)
      if self.threeVolumesCBox.checked:
        # direction
        item = qt.QStandardItem()
        item.setEditable(False)
        item.setText(self.AddStructureLayoutName)
        RowItems.append(item)

      self.structures.appendRow(RowItems)

      self.updatePrestructureButtons()
    else:
      self.errorDialog("WARNING: this label already exits, please choose another label.")

  def mergeStructures(self, LayoutName):
    """merge different structures in the current merge volume"""
    merge = self.getMerge(LayoutName)
    if not merge:
      return
    SelVolumes = self.GetSelectedStructuresByDirection(LayoutName)

    rows = self.structures.rowCount()

    combiner = slicer.vtkImageLabelCombine()
    MergeName = merge.GetName()
    dims = merge.GetImageData().GetDimensions()
    for VolumeName in SelVolumes:
      Nodes = slicer.mrmlScene.GetNodesByName(VolumeName)
      if Nodes.GetNumberOfItems() == 1:
        Volume = Nodes.GetItemAsObject(0)
        if Volume:
          # check that structure in the same size as the merge volume
          if Volume.GetImageData().GetDimensions() != dims:
            print("WARNING: Volume %s does not have the same dimensions as the target merge volume.  Use the Resample Scalar/Vector/DWI module to resample.  Use %s as the Reference Volume and select Nearest Neighbor (nn) Interpolation Type." % (VolumeName, MergeName))
          else:
            if vtk.VTK_MAJOR_VERSION <= 5:
              combiner.SetInput1(merge.GetImageData())
              combiner.SetInput2(Volume.GetImageData())
            else:
              combiner.SetInputConnection(0, merge.GetImageDataConnection())
              combiner.SetInputConnection(1, Volume.GetImageDataConnection())
            self.statusText("Merging %s" % VolumeName)
            combiner.Update()
            merge.GetImageData().DeepCopy(combiner.GetOutput())
        else:
          print("WARNING: No image data for volume node %s." % VolumeName)
      else:
        print("WARNING: The node %s for creating model not one, it's %s" % (VolumeName, str(Nodes.GetNumberOfItems())))

    self.editUtil.markVolumeNodeAsModified(merge)
    self.statusText("Finished merging.")

  def splitMerge(self, LayoutName):
    """split the merge volume into number of structures"""
    self.statusText("Splitting...")

    merge = self.getMerge(LayoutName)
    if not merge:
      return
    colorNode = merge.GetDisplayNode().GetColorNode()
    MergeName = merge.GetName()

    ScalarRange = self.mergeAxi.GetImageData().GetScalarRange()
    lo = int(ScalarRange[0])
    hi = int(ScalarRange[1])

    # TODO: pending resolution of bug 1822, run the thresholding
    # in single threaded mode to avoid data corruption observed on mac release
    # builds
    thresholder = vtk.vtkImageThreshold()
    thresholder.SetNumberOfThreads(1)
    for i in xrange(lo, hi + 1):
      if vtk.VTK_MAJOR_VERSION <= 5:
        thresholder.SetInput(merge.GetImageData())
      else:
        thresholder.SetInputConnection(merge.GetImageDataConnection())
      thresholder.SetInValue(i)
      thresholder.SetOutValue(0)
      thresholder.ReplaceInOn()
      thresholder.ReplaceOutOn()
      thresholder.ThresholdBetween(i, i)
      thresholder.SetOutputScalarType(merge.GetImageData().GetScalarType())
      thresholder.Update()
      if thresholder.GetOutput().GetScalarRange() != (0.0, 0.0):
        self.statusText("Splitting label %d..." % i)
        labelName = colorNode.GetColorName(i)
        SplitImageName = MergeName + '-l' + labelName
        self.statusText("Creating structure volume %s..." % SplitImageName)
        structureVolume = self.volumesLogic.CreateAndAddLabelVolume(slicer.mrmlScene, merge, SplitImageName)
        structureVolume.GetDisplayNode().SetAndObserveColorNodeID(colorNode.GetID())
        self.AddStructureLayoutName = LayoutName
        self.addStructure(i, structureVolume)
        structureVolume.GetImageData().DeepCopy(thresholder.GetOutput())
        self.editUtil.markVolumeNodeAsModified(structureVolume)

    self.statusText("Finished splitting.")

  def selectAllModelsCBoxChanged(self, state = None):
    rows = self.structures.rowCount()
    if self.selectAllModelsCBox.checked:
      for i in range(rows):
        self.structures.item(i, 0).setCheckState(2)
    else:
      AllBoxesChecked = True
      for i in range(rows):
        if self.structures.item(i, 0).checkState() == 0:
          AllBoxesChecked = False
          break
      if AllBoxesChecked:
        for i in range(rows):
          self.structures.item(i, 0).setCheckState(0)

  def onDeleteStructures(self, confirm = True, all = False):
    """delete all the structures"""
    rows = self.structures.rowCount()
    if confirm:
      NoRowsToDelete = 0
      for i in range(rows):
        if all or self.structures.item(i, 0).checkState() != 0:
          NoRowsToDelete = NoRowsToDelete + 1
      if NoRowsToDelete == 0:
        self.errorDialog('Please select the structures to be deleted.')
        return
      if not self.confirmDialog("Delete %d structure volume(s)?" % NoRowsToDelete):
        return
    for i in range(rows - 1, -1, -1):
      if all or self.structures.item(i, 0).checkState() != 0:
        self.structures.removeRow(i)
    self.updatePrestructureButtons()

  def onMergeStructures(self):
    """merge the named or all structure lab, label = "all"els into the master label"""
    if self.threeVolumesCBox.checked:
      self.mergeStructures('Red')
      self.mergeStructures('Yellow')
      self.mergeStructures('Green')
    else:
      self.mergeStructures('Red')

  def onBuildMerges(self):
    self.BuildVolume(self.mergeAxi)
    self.BuildVolume(self.mergeSag)
    self.BuildVolume(self.mergeCor)

  def BuildVolume(self, merge):
    #
    # get the image data for the label layer
    #

    self.statusText( "Building..." )
    if not merge:
      return

    #
    # create a model using the command line module
    # based on the current editor parameters
    #

    parameters = {}
    parameters["InputVolume"] = merge.GetID()
    parameters['FilterType'] = "Sinc"
    parameters['GenerateAll'] = True

    # not needed: setting StartLabel and EndLabel instead
    #parameters['Labels'] = self.getPaintLabel()

    parameters["JointSmoothing"] = True
    parameters["SplitNormals"] = True
    parameters["PointNormals"] = True
    parameters["SkipUnNamed"] = True

    # create models for all labels
    parameters["StartLabel"] = -1
    parameters["EndLabel"] = -1

    parameters["Decimate"] = 0.25
    parameters["Smooth"] = 10

    #
    # output
    # - make a new hierarchy node if needed
    #
    numNodes = slicer.mrmlScene.GetNumberOfNodesByClass( "vtkMRMLModelHierarchyNode" )
    outHierarchy = None
    for n in xrange(numNodes):
      node = slicer.mrmlScene.GetNthNodeByClass( n, "vtkMRMLModelHierarchyNode" )
      if node.GetName() == "Editor Models":
        outHierarchy = node
        break

    if outHierarchy and self.replaceModels.checked and numNodes > 0:
      # user wants to delete any existing models, so take down hierarchy and
      # delete the model nodes
      rr = range(numNodes)
      rr.reverse()
      for n in rr:
        node = slicer.mrmlScene.GetNthNodeByClass( n, "vtkMRMLModelHierarchyNode" )
        if node.GetParentNodeID() == outHierarchy.GetID():
          slicer.mrmlScene.RemoveNode( node.GetModelNode() )
          slicer.mrmlScene.RemoveNode( node )

    if not outHierarchy:
      outHierarchy = slicer.vtkMRMLModelHierarchyNode()
      outHierarchy.SetScene( slicer.mrmlScene )
      outHierarchy.SetName( "Editor Models" )
      slicer.mrmlScene.AddNode( outHierarchy )

    parameters["ModelSceneFile"] = outHierarchy

    try:
      modelMaker = slicer.modules.modelmaker
      #
      # run the task (in the background)
      # - use the GUI to provide progress feedback
      # - use the GUI's Logic to invoke the task
      # - model will show up when the processing is finished
      #
      slicer.cli.run(modelMaker, None, parameters)
      self.statusText( "Model Making Started..." )
    except AttributeError:
      qt.QMessageBox.critical(slicer.util.mainWindow(), 'Editor', 'The ModelMaker module is not available<p>Perhaps it was disabled in the application settings or did not load correctly.')

  def onBuildStrucures(self):
    """merging the segmentation into point cloud"""
    rows = self.structures.rowCount()
    for i in range(rows):
      LabelNumber = int(self.structures.item(i, 0).text())
      VolumeName = self.structures.item(i, 2).text()
      Nodes = slicer.mrmlScene.GetNodesByName(VolumeName)
      if Nodes.GetNumberOfItems() == 1:
        VolumeNode = Nodes.GetItemAsObject(0)
        self.BuildVolume(VolumeNode)
      else:
        print("WARNING: The node %s for creating model not one, it's %s" % (VolumeName, str(Nodes.GetNumberOfItems())))

  def IsMergeAlreadyAdded(self, Name):
    rows = self.structures.rowCount()
    for i in range(rows):
      if self.structures.item(i, 2).text() == Name:
        return True
    return False

  def onStructuresChanged(self, item):
    if item.checkState() == 0:
      self.selectAllModelsCBox.setCheckState(0)

  def onStructuresClicked(self, modelIndex):
    VolumeName = self.structures.item(modelIndex.row(), 2).text()
    Nodes = slicer.mrmlScene.GetNodesByName(VolumeName)
    if Nodes.GetNumberOfItems() == 1:
      Volume = Nodes.GetItemAsObject(0)
      if Volume:
        LayoutName = 'Red'
        if self.threeVolumesCBox.checked:
          LayoutName = self.structures.item(modelIndex.row(), 4).text()
        self.setMerge(Volume, LayoutName)
      else:
        print("WARNING: No image data for volume node %s." % VolumeName)
    else:
      print("WARNING: The node %s for creating model not one, it's %d" % (VolumeName, Nodes.GetNumberOfItems()))

  def GetSelectedStructures(self):
    VolumeNames = []
    rows = self.structures.rowCount()
    for i in range(rows):
      if self.structures.item(i, 0).checkState() == 2:
        VolumeNames.append(self.structures.item(i, 2).text())
    return VolumeNames

  def GetSelectedStructuresByDirection(self, LayoutName):
    if not self.threeVolumesCBox.checked:
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

  def createMasterFrame(self):
    """create the master frame"""
    self.masterFrame = qt.QFrame(self.parent)
    self.masterFrame.setLayout(qt.QVBoxLayout())
    self.parent.layout().addWidget(self.masterFrame)

    self.CheckBoxesFrame = qt.QFrame(self.masterFrame)
    self.CheckBoxesFrame.objectName = 'ThreeVolumesFrame'
    self.CheckBoxesFrame.setLayout(qt.QHBoxLayout())
    self.masterFrame.layout().addWidget(self.CheckBoxesFrame)

    self.threeVolumesCBox = qt.QCheckBox("Multiple volumes", self.CheckBoxesFrame)
    self.threeVolumesCBox.objectName = 'ThreeVolumesCBox'
    self.threeVolumesCBox.setToolTip("Upload one volume for each direction, i.e. Axial, Sagittal and Coronal.")
    self.threeVolumesCBox.setChecked(self.IsThreeVolume)
    self.threeVolumesCBox.connect("stateChanged(int)", self.threeVolumesCBoxChanged)
    self.CheckBoxesFrame.layout().addWidget(self.threeVolumesCBox)

    self.buildMergesButton = qt.QPushButton("Build Merges", self.CheckBoxesFrame)
    self.buildMergesButton.objectName = 'BuildMergesButton'
    self.buildMergesButton.setToolTip("Build model for the current merges.")
    self.buildMergesButton.setDisabled(True)
    self.CheckBoxesFrame.layout().addWidget(self.buildMergesButton)
    self.buildMergesButton.connect("clicked()", self.onBuildMerges)

  # TODO: make the text and selector the same size, so it looks better
  def createMasterAxiSelector(self):
    """create the master axial selector"""
    self.masterAxiSelectorFrame = qt.QFrame(self.parent)
    self.masterAxiSelectorFrame.objectName = 'MasterAxialVolumeFrame'
    self.masterAxiSelectorFrame.setLayout(qt.QHBoxLayout())
    self.masterFrame.layout().addWidget(self.masterAxiSelectorFrame)

    self.masterAxiSelectorLabel = qt.QLabel("Master Axial Volume: ", self.masterAxiSelectorFrame)
    self.masterAxiSelectorLabel.setToolTip( "Select the master axial volume (background grayscale scalar volume node)")
    self.masterAxiSelectorFrame.layout().addWidget(self.masterAxiSelectorLabel)

    self.masterAxiSelector = slicer.qMRMLNodeComboBox(self.masterAxiSelectorFrame)
    self.masterAxiSelector.objectName = 'MasterAxialVolumeNodeSelector'
    self.masterAxiSelector.nodeTypes = ( ("vtkMRMLScalarVolumeNode"), "" )
    self.masterAxiSelector.addAttribute( "vtkMRMLScalarVolumeNode", "LabelMap", 0 )
    self.masterAxiSelector.selectNodeUponCreation = False
    self.masterAxiSelector.addEnabled = False
    self.masterAxiSelector.removeEnabled = False
    self.masterAxiSelector.noneEnabled = True
    self.masterAxiSelector.showHidden = False
    self.masterAxiSelector.showChildNodeTypes = False
    self.masterAxiSelector.setMRMLScene( slicer.mrmlScene )
    self.masterAxiSelector.setToolTip( "Pick the master axial structural volume to define the segmentation.  A label volume with the with \"-label\" appended to the name will be created if it doesn't already exist." )
    self.masterAxiSelectorFrame.layout().addWidget(self.masterAxiSelector)

  def createMasterSagSelector(self):
    """create the master sagittal selector"""
    self.masterSagSelectorFrame = qt.QFrame(self.parent)
    self.masterSagSelectorFrame.objectName = 'MasterSagittalVolumeFrame'
    self.masterSagSelectorFrame.setLayout(qt.QHBoxLayout())
    self.masterFrame.layout().addWidget(self.masterSagSelectorFrame)

    self.masterSagSelectorLabel = qt.QLabel("Master Sagittal Volume: ", self.masterSagSelectorFrame)
    self.masterSagSelectorLabel.setToolTip( "Select the master sagittal volume (background grayscale scalar volume node)")
    self.masterSagSelectorFrame.layout().addWidget(self.masterSagSelectorLabel)

    self.masterSagSelector = slicer.qMRMLNodeComboBox(self.masterSagSelectorFrame)
    self.masterSagSelector.objectName = 'MasterSagittalVolumeNodeSelector'
    self.masterSagSelector.nodeTypes = ( ("vtkMRMLScalarVolumeNode"), "" )
    self.masterSagSelector.addAttribute( "vtkMRMLScalarVolumeNode", "LabelMap", 0 )
    self.masterSagSelector.selectNodeUponCreation = False
    self.masterSagSelector.addEnabled = False
    self.masterSagSelector.removeEnabled = False
    self.masterSagSelector.noneEnabled = True
    self.masterSagSelector.showHidden = False
    self.masterSagSelector.showChildNodeTypes = False
    self.masterSagSelector.setMRMLScene( slicer.mrmlScene )
    self.masterSagSelector.setToolTip( "Pick the master sagittal structural volume to define the segmentation.  A label volume with the with \"-label\" appended to the name will be created if it doesn't already exist." )
    self.masterSagSelectorFrame.layout().addWidget(self.masterSagSelector)

  def createMasterCorSelector(self):
    """create the master coronal selector"""
    self.masterCorSelectorFrame = qt.QFrame(self.parent)
    self.masterCorSelectorFrame.objectName = 'MasterCoronalVolumeFrame'
    self.masterCorSelectorFrame.setLayout(qt.QHBoxLayout())
    self.masterFrame.layout().addWidget(self.masterCorSelectorFrame)

    self.masterCorSelectorLabel = qt.QLabel("Master Coronal Volume: ", self.masterCorSelectorFrame)
    self.masterCorSelectorLabel.setToolTip( "Select the master coronal volume (background grayscale scalar volume node)")
    self.masterCorSelectorFrame.layout().addWidget(self.masterCorSelectorLabel)

    self.masterCorSelector = slicer.qMRMLNodeComboBox(self.masterCorSelectorFrame)
    self.masterCorSelector.objectName = 'MasterCoronalVolumeNodeSelector'
    self.masterCorSelector.nodeTypes = ( ("vtkMRMLScalarVolumeNode"), "" )
    self.masterCorSelector.addAttribute( "vtkMRMLScalarVolumeNode", "LabelMap", 0 )
    self.masterCorSelector.selectNodeUponCreation = False
    self.masterCorSelector.addEnabled = False
    self.masterCorSelector.removeEnabled = False
    self.masterCorSelector.noneEnabled = True
    self.masterCorSelector.showHidden = False
    self.masterCorSelector.showChildNodeTypes = False
    self.masterCorSelector.setMRMLScene( slicer.mrmlScene )
    # TODO: need to add a QLabel
    # self.masterCoronalSelector.SetLabelText( "Master Volume:" )
    self.masterCorSelector.setToolTip( "Pick the master coronal structural volume to define the segmentation.  A label volume with the with \"-label\" appended to the name will be created if it doesn't already exist." )
    self.masterCorSelectorFrame.layout().addWidget(self.masterCorSelector)

  def createMergeAxiFrame(self):
    """create merge axial frame"""
    self.mergeAxiFrame = qt.QFrame(self.masterFrame)
    self.mergeAxiFrame.objectName = 'MergeAxialVolumeFrame'
    self.mergeAxiFrame.setLayout(qt.QHBoxLayout())
    self.masterFrame.layout().addWidget(self.mergeAxiFrame)

    mergeAxiNameToolTip = "Composite label map containing the merged axial structures (be aware that merge axial operations will overwrite any edits applied to this volume)"
    self.mergeAxiNameLabel = qt.QLabel("Merge Axial Volume: ", self.mergeAxiFrame)
    self.mergeAxiNameLabel.setToolTip( mergeAxiNameToolTip )
    self.mergeAxiFrame.layout().addWidget(self.mergeAxiNameLabel)

    self.mergeAxiName = qt.QLabel("", self.mergeAxiFrame)
    self.mergeAxiName.setToolTip( mergeAxiNameToolTip )
    self.mergeAxiFrame.layout().addWidget(self.mergeAxiName)

    self.setMergeAxiButton = qt.QPushButton("Set", self.mergeAxiFrame)
    self.setMergeAxiButton.objectName = 'MergeAxialVolumeButton'
    self.setMergeAxiButton.setToolTip("Set the merge axial volume to use with this master axial.")
    self.setMergeAxiButton.setDisabled(True)
    self.mergeAxiFrame.layout().addWidget(self.setMergeAxiButton)

    self.addMergeAxiButton = qt.QPushButton("Add", self.mergeAxiFrame)
    self.addMergeAxiButton.objectName = 'AddMergeAxialVolumeButton'
    self.addMergeAxiButton.setToolTip("Add the merge axial volume to use for model making.")
    self.addMergeAxiButton.setDisabled(True)
    self.mergeAxiFrame.layout().addWidget(self.addMergeAxiButton)

    self.splitMergeAxiButton = qt.QPushButton("Split", self.mergeAxiFrame)
    self.splitMergeAxiButton.objectName = 'SplitMergeAxialVolumeButton'
    self.splitMergeAxiButton.setToolTip("Split the merge axial volume to different labels.")
    self.splitMergeAxiButton.setDisabled(True)
    self.mergeAxiFrame.layout().addWidget(self.splitMergeAxiButton)

  def createMergeSagFrame(self):
    """create merge sagittal frame"""
    self.mergeSagFrame = qt.QFrame(self.masterFrame)
    self.mergeSagFrame.objectName = 'MergeSagittalVolumeFrame'
    self.mergeSagFrame.setLayout(qt.QHBoxLayout())
    self.masterFrame.layout().addWidget(self.mergeSagFrame)

    mergeSagNameToolTip = "Composite label map containing the merged sagittal structures (be aware that merge sagittal operations will overwrite any edits applied to this volume)"
    self.mergeSagNameLabel = qt.QLabel("Merge Sagittal Volume: ", self.mergeSagFrame)
    self.mergeSagNameLabel.setToolTip( mergeSagNameToolTip )
    self.mergeSagFrame.layout().addWidget(self.mergeSagNameLabel)

    self.mergeSagName = qt.QLabel("", self.mergeSagFrame)
    self.mergeSagName.setToolTip( mergeSagNameToolTip )
    self.mergeSagFrame.layout().addWidget(self.mergeSagName)

    self.setMergeSagButton = qt.QPushButton("Set", self.mergeSagFrame)
    self.setMergeSagButton.objectName = 'MergeSagittalVolumeButton'
    self.setMergeSagButton.setToolTip("Set the merge sagittal volume to use with this master sagittal.")
    self.setMergeSagButton.setDisabled(True)
    self.mergeSagFrame.layout().addWidget(self.setMergeSagButton)

    self.addMergeSagButton = qt.QPushButton("Add", self.mergeSagFrame)
    self.addMergeSagButton.objectName = 'AddMergeSagittalVolumeButton'
    self.addMergeSagButton.setToolTip("Add the merge sagittal volume to use for model making.")
    self.addMergeSagButton.setDisabled(True)
    self.mergeSagFrame.layout().addWidget(self.addMergeSagButton)

    self.splitMergeSagButton = qt.QPushButton("Split", self.mergeSagFrame)
    self.splitMergeSagButton.objectName = 'SplitMergeSagittalVolumeButton'
    self.splitMergeSagButton.setToolTip("Split the merge sagittal volume to different labels.")
    self.splitMergeSagButton.setDisabled(True)
    self.mergeSagFrame.layout().addWidget(self.splitMergeSagButton)

  def createMergeCorFrame(self):
    """create merge coronal frame"""
    self.mergeCorFrame = qt.QFrame(self.masterFrame)
    self.mergeCorFrame.objectName = 'MergeCoronalVolumeFrame'
    self.mergeCorFrame.setLayout(qt.QHBoxLayout())
    self.masterFrame.layout().addWidget(self.mergeCorFrame)

    mergeCoronalNameToolTip = "Composite label map containing the merged coronal structures (be aware that merge coronal operations will overwrite any edits applied to this volume)"
    self.mergeCoronalNameLabel = qt.QLabel("Merge Coronal Volume: ", self.mergeCorFrame)
    self.mergeCoronalNameLabel.setToolTip( mergeCoronalNameToolTip )
    self.mergeCorFrame.layout().addWidget(self.mergeCoronalNameLabel)

    self.mergeCorName = qt.QLabel("", self.mergeCorFrame)
    self.mergeCorName.setToolTip( mergeCoronalNameToolTip )
    self.mergeCorFrame.layout().addWidget(self.mergeCorName)

    self.setMergeCorButton = qt.QPushButton("Set", self.mergeCorFrame)
    self.setMergeCorButton.objectName = 'MergeCoronalVolumeButton'
    self.setMergeCorButton.setToolTip("Set the merge coronal volume to use with this master coronal.")
    self.setMergeCorButton.setDisabled(True)
    self.mergeCorFrame.layout().addWidget(self.setMergeCorButton)

    self.addMergeCorButton = qt.QPushButton("Add", self.mergeCorFrame)
    self.addMergeCorButton.objectName = 'AddMergeCoronalVolumeButton'
    self.addMergeCorButton.setToolTip("Add the merge coronal volume to use for model making.")
    self.addMergeCorButton.setDisabled(True)
    self.mergeCorFrame.layout().addWidget(self.addMergeCorButton)

    self.splitMergeCorButton = qt.QPushButton("Split", self.mergeCorFrame)
    self.splitMergeCorButton.objectName = 'SplitMergeCoronalVolumeButton'
    self.splitMergeCorButton.setToolTip("Split the merge coronal volume to different labels.")
    self.splitMergeCorButton.setDisabled(True)
    self.mergeCorFrame.layout().addWidget(self.splitMergeCorButton)

  def create(self):
    """create the segmentation helper box"""
    self.createMasterFrame()
    self.createMasterAxiSelector()
    self.createMasterSagSelector()
    self.createMasterCorSelector()

    # merge label name and set button
    self.createMergeAxiFrame()
    self.createMergeSagFrame()
    self.createMergeCorFrame()

    # Structures Frame
    self.structuresFrame = ctk.ctkCollapsibleGroupBox(self.masterFrame)
    self.structuresFrame.objectName = 'PerStructureVolumesFrame'
    self.structuresFrame.title = "Per-Structure Volumes"
    self.structuresFrame.collapsed = True
    self.structuresFrame.setLayout(qt.QVBoxLayout())
    self.masterFrame.layout().addWidget(self.structuresFrame)

    # structures view
    self.structures = qt.QStandardItemModel()
    self.structures.setHorizontalHeaderLabels(["Index", "Colour", "Label Volume", "Order", "Layout"])
    self.structures.connect("itemChanged(QStandardItem*)", self.onStructuresChanged)

    self.structuresView = qt.QTreeView()
    self.structuresView.objectName = 'StructuresView'
    self.structuresView.sortingEnabled = True
    self.structuresView.setColumnWidth(0, 70)
    self.structuresView.setColumnWidth(1, 50)
    self.structuresView.setColumnWidth(2, 150)
    self.structuresView.setColumnWidth(3, 50)
    self.structuresView.setColumnWidth(4, 50)
    self.structuresView.setModel(self.structures)
    self.structuresView.connect("activated(QModelIndex)", self.onStructuresClicked)
    self.structuresView.setProperty('SH_ItemView_ActivateItemOnSingleClick', 1)
    self.structuresFrame.layout().addWidget(self.structuresView)

    # all buttons frame
    self.allButtonsFrame = qt.QFrame(self.structuresFrame)
    self.allButtonsFrame.objectName = 'AllButtonsFrameButton'
    self.allButtonsFrame.setLayout(qt.QHBoxLayout())
    self.structuresFrame.layout().addWidget(self.allButtonsFrame)

    # delete structures button
    self.deleteStructuresButton = qt.QPushButton("Delete Structures", self.allButtonsFrame)
    self.deleteStructuresButton.objectName = 'DeleteStructureButton'
    self.deleteStructuresButton.setToolTip("Delete the selected structure volumes from the scene.")
    self.allButtonsFrame.layout().addWidget(self.deleteStructuresButton)

    # merge button
    self.mergeStructuresButton = qt.QPushButton("Merge Volumes", self.allButtonsFrame)
    self.mergeStructuresButton.objectName = 'MergeStructuresButton'
    self.mergeStructuresButton.setToolTip("Merge the selected structures into a merge volume")
    self.mergeStructuresButton.setDisabled(True)
    self.allButtonsFrame.layout().addWidget(self.mergeStructuresButton)

    # merge and build button
    self.buildStructuresButton = qt.QPushButton("Build Models", self.allButtonsFrame)
    self.buildStructuresButton.objectName = 'BuildStructuresModelsButton'
    self.buildStructuresButton.setToolTip("Build model for the selected structures.")
    self.buildStructuresButton.setDisabled(True)
    self.allButtonsFrame.layout().addWidget(self.buildStructuresButton)

    # options frame
    self.optionsFrame = qt.QFrame(self.structuresFrame)
    self.optionsFrame.objectName = 'OptionsFrame'
    self.optionsFrame.setLayout(qt.QHBoxLayout())
    self.structuresFrame.layout().addWidget(self.optionsFrame)

    # replace models button
    self.selectAllModelsCBox = qt.QCheckBox("Select all", self.optionsFrame)
    self.selectAllModelsCBox.objectName = 'SelectAllModelsCheckBox'
    self.selectAllModelsCBox.setToolTip("Select all the structures")
    self.selectAllModelsCBox.setChecked(False)
    self.selectAllModelsCBox.setDisabled(True)
    self.optionsFrame.layout().addWidget(self.selectAllModelsCBox)
    self.selectAllModelsCBox.connect("stateChanged(int)", self.selectAllModelsCBoxChanged)

    # replace models button
    self.replaceModels = qt.QCheckBox("Replace Models", self.optionsFrame)
    self.replaceModels.objectName = 'ReplaceModelsCheckBox'
    self.replaceModels.setToolTip("Replace any existing models when building")
    self.replaceModels.setChecked(False)
    self.replaceModels.setDisabled(True)
    self.optionsFrame.layout().addWidget(self.replaceModels)

    # signals/slots on qt widgets are automatically when
    # this class destructs, but observers of the scene must be explicitly 
    # removed in the destuctor

    # node selected
    self.masterAxiSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelectAxi)
    self.masterSagSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelectSag)
    self.masterCorSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelectCor)

    # buttons pressed
    self.deleteStructuresButton.connect("clicked()", self.onDeleteStructures)
    self.mergeStructuresButton.connect("clicked()", self.onMergeStructures)
    self.buildStructuresButton.connect("clicked()", self.onBuildStrucures)
    self.setMergeAxiButton.connect("clicked()", self.setMergeAxiAction)
    self.setMergeSagButton.connect("clicked()", self.setMergeSagAction)
    self.setMergeCorButton.connect("clicked()", self.setMergeCorAction)
    self.addMergeAxiButton.connect("clicked()", self.addMergeAxiAction)
    self.addMergeSagButton.connect("clicked()", self.addMergeSagAction)
    self.addMergeCorButton.connect("clicked()", self.addMergeCorAction)
    self.splitMergeAxiButton.connect("clicked()", self.splitMergeAxiAction)
    self.splitMergeSagButton.connect("clicked()", self.splitMergeSagAction)
    self.splitMergeCorButton.connect("clicked()", self.splitMergeCorAction)

  def initialise(self):
    """reinitialises the class variables"""
    self.masterAxiSelector.setCurrentNode(None)
    self.masterSagSelector.setCurrentNode(None)
    self.masterCorSelector.setCurrentNode(None)
    self.setMerge(None, 'Red')
    self.setMerge(None, 'Yellow')
    self.setMerge(None, 'Green')
    # instance of a ColorBox
    self.colorBox = None
    # widgets that are dynamically created on demand
    self.colorSelect = None
    self.labelSelect = None
    self.labelSelector = None
    self.AddStructureLayoutName = ''
    self.onDeleteStructures(False, True)

  def threeVolumesCBoxChanged(self, state = None):
    """taking care of which frames to be displayed based on the choice of multiple or single volume."""
    self.IsThreeVolume = self.threeVolumesCBox.checked

    if not self.threeVolumesCBox.checked:
      self.mergeSagFrame.hide()
      self.masterSagSelectorFrame.hide()

      self.mergeCorFrame.hide()
      self.masterCorSelectorFrame.hide()

      self.masterAxiSelectorLabel.setText("Master Volume: ")
      self.masterAxiSelectorLabel.setToolTip("Select the master volume (background grayscale scalar volume node)")
      mergeAxiNameToolTip = "Composite label map containing the merged structures (be aware that merge operations will overwrite any edits applied to this volume)"
      self.mergeAxiNameLabel.setText("Merge Volume: ")
      self.mergeAxiNameLabel.setToolTip(mergeAxiNameToolTip)
      self.mergeAxiName.setToolTip( mergeAxiNameToolTip )
      self.setMergeAxiButton.setToolTip("Set the merge volume to use with this master.")

      self.structures.removeColumn(4)
      self.structures.setHorizontalHeaderLabels(["Index", "Colour", "Label Volume", "Order"])
      self.structuresView.setColumnWidth(0, 70)
      self.structuresView.setColumnWidth(1, 50)
      self.structuresView.setColumnWidth(2, 150)
      self.structuresView.setColumnWidth(3, 50)

    else:
      self.mergeSagFrame.show()
      self.masterSagSelectorFrame.show()

      self.mergeCorFrame.show()
      self.masterCorSelectorFrame.show()

      self.masterAxiSelectorLabel.setText("Master Axial Volume: ")
      self.masterAxiSelectorLabel.setToolTip("Select the master axial volume (background grayscale scalar volume node)")
      mergeAxiNameToolTip = "Composite label map containing the merged axial structures (be aware that merge axial operations will overwrite any edits applied to this volume)"
      self.mergeAxiNameLabel.setText("Merge Axial Volume: ")
      self.mergeAxiNameLabel.setToolTip( mergeAxiNameToolTip )
      self.mergeAxiName.setToolTip( mergeAxiNameToolTip )
      self.setMergeAxiButton.setToolTip("Set the merge axial volume to use with this master axial.")

      self.structures.insertColumn(4)
      self.structures.setHorizontalHeaderLabels(["Index", "Colour", "Label Volume", "Order", "Layout"])
      self.structuresView.setColumnWidth(0, 70)
      self.structuresView.setColumnWidth(1, 50)
      self.structuresView.setColumnWidth(2, 150)
      self.structuresView.setColumnWidth(3, 50)
      self.structuresView.setColumnWidth(4, 50)

    self.initialise()
    self.initialiseMasterAndMerge()

  def selectInitialMaster(self, name):
    """selecting the initial image based on the name of volumes"""
    numVolumeNodes = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLVolumeNode')
    for i in range(numVolumeNodes):
      volumeNode = slicer.mrmlScene.GetNthNodeByClass(i, 'vtkMRMLVolumeNode')
      if name in volumeNode.GetName().lower():
        return volumeNode
    return None

  def selectInitialMerge(self, masterImage):
    """selecting the initial image based on the name of volumes"""
    if masterImage and masterImage.GetImageData():
      numVolumeNodes = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLVolumeNode')
      name = masterImage.GetName().lower() + '-label'
      for i in range(numVolumeNodes):
        volumeNode = slicer.mrmlScene.GetNthNodeByClass(i, 'vtkMRMLVolumeNode')
        if volumeNode.GetName().lower() == name:
          return volumeNode
    return None

  # NOTE: nothing more to become independent?
  def colorSelectDialog(self, layoutName):
    """color table dialog"""

    if not self.colorSelect:
      self.colorSelect = qt.QDialog(slicer.util.mainWindow())
      self.colorSelect.objectName = 'EditorColorSelectDialog'
      self.colorSelect.setLayout( qt.QVBoxLayout() )

      self.colorPromptLabel = qt.QLabel()
      self.colorSelect.layout().addWidget( self.colorPromptLabel )

      self.mergeLineEditFrame = qt.QFrame()
      self.mergeLineEditFrame.objectName = 'MergeLineFrame'
      self.mergeLineEditFrame.setLayout(qt.QHBoxLayout())
      self.colorSelect.layout().addWidget(self.mergeLineEditFrame)

      self.mergeLineLabel = qt.QLabel()
      self.mergeLineLabel.setText("Merge Name: ")
      self.mergeLineEditFrame.layout().addWidget(self.mergeLineLabel)

      self.mergeLineEdit = qt.QLineEdit()
      self.mergeLineEditFrame.layout().addWidget(self.mergeLineEdit)

      self.colorSelectorFrame = qt.QFrame()
      self.colorSelectorFrame.objectName = 'ColorSelectorFrame'
      self.colorSelectorFrame.setLayout( qt.QHBoxLayout() )
      self.colorSelect.layout().addWidget( self.colorSelectorFrame )

      self.colorSelectorLabel = qt.QLabel()
      self.colorSelectorLabel.setText( "Color Table: " )
      self.colorSelectorFrame.layout().addWidget( self.colorSelectorLabel )

      self.colorSelector = slicer.qMRMLColorTableComboBox()
      self.colorSelector.nodeTypes = ("vtkMRMLColorNode", "")
      self.colorSelector.hideChildNodeTypes = ("vtkMRMLDiffusionTensorDisplayPropertiesNode", "vtkMRMLProceduralColorNode", "")
      self.colorSelector.addEnabled = False
      self.colorSelector.removeEnabled = False
      self.colorSelector.noneEnabled = False
      self.colorSelector.selectNodeUponCreation = True
      self.colorSelector.showHidden = True
      self.colorSelector.showChildNodeTypes = True
      self.colorSelector.setMRMLScene( slicer.mrmlScene )
      self.colorSelector.setToolTip( "Pick the table of structures you wish to edit" )
      self.colorSelect.layout().addWidget( self.colorSelector )

      # pick the default editor LUT for the user
      defaultID = self.colorLogic.GetDefaultEditorColorNodeID()
      defaultNode = slicer.mrmlScene.GetNodeByID(defaultID)
      if defaultNode:
        self.colorSelector.setCurrentNode( defaultNode )

      self.colorButtonFrame = qt.QFrame()
      self.colorButtonFrame.objectName = 'ColorButtonFrame'
      self.colorButtonFrame.setLayout( qt.QHBoxLayout() )
      self.colorSelect.layout().addWidget( self.colorButtonFrame )

      self.colorDialogApply = qt.QPushButton("Apply", self.colorButtonFrame)
      self.colorDialogApply.objectName = 'ColorDialogApply'
      self.colorDialogApply.setToolTip( "Use currently selected color node." )
      self.colorButtonFrame.layout().addWidget(self.colorDialogApply)

      self.colorDialogCancel = qt.QPushButton("Cancel", self.colorButtonFrame)
      self.colorDialogCancel.objectName = 'ColorDialogCancel'
      self.colorDialogCancel.setToolTip( "Cancel current operation." )
      self.colorButtonFrame.layout().addWidget(self.colorDialogCancel)

      self.colorDialogCancel.connect("clicked()", self.colorSelect.hide)

    self.mergeLineEdit.setText(self.getMaster(layoutName).GetName() + '-label')
    if layoutName == 'Red':
      applyCallBack = eval('self.%s' % 'axiColorDialogApplyAction')
    elif layoutName == 'Yellow':
      applyCallBack = eval('self.%s' % 'sagColorDialogApplyAction')
    elif layoutName == 'Green':
      applyCallBack = eval('self.%s' % 'corColorDialogApplyAction')

    self.colorDialogApply.disconnect("clicked()")
    self.colorDialogApply.connect("clicked()", applyCallBack)

    self.colorPromptLabel.setText( "Create a merge label map for selected master volume %s.\nSelect the color table node will be used for segmentation labels." %(self.getMaster(layoutName).GetName()))
    self.colorSelect.show()

  def onColorDialogApply(self, layoutName):
    self.createMerge(layoutName)
    self.colorSelect.hide()

  def axiColorDialogApplyAction(self):
    self.onColorDialogApply('Red');

  def sagColorDialogApplyAction(self):
    self.onColorDialogApply('Yellow');

  def corColorDialogApplyAction(self):
    self.onColorDialogApply('Green');

  # NOTE: nothing more to become independent?
  def labelSelectDialog(self, layoutName):
    """label table dialog"""

    if not self.labelSelect:
      # NOTE: not used anywhere
      self.labelSelect = qt.QFrame()
      self.labelSelect.setLayout( qt.QVBoxLayout() )

      # NOTE: not used anywhere
      self.labelPromptLabel = qt.QLabel()
      self.labelSelect.layout().addWidget( self.labelPromptLabel )

      # NOTE: not used anywhere
      self.labelSelectorFrame = qt.QFrame()
      self.labelSelectorFrame.setLayout( qt.QHBoxLayout() )
      self.labelSelect.layout().addWidget( self.labelSelectorFrame )

      # NOTE: not used anywhere
      self.labelSelectorLabel = qt.QLabel()
      self.labelPromptLabel.setText( "Label Map: " )
      self.labelSelectorFrame.layout().addWidget( self.labelSelectorLabel )

      self.labelSelector = slicer.qMRMLNodeComboBox()
      self.labelSelector.nodeTypes = ( "vtkMRMLScalarVolumeNode", "" )
      self.labelSelector.addAttribute( "vtkMRMLScalarVolumeNode", "LabelMap", "1" )
      # todo addAttribute
      self.labelSelector.selectNodeUponCreation = False
      self.labelSelector.addEnabled = False
      self.labelSelector.noneEnabled = False
      self.labelSelector.removeEnabled = False
      self.labelSelector.showHidden = False
      self.labelSelector.showChildNodeTypes = False
      self.labelSelector.setMRMLScene( slicer.mrmlScene )
      self.labelSelector.setToolTip( "Pick the label map to edit" )
      self.labelSelectorFrame.layout().addWidget( self.labelSelector )

      self.labelButtonFrame = qt.QFrame()
      self.labelButtonFrame.setLayout( qt.QHBoxLayout() )
      self.labelSelect.layout().addWidget( self.labelButtonFrame )

      self.labelDialogApply = qt.QPushButton("Apply", self.labelButtonFrame)
      self.labelDialogApply.setToolTip( "Use currently selected label node." )
      self.labelButtonFrame.layout().addWidget(self.labelDialogApply)

      self.labelDialogCancel = qt.QPushButton("Cancel", self.labelButtonFrame)
      self.labelDialogCancel.setToolTip( "Cancel current operation." )
      self.labelButtonFrame.layout().addWidget(self.labelDialogCancel)

      self.labelButtonFrame.layout().addStretch(1)

      self.labelDialogCreate = qt.QPushButton("Create New...", self.labelButtonFrame)
      self.labelDialogCreate.setToolTip( "Cancel current operation." )
      self.labelButtonFrame.layout().addWidget(self.labelDialogCreate)

      self.labelDialogCancel.connect("clicked()", self.labelSelect.hide)

    if layoutName == 'Red':
      createCallBack = eval('self.%s' % 'axiLabelDialogCreateAction')
      applyCallBack = eval('self.%s' % 'axiLabelDialogApplyAction')
    elif layoutName == 'Yellow':
      createCallBack = eval('self.%s' % 'sagLabelDialogCreateAction')
      applyCallBack = eval('self.%s' % 'sagLabelDialogApplyAction')
    elif layoutName == 'Green':
      createCallBack = eval('self.%s' % 'corLabelDialogCreateAction')
      applyCallBack = eval('self.%s' % 'corLabelDialogApplyAction')

    self.labelDialogApply.disconnect("clicked()")
    self.labelDialogApply.connect("clicked()", applyCallBack)
    self.labelDialogCreate.disconnect("clicked()")
    self.labelDialogCreate.connect("clicked()", createCallBack)

    self.labelPromptLabel.setText( "Select existing label map volume to edit." )
    p = qt.QCursor().pos()
    self.labelSelect.setGeometry(p.x(), p.y(), 400, 200)
    self.labelSelect.show()

  def setMergeAxiAction(self):
    self.labelSelectDialog('Red')

  def setMergeSagAction(self):
    self.labelSelectDialog('Yellow')

  def setMergeCorAction(self):
    self.labelSelectDialog('Green')

  def onLabelDialogApply(self, layoutName):
    self.setMergeVolume(layoutName)
    self.labelSelect.hide()

  def axiLabelDialogApplyAction(self):
    self.onLabelDialogApply('Red')

  def sagLabelDialogApplyAction(self):
    self.onLabelDialogApply('Yellow')

  def corLabelDialogApplyAction(self):
    self.onLabelDialogApply('Green')

  def onLabelDialogCreate(self, layoutName):
    self.colorSelectDialog(layoutName)
    self.labelSelect.hide()

  def axiLabelDialogCreateAction(self):
    self.onLabelDialogCreate('Red')

  def sagLabelDialogCreateAction(self):
    self.onLabelDialogCreate('Yellow')

  def corLabelDialogCreateAction(self):
    self.onLabelDialogCreate('Green')

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
