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

#ifndef __qMRMLScenePotentialSubjectHierarchyModel_p_h
#define __qMRMLScenePotentialSubjectHierarchyModel_p_h

// qMRML includes
#include "qMRMLScenePotentialSubjectHierarchyModel.h"
#include "qMRMLSceneHierarchyModel_p.h"

//------------------------------------------------------------------------------
// qMRMLScenePotentialSubjectHierarchyModelPrivate
//------------------------------------------------------------------------------

//------------------------------------------------------------------------------
/// \ingroup Slicer_QtModules_SubjectHierarchy
class Q_SLICER_MODULE_SUBJECTHIERARCHY_WIDGETS_EXPORT qMRMLScenePotentialSubjectHierarchyModelPrivate
  : public qMRMLSceneModelPrivate
{
protected:
  Q_DECLARE_PUBLIC(qMRMLScenePotentialSubjectHierarchyModel);

public:
  typedef qMRMLSceneModelPrivate Superclass;
  qMRMLScenePotentialSubjectHierarchyModelPrivate(qMRMLScenePotentialSubjectHierarchyModel& object);
  virtual void init();
};

#endif
