import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import os
import sys


class BatRunnerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Inject")
        self.root.geometry("600x600")
        self.root.minsize(600, 400)

        self.lines = []
        self.running = False
        self.current_row = -1
        if getattr(sys, 'frozen', False):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.inject_path = os.path.join(self.script_dir, "inject.txt")

        self._build_ui()
        self.root.after(100, self._auto_load_and_run)

    def _build_ui(self):
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("status", "command")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("status", text="状态")
        self.tree.heading("command", text="命令")
        self.tree.column("status", width=60, anchor=tk.CENTER, stretch=False)
        self.tree.column("command", width=600, anchor=tk.W)

        vsb = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        output_frame = ttk.LabelFrame(self.root, text="输出日志", padding=5)
        output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        self.output_text = scrolledtext.ScrolledText(output_frame, height=8, state=tk.DISABLED, font=("Consolas", 9))
        self.output_text.pack(fill=tk.BOTH, expand=True)

        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill=tk.X, padx=5, pady=(0, 5))

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=3).pack(
            fill=tk.X, padx=5, pady=(0, 5)
        )

    def _load_inject(self):
        if not os.path.isfile(self.inject_path):
            self.status_var.set(f"未找到 inject.txt: {self.inject_path}")
            return False

        with open(self.inject_path, "r", encoding="gbk", errors="replace") as f:
            self.lines = f.readlines()

        for item in self.tree.get_children():
            self.tree.delete(item)

        for i, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if stripped and not stripped.startswith("@") and not stripped.lower().startswith("rem"):
                self.tree.insert("", tk.END, iid=str(i), values=("⏳", stripped))

        self.progress["value"] = 0
        self.status_var.set(f"已加载 inject.txt，共 {len(self.lines)} 行")
        return True

    def _auto_load_and_run(self):
        if self._load_inject():
            self._run()

    def _run(self):
        if self.running:
            return
        if not self.lines:
            self.status_var.set("inject.txt 为空或未加载")
            return

        self.running = True
        self.current_row = -1
        self._set_output("")

        for item in self.tree.get_children():
            self.tree.item(item, values=(self.tree.item(item, "values")[0].replace("✅", "⏳").replace("❌", "⏳"), *self.tree.item(item, "values")[1:]))

        total = len(self.tree.get_children())
        self.progress["maximum"] = total
        self.progress["value"] = 0

        threading.Thread(target=self._execute, daemon=True).start()

    def _execute(self):
        items = self.tree.get_children()
        total = len(items)

        for idx, item_id in enumerate(items):
            if not self.running:
                break

            values = self.tree.item(item_id, "values")
            command = values[1]
            self.root.after(0, self._highlight_row, item_id)

            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding="gbk",
                    errors="replace",
                    timeout=60,
                    cwd=self.script_dir,
                )
                success = result.returncode == 0
                output = result.stdout + result.stderr
            except subprocess.TimeoutExpired:
                success = False
                output = "执行超时（60秒）"
            except Exception as e:
                success = False
                output = str(e)

            status_icon = "✅" if success else "❌"
            self.root.after(0, self._update_row, item_id, status_icon, output)
            self.root.after(0, self._update_progress, idx + 1, total)

        self.running = False
        self.root.after(0, lambda: self.status_var.set("执行完成，即将退出..."))
        self.root.after(1500, self.root.destroy)

    def _highlight_row(self, item_id):
        self.tree.selection_set(item_id)
        self.tree.see(item_id)
        values = self.tree.item(item_id, "values")
        self.tree.item(item_id, values=("▶", *values[1:]))
        self.status_var.set(f"正在执行: {values[1]}")

    def _update_row(self, item_id, status_icon, output):
        values = self.tree.item(item_id, "values")
        self.tree.item(item_id, values=(status_icon, *values[1:]))
        if output.strip():
            self._append_output(f"{values[1]}\n{output.strip()}\n{'─' * 40}\n")

    def _update_progress(self, current, total):
        self.progress["value"] = current
        self.status_var.set(f"进度: {current}/{total}")

    def _stop(self):
        self.running = False

    def _set_output(self, text):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, text)
        self.output_text.config(state=tk.DISABLED)

    def _append_output(self, text):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)


if __name__ == "__main__":
    root = tk.Tk()
    app = BatRunnerApp(root)
    root.mainloop()
