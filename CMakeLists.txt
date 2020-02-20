cmake_minimum_required(VERSION 3.5)

project(SlicerMorph)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://slicermorph.github.io/")
set(EXTENSION_CATEGORY "SlicerMorph")
set(EXTENSION_CONTRIBUTORS "Sara Rolfe (UW), Murat Maga (SCRI)")
set(EXTENSION_DESCRIPTION "This extension enables retrieval, visualization, measurement and annotation of high-resolution specimen data from volumetric scans (CTs and MRs) or 3D surface scans.")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/SlicerMorph/SlicerMorph/master/SlicerMorph_Color.png")
set(EXTENSION_SCREENSHOTURLS "https://na-mic.github.io/ProjectWeek/PW30_2019_GranCanaria/Projects/SlicerMorphGeometricMorphometricToolset/SM_screen.png https://na-mic.github.io/ProjectWeek/PW30_2019_GranCanaria/Projects/SlicerMorphGeometricMorphometricToolset/SM2.png")
set(EXTENSION_DEPENDS "SegmentEditorExtraEffects Sequences Sandbox SlicerIGT RawImageGuess") # Specified as a space separated string, a list or 'NA' if any

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(ConvertMorphologikaLandmarks)
add_subdirectory(GPA)
add_subdirectory(ImportSurfaceToSegment)
add_subdirectory(ReadLandmarkFile)
add_subdirectory(SkyscanReconImport)
add_subdirectory(MorphoSource)
add_subdirectory(SlicerMorphSampleData)
add_subdirectory(ResampleCurves)

## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
