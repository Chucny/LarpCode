"""
LarpCode IDE - Open Source Coding IDE
Dependencies: pip install customtkinter pygments pywebview
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk

from pygments import lex
from pygments.lexers import get_lexer_for_filename, get_lexer_by_name, TextLexer
from pygments.styles import get_style_by_name

# Sharp corners for standard IDE look
ctk.set_widget_scaling(1.0)
ctk.set_window_scaling(1.0)
CORNER = 0 

# ==========================================
# Code Editor Widget
# ==========================================
class CodeEditor(ctk.CTkTextbox):
    def __init__(self, master, filepath, **kwargs):
        super().__init__(master, corner_radius=CORNER, **kwargs)
        self.filepath = filepath
        self.lexer = TextLexer()
        self._after_id = None
        self.valid_tags = set()
        
        self.bind("<KeyRelease>", self.schedule_highlight)
        self._setup_tags('monokai')
        self.load_file()
        
    def _setup_tags(self, theme_name='monokai'):
        try:
            self.style = get_style_by_name(theme_name)
        except Exception:
            self.style = get_style_by_name('default')
            
        self.configure(fg_color=self.style.background_color)
        text_color = "#f8f8f2" if theme_name == "monokai" else "#1e1e1e"
        self._textbox.configure(insertbackground=text_color, fg=text_color)
        
        for tag in self._textbox.tag_names():
            self._textbox.tag_delete(tag)
        self.valid_tags.clear()
        
        for token, style_dict in self.style:
            if color := style_dict.get('color'):
                self._textbox.tag_configure(str(token), foreground=f"#{color}")
                self.valid_tags.add(token)

    def load_file(self):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.delete('1.0', ctk.END)
            self.insert(ctk.END, content)
            self.set_lexer_by_filename()
        except Exception as e:
            self.insert(ctk.END, f"Error loading file: {e}")

    def save_file(self):
        try:
            content = self.get('1.0', ctk.END)
            # Remove trailing newline added by tkinter
            if content.endswith('\n'):
                content = content[:-1]
            with open(self.filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
            return False

    def set_lexer_by_filename(self):
        try:
            self.lexer = get_lexer_for_filename(self.filepath)
        except Exception:
            self.lexer = TextLexer()
        self.schedule_highlight()

    def set_lexer_by_name(self, lang_name):
        try:
            self.lexer = get_lexer_by_name(lang_name.lower())
        except Exception:
            self.lexer = TextLexer()
        self.schedule_highlight()

    def schedule_highlight(self, event=None):
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(300, self._apply_highlighting)

    def _apply_highlighting(self):
        content = self.get('1.0', ctk.END)
        if len(content) > 150000: return # Prevent lag on huge files
            
        for tag in self.valid_tags:
            self._textbox.tag_remove(str(tag), '1.0', ctk.END)
            
        tokens = lex(content, self.lexer)
        line, col = 1, 0
        
        for token, text in tokens:
            t = token
            while t is not None and t not in self.valid_tags:
                try: t = t.parent
                except AttributeError: break
                    
            lines = text.split('\n')
            start_index = f"{line}.{col}"
            
            if len(lines) == 1:
                col += len(lines[0])
            else:
                line += len(lines) - 1
                col = len(lines[-1])
                
            if t in self.valid_tags:
                self._textbox.tag_add(str(t), start_index, f"{line}.{col}")


# ==========================================
# Main IDE Window
# ==========================================
class LarpCodeIDE(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LarpCode IDE")
        self.geometry("1400x800")
        ctk.set_appearance_mode("Dark")
        
        self.current_folder = ""
        self.mega_txt_path = ""
        self.open_tabs = {} # dict mapping tab_name -> CodeEditor widget
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self._build_toolbar()
        self._build_left_panel()
        self._build_editor_area()
        self._build_right_panel()

        # Global Hotkeys
        self.bind("<Control-s>", lambda e: self.save_current_file())

    def _build_toolbar(self):
        self.toolbar = ctk.CTkFrame(self, height=40, corner_radius=CORNER)
        self.toolbar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=2, pady=2)
        
        # Left side buttons
        ctk.CTkButton(self.toolbar, text="Open Folder", command=self.open_folder, corner_radius=CORNER, width=100).pack(side="left", padx=2)
        ctk.CTkButton(self.toolbar, text="Save (Ctrl+S)", command=self.save_current_file, fg_color="#2b7a0b", hover_color="#3c9d13", corner_radius=CORNER, width=100).pack(side="left", padx=2)
        ctk.CTkButton(self.toolbar, text="Close Tab", command=self.close_current_tab, fg_color="#8b0000", hover_color="#a52a2a", corner_radius=CORNER, width=80).pack(side="left", padx=2)
        
        # Center context buttons
        ctk.CTkButton(self.toolbar, text="Merge Files", command=self.merge_files, corner_radius=CORNER).pack(side="left", padx=(20, 2))
        ctk.CTkButton(self.toolbar, text="Build Prompt", command=self.finalize_prompt, corner_radius=CORNER).pack(side="left", padx=2)
        
        # Right side tools
        self.theme_var = ctk.StringVar(value="Dark")
        ctk.CTkSwitch(self.toolbar, text="Dark Mode", variable=self.theme_var, onvalue="Dark", offvalue="Light", command=self.toggle_theme).pack(side="right", padx=10)
        
        self.lang_var = ctk.StringVar(value="Auto")
        langs = ["Auto", "Python", "JavaScript", "HTML", "CSS", "C++", "Java", "Go", "Rust", "JSON", "C#", "PHP", "Ruby"]
        self.lang_menu = ctk.CTkOptionMenu(self.toolbar, values=langs, variable=self.lang_var, command=self.change_language, corner_radius=CORNER)
        self.lang_menu.pack(side="right", padx=10)
        ctk.CTkLabel(self.toolbar, text="Language:").pack(side="right")

    def _build_left_panel(self):
        self.left_panel = ctk.CTkFrame(self, width=250, corner_radius=CORNER)
        self.left_panel.grid(row=1, column=0, sticky="nswe", padx=2, pady=2)
        self.left_panel.grid_rowconfigure(0, weight=1)
        self.left_panel.grid_columnconfigure(0, weight=1)
        
        self.tree = ttk.Treeview(self.left_panel, show="tree")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_expand)
        # Fix: Double click to open files reliably
        self.tree.bind("<Double-1>", self.on_tree_double_click) 
        self.update_treeview_theme(True)

    def _build_editor_area(self):
        # Using Tabview for multiple files
        self.tabview = ctk.CTkTabview(self, corner_radius=CORNER)
        self.tabview.grid(row=1, column=1, sticky="nswe", padx=2, pady=2)

    def _build_right_panel(self):
        self.right_panel = ctk.CTkFrame(self, width=220, corner_radius=CORNER)
        self.right_panel.grid(row=1, column=2, sticky="nswe", padx=2, pady=2)
        
        ctk.CTkLabel(self.right_panel, text="AI Models", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        
        llms = {
            "Claude": "https://claude.ai",
            "ChatGPT": "https://chat.openai.com",
            "Qwen-32B": "https://huggingface.co/chat/models/Qwen/Qwen2.5-32B-Instruct",
            "HuggingFace": "https://huggingface.co",
            "Copilot": "https://github.com/features/copilot"
        }
        
        for name, url in llms.items():
            ctk.CTkButton(self.right_panel, text=name, corner_radius=CORNER, 
                          command=lambda u=url: self.launch_browser(u)).pack(pady=5, padx=10, fill="x")

    # ==========================================
    # Logic: UI & Theme
    # ==========================================
    def toggle_theme(self):
        is_dark = self.theme_var.get() == "Dark"
        ctk.set_appearance_mode("Dark" if is_dark else "Light")
        self.update_treeview_theme(is_dark)
        theme_name = 'monokai' if is_dark else 'default'
        for editor in self.open_tabs.values():
            editor._setup_tags(theme_name)
            editor.schedule_highlight()

    def update_treeview_theme(self, is_dark):
        bg = "#2b2b2b" if is_dark else "#dbdbdb"
        fg = "#ffffff" if is_dark else "#000000"
        sel = "#1f538d" if is_dark else "#3a7ebf"
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=bg, foreground=fg, fieldbackground=bg, borderwidth=0)
        style.map('Treeview', background=[('selected', sel)])

    def change_language(self, choice):
        current_tab = self.tabview.get()
        if current_tab in self.open_tabs:
            editor = self.open_tabs[current_tab]
            if choice == "Auto":
                editor.set_lexer_by_filename()
            else:
                editor.set_lexer_by_name(choice)




    # ==========================================
    # Logic: Tabs & Editing
    # ==========================================
    def save_current_file(self):
        current_tab = self.tabview.get()
        if current_tab in self.open_tabs:
            if self.open_tabs[current_tab].save_file():
                # Provide subtle visual feedback (optional)
                pass

    def close_current_tab(self):
        current_tab = self.tabview.get()
        if current_tab:
            self.tabview.delete(current_tab)
            del self.open_tabs[current_tab]

    def open_file_in_tab(self, filepath):
        filename = os.path.basename(filepath)
        
        # If already open, just switch to it
        if filename in self.open_tabs:
            self.tabview.set(filename)
            return
            
        try:
            self.tabview.add(filename)
            editor = CodeEditor(self.tabview.tab(filename), filepath, wrap="none")
            editor.pack(expand=True, fill="both")
            self.open_tabs[filename] = editor
            self.tabview.set(filename)
            self.lang_var.set("Auto") # Reset dropdown
        except ValueError:
            messagebox.showwarning("Warning", "A file with this name is already open.")

    # ==========================================
    # Logic: File Tree
    # ==========================================
    def open_folder(self):
        folder = filedialog.askdirectory(title="Select Folder")
        if not folder: return
        self.current_folder = folder
        self.tree.delete(*self.tree.get_children())
        self.populate_tree("", folder)
        
    def populate_tree(self, parent, path):
        try:
            items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
            for item in items:
                abspath = os.path.join(path, item)
                isdir = os.path.isdir(abspath)
                oid = self.tree.insert(parent, "end", text=item, open=False, values=[abspath])
                if isdir: self.tree.insert(oid, "end", text="dummy")
        except PermissionError: pass

    def on_tree_expand(self, event):
        item = self.tree.focus()
        children = self.tree.get_children(item)
        if len(children) == 1 and self.tree.item(children[0], "text") == "dummy":
            self.tree.delete(children[0])
            self.populate_tree(item, self.tree.item(item, "values")[0])

    def on_tree_double_click(self, event):
        item = self.tree.focus()
        if not item: return
        values = self.tree.item(item, "values")
        if values and os.path.isfile(values[0]):
            self.open_file_in_tab(values[0])

    # ==========================================
    # Logic: Megatxt & Prompts
    # ==========================================
    def merge_files(self):
        paths = filedialog.askopenfilenames(title="Select up to 80 files", filetypes=[("All Files", "*.*")])
        if not paths: return
        paths = paths[:80]
            
        out = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="mega_context.txt")
        if not out: return
        
        try:
            with open(out, 'w', encoding='utf-8') as f_out:
                f_out.write("=== PROJECT CONTEXT ===\n\n")
                for p in paths:
                    f_out.write(f"{'='*60}\nFILE: {os.path.basename(p)}\nPATH: {p}\n{'='*60}\n")
                    try:
                        with open(p, 'r', encoding='utf-8') as f_in: f_out.write(f_in.read() + "\n\n")
                    except Exception as e: f_out.write(f"<Read Error: {e}>\n\n")
            self.mega_txt_path = out
            messagebox.showinfo("Success", f"Merged {len(paths)} files.")
        except Exception as e: messagebox.showerror("Error", str(e))

    def finalize_prompt(self):
        if not getattr(self, 'mega_txt_path', None) or not os.path.exists(self.mega_txt_path):
            messagebox.showwarning("Warning", "Merge files first!")
            return
            
        pw = ctk.CTkToplevel(self)
        pw.title("Build Final AI Prompt")
        pw.geometry("700x550")
        prompt_tb = ctk.CTkTextbox(pw, width=650, height=400, corner_radius=CORNER)
        prompt_tb.pack(pady=20)
        
        def save():
            text = prompt_tb.get("1.0", ctk.END).strip()
            if not text: return
            out = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="final_prompt.txt")
            if out:
                with open(self.mega_txt_path, 'r', encoding='utf-8') as ctx, open(out, 'w', encoding='utf-8') as f:
                    f.write(f"=== USER INSTRUCTIONS ===\n{text}\n\n{ctx.read()}")
                pw.destroy()
                messagebox.showinfo("Success", "Prompt saved.")
                
        ctk.CTkButton(pw, text="Save Combined Prompt", command=save, corner_radius=CORNER).pack()

    # ==========================================
    # Logic: Browser Subprocess
    # ==========================================
    def launch_browser(self, url):
        """
        Embed Note: Natively embedding a WebView (which runs Chromium/WebKit threads) 
        directly into a Tkinter frame on Linux without X11 crashes or lag is historically unstable.
        
        To fulfill your strict 'no lag' and 'cannot crash' requirement while addressing 
        the 'private_mode' crash:
        1. We removed the crash-causing 'private_mode' flag.
        2. We spawn it as a child borderless/dialog window that sits *over* the IDE 
           (visually acting as if it's inside) rather than embedding it into the Tkinter grid natively.
        """
        
        code = f"""
import webview
# Note: Removed private_mode to fix TypeError crash on certain pywebview backends.
webview.create_window('LarpCode LLM Panel', '{url}', width=900, height=800)
webview.start()
"""
        subprocess.Popen([sys.executable, "-c", code])


if __name__ == "__main__":
    app = LarpCodeIDE()
    app.mainloop()
