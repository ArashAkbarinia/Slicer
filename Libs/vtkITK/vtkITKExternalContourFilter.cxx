/*=========================================================================

Program:   Visualization Toolkit
Module:    $RCSfile: vtkITKExternalContourFilter.cxx,v $

Copyright (c) Arash Akbarinia
All rights reserved.
See Copyright.txt or http://www.kitware.com/Copyright.htm for details.

This software is distributed WITHOUT ANY WARRANTY; without even
the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE.  See the above copyright notice for more information.


=========================================================================*/
#include "vtkITKExternalContourFilter.h"

#include "vtkCellArray.h"
#include "vtkInformation.h"
#include "vtkInformationVector.h"
#include "vtkLine.h"
#include "vtkPointData.h"
#include "vtkStructuredPoints.h"
#include "vtkStreamingDemandDrivenPipeline.h"
#include "vtkSmartPointer.h"

#include "itkExtractImageFilter.h"
#include "itkBinaryContourImageFilter.h"
#include "itkBinaryFillholeImageFilter.h"
#include "itkImageRegionConstIterator.h"

vtkStandardNewMacro ( vtkITKExternalContourFilter );

vtkITKExternalContourFilter::vtkITKExternalContourFilter()
{
  SliceNumber = 0;
}

vtkITKExternalContourFilter::~vtkITKExternalContourFilter()
{
}


template <class T>
void vtkITKExtractExternalContours ( vtkITKExternalContourFilter *vtkNotUsed ( self ), T* scalars,
                                     int dims[3], int extent[6], double origin[3], double spacing[3],
                                     vtkPoints *newPoints, vtkCellArray *newPolys, int SliceNumber )
{
  // Wrap scalars into an ITK image
  typedef itk::Image<T, 3> ImageType;
  typename ImageType::Pointer image = ImageType::New();
  image->GetPixelContainer()->SetImportPointer ( scalars, dims[0]*dims[1]*dims[2], false );
  image->SetOrigin ( origin );
  image->SetSpacing ( spacing );

  typename ImageType::RegionType region;
  typename ImageType::IndexType index;
  typename ImageType::SizeType size;
  index[0] = extent[0];
  index[1] = extent[2];
  index[2] = extent[4];
  region.SetIndex ( index );
  size[0] = extent[1] - extent[0] + 1;
  size[1] = extent[3] - extent[2] + 1;
  size[2] = extent[5] - extent[4] + 1;
  region.SetSize ( size );
  image->SetRegions ( region );

  // Extract the 2D slice to process
  typedef itk::Image<T,2> Image2DType;
  typedef itk::ExtractImageFilter<ImageType, Image2DType> ExtractType;
  typename ExtractType::Pointer extract = ExtractType::New();
#if  ITK_VERSION_MAJOR >=4
  extract->SetDirectionCollapseToIdentity(); //If you don't care about resulting image dimension
#endif

  typename ImageType::RegionType InputRegion = image->GetLargestPossibleRegion();
  typename ImageType::SizeType ExtractSize = InputRegion.GetSize();
  ExtractSize[2] = 0;
  typename ImageType::IndexType ExtractStart = InputRegion.GetIndex();
  ExtractStart[2] = SliceNumber;
  typename ImageType::RegionType DesiredRegion;
  DesiredRegion.SetSize ( ExtractSize );
  DesiredRegion.SetIndex ( ExtractStart );

  extract->SetInput ( image );
  extract->SetExtractionRegion ( DesiredRegion );

  // Get the external contours using itk::ExternalContourFilter
  typedef itk::BinaryFillholeImageFilter<Image2DType> binaryFillholeImageFilter;
  typename binaryFillholeImageFilter::Pointer binaryFillHoleFilter = binaryFillholeImageFilter::New();
  binaryFillHoleFilter->SetForegroundValue ( 1 );
  binaryFillHoleFilter->SetInput ( extract->GetOutput() );
  binaryFillHoleFilter->Update();

  typedef itk::BinaryContourImageFilter<Image2DType, Image2DType> binaryContourImageFilterType;
  typename binaryContourImageFilterType::Pointer binaryContourFilter = binaryContourImageFilterType::New();
  binaryContourFilter->SetBackgroundValue ( 0 );
  binaryContourFilter->SetForegroundValue ( 1 );
  binaryContourFilter->SetInput ( binaryFillHoleFilter->GetOutput() );
  binaryContourFilter->Update();

  typename Image2DType::IndexType CurrentIndex;

  typename Image2DType::Pointer ContourImage = binaryContourFilter->GetOutput();
  itk::ImageRegionConstIterator<Image2DType> ContourImageIterator ( ContourImage, ContourImage->GetLargestPossibleRegion() );
  while ( !ContourImageIterator.IsAtEnd() )
    {
      if ( ContourImageIterator.Get() == 1 )
        {
          CurrentIndex = ContourImageIterator.GetIndex();
          newPoints->InsertNextPoint ( CurrentIndex[0], CurrentIndex[1], SliceNumber );
        }
      ++ContourImageIterator;
    }

  for ( int i = 0; i < newPoints->GetNumberOfPoints(); i++ )
    {
      vtkSmartPointer<vtkLine> line = vtkSmartPointer<vtkLine>::New();
      line->GetPointIds()->SetId ( 0, i );
      int j = i + 1;
      if ( i == newPoints->GetNumberOfPoints() - 1 )
        {
          j = 0;
        }
      line->GetPointIds()->SetId ( 1, j );
      newPolys->InsertNextCell ( line );
    }
}

//
// Contouring filter specialized for volumes and "short int" data values.
//
int vtkITKExternalContourFilter::RequestData (
  vtkInformation *vtkNotUsed ( request ),
  vtkInformationVector **inputVector,
  vtkInformationVector *outputVector )
{
  // get the info objects
  vtkInformation *inInfo = inputVector[0]->GetInformationObject ( 0 );
  vtkInformation *outInfo = outputVector->GetInformationObject ( 0 );

  // get the input and ouptut
  vtkImageData *input = vtkImageData::SafeDownCast ( inInfo->Get ( vtkDataObject::DATA_OBJECT() ) );
  vtkPolyData *output = vtkPolyData::SafeDownCast ( outInfo->Get ( vtkDataObject::DATA_OBJECT() ) );

  vtkPoints *newPts;
  vtkCellArray *newPolys;
  vtkPointData *pd;
  vtkDataArray *inScalars;
  int dims[3], extent[6];
  int estimatedSize;
  double spacing[3], origin[3];

  vtkDebugMacro ( << "Executing fill holes" );

  //
  // Initialize and check input
  //
  pd = input->GetPointData();
  if ( pd ==NULL )
    {
      vtkErrorMacro ( <<"PointData is NULL" );
      return 1;
    }
  inScalars = pd->GetScalars();
  if ( inScalars == NULL )
    {
      vtkErrorMacro ( <<"Scalars must be defined for fill holes" );
      return 1;
    }

  input->GetDimensions ( dims );
  input->GetOrigin ( origin );
  input->GetSpacing ( spacing );

  inInfo->Get ( vtkStreamingDemandDrivenPipeline::WHOLE_EXTENT(), extent );

  // estimate the number of points from the volume dimensions
  estimatedSize = ( int ) pow ( ( double ) ( dims[0] * dims[1] * dims[2] ), .75 );
  estimatedSize = estimatedSize / 1024 * 1024; //multiple of 1024
  if ( estimatedSize < 1024 )
    {
      estimatedSize = 1024;
    }
  vtkDebugMacro ( << "Estimated allocation size is " << estimatedSize );

  newPts = vtkPoints::New();
  newPts->Allocate ( estimatedSize,estimatedSize/2 );

  newPolys = vtkCellArray::New();
  newPolys->Allocate ( newPolys->EstimateSize ( estimatedSize,2 ) );

////////// These types are not defined in itk::NumericTraits ////////////
#ifdef vtkTemplateMacroCase_ui64
#undef vtkTemplateMacroCase_ui64
# define vtkTemplateMacroCase_ui64(typeN, type, call)
#endif
#ifdef vtkTemplateMacroCase_si64
#undef vtkTemplateMacroCase_si64
# define vtkTemplateMacroCase_si64(typeN, type, call)
#endif
#ifdef vtkTemplateMacroCase_ll
#undef vtkTemplateMacroCase_ll
# define vtkTemplateMacroCase_ll(typeN, type, call)
#endif
  if ( inScalars->GetNumberOfComponents() == 1 )
    {
      void* scalars = inScalars->GetVoidPointer ( 0 );
      switch ( inScalars->GetDataType() )
        {
          vtkTemplateMacro (
            vtkITKExtractExternalContours ( this, static_cast<VTK_TT*> ( scalars ),
                                            dims,extent,origin,spacing,
                                            newPts,newPolys, this->SliceNumber
                                          )
          );
        } //switch
    }
  else
    {
      vtkErrorMacro ( << "Can only trace scalar images." );
    }

  vtkDebugMacro ( <<"Created: "
                  << newPts->GetNumberOfPoints() << " points. " );
  //
  // Update ourselves.  Because we don't know up front how many edges
  // we've created, take care to reclaim memory.
  //
  output->SetPoints ( newPts );
  newPts->Delete();

  output->SetLines ( newPolys );
  newPolys->Delete();

  output->Squeeze();
  return 1;
}

int vtkITKExternalContourFilter::FillInputPortInformation ( int, vtkInformation *info )
{
  info->Set ( vtkAlgorithm::INPUT_REQUIRED_DATA_TYPE(), "vtkImageData" );
  return 1;
}

void vtkITKExternalContourFilter::PrintSelf ( ostream& os, vtkIndent indent )
{
  this->Superclass::PrintSelf ( os, indent );
  os << indent << "Slice number: [" << SliceNumber << std::endl;
}
