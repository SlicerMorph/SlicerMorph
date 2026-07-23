import numpy as np
import os
import fnmatch
import scipy.linalg as sp

# PCA
def makeTwoDim(monsters):
    # Reshape (n_landmarks, 3, n_subjects) to (3*n_landmarks, n_subjects) in Fortran order,
    # then center each row across subjects.
    i, j, k = monsters.shape
    tmp = monsters.reshape(i * j, k, order='F').astype(np.float64, copy=True)
    tmp -= np.mean(tmp, axis=1, keepdims=True)
    return tmp

def calcMean(vec):
    return vec.mean(axis=1)

def calcCov(vec):
    # Vectorized covariance: (X - mean) @ (X - mean).T / N
    # Matches the original convention of dividing by N (not N-1).
    i, j = vec.shape
    centered = vec - vec.mean(axis=1, keepdims=True)
    return (centered @ centered.T) / float(j)

def sortEig(eVal, eVec):
    i,j=eVec.shape
    ePair=list(range(j))
    for y in range(j):
      ePair[y]=[(np.abs(eVal[y]), eVec[:,y])]
      ePair[y].sort()
      ePair[y].reverse()
    return ePair

def pairEig(eVal, eVec):
    i,j=eVec.shape
    ePair=list(range(j))
    for y in range(j):
      ePair[y]=[(np.abs(eVal[y]), eVec[:,y])]
    return ePair

def makeTransformMatrix(ePair,pcA,pcB):
    tmp=ePair[0][0][1]
    i=tmp.shape
    i=i[0]
    vec1=ePair[pcA][0][1]
    vec2=ePair[pcB][0][1]

    transform=np.zeros((i,2))
    transform[:,0]=vec1.reshape(i).real
    transform[:,1]=vec2.reshape(i).real
    return transform

def plotTanProj(monsters,pcA,pcB):
    i, j, k = monsters.shape
    twoDim=makeTwoDim(monsters)
    mShape=calcMean(twoDim)
    covMatrix=calcCov(twoDim)
    if k > i * j:  # limit results returned if sample number is less than observations
      self.val, self.vec = sp.eigh(covMatrix)
    else:
      self.val, self.vec = sp.eigh(covMatrix, eigvals=(i * j - k, i * j - 1))
    eigVal=eigVal[::-1]
    eigVec=eigVec[:, ::-1]
    eigPair=pairEig(eigVal,eigVec)
    transform=makeTransformMatrix(eigPair,pcA,pcB)
    transform=np.transpose(transform)
    coords=np.dot(transform,twoDim)
    tmp=np.column_stack((coords[0,:],coords[1,:]))
    return tmp

def plotTanProj(monsters,eigSort,pcA,pcB):
    twoDim=makeTwoDim(monsters)
    transform=makeTransformMatrix(eigSort,pcA,pcB)
    transform=np.transpose(transform)
    coords=np.dot(transform,twoDim)
    tmp=np.column_stack((coords[0,:],coords[1,:]))
    return tmp

############## GPA original
#center shape by removing the mean of each column
def centerShape(shape):
    shape=shape-shape.mean(axis=0)
    return shape

#scale shape by divinding by frobinius norm
def scaleShape(shape):
    shape=shape/np.linalg.norm(shape)
    return shape

#align one shape to a reference shape, solely by rotation
def alignShape(refShape,shape):
    """
    Align the shape to the mean.
    """
    u,s,v=sp.svd(np.dot(np.transpose(refShape),shape), full_matrices=True)
    rotationMatrix=np.dot(np.transpose(v), np.transpose(u))
    shape=np.dot(shape,rotationMatrix)
    return shape

def meanShape(monsters):
    return monsters.mean(axis=2)

def procDist(monsters,mshape):
    i,j,k=monsters.shape
    procDists=np.zeros(k)
    for x in range(k):
      tmp=monsters[:,:,x]-mshape
      procDists[x]=np.linalg.norm(tmp,'fro')
    return procDists

################# GPA update

# ---------------------------------------------------------------------------
# Sliding semilandmark GPA
#
# REFERENCE IMPLEMENTATION / ACKNOWLEDGMENT
#   This is a faithful Python port of the sliding-semilandmark Generalized
#   Procrustes Analysis in the R package **geomorph** (Adams, Collyer, Kaliontzopoulou
#   & Baken), which is the reference implementation that was ported here.
#   Specifically, it reproduces geomorph's gpagen() and its supporting routines:
#     - gpagen                     R/gpagen.r
#     - pGpa.wSliders, BE.slide, procD.slide, semilandmarks.slide.BE/.ProcD,
#       Ltemplate / LtemplateApprox, getSurfPCs, getU_s, tangents, orp
#                                  R/geomorph.support.code.r
#     - center.scale, cs.scale, apply.pPsup, fast.ginv (from RRPP, Collyer &
#       Adams)          RRPP/R/shared.support.code.r
#   Source: https://github.com/geomorphR/geomorph (Stable branch, v4.0.10).
#   geomorph is distributed under the GPL; see that project for its license and
#   the underlying methods (Bookstein 1997; Gunz et al. 2005; Rohlf 2010).
#
# Semilandmarks are slid along curve tangents and/or within surface tangent
# planes to minimize either bending energy (BE, geomorph ProcD=FALSE, the
# geomorph default) or Procrustes distance (ProcD, geomorph ProcD=TRUE).
#
# Convention: landmark arrays are (p, k, n) = (landmarks, dims, specimens);
# each specimen is a (p, k) matrix.  This block is self-contained and does not
# alter the fixed-landmark GPA path (runGPA / runGPANoScale) when no
# semilandmarks are supplied.  Verified to reproduce geomorph 4.0.10 to
# machine precision on the mouse-skull test data (3D).
# ---------------------------------------------------------------------------

def _gm_center(x):
    return x - x.mean(axis=0, keepdims=True)

def _gm_csize(x):
    c = _gm_center(np.asarray(x, dtype=float))
    return np.sqrt(np.sum(c * c))

def _gm_cs_scale(x):
    return x / _gm_csize(x)

def _gm_center_scale(x):
    c = _gm_center(np.asarray(x, dtype=float))
    cs = np.sqrt(np.sum(c * c))
    return c / cs, cs

def _gm_rotate_onto(M_rot, y_rot, y_full):
    # Partial Procrustes rotation of y_full onto M using the rot.pts subset.
    k = y_full.shape[1]
    MY = M_rot.T @ y_rot
    U, _, Vt = np.linalg.svd(MY)
    sgn = np.sign(np.linalg.det(MY))
    if sgn == 0:
        sgn = 1.0
    U[:, k - 1] = U[:, k - 1] * sgn
    R = U @ Vt
    return y_full @ R.T

def _gm_apply_pPsup(M, Ya, rot_pts):
    Ms = _gm_cs_scale(M)
    return [_gm_rotate_onto(Ms[rot_pts, :], y[rot_pts, :], y) for y in Ya]

def _gm_pairwise_dist(Mr):
    diff = Mr[:, None, :] - Mr[None, :, :]
    return np.sqrt(np.sum(diff * diff, axis=2))

def _gm_Ltemplate(Mr, approx=False):
    # Inverse of the thin-plate-spline bending-energy matrix (top-left p x p
    # block).  3D kernel P = Euclidean distance (biharmonic |r|); 2D = r^2 log r.
    Mr = np.asarray(Mr, dtype=float)
    p, k = Mr.shape
    P = _gm_pairwise_dist(Mr)
    if k == 2:
        with np.errstate(divide='ignore', invalid='ignore'):
            P = P ** 2 * np.log(P)
        P[~np.isfinite(P)] = 0.0
    Q = np.hstack([np.ones((p, 1)), Mr])
    L = np.zeros((p + k + 1, p + k + 1))
    L[:p, :p] = P
    L[:p, p:] = Q
    L[p:, :p] = Q.T
    L = 0.5 * (L + L.T)
    if approx:
        np.fill_diagonal(L, 1e-4 * np.std(L, ddof=1))
    try:
        Linv = np.linalg.solve(L, np.eye(L.shape[0]))
    except np.linalg.LinAlgError:
        Linv = -np.linalg.pinv(L)
    return Linv[:p, :p]

def _gm_getSurfPCs(y, surf):
    # Local tangent-plane basis (top two PCs) at each surface semilandmark,
    # sign-matched to the specimen's global PC axes (geomorph getSurfPCs).
    y = np.asarray(y, dtype=float)
    p, k = y.shape
    Vt = np.linalg.svd(_gm_center(y), full_matrices=True)[2]
    d = _gm_pairwise_dist(y)
    pc_dir = [np.zeros((k, k)) for _ in range(p)]
    surf_set = {int(s) for s in surf}
    for j in range(p):
        if j not in surf_set:
            continue
        nn = np.argsort(d[:, j], kind='stable')[:5]   # 5 nearest incl self
        x = _gm_center(y[nn, :])
        pc = np.linalg.svd(x, full_matrices=True)[2]
        s = np.sign(np.array([Vt[:, i] @ pc[:, i] for i in range(k)]))
        s[s == 0] = 1.0
        pc_dir[j] = pc * s[:, None]
    p1 = np.array([m[0, :] for m in pc_dir])
    p2 = np.array([m[1, :] for m in pc_dir])
    return p1, p2

def _gm_tangents(curves, x, scaled=True):
    # Curve tangent direction at each slider, from its two flanking landmarks.
    x = np.asarray(x, dtype=float)
    ts = x[curves[:, 2], :] - x[curves[:, 0], :]
    if scaled:
        norm = np.sqrt(np.sum(ts * ts, axis=1, keepdims=True))
        norm[norm == 0] = 1.0
        ts = ts / norm
    y = np.zeros_like(x)
    y[curves[:, 1], :] = ts
    return y

def _gm_getU_s(y, tans, surf, BEp, m, k):
    # Sliding-direction basis U (m*k x ncols); zero columns dropped.
    if tans is not None and surf is None:
        U = np.zeros((m * k, m))
    elif tans is None and surf is not None:
        U = np.zeros((m * k, 2 * m))
    else:
        U = np.zeros((m * k, 3 * m))
    if BEp is None:
        BEp = np.arange(m)
    BEp = np.asarray(BEp)
    if tans is not None:
        for ax in range(k):
            U[ax * m:(ax + 1) * m, 0:m] = np.diag(tans[BEp, ax])
    if surf is not None:
        tp = m if (tans is not None) else 0
        p1, p2 = _gm_getSurfPCs(y, surf)
        p1b = p1[BEp, :]
        p2b = p2[BEp, :]
        for ax in range(k):
            U[ax * m:(ax + 1) * m, tp:tp + m] = np.diag(p1b[:, ax])
            U[ax * m:(ax + 1) * m, tp + m:tp + 2 * m] = np.diag(p2b[:, ax])
    keep = np.where(np.sum(U * U, axis=0) != 0)[0]
    return U[:, keep]

def _gm_slide_BE(y, tans, surf, ref, Lk, appBE, BEp):
    y = np.asarray(y, dtype=float)
    yc = y - ref
    p, k = yc.shape
    m = len(BEp) if appBE else p
    if m == p:
        appBE = False
    if not appBE:
        BEp = np.arange(p)
    yvec = yc[BEp, :].reshape(-1, order='F')
    U = _gm_getU_s(y, tans, surf, BEp, m, k)
    tULk = U.T @ Lk
    mid = tULk @ U
    mid = 0.5 * (mid + mid.T)
    # mid is PSD but can be exactly singular for legitimate configurations:
    # the bending-energy operator has a (k+1)-per-axis null space (the affine
    # part), so it goes singular whenever the sliding directions span into it
    # (coincident semilandmarks, near-coplanar points, or too many sliders for
    # the landmark count).  geomorph falls back to a generalized inverse here
    # for the same reason; mirror that instead of raising out of Execute GPA.
    try:
        coef = np.linalg.solve(mid, tULk @ yvec)
    except np.linalg.LinAlgError:
        coef = np.linalg.pinv(mid) @ (tULk @ yvec)
    res = (U @ coef).reshape(m, k, order='F')
    if appBE:
        temp = np.zeros((p, k))
        temp[BEp, :] = res
    else:
        temp = res
    return y - temp

def _gm_slide_ProcD(y, tans, surf, ref):
    y = np.asarray(y, dtype=float)
    yc = y - ref
    p, k = yc.shape
    U = _gm_getU_s(y, tans, surf, None, p, k)
    yvec = yc.reshape(-1, order='F')
    res = (U @ (U.T @ yvec)).reshape(p, k, order='F')
    return y - res

def _gm_sum_list(Ya):
    S = np.zeros_like(Ya[0])
    for y in Ya:
        S = S + y
    return S

def _gm_BE_slide(curves, surf, rot_pts, Ya, ref, appBE, sen, max_iter, tol):
    n = len(Ya)
    p, k = Ya[0].shape
    it = 1
    slid0 = Ya
    ss0 = np.sum(_gm_sum_list(Ya)[rot_pts, :] ** 2) / n
    Q = ss0
    if not isinstance(sen, (int, float)):
        sen = 0.5
    if sen < 0.1:
        sen = 0.1
    if sen >= 1:
        appBE = False
    if appBE:
        BEp = []
        if curves is not None:
            BEp += list(np.unique(curves.reshape(-1)))
        if surf is not None:
            BEp += list(np.asarray(surf))
        Up = np.round(np.linspace(1, p, int(round(p * sen)))).astype(int) - 1
        BEp = np.array(sorted(set(list(BEp) + list(Up))))
    else:
        BEp = np.arange(p)
    doTans = curves is not None
    while Q > tol:
        it += 1
        tans_list = ([_gm_tangents(curves, y, True) for y in slid0]
                     if doTans else [None] * n)
        L = _gm_Ltemplate(ref[BEp, :], approx=True) if appBE else _gm_Ltemplate(ref)
        Lk = np.kron(np.eye(k), L)
        slid = [_gm_slide_BE(slid0[j], tans_list[j], surf, ref, Lk, appBE, BEp)
                for j in range(n)]
        ss = np.sum(_gm_sum_list(slid)[rot_pts, :] ** 2) / n
        slid0 = _gm_apply_pPsup(ref, slid, rot_pts)
        ref = _gm_cs_scale(_gm_sum_list(slid0) / n)
        Q = abs(ss0 - ss)
        ss0 = ss
        if it >= max_iter:
            break
    return slid0, ref, it + 1, Q

def _gm_procD_slide(curves, surf, rot_pts, Ya, ref, max_iter, tol):
    n = len(Ya)
    p, k = Ya[0].shape
    it = 1
    slid0 = Ya
    ss0 = np.sum(_gm_sum_list(Ya)[rot_pts, :] ** 2) / n
    Q = ss0
    doTans = curves is not None
    while Q > tol:
        it += 1
        tans_list = ([_gm_tangents(curves, y, True) for y in slid0]
                     if doTans else [None] * n)
        slid = [_gm_slide_ProcD(slid0[j], tans_list[j], surf, ref) for j in range(n)]
        ss = np.sum(_gm_sum_list(slid)[rot_pts, :] ** 2) / n
        slid0 = _gm_apply_pPsup(ref, slid, rot_pts)
        ref = _gm_cs_scale(_gm_sum_list(slid0) / n)
        Q = abs(ss0 - ss)
        ss0 = ss
        if it >= max_iter:
            break
    return slid0, ref, it + 1, Q

def _gm_orp(Y):
    # Orthogonal projection of aligned coords into the tangent space at the mean.
    n = len(Y)
    p, k = Y[0].shape
    Mc, _ = _gm_center_scale(_gm_sum_list(Y) / n)
    Y1 = Mc.reshape(-1, order='F')
    mat = np.array([y.reshape(-1, order='F') for y in Y])
    Ipk = np.eye(p * k)
    Xp = mat @ (Ipk - np.outer(Y1, Y1)) + np.outer(np.ones(n), Y1)
    return [Xp[j, :].reshape(p, k, order='F') for j in range(n)]

def runGPAWithSliders(allLandmarkSets, surfaceIndices=None, curves=None,
                      slidingMethod='BE', rot_pts=None, max_iter=10, tol=1e-4,
                      doProjection=True):
    """Generalized Procrustes Analysis with sliding semilandmarks (geomorph gpagen).

    allLandmarkSets : (p, k, n) landmark array (modified copy is used).
    surfaceIndices  : 0-based indices of SURFACE semilandmarks (geomorph surfaces=).
    curves          : optional (nCurve, 3) int array of (before, slider, after)
                      0-based indices for CURVE semilandmarks (geomorph curves=).
    slidingMethod   : 'BE' -> minimize bending energy (geomorph default);
                      'ProcD' -> minimize Procrustes distance.
    Returns (coords, meanShape) with coords shaped (p, k, n), matching runGPA.
    """
    A = np.asarray(allLandmarkSets, dtype=float)
    p, k, n = A.shape
    Y = [A[:, :, j].copy() for j in range(n)]

    surf = None
    if surfaceIndices is not None and len(surfaceIndices) > 0:
        surf = np.asarray([int(s) for s in surfaceIndices])
    if curves is not None and len(curves) > 0:
        curves = np.asarray(curves, dtype=int)
    else:
        curves = None
    if rot_pts is None:
        rot_pts = np.arange(p)
    rot_pts = np.asarray(rot_pts)

    Yc = [_gm_center_scale(y) for y in Y]
    Ya = [c for (c, _) in Yc]
    Ya = _gm_apply_pPsup(Ya[0], Ya, rot_pts)
    M = _gm_sum_list(Ya) / n

    useProcD = str(slidingMethod).upper().startswith('PROC')
    if useProcD:
        coords, M, _, _ = _gm_procD_slide(curves, surf, rot_pts, Ya, M, max_iter, tol)
    else:
        coords, M, _, _ = _gm_BE_slide(curves, surf, rot_pts, Ya, M,
                                       False, 0.5, max_iter, tol)

    if doProjection:
        coords = _gm_orp(coords)
    meanShapeOut = _gm_sum_list(coords) / n
    outCoords = np.stack(coords, axis=2)   # (p, k, n)
    # Write the aligned coordinates back into the caller's array, mirroring the
    # in-place behavior of the fixed-landmark runGPA / runGPANoScale paths. This
    # keeps a reused reference (e.g. LMData.lmOrig) on the same unit-centroid-size
    # scale as the returned coords / mean, so downstream code such as
    # calcLMVariation() does not mix raw and scaled units.
    try:
        allLandmarkSets[...] = outCoords
        return allLandmarkSets, meanShapeOut
    except (TypeError, ValueError, AttributeError):
        return outCoords, meanShapeOut


def runGPA(allLandmarkSets, semiLandmarkIndices=None, slidingMethod='BE', curves=None):
  if semiLandmarkIndices:
    return runGPAWithSliders(allLandmarkSets, surfaceIndices=semiLandmarkIndices,
                             curves=curves, slidingMethod=slidingMethod)
  i,j,k=allLandmarkSets.shape
  for index in range(k):
    landmarkSet=allLandmarkSets[:,:,index]
    tempSet = applyCenterScale(landmarkSet)
    allLandmarkSets[:,:,index]=tempSet
  allLandmarkSets = procrustesAlign(allLandmarkSets[:,:,0],allLandmarkSets)
  initialMeanShape=meanShape(allLandmarkSets)
  initialMeanShape = scaleShape(initialMeanShape)
  diff=1
  tries=0
  while diff>0.0001 and tries<5:
    allLandmarkSets = procrustesAlign(initialMeanShape,allLandmarkSets)
    currentMeanShape=meanShape(allLandmarkSets)
    diff=np.linalg.norm(initialMeanShape-currentMeanShape)
    initialMeanShape=currentMeanShape
    tries=tries+1
  return allLandmarkSets, currentMeanShape


def procrustesAlign(mean, allLandmarkSets):
  mean = scaleShape(mean)
  i,j,k=allLandmarkSets.shape
  for index in range(k):
    allLandmarkSets[:,:,index] = alignShape(mean, allLandmarkSets[:,:,index])
  return allLandmarkSets

def applyCenterScale(landmarkSet):
  landmarkSet=centerShape(landmarkSet)
  landmarkSet=scaleShape(landmarkSet)
  return landmarkSet

def runGPANoScale(allLandmarkSets, semiLandmarkIndices=None, slidingMethod='BE', curves=None):
    if semiLandmarkIndices is None:
      semiLandmarkIndices = []
    if semiLandmarkIndices:
      # Sliding semilandmarks are defined on centroid-size-scaled configurations
      # (geomorph gpagen), so the Boas / no-scale path defers to the standard
      # scaled sliding GPA when sliders are present.
      return runGPAWithSliders(allLandmarkSets, surfaceIndices=semiLandmarkIndices,
                               curves=curves, slidingMethod=slidingMethod)
    i,j,k = allLandmarkSets.shape
    for index in range(k):
      landmarkSet = allLandmarkSets[:,:,index]
      tempSet = applyCenter(landmarkSet)  # center only, no scaling
      allLandmarkSets[:,:,index] = tempSet
    allLandmarkSets = procrustesAlignNoScale(allLandmarkSets[:,:,0], allLandmarkSets)
    initialMeanShape = meanShape(allLandmarkSets)
    initialMeanShape = centerShape(initialMeanShape) # re-center when no scaling
    diff = 1
    tries = 0
    while diff > 0.0001 and tries < 5:
      allLandmarkSets = procrustesAlignNoScale(initialMeanShape, allLandmarkSets)
      currentMeanShape = meanShape(allLandmarkSets)
      currentMeanShape = centerShape(currentMeanShape)  # re-center when no scaling
      diff = np.linalg.norm(initialMeanShape-currentMeanShape)
      initialMeanShape = currentMeanShape
      tries += 1
    for index in range(k):
      allLandmarkSets[:,:,index] = centerShape(allLandmarkSets[:,:,index])
    return allLandmarkSets, currentMeanShape

def procrustesAlignNoScale(mean, allLandmarkSets):
    i,j,k = allLandmarkSets.shape
    mean = centerShape(mean)  # re-center when no scaling
    for index in range(k):
      aligned = alignShape(mean, allLandmarkSets[:, :, index])
      aligned = centerShape(aligned)  # re-center when no scaling
      allLandmarkSets[:,:,index] = aligned
    return allLandmarkSets

def applyCenter(landmarkSet):
  landmarkSet=centerShape(landmarkSet)
  return landmarkSet
