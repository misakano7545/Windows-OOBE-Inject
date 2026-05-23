import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import os
import sys
import locale

COMMAND_TIMEOUT = 300


class BatRunnerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Inject")
        self.root.geometry("600x600")
        self.root.minsize(600, 400)

        self.lines = []
        self.running = False
        self.current_row = -1
        self.has_failure = False
        self.encoding = locale.getpreferredencoding(False) or "utf-8"
        if getattr(sys, 'frozen', False):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.inject_path = os.path.join(self.script_dir, "inject.txt")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._auto_load_and_run)

    def _on_close(self):
        self.running = False
        self._safe_destroy()

    def _safe_after(self, delay, func, *args):
        try:
            if self.root.winfo_exists():
                self.root.after(delay, func, *args)
        except tk.TclError:
            pass

    def _safe_destroy(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

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

        try:
            with open(self.inject_path, "r", encoding=self.encoding, errors="replace") as f:
                self.lines = f.readlines()
        except OSError as e:
            self.status_var.set(f"读取失败: {e}")
            return False

        for item in self.tree.get_children():
            self.tree.delete(item)

        for i, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("@") or stripped.startswith("::"):
                continue
            first_word = stripped.split(None, 1)[0].lower()
            if first_word == "rem":
                continue
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

        items = self.tree.get_children()
        if not items:
            self.status_var.set("没有可执行的命令")
            return

        tasks = []
        for item_id in items:
            values = self.tree.item(item_id, "values")
            tasks.append((item_id, values[1]))
            self.tree.item(item_id, values=("⏳", *values[1:]))

        self.running = True
        self.has_failure = False
        self.current_row = -1
        self._set_output("")

        total = len(tasks)
        self.progress["maximum"] = total
        self.progress["value"] = 0

        threading.Thread(target=self._execute, args=(tasks,), daemon=True).start()

    def _execute(self, tasks):
        total = len(tasks)

        for idx, (item_id, command) in enumerate(tasks):
            if not self.running:
                break

            self._safe_after(0, self._highlight_row, item_id, command)

            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding=self.encoding,
                    errors="replace",
                    timeout=COMMAND_TIMEOUT,
                    cwd=self.script_dir,
                )
                success = result.returncode == 0
                output = (result.stdout or "") + (result.stderr or "")
            except subprocess.TimeoutExpired:
                success = False
                output = f"执行超时（{COMMAND_TIMEOUT}秒）"
            except Exception as e:
                success = False
                output = str(e)

            if not success:
                self.has_failure = True

            status_icon = "✅" if success else "❌"
            self._safe_after(0, self._update_row, item_id, command, status_icon, output)
            self._safe_after(0, self._update_progress, idx + 1, total)

        self.running = False
        self._safe_after(0, self._finalize)

    def _finalize(self):
        if self.has_failure:
            self.status_var.set("执行完成（含失败项），10 秒后退出")
            self._safe_after(10000, self._safe_destroy)
        else:
            self.status_var.set("执行完成，即将退出...")
            self._safe_after(1500, self._safe_destroy)

    def _highlight_row(self, item_id, command):
        if not self.tree.exists(item_id):
            return
        self.tree.selection_set(item_id)
        self.tree.see(item_id)
        values = self.tree.item(item_id, "values")
        self.tree.item(item_id, values=("▶", *values[1:]))
        self.status_var.set(f"正在执行: {command}")

    def _update_row(self, item_id, command, status_icon, output):
        if not self.tree.exists(item_id):
            return
        values = self.tree.item(item_id, "values")
        self.tree.item(item_id, values=(status_icon, *values[1:]))
        if output.strip():
            self._append_output(f"{command}\n{output.strip()}\n{'─' * 40}\n")

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
