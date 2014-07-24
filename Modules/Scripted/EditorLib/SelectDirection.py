import slicer
from __main__ import qt
from __main__ import vtk

#########################################################
#
# 
comment = """

  SelectDirection is a wrapper around a set of Qt widgets and other
  structures to manage the checkboxes of sellecting which direction
  is active.

# TODO :
"""
#
#########################################################

class SelectDirection(object):

  def __init__(self, parent = 0):
    self.observerTags = []
    self.parameterNode = None
    self.parameterNodeTag = None
    if parent == 0:
      self.parent = slicer.qMRMLWidget()
      self.parent.setLayout(qt.QVBoxLayout())
      self.parent.setMRMLScene(slicer.mrmlScene)
      self.create()
      self.parent.show()
    else:
      self.parent = parent
      self.create()

  def __del__(self):
    self.cleanup()

  def cleanup(self, QObject=None):
    if self.parameterNode:
      self.parameterNode.RemoveObserver(self.parameterNodeTag)
    for tagpair in self.observerTags:
      tagpair[0].RemoveObserver(tagpair[1])

  def create(self):
    self.frame = qt.QFrame(self.parent)
    self.frame.objectName = 'SelectDirectionFrame'
    self.frame.setLayout(qt.QHBoxLayout())
    self.parent.layout().addWidget(self.frame)

    self.AxiCBox = qt.QCheckBox("Axial", self.frame)
    self.AxiCBox.objectName = 'AxiCheckBox'
    self.AxiCBox.setToolTip("Apply the effect on axial view.")
    self.AxiCBox.setChecked(True)
    self.frame.layout().addWidget(self.AxiCBox)

    self.SagCBox = qt.QCheckBox("Sagittal", self.frame)
    self.SagCBox.objectName = 'SagCheckBox'
    self.SagCBox.setToolTip("Apply the effect on sagittal view.")
    self.SagCBox.setChecked(True)
    self.frame.layout().addWidget(self.SagCBox)

    self.CorCBox = qt.QCheckBox("Coronal", self.frame)
    self.CorCBox.objectName = 'CorCheckBox'
    self.CorCBox.setToolTip("Apply the effect on coronal view.")
    self.CorCBox.setChecked(True)
    self.frame.layout().addWidget(self.CorCBox)
