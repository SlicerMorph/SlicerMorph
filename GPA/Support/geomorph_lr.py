# Support/geomorph_lr.py
# -----------------------------------------------------------------------------
# Geomorph Linear Regression (LR) controller for the SlicerMorph GPA module.
# Encapsulates:
#   • LR tab (formula autocomplete + validation)
#   • R/Rserve panel (detect/launch/connect/check geomorph)
#   • Coefficient visualization (TPS grid + warped landmarks/models)
#
# Usage (from GPAWidget.setup()):
#   from Support.geomorph_lr import GeomorphLR
#   self.lr = GeomorphLR(parent_widget=self, node_collection=GPANodeCollection)
#   self.lr.attach()
#
# This module avoids circular imports: it does not import GPAWidget or GPALogic.
# Any data it needs (LM arrays, files, mean landmarks, scale factors, etc.)
# are read from the parent widget (self.w).
# -----------------------------------------------------------------------------

import os, time, socket, platform, subprocess, shutil, signal
import numpy as np

# Optional pandas/patsy import is deferred until needed
try:
  import pandas as pd  # noqa: F401
except Exception:
  pd = None

import vtk, qt, slicer


# ----------------------------- Small helpers ---------------------------------

class _DummyCollection:
  def AddItem(self, node): pass
  def RemoveItem(self, node): pass


def _safe_text(widget):
  """Return text from QLineEdit/QPlainTextEdit in a PythonQt-safe way."""
  if hasattr(widget, "toPlainText"):
    return str(widget.toPlainText())
  if hasattr(widget, "text"):
    try: return str(widget.text())
    except Exception: return str(widget.text)
  return ""


def _set_text(widget, s):
  """Set text into QLineEdit/QPlainTextEdit in a PythonQt-safe way."""
  if hasattr(widget, "setPlainText"):
    widget.setPlainText(str(s))
  elif hasattr(widget, "setText"):
    try: widget.setText(str(s))
    except Exception: widget.setText = str(s)  # PythonQt fallback


def _set_enabled(widget, enabled: bool):
  try:
    widget.setEnabled(bool(enabled))
  except Exception:
    try: widget.enabled = bool(enabled)
    except Exception: pass


def _set_label(widget, text):
  try:
    widget.setText(str(text))
  except Exception:
    try: widget.text = str(text)
    except Exception: pass


def _is_port_open(host, port, timeout=0.25):
  try:
    with socket.create_connection((host, int(port)), timeout=timeout):
      return True
  except Exception:
    return False


def _pids_listening_on_port(port):
  """Return PIDs of processes currently LISTENing on TCP `port`.

  Cross-platform best-effort:
    - macOS / Linux: parse `lsof -nP -iTCP:<port> -sTCP:LISTEN -t`
      (lsof is part of base macOS; on Linux it is almost always installed,
       and we fall back to `ss`/`fuser` if not).
    - Windows: parse `netstat -ano -p TCP` and match the local port.
  Returns [] on any failure (caller treats as 'nothing to kill').
  """
  port = int(port)
  pids = set()
  try:
    if platform.system() == "Windows":
      out = subprocess.check_output(["netstat", "-ano", "-p", "TCP"],
                                    stderr=subprocess.DEVNULL, text=True)
      for line in out.splitlines():
        parts = line.split()
        # cols: Proto  Local Address  Foreign Address  State  PID
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
          local = parts[1]
          if local.endswith(f":{port}"):
            try: pids.add(int(parts[4]))
            except Exception: pass
      return list(pids)

    # POSIX: prefer lsof (gives PIDs directly)
    if shutil.which("lsof"):
      out = subprocess.check_output(
        ["lsof", "-nP", "-iTCP:%d" % port, "-sTCP:LISTEN", "-t"],
        stderr=subprocess.DEVNULL, text=True)
      for tok in out.split():
        try: pids.add(int(tok))
        except Exception: pass
      return list(pids)

    # Fallback: ss (Linux) or fuser (Linux)
    if shutil.which("ss"):
      out = subprocess.check_output(
        ["ss", "-Hltnp", "sport", "=", ":%d" % port],
        stderr=subprocess.DEVNULL, text=True)
      import re as _re
      for m in _re.finditer(r"pid=(\d+)", out):
        try: pids.add(int(m.group(1)))
        except Exception: pass
      return list(pids)

    if shutil.which("fuser"):
      out = subprocess.check_output(["fuser", "-n", "tcp", str(port)],
                                    stderr=subprocess.DEVNULL, text=True)
      for tok in out.split():
        try: pids.add(int(tok))
        except Exception: pass
      return list(pids)
  except Exception:
    pass
  return list(pids)


def _terminate_pid(pid, force=False):
  """Cross-platform process termination by PID.

  Windows:  taskkill (graceful when force=False uses no /F; force=True adds /F).
            os.kill on Windows would map SIGTERM -> TerminateProcess unconditionally
            and SIGKILL is not defined at all, so we shell out to taskkill instead.
  POSIX:    SIGTERM, then SIGKILL when force=True.
  Returns True if the OS accepted the request (does not guarantee the process is gone).
  """
  pid = int(pid)
  try:
    if platform.system() == "Windows":
      args = ["taskkill", "/PID", str(pid)]
      if force: args.insert(1, "/F")
      subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
      return True
    sig = signal.SIGKILL if force else signal.SIGTERM
    os.kill(pid, sig)
    return True
  except Exception:
    return False


def _convert_numpy_to_vtk_points(A):
  """A: (p,3) float -> vtkPoints."""
  p, c = A.shape
  pts = vtk.vtkPoints()
  for i in range(p):
    pts.InsertNextPoint(float(A[i, 0]), float(A[i, 1]), float(A[i, 2]))
  return pts


def _expanded_bounds(node, paddingFactor=0.1):
  """Return node RAS bounds with symmetric padding."""
  b = [0.0] * 6
  node.GetRASBounds(b)
  xr = b[1] - b[0]
  yr = b[3] - b[2]
  zr = b[5] - b[4]
  b[0] -= xr * paddingFactor; b[1] += xr * paddingFactor
  b[2] -= yr * paddingFactor; b[3] += yr * paddingFactor
  b[4] -= zr * paddingFactor; b[5] += zr * paddingFactor
  return b


def _view_node_by_name(name: str):
  try:
    return slicer.mrmlScene.GetFirstNodeByName(name)
  except Exception:
    return None


# ------------------------- Slider controller (local) --------------------------

class _PCSliderController:
  """
  Minimal copy of your slider<->spinbox<->combobox linker to avoid circular imports.
  API: setRange, setValue, sliderValue, comboBoxIndex, populateComboBox
  """
  def __init__(self, comboBox, slider, spinBox,
               dynamic_min=-1.0, dynamic_max=1.0,
               onSliderChanged=None, onComboBoxChanged=None):
    self.comboBox, self.slider, self.spinBox = comboBox, slider, spinBox
    self.dynamic_min, self.dynamic_max = float(dynamic_min), float(dynamic_max)

    self.slider.setMinimum(-100); self.slider.setMaximum(100)
    try: self.spinBox.setDecimals(3)
    except Exception: pass
    self.spinBox.setMinimum(self.dynamic_min); self.spinBox.setMaximum(self.dynamic_max)
    try: self.spinBox.setSingleStep(0.01)
    except Exception: pass

    self.slider.valueChanged.connect(self._updateSpinFromSlider)
    self.spinBox.valueChanged.connect(self._updateSliderFromSpin)

    if onSliderChanged: self.slider.valueChanged.connect(onSliderChanged)
    if onComboBoxChanged: self.comboBox.currentIndexChanged.connect(onComboBoxChanged)

  def setRange(self, a, b):
    self.dynamic_min, self.dynamic_max = float(a), float(b)
    self.spinBox.blockSignals(True)
    self.spinBox.setMinimum(self.dynamic_min); self.spinBox.setMaximum(self.dynamic_max)
    self.spinBox.blockSignals(False)
    s0 = self._map_dynamic_to_slider(0.0)
    s0 = max(min(s0, self.slider.maximum), self.slider.minimum)
    self.spinBox.blockSignals(True); self.slider.blockSignals(True)
    try:
      self.spinBox.setValue(0.0); self.slider.setValue(s0)
    finally:
      self.slider.blockSignals(False); self.spinBox.blockSignals(False)

  def setValue(self, dynamic_value):
    self.slider.setValue(self._map_dynamic_to_slider(float(dynamic_value)))

  def sliderValue(self):
    try: return float(self.spinBox.value())
    except TypeError: return float(self.spinBox.value)

  def comboBoxIndex(self):
    try: return int(self.comboBox.currentIndex())
    except TypeError: return int(self.comboBox.currentIndex)

  def populateComboBox(self, items):
    self.comboBox.clear()
    for it in items: self.comboBox.addItem(str(it))

  # mapping
  def _map_slider_to_dynamic(self, s):
    t = (float(s) + 100.0) / 200.0
    val = self.dynamic_min + t * (self.dynamic_max - self.dynamic_min)
    return 0.0 if abs(val) < 1e-12 else val

  def _map_dynamic_to_slider(self, v):
    if self.dynamic_max == self.dynamic_min: return 0
    t = (float(v) - self.dynamic_min) / (self.dynamic_max - self.dynamic_min)
    return int(round(t * 200.0 - 100.0))

  def _updateSpinFromSlider(self, s):
    val = self._map_slider_to_dynamic(s)
    if int(s) == 0 or abs(val) < 1e-6: val = 0.0
    self.spinBox.blockSignals(True); self.spinBox.setValue(val); self.spinBox.blockSignals(False)

  def _updateSliderFromSpin(self, v):
    self.slider.blockSignals(True); self.slider.setValue(self._map_dynamic_to_slider(v)); self.slider.blockSignals(False)


# -------------------------- Main controller class -----------------------------

class GeomorphLR:
  """
  Wraps *all* methods previously named:
    - _lr_* (LR tab)
    - _r_*  (R/Rserve panel)
    - _coef_* (coefficient/TPS visualization)
  so the GPA module stays lean. This class reads/writes state on the parent
  widget (self.w) where appropriate (LM data, files, outputFolder, etc.).
  """

  # --------------------- construction & top-level attach ----------------------

  def __init__(self, parent_widget, node_collection=None):
    self.w = parent_widget                 # GPAWidget instance
    self.ui = parent_widget.ui             # UI shortcuts
    self.nodes = node_collection or _DummyCollection()

    # Rserve state
    self._rserve_proc = None
    self._rserve_started_by_us = False
    self._r_conn = None
    self._r_last_error = ""

    # LR state (formula/completer)
    self._lr_completer = None
    self._lr_completer_model = None
    self._lr_popup_connected = False

    # Coef viz state
    self._coef_enabled = False
    self._coef_vectors = []
    self._coef_names = []
    self._coef_current = -1

  def attach(self):
    """
    Wire up all LR/Rserve/Coef panels to the current UI.
    Safe no-op if the relevant widgets aren't present in the .ui file.
    """
    # LR tab
    self._lr_initTab()

    # R/Rserve panel
    self._r_initPanel()

    # Coefficient visualization panel
    self._coef_initUI()

  # ---------------------- LR: UI + validation + completer ---------------------

  def _lr_initTab(self):
    if not hasattr(self.ui, 'geomorphLRTab'):
      return  # LR tab not present in the .ui (safe no-op)

    # Map controls
    self._lr_formula = getattr(self.ui, 'lrFormulaEdit', None) or getattr(self.ui, 'lrFormulaLine', None)
    self._lr_status = self.ui.lrStatusLabel
    self._lr_validateBtn = self.ui.lrValidateButton
    self._lr_copyBtn = self.ui.lrCopyButton
    self._lr_resetBtn = self.ui.lrResetButton
    self._lr_possibleList = self.ui.lrPossibleCovariatesList

    # Fit widgets
    self._lr_fitBtn = self.ui.lrFitButton
    self._lr_fitStatus = self.ui.lrFitStatusLabel

    self._lr_summaryWidget = getattr(self.ui, 'lrSummaryText', None)
    if self._lr_summaryWidget:
      self._lr_setSummaryText("Run a model to see the geomorph::procD.lm summary here.")

    # If the .ui had a single-line widget, upgrade to multiline quietly
    self._lr_upgradeFormulaWidget()

    # Live validation on keystroke
    try:
      self._lr_formula.textChanged.connect(lambda: self._lr_onFormulaEdited())
    except Exception:
      pass

    # Buttons
    self._lr_validateBtn.clicked.connect(lambda: self._lr_onFormulaEdited(force=True))
    self._lr_copyBtn.clicked.connect(self._lr_onCopyClicked)
    self._lr_resetBtn.clicked.connect(self._lr_onResetClicked)
    self._lr_fitBtn.clicked.connect(self._lr_onFitInRClicked)

    # Defaults
    _set_enabled(self._lr_copyBtn, False)
    self._lr_setStatus("Waiting for input…", ok=None)
    _set_text(self._lr_formula, "Coords ~ Size")
    _set_enabled(self._lr_fitBtn, False)
    _set_label(self._lr_fitStatus, "Not ready")

    # Whitelist, completer, first validation
    self.refreshFromCovariates()
    self.refreshFitButton()

  def _lr_setStatus(self, msg, ok=None):
    _set_label(self._lr_status, msg)
    css_ok = "QLineEdit, QPlainTextEdit { border: 2px solid #2e7d32; border-radius: 3px; }"
    css_bad = "QLineEdit, QPlainTextEdit { border: 2px solid #c62828; border-radius: 3px; }"
    if ok is True:
      try: self._lr_formula.setStyleSheet(css_ok)
      except Exception: pass
      _set_enabled(self._lr_copyBtn, True)
    elif ok is False:
      try: self._lr_formula.setStyleSheet(css_bad)
      except Exception: pass
      _set_enabled(self._lr_copyBtn, False)
    else:
      try: self._lr_formula.setStyleSheet("")
      except Exception: pass
      _set_enabled(self._lr_copyBtn, False)

  def _lr_onResetClicked(self):
    try: self._lr_formula.blockSignals(True)
    except Exception: pass
    _set_text(self._lr_formula, "Coords ~ Size")
    try: self._lr_formula.blockSignals(False)
    except Exception: pass
    self._lr_onFormulaEdited()

  def _lr_onCopyClicked(self):
    qt.QApplication.clipboard().setText(self._lr_getFormulaText())

  def _lr_getCovariateNames(self):
    names = []
    ftn = getattr(self.w, 'factorTableNode', None)
    if not ftn:
      return names
    try:
      table = ftn.GetTable()
      ncols = ftn.GetNumberOfColumns()
      for c in range(1, ncols):
        nm = str(table.GetColumnName(c)).strip()
        if nm:
          names.append(nm)
    except Exception:
      pass
    return names

  def _lr_computeWhitelist(self):
    covs = self._lr_getCovariateNames()
    return ["Size"] + covs

  def _lr_applyCompleter(self):
    # dispose prior
    try:
      if self._lr_completer is not None:
        self._lr_completer.setParent(None)
        self._lr_completer.deleteLater()
    except Exception: pass
    self._lr_completer = None; self._lr_completer_model = None

    model = qt.QStringListModel(self._lr_formula)  # parent so it lives
    comp = qt.QCompleter(model, self._lr_formula)
    comp.setCaseSensitivity(qt.Qt.CaseSensitive)
    try: comp.setCompletionMode(qt.QCompleter.PopupCompletion)
    except Exception: pass

    self._lr_completer_model = model
    self._lr_completer = comp
    comp.setWidget(self._lr_formula)

    try:
      comp.activated[str].connect(self._lr_insertCompletion)
    except Exception:
      comp.activated.connect(lambda s: self._lr_insertCompletion(str(s)))

    if not self._lr_popup_connected:
      try:
        self._lr_formula.textChanged.connect(self._lr_completerMaybePopup)
        self._lr_popup_connected = True
      except Exception:
        pass

    self._lr_updateCompleterModel()

  def refreshFromCovariates(self):
    """Public wrapper (used by GPAWidget): rebuild list + completer + revalidate."""
    if not hasattr(self.ui, 'geomorphLRTab'):
      return
    mains = self._lr_computeWhitelist()
    self._lr_possibleList.clear()
    for nm in mains:
      self._lr_possibleList.addItem(nm)
    self._lr_applyCompleter()
    self._lr_onFormulaEdited()

  # --- formula parsing/validation helpers (patsy-based) ---

  def _lr_extract_term_names(self, patsy_term):
    names = []
    for fac in getattr(patsy_term, 'factors', []):
      nm = getattr(fac, 'code', None)
      if nm is None:
        nm = getattr(fac, 'name', None)
        if callable(nm):
          try: nm = nm()
          except Exception: nm = None
      if nm is None:
        nm = str(fac)
        if "EvalFactor(" in nm and "'" in nm:
          try: nm = nm.split("'", 2)[1]
          except Exception: pass
      names.append(str(nm).strip())
    return names

  def _lr_allowed_function_names(self):
    return {"log","log10","log1p","exp","sqrt","I","C","scale","center","bs","cr","poly"}

  def _lr_factor_base_vars(self, factor_str, mains_allowed):
    import re
    s = str(factor_str).strip()
    if s in mains_allowed:
      return {s}
    func_call = re.match(r'\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\((.*)\)\s*$', s)
    if func_call:
      func_name = func_call.group(1).split('.')[-1]
      inner = func_call.group(2)
      if func_name in self._lr_allowed_function_names():
        ids = set(re.findall(r'[A-Za-z_]\w*', inner))
        ids = {tok for tok in ids if tok in mains_allowed}
        if ids:
          return ids
    ids = set(re.findall(r'[A-Za-z_]\w*', s))
    ids = {tok for tok in ids if tok in mains_allowed}
    return ids

  def _lr_is_pairwise_term(self, names): return len(names) == 2

  def _lr_validateFormula(self, formula):
    # ensure patsy
    try:
      import patsy  # noqa: F401
    except Exception:
      try:
        progress = slicer.util.createProgressDialog(windowTitle="Installing...",
                                                    labelText="Installing patsy (formula parser)...",
                                                    maximum=0)
        slicer.app.processEvents()
        slicer.util.pip_install(["patsy"])
        progress.close()
        import patsy  # noqa: F401
      except Exception:
        try: progress.close()
        except Exception: pass
        return (False, "patsy is not available and could not be installed.")

    import patsy
    txt = (formula or "").strip()
    if not txt: return (False, "Enter a formula, e.g., Coords ~ Size + Sex.")
    if "~" not in txt: return (False, "Formula must contain '~'. Example: Coords ~ Size + Sex.")

    try:
      desc = patsy.ModelDesc.from_formula(txt)
    except Exception as e:
      return (False, f"Syntax error: {e}")

    # LHS checks
    lhs_terms = getattr(desc, "lhs_termlist", [])
    if len(lhs_terms) != 1:
      return (False, "Left-hand side must be a single variable: 'Coords'.")
    lhs_names = self._lr_extract_term_names(lhs_terms[0])
    if len(lhs_names) != 1 or lhs_names[0] not in ["Coords","Shape","SHAPE","shape"]:
      return (False, "LHS should be 'Coords'. If you used 'Shape', it will be treated as an alias.")

    mains_allowed = set(self._lr_computeWhitelist())
    # RHS terms
    for term in getattr(desc, "rhs_termlist", []):
      names = self._lr_extract_term_names(term)
      if len(names) == 0:  # intercept-only
        continue
      if len(names) == 1:  # main effect
        fac = names[0]
        bases = self._lr_factor_base_vars(fac, mains_allowed)
        if not bases:
          return (False, f"Unknown variable or unsupported transform: '{fac}'.")
        if len(bases) > 1:
          return (False, f"Ambiguous transformed main effect '{fac}'. Use one variable or split the term.")
        continue
      # interaction (pairwise only)
      if not self._lr_is_pairwise_term(names):
        return (False, "Only pairwise interactions (A:B) are allowed.")
      left_bases = self._lr_factor_base_vars(names[0], mains_allowed)
      right_bases = self._lr_factor_base_vars(names[1], mains_allowed)
      if not left_bases:  return (False, f"Unknown variable on left of interaction: '{names[0]}'.")
      if not right_bases: return (False, f"Unknown variable on right of interaction: '{names[1]}'.")
      if len(left_bases) > 1 or len(right_bases) > 1:
        return (False, f"Ambiguous transformed interaction '{':'.join(names)}'. Use one base variable per side.")

    return (True, "OK")

  def _lr_onFormulaEdited(self, force=False):
    txt = self._lr_getFormulaText()
    ok, msg = self._lr_validateFormula(txt)
    self._lr_setStatus(msg, ok=ok)
    self.refreshFitButton()

  def _lr_upgradeFormulaWidget(self):
    # If single-line exists, replace with a multi-line editor in the same grid cell
    if hasattr(self.ui, 'lrFormulaEdit'):
      self._lr_formula = self.ui.lrFormulaEdit
      return
    if not (hasattr(self.ui, 'lrFormulaLine') and hasattr(self.ui, 'lrFormulaGrid')):
      return
    edit = qt.QPlainTextEdit()
    edit.setObjectName('lrFormulaEdit')
    edit.setMinimumHeight(72); edit.setMaximumHeight(120)
    edit.setSizePolicy(qt.QSizePolicy.Policy.Expanding, qt.QSizePolicy.Policy.Fixed)
    try: edit.setPlaceholderText("Coords ~ Size + Sex + Species")
    except Exception: pass
    grid = self.ui.lrFormulaGrid
    old = self.ui.lrFormulaLine
    try: grid.removeWidget(old)
    except Exception: pass
    old.deleteLater()
    grid.addWidget(edit, 0, 1, 1, 1)
    self.ui.lrFormulaEdit = edit
    self._lr_formula = edit
    edit.textChanged.connect(lambda: self._lr_onFormulaEdited())
    try:
      f = edit.font; f.setFamily("Menlo"); edit.setFont(f)
    except Exception: pass

  def _lr_getFormulaText(self): return _safe_text(self._lr_formula)
  def _lr_setFormulaText(self, s): _set_text(self._lr_formula, s)

  def _lr_completerMaybePopup(self):
    comp = self._lr_completer
    if comp is None: return
    self._lr_updateCompleterModel()

    prefix = self._lr_currentTokenPrefix()
    try: comp.setCompletionPrefix(prefix)
    except Exception: return

    if not prefix:
      try: comp.popup().hide()
      except Exception: pass
      return

    try:
      r = self._lr_formula.cursorRect(self._lr_formula.textCursor())
    except Exception:
      try: r = self._lr_formula.cursorRect()
      except Exception: r = qt.QRect(0,0,1,1)

    try:
      top_left = self._lr_formula.viewport().mapTo(self._lr_formula, r.bottomLeft())
      r = qt.QRect(top_left, qt.QSize(max(280, r.width()), max(22, r.height())))
    except Exception:
      r = qt.QRect(0, 0, 280, 22)
    comp.complete(r)

  def _lr_currentTokenPrefix(self):
    import re
    text = self._lr_getFormulaText()
    try:
      cursor = self._lr_formula.textCursor(); pos = cursor.position()
      left = text[:pos]
    except Exception:
      left = text
    token = re.split(r'[\s\+\:\~\*\(\)]+', left)[-1]
    return token or ""

  def _lr_insertCompletion(self, completion: str):
    try:
      cursor = self._lr_formula.textCursor()
      prefix = self._lr_currentTokenPrefix()
      if prefix:
        cursor.movePosition(qt.QTextCursor.Left, qt.QTextCursor.KeepAnchor, len(prefix))
      cursor.insertText(completion)
      self._lr_formula.setTextCursor(cursor)
    except Exception:
      try: self._lr_formula.insertPlainText(completion)
      except Exception: pass

  def _lr_contextBeforePrefix(self):
    import re
    text = self._lr_getFormulaText()
    try:
      cursor = self._lr_formula.textCursor(); pos = cursor.position()
      left = text[:pos]
    except Exception:
      left = text
    token = re.split(r'[\s\+\:\~\*\(\)]+', left)[-1]
    before = left[:-len(token)] if token else left
    return before[-1:] if before else ''

  def _lr_updateCompleterModel(self):
    mains = self._lr_computeWhitelist()
    ops = ["~", "+", ":", "-1"]
    func_tokens = [f + "(" for f in sorted(self._lr_allowed_function_names())]
    context_char = self._lr_contextBeforePrefix()
    if context_char in (":", "*", "+", "~", "(") or self._lr_currentTokenPrefix() == "":
      candidates = ops + func_tokens + mains
    else:
      candidates = ops + mains
    if self._lr_completer_model is not None:
      self._lr_completer_model.setStringList(candidates)

  # ----------------------------- R / Rserve panel -----------------------------

  def _r_initPanel(self):
    """Wire the R/Rserve controls (no geomorph/RRPP UI checks)."""
    if not hasattr(self.ui, "rserveGroup"):
      return

    try:
      self.ui.rPortSpin.setMinimum(1024)
      self.ui.rPortSpin.setMaximum(65535)
      if int(self.ui.rPortSpin.value) == 0:
        self.ui.rPortSpin.setValue(6311)
    except Exception:
      pass

    self.ui.rDetectButton.clicked.connect(self._r_onDetectR)
    self.ui.rLaunchButton.clicked.connect(self._r_onLaunchClicked)
    self.ui.rShutdownButton.clicked.connect(self._r_onShutdownClicked)
    self.ui.rConnectButton.clicked.connect(self._r_onConnectClicked)
    self.ui.rDisconnectButton.clicked.connect(self._r_onDisconnectClicked)
    self.ui.rRefreshButton.clicked.connect(self._r_refreshRStatus)

    # Initial status
    self._r_onDetectR()
    self._refreshButtons()
    self._refreshStatusLabels()

  def _r_onDetectR(self):
    """Try to auto-locate Rscript and update Rscript label."""
    path = self._r_find_rscript()
    if path:
      try:
        self.ui.rscriptPath.setCurrentPath(path)
      except Exception:
        try:
          self.ui.rscriptPath.currentPath = path
        except Exception:
          pass
      _set_label(self.ui.rExeStatusLabel, f"Found: {path}")
    else:
      _set_label(self.ui.rExeStatusLabel, "Not found on PATH/R_HOME; set path manually.")
    self._refreshStatusLabels()
    self._refreshButtons()

  def _r_onLaunchClicked(self):
    """Launch Rserve robustly across platforms.
    - Windows: wait=TRUE so the port is ready before return.
    - macOS/Linux: let Rserve daemonize (default), keep foreground clean.
    """
    port = int(self.ui.rPortSpin.value)
    allow_remote = bool(getattr(self.ui.rAllowRemote, "isChecked", lambda: False)())
    rscript = self._r_getRscriptFromUI()
    if not rscript or not os.path.exists(rscript):
        _set_label(self.ui.rRserveStatusLabel, "Cannot launch: Rscript path invalid.")
        return

    # Common args (UTF-8 helps on Windows and is harmless elsewhere)
    common_args = f"--RS-port {port} --no-save --RS-encoding utf8"
    if allow_remote:
        common_args += " --RS-enable-remote"

    if platform.system() == "Windows":
        # Foreground (no daemon) so port is reliably open before return
        code = (
            "Sys.setenv(RGL_USE_NULL='TRUE'); "
            "options(rgl.useNULL=TRUE); "
            f"Rserve::Rserve(debug=TRUE, wait=TRUE, args='{common_args}')"
        )
    else:
        # Unix: let Rserve daemonize as usual (wait=FALSE / default)
        # (Do not pass wait=TRUE to keep the old behavior.)
        code = (
            "Sys.setenv(RGL_USE_NULL='TRUE'); "
            "options(rgl.useNULL=TRUE); "
            f"Rserve::Rserve(debug=FALSE, args='{common_args}')"
        )

    cmd = [rscript, "-e", code]

    # Pin BLAS / OpenMP thread counts to 1 for the Rserve child.
    # Rationale: macOS Accelerate/vecLib (and several OpenBLAS builds on Linux)
    # crash the R process with a segfault / "EndOfData" when an Rserve worker
    # session calls into multi-threaded BLAS routines from packages like
    # RRPP::lm.rrpp / geomorph::procD.lm with response widths >~ 600 columns.
    # These env vars must be set BEFORE R loads its BLAS, hence Popen(env=...).
    # Cost is negligible: GPA's R workload is dominated by R-level loops, not
    # large dense matmul, and this trade is universally safer than the crash.
    rserve_env = os.environ.copy()
    rserve_env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    rserve_env.setdefault("OPENBLAS_NUM_THREADS", "1")
    rserve_env.setdefault("OMP_NUM_THREADS", "1")
    rserve_env.setdefault("MKL_NUM_THREADS", "1")
    rserve_env.setdefault("BLIS_NUM_THREADS", "1")

    try:
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if platform.system() == "Windows" else 0
        self._rserve_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            env=rserve_env,
        )
        self._rserve_started_by_us = True

        # Poll for the socket to come up (Windows needs this; harmless elsewhere)
        timeout = 20.0 if platform.system() == "Windows" else 10.0
        t0 = time.time()
        while time.time() - t0 < timeout:
            if _is_port_open("127.0.0.1", port) or _is_port_open("localhost", port):
                _set_label(self.ui.rRserveStatusLabel, f"Rserve is running on port {port}.")
                break
            time.sleep(0.25)
        else:
            _set_label(self.ui.rRserveStatusLabel, "Launch attempted, but port not open yet.")
    except Exception as e:
        _set_label(self.ui.rRserveStatusLabel, f"Launch failed: {e}")
    finally:
        self._refreshButtons()


  def _r_onShutdownClicked(self):
    port = int(self.ui.rPortSpin.value)

    # Always close our own pyRserve worker session first; the master daemon
    # outlives it and that's what we actually need to stop.
    self._safeCloseRConn()

    # 1. Best-effort: ask the daemon nicely via a fresh shutdown control session.
    try:
      pyR = self._r_ensure_pyRserve()
      if pyR:
        try:
          conn = pyR.connect(host="127.0.0.1", port=port, timeout=2.0)
          try:
            if hasattr(conn, "shutdown"): conn.shutdown()
          finally:
            try: conn.close()
            except Exception: pass
        except Exception: pass
    except Exception: pass

    # 2. Find every process actually listening on the port and terminate it.
    #    The Popen handle we kept is just the launcher Rscript, which exited
    #    immediately after Rserve daemonized — terminating it is a no-op.
    pids = _pids_listening_on_port(port)
    for pid in pids:
      _terminate_pid(pid, force=False)

    # 3. Wait briefly for the port to actually free; force-kill stragglers.
    deadline = time.time() + 3.0
    while time.time() < deadline and _is_port_open("127.0.0.1", port):
      time.sleep(0.1)
    if _is_port_open("127.0.0.1", port):
      for pid in _pids_listening_on_port(port):
        _terminate_pid(pid, force=True)
      time.sleep(0.3)

    # Reap our launcher Popen if it's still around (it usually isn't).
    if self._rserve_proc is not None:
      try: self._rserve_proc.poll()
      except Exception: pass
    self._rserve_proc = None
    self._rserve_started_by_us = False

    if _is_port_open("127.0.0.1", port):
      _set_label(self.ui.rRserveStatusLabel,
                 f"Shutdown failed: port {port} still in use.")
    else:
      _set_label(self.ui.rRserveStatusLabel, "Rserve shut down.")
    self._refreshButtons(); self._refreshStatusLabels()

  def _r_onConnectClicked(self):
    """Open a pyRserve connection (no extra geomorph UI checks)."""
    _set_label(self.ui.rConnStatusLabel, "Connecting…")
    pyR = self._r_ensure_pyRserve()
    if not pyR:
      _set_label(self.ui.rConnStatusLabel, f"pyRserve not available. {self._r_last_error}")
      self._refreshButtons()
      self._refreshStatusLabels()
      return

    port = int(self.ui.rPortSpin.value)
    last_exc = None
    for host in ("127.0.0.1", "localhost", "::1"):
      try:
        self._safeCloseRConn()
        self._r_conn = pyR.connect(host, port) if hasattr(pyR, "connect") else pyR.rconnect(host, port)
        try:
          _ = self._r_conn.eval("1+1")
        except Exception:
          pass
        _set_label(self.ui.rConnStatusLabel, f"Connected to {host}:{port}")
        self._refreshButtons()
        self._refreshStatusLabels()
        return
      except Exception as e:
        last_exc = e

    self._r_conn = None
    _set_label(self.ui.rConnStatusLabel, f"Connect failed on port {port}: {last_exc}")
    self._log(f"[Rserve] Connect failed on {port}: {last_exc}")
    self._refreshButtons()
    self._refreshStatusLabels()


  def _r_onDisconnectClicked(self):
    self._safeCloseRConn()
    _set_label(self.ui.rConnStatusLabel, "Disconnected.")
    self._refreshButtons(); self._refreshStatusLabels()

  def _r_refreshRStatus(self):
    self._refreshStatusLabels(); self._refreshButtons()

  def _refreshStatusLabels(self):
    # Rscript
    rscript = self._r_getRscriptFromUI()
    if rscript and os.path.exists(rscript):
      _set_label(self.ui.rExeStatusLabel, f"Found: {rscript}")
    else:
      _set_label(self.ui.rExeStatusLabel, "Not found; set path and 'Auto-detect' if needed.")

    # Rserve
    port = int(self.ui.rPortSpin.value)
    running = _is_port_open("127.0.0.1", port)
    _set_label(self.ui.rRserveStatusLabel, f"Listening on {port}" if running else "Not listening")

    # Connection
    if self._r_conn:
      try:
        _ = self._r_conn.eval("1+1")
        _set_label(self.ui.rConnStatusLabel, "Connected")
      except Exception:
        _set_label(self.ui.rConnStatusLabel, "Connection lost")
        self._safeCloseRConn()
    else:
      _set_label(self.ui.rConnStatusLabel, "Not connected")

    # Fit gating
    self.refreshFitButton()

  def _refreshButtons(self):
    """Enable/disable Rserve buttons based on current state."""
    port = int(self.ui.rPortSpin.value)
    rscript_ok = bool(self._r_getRscriptFromUI() and os.path.exists(self._r_getRscriptFromUI()))
    rserve_running = _is_port_open("127.0.0.1", port)
    connected = bool(self._r_conn)

    _set_enabled(self.ui.rLaunchButton,   rscript_ok and not rserve_running)
    _set_enabled(self.ui.rShutdownButton, rserve_running)
    _set_enabled(self.ui.rConnectButton,  rserve_running and not connected)
    _set_enabled(self.ui.rDisconnectButton, connected)
    # NOTE: rCheckGeomorphButton is removed from the UI; nothing to toggle here.

  def _r_getRscriptFromUI(self):
    p = None
    try: p = self.ui.rscriptPath.currentPath
    except Exception:
      try: p = str(self.ui.rscriptPath.text())
      except Exception: p = None
    if not p: return None
    p = os.path.expanduser(str(p).strip())
    return os.path.realpath(p)

  def _r_find_rscript(self):
    p = shutil.which("Rscript") if 'shutil' in globals() else None
    if p: return p
    try:
      import shutil as _sh
      p = _sh.which("Rscript") or _sh.which("Rscript.exe")
      if p: return p
    except Exception:
      pass

    r_home = os.environ.get("R_HOME", "")
    if r_home:
      for c in [os.path.join(r_home,"bin","Rscript"),
                os.path.join(r_home,"bin","Rscript.exe"),
                os.path.join(r_home,"bin","x64","Rscript.exe")]:
        if os.path.exists(c): return c

    if platform.system() == "Windows":
      roots = [os.environ.get("ProgramFiles",""), os.environ.get("ProgramFiles(x86)","")]
      for root in roots:
        if not root: continue
        try:
          for ver in os.listdir(os.path.join(root, "R")):
            c1 = os.path.join(root, "R", ver, "bin", "Rscript.exe")
            c2 = os.path.join(root, "R", ver, "bin", "x64", "Rscript.exe")
            if os.path.exists(c2): return c2
            if os.path.exists(c1): return c1
        except Exception: pass
    else:
      for c in ("/opt/homebrew/bin/Rscript", "/usr/local/bin/Rscript", "/usr/bin/Rscript"):
        if os.path.exists(c): return c
    return None

  def _safeCloseRConn(self):
    if self._r_conn is not None:
      try: self._r_conn.close()
      except Exception: pass
    self._r_conn = None

  def _r_ensure_pyRserve(self):
    # NumPy 2.0 compat shim before importing pyRserve
    try:
      import numpy as _np
      from types import SimpleNamespace as _SS
      if not hasattr(_np, "string_"):  _np.string_ = _np.bytes_
      if not hasattr(_np, "unicode_"): _np.unicode_ = str
      if not hasattr(_np, "int"):      _np.int = int
      if not hasattr(_np, "bool"):     _np.bool = bool
      if not hasattr(_np, "float"):    _np.float = float
      if not hasattr(_np, "object"):   _np.object = object
      if not hasattr(_np, "compat"): _np.compat = _SS(long=int)
      elif not hasattr(_np.compat, "long"): _np.compat.long = int
    except Exception:
      pass

    try:
      import sys
      if "pyRserve" in sys.modules:
        import pyRserve as _pyRserve
        return _pyRserve
    except Exception: pass

    try:
      import pyRserve as _pyRserve
      return _pyRserve
    except Exception as e:
      try:
        progress = slicer.util.createProgressDialog(
          windowTitle="Installing...", labelText="Installing pyRserve...", maximum=0)
        slicer.app.processEvents()
        slicer.util.pip_install(["pyRserve"])
        progress.close()
        import pyRserve as _pyRserve
        return _pyRserve
      except Exception as ee:
        try: progress.close()
        except Exception: pass
        self._r_last_error = str(ee)
        return None

  # ------------------------ Fit gating & covariate plumbing -------------------

  def _lr_canFit(self) -> bool:
    try:
      fml = self._lr_getFormulaText()
      ok,_ = self._lr_validateFormula(fml)
    except Exception:
      ok = False
    if not (ok and bool(self._r_conn)):
      return False
    # If we already produced a fit for this exact formula, don't let the
    # user re-run it just to re-arm the LR visualization. They should switch
    # back via the warp-source radio (PCA / Geomorph LR) instead. Editing
    # the formula text re-arms the button automatically.
    try:
      last = getattr(self, "_lr_last_fit", None)
      if last and str(last.get("formula", "")) == str(fml):
        return False
    except Exception:
      pass
    return True

  def refreshFitButton(self):
    can = self._lr_canFit()
    _set_enabled(self._lr_fitBtn, bool(can))
    if can:
      _set_label(self._lr_fitStatus, "Ready")
    else:
      # Distinguish "already fit" from "formula/connection not ready".
      try:
        fml = self._lr_getFormulaText()
        ok,_ = self._lr_validateFormula(fml)
      except Exception:
        ok = False
      already = False
      try:
        last = getattr(self, "_lr_last_fit", None)
        already = bool(ok and self._r_conn and last
                       and str(last.get("formula", "")) == str(fml))
      except Exception:
        pass
      if already:
        _set_label(self._lr_fitStatus,
                   "Fit complete (edit formula or switch warp source to re-fit)")
      else:
        _set_label(self._lr_fitStatus, "Not ready")

  def _lr_findCovariatesPath(self) -> str:
    paths = []
    try:
      p = str(self.ui.selectCovariatesText.text)
      if p: paths.append(p)
    except Exception: pass
    try:
      p2 = os.path.join(self.w.outputFolder, "covariateTable.csv")
      paths.append(p2)
    except Exception: pass
    for p in paths:
      if p and os.path.isfile(p):
        return p
    return ""

  def _lr_get_base_variables_from_formula(self, formula: str):
    try:
      import patsy  # noqa: F401
    except Exception:
      return set()
    import patsy, re
    desc = patsy.ModelDesc.from_formula((formula or "").strip())
    mains_allowed = set(self._lr_computeWhitelist())
    bases = set()
    for term in getattr(desc, "rhs_termlist", []):
      names = self._lr_extract_term_names(term)
      if len(names) == 0: continue
      if len(names) == 1:
        bases |= self._lr_factor_base_vars(names[0], mains_allowed)
      elif self._lr_is_pairwise_term(names):
        bases |= self._lr_factor_base_vars(names[0], mains_allowed)
        bases |= self._lr_factor_base_vars(names[1], mains_allowed)
    drop = {"Coords","Shape","SHAPE","shape","Size","size"}
    return {b for b in bases if b not in drop}

  # -------------------------------- Fit in R ----------------------------------

  def _lr_onFitInRClicked(self):
    import numpy as _np
    # guards
    if not getattr(self.w, "LM", None):
      _set_label(self._lr_fitStatus, "No GPA data");
      return

    fml_raw = self._lr_getFormulaText()
    ok, msg = self._lr_validateFormula(fml_raw)
    if not ok:
      _set_label(self._lr_fitStatus, "Invalid formula")
      self._log(f"[LR] Invalid formula: {msg}")
      return

    # Show a progress dialog so the UI doesn't appear frozen during the fit
    # (procD.lm itself is fast; the post-fit TPS warp setup with many landmarks
    # is what tends to dominate wall-clock).
    pd = None
    try:
      pd = slicer.util.createProgressDialog(
        windowTitle="Fitting linear model",
        labelText=f"Fitting:  {fml_raw}\n(this may take a moment for high-density landmarks)",
        maximum=0,
      )
      pd.setCancelButton(None)
      pd.setModal(True); pd.show(); pd.raise_(); pd.repaint()
      for _ in range(5): slicer.app.processEvents()
    except Exception:
      pd = None

    # Stash the dialog so _lr_doFitInR / sub-steps can update its label without
    # plumbing it through every signature.
    self._lr_progress = pd

    import time as _time
    t_start = _time.perf_counter()
    try:
      self._lr_doFitInR(fml_raw)
    finally:
      self._log(f"[LR] total fit + post-fit: {_time.perf_counter() - t_start:.2f}s")
      self._lr_progress = None
      if pd is not None:
        try: pd.close(); pd.deleteLater()
        except Exception: pass

  def _lr_progressLabel(self, text):
    """Update the fit progress dialog's label, if visible. Safe to call any time."""
    pd = getattr(self, "_lr_progress", None)
    if pd is None:
      return
    try:
      pd.labelText = str(text)
      pd.repaint()
      slicer.app.processEvents()
    except Exception:
      pass

  def _lr_doFitInR(self, fml_raw):
    import numpy as _np
    import time as _time

    conn = self._r_conn
    if not conn:
      _set_label(self._lr_fitStatus, "Rserve not connected");
      return

    arr = _np.asarray(self.w.LM.lm)  # (p,3,n)
    if arr.ndim != 3 or arr.shape[1] != 3:
      _set_label(self._lr_fitStatus, "Bad landmark array")
      self._log(f"[LR] Unexpected LM.lm shape: {arr.shape}")
      return
    p, _, n = arr.shape

    coords_mat = arr.transpose(2, 0, 1).reshape(n, 3 * p, order="C")
    size_vec = _np.asarray(self.w.LM.centriodSize, dtype=float).reshape(-1)
    if size_vec.shape[0] != n:
      _set_label(self._lr_fitStatus, "Bad centroid size")
      self._log(f"[LR] centroid size length {size_vec.shape[0]} != specimens {n}")
      return

    files = list(self.w.files) if (
              hasattr(self.w, "files") and isinstance(self.w.files, (list, tuple)) and len(self.w.files) == n) \
      else [f"spec_{i + 1}" for i in range(n)]

    base_vars = self._lr_get_base_variables_from_formula(fml_raw)
    cov_df, cov_path = None, ""
    if base_vars:
      cov_path = self._lr_findCovariatesPath()
      if not cov_path:
        _set_label(self._lr_fitStatus, "Missing covariate table")
        self._log("[LR] No covariate CSV found; cannot satisfy formula variables.")
        return
      try:
        import pandas as pd
      except Exception:
        _set_label(self._lr_fitStatus, "pandas missing")
        self._log("[LR] pandas not available.")
        return
      try:
        cov_df = pd.read_csv(cov_path)
        if cov_df.shape[1] < 2:
          raise ValueError("Covariate CSV needs ID col + covariate columns.")
        cov_df = cov_df.set_index(cov_df.columns[0])
        ids = [os.path.splitext(os.path.basename(f))[0] for f in files]
        missing = [i for i in ids if i not in cov_df.index]
        if missing:
          raise ValueError(f"IDs missing in covariate table (first 10): {missing[:10]}")
        cov_df = cov_df.loc[ids]
      except Exception as e:
        _set_label(self._lr_fitStatus, "Covariate load error")
        self._log(f"[LR] Failed to read/align covariates: {e}")
        return

    step = self._r_step

    # --- PHASE: ship landmarks + size to R ---
    self._lr_progressLabel(f"Sending {n} specimens × {p} landmarks to R…")
    _tphase = _time.perf_counter()

    # Headless rgl
    if not step(conn, "Headless rgl",
                'options(rgl.useNULL=TRUE); Sys.setenv(RGL_USE_NULL="TRUE"); Sys.setenv(RGL_ALWAYS_SOFTWARE="TRUE")'):
      _set_label(self._lr_fitStatus, "R data error (rgl)");
      return

    # Require geomorph installed in Rserve
    ok_pkg, _ = self._r_try(
      'if (!"geomorph" %in% rownames(installed.packages())) stop("geomorph not installed in this Rserve")',
      "check geomorph")
    if not ok_pkg:
      _set_label(self._lr_fitStatus, "geomorph missing");
      return

    # Ship coords + size
    try:
      conn.r.coords = coords_mat;
      conn.r.size = size_vec
    except Exception as e:
      _set_label(self._lr_fitStatus, "R data error (send)")
      self._log(f"[LR] send coords/size: {repr(e)}")
      return

    if not step(conn, "Prepare coords", 'coords <- base::as.matrix(coords); storage.mode(coords) <- "double"'):
      _set_label(self._lr_fitStatus, "R data error (coords)");
      return
    if not step(conn, "arrayspecs", f'arr <- geomorph::arrayspecs(coords, p={p}, k=3)'):
      _set_label(self._lr_fitStatus, "R data error (arrayspecs)");
      return
    self._log(f"[LR/timing] ship + arrayspecs: {_time.perf_counter() - _tphase:.2f}s")

    # --- PHASE: predictors / covariates ---
    _tphase = _time.perf_counter()

    # predictors in .GlobalEnv
    added_vars = []
    if base_vars and cov_df is not None:
      for var in sorted(base_vars):
        if var not in cov_df.columns:
          _set_label(self._lr_fitStatus, "Missing covariate column")
          self._log(f"[LR] Column '{var}' not found in covariate CSV.");
          return
        series = cov_df[var]
        tmpname = f'.py_{var}'
        try:
          import pandas as pd
          s_num = pd.to_numeric(series, errors="raise").to_numpy().astype(float)  # type: ignore
          conn.r.__setattr__(tmpname, s_num)
          if not step(conn, f"Set {var} (numeric)", f'{var} <- base::as.numeric({tmpname})'):
            _set_label(self._lr_fitStatus, "R data error (covariate)");
            return
        except Exception:
          conn.r.__setattr__(tmpname, series.astype(str).tolist())
          if not step(conn, f"Set {var} (factor)",
                      f'{var} <- base::factor(base::as.character(base::unlist({tmpname})))'):
            _set_label(self._lr_fitStatus, "R data error (covariate)");
            return
        added_vars.append(var)

    pieces = ['Size=base::as.numeric(size)', 'Coords=arr']
    for var in added_vars: pieces.insert(1, f'{var}={var}')
    gdf_call = 'gdf <- geomorph::geomorph.data.frame(' + ', '.join(pieces) + ')'
    if not step(conn, "Build gdf", gdf_call):
      _set_label(self._lr_fitStatus, "R data error (gdf)");
      return
    self._log(f"[LR/timing] covariates + gdf: {_time.perf_counter() - _tphase:.2f}s")

    import re as _re
    fml = _re.sub(r'^\s*(Y|Coords|Shape|SHAPE|shape)\s*~', 'Coords ~', fml_raw.strip())
    try:
      conn.r.__setattr__('fml', fml)
    except Exception as e:
      _set_label(self._lr_fitStatus, "R data error (formula set)")
      self._log(f"[LR] set fml: {repr(e)}");
      return
    if not step(conn, "Build formula", 'mod <- stats::as.formula(fml)'):
      _set_label(self._lr_fitStatus, "Bad formula");
      return

    # --- PHASE: actual procD.lm fit ---
    self._lr_progressLabel(f"Running procD.lm:  {fml}")
    _tphase = _time.perf_counter()
    if not step(conn, "Fit procD.lm",
                'outlm <- geomorph::procD.lm(mod, data=gdf, SS.type="II")'):
      _set_label(self._lr_fitStatus, "Fit failed");
      return
    self._log(f"[LR/timing] procD.lm fit: {_time.perf_counter() - _tphase:.2f}s")

    # --- PHASE: pull coefficients back to Python ---
    self._lr_progressLabel(f"Pulling coefficients back from R…")
    _tphase = _time.perf_counter()
    if not step(conn, "Extract coefficients", 'coef_mat <- outlm$coefficients; coef_names <- base::rownames(coef_mat)'):
      _set_label(self._lr_fitStatus, "Extract error");
      return

    try:
      coef_mat = np.asarray(conn.eval('coef_mat'))
      coef_names = list(conn.eval('as.character(coef_names)'))
    except Exception as e:
      _set_label(self._lr_fitStatus, "Pull-back error")
      self._log(f"[LR] pull coef: {repr(e)}");
      return
    self._log(f"[LR/timing] pull coef_mat ({coef_mat.shape}): {_time.perf_counter() - _tphase:.2f}s")

    # Pull factor levels (so we can label categorical sliders by group name).
    # R returns a named list; ask for names + JSON-ish flat encoding to keep pyRserve happy.
    if not step(conn, "Summarize model", 'sumtxt <- paste(utils::capture.output(summary(outlm)), collapse="\\n")'):
      self._lr_setSummaryText("Failed to build summary(outlm).")
      summary_text = ""
    else:
      try:
        summary_text = str(conn.eval('sumtxt'))
      except Exception as e:
        summary_text = f"Could not read summary from R: {repr(e)}"
      self._lr_setSummaryText(summary_text)

    # --- PHASE: factor levels + covariate stats (categorical slider labels etc.) ---
    self._lr_progressLabel("Pulling factor levels & covariate stats…")
    _tphase = _time.perf_counter()
    factor_levels = {}
    try:
      conn.eval('factor_levels <- lapply(Filter(is.factor, as.list(gdf)), levels)')
      fl_names = self._py_to_str_list(conn.eval('as.character(names(factor_levels))'))
      for nm in fl_names:
        nm = str(nm)
        if not nm:
          continue
        try:
          lv = conn.eval(f'as.character(factor_levels[["{nm}"]])')
          factor_levels[nm] = self._py_to_str_list(lv)
        except Exception:
          pass
      self._log(f"[LR] factor levels: {factor_levels}")
    except Exception as e:
      self._log(f"[LR] could not pull factor levels: {e}")
    self._log(f"[LR/timing] factor levels: {_time.perf_counter() - _tphase:.2f}s")

    # ---- NEW: cache covariate ranges for numeric sliders ----
    cov_stats = {}
    def _add_numeric_stats(name, vals):
      vals = _np.asarray(vals, dtype=float)
      finite = vals[_np.isfinite(vals)]
      if finite.size == 0:
        return
      entry = {
        "is_numeric": True,
        "min": float(finite.min()),
        "max": float(finite.max()),
        "mean": float(finite.mean()),
      }
      # Geometric-mean center for log(x): only defined when x > 0 everywhere.
      pos = finite[finite > 0]
      if pos.size == finite.size and pos.size > 0:
        entry["log_mean"] = float(_np.mean(_np.log(pos)))
      # Quadratic-mean center for sqrt(x): need x >= 0 everywhere.
      nonneg = finite[finite >= 0]
      if nonneg.size == finite.size:
        entry["sqrt_mean"] = float(_np.mean(_np.sqrt(nonneg)))
      cov_stats[str(name)] = entry

    try:
      _add_numeric_stats("Size", size_vec)
      if cov_df is not None:
        import pandas as pd
        for col in cov_df.columns:
          series = cov_df[col]
          is_num = False
          try:
            is_num = bool(pd.api.types.is_numeric_dtype(series))
          except Exception:
            try:
              _ = pd.to_numeric(series, errors="raise")
              is_num = True
            except Exception:
              is_num = False
          if is_num:
            _add_numeric_stats(col, _np.asarray(series, dtype=float))
    except Exception:
      pass
    # ----------------------------------------------

    # cache for coefficient viz (+ covariate stats + factor levels)
    self._lr_last_fit = {
      "formula": fml,
      "coef_mat": coef_mat,
      "coef_names": coef_names,
      "n_specimens": n,
      "p_landmarks": p,
      "covariate_path": cov_path,
      "summary_text": summary_text,
      "covariate_stats": cov_stats,
      "factor_levels": factor_levels,
    }

    self._log(f"[LR] geomorph::procD.lm OK: coef_mat {coef_mat.shape}, terms={len(coef_names)}")
    _set_label(self._lr_fitStatus, "Fit complete")

    # --- PHASE: build coefficient warp infra (TPS source landmarks etc.) ---
    self._lr_progressLabel(f"Setting up coefficient warps for {p} landmarks…")
    try:
      _t0 = _time.perf_counter()
      self._coef_refreshFromFit()
      self._log(f"[LR/timing] _coef_refreshFromFit: {_time.perf_counter() - _t0:.2f}s")
    except Exception as e:
      self._log(f"[LR] _coef_refreshFromFit error: {repr(e)}")
    # Now that this formula has been fit, disable the Fit button until the
    # user edits the formula (refreshFitButton checks _lr_last_fit.formula).
    try:
      self.refreshFitButton()
    except Exception:
      pass

  def _r_try(self, code: str, tag: str = ""):
    conn = self._r_conn
    if not conn: return (False, "No Rserve connection")
    conn.r.__setattr__(".pycode", code)
    res = str(conn.eval(
      'tryCatch({ eval(parse(text=.pycode), envir=.GlobalEnv); "OK" }, '
      '         error=function(e) paste("ERR:", conditionMessage(e)))'
    )).strip()
    if tag and res != "OK":
      self._log(f"[LR] {tag}: {res}")
    return (res == "OK", res)

  def _r_step(self, conn, tag: str, code: str) -> bool:
    try:
      conn.r.__setattr__(".pycode", code)
      res = str(conn.eval(
        'tryCatch({ eval(parse(text=.pycode), envir=.GlobalEnv); "OK" }, '
        '         error=function(e) paste("ERR:", conditionMessage(e)))'
      )).strip()
      if res != "OK":
        self._log(f"[LR] {tag}: {res}")
        return False
      self._log(f"[LR] {tag}: OK")
      return True
    except Exception as e:
      self._log(f"[LR] {tag}: PYERR {repr(e)}")
      try: self._safeCloseRConn(); self._refreshStatusLabels()
      except Exception: pass
      return False

  # ---------------------- Coefficient visualization (TPS) ---------------------

  def _coef_initUI(self):
    if not hasattr(self.ui, "coefVisualizationParametersButton"):
      self._coef_enabled = False
      return

    self._coef_enabled = True
    self._coef_vectors = []
    self._coef_names = []
    self._coef_current = -1

    # Slider controller for NUMERIC coefficient warps (existing behavior)
    try:
      self.coefController = _PCSliderController(
        comboBox=self.ui.coefComboBox,
        slider=self.ui.coefSlider,
        spinBox=self.ui.coefSpinBox,
        dynamic_min=-1.0,
        dynamic_max=1.0,
        onSliderChanged=lambda _: self._coef_updateScaling(),
        onComboBoxChanged=lambda _: self._coef_onSelectCoefficient(),
      )
    except Exception:
      self.coefController = None

    # Magnification (shared for numeric mode)
    try:
      self.ui.coefUpdateMagnificationButton.clicked.connect(self._coef_setMagnification)
    except Exception:
      pass
    try:
      self.ui.coefMagnificationSpin.setDecimals(2)
      self.ui.coefMagnificationSpin.setMinimum(0.01)
      self.ui.coefMagnificationSpin.setMaximum(1_000_000.0)
      self.ui.coefMagnificationSpin.setSingleStep(10.0)
      self.ui.coefMagnificationSpin.setValue(1.0)
    except Exception:
      pass

    # Reuse "Init / Reset" button
    try:
      self.ui.coefResetButton.setText("Init / Reset Coefficient View")
      self.ui.coefResetButton.setToolTip(
        "Create LR warping infrastructure if needed, then reset the view to neutral (identity TPS)."
      )
      self.ui.coefResetButton.clicked.connect(self._coef_initOrResetClicked)
    except Exception:
      pass

    # Grid transform node (kept alive)
    self._ensureLRGridNode()
    if self.coefController:
      self.coefController.setRange(-1.0, 1.0)
      self.coefController.setValue(0.0)

  def _coef_refreshFromFit(self):
    if not self._coef_enabled:
      return
    last = getattr(self, "_lr_last_fit", None)
    if not last:
      self._coef_clearChoices()
      return

    # Re-entrance guard: while we are in this function, suppress the cascade
    # of slider/combobox callbacks that would otherwise re-run
    # _coef_applyTPS / _coef_set_slider_domain_for_current /
    # _coef_attachTargets several times for the same fit. We do all those
    # ourselves at the end of this function, exactly once.
    self._coef_in_refresh = True
    # Pause the 3D renderer for the entire post-fit setup so the 1000-fid
    # markup display only re-evaluates the TPS once at the end, instead of
    # re-rendering after every TPS / transform-parent change.
    _paused = False
    try:
      slicer.app.pauseRender()
      _paused = True
    except Exception:
      _paused = False
    try:
      self._coef_refreshFromFit_body(last)
    finally:
      self._coef_in_refresh = False
      if _paused:
        try: slicer.app.resumeRender()
        except Exception: pass

  def _coef_refreshFromFit_body(self, last):
    import numpy as _np
    coef_mat = _np.asarray(last.get("coef_mat", []))
    coef_names = list(last.get("coef_names", []))
    if coef_mat.ndim != 2 or len(coef_names) != coef_mat.shape[0]:
      self._coef_clearChoices()
      return

    self._coef_vectors = [_np.asarray(coef_mat[i, :]).reshape(-1).copy() for i in range(coef_mat.shape[0])]
    self._coef_names = [str(n) for n in coef_names]

    # Cache the intercept's predicted shape (p,3) as the WARP BASE.
    # All coefficient contributions are predicted shape DEVIATIONS from this point;
    # the intercept is the model's prediction at all-zero / reference predictors.
    self._coef_intercept_shape = None
    try:
      p = int(self.w.rawMeanLandmarks.shape[0]) if getattr(self.w, "rawMeanLandmarks", None) is not None else 0
      for i, nm in enumerate(self._coef_names):
        if nm.strip() == "(Intercept)" and p > 0 and self._coef_vectors[i].size == 3 * p:
          row = self._coef_vectors[i]
          base = _np.zeros((p, 3), dtype=float)
          base[:, 0] = row[0:p]
          base[:, 1] = row[p:2 * p]
          base[:, 2] = row[2 * p:3 * p]
          self._coef_intercept_shape = base
          break
    except Exception as e:
      self._log(f"[LR/COEF] intercept-shape capture failed: {e}")

    # Build the visible (combobox) index -> underlying coef index mapping.
    # The intercept is hidden from the slider UI: it is not a 'direction' you can
    # slide along, it is the absolute base shape.
    self._coef_visible_indices = [
      i for i, nm in enumerate(self._coef_names) if nm.strip() != "(Intercept)"
    ]

    # default to first visible coef (first non-intercept term)
    first_term = self._coef_visible_indices[0] if self._coef_visible_indices else 0
    self._coef_current = int(first_term)

    if self.coefController:
      visible_names = [self._coef_names[i] for i in self._coef_visible_indices]
      import time as _time
      _t0 = _time.perf_counter()
      self.coefController.populateComboBox(visible_names)
      self._log(f"[LR/COEF/timing] populateComboBox ({len(visible_names)} terms): {_time.perf_counter() - _t0:.2f}s")
      try:
        # combobox index 0 corresponds to the first visible coef (which is
        # self._coef_visible_indices[0] in the underlying arrays)
        _t0 = _time.perf_counter()
        self.ui.coefComboBox.setCurrentIndex(0)
        self._log(f"[LR/COEF/timing] coefComboBox.setCurrentIndex(0): {_time.perf_counter() - _t0:.2f}s")
      except Exception:
        pass

    # Domains for numeric mode
    import time as _time
    _t0 = _time.perf_counter()
    try:
      self._coef_build_domains()
    except Exception as e:
      self._log(f"[LR/COEF] domain build warning: {e}")
    self._log(f"[LR/COEF/timing] _coef_build_domains: {_time.perf_counter() - _t0:.2f}s")

    # Ensure infra + identity warp at neutral
    _t0 = _time.perf_counter()
    self._lr_prepareWarpInfra()
    self._log(f"[LR/COEF/timing] _lr_prepareWarpInfra: {_time.perf_counter() - _t0:.2f}s")
    _t0 = _time.perf_counter()
    self._ensureLRTPSNode()
    self._log(f"[LR/COEF/timing] _ensureLRTPSNode: {_time.perf_counter() - _t0:.2f}s")

    _t0 = _time.perf_counter()
    try:
      self._coef_set_slider_domain_for_current()
    except Exception as e:
      self._log(f"[LR/COEF] domain set failed: {e}")
      if self.coefController:
        self.coefController.setRange(-1.0, 1.0)
        self.coefController.setValue(0.0)
    self._log(f"[LR/COEF/timing] _coef_set_slider_domain_for_current: {_time.perf_counter() - _t0:.2f}s")

    # Build initial numeric TPS
    _t0 = _time.perf_counter()
    try:
      self._coef_applyTPS()
    except Exception as e:
      self._log(f"[LR/COEF] initial TPS build failed: {e}")
    self._log(f"[LR/COEF/timing] _coef_applyTPS (initial): {_time.perf_counter() - _t0:.2f}s")

    _t0 = _time.perf_counter()
    self._coef_attachTargets(enabled=True)
    self._log(f"[LR/COEF/timing] _coef_attachTargets: {_time.perf_counter() - _t0:.2f}s")

    # If the user jumped straight to the LR tab without first hitting Apply
    # on the 3D Visualization tab, the shared clone landmark/model nodes
    # don't exist yet — so the slider has nothing visible to drive. Nudge
    # them with a one-shot popup (per session).
    #
    # Defer via QTimer.singleShot so the modal popup does NOT block (and
    # inflate) the surrounding timing logs / progress dialog teardown.
    try:
      lm = getattr(self.w, "cloneLandmarkNode", None)
      have_lm = bool(lm is not None and slicer.mrmlScene.IsNodePresent(lm))
      if (not have_lm) and (not getattr(self, "_lr_applyHintShown", False)):
        self._lr_applyHintShown = True
        def _showApplyHint():
          try:
            slicer.util.infoDisplay(
              "Regression fit complete, but no warped landmarks are visible yet.\n\n"
              "Go to the '3D Visualization' tab and click 'Apply' to create the "
              "warped landmark / model display, then return here.",
              windowTitle="Geomorph LR")
          except Exception:
            pass
        qt.QTimer.singleShot(0, _showApplyHint)
    except Exception:
      pass

  def _coef_onSelectCoefficient(self):
    if not self._coef_enabled: return
    if getattr(self, "_coef_in_refresh", False): return
    try:
      vis_idx = int(self.coefController.comboBoxIndex())
    except Exception:
      vis_idx = -1
    visible = getattr(self, "_coef_visible_indices", []) or []
    if vis_idx < 0 or vis_idx >= len(visible): return
    self._coef_current = int(visible[vis_idx])

    # Set slider range & neutral for this coefficient
    try:
      self._coef_set_slider_domain_for_current()
    except Exception as e:
      self._log(f"[LR/COEF] domain set (select) failed: {e}")
      if self.coefController:
        self.coefController.setRange(-1.0, 1.0)
        self.coefController.setValue(0.0)

    try:
      self._coef_applyTPS()
    except Exception as e:
      self._log(f"[LR/COEF] TPS build (new coef) failed: {e}")
    self._coef_attachTargets(enabled=True)

  def _coef_setMagnification(self):
    if not self._coef_enabled: return
    try:
      self._coef_applyTPS()
    except Exception as e:
      self._log(f"[LR/COEF] TPS rebuild (magnification) failed: {e}")

  def _coef_updateScaling(self):
    if not self._coef_enabled:
      return
    if getattr(self, "_coef_in_refresh", False):
      return
    # User is interacting with an LR coefficient → claim ownership of the
    # shared warped-landmark/model clones for the LR pipeline. Auto-switches
    # the warp-mode toggle if PCA had previously claimed them.
    try:
      if getattr(self.w, "activeWarpMode", "pca") != "lr":
        self.w._setWarpMode("lr")
    except Exception:
      pass
    try:
      self._coef_applyTPS()
    except Exception as e:
      self._log(f"[LR/COEF] TPS rebuild failed: {e}")

  def _coef_resetView(self):
    # Set slider to neutral based on domain
    try:
      dom = self._coef_current_domain()
    except Exception:
      dom = {"mode": "unit", "ref": 0.0}
    if self.coefController:
      neutral = float(dom.get("ref", 0.0)) if dom.get("mode") == "real" else 0.0
      self.coefController.setValue(neutral)

    # Identity TPS
    node = self._ensureLRTPSNode()
    try:
      id_tps = vtk.vtkThinPlateSplineTransform();
      id_tps.SetBasisToR()
      node.SetAndObserveTransformToParent(id_tps);
      node.Modified()
    except Exception:
      pass
    self._coef_debugPipeline(tag="reset", sample_scale=0.0)

  def _coef_initOrResetClicked(self):
    """
    One-button convenience:
      - Ensure LR warping infra exists (landmarks, TPS node, attachments)
      - Reset the coefficient view to neutral (slider=0, identity TPS)
    Safe to click before or after fitting a model.
    """
    # Always try to bring infra up (idempotent no-op if already built)
    try:
      self._lr_prepareWarpInfra()
    except Exception as e:
      self._log(f"[LR/COEF] Init/Reset: infra prep warning: {e}")

    # Reset slider + TPS to identity (existing helper does both)
    try:
      self._coef_resetView()
    except Exception as e:
      self._log(f"[LR/COEF] Init/Reset: reset failed: {e}")

    # Make sure targets are attached (warped landmarks, and model if selected)
    try:
      self._coef_attachTargets(enabled=True)
    except Exception as e:
      self._log(f"[LR/COEF] Init/Reset: attach targets warning: {e}")

    self._coef_debugPipeline(tag="init/reset", sample_scale=0.0)

  def _coef_attachTargets(self, enabled: bool):
    node = getattr(self, "lrTPSTransformNode", None)
    if not node:
      self._log("[LR/COEF] lrTPSTransformNode missing in _coef_attachTargets"); return
    import time as _time
    # Route attachment through the widget's warp-mode toggle so PCA/LR
    # ownership of the shared clones stays consistent and the radio buttons
    # in Setup Interactive Visualization reflect reality.
    try:
      if enabled:
        _t = _time.perf_counter()
        self.w._setWarpMode("lr")
        self._log(f"[LR/COEF/timing]   _setWarpMode('lr'): {_time.perf_counter() - _t:.2f}s")
      else:
        # Detach by switching back to PCA (or, if no PCA grid yet, clear).
        if getattr(self.w, "gridTransformNode", None) is not None:
          self.w._setWarpMode("pca")
        else:
          lm = getattr(self.w, "cloneLandmarkNode", None) or getattr(self.w, "copyLandmarkNode", None)
          if lm is not None and slicer.mrmlScene.IsNodePresent(lm):
            try: lm.SetAndObserveTransformNodeID(None)
            except Exception: pass
          cm = getattr(self.w, "cloneModelNode", None)
          if cm is not None and slicer.mrmlScene.IsNodePresent(cm):
            try: cm.SetAndObserveTransformNodeID(None)
            except Exception: pass
    except Exception as e:
      self._log(f"[LR/COEF] attach via warp-mode toggle failed: {e}")
    self._coef_debugPipeline(tag=f"attachTargets(enabled={enabled})", sample_scale=None)

  def _coef_clearChoices(self):
    self._coef_vectors = []; self._coef_names = []; self._coef_current = -1
    if hasattr(self.ui, "coefComboBox"):
      try: self.ui.coefComboBox.clear()
      except Exception: pass
    if self.coefController:
      self.coefController.setRange(-1.0, 1.0); self.coefController.setValue(0.0)
    self._coef_attachTargets(enabled=False)

  def _coef_debugPipeline(self, tag="debug", sample_scale=None):
    """Silenced debug hook for the coefficient-warp pipeline."""
    return

  def _ensureLRGridNode(self):
    try:
      if getattr(self, 'lrGridTransformNode', None) and slicer.mrmlScene.IsNodePresent(self.lrGridTransformNode):
        return self.lrGridTransformNode
    except Exception: pass
    self.lrGridTransformNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLGridTransformNode', 'LRGridTransform')
    self.nodes.AddItem(self.lrGridTransformNode)
    self._log(f"[LR] Created LRGridTransform: {self.lrGridTransformNode.GetID()}")
    return self.lrGridTransformNode

  def _lr_prepareWarpInfra(self):
    """
    Prepare LR warp infra:
      - Ensure mean landmarks are available
      - Create/reuse the LR TPS transform
      - Attach the SHARED Interactive-Visualization clones (cloneLandmarkNode
        and, if model viz is enabled, cloneModelNode) under the LR transform.

    NOTE: Earlier revisions of this file created a dedicated 'LR Warped
    Landmarks' fiducial node (`lrWarpNode`) as a separate green/purple set
    in viewer 2. That has been removed: the LR tab now drives the same
    `cloneLandmarkNode` (and `cloneModelNode`) that the PCA tab drives, so
    viewer 2 only ever shows ONE warped landmark/model pair. A separate LR
    glyph node duplicated geometry in the same view, was easy to drag (the
    bug we just fixed), and required parallel color/scale/visibility
    bookkeeping. Single shared clone is simpler and avoids the confusion
    seen in the screenshot of two overlapping landmark sets.
    """
    # Ensure we have mean landmarks
    if getattr(self.w, "rawMeanLandmarks", None) is None:
        try:
            if getattr(self.w, "LM", None) and getattr(self.w.LM, "mShape", None) is not None:
                self.w.rawMeanLandmarks = np.asarray(self.w.LM.mShape, dtype=float)
            elif getattr(self.w, "LM", None) and getattr(self.w.LM, "lmOrig", None) is not None:
                self.w.rawMeanLandmarks = np.asarray(self.w.LM.lmOrig.mean(2), dtype=float)
        except Exception:
            pass
    if getattr(self.w, "rawMeanLandmarks", None) is None:
        self._log("[LR] Cannot initialize: no mean landmarks available yet.")
        return

    # Ensure the LR TPS transform exists.
    node = self._ensureLRTPSNode()

    # Attach the shared Interactive-Visualization clones under the LR
    # transform. If the user has not yet clicked Apply in Setup Interactive
    # Visualization, no clone exists; the slider will still update the
    # transform but viewer 2 will appear empty until Apply is clicked.
    #
    # PERF: SKIP the attach if we're inside _coef_refreshFromFit. In that
    # context _coef_attachTargets / _setWarpMode will perform the attach
    # AFTER the TPS has been set on the (still-unparented) transform node,
    # so the markups display does the expensive TPS evaluation exactly once
    # at attach time instead of twice (once now while the transform is
    # identity, then again after _coef_applyTPS swaps the TPS in).
    if getattr(self, "_coef_in_refresh", False):
        try:
            tid = node.GetID() if node else "(none)"
            self._log(f"[LR] Infra ready (TPS, deferred attach). transform={tid}")
        except Exception:
            pass
        return

    lm = getattr(self.w, "cloneLandmarkNode", None) or getattr(self.w, "copyLandmarkNode", None)
    if lm is not None and slicer.mrmlScene.IsNodePresent(lm):
        try:
            lm.SetAndObserveTransformNodeID(node.GetID())
        except Exception:
            pass

    try:
        modelChecked = bool(self.w.ui.modelVisualizationType.isChecked())
    except Exception:
        modelChecked = False
    if modelChecked and getattr(self.w, "cloneModelNode", None):
        try:
            self.w.cloneModelNode.SetAndObserveTransformNodeID(node.GetID())
        except Exception:
            pass

    try:
        tid = node.GetID() if node else "(none)"
        lid = lm.GetID() if (lm is not None and slicer.mrmlScene.IsNodePresent(lm)) else "(none)"
        self._log(f"[LR] Infra ready (TPS). transform={tid}, sharedLandmarkNode={lid}")
    except Exception:
        pass

  def _coef_row_to_shift(self, row_3p):
    if getattr(self.w, "rawMeanLandmarks", None) is None:
      raise RuntimeError("No mean landmarks available yet")
    p = int(self.w.rawMeanLandmarks.shape[0])
    a = np.asarray(row_3p, dtype=float).reshape(-1)
    if a.size != 3 * p:
      raise RuntimeError(f"Coefficient row length {a.size} != 3*p ({3 * p})")

    v = np.zeros((p, 3), dtype=float)
    v[:, 0] = a[0:p]
    v[:, 1] = a[p:2 * p]
    v[:, 2] = a[2 * p:3 * p]

    try:
      mag = float(self.ui.coefMagnificationSpin.value)
    except Exception:
      mag = 1000.0
    try:
      ssf = float(getattr(self.w, "sampleSizeScaleFactor", 1.0))
    except Exception:
      ssf = 1.0

    shift = (mag * ssf / 3.0) * v
    return shift

  def _ensureLRTPSNode(self):
    try:
      if getattr(self, 'lrTPSTransformNode', None) and slicer.mrmlScene.IsNodePresent(self.lrTPSTransformNode):
        return self.lrTPSTransformNode
    except Exception: pass
    self.lrTPSTransformNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTransformNode', 'LRTPS_Transform')
    self.nodes.AddItem(self.lrTPSTransformNode)
    self._log(f"[LR] Created LRTPS_Transform: {self.lrTPSTransformNode.GetID()}")
    return self.lrTPSTransformNode

  def _coef_applyTPS(self, scale: float | None = None):
    if self._coef_current is None or self._coef_current < 0:
      return
    if getattr(self.w, "rawMeanLandmarks", None) is None:
      return
    if not (self._coef_vectors and len(self._coef_vectors) > self._coef_current):
      return

    # Determine delta multiplier from current domain & slider value
    dom = self._coef_current_domain()
    if scale is None:
      try:
        value = float(self.coefController.sliderValue())
      except Exception:
        value = 0.0
    else:
      value = float(scale)

    if dom.get("mode") == "real":
      # Real units: slider shows the actual covariate value. Center on the
      # covariate mean (`ref`) so the midpoint of the slider is the zero-shift
      # reference shape; moving away from the mean adds value*beta deformation,
      # and the magnification factor only scales that offset (not the baseline).
      delta = value - float(dom.get("ref", 0.0))
    elif dom.get("mode") == "log":
      # Slider shows raw covariate; the regressor is log(value).
      # Center on the geometric mean so doubling/halving are mirror-image shifts.
      import math as _math
      ref = float(dom.get("ref", 1.0))
      v = float(value)
      if v <= 0.0 or ref <= 0.0:
        delta = 0.0
      else:
        delta = _math.log(v) - _math.log(ref)
    elif dom.get("mode") == "sqrt":
      import math as _math
      ref = float(dom.get("ref", 0.0))
      v = float(value)
      if v < 0.0 or ref < 0.0:
        delta = 0.0
      else:
        delta = _math.sqrt(v) - _math.sqrt(ref)
    elif dom.get("mode") == "cat":
      # Categorical: snap to nearest integer level index.
      # The coef row encodes (active_level - ref_level); contribute it only when
      # the slider lands on this coef's active_level.
      idx = int(round(value))
      idx = max(0, min(int(dom.get("max", 1)), idx))
      active_index = int(dom.get("active_index", 1))
      delta = 1.0 if (idx == active_index) else 0.0
      # Update spinbox suffix to reflect the currently-selected level name
      try:
        levels = list(dom.get("levels", []))
        if 0 <= idx < len(levels):
          spin = getattr(self.coefController, "spinBox", None)
          if spin is not None:
            spin.setSuffix(f"  ({levels[idx]})")
          # also snap the spinbox value to the integer
          if abs(value - idx) > 1e-9:
            try:
              self.coefController.setValue(float(idx))
            except Exception:
              pass
      except Exception:
        pass
    else:
      # Unit domain: keep legacy behavior in [-1, 1]
      if value > 1.0: value = 1.0
      if value < -1.0: value = -1.0
      delta = value

    row = np.asarray(self._coef_vectors[self._coef_current]).reshape(-1)
    base_shift = self._coef_row_to_shift(row)  # includes magnification & sample-size scaling
    shift = float(delta) * base_shift
    # Use intercept-predicted shape as the visualization base when available,
    # so that at slider==reference the picture is the model's prediction at
    # the reference predictors (Size=0, Sex=ref, ...). Falls back to the
    # Procrustes mean if the intercept could not be captured.
    base_shape = getattr(self, "_coef_intercept_shape", None)
    if base_shape is None or base_shape.shape != self.w.rawMeanLandmarks.shape:
      base_shape = self.w.rawMeanLandmarks
    target = base_shape + shift

    import time as _time
    node = self._ensureLRTPSNode()

    # PERF: at neutral (delta == 0), target == base_shape and the TPS is the
    # identity. The vtkTPS LU weight solve is O(p^3) and dominates the
    # post-fit cost (~13s at p=1000, ~80s at p=1440). Use a cheap identity
    # transform instead and only build a real TPS when the user actually
    # moves the slider.
    if abs(float(delta)) < 1e-12:
      _t = _time.perf_counter()
      ident = vtk.vtkTransform()  # identity
      node.SetAndObserveTransformToParent(ident)
      try: node.Modified()
      except Exception: pass
      self._log(f"[LR/COEF/timing]   identity transform (delta=0): {_time.perf_counter() - _t:.2f}s")
      self._coef_debugPipeline(tag=f"TPS val={value} (delta=0, identity)", sample_scale=None)
      return

    _t = _time.perf_counter()
    tps = vtk.vtkThinPlateSplineTransform()
    tps.SetSourceLandmarks(_convert_numpy_to_vtk_points(base_shape))
    tps.SetTargetLandmarks(_convert_numpy_to_vtk_points(target))
    tps.SetBasisToR()
    self._log(f"[LR/COEF/timing]   build vtkTPS (p={base_shape.shape[0]}): {_time.perf_counter() - _t:.2f}s")

    # Force the TPS weight solve here so the cost is visible (it would
    # otherwise be paid lazily by the first downstream consumer).
    _t = _time.perf_counter()
    try:
      tps.TransformPoint([0.0, 0.0, 0.0])
    except Exception:
      pass
    self._log(f"[LR/COEF/timing]   tps.TransformPoint (forces solve): {_time.perf_counter() - _t:.2f}s")

    _t = _time.perf_counter()
    node.SetAndObserveTransformToParent(tps)
    self._log(f"[LR/COEF/timing]   SetAndObserveTransformToParent: {_time.perf_counter() - _t:.2f}s")
    _t = _time.perf_counter()
    try:
      node.Modified()
    except Exception:
      pass
    self._log(f"[LR/COEF/timing]   node.Modified(): {_time.perf_counter() - _t:.2f}s")

    self._coef_debugPipeline(tag=f"TPS val={value} (delta={delta})", sample_scale=None)

  # ------------------------------ Misc UI helpers -----------------------------

  def _lr_setSummaryText(self, txt: str):
    w = getattr(self.ui, 'lrSummaryText', None)
    if not w: return
    try:
      w.setPlainText(str(txt) if txt is not None else "")
      try: w.setLineWrapMode(qt.QPlainTextEdit.NoWrap)
      except Exception: pass
      try:
        f = w.font
        for fam in ["Menlo","Consolas","Courier New","Monospace"]:
          f.setFamily(fam); break
        f.setFixedPitch(True); w.setFont(f)
      except Exception: pass
    except Exception: pass

  def _log(self, s: str):
    try:
      print(s)
      self.ui.GPALogTextbox.insertPlainText(s + "\n")
    except Exception:
      print(s)

  def _coef_build_domains(self):
    """
    Build per-coefficient slider domains:
      - Numeric (e.g., Size, Age): mode='real', range=[min,max], ref=mean
      - Categorical (e.g., SexM with levels=[F,M]): mode='cat',
          range=[0, k-1], levels=['F','M',...], ref_level, active_level, active_index
      - Otherwise: mode='unit', range=[-1,1], ref=0
    Saves into self._coef_domains: {coef_name: dict}
    """
    self._coef_domains = {}
    last = getattr(self, "_lr_last_fit", {}) or {}
    stats = last.get("covariate_stats", {}) or {}
    factor_levels = last.get("factor_levels", {}) or {}

    import math, re
    _TRANSFORM_RE = re.compile(r"^\s*(log|sqrt)\s*\(\s*([A-Za-z_][\w.]*)\s*\)\s*$")

    def numeric_domain_for(var_name: str):
      s = stats.get(var_name)
      if s and s.get("is_numeric"):
        return {"mode": "real", "min": float(s["min"]), "max": float(s["max"]), "ref": float(s["mean"])}
      return None

    def transformed_domain_for(token: str):
      """Detect tokens like 'log(Size)' or 'sqrt(Age)'. Slider stays in raw
      units; the apply step takes log/sqrt of the slider value, so the user
      thinks in mm even though the regression is on log(mm)."""
      m = _TRANSFORM_RE.match(token)
      if not m:
        return None
      fn, var = m.group(1), m.group(2)
      s = stats.get(var)
      if not s or not s.get("is_numeric"):
        return None
      if fn == "log":
        if "log_mean" not in s or s["min"] <= 0:
          return None  # log undefined on this column
        return {
          "mode": "log", "var": var,
          "min": float(s["min"]), "max": float(s["max"]),
          "ref": float(math.exp(s["log_mean"])),  # geometric mean
        }
      if fn == "sqrt":
        if "sqrt_mean" not in s or s["min"] < 0:
          return None
        return {
          "mode": "sqrt", "var": var,
          "min": float(s["min"]), "max": float(s["max"]),
          "ref": float(s["sqrt_mean"] ** 2),  # quadratic-mean center
        }
      return None

    def categorical_domain_for(coef_token: str):
      # coef_token looks like "SexM", "CrossDirectionFB", "GenotypeAA" etc.
      # Match the longest factor name that is a prefix of coef_token,
      # such that the remaining suffix is one of that factor's levels.
      best = None
      for fname, levels in factor_levels.items():
        if not fname or not levels:
          continue
        if coef_token.startswith(fname):
          suffix = coef_token[len(fname):]
          if suffix in levels:
            if (best is None) or (len(fname) > len(best[0])):
              best = (fname, suffix, list(levels))
      if best is None:
        return None
      fname, level, levels = best
      try:
        ref_level = levels[0]
        active_index = int(levels.index(level))
      except Exception:
        return None
      return {
        "mode": "cat",
        "min": 0.0,
        "max": float(max(1, len(levels) - 1)),
        "ref": 0.0,
        "factor": fname,
        "levels": levels,
        "ref_level": ref_level,
        "active_level": level,
        "active_index": active_index,
      }

    for nm in (self._coef_names or []):
      nm_str = str(nm).strip()
      dom = None

      # 1) Transformed numeric (e.g., "log(Size)", "sqrt(Age)")
      dom = transformed_domain_for(nm_str)

      # 2) Plain numeric (e.g., "Size")
      if dom is None:
        dom = numeric_domain_for(nm_str)

      # 3) Categorical (e.g., "SexM")
      if dom is None:
        dom = categorical_domain_for(nm_str)

      # 4) Interaction term: prefer numeric/transformed side; otherwise pick first categorical side
      if dom is None and ":" in nm_str:
        parts = [p.strip() for p in nm_str.split(":") if p.strip()]
        for p in parts:
          cand = transformed_domain_for(p) or numeric_domain_for(p)
          if cand is not None:
            dom = cand
            dom["interaction_numeric"] = p
            break
        if dom is None:
          for p in parts:
            cand = categorical_domain_for(p)
            if cand is not None:
              dom = cand
              dom["interaction_categorical"] = p
              break

      # 4) Default unit domain
      if dom is None:
        dom = {"mode": "unit", "min": -1.0, "max": 1.0, "ref": 0.0}

      self._coef_domains[nm_str] = dom

  def _coef_current_domain(self):
    """Return domain dict for the currently-selected coefficient."""
    if self._coef_current is None or self._coef_current < 0:
      return {"mode": "unit", "min": -1.0, "max": 1.0, "ref": 0.0}
    try:
      name = str(self._coef_names[self._coef_current]).strip()
    except Exception:
      return {"mode": "unit", "min": -1.0, "max": 1.0, "ref": 0.0}
    dom = getattr(self, "_coef_domains", {}).get(name)
    if not dom:
      dom = {"mode": "unit", "min": -1.0, "max": 1.0, "ref": 0.0}
    return dom

  def _coef_set_slider_domain_for_current(self):
    """
    Apply domain to the slider/spinbox:
      - Numeric:     range=[min,max], set value=mean (neutral), free movement
      - Categorical: range=[0,k-1],   set value=0 (reference level), integer snap,
                     spinbox suffix shows current level name (e.g. " (F)")
      - Unit:        range=[-1,1],    set value=0.0 (neutral)
    """
    if not self.coefController:
      return
    dom = self._coef_current_domain()
    self.coefController.setRange(float(dom["min"]), float(dom["max"]))

    mode = dom.get("mode")
    # configure spinbox precision/step + suffix per mode
    spin = getattr(self.coefController, "spinBox", None)
    if spin is not None:
      try:
        if mode == "cat":
          spin.setDecimals(0)
          spin.setSingleStep(1.0)
          spin.setSuffix(f"  ({dom['levels'][0]})")
        elif mode in ("log", "sqrt"):
          spin.setDecimals(3)
          spin.setSingleStep(0.01)
          spin.setSuffix(f"  ({mode})")
        else:
          spin.setDecimals(3)
          spin.setSingleStep(0.01)
          spin.setSuffix("")
      except Exception:
        pass

    if mode in ("real", "log", "sqrt"):
      neutral = float(dom.get("ref", 0.0))
    else:
      # cat and unit both start at 0 (reference / neutral)
      neutral = 0.0
    self.coefController.setValue(neutral)

    if mode in ("real", "log", "sqrt"):
      try:
        self.ui.coefMagnificationSpin.setValue(1.0)
      except Exception:
        pass

  def _py_to_str_list(self, obj):
    """
    Coerce obj (str | list[str] | tuple[str] | numpy array) into a list[str].
    Avoids the 'list(\"Species\") -> ['S','p',...]' trap when pyRserve returns a scalar.
    """
    try:
      import numpy as _np
    except Exception:
      _np = None

    if isinstance(obj, (list, tuple)):
      return [str(x) for x in obj]
    if _np is not None and isinstance(obj, _np.ndarray):
      try:
        return [str(x) for x in obj.tolist()]
      except Exception:
        return [str(obj)]
    # scalar (incl. Python str) -> wrap
    return [str(obj)]
    return [str(obj)]