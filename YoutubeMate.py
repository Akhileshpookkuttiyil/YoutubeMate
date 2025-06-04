import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import yt_dlp
import os


class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎥 YouTube High-Quality Downloader")
        self.root.geometry("650x400")
        self.root.resizable(False, False)

        self.formats = []
        self.output_folder = os.getcwd()

        self.create_widgets()

    def create_widgets(self):
        # Main Frame
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill="both", expand=True)

        # Title
        title_label = ttk.Label(main_frame, text="YouTube High-Quality Downloader", font=("Segoe UI", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # URL Entry
        ttk.Label(main_frame, text="YouTube Video URL:").grid(row=1, column=0, sticky="w", pady=5)
        self.url_entry = ttk.Entry(main_frame, width=60)
        self.url_entry.grid(row=1, column=1, columnspan=2, sticky="ew", pady=5)

        # Output Folder Selector
        ttk.Label(main_frame, text="Output Folder:").grid(row=2, column=0, sticky="w", pady=5)
        self.folder_label = ttk.Label(main_frame, text=self.output_folder, width=45)
        self.folder_label.grid(row=2, column=1, sticky="w", pady=5)
        ttk.Button(main_frame, text="Browse", command=self.select_output_folder).grid(row=2, column=2, sticky="e", pady=5)

        # Fetch Formats Button
        self.fetch_btn = ttk.Button(main_frame, text="Fetch Formats", command=self.fetch_formats)
        self.fetch_btn.grid(row=3, column=0, columnspan=3, pady=15, sticky="ew")

        # Format Combo
        ttk.Label(main_frame, text="Available Formats:").grid(row=4, column=0, sticky="w", pady=5)
        self.format_combo = ttk.Combobox(main_frame, state="readonly", width=57)
        self.format_combo.grid(row=4, column=1, columnspan=2, sticky="ew", pady=5)

        # Download Button
        self.download_btn = ttk.Button(main_frame, text="Download", command=self.download_video)
        self.download_btn.grid(row=5, column=0, columnspan=3, pady=15, sticky="ew")

        # Status Label
        self.status_label = ttk.Label(main_frame, text="", foreground="blue", anchor="center")
        self.status_label.grid(row=6, column=0, columnspan=3, pady=10)

        # Configure column resizing
        main_frame.columnconfigure(1, weight=1)

    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            self.folder_label.config(text=folder)

    def fetch_formats(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Input Required", "Please enter a YouTube URL.")
            return

        def _fetch():
            self.fetch_btn.config(state="disabled")
            self.download_btn.config(state="disabled")
            self.status_label.config(text="Fetching formats...")
            self.formats.clear()

            ydl_opts = {'quiet': True, 'skip_download': True}

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    for f in info.get('formats', []):
                        if f.get('vcodec') != 'none' and f.get('acodec') == 'none' and f.get('height', 0) >= 720:
                            label = f"{f['format_id']} - {f['height']}p - {f['ext']}"
                            self.formats.append((label, f['format_id']))

                    if not self.formats:
                        self.status_label.config(text="No high-quality formats found.")
                        return

                    self.format_combo['values'] = [f[0] for f in self.formats]
                    self.format_combo.current(0)
                    self.status_label.config(text="Formats loaded.")
            except Exception as e:
                self.status_label.config(text="Failed to fetch formats.")
                messagebox.showerror("Error", str(e))
            finally:
                self.fetch_btn.config(state="normal")
                self.download_btn.config(state="normal")

        threading.Thread(target=_fetch).start()

    def download_video(self):
        url = self.url_entry.get().strip()
        if not url or not self.formats:
            messagebox.showwarning("Missing Info", "Enter URL and select a format.")
            return

        if self.format_combo.current() == -1:
            messagebox.showwarning("No Format Selected", "Please select a format to download.")
            return

        selected_format_id = self.formats[self.format_combo.current()][1]

        def _download():
            self.fetch_btn.config(state="disabled")
            self.download_btn.config(state="disabled")
            self.status_label.config(text="Starting download...")

            def progress_hook(d):
                if d['status'] == 'downloading':
                    percent = d.get('_percent_str', '').strip()
                    speed = d.get('_speed_str', '')
                    eta = d.get('_eta_str', '')
                    self.status_label.config(text=f"Downloading:{percent}|Speed:{speed}|ETA:{eta}")
                elif d['status'] == 'finished':
                    self.status_label.config(text="Download finished. Merging...")

            ydl_opts = {
                'format': f"{selected_format_id}+bestaudio",
                'outtmpl': os.path.join(self.output_folder, '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'quiet': True,
                'progress_hooks': [progress_hook],
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                self.status_label.config(text="Download complete.")
                messagebox.showinfo("Success", "Video downloaded successfully!")
            except Exception as e:
                self.status_label.config(text="Download failed.")
                messagebox.showerror("Error", str(e))
            finally:
                self.fetch_btn.config(state="normal")
                self.download_btn.config(state="normal")

        threading.Thread(target=_download).start()


# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()
