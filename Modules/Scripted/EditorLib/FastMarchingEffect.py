import os
from __main__ import vtk, qt, ctk, slicer
import EditorLib
from EditorLib.EditOptions import HelpButton
from EditorLib.EditOptions import EditOptions
from EditorLib import EditUtil
from EditorLib import Effect

#
# The Editor Extension itself.
#
# This needs to define the hooks to be come an editor effect.
#

#
# FastMarchingEffectOptions - see EditOptions and Effect for superclasses
#

class FastMarchingEffectOptions(Effect.EffectOptions):
  """ FastMarchingEffect-specfic gui
  """

  def __init__(self, parent=0):
    super(FastMarchingEffectOptions,self).__init__(parent)

    # self.attributes should be tuple of options:
    # 'MouseTool' - grabs the cursor
    # 'Nonmodal' - can be applied while another is active
    # 'Disabled' - not available
    # self.attributes = ('MouseTool')
    self.displayName = 'FastMarchingEffect Effect'

    self.logic = FastMarchingEffectLogic(self.editUtil.getSliceLogic())

  def __del__(self):
    super(FastMarchingEffectOptions,self).__del__()

  def create(self):
    super(FastMarchingEffectOptions,self).create()

    import SelectDirection
    self.SelectionDirection = SelectDirection.SelectDirection(self.frame)
    self.SelectionDirection.AxiCBox.connect("stateChanged(int)", self.UpdatePercentText)
    self.SelectionDirection.SagCBox.connect("stateChanged(int)", self.UpdatePercentText)
    self.SelectionDirection.CorCBox.connect("stateChanged(int)", self.UpdatePercentText)

    self.defaultMaxPercent = 30

    self.percentLabel = qt.QLabel('Expected structure volume as % of image volume:',self.frame)
    self.percentLabel.setToolTip('Segmentation will grow from the seed label until this value is reached')
    self.frame.layout().addWidget(self.percentLabel)
    self.widgets.append(self.percentLabel)

    self.percentMax = ctk.ctkSliderWidget(self.frame)
    self.percentMax.minimum = 0
    self.percentMax.maximum = 100
    self.percentMax.singleStep = 1
    self.percentMax.value = self.defaultMaxPercent
    self.percentMax.setToolTip('Approximate volume of the structure to be segmented relative to the total volume of the image')
    self.frame.layout().addWidget(self.percentMax)
    self.widgets.append(self.percentMax)
    self.percentMax.connect('valueChanged(double)', self.percentMaxChanged)

    self.march = qt.QPushButton("March", self.frame)
    self.march.setToolTip("Perform the Marching operation into the current label map")
    self.frame.layout().addWidget(self.march)
    self.widgets.append(self.march)

    self.percentVolume = qt.QLabel('Maximum volume of the structure: ')
    self.percentVolume.setToolTip('Total maximum volume')
    self.frame.layout().addWidget(self.percentVolume)
    self.widgets.append(self.percentVolume)

    self.marcher = ctk.ctkSliderWidget(self.frame)
    self.marcher.minimum = 0
    self.marcher.maximum = 1
    self.marcher.singleStep = 0.01
    self.marcher.enabled = False
    self.frame.layout().addWidget(self.marcher)
    self.widgets.append(self.marcher)
    self.marcher.connect('valueChanged(double)',self.onMarcherChanged)

    HelpButton(self.frame, "To use FastMarching effect, first mark the areas that belong to the structure of interest to initialize the algorithm. Define the expected volume of the structure you are trying to segment, and hit March.\nAfter computation is complete, use the Marcher slider to go over the segmentation history.")

    self.march.connect('clicked()', self.onMarch)

    # Add vertical spacer
    self.frame.layout().addStretch(1)

    self.percentMaxChanged(self.percentMax.value)

  def destroy(self):
    super(FastMarchingEffectOptions,self).destroy()

  # note: this method needs to be implemented exactly as-is
  # in each leaf subclass so that "self" in the observer
  # is of the correct type
  def updateParameterNode(self, caller, event):
    node = EditUtil.EditUtil().getParameterNode()
    if node != self.parameterNode:
      if self.parameterNode:
        node.RemoveObserver(self.parameterNodeTag)
      self.parameterNode = node
      self.parameterNodeTag = node.AddObserver(vtk.vtkCommand.ModifiedEvent, self.updateGUIFromMRML)

  def setMRMLDefaults(self):
    super(FastMarchingEffectOptions,self).setMRMLDefaults()

  def updateGUIFromMRML(self,caller,event):
    super(FastMarchingEffectOptions,self).updateGUIFromMRML(caller,event)
    self.disconnectWidgets()
    # TODO: get the march parameter from the node
    # march = float(self.parameterNode.GetParameter
    self.connectWidgets()

  def doMarch(self, LayoutName):
    try:
      self.sliceLogic = self.editUtil.getSliceLogic(LayoutName)
      slicer.util.showStatusMessage('Running FastMarching...', 2000)
      self.logic.undoRedo = self.undoRedo
      npoints = self.logic.fastMarching(self.percentMax.value, LayoutName)
      slicer.util.showStatusMessage('FastMarching finished', 2000)
      if npoints:
        self.marcher.minimum = 0
        self.marcher.maximum = npoints
        self.marcher.value = npoints
        self.marcher.singleStep = 1
        self.marcher.enabled = True
    except IndexError:
      print('No tools available!')
      pass

  def onMarch(self):
    if self.SelectionDirection.AxiCBox.checked:
      self.doMarch('Red')
    if self.SelectionDirection.SagCBox.checked:
      self.doMarch('Yellow')
    if self.SelectionDirection.CorCBox.checked:
      self.doMarch('Green')

  def onMarcherChanged(self, value):
    if self.SelectionDirection.AxiCBox.checked:
      self.logic.updateLabel(value / self.marcher.maximum, 'Red')
    if self.SelectionDirection.SagCBox.checked:
      self.logic.updateLabel(value / self.marcher.maximum, 'Yellow')
    if self.SelectionDirection.CorCBox.checked:
      self.logic.updateLabel(value / self.marcher.maximum, 'Green')

  def calculatePercent(self, Value, LayoutName):
    self.sliceLogic = self.editUtil.getSliceLogic(LayoutName)
    labelNode = self.logic.getLabelNode()
    labelImage = self.editUtil.getLabelImage(LayoutName)
    spacing = labelNode.GetSpacing()
    if vtk.VTK_MAJOR_VERSION <= 5:
      dim = labelImage.GetDimensions()
      totalVolume = spacing[0]*(dim[1]+1)+spacing[1]*(dim[3]+1)+spacing[2]*(dim[5]+1)
    else:
      dim = labelImage.GetDimensions()
      print dim
      totalVolume = spacing[0]*dim[0]+spacing[1]*dim[1]+spacing[2]*dim[2]
    percentVolumeStr = "%.5f" % (totalVolume * Value / 100.)
    return percentVolumeStr

  def UpdatePercentText(self, state):
    self.percentMaxChanged(self.percentMax.value)

  def percentMaxChanged(self, val):
    PercentVolumeText = '(maximum total volume: '
    if self.SelectionDirection.AxiCBox.checked:
      pcent = self.calculatePercent(val, 'Red')
      PercentVolumeText = PercentVolumeText + '[axi ' + pcent + '] '
    if self.SelectionDirection.SagCBox.checked:
      pcent = self.calculatePercent(val, 'Yellow')
      PercentVolumeText = PercentVolumeText + '[sag ' + pcent + '] '
    if self.SelectionDirection.CorCBox.checked:
      pcent = self.calculatePercent(val, 'Green')
      PercentVolumeText = PercentVolumeText + '[cor ' + pcent + '] '
    PercentVolumeText = PercentVolumeText + 'mL)'
    self.percentVolume.text = PercentVolumeText

  def updateMRMLFromGUI(self):
    if self.updatingGUI:
      return
    disableState = self.parameterNode.GetDisableModifiedEvent()
    self.parameterNode.SetDisableModifiedEvent(1)
    super(FastMarchingEffectOptions,self).updateMRMLFromGUI()
    self.parameterNode.SetDisableModifiedEvent(disableState)
    if not disableState:
      self.parameterNode.InvokePendingModifiedEvent()


#
# FastMarchingEffectTool
#

class FastMarchingEffectTool(Effect.EffectTool):
  """
  One instance of this will be created per-view when the effect
  is selected.  It is responsible for implementing feedback and
  label map changes in response to user input.
  This class observes the editor parameter node to configure itself
  and queries the current view for background and label volume
  nodes to operate on.
  """

  def __init__(self, sliceWidget):
    super(FastMarchingEffectTool,self).__init__(sliceWidget)


  def cleanup(self):
    super(FastMarchingEffectTool,self).cleanup()

  def processEvent(self, caller=None, event=None):
    """
    handle events from the render window interactor
    """
    return

  def getVolumeNode(self):
    return self.sliceWidget.sliceLogic().GetLabelLayer().GetVolumeNode()
#
# FastMarchingEffectLogic
#

class FastMarchingEffectLogic(Effect.EffectLogic):
  """
  This class contains helper methods for a given effect
  type.  It can be instanced as needed by an FastMarchingEffectTool
  or FastMarchingEffectOptions instance in order to compute intermediate
  results (say, for user feedback) or to implement the final
  segmentation editing operation.  This class is split
  from the FastMarchingEffectTool so that the operations can be used
  by other code without the need for a view context.
  """

  def __init__(self,sliceLogic):
    super(FastMarchingEffectLogic,self).__init__(sliceLogic)
    self.fm = {}

  def fastMarching(self, percentMax, LayoutName):

    self.fm.update({LayoutName : None})
    # allocate a new filter each time March is hit
    bgImage = self.editUtil.getBackgroundImage(LayoutName)
    labelImage = self.editUtil.getLabelImage(LayoutName)

    # collect seeds
    dim = bgImage.GetWholeExtent()
    # initialize the filter
    tmpfm = slicer.vtkPichonFastMarching()
    scalarRange = bgImage.GetScalarRange()
    depth = scalarRange[1]-scalarRange[0]

    # this is more or less arbitrary; large depth values will bring the
    # algorithm to the knees
    scaleValue = 0
    shiftValue = 0

    if depth>300:
      scaleValue = 300./depth
    if scalarRange[0] < 0:
      shiftValue = scalarRange[0]*-1

    if scaleValue or shiftValue:
      rescale = vtk.vtkImageShiftScale()
      if vtk.VTK_MAJOR_VERSION <= 5:
        rescale.SetInput(bgImage)
      else:
        rescale.SetInputData(bgImage)
      rescale.SetScale(scaleValue)
      rescale.SetShift(shiftValue)
      rescale.Update()
      bgImage = rescale.GetOutput()
      scalarRange = bgImage.GetScalarRange()
      depth = scalarRange[1]-scalarRange[0]

    print('Input scalar range: '+str(depth))
    if vtk.VTK_MAJOR_VERSION <= 5:
      tmpfm.init(dim[1]+1, dim[3]+1, dim[5]+1, depth, 1, 1, 1)
    else:
      tmpfm.init(dim[0], dim[1], dim[2], depth, 1, 1, 1)

    caster = vtk.vtkImageCast()
    caster.SetOutputScalarTypeToShort()
    if vtk.VTK_MAJOR_VERSION <= 5:
      caster.SetInput(bgImage)
      caster.Update()
      tmpfm.SetInput(caster.GetOutput())
    else:
      caster.SetInputData(bgImage)
      tmpfm.SetInputConnection(caster.GetOutputPort())

    # self.fm.SetOutput(labelImage)

    if vtk.VTK_MAJOR_VERSION <= 5:
      npoints = int((dim[1]+1)*(dim[3]+1)*(dim[5]+1)*percentMax/100.)
    else:
      npoints = int(dim[0]*dim[1]*dim[2]*percentMax/100.)

    tmpfm.setNPointsEvolution(npoints)
    print('Setting active label to '+str(self.editUtil.getLabel()))
    tmpfm.setActiveLabel(self.editUtil.getLabel())

    nSeeds = tmpfm.addSeedsFromImage(labelImage)
    self.fm.update({LayoutName : tmpfm})
    if nSeeds == 0:
      return 0

    tmpfm.Modified()
    tmpfm.Update()

    # TODO: need to call show() twice for data to be updated
    tmpfm.show(1)
    tmpfm.Modified()
    tmpfm.Update()

    tmpfm.show(1)
    tmpfm.Modified()
    tmpfm.Update()

    self.fm.update({LayoutName : tmpfm})

    self.undoRedo.saveState(LayoutName)

    self.editUtil.getLabelImage(LayoutName).DeepCopy(tmpfm.GetOutput())
    self.editUtil.markVolumeNodeAsModified(self.sliceLogic.GetLabelLayer().GetVolumeNode())
    # print('FastMarching output image: '+str(output))
    print('FastMarching march update completed')

    return npoints

  def updateLabel(self, value, LayoutName):
    self.sliceLogic = self.editUtil.getSliceLogic(LayoutName)
    tmpfm = self.fm.get(LayoutName)
    if not tmpfm:
      return
    tmpfm.show(value)
    tmpfm.Modified()
    tmpfm.Update()
    self.fm.update({LayoutName : tmpfm})

    self.editUtil.getLabelImage(LayoutName).DeepCopy(tmpfm.GetOutput())
    self.editUtil.getLabelImage(LayoutName).Modified()

    self.editUtil.markVolumeNodeAsModified(self.sliceLogic.GetLabelLayer().GetVolumeNode())

  def getLabelNode(self):
    return self.sliceLogic.GetLabelLayer().GetVolumeNode()


#
# The FastMarchingEffectExtension class definition
#

class FastMarchingEffect(Effect.Effect):
  """Organizes the Options, Tool, and Logic classes into a single instance
  that can be managed by the EditBox
  """

  def __init__(self):
    # name is used to define the name of the icon image resource (e.g. FastMarchingEffect.png)
    self.name = "FastMarchingEffect"
    # tool tip is displayed on mouse hover
    self.toolTip = "FastMarchingEffect - a similarity based 3D region growing"

    self.options = FastMarchingEffectOptions
    self.tool = FastMarchingEffectTool
    self.logic = FastMarchingEffectLogic
