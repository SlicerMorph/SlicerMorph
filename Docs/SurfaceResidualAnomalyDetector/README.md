## Surface Residual Anomaly Detector

**Title:** Unsupervised Surface Anomaly Detection from Smoothing Residuals

**Summary:** This module compares an input surface model with a smoothed copy of itself and visualizes the per-vertex geometric residual as an anomaly heatmap. The core pipeline is deterministic, dependency-free (no pretrained models, no deep learning) and based on robust statistics (median / median absolute deviation). It tolerates real-world acquisition artifacts — disconnected scan fragments, high-frequency surface noise, and open/cropped mesh boundaries — and optionally augments the geometric signal with an unsupervised Isolation Forest model when scikit-learn is available.

The AI mode is self-contained and unsupervised: it learns the distribution of local geometric descriptors from the current specimen and identifies statistically rare surface patterns. It does not recognize pathology and does not use clinical labels.

### PIPELINE

1. Read the selected input model and deep-copy its surface (the original node is never modified), then triangulate it (`vtkTriangleFilter`).
2. **Remove small disconnected components** (optional, on by default): `vtkPolyDataConnectivityFilter` labels every connected fragment of the mesh. Fragments smaller than the component-size threshold (a percentage of the total point count) are dropped; the rest — including every anatomically-sized piece, not just the single largest one — are kept. A "keep largest component only" mode is available for meshes that should reduce to a single island.
3. Compute consistent point normals (`vtkPolyDataNormals`, splitting disabled so point count/order is preserved).
4. **Smooth the reference surface** with one of two non-topology-changing filters:
   - **Windowed sinc** (default): `vtkWindowedSincPolyDataFilter`, a non-shrinking smoother controlled by iterations and pass band.
   - **Laplacian**: `vtkSmoothPolyDataFilter`, controlled by iterations and relaxation factor.
5. Verify explicitly that the original and smoothed meshes have the same number of points and cells. If correspondence is lost, the module stops and reports an error instead of silently computing incorrect distances.
6. **Detect and exclude open/cropped mesh boundaries**: `vtkFeatureEdges` (boundary edges only) finds true boundary vertices, which are then ring-expanded across the mesh adjacency graph (0 = true boundary only, N = N edge-hops out). When "Ignore boundary vertices" is enabled, excluded vertices never contribute to the residual median/MAD, AI feature normalization/training, or any percentile threshold, and are always forced to 0 in every final anomaly mask.
7. Compute a raw per-vertex residual (`Surface_Residual_Raw`) using one of two modes:
   - **Normal displacement** (default): `residual = abs(dot(original_point - smoothed_point, original_normal))`. Emphasizes inward/outward surface deviation and is less sensitive to tangential vertex motion.
   - **Euclidean distance**: `residual = ||original_point - smoothed_point||`.
8. **Denoise the residual map** (optional, on by default): vertex adjacency is built directly from the mesh triangles and reused everywhere below. Each vertex's residual is replaced by the median (default) or mean of itself and its neighbors within the selected ring size (1-3 hops), repeated for the selected number of iterations. The result is stored as `Surface_Residual_Filtered`. When denoising is off, `Surface_Residual_Filtered` equals `Surface_Residual_Raw`.
9. Normalize the raw residual by the bounding-box diagonal of the original mesh (`Normalized_Surface_Residual`), guarding against a zero or invalid scale.
10. Compute a robust anomaly score using the median and median absolute deviation (MAD) of the residual used for scoring (the filtered residual when denoising is enabled, otherwise the raw residual):
    ```
    median = median(residuals)
    mad = median(abs(residuals - median))
    robust_z = (residuals - median) / (1.4826 * mad + epsilon)
    ```
    This is computed twice: once unrestricted (`Residual_Anomaly_Score_Raw`), and once with the median/MAD taken only from valid (non-excluded) vertices and excluded vertices pinned to the minimum valid score (`Residual_Anomaly_Score_BoundaryAware`). `Residual_Anomaly_Score` is kept as a copy of the boundary-aware score for backward compatibility. Higher scores mean more anomalous. The percentile threshold is computed on the full, unclamped distribution of valid vertices; clamping is only applied to the display scalar range, never to the stored data or the percentile calculation.
11. **Optional unsupervised AI**: builds a six-descriptor feature vector per vertex (normalized raw/filtered residual, mean curvature, local normal variation, local roughness, radial distance from the mesh centroid), z-normalizes each feature using only valid vertices, and fits an Isolation Forest (deterministic, seed 42, capped at 50,000 training vertices) on the valid subset. Inference always runs on every vertex.
12. **Fusion** (AI plus residual fusion mode): both the AI score and the boundary-aware residual score are converted to 0-1 percentile ranks over valid vertices, then combined as `fused = ai_weight * AI_normalized + (1 - ai_weight) * residual_normalized`.
13. Flag points above the selected percentile in `*_Anomaly_Mask_Raw` for each active method (residual, AI, fused) — always computed only from valid vertices, with excluded vertices forced to 0.
14. **Remove small anomaly clusters** (optional, on by default): connectivity is built only between neighboring vertices that are both flagged 1, using the direct mesh adjacency. Connected clusters smaller than the minimum cluster size are cleared back to 0, producing the `*_Anomaly_Mask_Clean` arrays used by the clean/binary visualization modes.
15. Display the residual-analysis output as a scalar heatmap using a robust (2nd-98th percentile) color range, with a "Surface residual anomaly" color legend.

### OUTPUT ARRAYS

Stored as point-data scalar arrays on the `<input name> - Residual Analysis` output model (which preserves the cleaned original geometry — i.e. after any small-component removal):

- `Surface_Residual_Raw` — per-vertex residual in mesh units, before spatial denoising.
- `Surface_Residual_Filtered` — the same residual after neighborhood median/mean filtering (equals the raw array when denoising is disabled).
- `Normalized_Surface_Residual` — the raw residual divided by the bounding-box diagonal.
- `Boundary_Exclusion_Mask` — 1 = excluded from analysis (true boundary + ring expansion), 0 = valid.
- `Residual_Anomaly_Score_Raw` — robust z-score computed from every vertex, ignoring boundary exclusion.
- `Residual_Anomaly_Score_BoundaryAware` — robust z-score computed from valid vertices only; excluded vertices pinned to the minimum valid score.
- `Residual_Anomaly_Score` — alias/copy of `Residual_Anomaly_Score_BoundaryAware`, kept for backward compatibility.
- `Residual_Anomaly_Score_Normalized` — `Residual_Anomaly_Score_BoundaryAware` converted to a 0-1 percentile rank over valid vertices.
- `Residual_Anomaly_Mask_Raw` / `Residual_Anomaly_Mask_Clean` — percentile-threshold mask before/after small-cluster cleanup.
- `AI_Anomaly_Score_Raw` / `AI_Anomaly_Score_Normalized`, `AI_Anomaly_Mask_Raw` / `AI_Anomaly_Mask_Clean` — present only when an AI or fusion run completed successfully.
- `Fused_Anomaly_Score`, `Fused_Anomaly_Mask_Raw` / `Fused_Anomaly_Mask_Clean` — present only when "AI plus residual fusion" completed successfully.

### OUTPUT NODES

- **`<input name> - Residual Analysis`**: cleaned original geometry with the scalar arrays above. This is the heatmap you interact with.
- **`<input name> - Smoothed Reference`**: the smoothed geometry, optionally displayed at low opacity.

Running the module again on the same input updates these two nodes in place instead of creating duplicates. The original input model is never modified or destroyed; it is automatically shown at reduced opacity so the heatmap is easy to read. Switching the visualization mode only re-colors the already-computed arrays; it never reruns smoothing, feature extraction, or the AI fit.

### USAGE

**Mesh Cleanup**
- **Remove small disconnected components:** removes tiny floating acquisition fragments before analysis, using `vtkPolyDataConnectivityFilter`. On by default; the main anatomical surface is always preserved.
- **Component-size threshold:** components smaller than this percentage of the total mesh points are removed (0.01-5%, default 0.1%).
- **Keep largest component only:** discards every fragment except the single largest one, regardless of size. Off by default — the default behavior keeps every anatomically-sized piece, not just the largest.
- **Remove weakly connected components (erosion):** off by default. Strict component filtering above only removes fragments that are *never actually disconnected* — it cannot catch debris that got merged onto the main surface through a thin/sparse bridge during acquisition or segmentation (still one connected component by graph standards). This applies progressive topological erosion instead: each pass peels away every currently-remaining vertex with fewer than **Erosion min degree** (default 5; a well-connected mesh interior vertex has degree ~6, thin bridges typically 3-4) still-remaining neighbors, for up to **Erosion iterations** passes (default 6). The vertex labels that survive erosion are then grown back out across the full mesh graph, splitting it into regions; any region other than the largest one that is smaller than the **Component-size threshold** above is removed from the original (non-eroded) mesh. A solid, well-connected mesh is left completely untouched by this step.

**Reference Smoothing**
- **Smoothing method:** **Windowed sinc** (default, non-shrinking) or **Laplacian**.
- **Smoothing iterations:** 1-100, default 20.
- **Pass band:** windowed-sinc only, 0.001-0.5, default 0.08. Lower values smooth more aggressively.
- **Relaxation factor:** Laplacian only, 0.01-0.5, default 0.1.
- **Boundary smoothing:** allow mesh boundary points to move during smoothing.

**Residual**
- **Residual mode:** **Normal displacement** (default) or **Euclidean distance**.
- **Denoise residual map:** on by default; suppresses isolated per-vertex acquisition noise before scoring.
- **Neighborhood rings:** 1-3, default 1.
- **Filtering iterations:** 1-5, default 2.
- **Filter mode:** **Median** (default) or **Mean**.

**Boundary Handling**
- **Ignore boundary vertices:** on by default; excludes detected open/cropped boundary vertices from every statistic, threshold, and final mask.
- **Boundary exclusion rings:** 0-10, default 3. 0 = true boundary vertices only.
- **Show excluded boundary region:** off by default; highlights the excluded region in a distinct color on top of the clean binary visualization modes.

**Anomaly Detection**
- **Anomaly percentile:** percentile of the robust anomaly score used to build the anomaly mask (80-99.5, default 95). Raise it to isolate only the strongest deviations.
- **Remove small anomaly clusters:** on by default; clears anomalous regions that are too small to be spatially coherent.
- **Minimum cluster size:** 5-1000 vertices, default 50.

**Detection Method**
- **Detection method:** **Robust residual statistics**, **Unsupervised AI**, or **AI plus residual fusion**. Defaults to fusion when scikit-learn is available, otherwise falls back to robust residual statistics; the AI-only and fusion options are grayed out (never removed) when scikit-learn is missing, and an AI status label explains why.
- **AI weight:** 0.0-1.0, default 0.5. Only used in fusion mode: `fused_score = ai_weight * AI_normalized + (1 - ai_weight) * residual_normalized`.

**Visualization**
- **Visualization mode:** Continuous residual anomaly score (default), Filtered residual, AI anomaly score, Fused anomaly score, Clean residual anomalies, Clean AI anomalies, Clean fused anomalies, or Boundary exclusion mask. AI/fused modes are only enabled once the corresponding results exist for the current output.
- **Show smoothed reference:** display the `Smoothed Reference` output at low opacity alongside the heatmap.

**Run**
- **Show original (before) / Show result (after):** a checkable button, at the top of the Run section for visibility, that toggles between the two. Pressed ("before"): shows the true, completely unprocessed original input model — never touched by this module — at full opacity, and hides the heatmap. Not pressed ("after"): shows the residual analysis heatmap as usual. Just toggles visibility of the already-existing nodes; never recomputes or modifies any geometry.
- **Display range percentile:** 50-100, default 98. Symmetric percentile `[100-p, p]` used to clamp the color range of the continuous heatmaps. A few extreme outliers (e.g. a very sharp anomaly) can otherwise dominate the default range and make most of the surface look like a single saturated color; lower this value to increase contrast among the remaining results, or raise it toward 100 to bring more extreme values into the visible range. Only re-colors the existing output, no recomputation.
- **Compute residual map:** runs the pipeline described above.
- **Reset visualization:** restores the original model to full opacity/visibility and hides the residual outputs, without deleting them.
- **Export anomalies to JSON...:** writes every point-data array currently on the `Residual Analysis` output (point coordinates, normals, raw/filtered residuals, boundary-aware/normalized scores, boundary exclusion mask, and any AI/fused scores and masks that were computed) plus the settings and run report to a JSON file. Intended as a labeled per-vertex dataset for downstream anomaly-detection training or analysis; enabled only after a successful run.

### INTERPRETATION

The method identifies regions that deviate strongly from a smoothed geometric reference. High residuals may represent anatomical detail, scanning noise, mesh artifacts, damage, or genuine morphological irregularity. They must not be interpreted automatically as pathology.

- **Residual detection** measures deviation from a smoothed reference: it answers "how far did this vertex move when the surface was smoothed?"
- **AI detection** identifies rare combinations of local geometric descriptors (curvature, normal variation, roughness, radial distance, residuals): it answers "how unusual is this vertex's local shape compared to the rest of this specimen?", independent of any single smoothing residual value.
- **Fusion** combines both signals into one 0-1 score, retaining complementary information from each.
- **Boundary exclusion** suppresses open-surface and crop artifacts: cut edges and cropped regions produce large, spurious smoothing residuals and unusual local descriptors that have nothing to do with anatomy.
- AI may detect acquisition noise, anatomical boundaries, mesh artifacts, or real morphology. A high anomaly score — from the residual detector, the AI detector, or their fusion — must not be interpreted automatically as disease or pathology.
- Aggressive boundary exclusion or residual filtering may also remove valid fine anatomy: small but genuine morphological features (fine sutures, small foramina, subtle surface texture) can fall below the minimum cluster size, be smoothed away by a large neighborhood/iteration count, or fall inside an over-large boundary exclusion ring. If fine detail matters, lower the neighborhood rings/filtering iterations/boundary exclusion rings, reduce the minimum cluster size, or inspect the `*_Raw` arrays directly.

**The geometric detector measures deviation from a smooth reference, while the unsupervised model learns which combinations of local surface descriptors are statistically rare. Their fusion retains complementary information while boundary-aware spatial cleanup suppresses acquisition artifacts.**

### PRESENTATION: COMPARING THE FOUR STAGES

A useful way to present the module is to compare, on the same specimen and the same visualization palette:

1. **Residual score** (`Continuous residual anomaly score`) — pure geometric deviation from the smoothed reference.
2. **AI score** (`AI anomaly score`) — pure statistical rarity of local shape descriptors.
3. **Fused score** (`Fused anomaly score`) — the weighted combination of both.
4. **Fused score after boundary exclusion and spatial cleanup** (`Clean fused anomalies`) — the same signal, restricted to spatially coherent regions away from crop/boundary artifacts.

Each stage typically narrows the highlighted region, illustrating how boundary exclusion and cluster cleanup progressively remove artifacts while preserving the genuine anomaly.

### 60-SECOND DEMO

1. Load an anatomical mesh.
2. Select it in the module.
3. Compute the normal-displacement residual.
4. Show the resulting heatmap.
5. Enable the smoothed reference.
6. Change smoothing iterations.
7. Increase the anomaly percentile to isolate only the strongest deviations.
