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

// SubjectHierarchy MRML includes
#include "vtkMRMLSubjectHierarchyConstants.h"
#include "vtkMRMLSubjectHierarchyNode.h"

// SubjectHierarchy Plugins includes
#include "qSlicerSubjectHierarchyPluginHandler.h"
#include "qSlicerSubjectHierarchyParseLocalDataPlugin.h"

// Qt includes
#include <QDebug>
#include <QAction>
#include <QStandardItem>

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLStorableNode.h>
#include <vtkMRMLStorageNode.h>

// VTK includes
#include <vtkObjectFactory.h>
#include <vtkSmartPointer.h>
#include <vtkCollection.h>

//-----------------------------------------------------------------------------
/// \ingroup Slicer_QtModules_SubjectHierarchy_Plugins
class qSlicerSubjectHierarchyParseLocalDataPluginPrivate: public QObject
{
  Q_DECLARE_PUBLIC(qSlicerSubjectHierarchyParseLocalDataPlugin);
protected:
  qSlicerSubjectHierarchyParseLocalDataPlugin* const q_ptr;
public:
  qSlicerSubjectHierarchyParseLocalDataPluginPrivate(qSlicerSubjectHierarchyParseLocalDataPlugin& object);
  ~qSlicerSubjectHierarchyParseLocalDataPluginPrivate();
  void init();
public:
  QAction* CreateHierarchyFromLoadedLocalDirectoriesAction;
};

//-----------------------------------------------------------------------------
// qSlicerSubjectHierarchyParseLocalDataPluginPrivate methods

//-----------------------------------------------------------------------------
qSlicerSubjectHierarchyParseLocalDataPluginPrivate::qSlicerSubjectHierarchyParseLocalDataPluginPrivate(qSlicerSubjectHierarchyParseLocalDataPlugin& object)
: q_ptr(&object)
{
  this->CreateHierarchyFromLoadedLocalDirectoriesAction = NULL;
}

//------------------------------------------------------------------------------
void qSlicerSubjectHierarchyParseLocalDataPluginPrivate::init()
{
  Q_Q(qSlicerSubjectHierarchyParseLocalDataPlugin);

  this->CreateHierarchyFromLoadedLocalDirectoriesAction = new QAction("Create hierarchy from loaded directory structure",q);
  QObject::connect(this->CreateHierarchyFromLoadedLocalDirectoriesAction, SIGNAL(triggered()), q, SLOT(createHierarchyFromLoadedLocalDirectories()));
}

//-----------------------------------------------------------------------------
qSlicerSubjectHierarchyParseLocalDataPluginPrivate::~qSlicerSubjectHierarchyParseLocalDataPluginPrivate()
{
}

//-----------------------------------------------------------------------------
qSlicerSubjectHierarchyParseLocalDataPlugin::qSlicerSubjectHierarchyParseLocalDataPlugin(QObject* parent)
 : Superclass(parent)
 , d_ptr( new qSlicerSubjectHierarchyParseLocalDataPluginPrivate(*this) )
{
  this->m_Name = QString("ParseLocalData");

  Q_D(qSlicerSubjectHierarchyParseLocalDataPlugin);
  d->init();
}

//-----------------------------------------------------------------------------
qSlicerSubjectHierarchyParseLocalDataPlugin::~qSlicerSubjectHierarchyParseLocalDataPlugin()
{
}

//-----------------------------------------------------------------------------
QList<QAction*> qSlicerSubjectHierarchyParseLocalDataPlugin::sceneContextMenuActions()const
{
  Q_D(const qSlicerSubjectHierarchyParseLocalDataPlugin);

  QList<QAction*> actions;
  actions << d->CreateHierarchyFromLoadedLocalDirectoriesAction;
  return actions;
}

//---------------------------------------------------------------------------
void qSlicerSubjectHierarchyParseLocalDataPlugin::showContextMenuActionsForNode(vtkMRMLSubjectHierarchyNode* node)
{
  Q_D(qSlicerSubjectHierarchyParseLocalDataPlugin);
  this->hideAllContextMenuActions();

  // Scene
  if (!node)
    {
    // Only show create hierarchy from loaded local directory structure if there are possible nodes to use
    // That is to have nodes in the scene with storage nodes with valid file names outside subject hierarchy
    vtkMRMLScene* scene = qSlicerSubjectHierarchyPluginHandler::instance()->scene();
    vtkSmartPointer<vtkCollection> storableNodes = vtkSmartPointer<vtkCollection>::Take( scene->GetNodesByClass("vtkMRMLStorableNode") );
    vtkObject* nextObject = NULL;
    for (storableNodes->InitTraversal(); (nextObject = storableNodes->GetNextItemAsObject()); )
      {
      vtkMRMLStorableNode* storableNode = vtkMRMLStorableNode::SafeDownCast(nextObject);
      if ( storableNode && storableNode->GetStorageNode() && !storableNode->GetHideFromEditors() )
        {
        QList<qSlicerSubjectHierarchyAbstractPlugin*> foundPlugins =
          qSlicerSubjectHierarchyPluginHandler::instance()->pluginsForAddingToSubjectHierarchyForNode(storableNode);
        if (!foundPlugins.empty())
          {
          d->CreateHierarchyFromLoadedLocalDirectoriesAction->setVisible(true);
          }
        }
      }
    }
}

//--------------------------------------------------------------------------
void qSlicerSubjectHierarchyParseLocalDataPlugin::createHierarchyFromLoadedLocalDirectories()
{
  QList<QStringList> loadedFilePaths;
  QList<vtkMRMLStorableNode*> loadedNodes;
  vtkMRMLScene* scene = qSlicerSubjectHierarchyPluginHandler::instance()->scene();

  // Get all file paths from the storable nodes into the list
  vtkSmartPointer<vtkCollection> storableNodes = vtkSmartPointer<vtkCollection>::Take( scene->GetNodesByClass("vtkMRMLStorableNode") );
  vtkObject* nextObject = NULL;
  for (storableNodes->InitTraversal(); (nextObject = storableNodes->GetNextItemAsObject()); )
    {
    vtkMRMLStorableNode* storableNode = vtkMRMLStorableNode::SafeDownCast(nextObject);
    if ( storableNode && storableNode->GetStorageNode() && !storableNode->GetHideFromEditors() )
      {
      QList<qSlicerSubjectHierarchyAbstractPlugin*> foundPlugins =
        qSlicerSubjectHierarchyPluginHandler::instance()->pluginsForAddingToSubjectHierarchyForNode(storableNode);
      if (!foundPlugins.empty())
        {
        vtkMRMLStorageNode* storageNode = storableNode->GetStorageNode();
        // Cannot parse if loaded from multiple files (in which case there is a non-empty file list)
        if ( storageNode->GetNumberOfFileNames() == 0
          && storageNode->GetFileName() )
          {
          QString filePath(storageNode->GetFileName());
          loadedFilePaths << filePath.split('/', QString::SkipEmptyParts);
          loadedNodes << storableNode;
          }
        }
      }
    }
  if (loadedFilePaths.empty())
    {
    return;
    }

  // Remove the leading components of the file paths until they match
  bool firstComponentMatch = true;
  do
    {
    QString firstComponent;
    foreach(QStringList filePath, loadedFilePaths)
      {
      if (filePath.count() == 0)
        {
        qWarning() << "qSlicerSubjectHierarchyParseLocalDataPlugin::createHierarchyFromLoadedLocalDirectories: Too shallow file path found!";
        firstComponentMatch = false;
        break;
        }
      if (firstComponent.isEmpty())
        {
        firstComponent = filePath[0];
        }
      else if (firstComponent.compare(filePath[0]))
        {
        firstComponentMatch = false;
        break;
        }
      }

    // If first component matches through all file paths, remove it
    if (firstComponentMatch)
      {
      qDebug() << "qSlicerSubjectHierarchyParseLocalDataPlugin::createHierarchyFromLoadedLocalDirectories: "
                  "First component (" << firstComponent << ") matches in all paths, removing";
      for (int i=0; i<loadedFilePaths.count(); ++i)
        {
        QStringList currentFilePath = loadedFilePaths[i];
        currentFilePath.removeFirst();
        loadedFilePaths.replace(i, currentFilePath);
        }
      }
    }
  while (firstComponentMatch);

  // Create hierarchy
  QList<vtkMRMLSubjectHierarchyNode*> createdNodes;
  for (int nodeIndex=0; nodeIndex<loadedNodes.count(); ++nodeIndex)
    {
    vtkMRMLSubjectHierarchyNode* parent = NULL;
    foreach(QString component, loadedFilePaths[nodeIndex])
      {
      vtkMRMLSubjectHierarchyNode* foundNode = vtkMRMLSubjectHierarchyNode::GetChildWithName(parent, component.toLatin1().constData(), scene);
      if (foundNode)
        {
        parent = foundNode;
        }
      else
        {
        parent = qSlicerSubjectHierarchyPluginHandler::instance()->pluginByName("DICOM")->createChildNode(parent, component);
        createdNodes << parent;
        }
      }
    parent->SetAssociatedNodeID(loadedNodes[nodeIndex]->GetID());

    // Have it removed from potential list if added
    loadedNodes[nodeIndex]->Modified();
    }

  foreach(vtkMRMLSubjectHierarchyNode* createdNode, createdNodes)
    {
    emit requestExpandNode(createdNode);
    }
}
