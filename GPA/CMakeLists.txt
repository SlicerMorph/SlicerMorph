#-----------------------------------------------------------------------------
set(MODULE_NAME GPA)

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  Support/__init__.py
  Support/gpa_lib.py
  Support/vtk_lib.py
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  Resources/Icons/LayoutSlicerMorphView.png
  Resources/Icons/LayoutTableOnlyView.png
  Resources/Icons/LayoutPlotOnlyView.png
  Resources/UI/GPA_SetupAnalysis.ui
  Resources/UI/GPA_ExploreDataResults.ui
  Resources/UI/GPA_Interactive3D.ui
  Resources/UI/GPA_GeomorphLR.ui
)
#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  WITH_GENERIC_TESTS
  )
#-----------------------------------------------------------------------------
if(BUILD_TESTING)

  # Register the unittest subclass in the main script as a ctest.
  # Note that the test will also be available at runtime.
  slicer_add_python_unittest(SCRIPT ${MODULE_NAME}.py)
endif()
