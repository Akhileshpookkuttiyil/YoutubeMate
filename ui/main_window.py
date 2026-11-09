import os
import tkinter as tk
from tkinter import ttk, filedialog
from config import DARK_COLORS, FONTS, APP_NAME, APP_VERSION, AUTH_BROWSER_DISPLAY_NAMES, ICON_PNG_PATH
from ui.components import Tooltip
from utils.file_utils import open_folder


def configure_styles(app):
    """Configures clean ttk styles for the modern dark theme."""
    app.colors = dict(DARK_COLORS)
    app.fonts = dict(FONTS)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    c = app.colors
    f = app.fonts

    app.root.configure(bg=c["bg"])

    # Base Frame & Label styles
    style.configure(".", background=c["bg"], foreground=c["text"], font=f["label"])
    style.configure("App.TFrame", background=c["bg"])
    style.configure(
        "Card.TFrame",
        background=c["card"],
        bordercolor=c["border"],
        lightcolor=c["border"],
        darkcolor=c["border"],
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "CardAlt.TFrame",
        background=c["card_alt"],
        bordercolor=c["border"],
        lightcolor=c["border"],
        darkcolor=c["border"],
        borderwidth=1,
        relief="solid",
    )

    # Typography styles
    style.configure("Header.TLabel", background=c["bg"], foreground=c["text"], font=f["title"])
    style.configure("HeaderIcon.TLabel", background=c["bg"])
    style.configure("Subheader.TLabel", background=c["bg"], foreground=c["secondary_text"], font=f["subtitle"])
    style.configure("CardTitle.TLabel", background=c["card"], foreground=c["text"], font=f["section"])
    style.configure("Body.TLabel", background=c["card"], foreground=c["text"], font=f["label"])
    style.configure("Muted.TLabel", background=c["card"], foreground=c["secondary_text"], font=f["label"])

    style.configure(
        "Badge.TLabel",
        background=c["badge_bg"],
        foreground=c["primary"],
        font=f["badge"],
        padding=(6, 2),
    )

    # Status styles
    style.configure("Status.TLabel", background=c["card"], foreground=c["secondary_text"], font=f["status"])
    style.configure("StatusSuccess.TLabel", background=c["card"], foreground=c["success"], font=f["status"])
    style.configure("StatusError.TLabel", background=c["card"], foreground=c["error"], font=f["status"])
    style.configure("StatusWarning.TLabel", background=c["card"], foreground=c["warning"], font=f["status"])

    # Progress and meta readout styles
    style.configure("Eta.TLabel", background=c["card"], foreground=c["secondary_text"], font=f["small"])
    style.configure("ProgressMeta.TLabel", background=c["card"], foreground=c["secondary_text"], font=f["small"])
    style.configure("ProgressValue.TLabel", background=c["card"], foreground=c["text"], font=f["section"])

    # Input entry styles
    style.configure(
        "TEntry",
        fieldbackground=c["entry_bg"],
        foreground=c["entry_fg"],
        bordercolor=c["border"],
        lightcolor=c["border"],
        darkcolor=c["border"],
        padding=6,
        font=f["input"],
    )
    style.map("TEntry", bordercolor=[("focus", c["primary"])])

    # Combobox styling
    style.configure(
        "TCombobox",
        fieldbackground=c["entry_bg"],
        background=c["card_alt"],
        foreground=c["entry_fg"],
        arrowcolor=c["text"],
        bordercolor=c["border"],
        darkcolor=c["border"],
        lightcolor=c["border"],
        padding=5,
        font=f["input"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", c["entry_bg"])],
        foreground=[("readonly", c["entry_fg"])],
        bordercolor=[("focus", c["primary"])],
    )

    # Button styles
    style.configure(
        "Primary.TButton",
        background=c["primary"],
        foreground="#FFFFFF",
        font=f["button"],
        borderwidth=0,
        padding=(16, 8),
    )
    style.map(
        "Primary.TButton",
        background=[("disabled", c["button_surface"]), ("active", c["primary_hover"])],
        foreground=[("disabled", c["secondary_text"])],
    )

    style.configure(
        "Action.TButton",
        background=c["primary"],
        foreground="#FFFFFF",
        font=f["button"],
        borderwidth=0,
        padding=(12, 6),
    )
    style.map(
        "Action.TButton",
        background=[("disabled", c["button_surface"]), ("active", c["primary_hover"])],
        foreground=[("disabled", c["secondary_text"])],
    )

    style.configure(
        "Cancel.TButton",
        background=c["error"],
        foreground="#FFFFFF",
        font=f["button"],
        borderwidth=0,
        padding=(14, 8),
    )
    style.map(
        "Cancel.TButton",
        background=[("disabled", c["button_surface"]), ("active", "#D32F2F")],
        foreground=[("disabled", c["secondary_text"])],
    )

    style.configure(
        "Secondary.TButton",
        background=c["button_surface"],
        foreground=c["text"],
        font=f["button"],
        bordercolor=c["border"],
        lightcolor=c["border"],
        darkcolor=c["border"],
        borderwidth=1,
        padding=(10, 5),
    )
    style.map(
        "Secondary.TButton",
        background=[("disabled", c["card_alt"]), ("active", c["button_hover"])],
        foreground=[("disabled", c["secondary_text"])],
    )

    # Progress bar styling
    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=c["progressbar_bg"],
        background=c["primary"],
        bordercolor=c["border"],
        lightcolor=c["primary"],
        darkcolor=c["primary_hover"],
        thickness=10,
    )


def create_ui_widgets(app):
    """Builds the modern responsive grid layout for YouTubeMate."""
    app.root.grid_rowconfigure(0, weight=1)
    app.root.grid_columnconfigure(0, weight=1)

    main_frame = ttk.Frame(app.root, style="App.TFrame", padding=(20, 16, 20, 16))
    main_frame.grid(row=0, column=0, sticky="nsew")
    main_frame.grid_columnconfigure(0, weight=1)

    current_row = 0

    # 1. Header Row
    header_frame = ttk.Frame(main_frame, style="App.TFrame")
    header_frame.grid(row=current_row, column=0, sticky="ew", pady=(0, 12))
    header_frame.grid_columnconfigure(0, weight=1)

    title_box = ttk.Frame(header_frame, style="App.TFrame")
    title_box.grid(row=0, column=0, sticky="w")

    has_header_icon = False
    if os.path.isfile(ICON_PNG_PATH):
        try:
            from PIL import Image, ImageTk
            with Image.open(ICON_PNG_PATH) as _raw_icon:
                icon_img = _raw_icon.resize((26, 26), Image.Resampling.LANCZOS)
                app._header_icon_photo = ImageTk.PhotoImage(icon_img)
            header_icon_lbl = ttk.Label(title_box, image=app._header_icon_photo, style="HeaderIcon.TLabel")
            header_icon_lbl.pack(side="left", padx=(0, 8))
            has_header_icon = True
        except Exception:
            has_header_icon = False

    header_title = APP_NAME if has_header_icon else f"🎥 {APP_NAME}"
    ttk.Label(title_box, text=header_title, style="Header.TLabel").pack(side="left")
    ttk.Label(title_box, text=f"v{APP_VERSION}", style="Badge.TLabel").pack(side="left", padx=(10, 0))

    dep_status = app.get_startup_status()
    dep_label = ttk.Label(header_frame, text=f"● {dep_status}", style="Subheader.TLabel")
    dep_label.grid(row=0, column=1, sticky="e")
    current_row += 1

    # 2. URL Input Card
    url_card = ttk.Frame(main_frame, style="Card.TFrame", padding=(16, 12))
    url_card.grid(row=current_row, column=0, sticky="ew", pady=(0, 10))
    url_card.grid_columnconfigure(1, weight=1)

    ttk.Label(url_card, text="YouTube URL:", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 10))
    app.url_entry = ttk.Entry(url_card, font=app.fonts["input"])
    app.url_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
    app.url_entry.bind("<Return>", lambda e: app.fetch_formats())
    Tooltip(app.url_entry, "Paste a YouTube video URL here and press Enter")

    app.fetch_btn = ttk.Button(url_card, text="Fetch Formats", style="Action.TButton", command=app.fetch_formats)
    app.fetch_btn.grid(row=0, column=2, sticky="e")
    Tooltip(app.fetch_btn, "Inspect video metadata and list available resolutions")

    # Optional Browser Authentication
    auth_frame = ttk.Frame(url_card, style="Card.TFrame")
    auth_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))

    ttk.Label(auth_frame, text="Browser Auth:", style="Body.TLabel").pack(side="left", padx=(0, 8))
    app.auth_browser_combo = ttk.Combobox(
        auth_frame,
        textvariable=getattr(app, 'auth_browser_value', None),
        values=AUTH_BROWSER_DISPLAY_NAMES,
        state="readonly",
        width=24,
    )
    app.auth_browser_combo.pack(side="left", padx=(0, 10))
    Tooltip(
        app.auth_browser_combo,
        "Optional: Use your existing signed-in browser session for age-restricted or private videos. Default: None (Unauthenticated)."
    )

    auth_hint = ttk.Label(
        auth_frame,
        text="Optional (for age-restricted or private videos)",
        style="Muted.TLabel",
    )
    auth_hint.pack(side="left")
    current_row += 1

    # 3. Video Metadata Preview Card
    app.meta_card = ttk.Frame(main_frame, style="Card.TFrame", padding=(14, 12))
    app.meta_card.grid(row=current_row, column=0, sticky="ew", pady=(0, 10))
    app.meta_card.grid_columnconfigure(1, weight=1)

    # Thumbnail Container
    app.thumb_frame = ttk.Frame(app.meta_card, style="CardAlt.TFrame", width=120, height=68)
    app.thumb_frame.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 14))
    app.thumb_frame.grid_propagate(False)

    app.thumb_label = ttk.Label(app.thumb_frame, text="No Preview", style="Muted.TLabel", anchor="center")
    app.thumb_label.place(relx=0.5, rely=0.5, anchor="center")

    # Metadata Details (Title, Channel, Duration, Views)
    app.meta_title_label = ttk.Label(
        app.meta_card,
        text="No video loaded. Enter a URL above and click 'Fetch Formats'.",
        style="CardTitle.TLabel",
        wraplength=580,
    )
    app.meta_title_label.grid(row=0, column=1, sticky="nw", pady=(0, 4))

    meta_row1 = ttk.Frame(app.meta_card, style="Card.TFrame")
    meta_row1.grid(row=1, column=1, sticky="w", pady=(0, 4))

    ttk.Label(meta_row1, text="Channel: ", style="Muted.TLabel").pack(side="left")
    app.meta_channel_label = ttk.Label(meta_row1, text="--", style="Body.TLabel")
    app.meta_channel_label.pack(side="left", padx=(0, 16))

    ttk.Label(meta_row1, text="Duration: ", style="Muted.TLabel").pack(side="left")
    app.meta_duration_label = ttk.Label(meta_row1, text="--:--", style="Body.TLabel")
    app.meta_duration_label.pack(side="left", padx=(0, 16))

    ttk.Label(meta_row1, text="Views: ", style="Muted.TLabel").pack(side="left")
    app.meta_views_label = ttk.Label(meta_row1, text="--", style="Body.TLabel")
    app.meta_views_label.pack(side="left")
    current_row += 1

    # 4. Download Controls Card
    controls_card = ttk.Frame(main_frame, style="Card.TFrame", padding=(16, 12))
    controls_card.grid(row=current_row, column=0, sticky="ew", pady=(0, 10))
    controls_card.grid_columnconfigure(1, weight=1)

    # Mode Selector
    ttk.Label(controls_card, text="Download Mode:", style="Body.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
    app.mode_combo = ttk.Combobox(
        controls_card,
        textvariable=app.download_mode_value,
        values=["Video (MP4 / WebM)", "Audio Only (M4A - No FFmpeg)", "Audio Only (MP3 - FFmpeg)"],
        state="readonly",
    )
    app.mode_combo.grid(row=0, column=1, columnspan=2, sticky="ew", pady=(0, 8))
    app.mode_combo.bind("<<ComboboxSelected>>", app.on_download_mode_changed)
    Tooltip(app.mode_combo, "Select whether to download full video, direct native audio (M4A), or converted MP3")

    # Format / Quality Selector
    ttk.Label(controls_card, text="Quality / Format:", style="Body.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
    app.format_combo = ttk.Combobox(controls_card, state="readonly")
    app.format_combo.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(0, 8))
    app.update_format_combo((), select_first=False)
    Tooltip(app.format_combo, "Select target video resolution or audio quality")

    # Output Destination Folder Row
    ttk.Label(controls_card, text="Save Destination:", style="Body.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 10))
    app.folder_label = ttk.Label(controls_card, text=app.output_folder, style="Muted.TLabel", anchor="w")
    app.folder_label.grid(row=2, column=1, sticky="ew", padx=(0, 8))

    btn_box = ttk.Frame(controls_card, style="Card.TFrame")
    btn_box.grid(row=2, column=2, sticky="e")

    browse_btn = ttk.Button(btn_box, text="Browse", style="Secondary.TButton", command=app.select_output_folder)
    browse_btn.pack(side="left", padx=(0, 6))
    Tooltip(browse_btn, "Choose a destination folder for downloaded files")

    open_btn = ttk.Button(btn_box, text="Open Folder", style="Secondary.TButton", command=app.open_output_folder)
    open_btn.pack(side="left")
    Tooltip(open_btn, "Open current output folder in Windows File Explorer")
    current_row += 1

    # 5. Progress Card
    progress_card = ttk.Frame(main_frame, style="Card.TFrame", padding=(16, 12))
    progress_card.grid(row=current_row, column=0, sticky="ew", pady=(0, 10))
    progress_card.grid_columnconfigure(0, weight=1)

    app.status_label = ttk.Label(progress_card, text="Ready", style="Status.TLabel")
    app.status_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

    app.progress_bar = ttk.Progressbar(
        progress_card,
        style="Horizontal.TProgressbar",
        mode="determinate",
        variable=app.progress_value,
        maximum=100.0,
    )
    app.progress_bar.grid(row=1, column=0, sticky="ew", pady=(0, 6))

    meta_row = ttk.Frame(progress_card, style="Card.TFrame")
    meta_row.grid(row=2, column=0, sticky="ew")
    meta_row.grid_columnconfigure(1, weight=1)

    app.percent_label = ttk.Label(meta_row, textvariable=app.progress_text, style="ProgressValue.TLabel")
    app.percent_label.grid(row=0, column=0, sticky="w")

    meta_right = ttk.Frame(meta_row, style="Card.TFrame")
    meta_right.grid(row=0, column=2, sticky="e")

    app.speed_label = ttk.Label(meta_right, textvariable=app.speed_value, style="ProgressMeta.TLabel")
    app.speed_label.pack(side="left", padx=(0, 12))

    app.eta_label = ttk.Label(meta_right, textvariable=app.eta_value, style="Eta.TLabel")
    app.eta_label.pack(side="left")

    app.warning_label = ttk.Label(progress_card, textvariable=app.warning_value, style="StatusWarning.TLabel")
    app.warning_label.grid(row=3, column=0, sticky="w", pady=(4, 0))
    current_row += 1

    # 6. Bottom Action Row
    actions_frame = ttk.Frame(main_frame, style="App.TFrame")
    actions_frame.grid(row=current_row, column=0, sticky="ew", pady=(4, 0))
    actions_frame.grid_columnconfigure(0, weight=1)

    actions_box = ttk.Frame(actions_frame, style="App.TFrame")
    actions_box.grid(row=0, column=1, sticky="e")

    app.cancel_btn = ttk.Button(actions_box, text="Cancel", style="Cancel.TButton", state="disabled", command=app.cancel_active_download)
    app.cancel_btn.pack(side="left", padx=(0, 10))
    Tooltip(app.cancel_btn, "Cancel active download and cleanly delete incomplete files")

    app.download_btn = ttk.Button(actions_box, text="Download Now", style="Primary.TButton", command=app.download_video)
    app.download_btn.pack(side="left")
    Tooltip(app.download_btn, "Start downloading the selected video or audio format")
