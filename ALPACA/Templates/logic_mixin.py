"""Mixin class that provides all Templates-tab logic methods for ALPACALogic.

Imported by ALPACA.py and mixed into ALPACALogic via multiple inheritance:

    class ALPACALogic(_ALPACATemplatesLogic, ScriptedLoadableModuleLogic):
        ...

All methods were verbatim in ALPACALogic; this is a pure code move with no
behavioural changes.
"""

import os
import json
import logging
import numpy as np
import vtk
import slicer


class _ALPACATemplatesLogic:
    """Templates-tab computation methods, extracted from ALPACALogic."""

    ###Functions for select templates based on kmeans
    def downReference(self, referenceFilePath, spacingFactor):
        targetModelNode = slicer.util.loadModel(referenceFilePath)
        targetModelNode.GetDisplayNode().SetVisibility(False)
        templatePolydata = targetModelNode.GetPolyData()
        sparseTemplate = self.DownsampleTemplate(templatePolydata, spacingFactor)
        template_density = sparseTemplate.GetNumberOfPoints()
        return sparseTemplate, template_density, targetModelNode

    def matchingPCD(
        self,
        modelsDir,
        sparseTemplate,
        targetModelNode,
        pcdOutputDir,
        spacingFactor,
        useJSONFormat,
        parameterDictionary,
        usePoisson=False,
    ):
        if useJSONFormat:
            extensionLM = ".mrk.json"
        else:
            extensionLM = ".fcsv"
        template_density = sparseTemplate.GetNumberOfPoints()
        ID_list = list()

        # Cap RANSAC trials for templates point-cloud extraction. Specimens of
        # the same sample share morphology, so far fewer trials than the user's
        # full landmark-transfer maxRANSAC are needed for reliable alignment.
        # ITK divides the budget by thread count internally, so 100k -> ~12.5k
        # per thread on an 8-core box, which is plenty here. Full user
        # maxRANSAC is preserved for single/batch landmark transfer.
        _matchingParamDict = dict(parameterDictionary)
        _ransac_full = int(parameterDictionary.get("maxRANSAC", 1_000_000))
        _matchingParamDict["maxRANSAC"] = max(10_000, min(_ransac_full, 100_000))

        # Alignment and matching points
        referenceFileList = [
            f
            for f in os.listdir(modelsDir)
            if f.endswith((".ply", ".stl", ".obj", ".vtk", ".vtp"))
        ]
        import time as _time
        _stage_totals = {"load": 0.0, "subsample": 0.0, "estimate": 0.0,
                         "corresp": 0.0, "save": 0.0}
        _per_specimen = []
        for file in referenceFileList:
            _spec_t0 = _time.perf_counter()
            sourceFilePath = os.path.join(modelsDir, file)
            _t = _time.perf_counter()
            sourceModelNode = slicer.util.loadModel(sourceFilePath)
            _stage_totals["load"] += _time.perf_counter() - _t
            sourceModelNode.GetDisplayNode().SetVisibility(False)
            rootName = os.path.splitext(file)[0]
            scalingOption = True
            _t = _time.perf_counter()
            (
                sourcePoints,
                targetPoints,
                sourceFeatures,
                targetFeatures,
                voxelSize,
                scalingFactor,
            ) = self.runSubsample(
                sourceModelNode,
                targetModelNode,
                scalingOption,
                _matchingParamDict,
                usePoisson,
            )
            _stage_totals["subsample"] += _time.perf_counter() - _t
            _t = _time.perf_counter()
            ICPTransform_similarity, similarityFlag = self.estimateTransform(
                sourcePoints,
                targetPoints,
                sourceFeatures,
                targetFeatures,
                voxelSize,
                scalingOption,
                _matchingParamDict,
            )
            _stage_totals["estimate"] += _time.perf_counter() - _t

            _t = _time.perf_counter()
            vtkSimilarityTransform = self.itkToVTKTransform(
                ICPTransform_similarity, similarityFlag
            )
            ICPTransformNode = self.convertMatrixToTransformNode(
                vtkSimilarityTransform, "Rigid Transformation Matrix"
            )

            sourceModelNode.SetAndObserveTransformNodeID(ICPTransformNode.GetID())
            slicer.vtkSlicerTransformLogic().hardenTransform(sourceModelNode)

            alignedSubjectPolydata = sourceModelNode.GetPolyData()
            ID, correspondingSubjectPoints = self.GetCorrespondingPoints(
                sparseTemplate, alignedSubjectPolydata
            )
            ID_list.append(ID)
            subjectFiducial = slicer.vtkMRMLMarkupsFiducialNode()
            for i in range(correspondingSubjectPoints.GetNumberOfPoints()):
                subjectFiducial.AddControlPoint(correspondingSubjectPoints.GetPoint(i))
            slicer.mrmlScene.AddNode(subjectFiducial)
            subjectFiducial.SetFixedNumberOfControlPoints(True)

            ICPTransformNode.Inverse()
            subjectFiducial.SetAndObserveTransformNodeID(ICPTransformNode.GetID())
            slicer.vtkSlicerTransformLogic().hardenTransform(subjectFiducial)

            sourceArray = slicer.util.arrayFromMarkupsControlPoints(subjectFiducial).copy()
            for i in range(subjectFiducial.GetNumberOfControlPoints()):
                subjectFiducial.SetNthControlPointLocked(i, 1)

            sourceArray = sourceArray * (1/scalingFactor)

            slicer.util.updateMarkupsControlPointsFromArray(subjectFiducial, sourceArray)

            _stage_totals["corresp"] += _time.perf_counter() - _t
            _t = _time.perf_counter()
            slicer.util.saveNode(
                subjectFiducial, os.path.join(pcdOutputDir, f"{rootName}" + extensionLM)
            )
            _stage_totals["save"] += _time.perf_counter() - _t
            slicer.mrmlScene.RemoveNode(sourceModelNode)
            slicer.mrmlScene.RemoveNode(ICPTransformNode)
            slicer.mrmlScene.RemoveNode(subjectFiducial)
            _per_specimen.append((file, _time.perf_counter() - _spec_t0))
        # Remove template node
        slicer.mrmlScene.RemoveNode(targetModelNode)
        # Per-specimen + stage timing summary (consensus / templates diagnostics)
        try:
            import logging as _lg
            _total = sum(t for _, t in _per_specimen)
            _msg = "[matchingPCD] %d specimens in %.1fs" % (len(_per_specimen), _total)
            print(_msg); _lg.info(_msg)
            for fn, dt in _per_specimen:
                _msg = "  %-32s  %6.2fs" % (fn, dt)
                print(_msg); _lg.info(_msg)
            _msg = "[matchingPCD] stage totals:"
            print(_msg); _lg.info(_msg)
            for k, v in _stage_totals.items():
                pct = 100.0 * v / _total if _total > 0 else 0.0
                _msg = "  %-12s %7.2fs  (%.1f%%)" % (k, v, pct)
                print(_msg); _lg.info(_msg)
        except Exception:
            pass
        # Printing results of points matching
        matchedPoints = [len(set(x)) for x in ID_list]
        indices = [i for i, x in enumerate(matchedPoints) if x < template_density]
        files = [os.path.splitext(file)[0] for file in referenceFileList]
        return template_density, matchedPoints, indices, files

    @staticmethod
    def _loadGPAModule():
        """Return the GPA Python module with class symbols populated."""
        import importlib, importlib.util, sys, traceback
        try:
            mod_path = slicer.modules.gpa.path
        except Exception:
            mod_path = None
        if not (mod_path and os.path.isfile(mod_path)):
            raise RuntimeError(
                "Cannot locate GPA module file. Is the SlicerMorph GPA module installed?"
            )
        mod_dir = os.path.dirname(mod_path)
        added = False
        if mod_dir not in sys.path:
            sys.path.insert(0, mod_dir)
            added = True
        try:
            # Drop any half-loaded GPA from sys.modules so the fresh exec
            # below does not get short-circuited.
            sys.modules.pop("GPA", None)
            spec = importlib.util.spec_from_file_location(
                "GPA", mod_path,
                submodule_search_locations=[mod_dir],
            )
            _GPA = importlib.util.module_from_spec(spec)
            sys.modules["GPA"] = _GPA
            try:
                spec.loader.exec_module(_GPA)
            except Exception:
                # Surface the underlying ImportError / NameError so we know why
                # GPALogic never got defined.
                logging.error("ALPACA: failed to execute GPA.py:\n" + traceback.format_exc())
                raise
        finally:
            if added:
                try:
                    sys.path.remove(mod_dir)
                except ValueError:
                    pass
        if not hasattr(_GPA, "GPALogic"):
            raise RuntimeError(
                f"GPA module loaded from {mod_path} but does not expose GPALogic. "
                f"Module attributes: {sorted(a for a in dir(_GPA) if not a.startswith('_'))}"
            )
        return _GPA

    # inputFilePaths: file paths of pcd files
    def pcdGPA(self, inputFilePaths):
        basename, extension = os.path.splitext(inputFilePaths[0])
        # Load GPA's logic classes directly from its source file, bypassing
        # Slicer's scripted-module activation (which can pop modal dialogs).
        _GPA = self._loadGPAModule()

        GPAlogic = _GPA.GPALogic()
        LM = _GPA.LMData()
        LMExclusionList = []
        LM.lmOrig, landmarkTypeArray = GPAlogic.loadLandmarks(
            inputFilePaths, LMExclusionList, extension
        )
        shape = LM.lmOrig.shape
        scalingOption = True
        try:
            LM.doGpa(scalingOption)
        except ValueError:
            print(
                "Point clouds may not have been generated correctly. Please re-run the point cloud generation step."
            )
        LM.calcEigen()
        import Support.gpa_lib as gpa_lib

        twoDcoors = gpa_lib.makeTwoDim(LM.lmOrig)
        scores = np.dot(np.transpose(twoDcoors), LM.vec)
        scores = np.real(scores)
        size = scores.shape[0] - 1
        scores = scores[:, 0:size]
        return scores, LM

    def templatesSelection(
        self,
        modelsDir,
        scores,
        inputFilePaths,
        templatesOutputDir,
        templatesNumber,
        iterations,
    ):
        """Run k-means on PC scores and return the chosen template specimen names.

        modelsDir and templatesOutputDir are accepted for signature compatibility
        but no longer used; only the names of selected templates are reported.
        """
        templatesNumber = int(templatesNumber)
        iterations = int(iterations)
        files = [os.path.basename(path).split(".")[0] for path in inputFilePaths]
        from scipy.cluster.vq import vq, kmeans

        # np.random.seed(1000) #Set numpy random seed to ensure consistent Kmeans result
        centers, distortion = kmeans(scores, templatesNumber, thresh=0, iter=iterations)
        # clusterID returns the cluster allocation of each specimen
        clusterID, min_dists = vq(scores, centers)
        templatesIndices = []
        for i in range(templatesNumber):
            indices_i = [index for index, x in enumerate(clusterID) if x == i]
            dists = [min_dists[index] for index in indices_i]
            index = dists.index(min(dists))
            templateIndex = indices_i[index]
            templatesIndices.append(templateIndex)
        templates = [files[x] for x in templatesIndices]
        return templates, clusterID, templatesIndices

    # ------------------------------------------------------------------
    # Consensus atlas construction (bias-free template generation)
    # ------------------------------------------------------------------
    def buildConsensusAtlas(
        self,
        modelsDir,
        outputDir,
        spacingFactor,
        parameterDictionary,
        iterations=3,
        useJSONFormat=True,
        useScaling=True,
        userReferencePath=None,
        smoothingIterations=20,
        outlierRejectFactor=3.0,
        progressCallback=None,
    ):
        """Build a bias-free consensus atlas mesh from a folder of models.

        Strategy: bootstrap correspondences from an arbitrary specimen, compute
        the Procrustes mean shape, TPS-warp the bootstrap mesh to that mean,
        then iterate using the synthesized atlas as the new reference. After a
        few iterations the atlas converges to a consensus that no individual
        specimen biases.

        Parameters
        ----------
        modelsDir : str
            Folder containing input meshes (.ply/.stl/.obj/.vtk/.vtp).
        outputDir : str
            Folder to write per-iteration atlases and the final consensus.
        spacingFactor : float
            Spacing factor passed to DownsampleTemplate (same meaning as in
            the existing Templates tab).
        parameterDictionary : dict
            FPFH/RANSAC/ICP/CPD parameters (already populated from the
            Advanced Settings tab).
        iterations : int
            Number of refinement iterations. 2-3 usually suffices.
        useJSONFormat : bool
            Output format for intermediate per-specimen point clouds.
        useScaling : bool
            Whether to allow scaling during Procrustes alignment of
            per-specimen point clouds.
        userReferencePath : str or None
            Optional path to a user-selected reference mesh used to bootstrap
            iteration 0. If None, the first model in ``modelsDir`` is used.
        smoothingIterations : int
            Taubin (volume-preserving) smoothing iterations applied to the
            final consensus atlas to remove high-frequency pitting from
            outlier closest-point hits. 0 disables smoothing.
        outlierRejectFactor : float
            During dense averaging, per-specimen closest-point contributions
            whose distance to the atlas vertex exceeds this multiple of the
            specimen's median closest-point distance are dropped. Suppresses
            artifacts from local TPS folding. Set to 0 to disable.
        progressCallback : callable(str) or None
            Optional callback invoked with status messages.

        Returns
        -------
        str
            Path to the final consensus atlas mesh (PLY).
        """
        import vtk
        import shutil
        import tempfile
        import logging
        import time

        def _log(msg):
            logging.info(msg)
            if progressCallback is not None:
                progressCallback(msg)

        os.makedirs(outputDir, exist_ok=True)

        modelFiles = sorted(
            f for f in os.listdir(modelsDir)
            if f.endswith((".ply", ".stl", ".obj", ".vtk", ".vtp"))
        )
        if len(modelFiles) < 3:
            raise ValueError("buildConsensusAtlas requires at least 3 input models")

        ext = ".mrk.json" if useJSONFormat else ".fcsv"
        workDir = tempfile.mkdtemp(prefix="alpaca_consensus_")

        # Bootstrap reference: user-selected if provided, else arbitrary first
        # model. The choice does NOT bias the final mean — it only seeds the
        # initial correspondences, which subsequent iterations refine using
        # the synthesized atlas.
        if userReferencePath and os.path.isfile(userReferencePath):
            currentAtlasPath = userReferencePath
            _log(f"Bootstrap reference (user-selected): "
                 f"{os.path.basename(userReferencePath)}")
        else:
            currentAtlasPath = os.path.join(modelsDir, modelFiles[0])
            _log(f"Bootstrap reference (default, first model): {modelFiles[0]}")

        # Consensus-specific RANSAC caps (cross-platform).
        # Specimens of the same sample are morphologically similar; far fewer
        # RANSAC trials reliably find the correct alignment than for arbitrary
        # landmark transfer. Cap iteration 0 at 100k and subsequent iterations
        # at 10k (the atlas is already near the mean so FPFH correspondences
        # are tight from the start and RANSAC converges on the first attempt).
        from vtk.util.numpy_support import vtk_to_numpy as _v2n_build
        _ransac_full = int(parameterDictionary.get("maxRANSAC", 1_000_000))
        _RANSAC_ITER0 = max(10_000, min(_ransac_full, 100_000))
        # Use the same cap for all iterations: the consensus atlas is a smooth
        # population average whose FPFH features are blurrier than any individual
        # specimen, so ITK RANSAC needs the same number of trials to resolve the
        # correct global orientation. 10k was too low and caused 180° flips in
        # iteration 2+ because ITK divides by thread count internally.
        _RANSAC_ITERN = _RANSAC_ITER0

        prevMeanVerts = None
        for it in range(iterations):
            _log(f"--- Consensus iteration {it + 1}/{iterations} ---")
            iter_t0 = time.perf_counter()
            stage_times = {}

            # 1) Load atlas mesh + sparse template control points (atlas frame).
            t0 = time.perf_counter()
            atlasNode = slicer.util.loadModel(currentAtlasPath)
            atlasNode.GetDisplayNode().SetVisibility(False)
            atlasPolyData = vtk.vtkPolyData()
            atlasPolyData.DeepCopy(atlasNode.GetPolyData())
            sparseTemplate = self.DownsampleTemplate(atlasPolyData, spacingFactor)
            density = sparseTemplate.GetNumberOfPoints()
            n_atlas_verts = atlasPolyData.GetNumberOfPoints()
            atlasCorresp = _v2n_build(sparseTemplate.GetPoints().GetData()).copy()
            stage_times["downReference"] = time.perf_counter() - t0
            _log(f"  Sparse control points: {density};  atlas vertices: {n_atlas_verts}")

            # 2) For each specimen: rigid+ICP align to atlas, sparse correspondence,
            #    TPS-warp specimen mesh to atlas frame, nearest-project every
            #    atlas vertex onto the warped specimen surface. Accumulate mean.
            t0 = time.perf_counter()
            sumVerts = np.zeros((n_atlas_verts, 3), dtype=np.float64)
            countVerts = np.zeros(n_atlas_verts, dtype=np.int64)
            # Build a consensus-specific parameter dict with a reduced RANSAC
            # cap. Full user maxRANSAC is preserved for landmark transfer.
            _ransac_cap = _RANSAC_ITER0 if it == 0 else _RANSAC_ITERN
            _consensusParamDict = dict(parameterDictionary)
            _consensusParamDict["maxRANSAC"] = _ransac_cap
            _log(f"  RANSAC cap this iteration: {_ransac_cap:,}")
            n_used, closest_stack = self._denseConsensusAccumulate(
                modelsDir=modelsDir,
                atlasPolyData=atlasPolyData,
                atlasNode=atlasNode,
                sparseTemplate=sparseTemplate,
                atlasCorresp=atlasCorresp,
                parameterDictionary=_consensusParamDict,
                sumVerts=sumVerts,
                countVerts=countVerts,
                outlierRejectFactor=outlierRejectFactor,
                progressCallback=progressCallback,
            )
            stage_times["denseAccumulate"] = time.perf_counter() - t0
            _log(f"  Aggregated dense correspondences from {n_used} specimens")

            # 3) Compute per-vertex mean via partial Procrustes (rotation +
            #    translation only, no scale).  This replaces the star-shaped
            #    simple average with a GPA that simultaneously aligns all M
            #    per-specimen correspondence arrays to their common mean,
            #    removing residual pose inconsistency from independent ICP
            #    solutions and reducing the anchor bias toward the current
            #    atlas shape.  The result is re-anchored to the initial
            #    simple-average frame so the atlas stays co-registered across
            #    iterations.  Vertices with zero hits fall back to their
            #    current atlas position.
            t0 = time.perf_counter()
            atlasVertsArray = _v2n_build(atlasPolyData.GetPoints().GetData()).copy()
            meanVerts = atlasVertsArray.copy()
            if len(closest_stack) >= 3:
                stack_arr = np.array(closest_stack, dtype=np.float64)  # (M, N, 3)
                mask = countVerts > 0
                meanVerts[mask] = self._partial_procrustes_mean(
                    stack_arr[:, mask, :]
                )
            else:
                # Fewer than 3 specimens — fall back to simple average.
                mask = countVerts > 0
                meanVerts[mask] = sumVerts[mask] / countVerts[mask, None]
            stage_times["meanVerts"] = time.perf_counter() - t0
            _log(f"  Partial Procrustes mean computed ({len(closest_stack)} specimens)")

            # 4) Write atlas with reference topology + new mean vertex positions.
            iterAtlasPath = os.path.join(outputDir, f"consensus_atlas_iter{it:02d}.ply")
            t0 = time.perf_counter()
            self._writeMeshWithNewVertices(atlasPolyData, meanVerts, iterAtlasPath)
            stage_times["writeAtlas"] = time.perf_counter() - t0
            _log(f"  Wrote {iterAtlasPath}")

            # Convergence diagnostic vs previous iteration's atlas vertices.
            if it > 0 and prevMeanVerts is not None and prevMeanVerts.shape == meanVerts.shape:
                rms = float(np.sqrt(np.mean(np.sum((meanVerts - prevMeanVerts) ** 2, axis=1))))
                _log(f"  [convergence] RMS vertex displacement vs iter {it}: {rms:.5f}")
            prevMeanVerts = meanVerts

            # Clean up the loaded atlas node.
            try:
                slicer.mrmlScene.RemoveNode(atlasNode)
            except Exception:
                pass

            iter_total = time.perf_counter() - iter_t0
            _log(f"  [timing] iter {it + 1} total: {iter_total:.1f}s")
            for stage, t in stage_times.items():
                pct = 100.0 * t / iter_total if iter_total > 0 else 0.0
                _log(f"    {stage:18s} {t:7.2f}s  ({pct:4.1f}%)")

            currentAtlasPath = iterAtlasPath

        # Copy final iteration as the canonical output.
        finalPath = os.path.join(outputDir, "consensus_atlas.ply")
        import shutil
        shutil.copyfile(currentAtlasPath, finalPath)
        _log(f"Consensus atlas: {finalPath}")

        # Post-process: Taubin smoothing to remove residual high-frequency
        # pitting from outlier closest-point hits (volume preserving, keeps
        # topology unchanged).
        if smoothingIterations and smoothingIterations > 0:
            t0 = time.perf_counter()
            self._taubinSmoothMeshInPlace(finalPath, int(smoothingIterations))
            _log(
                f"  Post-smoothed atlas (Taubin, {int(smoothingIterations)} iters)"
                f" in {time.perf_counter() - t0:.2f}s"
            )

        # Clean up temporary correspondence files.
        try:
            import shutil as _shutil
            _shutil.rmtree(workDir)
        except Exception:
            pass

        return finalPath

    @staticmethod
    def _loadPointCloudsAsArray(pcdPaths):
        """Load a list of .mrk.json or .fcsv point cloud files as (N,K,3) array."""
        all_pts = []
        for path in pcdPaths:
            if path.endswith(".fcsv"):
                pts = []
                with open(path) as f:
                    for line in f:
                        if line.startswith("#") or not line.strip():
                            continue
                        parts = line.strip().split(",")
                        if len(parts) >= 4:
                            pts.append([float(parts[1]), float(parts[2]), float(parts[3])])
                all_pts.append(np.array(pts, dtype=float))
            else:  # .mrk.json
                with open(path) as f:
                    d = json.load(f)
                cps = d["markups"][0]["controlPoints"]
                all_pts.append(
                    np.array([cp["position"] for cp in cps], dtype=float)
                )
        # All configurations must share point count.
        K = all_pts[0].shape[0]
        for i, a in enumerate(all_pts):
            if a.shape[0] != K:
                raise ValueError(
                    f"Inconsistent point count in {pcdPaths[i]}: "
                    f"{a.shape[0]} (expected {K})"
                )
        return np.stack(all_pts, axis=0)

    @staticmethod
    def _procrustesMean(configs, useScaling=True, maxIter=10, tol=1e-6):
        """Generalized Procrustes Analysis.

        Parameters
        ----------
        configs : ndarray (N, K, 3)
            Stacked configurations.
        useScaling : bool
            If True, normalize each config to unit centroid size during alignment.
        maxIter : int
            Maximum GPA iterations.
        tol : float
            Convergence tolerance on mean-shape change.

        Returns
        -------
        meanShape : ndarray (K, 3)
            Procrustes mean configuration.
        aligned : ndarray (N, K, 3)
            All configurations aligned to the mean.
        """
        configs = np.asarray(configs, dtype=float)
        N, K, _ = configs.shape

        # Center each configuration on its centroid.
        centered = configs - configs.mean(axis=1, keepdims=True)

        # Optional unit centroid size normalization.
        if useScaling:
            sizes = np.sqrt((centered ** 2).sum(axis=(1, 2), keepdims=True))
            sizes[sizes == 0] = 1.0
            centered = centered / sizes

        aligned = centered.copy()
        meanShape = aligned[0].copy()

        for _ in range(maxIter):
            new_aligned = np.empty_like(aligned)
            for i in range(N):
                # Kabsch alignment of aligned[i] onto meanShape.
                A = aligned[i]
                B = meanShape
                H = A.T @ B
                U, S, Vt = np.linalg.svd(H)
                d = np.sign(np.linalg.det(Vt.T @ U.T))
                D = np.eye(3)
                D[2, 2] = d
                R = Vt.T @ D @ U.T
                new_aligned[i] = A @ R.T
            new_mean = new_aligned.mean(axis=0)
            # Re-normalize mean to unit centroid size for stability.
            if useScaling:
                ms = np.sqrt((new_mean ** 2).sum())
                if ms > 0:
                    new_mean = new_mean / ms
            change = np.linalg.norm(new_mean - meanShape)
            aligned = new_aligned
            meanShape = new_mean
            if change < tol:
                break

        return meanShape, aligned

    @staticmethod
    def _similarityAlign(source, target, useScaling=True):
        """Align `source` (K,3) to `target` (K,3) via similarity transform
        (translation + rotation + optional uniform scale). Returns transformed
        source coordinates (K,3)."""
        source = np.asarray(source, dtype=float)
        target = np.asarray(target, dtype=float)
        sc = source.mean(axis=0)
        tc = target.mean(axis=0)
        S = source - sc
        T = target - tc
        # Optimal rotation via SVD (Kabsch).
        H = S.T @ T
        U, _, Vt = np.linalg.svd(H)
        d = np.sign(np.linalg.det(Vt.T @ U.T))
        D = np.eye(3)
        D[2, 2] = d
        R = Vt.T @ D @ U.T
        # Optimal scale.
        if useScaling:
            num = np.sum(T * (S @ R.T))
            den = np.sum(S * S)
            scale = num / den if den > 0 else 1.0
        else:
            scale = 1.0
        return scale * (S @ R.T) + tc

    @staticmethod
    def _partial_procrustes_mean(stack, max_iter=20, tol=1e-6):
        """Partial Procrustes mean of M correspondence sets (rotation + translation only).

        Each of the M per-specimen arrays is optimally aligned to the evolving
        group mean using a rigid (no-scale) transform, preserving biological
        scale.  After GPA convergence the result is re-anchored to the initial
        simple-average frame via a second rigid transform, so the atlas remains
        co-registered with the previous iteration's output.

        Parameters
        ----------
        stack : (M, N, 3) ndarray
            M per-specimen closest-point arrays, each of length N (= number of
            atlas vertices), already expressed in atlas space.
        max_iter : int
            Maximum GPA iterations (typically converges in < 10).
        tol : float
            Convergence threshold: RMS change in the mean across iterations (mm).

        Returns
        -------
        mean : (N, 3) ndarray
            Partial Procrustes mean, re-anchored to the initial frame.
        """
        M, N, _ = stack.shape

        # Initialise with simple average (already in atlas frame) and remember
        # it for re-anchoring after GPA.
        mean   = stack.mean(axis=0)   # (N, 3)
        anchor = mean.copy()

        for _ in range(max_iter):
            aligned = np.empty_like(stack)
            for j in range(M):
                cj  = stack[j].mean(axis=0)
                cm  = mean.mean(axis=0)
                Xj  = stack[j] - cj          # centred source
                Xm  = mean     - cm          # centred target
                H   = Xj.T @ Xm             # (3, 3) cross-covariance
                U, _, Vt = np.linalg.svd(H)
                R   = Vt.T @ U.T
                if np.linalg.det(R) < 0:    # avoid improper rotation
                    Vt[-1] *= -1
                    R = Vt.T @ U.T
                t   = cm - R @ cj
                aligned[j] = (R @ stack[j].T).T + t

            new_mean = aligned.mean(axis=0)
            change   = float(np.sqrt(((new_mean - mean) ** 2).sum(axis=1).mean()))
            mean     = new_mean
            if change < tol:
                break

        # Re-anchor: rigid transform (no scale) that maps the GPA mean back to
        # the initial simple-average frame, keeping the atlas co-registered with
        # the previous iteration.
        ca  = anchor.mean(axis=0)
        cm  = mean.mean(axis=0)
        H   = (mean - cm).T @ (anchor - ca)
        U, _, Vt = np.linalg.svd(H)
        R   = Vt.T @ U.T
        if np.linalg.det(R) < 0:
            Vt[-1] *= -1
            R = Vt.T @ U.T
        t   = ca - R @ cm
        mean = (R @ mean.T).T + t

        return mean

    def _denseConsensusAccumulate(
        self,
        modelsDir,
        atlasPolyData,
        atlasNode,
        sparseTemplate,
        atlasCorresp,
        parameterDictionary,
        sumVerts,
        countVerts,
        outlierRejectFactor=3.0,
        progressCallback=None,
    ):
        """For each input specimen: rigid+ICP align to atlas, get sparse
        correspondences, TPS-warp the full specimen mesh into atlas frame
        using sparse correspondences as control points, then for every atlas
        vertex find nearest point on the warped specimen surface. Accumulate
        per-vertex sums into ``sumVerts`` and counts into ``countVerts``.

        Returns
        -------
        n_used : int
            Number of specimens successfully processed.
        closest_stack : list of (n_atlas_verts, 3) ndarray
            Per-specimen closest-point arrays in atlas space, one entry per
            successfully processed specimen.  Vertices whose closest-point
            distance exceeded the outlier threshold are filled with the atlas
            vertex's own position so they contribute zero displacement to any
            downstream mean.
        """
        import vtk
        import logging
        from vtk.util.numpy_support import vtk_to_numpy as _v2n, numpy_to_vtk as _n2v

        n_atlas_verts = atlasPolyData.GetNumberOfPoints()
        atlasVertsArray = _v2n(atlasPolyData.GetPoints().GetData()).copy()

        # Source landmarks for TPS (atlas-frame template control points).
        atlasLM_vtk = vtk.vtkPoints()
        atlasLM_vtk.SetData(_n2v(np.asarray(atlasCorresp, dtype=np.float64), deep=True))

        modelFiles = sorted(
            f for f in os.listdir(modelsDir)
            if f.endswith((".ply", ".stl", ".obj", ".vtk", ".vtp"))
        )

        n_used = 0
        closest_stack = []
        for fname in modelFiles:
            specimenPath = os.path.join(modelsDir, fname)
            try:
                sourceModelNode = slicer.util.loadModel(specimenPath)
                sourceModelNode.GetDisplayNode().SetVisibility(False)

                # Rigid + ICP align specimen to atlas (atlas == targetNode).
                (
                    sourcePoints,
                    targetPoints,
                    sourceFeatures,
                    targetFeatures,
                    voxelSize,
                    scalingFactor,
                ) = self.runSubsample(
                    sourceModelNode,
                    atlasNode,
                    True,                     # scaling on
                    parameterDictionary,
                    False,                    # poisson off
                )
                ICPTransform_similarity, similarityFlag = self.estimateTransform(
                    sourcePoints, targetPoints, sourceFeatures, targetFeatures,
                    voxelSize, True, parameterDictionary,
                )
                vtkSimTransform = self.itkToVTKTransform(
                    ICPTransform_similarity, similarityFlag
                )
                ICPTransformNode = self.convertMatrixToTransformNode(
                    vtkSimTransform, "RigidXform"
                )
                sourceModelNode.SetAndObserveTransformNodeID(ICPTransformNode.GetID())
                slicer.vtkSlicerTransformLogic().hardenTransform(sourceModelNode)
                alignedSpecimen = sourceModelNode.GetPolyData()

                # Sparse atlas-frame correspondences on this specimen.
                _ID, correspPts_vtk = self.GetCorrespondingPoints(
                    sparseTemplate, alignedSpecimen
                )

                # TPS warp aligned specimen so that its sparse correspondences
                # land exactly at atlas template control points. This pulls the
                # specimen geometry into tight alignment with the atlas frame
                # at high frequency too, not just rigidly.
                tps = vtk.vtkThinPlateSplineTransform()
                tps.SetSourceLandmarks(correspPts_vtk)  # specimen-frame
                tps.SetTargetLandmarks(atlasLM_vtk)     # atlas-frame
                tps.SetBasisToR()
                tps.Update()

                tf = vtk.vtkTransformPolyDataFilter()
                tf.SetInputData(alignedSpecimen)
                tf.SetTransform(tps)
                tf.Update()
                warpedSpecimen = tf.GetOutput()

                # Batch closest-point lookup via scipy cKDTree on warped
                # specimen vertices. Vertex-to-vertex matching is consistent
                # with GetCorrespondingPoints (vtkPointLocator). Cross-platform;
                # workers=-1 uses C-level threading (safe on Win/macOS/Linux).
                from scipy.spatial import cKDTree as _cKDTree
                warpedPts = _v2n(warpedSpecimen.GetPoints().GetData())
                _tree = _cKDTree(warpedPts)
                specimenDist, _idx = _tree.query(atlasVertsArray, workers=-1)
                specimenClosest = warpedPts[_idx].copy()
                specimenDist2 = specimenDist ** 2

                if outlierRejectFactor and outlierRejectFactor > 0:
                    medianD = float(np.sqrt(np.median(specimenDist2)))
                    threshold = (outlierRejectFactor * medianD) ** 2
                    keep = specimenDist2 <= threshold
                    n_rejected = int((~keep).sum())
                else:
                    keep = np.ones(n_atlas_verts, dtype=bool)
                    n_rejected = 0

                sumVerts[keep] += specimenClosest[keep]
                countVerts[keep] += 1

                # Build per-specimen array for partial Procrustes averaging.
                # Rejected vertices are filled with the atlas vertex's own
                # position so they contribute zero displacement to the mean.
                specimenEntry = specimenClosest.copy()
                if not keep.all():
                    specimenEntry[~keep] = atlasVertsArray[~keep]
                closest_stack.append(specimenEntry)

                n_used += 1
                if n_rejected and progressCallback is not None:
                    progressCallback(
                        f"    rejected {n_rejected}/{n_atlas_verts} outlier verts"
                    )
                if progressCallback is not None:
                    progressCallback(f"  + {fname}")
                slicer.mrmlScene.RemoveNode(sourceModelNode)
                slicer.mrmlScene.RemoveNode(ICPTransformNode)
                # Yield to Qt so the UI stays responsive on long datasets.
                try:
                    slicer.app.processEvents()
                except Exception:
                    pass
            except Exception as e:
                logging.warning(f"Specimen {fname} skipped: {e}")
                if progressCallback is not None:
                    progressCallback(f"  ! skipped {fname}: {e}")
                try:
                    slicer.mrmlScene.RemoveNode(sourceModelNode)
                except Exception:
                    pass

        return n_used, closest_stack

    @staticmethod
    def _writeMeshWithNewVertices(referencePolyData, newVerts, outputPath):
        """Write a PLY whose topology is taken from ``referencePolyData`` and
        whose vertex positions are replaced by ``newVerts`` (N,3)."""
        import vtk

        out = vtk.vtkPolyData()
        out.DeepCopy(referencePolyData)
        from vtk.util.numpy_support import numpy_to_vtk as _n2v
        pts = vtk.vtkPoints()
        pts.SetData(_n2v(np.asarray(newVerts, dtype=np.float64), deep=True))
        out.SetPoints(pts)

        writer = vtk.vtkPLYWriter()
        writer.SetFileName(outputPath)
        writer.SetInputData(out)
        writer.SetFileTypeToBinary()
        writer.Write()

    @staticmethod
    def _taubinSmoothMeshInPlace(meshPath, iterations, passBand=0.1):
        """Apply Taubin (volume-preserving) smoothing to the mesh at
        ``meshPath`` and overwrite it. Uses ``vtkWindowedSincPolyDataFilter``
        which avoids the shrinkage of plain Laplacian smoothing.
        """
        import vtk

        reader = vtk.vtkPLYReader()
        reader.SetFileName(meshPath)
        reader.Update()

        smoother = vtk.vtkWindowedSincPolyDataFilter()
        smoother.SetInputData(reader.GetOutput())
        smoother.SetNumberOfIterations(int(iterations))
        smoother.SetPassBand(passBand)
        smoother.BoundarySmoothingOff()
        smoother.FeatureEdgeSmoothingOff()
        smoother.NonManifoldSmoothingOn()
        smoother.NormalizeCoordinatesOn()
        smoother.Update()

        writer = vtk.vtkPLYWriter()
        writer.SetFileName(meshPath)
        writer.SetInputData(smoother.GetOutput())
        writer.SetFileTypeToBinary()
        writer.Write()

    @staticmethod
    def _tpsWarpMesh(meshPath, sourcePoints, targetPoints, outputPath):
        """TPS-warp a mesh using paired (source -> target) landmarks.

        Reads `meshPath`, applies a vtkThinPlateSplineTransform whose source
        landmarks are `sourcePoints` (K,3) and target landmarks are
        `targetPoints` (K,3), and writes the warped mesh to `outputPath`.
        """
        import vtk

        ext = os.path.splitext(meshPath)[1].lower()
        if ext == ".ply":
            reader = vtk.vtkPLYReader()
        elif ext in (".vtk", ".vtp"):
            reader = vtk.vtkPolyDataReader()
        elif ext == ".obj":
            reader = vtk.vtkOBJReader()
        elif ext == ".stl":
            reader = vtk.vtkSTLReader()
        else:
            raise ValueError(f"Unsupported mesh format: {ext}")
        reader.SetFileName(meshPath)
        reader.Update()
        polydata = reader.GetOutput()

        srcPts = vtk.vtkPoints()
        for p in sourcePoints:
            srcPts.InsertNextPoint(float(p[0]), float(p[1]), float(p[2]))
        tgtPts = vtk.vtkPoints()
        for p in targetPoints:
            tgtPts.InsertNextPoint(float(p[0]), float(p[1]), float(p[2]))

        tps = vtk.vtkThinPlateSplineTransform()
        tps.SetSourceLandmarks(srcPts)
        tps.SetTargetLandmarks(tgtPts)
        tps.SetBasisToR()  # 3D TPS basis
        tps.Update()

        tf = vtk.vtkTransformPolyDataFilter()
        tf.SetInputData(polydata)
        tf.SetTransform(tps)
        tf.Update()

        writer = vtk.vtkPLYWriter()
        writer.SetFileName(outputPath)
        writer.SetInputData(tf.GetOutput())
        writer.SetFileTypeToBinary()
        writer.Write()

    def DownsampleTemplate(self, templatePolyData, spacingPercentage):
        import vtk

        filter = vtk.vtkCleanPolyData()
        filter.SetToleranceIsAbsolute(False)
        filter.SetTolerance(spacingPercentage)
        filter.SetInputData(templatePolyData)
        filter.Update()
        return filter.GetOutput()

    def GetCorrespondingPoints(self, templatePolyData, subjectPolydata):
        import vtk
        import numpy as np
        from vtk.util.numpy_support import vtk_to_numpy as _v2n, numpy_to_vtk as _n2v
        from scipy.spatial import cKDTree

        print(templatePolyData.GetNumberOfPoints())
        print(subjectPolydata.GetNumberOfPoints())

        templatePts = _v2n(templatePolyData.GetPoints().GetData())
        subjectPts  = _v2n(subjectPolydata.GetPoints().GetData())

        tree = cKDTree(subjectPts)
        _, idx = tree.query(templatePts, workers=-1)

        correspondingPtsArr = subjectPts[idx]
        correspondingPoints = vtk.vtkPoints()
        correspondingPoints.SetData(_n2v(np.ascontiguousarray(correspondingPtsArr, dtype=np.float64), deep=True))

        ID = idx.tolist()
        return ID, correspondingPoints

    def makeScatterPlotWithFactors(
        self, data, files, factors, title, xAxis, yAxis, pcNumber, templatesIndices
    ):
        """Plot all specimens as gray squares (one shared series) and overlay
        the per-group templates as colored diamonds, one series per group."""
        numPoints = len(data)
        uniqueFactors = sorted(set(factors))

        chartName = "Chart_PCA_cov_with_groups" + xAxis + "v" + yAxis
        plotChartNode = slicer.mrmlScene.GetFirstNodeByName(chartName)
        if plotChartNode is None:
            plotChartNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLPlotChartNode", chartName
            )
        else:
            plotChartNode.RemoveAllPlotSeriesNodeIDs()

        # ---- Background series: every specimen as a gray square ----
        bgTableName = "PCA Scatter Plot Table All Specimens (groups)"
        bgTable = slicer.mrmlScene.GetFirstNodeByName(bgTableName)
        if bgTable is None:
            bgTable = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLTableNode", bgTableName
            )
        else:
            bgTable.RemoveAllColumns()
        bgTable.AddColumn().SetName("Subject ID")
        bgTable.SetColumnType("Subject ID", vtk.VTK_STRING)
        for i in range(pcNumber):
            col = bgTable.AddColumn()
            col.SetName("PC" + str(i + 1))
            bgTable.SetColumnType("PC" + str(i + 1), vtk.VTK_FLOAT)
        t = bgTable.GetTable()
        t.SetNumberOfRows(numPoints)
        for i in range(numPoints):
            t.SetValue(i, 0, files[i])
            for j in range(pcNumber):
                t.SetValue(i, j + 1, data[i, j])

        bgSeries = slicer.mrmlScene.GetFirstNodeByName("Specimens_all_groups")
        if bgSeries is None:
            bgSeries = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLPlotSeriesNode", "Specimens_all_groups"
            )
        bgSeries.SetAndObserveTableNodeID(bgTable.GetID())
        bgSeries.SetXColumnName(xAxis)
        bgSeries.SetYColumnName(yAxis)
        bgSeries.SetLabelColumnName("Subject ID")
        bgSeries.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
        bgSeries.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
        bgSeries.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleSquare)
        bgSeries.SetColor(0.6, 0.6, 0.6)  # gray
        plotChartNode.AddAndObservePlotSeriesNodeID(bgSeries.GetID())

        # ---- One templates series per group, each with a distinct color ----
        groupColors = [
            (1.00, 0.00, 0.00),   # red
            (0.00, 0.50, 1.00),   # blue
            (0.00, 0.70, 0.20),   # green
            (1.00, 0.55, 0.00),   # orange
            (0.60, 0.20, 0.80),   # purple
            (0.00, 0.75, 0.75),   # cyan
            (0.85, 0.85, 0.00),   # yellow
            (0.85, 0.10, 0.55),   # magenta
        ]
        for gIdx, factor in enumerate(uniqueFactors):
            tplIdxThisGroup = [
                ti for ti in templatesIndices if factors[ti] == factor
            ]
            if not tplIdxThisGroup:
                continue
            tblName = f"PCA Scatter Plot Table Templates Group {factor}"
            tbl = slicer.mrmlScene.GetFirstNodeByName(tblName)
            if tbl is None:
                tbl = slicer.mrmlScene.AddNewNodeByClass(
                    "vtkMRMLTableNode", tblName
                )
            else:
                tbl.RemoveAllColumns()
            tbl.AddColumn().SetName("Subject ID")
            tbl.SetColumnType("Subject ID", vtk.VTK_STRING)
            for i in range(pcNumber):
                col = tbl.AddColumn()
                col.SetName("PC" + str(i + 1))
                tbl.SetColumnType("PC" + str(i + 1), vtk.VTK_FLOAT)
            tt = tbl.GetTable()
            tt.SetNumberOfRows(len(tplIdxThisGroup))
            for r, ti in enumerate(tplIdxThisGroup):
                tt.SetValue(r, 0, files[ti])
                for j in range(pcNumber):
                    tt.SetValue(r, j + 1, data[ti, j])

            seriesName = f"Templates_{factor}"
            series = slicer.mrmlScene.GetFirstNodeByName(seriesName)
            if series is None:
                series = slicer.mrmlScene.AddNewNodeByClass(
                    "vtkMRMLPlotSeriesNode", seriesName
                )
            series.SetAndObserveTableNodeID(tbl.GetID())
            series.SetXColumnName(xAxis)
            series.SetYColumnName(yAxis)
            series.SetLabelColumnName("Subject ID")
            series.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
            series.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
            series.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleDiamond)
            series.SetMarkerSize(11)
            color = groupColors[gIdx % len(groupColors)]
            series.SetColor(*color)
            plotChartNode.AddAndObservePlotSeriesNodeID(series.GetID())

        plotChartNode.SetTitle("PCA Scatter Plot with kmeans clusters")
        plotChartNode.SetXAxisTitle(xAxis)
        plotChartNode.SetYAxisTitle(yAxis)

        # Make axes symmetric around 0 with equal extent on both axes so the
        # visual spread on PC1 and PC2 is comparable.
        _absMax = float(np.max(np.abs(data[:, :pcNumber]))) if numPoints else 1.0
        _pad = _absMax * 1.05 if _absMax > 0 else 1.0
        plotChartNode.SetXAxisRangeAuto(False)
        plotChartNode.SetYAxisRangeAuto(False)
        plotChartNode.SetXAxisRange(-_pad, _pad)
        plotChartNode.SetYAxisRange(-_pad, _pad)

        layoutManager = slicer.app.layoutManager()
        layoutManager.setLayout(505)
        slicer.app.processEvents()

        plotWidget = layoutManager.plotWidget(0)
        plotViewNode = plotWidget.mrmlPlotViewNode()
        plotViewNode.SetPlotChartNodeID(plotChartNode.GetID())

    def makeScatterPlot(
        self, data, files, title, xAxis, yAxis, pcNumber, templatesIndices
    ):
        numPoints = len(data)
        # Scatter plot for all specimens with no group input
        plotChartNode = slicer.mrmlScene.GetFirstNodeByName(
            "Chart_PCA_cov" + xAxis + "v" + yAxis
        )
        if plotChartNode is None:
            plotChartNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLPlotChartNode", "Chart_PCA_cov" + xAxis + "v" + yAxis
            )
        else:
            plotChartNode.RemoveAllPlotSeriesNodeIDs()

        tableNode = slicer.mrmlScene.GetFirstNodeByName(
            "PCA Scatter Plot Table without group input"
        )
        if tableNode is None:
            tableNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLTableNode", "PCA Scatter Plot Table without group input"
            )
        else:
            tableNode.RemoveAllColumns()  # clear previous data from columns

        labels = tableNode.AddColumn()
        labels.SetName("Subject ID")
        tableNode.SetColumnType("Subject ID", vtk.VTK_STRING)

        for i in range(pcNumber):
            pc = tableNode.AddColumn()
            colName = "PC" + str(i + 1)
            pc.SetName(colName)
            tableNode.SetColumnType(colName, vtk.VTK_FLOAT)

        table = tableNode.GetTable()
        table.SetNumberOfRows(numPoints)
        for i in range(len(files)):
            table.SetValue(i, 0, files[i])
            for j in range(pcNumber):
                table.SetValue(i, j + 1, data[i, j])

        plotSeriesNode1 = slicer.mrmlScene.GetFirstNodeByName(
            "Specimens_no_group_input"
        )
        if plotSeriesNode1 is None:
            plotSeriesNode1 = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLPlotSeriesNode", "Specimens_no_group_input"
            )

        plotSeriesNode1.SetAndObserveTableNodeID(tableNode.GetID())
        plotSeriesNode1.SetXColumnName(xAxis)
        plotSeriesNode1.SetYColumnName(yAxis)
        plotSeriesNode1.SetLabelColumnName("Subject ID")
        plotSeriesNode1.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
        plotSeriesNode1.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
        plotSeriesNode1.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleSquare)
        plotSeriesNode1.SetColor(0.5, 0.5, 0.5)  # gray for individual specimens
        plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode1.GetID())

        # Set up plotSeriesNode for templates
        tableNode = slicer.mrmlScene.GetFirstNodeByName(
            "PCA_Scatter_Plot_Table_Templates_no_group"
        )
        if tableNode is None:
            tableNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLTableNode", "PCA_Scatter_Plot_Table_Templates_no_group"
            )
        else:
            tableNode.RemoveAllColumns()  # clear previous data from columns

        labels = tableNode.AddColumn()
        labels.SetName("Subject ID")
        tableNode.SetColumnType("Subject ID", vtk.VTK_STRING)

        for i in range(pcNumber):
            pc = tableNode.AddColumn()
            colName = "PC" + str(i + 1)
            pc.SetName(colName)
            tableNode.SetColumnType(colName, vtk.VTK_FLOAT)

        table = tableNode.GetTable()
        table.SetNumberOfRows(len(templatesIndices))
        for i in range(len(templatesIndices)):
            tempIndex = templatesIndices[i]
            table.SetValue(i, 0, files[tempIndex])
            for j in range(pcNumber):
                table.SetValue(i, j + 1, data[tempIndex, j])

        plotSeriesNode1 = slicer.mrmlScene.GetFirstNodeByName(
            "Templates_no_group_input"
        )
        if plotSeriesNode1 is None:
            plotSeriesNode1 = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLPlotSeriesNode", "Templates_no_group_input"
            )
        plotSeriesNode1.SetAndObserveTableNodeID(tableNode.GetID())
        plotSeriesNode1.SetXColumnName(xAxis)
        plotSeriesNode1.SetYColumnName(yAxis)
        plotSeriesNode1.SetLabelColumnName("Subject ID")
        plotSeriesNode1.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
        plotSeriesNode1.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
        plotSeriesNode1.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleDiamond)
        plotSeriesNode1.SetColor(1.0, 0.0, 0.0)  # bright red for templates
        # Add data series to chart
        plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode1.GetID())

        plotChartNode.SetTitle("PCA Scatter Plot with templates")
        plotChartNode.SetXAxisTitle(xAxis)
        plotChartNode.SetYAxisTitle(yAxis)

        # Make axes symmetric around 0 with equal extent on both axes.
        _absMax = float(np.max(np.abs(data[:, :pcNumber]))) if numPoints else 1.0
        _pad = _absMax * 1.05 if _absMax > 0 else 1.0
        plotChartNode.SetXAxisRangeAuto(False)
        plotChartNode.SetYAxisRangeAuto(False)
        plotChartNode.SetXAxisRange(-_pad, _pad)
        plotChartNode.SetYAxisRange(-_pad, _pad)

        # Switch to a Slicer layout that contains a plot view for plotwidget
        layoutManager = slicer.app.layoutManager()
        layoutManager.setLayout(505)
        slicer.app.processEvents()

        # Select chart in plot view
        plotWidget = layoutManager.plotWidget(0)
        plotViewNode = plotWidget.mrmlPlotViewNode()
        plotViewNode.SetPlotChartNodeID(plotChartNode.GetID())
