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
set(EXTENSION_DEPENDS "SegmentEditorExtraEffects") # Specified as a space separated string, a list or 'NA' if any

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(ALPACA)
add_subdirectory(Animator)
add_subdirectory(CreateSemiLMPatches)
add_subdirectory(ExportMorphoJLandmarkFile)
add_subdirectory(FastModelAlign)
add_subdirectory(FormatMarkups)
add_subdirectory(GEVolImport)
add_subdirectory(GPA)
add_subdirectory(HiResScreenCapture)
add_subdirectory(IDAVLMConverter)
add_subdirectory(ImageStacks)
add_subdirectory(ImportFromURL)
add_subdirectory(ImportSurfaceToSegment)
add_subdirectory(MarkupsFcsv)
add_subdirectory(MarkupEditor)
add_subdirectory(MergeMarkups)
add_subdirectory(MorphologikaLMConverter)
add_subdirectory(MorphoSourceImport)
add_subdirectory(MorphPreferences)
add_subdirectory(OBJFile)
add_subdirectory(QuickAlign)
add_subdirectory(SkyscanReconImport)
add_subdirectory(SlicerMorphSampleData)
add_subdirectory(PlaceLandmarkGrid)
add_subdirectory(PlaceSemiLMPatches)
add_subdirectory(ProjectSemiLM)
add_subdirectory(PseudoLMGenerator)
add_subdirectory(SegmentEndocranium)
add_subdirectory(Tutorials)

## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
