import math
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import List, Tuple

try:
    import ezdxf
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        'Missing dependency',
        'The ezdxf package is not installed.\n\nRun the included BAT file on Windows to install it automatically.'
    )
    raise

REQUIRED_POLYLINE_LAYER = 'CUT'
OPTIONAL_TOP_LAYER = 'TOP'
CLOSE_TOLERANCE = 0.01

class ValidationIssue:
    def __init__(self, severity: str, message: str):
        self.severity = severity
        self.message = message
    def __str__(self) -> str:
        return f'[{self.severity}] {self.message}'

class DXFValidationResult:
    def __init__(self):
        self.issues: List[ValidationIssue] = []
        self.closed_polylines_found = 0
        self.open_polylines_found = 0
        self.total_polylines_found = 0
        self.required_layer_found = False
        self.optional_top_layer_found = False
        self.loose_entities_found = 0
    def add(self, severity: str, message: str):
        self.issues.append(ValidationIssue(severity, message))
    @property
    def is_valid(self) -> bool:
        return not any(i.severity == 'ERROR' for i in self.issues)

def dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def lwpolyline_points(entity):
    return [(p[0], p[1]) for p in entity.get_points()]

def polyline_points(entity):
    pts = []
    for v in entity.vertices:
        loc = v.dxf.location
        pts.append((loc.x, loc.y))
    return pts

def entity_is_closed(entity) -> bool:
    t = entity.dxftype()
    if t == 'LWPOLYLINE':
        if entity.closed:
            return True
        pts = lwpolyline_points(entity)
        return len(pts) > 2 and dist(pts[0], pts[-1]) <= CLOSE_TOLERANCE
    if t == 'POLYLINE':
        if entity.is_closed:
            return True
        pts = polyline_points(entity)
        return len(pts) > 2 and dist(pts[0], pts[-1]) <= CLOSE_TOLERANCE
    return False

def validate_dxf(path: str, required_layer: str, top_layer: str) -> DXFValidationResult:
    result = DXFValidationResult()
    try:
        doc = ezdxf.readfile(path)
    except Exception as e:
        result.add('ERROR', f'Could not open DXF: {e}')
        return result

    msp = doc.modelspace()
    layers = {layer.dxf.name for layer in doc.layers}

    if required_layer in layers:
        result.required_layer_found = True
    else:
        result.add('ERROR', f"Required layer '{required_layer}' is missing.")

    if top_layer in layers:
        result.optional_top_layer_found = True
    else:
        result.add('WARNING', f"Top layer '{top_layer}' was not found.")

    for e in msp:
        t = e.dxftype()
        if t in ('LWPOLYLINE', 'POLYLINE'):
            result.total_polylines_found += 1
            layer_name = e.dxf.layer
            if entity_is_closed(e):
                result.closed_polylines_found += 1
            else:
                result.open_polylines_found += 1
                result.add('ERROR', f"Open polyline found on layer '{layer_name}'. It must be closed.")
            if layer_name != required_layer:
                result.add('WARNING', f"Polyline found on layer '{layer_name}', expected '{required_layer}'.")
        elif t in ('LINE', 'ARC', 'SPLINE'):
            result.loose_entities_found += 1
            result.add('WARNING', f"Loose {t} entity found on layer '{e.dxf.layer}'. Jet imports often prefer closed polylines.")

    if result.total_polylines_found == 0:
        result.add('ERROR', 'No POLYLINE or LWPOLYLINE entities were found.')
    if result.closed_polylines_found == 0:
        result.add('ERROR', 'No closed polylines were found.')
    return result

def ensure_layer(doc, layer_name: str):
    if layer_name not in doc.layers:
        doc.layers.add(layer_name)

def try_close_entity(entity) -> bool:
    t = entity.dxftype()
    if t == 'LWPOLYLINE':
        pts = lwpolyline_points(entity)
        if len(pts) < 3:
            return False
        entity.closed = True
        return True
    if t == 'POLYLINE':
        pts = polyline_points(entity)
        if len(pts) < 3:
            return False
        entity.close(True)
        return True
    return False

def fix_dxf(input_path: str, output_path: str, required_layer: str, top_layer: str) -> List[str]:
    notes = []
    doc = ezdxf.readfile(input_path)
    msp = doc.modelspace()
    ensure_layer(doc, required_layer)
    ensure_layer(doc, top_layer)
    fixed_any = False

    for e in msp:
        if e.dxftype() not in ('LWPOLYLINE', 'POLYLINE'):
            continue
        if e.dxf.layer != required_layer:
            notes.append(f"Moved polyline from layer '{e.dxf.layer}' to '{required_layer}'.")
            e.dxf.layer = required_layer
            fixed_any = True
        if not entity_is_closed(e):
            if try_close_entity(e):
                notes.append('Closed an open polyline.')
                fixed_any = True
            else:
                notes.append('Could not close one polyline because it had too few vertices.')

    if not fixed_any:
        notes.append('No automatic changes were needed.')

    doc.saveas(output_path)
    notes.append(f'Saved fixed file to: {output_path}')
    return notes

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('Donatoni Jet 625 DXF Checker')
        self.root.geometry('920x700')

        self.file_path = tk.StringVar()
        self.required_layer = tk.StringVar(value=REQUIRED_POLYLINE_LAYER)
        self.top_layer = tk.StringVar(value=OPTIONAL_TOP_LAYER)

        frm = ttk.Frame(root, padding=12)
        frm.pack(fill='both', expand=True)

        row1 = ttk.Frame(frm)
        row1.pack(fill='x', pady=4)
        ttk.Label(row1, text='DXF File:').pack(side='left')
        ttk.Entry(row1, textvariable=self.file_path).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(row1, text='Browse', command=self.browse).pack(side='left')

        row2 = ttk.Frame(frm)
        row2.pack(fill='x', pady=4)
        ttk.Label(row2, text='Required polyline layer:').pack(side='left')
        ttk.Entry(row2, textvariable=self.required_layer, width=18).pack(side='left', padx=8)
        ttk.Label(row2, text='Top layer:').pack(side='left')
        ttk.Entry(row2, textvariable=self.top_layer, width=18).pack(side='left', padx=8)

        row3 = ttk.Frame(frm)
        row3.pack(fill='x', pady=8)
        ttk.Button(row3, text='Validate', command=self.run_validation).pack(side='left')
        ttk.Button(row3, text='Validate + Save Fixed Copy', command=self.run_fix).pack(side='left', padx=8)
        ttk.Button(row3, text='Open DXF Folder', command=self.open_folder).pack(side='left', padx=8)

        self.output = scrolledtext.ScrolledText(frm, wrap='word', height=30)
        self.output.pack(fill='both', expand=True, pady=8)

        self.write('Donatoni Jet 625 DXF Checker\n')
        self.write('Checks for:')
        self.write('- required layer exists')
        self.write('- top layer exists')
        self.write('- POLYLINE/LWPOLYLINE entities exist')
        self.write('- polylines are closed')
        self.write('- polylines are on the required layer')
        self.write('- loose LINE / ARC / SPLINE entities')
        self.write('')
        self.write('Default layers: CUT and TOP. Change them above if your machine needs different names.')

    def write(self, text: str):
        self.output.insert('end', text + '\n')
        self.output.see('end')

    def clear_output(self):
        self.output.delete('1.0', 'end')

    def browse(self):
        path = filedialog.askopenfilename(title='Select DXF file', filetypes=[('DXF Files', '*.dxf'), ('All Files', '*.*')])
        if path:
            self.file_path.set(path)

    def open_folder(self):
        path = self.file_path.get().strip()
        if not path:
            messagebox.showinfo('No file selected', 'Choose a DXF file first.')
            return
        folder = os.path.dirname(path)
        if sys.platform.startswith('win'):
            os.startfile(folder)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', folder])
        else:
            subprocess.Popen(['xdg-open', folder])

    def run_validation(self):
        path = self.file_path.get().strip()
        if not path:
            messagebox.showerror('Missing file', 'Please choose a DXF file.')
            return
        self.clear_output()
        result = validate_dxf(path, self.required_layer.get().strip(), self.top_layer.get().strip())
        self.write(f'File: {path}')
        self.write(f'Total polylines: {result.total_polylines_found}')
        self.write(f'Closed polylines: {result.closed_polylines_found}')
        self.write(f'Open polylines: {result.open_polylines_found}')
        self.write(f'Loose LINE/ARC/SPLINE entities: {result.loose_entities_found}')
        self.write('')
        self.write('VALID' if result.is_valid else 'INVALID')
        self.write('')
        for issue in result.issues:
            self.write(str(issue))

    def run_fix(self):
        path = self.file_path.get().strip()
        if not path:
            messagebox.showerror('Missing file', 'Please choose a DXF file.')
            return
        base, ext = os.path.splitext(path)
        output_path = base + '_fixed' + ext
        self.clear_output()
        try:
            notes = fix_dxf(path, output_path, self.required_layer.get().strip(), self.top_layer.get().strip())
            self.write('Fix completed.\n')
            for note in notes:
                self.write(note)
            self.write('\nRe-validating fixed file...\n')
            result = validate_dxf(output_path, self.required_layer.get().strip(), self.top_layer.get().strip())
            self.write(f'Total polylines: {result.total_polylines_found}')
            self.write(f'Closed polylines: {result.closed_polylines_found}')
            self.write(f'Open polylines: {result.open_polylines_found}')
            self.write(f'Loose LINE/ARC/SPLINE entities: {result.loose_entities_found}')
            self.write('')
            for issue in result.issues:
                self.write(str(issue))
            self.write('\nFINAL RESULT: Fixed file passes the current checks.' if result.is_valid else '\nFINAL RESULT: Fixed file still has issues that need manual correction.')
        except Exception as e:
            messagebox.showerror('Fix failed', str(e))

if __name__ == '__main__':
    root = tk.Tk()
    app = App(root)
    root.mainloop()
