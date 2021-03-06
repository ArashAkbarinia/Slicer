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

#include "qMRMLSceneSubjectHierarchyModel.h"

// Subject Hierarchy includes
#include "vtkMRMLSubjectHierarchyConstants.h"
#include "vtkMRMLSubjectHierarchyNode.h"
#include "vtkSlicerSubjectHierarchyModuleLogic.h"
#include "qMRMLSceneSubjectHierarchyModel_p.h"
#include "qSlicerSubjectHierarchyPluginHandler.h"
#include "qSlicerSubjectHierarchyAbstractPlugin.h"

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLSceneViewNode.h>
#include <vtkMRMLTransformNode.h>

// Qt includes
#include <QDebug>
#include <QMimeData>
#include <QApplication>
#include <QMessageBox>

//------------------------------------------------------------------------------
qMRMLSceneSubjectHierarchyModelPrivate::qMRMLSceneSubjectHierarchyModelPrivate(qMRMLSceneSubjectHierarchyModel& object)
: Superclass(object)
{
  this->NodeTypeColumn = -1;
  this->TransformColumn = -1;

  this->UnknownIcon = QIcon(":Icons/Unknown.png");
  this->WarningIcon = QIcon(":Icons/Warning.png");
}

//------------------------------------------------------------------------------
void qMRMLSceneSubjectHierarchyModelPrivate::init()
{
  Q_Q(qMRMLSceneSubjectHierarchyModel);
  this->Superclass::init();

  q->setNameColumn(0);
  q->setNodeTypeColumn(q->nameColumn());
  q->setVisibilityColumn(1);
  q->setTransformColumn(2);
  q->setIDColumn(3);

  q->setHorizontalHeaderLabels(
    QStringList() << "Node" << "Vis" << "Tr" << "IDs");

  q->horizontalHeaderItem(q->nameColumn())->setToolTip(QObject::tr("Node name and type"));
  q->horizontalHeaderItem(q->visibilityColumn())->setToolTip(QObject::tr("Show/hide branch or node"));
  q->horizontalHeaderItem(q->transformColumn())->setToolTip(QObject::tr("Applied transform"));
  q->horizontalHeaderItem(q->idColumn())->setToolTip(QObject::tr("Node ID"));

  // Set visibility icons from model to the default plugin
  qSlicerSubjectHierarchyPluginHandler::instance()->defaultPlugin()->setDefaultVisibilityIcons(this->VisibleIcon, this->HiddenIcon, this->PartiallyVisibleIcon);
}


//------------------------------------------------------------------------------

//------------------------------------------------------------------------------
qMRMLSceneSubjectHierarchyModel::qMRMLSceneSubjectHierarchyModel(QObject *vparent)
: Superclass(new qMRMLSceneSubjectHierarchyModelPrivate(*this), vparent)
{
  Q_D(qMRMLSceneSubjectHierarchyModel);
  d->init();
}

//------------------------------------------------------------------------------
qMRMLSceneSubjectHierarchyModel::~qMRMLSceneSubjectHierarchyModel()
{
}

//------------------------------------------------------------------------------
QStringList qMRMLSceneSubjectHierarchyModel::mimeTypes()const
{
  QStringList types;
  types << "application/vnd.text.list";
  return types;
}

//------------------------------------------------------------------------------
QMimeData* qMRMLSceneSubjectHierarchyModel::mimeData(const QModelIndexList &indexes) const
{
  Q_D(const qMRMLSceneSubjectHierarchyModel);

  QMimeData* mimeData = new QMimeData();
  QByteArray encodedData;

  QDataStream stream(&encodedData, QIODevice::WriteOnly);

  foreach (const QModelIndex &index, indexes)
    {
    // Only add one pointer per row
    if (index.isValid() && index.column() == 0)
      {
      d->DraggedNodes << this->mrmlNodeFromIndex(index);
      QString text = data(index, PointerRole).toString();
      stream << text;
      }
    }

  mimeData->setData("application/vnd.text.list", encodedData);
  return mimeData;
}

//------------------------------------------------------------------------------
vtkMRMLNode* qMRMLSceneSubjectHierarchyModel::parentNode(vtkMRMLNode* node)const
{
  vtkMRMLSubjectHierarchyNode* subjectHierarchyNode = vtkMRMLSubjectHierarchyNode::SafeDownCast(node);
  if (!subjectHierarchyNode)
    {
    subjectHierarchyNode = vtkMRMLSubjectHierarchyNode::GetAssociatedSubjectHierarchyNode(node);
    }
  return subjectHierarchyNode ? subjectHierarchyNode->GetParentNode() : 0;
}

//------------------------------------------------------------------------------
int qMRMLSceneSubjectHierarchyModel::nodeIndex(vtkMRMLNode* node)const
{
  Q_D(const qMRMLSceneSubjectHierarchyModel);
  if (!d->MRMLScene)
    {
    return -1;
    }

  const char* nodeId = node ? node->GetID() : 0;
  if (nodeId == 0)
    {
    return -1;
    }

  vtkMRMLSubjectHierarchyNode *shNode = vtkMRMLSubjectHierarchyNode::SafeDownCast(node);

  // Is there a hierarchy node associated with this node?
  if (!shNode)
    {
    vtkMRMLSubjectHierarchyNode *assocHierarchyNode = vtkMRMLSubjectHierarchyNode::GetAssociatedSubjectHierarchyNode(node);
    if (assocHierarchyNode)
      {
      int assocHierarchyNodeIndex = this->nodeIndex(assocHierarchyNode);
      return assocHierarchyNodeIndex + 1;
      }
    }

  int index = 0;
  vtkMRMLNode* parent = this->parentNode(node);
  if (parent)
    {
    if (shNode)
      {
      vtkMRMLSubjectHierarchyNode* parentHierarchy = vtkMRMLSubjectHierarchyNode::SafeDownCast(parent);
      const int childrenCount = parentHierarchy->GetNumberOfChildrenNodes();
      for (int i = 0; i < childrenCount ; ++i)
        {
        vtkMRMLHierarchyNode* child = parentHierarchy->GetNthChildNode(i);
        if (child == shNode)
          {
          return index;
          }
        ++index;
        }
      }
    }

  // Otherwise, iterate through the scene
  vtkCollection* nodes = d->MRMLScene->GetNodes();
  const char* nId = 0;
  vtkMRMLNode* n = 0;
  vtkCollectionSimpleIterator it;
  for (nodes->InitTraversal(it); (n = (vtkMRMLNode*)nodes->GetNextItemAsObject(it)) ;)
    {
    // Note: parent can be NULL, it means that the scene is the parent
    if (parent == this->parentNode(n))
      {
      nId = n->GetID();
      if (nId && !strcmp(nodeId, nId))
        {
        return index;
        }
      if (!vtkMRMLSubjectHierarchyNode::GetAssociatedSubjectHierarchyNode(n))
        {
        ++index;
        }
      vtkMRMLSubjectHierarchyNode* hierarchy = vtkMRMLSubjectHierarchyNode::SafeDownCast(n);
      if (hierarchy && hierarchy->GetAssociatedNode())
        {
        // if the current node is a hierarchy node associated with the node,
        // then it should have been caught at the beginning of the function
        Q_ASSERT(strcmp(nodeId, hierarchy->GetAssociatedNodeID()));
        ++index;
        }
      }
    }

  return -1;
}

//------------------------------------------------------------------------------
bool qMRMLSceneSubjectHierarchyModel::canBeAChild(vtkMRMLNode* node)const
{
  return node && node->IsA("vtkMRMLSubjectHierarchyNode");
}

//------------------------------------------------------------------------------
bool qMRMLSceneSubjectHierarchyModel::canBeAParent(vtkMRMLNode* node)const
{
  return node && node->IsA("vtkMRMLSubjectHierarchyNode");
}

//------------------------------------------------------------------------------
int qMRMLSceneSubjectHierarchyModel::nodeTypeColumn()const
{
  Q_D(const qMRMLSceneSubjectHierarchyModel);
  return d->NodeTypeColumn;
}

//------------------------------------------------------------------------------
void qMRMLSceneSubjectHierarchyModel::setNodeTypeColumn(int column)
{
  Q_D(qMRMLSceneSubjectHierarchyModel);
  d->NodeTypeColumn = column;
  this->updateColumnCount();
}

//------------------------------------------------------------------------------
int qMRMLSceneSubjectHierarchyModel::transformColumn()const
{
  Q_D(const qMRMLSceneSubjectHierarchyModel);
  return d->TransformColumn;
}

//------------------------------------------------------------------------------
void qMRMLSceneSubjectHierarchyModel::setTransformColumn(int column)
{
  Q_D(qMRMLSceneSubjectHierarchyModel);
  d->TransformColumn = column;
  this->updateColumnCount();
}

//------------------------------------------------------------------------------
int qMRMLSceneSubjectHierarchyModel::maxColumnId()const
{
  Q_D(const qMRMLSceneSubjectHierarchyModel);
  int maxId = this->Superclass::maxColumnId();
  maxId = qMax(maxId, d->VisibilityColumn);
  maxId = qMax(maxId, d->NodeTypeColumn);
  maxId = qMax(maxId, d->TransformColumn);
  maxId = qMax(maxId, d->NameColumn);
  maxId = qMax(maxId, d->IDColumn);
  return maxId;
}

//------------------------------------------------------------------------------
QFlags<Qt::ItemFlag> qMRMLSceneSubjectHierarchyModel::nodeFlags(vtkMRMLNode* node, int column)const
{
  QFlags<Qt::ItemFlag> flags = this->Superclass::nodeFlags(node, column);

  if (column == this->transformColumn() && node)
    {
    flags = flags | Qt::ItemIsEditable;
    }

  return flags;
}

//------------------------------------------------------------------------------
void qMRMLSceneSubjectHierarchyModel::updateItemDataFromNode(QStandardItem* item, vtkMRMLNode* node, int column)
{
  Q_D(qMRMLSceneSubjectHierarchyModel);

  vtkMRMLSubjectHierarchyNode* subjectHierarchyNode = vtkMRMLSubjectHierarchyNode::SafeDownCast(node);
  if (!subjectHierarchyNode)
    {
    return;
    }
  qSlicerSubjectHierarchyAbstractPlugin* ownerPlugin =
    qSlicerSubjectHierarchyPluginHandler::instance()->getOwnerPluginForSubjectHierarchyNode(subjectHierarchyNode);
  if (!ownerPlugin)
    {
    // Set warning icon if the column is the node type column
    if (column == this->nodeTypeColumn())
      {
      item->setIcon(d->WarningIcon);
      }

    qCritical() << "qMRMLSceneSubjectHierarchyModel::updateItemDataFromNode: No owner plugin defined for subject hierarchy node '" << subjectHierarchyNode->GetName() << "'!";
    return;
    }

  // Name column
  if (column == this->nameColumn())
    {
    // Have owner plugin set the name and the tooltip
    item->setText(ownerPlugin->displayedName(subjectHierarchyNode));
    item->setToolTip(ownerPlugin->tooltip(subjectHierarchyNode));
    }
  // ID column
  if (column == this->idColumn())
    {
    item->setText(QString(subjectHierarchyNode->GetID()));
    }
  // Visibility column
  if (column == this->visibilityColumn())
    {
    // Have owner plugin set the visibility icon
    ownerPlugin->setVisibilityIcon(subjectHierarchyNode, item);
    }
  // Node type column
  if (column == this->nodeTypeColumn())
    {
    // Have owner plugin set the icon
    bool iconSetSuccessfullyByPlugin = ownerPlugin->setIcon(subjectHierarchyNode, item);
    if (!iconSetSuccessfullyByPlugin)
      {
      item->setIcon(d->UnknownIcon);
      }
    }
  // Transform column
  if (column == this->transformColumn())
    {
    if (item->data(Qt::WhatsThisRole).toString().isEmpty())
      {
      item->setData( "Transform", Qt::WhatsThisRole );
      }

    vtkMRMLNode* associatedNode = subjectHierarchyNode->GetAssociatedNode();
    vtkMRMLTransformableNode* transformableNode = vtkMRMLTransformableNode::SafeDownCast(associatedNode);
    if (transformableNode)
      {
      vtkMRMLTransformNode* parentTransformNode = ( transformableNode->GetParentTransformNode() ? transformableNode->GetParentTransformNode() : NULL );
      QString transformNodeId( parentTransformNode ? parentTransformNode->GetID() : "" );
      QString transformNodeName( parentTransformNode ? parentTransformNode->GetName() : "" );
      // Only change item if the transform itself changed
      if (item->text().compare(transformNodeName))
        {
        item->setData( transformNodeId, qMRMLSceneSubjectHierarchyModel::TransformIDRole );
        item->setText( transformNodeName );
        item->setToolTip( parentTransformNode ? tr("%1 (%2)").arg(parentTransformNode->GetName()).arg(parentTransformNode->GetID()) : "" );
        }
      }
    else
      {
      //item->setData( tr(""), qMRMLSceneSubjectHierarchyModel::TransformIDRole );
      item->setToolTip(tr("No transform can be directly applied on non-transformable nodes,\nhowever a transform can be chosen to apply it on all the children"));
      }
    }
}

//------------------------------------------------------------------------------
void qMRMLSceneSubjectHierarchyModel::updateNodeFromItemData(vtkMRMLNode* node, QStandardItem* item)
{
  vtkMRMLSubjectHierarchyNode* subjectHierarchyNode = vtkMRMLSubjectHierarchyNode::SafeDownCast(node);
  if (!subjectHierarchyNode)
    {
    qCritical() << "qMRMLSceneSubjectHierarchyModel::updateNodeFromItemData: Invalid node in subject hierarchy tree! Nodes must all be subject hierarchy nodes";
    return;
    }
  qSlicerSubjectHierarchyAbstractPlugin* ownerPlugin =
    qSlicerSubjectHierarchyPluginHandler::instance()->getOwnerPluginForSubjectHierarchyNode(subjectHierarchyNode);

  // Name column
  if ( item->column() == this->nameColumn() )
    {
    subjectHierarchyNode->SetName(item->text().append(vtkMRMLSubjectHierarchyConstants::SUBJECTHIERARCHY_NODE_NAME_POSTFIX.c_str()).toLatin1().constData());

    // Rename data node too
    vtkMRMLNode* associatedDataNode = subjectHierarchyNode->GetAssociatedNode();
    if (associatedDataNode)
      {
      associatedDataNode->SetName(item->text().toLatin1().constData());
      }
    }
  // Visibility column
  if ( item->column() == this->visibilityColumn()
    && !item->data(VisibilityRole).isNull() )
    {
    int visible = item->data(VisibilityRole).toInt();
    if (visible > -1)
      {
      // Have owner plugin set the display visibility
      ownerPlugin->setDisplayVisibility(subjectHierarchyNode, visible);
      }
    }
  // Transform column
  if (item->column() == this->transformColumn())
    {
    QVariant transformIdData = item->data(qMRMLSceneSubjectHierarchyModel::TransformIDRole);
    std::string newParentTransformNodeIdStr = transformIdData.toString().toLatin1().constData();
    vtkMRMLTransformNode* newParentTransformNode =
      vtkMRMLTransformNode::SafeDownCast( this->mrmlScene()->GetNodeByID(newParentTransformNodeIdStr) );

    // No checks and questions when the transform is being removed
    if (!newParentTransformNode)
      {
      subjectHierarchyNode->TransformBranch(NULL, false);
      return;
      }

    // No action if the chosen transform is the same as the applied one
    vtkMRMLTransformableNode* dataNode = vtkMRMLTransformableNode:: SafeDownCast(
      subjectHierarchyNode->GetAssociatedNode() );
    if (dataNode && dataNode->GetParentTransformNode() == newParentTransformNode)
      {
      return;
      }

    // Ask the user if any child node in the tree is transformed with a transform different from the chosen one
    bool hardenExistingTransforms = true;
    if (subjectHierarchyNode->IsAnyNodeInBranchTransformed(newParentTransformNode))
      {
      QMessageBox::StandardButton answer =
        QMessageBox::question(NULL, tr("Some nodes in the branch are already transformed"),
        tr("Do you want to harden all already applied transforms before setting the new one?\n\n"
        "  Note: If you choose no, then the applied transform will simply be replaced."),
        QMessageBox::Yes | QMessageBox::No | QMessageBox::Cancel,
        QMessageBox::Yes);
      if (answer == QMessageBox::No)
        {
        hardenExistingTransforms = false;
        }
      else if (answer == QMessageBox::Cancel)
        {
        //qDebug() << "qMRMLSceneSubjectHierarchyModel::updateNodeFromItemData: Transform branch cancelled";
        return;
        }
      }

    subjectHierarchyNode->TransformBranch(newParentTransformNode, hardenExistingTransforms);
    }
}

//------------------------------------------------------------------------------
bool qMRMLSceneSubjectHierarchyModel::dropMimeData(const QMimeData* data, Qt::DropAction action, int row, int column, const QModelIndex &parent)
{
  Q_D(const qMRMLSceneSubjectHierarchyModel);
  Q_UNUSED(row);
  Q_UNUSED(column);

  // This list is not used now in this model, can be emptied
  d->DraggedNodes.clear();

  if (action == Qt::IgnoreAction)
    {
    return true;
    }
  if (!this->mrmlScene())
    {
    std::cerr << "qMRMLSceneSubjectHierarchyModel::dropMimeData: Invalid MRML scene!" << std::endl;
    return false;
    }
  if (!data->hasFormat("application/vnd.text.list"))
    {
    vtkErrorWithObjectMacro(this->mrmlScene(), "qMRMLSceneSubjectHierarchyModel::dropMimeData: Plain text MIME type is expected");
    return false;
    }

  // Nothing can be dropped to the top level (subjects/patients can only be loaded at from the DICOM browser or created manually)
  if (!parent.isValid())
    {
    vtkWarningWithObjectMacro(this->mrmlScene(), "qMRMLSceneSubjectHierarchyModel::dropMimeData: Items cannot be dropped on top level!");
    return false;
    }
  vtkMRMLNode* parentNode = this->mrmlNodeFromIndex(parent);
  if (!parentNode)
    {
    vtkErrorWithObjectMacro(this->mrmlScene(), "qMRMLSceneSubjectHierarchyModel::dropMimeData: Unable to get parent node!");
    // TODO: This is a workaround. Without this the node disappears and the tree collapses
    emit saveTreeExpandState();
    QApplication::processEvents();
    emit invalidateModels();
    QApplication::processEvents();
    this->updateScene();
    emit loadTreeExpandState();
    return false;
    }

  // Decode MIME data
  QByteArray encodedData = data->data("application/vnd.text.list");
  QDataStream stream(&encodedData, QIODevice::ReadOnly);
  QStringList streamItems;
  int rows = 0;

  while (!stream.atEnd())
    {
    QString text;
    stream >> text;
    streamItems << text;
    ++rows;
    }

  if (rows == 0)
    {
    vtkErrorWithObjectMacro(this->mrmlScene(), "qMRMLSceneSubjectHierarchyModel::dropMimeData: Unable to decode dropped MIME data!");
    return false;
    }
  if (rows > 1)
    {
    vtkWarningWithObjectMacro(this->mrmlScene(), "qMRMLSceneSubjectHierarchyModel::dropMimeData: More than one data item decoded from dropped MIME data! Only the first one will be used.");
    }

  QString nodePointerString = streamItems[0];

  vtkMRMLNode* droppedNode = vtkMRMLNode::SafeDownCast(reinterpret_cast<vtkObject*>(nodePointerString.toULongLong()));
  if (!droppedNode)
    {
    vtkErrorWithObjectMacro(this->mrmlScene(), "qMRMLSceneSubjectHierarchyModel::dropMimeData: Unable to get MRML node from dropped MIME text (" << nodePointerString.toLatin1().constData() << ")!");
    return false;
    }

  // Reparent the node
  return this->reparent(droppedNode, parentNode);
}

//------------------------------------------------------------------------------
bool qMRMLSceneSubjectHierarchyModel::reparent(vtkMRMLNode* node, vtkMRMLNode* newParent)
{
  if (!node || newParent == node)
    {
    std::cerr << "qMRMLSceneSubjectHierarchyModel::reparent: Invalid node to reparent!" << std::endl;
    return false;
    }

  // Prevent collapse of the subject hierarchy tree view (TODO: This is a workaround)
  emit saveTreeExpandState();
  QApplication::processEvents();

  if (this->parentNode(node) == newParent)
    {
    // TODO: This is a workaround. Without this the node disappears and the tree collapses
    emit invalidateModels();
    QApplication::processEvents();
    this->updateScene();
    emit loadTreeExpandState();
    return true;
    }

  if (!this->mrmlScene())
    {
    std::cerr << "qMRMLSceneSubjectHierarchyModel::reparent: Invalid MRML scene!" << std::endl;
    return false;
    }

  vtkMRMLSubjectHierarchyNode* parentSubjectHierarchyNode = vtkMRMLSubjectHierarchyNode::SafeDownCast(newParent);
  vtkMRMLSubjectHierarchyNode* subjectHierarchyNode = vtkMRMLSubjectHierarchyNode::SafeDownCast(node);

  if (!this->canBeAParent(newParent))
    {
    vtkWarningWithObjectMacro(this->mrmlScene(), "qMRMLSceneSubjectHierarchyModel::reparent: Target parent node (" << newParent->GetName() << ") is not a valid subject hierarchy parent node!");
    }

  // If dropped from within the subject hierarchy tree
  if (subjectHierarchyNode)
    {
    bool successfullyReparentedByPlugin = false;
    QList<qSlicerSubjectHierarchyAbstractPlugin*> foundPlugins =
      qSlicerSubjectHierarchyPluginHandler::instance()->pluginsForReparentingInsideSubjectHierarchyForNode(subjectHierarchyNode, parentSubjectHierarchyNode);
    qSlicerSubjectHierarchyAbstractPlugin* selectedPlugin = NULL;
    if (foundPlugins.size() > 1)
      {
      // Let the user choose a plugin if more than one returned the same non-zero confidence value
      vtkMRMLNode* associatedNode = (subjectHierarchyNode->GetAssociatedNode() ? subjectHierarchyNode->GetAssociatedNode() : subjectHierarchyNode);
      QString textToDisplay = QString("Equal confidence number found for more than one subject hierarchy plugin for reparenting.\n\nSelect plugin to reparent node named\n'%1'\n(type %2)\nParent node: %3").arg(associatedNode->GetName()).arg(associatedNode->GetNodeTagName()).arg(parentSubjectHierarchyNode->GetName());
      selectedPlugin = qSlicerSubjectHierarchyPluginHandler::instance()->selectPluginFromDialog(textToDisplay, foundPlugins);
      }
    else if (foundPlugins.size() == 1)
      {
      selectedPlugin = foundPlugins[0];
      }
    else
      {
      // Choose default plugin if all registered plugins returned confidence value 0
      selectedPlugin = qSlicerSubjectHierarchyPluginHandler::instance()->defaultPlugin();
      }

    // Have the selected plugin reparent the node
    successfullyReparentedByPlugin = selectedPlugin->reparentNodeInsideSubjectHierarchy(subjectHierarchyNode, parentSubjectHierarchyNode);
    if (!successfullyReparentedByPlugin)
      {
      // TODO: Does this cause #473?
      // Put back to its original place
      subjectHierarchyNode->SetParentNodeID( subjectHierarchyNode->GetParentNodeID() );

      vtkWarningWithObjectMacro(this->mrmlScene(), "qMRMLSceneSubjectHierarchyModel::reparent: Failed to reparent node "
        << subjectHierarchyNode->GetName() << " through plugin '" << selectedPlugin->name().toLatin1().constData() << "'");
      }
    }
  // If dropped from the potential subject hierarchy nodes list
  else
    {
    // If there is a plugin that can handle the dropped node then let it take care of it
    bool successfullyAddedByPlugin = false;
    QList<qSlicerSubjectHierarchyAbstractPlugin*> foundPlugins =
      qSlicerSubjectHierarchyPluginHandler::instance()->pluginsForAddingToSubjectHierarchyForNode(node, parentSubjectHierarchyNode);
    qSlicerSubjectHierarchyAbstractPlugin* selectedPlugin = NULL;
    if (foundPlugins.size() > 1)
      {
      // Let the user choose a plugin if more than one returned the same non-zero confidence value
      QString textToDisplay = QString("Equal confidence number found for more than one subject hierarchy plugin for adding potential node to subject hierarchy.\n\nSelect plugin to add node named\n'%1'\n(type %2)\nParent node: %3").arg(node->GetName()).arg(node->GetNodeTagName()).arg(parentSubjectHierarchyNode->GetName());
      selectedPlugin = qSlicerSubjectHierarchyPluginHandler::instance()->selectPluginFromDialog(textToDisplay, foundPlugins);
      }
    else if (foundPlugins.size() == 1)
      {
      selectedPlugin = foundPlugins[0];
      }
    else
      {
      // Choose default plugin if all registered plugins returned confidence value 0
      selectedPlugin = qSlicerSubjectHierarchyPluginHandler::instance()->defaultPlugin();
      }

    // Have the selected plugin add the potential node to subject hierarchy
    successfullyAddedByPlugin = selectedPlugin->addNodeToSubjectHierarchy(node, parentSubjectHierarchyNode);
    if (!successfullyAddedByPlugin)
      {
      vtkWarningWithObjectMacro(this->mrmlScene(), "qMRMLSceneSubjectHierarchyModel::reparent: Failed to add node "
        << node->GetName() << " through plugin '" << selectedPlugin->name().toLatin1().constData() << "'");
      }
    }

  // TODO: This is a workaround. Without this the node disappears and the tree collapses
  emit invalidateModels();
  QApplication::processEvents();
  this->updateScene();
  emit loadTreeExpandState();

  return true;
}

//------------------------------------------------------------------------------
void qMRMLSceneSubjectHierarchyModel::onHardenTransformOnBranchOfCurrentNode()
{
  vtkMRMLSubjectHierarchyNode* currentNode = qSlicerSubjectHierarchyPluginHandler::instance()->currentNode();
  if (currentNode)
    {
    currentNode->HardenTransformOnBranch();
    }
}

//------------------------------------------------------------------------------
void qMRMLSceneSubjectHierarchyModel::onRemoveTransformsFromBranchOfCurrentNode()
{
  vtkMRMLSubjectHierarchyNode* currentNode = qSlicerSubjectHierarchyPluginHandler::instance()->currentNode();
  if (currentNode)
    {
    currentNode->TransformBranch(NULL, false);
    }
}

//------------------------------------------------------------------------------
void qMRMLSceneSubjectHierarchyModel::forceUpdateScene()
{
  // Force updating the whole scene (TODO: this should not be needed)
  this->updateScene();
}
