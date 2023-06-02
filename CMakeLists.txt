cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(registration_test)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/chz31/registration_test")
set(EXTENSION_CATEGORY "Examples")
set(EXTENSION_CONTRIBUTORS "Chi Zhang (SCRI)")
set(EXTENSION_DESCRIPTION "Testing registration functions from ALPACA (ITK)")
set(EXTENSION_ICONURL "https://www.example.com/Slicer/Extensions/registration_test.png")
set(EXTENSION_SCREENSHOTURLS "https://www.example.com/Slicer/Extensions/registration_test/Screenshots/1.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(ALPACAModelRegistration)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
