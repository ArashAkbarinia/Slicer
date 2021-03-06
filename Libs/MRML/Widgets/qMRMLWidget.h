/*==============================================================================

  Program: 3D Slicer

  Copyright (c) Kitware Inc.

  See COPYRIGHT.txt
  or http://www.slicer.org/copyright/copyright.txt for details.

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

  This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc.
  and was partially funded by NIH grant 3P41RR013218-12S1

==============================================================================*/

#ifndef __qMRMLWidget_h
#define __qMRMLWidget_h

// Qt includes
#include <QWidget>

// MRMLWidgets includes
#include "qMRMLWidgetsExport.h"
class qMRMLWidgetPrivate;

// VTK includes
class vtkMRMLScene;

/// Base class for any widget that requires a MRML Scene.
class QMRML_WIDGETS_EXPORT qMRMLWidget : public QWidget
{
  Q_OBJECT

public:

  typedef QWidget Superclass;
  explicit qMRMLWidget(QWidget *parent=0, Qt::WindowFlags f=0);
  virtual ~qMRMLWidget();

  /// Return a pointer on the current MRML scene
  vtkMRMLScene* mrmlScene() const;

public slots:

  /// Set the MRML \a scene associated with the widget
  virtual void setMRMLScene(vtkMRMLScene* newScene);

signals:
  /// When designing custom qMRMLWidget in the designer, you can connect the
  /// mrmlSceneChanged signal directly to the aggregated MRML widgets that
  /// have a setMRMLScene slot.
  void mrmlSceneChanged(vtkMRMLScene*);

protected:
  QScopedPointer<qMRMLWidgetPrivate> d_ptr;

private:
  Q_DECLARE_PRIVATE(qMRMLWidget);
  Q_DISABLE_COPY(qMRMLWidget);
};

#endif
