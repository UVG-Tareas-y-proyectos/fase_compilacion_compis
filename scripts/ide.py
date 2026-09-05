"""IDE de la Fase 1 de Compiscript: árbol, símbolos y diagnósticos."""

import re
import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from compiscript.pipeline import analyze_source  # noqa: E402
from compiscript.tree import Token, Tree  # noqa: E402


EXAMPLES = ROOT / "examples"
COLORS = {
    "background": "#0b1020",
    "panel": "#111827",
    "editor": "#090e1a",
    "surface": "#1f2937",
    "border": "#334155",
    "text": "#e5e7eb",
    "muted": "#94a3b8",
    "accent": "#22c55e",
    "accent_hover": "#16a34a",
    "error": "#fb7185",
    "warning": "#fbbf24",
    "keyword": "#c084fc",
    "type": "#38bdf8",
    "literal": "#fb923c",
    "string": "#86efac",
    "comment": "#64748b",
}

SYNTAX = [
    ("type", r"\b(integer|float|boolean|string)\b"),
    ("keyword", r"\b(let|var|const|function|class|new|this|if|else|while|"
                r"do|for|foreach|in|switch|case|default|try|catch|return|"
                r"break|continue)\b"),
    ("literal", r"\b(true|false|null|\d+(?:\.\d+)?)\b"),
    ("string", r'"[^"\n]*"'),
    ("comment", r"//[^\n]*"),
]


class CompiscriptIDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Compiscript - Fase 1: análisis semántico")
        self.geometry("1400x840")
        self.minsize(1050, 650)
        self.configure(bg=COLORS["background"])
        self.file_path = None
        self.result = None

        family = self._monospace_font()
        self.code_font = (family, 11)
        self.small_code_font = (family, 10)
        self._configure_styles()
        self._build()
        self._bind_shortcuts()
        self._load_example("basico")

    def _monospace_font(self):
        available = set(tkfont.families(self))
        for candidate in ("Cascadia Code", "JetBrains Mono", "Consolas",
                          "DejaVu Sans Mono"):
            if candidate in available:
                return candidate
        return "TkFixedFont"

    def _configure_styles(self):
        c = COLORS
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=c["background"], foreground=c["text"])
        style.configure("TFrame", background=c["background"])
        style.configure("TNotebook", background=c["panel"], borderwidth=0)
        style.configure("TNotebook.Tab", background=c["surface"],
                        foreground=c["muted"], padding=(14, 8))
        style.map("TNotebook.Tab",
                  background=[("selected", c["panel"])],
                  foreground=[("selected", c["text"])])
        style.configure("Treeview", background=c["editor"],
                        fieldbackground=c["editor"], foreground=c["text"],
                        rowheight=26, font=self.small_code_font)
        style.configure("Treeview.Heading", background=c["surface"],
                        foreground=c["muted"], font=("Segoe UI Semibold", 9))
        style.map("Treeview", background=[("selected", "#1d4ed8")])
        style.configure("TCombobox", fieldbackground=c["surface"],
                        background=c["surface"], foreground=c["text"])

    def _build(self):
        c = COLORS
        container = tk.Frame(self, bg=c["background"], padx=14, pady=12)
        container.pack(fill="both", expand=True)

        toolbar = tk.Frame(container, bg=c["background"])
        toolbar.pack(fill="x", pady=(0, 10))
        tk.Label(toolbar, text="Compiscript", bg=c["background"], fg=c["text"],
                 font=("Segoe UI Semibold", 17)).pack(side="left")
        tk.Label(toolbar, text="  Fase 1 · árbol · símbolos · semántica",
                 bg=c["background"], fg=c["muted"],
                 font=("Segoe UI", 10)).pack(side="left", pady=(4, 0))

        self._button(toolbar, "Analizar (F5)", self.analyze,
                     primary=True).pack(side="right")
        self.example_name = tk.StringVar(value="basico")
        names = sorted(path.stem for path in EXAMPLES.glob("*.cps"))
        combo = ttk.Combobox(toolbar, textvariable=self.example_name,
                             values=names, state="readonly", width=18)
        combo.bind("<<ComboboxSelected>>",
                   lambda _event: self._load_example(self.example_name.get()))
        combo.pack(side="right", padx=8)
        self._button(toolbar, "Guardar", self.save_file).pack(side="right", padx=3)
        self._button(toolbar, "Abrir", self.open_file).pack(side="right", padx=3)

        panes = tk.PanedWindow(container, orient="horizontal",
                               bg=c["background"], sashwidth=6, bd=0)
        panes.pack(fill="both", expand=True)
        editor_frame = tk.Frame(panes, bg=c["panel"], padx=8, pady=8)
        output_frame = tk.Frame(panes, bg=c["panel"])
        panes.add(editor_frame, minsize=430, stretch="always")
        panes.add(output_frame, minsize=520, stretch="always")
        self._build_editor(editor_frame)
        self._build_outputs(output_frame)

        status = tk.Frame(container, bg=c["surface"], padx=12, pady=7)
        status.pack(fill="x", pady=(10, 0))
        self.status = tk.Label(status, text="Listo", bg=c["surface"],
                               fg=c["muted"], font=self.small_code_font)
        self.status.pack(side="left")
        self.position = tk.Label(status, text="Ln 1, Col 1", bg=c["surface"],
                                 fg=c["muted"], font=("Segoe UI", 9))
        self.position.pack(side="right")

    def _button(self, parent, text, command, primary=False):
        c = COLORS
        normal = c["accent"] if primary else c["surface"]
        hover = c["accent_hover"] if primary else c["border"]
        button = tk.Label(parent, text=text, cursor="hand2", padx=14, pady=7,
                          bg=normal, fg="#ffffff" if primary else c["text"],
                          font=("Segoe UI Semibold", 9))
        button.bind("<Button-1>", lambda _event: command())
        button.bind("<Enter>", lambda _event: button.configure(bg=hover))
        button.bind("<Leave>", lambda _event: button.configure(bg=normal))
        return button

    def _build_editor(self, parent):
        c = COLORS
        scrollbar = ttk.Scrollbar(parent, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.editor = tk.Text(
            parent, wrap="none", undo=True, font=self.code_font,
            bg=c["editor"], fg=c["text"], insertbackground=c["accent"],
            selectbackground="#1d4ed8", relief="flat", padx=12, pady=12,
            yscrollcommand=scrollbar.set,
        )
        self.editor.pack(fill="both", expand=True)
        scrollbar.configure(command=self.editor.yview)
        for tag in ("type", "keyword", "literal", "string", "comment"):
            self.editor.tag_configure(tag, foreground=c[tag])
        self.editor.tag_configure("error_line", background="#3f1722")
        self.editor.tag_configure("warning_line", background="#3b3013")
        self.editor.bind("<KeyRelease>", self._on_editor_change)
        self.editor.bind("<ButtonRelease-1>", self._update_position)

    def _build_outputs(self, parent):
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.ast_frame = tk.Frame(self.notebook, bg=COLORS["panel"])
        self.symbol_frame = tk.Frame(self.notebook, bg=COLORS["panel"])
        self.error_frame = tk.Frame(self.notebook, bg=COLORS["panel"])
        self.notebook.add(self.ast_frame, text="Árbol sintáctico")
        self.notebook.add(self.symbol_frame, text="Tabla de símbolos")
        self.notebook.add(self.error_frame, text="Errores")

        self.ast_tree = self._tree(self.ast_frame, ("Nodo", "Línea"),
                                   (600, 70), tree_column=True)
        self.symbol_tree = self._tree(
            self.symbol_frame,
            ("Ámbito", "Tipo ámbito", "Nivel", "Nombre", "Clase", "Tipo",
             "Mutable", "Línea", "Columna"),
            (170, 90, 50, 120, 90, 210, 65, 55, 65),
        )
        self.error_tree = self._tree(
            self.error_frame,
            ("Severidad", "Fase", "Línea", "Columna", "Mensaje"),
            (75, 90, 55, 65, 520),
        )
        self.error_tree.tag_configure("error", foreground=COLORS["error"])
        self.error_tree.tag_configure("aviso", foreground=COLORS["warning"])
        self.error_tree.bind("<<TreeviewSelect>>", self._go_to_diagnostic)

    def _tree(self, parent, columns, widths, tree_column=False):
        scrollbar = ttk.Scrollbar(parent, orient="vertical")
        show = "tree headings" if tree_column else "headings"
        tree = ttk.Treeview(parent, columns=columns[1:] if tree_column else columns,
                            show=show, yscrollcommand=scrollbar.set)
        if tree_column:
            tree.heading("#0", text=columns[0])
            tree.column("#0", width=widths[0], stretch=True)
            pairs = zip(columns[1:], widths[1:])
        else:
            pairs = zip(columns, widths)
        for column, width in pairs:
            tree.heading(column, text=column)
            tree.column(column, width=width, anchor="w", stretch=width > 180)
        scrollbar.configure(command=tree.yview)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        return tree

    def _bind_shortcuts(self):
        self.bind("<F5>", lambda _event: self.analyze())
        self.bind("<Control-o>", lambda _event: self.open_file())
        self.bind("<Control-s>", lambda _event: self.save_file())

    def _on_editor_change(self, _event=None):
        self._highlight()
        self._update_position()

    def _highlight(self):
        source = self.editor.get("1.0", "end-1c")
        for tag, _ in SYNTAX:
            self.editor.tag_remove(tag, "1.0", "end")
        for tag, pattern in SYNTAX:
            for match in re.finditer(pattern, source):
                self.editor.tag_add(tag, f"1.0+{match.start()}c",
                                    f"1.0+{match.end()}c")

    def _update_position(self, _event=None):
        line, column = self.editor.index("insert").split(".")
        self.position.configure(text=f"Ln {line}, Col {int(column) + 1}")

    def _load_example(self, name):
        path = EXAMPLES / f"{name}.cps"
        if path.exists():
            self._load(path.read_text(encoding="utf-8"), path)
            self.analyze()

    def _load(self, source, path=None):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", source)
        self.file_path = path
        self._highlight()
        self.title("Compiscript - Fase 1" +
                   (f" - {path.name}" if path else ""))

    def open_file(self):
        path = filedialog.askopenfilename(
            initialdir=EXAMPLES, filetypes=[("Compiscript", "*.cps")]
        )
        if path:
            selected = Path(path)
            self._load(selected.read_text(encoding="utf-8"), selected)
            self.analyze()

    def save_file(self):
        if self.file_path is None:
            path = filedialog.asksaveasfilename(
                defaultextension=".cps",
                filetypes=[("Compiscript", "*.cps")],
            )
            if not path:
                return
            self.file_path = Path(path)
        self.file_path.write_text(self.editor.get("1.0", "end-1c"),
                                  encoding="utf-8")

    def analyze(self):
        try:
            self.result = analyze_source(self.editor.get("1.0", "end-1c"))
        except Exception as exc:
            messagebox.showerror("Error interno", str(exc))
            raise
        self._show_ast()
        self._show_symbols()
        self._show_diagnostics()

        errors = len(self.result.errors)
        warnings = len(self.result.warnings)
        if errors:
            self.status.configure(text=f"Fase 1 con {errors} error(es) y "
                                       f"{warnings} aviso(s)",
                                  fg=COLORS["error"])
            self.notebook.select(self.error_frame)
        else:
            self.status.configure(text=f"Fase 1 correcta · {warnings} aviso(s)",
                                  fg=COLORS["accent"])
            self.notebook.select(self.symbol_frame)

    def _show_ast(self):
        self.ast_tree.delete(*self.ast_tree.get_children())
        if self.result.tree is None:
            return

        def add(node, parent=""):
            if isinstance(node, Tree):
                line = getattr(node.meta, "line", "")
                item = self.ast_tree.insert(parent, "end", text=str(node.data),
                                            values=(line,), open=True)
                for child in node.children:
                    add(child, item)
            elif isinstance(node, Token):
                self.ast_tree.insert(parent, "end",
                                     text=f"{node.type}: {node.value}",
                                     values=(node.line or "",))

        add(self.result.tree)

    def _show_symbols(self):
        self.symbol_tree.delete(*self.symbol_tree.get_children())
        if self.result.symbol_table is None:
            return
        for row in self.result.symbol_table.rows():
            self.symbol_tree.insert("", "end", values=row)

    def _show_diagnostics(self):
        self.error_tree.delete(*self.error_tree.get_children())
        self.editor.tag_remove("error_line", "1.0", "end")
        self.editor.tag_remove("warning_line", "1.0", "end")
        for diagnostic in self.result.diagnostics:
            self.error_tree.insert(
                "", "end",
                values=(diagnostic.severity, diagnostic.phase, diagnostic.line,
                        diagnostic.column, diagnostic.message),
                tags=(diagnostic.severity,),
            )
            if diagnostic.line:
                tag = ("warning_line" if diagnostic.severity == "aviso"
                       else "error_line")
                self.editor.tag_add(tag, f"{diagnostic.line}.0",
                                    f"{diagnostic.line + 1}.0")
        self.notebook.tab(self.error_frame,
                          text=f"Errores ({len(self.result.errors)}+"
                               f"{len(self.result.warnings)})")

    def _go_to_diagnostic(self, _event=None):
        selected = self.error_tree.selection()
        if not selected:
            return
        values = self.error_tree.item(selected[0], "values")
        if values and values[2]:
            line = int(values[2])
            column = max(int(values[3]) - 1, 0)
            self.editor.mark_set("insert", f"{line}.{column}")
            self.editor.see(f"{line}.0")
            self.editor.focus_set()
            self._update_position()


if __name__ == "__main__":
    CompiscriptIDE().mainloop()
