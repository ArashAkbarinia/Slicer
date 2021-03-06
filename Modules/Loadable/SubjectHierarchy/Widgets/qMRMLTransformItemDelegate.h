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

  This file was originally developed by Csaba Pinter, PerkLab, Queen's University
  and was supported through the Applied Cancer Research Unit program of Cancer Care
  Ontario with funds provided by the Ontario Ministry of Health and Long-Term Care

==============================================================================*/

#ifndef __qMRMLTransformItemDelegate_h
#define __qMRMLTransformItemDelegate_h

// Qt includes
#include <QStyledItemDelegate>

// SubjectHierarchy includes
#include "qSlicerSubjectHierarchyModuleWidgetsExport.h"

class vtkMRMLScene;

/// \brief Item Delegate for MRML parent transform property
class Q_SLICER_MODULE_SUBJECTHIERARCHY_WIDGETS_EXPORT qMRMLTransformItemDelegate: public QStyledItemDelegate
{
  Q_OBJECT
public:
  qMRMLTransformItemDelegate(QObject *parent = 0);
  virtual ~qMRMLTransformItemDelegate();

  void setMRMLScene(vtkMRMLScene* scene);

  bool isTransform(const QModelIndex& index)const;

  virtual QWidget *createEditor(QWidget *parent, const QStyleOptionViewItem &option,
    const QModelIndex &index) const;

  virtual void setEditorData(QWidget *editor, const QModelIndex &index) const;
  virtual void setModelData(QWidget *editor, QAbstractItemModel *model,
                    const QModelIndex &index) const;

  virtual QSize sizeHint(const QStyleOptionViewItem &option,
                         const QModelIndex &index) const;

  void updateEditorGeometry(QWidget *editor,
    const QStyleOptionViewItem &option, const QModelIndex &index) const;

  virtual bool eventFilter(QObject *object, QEvent *event);

  // We make initStyleOption public so it can be used by qMRMLTreeView
  using QStyledItemDelegate::initStyleOption;

signals:
  void removeTransformsFromBranchOfCurrentNode();
  void hardenTransformOnBranchOfCurrentNode();

protected slots:
  void commitAndClose();

protected:
  vtkMRMLScene* MRMLScene;
  QAction* RemoveTransformAction;
  QAction* HardenAction;
};

#endif
