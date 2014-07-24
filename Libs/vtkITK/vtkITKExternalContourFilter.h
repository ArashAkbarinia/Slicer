#ifndef __vtkITKExternalContourFilter_h
#define __vtkITKExternalContourFilter_h

#include "vtkITK.h"
#include "vtkPolyDataAlgorithm.h"
#include "vtkObjectFactory.h"

/// \brief return the external contour of a binary image.
class VTK_ITK_EXPORT vtkITKExternalContourFilter : public vtkPolyDataAlgorithm
{
public:
  static vtkITKExternalContourFilter *New();
  vtkTypeMacro ( vtkITKExternalContourFilter, vtkPolyDataAlgorithm );
  void PrintSelf ( ostream& os, vtkIndent indent );

  /// Methods to set/get SliceNumber.
  vtkSetMacro ( SliceNumber, int );
  vtkGetMacro ( SliceNumber, int );

protected:
  vtkITKExternalContourFilter();
  ~vtkITKExternalContourFilter();

  int SliceNumber;

  virtual int RequestData ( vtkInformation *, vtkInformationVector **, vtkInformationVector * );
  virtual int FillInputPortInformation ( int port, vtkInformation *info );

private:
  vtkITKExternalContourFilter ( const vtkITKExternalContourFilter& ); /// Not implemented.
  void operator= ( const vtkITKExternalContourFilter& ); /// Not implemented.
};

#endif
