"""8.5-Inch 4:3 Phosphor-Green Retro HUD & VS-20501 Hardware Simulator (src/retro_hud.py)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, Static

from src.audio_router import DualMicRouter
from src.config import (
    HUD_ASPECT_RATIO,
    HUD_HEIGHT,
    HUD_WIDTH,
    PHOSPHOR_GREEN,
    PITCH_BLACK,
    WORKBENCH_DB_PATH,
)
from src.vern_agent import VernAgent
from src.vision_hub import VisionHub

HUD_MODES: tuple[str, str, str, str] = (
    "MODE_1_OSCILLOSCOPE",
    "MODE_2_PINOUT",
    "MODE_3_VISION_RETICLE",
    "MODE_4_SCREW_BUTLER",
)

HUD_MODE_TITLES: dict[str, str] = {
    "MODE_1_OSCILLOSCOPE": "MODE 1: OSCILLOSCOPE FACE (PHOSPHOR VOICE WAVEFORM)",
    "MODE_2_PINOUT": "MODE 2: PINOUT & SPEC FLASHCARD (3-FT BENCH HUD)",
    "MODE_3_VISION_RETICLE": "MODE 3: VISION TARGET RETICLE (DUAL-CAM SWITCHBOARD)",
    "MODE_4_SCREW_BUTLER": "MODE 4: SCREW BUTLER & TELEMETRY TOAST",
}


def render_oscilloscope_ascii(samples: list[float], width: int = 72, height: int = 13) -> str:
    """Render an animated #00FF66 CRT oscilloscope phosphor waveform grid."""
    grid = [[" " for _ in range(width)] for _ in range(height)]
    mid_y = height // 2

    # Draw subtle CRT graticule centerlines
    for x in range(width):
        grid[mid_y][x] = "─" if x % 4 != 0 else "┼"
    for y in range(height):
        grid[y][width // 2] = "│" if y != mid_y else "┼"

    if samples:
        for x in range(width):
            idx = min(len(samples) - 1, int((x / max(1, width - 1)) * len(samples)))
            val = max(-1.0, min(1.0, samples[idx]))
            y = int(round(mid_y - val * (mid_y - 1)))
            y = max(0, min(height - 1, y))
            grid[y][x] = "█"
            if y > 0 and abs(val) > 0.35:
                grid[y - 1 if val > 0 else min(height - 1, y + 1)][x] = "▓"

    border_top = "╔" + ("═" * width) + "╗"
    border_bot = "╚" + ("═" * width) + "╝"
    body = [f"║{''.join(row)}║" for row in grid]
    return "\n".join([border_top, *body, border_bot])


def render_mode_1_oscilloscope(agent: VernAgent, mic_router: DualMicRouter) -> str:
    samples = mic_router.sample_waveform_points(num_points=72, speaking=True)
    scope_art = render_oscilloscope_ascii(samples, width=72, height=11)
    hw = agent.hardware_state
    return (
        f"  [ VS-20501 CRT PHOSPHOR OSCILLOSCOPE — {HUD_WIDTH}x{HUD_HEIGHT} ({HUD_ASPECT_RATIO}) ]\n"
        f"{scope_art}\n\n"
        f"  V.E.R.N. AUDIO TELEMETRY LINK ({hw.active_mic}):\n"
        f'  "{hw.last_spoken_reply}"'
    )


def render_mode_2_pinout_flashcard(agent: VernAgent) -> str:
    hw = agent.hardware_state
    return (
        f"╔══════════════════════════════════════════════════════════════════════════╗\n"
        f"║  {hw.flashcard_title:<70}  ║\n"
        f"╠══════════════════════════════════════════════════════════════════════════╣\n"
        f"║  {hw.flashcard_banner:<70}  ║\n"
        f"╚══════════════════════════════════════════════════════════════════════════╝\n\n"
        f"{hw.flashcard_diagram}\n"
    )


def render_mode_3_vision_reticle(agent: VernAgent, vision_hub: VisionHub) -> str:
    zoom = vision_hub.zoom_level
    last_snap = vision_hub.snapshots[-1].summary if vision_hub.snapshots else "No dual snapshot captured yet (Press F14)"
    return (
        "  ┌───────────────────────────────────┐  ┌───────────────────────────────────┐\n"
        "  │ CAM 0: OVERHEAD WIDE VIDICON TUBE │  │ CAM 1: MACRO SCANNER ("
        f"{zoom:0.1f}x ZOOM)   │\n"
        "  │  .-----------------------------.  │  │       .-------------------.       │\n"
        "  │  | [PSU]      [TONE/PREAMP]    |  │  │       |     .-------.     |       │\n"
        "  │  |              ┌───┐          |  │  │       |     | Q101  |     |       │\n"
        "  │  |  [MAIN AMP]  │ + │ <--LOCK  |  │  │       |  ───┼──[+ ]─┼───  |       │\n"
        "  │  |              └───┘          |  │  │       |     |2SC458 |     |       │\n"
        "  │  '-----------------------------'  │  │       '-------------------'       │\n"
        "  │  RES: 768x768 TILE | LIVE 30 FPS  │  │  1.5s DWELL-TO-INSPECT: ARMED     │\n"
        "  └───────────────────────────────────┘  └───────────────────────────────────┘\n"
        f"  >> LAST CAPTURE: {last_snap}"
    )


def render_mode_4_screw_butler_toast(agent: VernAgent, unit_id: int | None = None) -> str:
    bins = agent.db.get_screw_bins(unit_id)
    telemetry = agent.db.get_test_telemetry(unit_id) if unit_id else []
    latest_t = telemetry[-1] if telemetry else None

    bin_lines = []
    for b in bins:
        bin_lines.append(
            f"  ║  [{b['bin_label']}]  COUNT: {b['screw_count']:>2} pcs  │ {b['description']:<36} │ {b['tray_state']:<9} ║"
        )

    if latest_t:
        dbt_str = (
            f"DBT: {latest_t['dbt_status']}  |  B+ RAIL: {latest_t['b_plus_vdc'] or 0.0:.1f} VDC  |  "
            f"120Hz RIPPLE: {latest_t['ripple_vac_120hz'] or 0.0:.3f} VAC"
        )
    else:
        dbt_str = f"DBT BEACON: {agent.hardware_state.beacon_color}  |  B+ RAIL: 56.4 VDC (NOMINAL)  |  120Hz RIPPLE: 0.015 VAC"

    return (
        "  ╔════════════════════════════════════════════════════════════════════════════╗\n"
        "  ║             MOTORIZED 'SCREW BUTLER' MAGNETIC STAGE TRAY AUDIT             ║\n"
        "  ╠════════════════════════════════════════════════════════════════════════════╣\n"
        + "\n".join(bin_lines)
        + "\n"
        "  ╠════════════════════════════════════════════════════════════════════════════╣\n"
        f"  ║  {dbt_str:<74}║\n"
        "  ╚════════════════════════════════════════════════════════════════════════════╝\n\n"
        f'  V.E.R.N.: "{agent.hardware_state.last_spoken_reply}"'
    )


def format_hardware_status_bar(agent: VernAgent, vision_hub: VisionHub) -> str:
    hw = agent.hardware_state
    return (
        f" [SERVO ARM: {hw.arm_emote.upper()}]  │  "
        f"[SCREW TRAY: {hw.tray_state}]  │  "
        f"[TURRET BEACON: {hw.beacon_color}]  │  "
        f"[MIC: {hw.active_mic}]  │  "
        f"[ZOOM: {vision_hub.zoom_level:.1f}x]\n"
        " KEYS: '[' Left Dial (Cycle Mode) | ']' Right Dial (Zoom/Rack) | 'Space' Screw Tray | 'F14' Foot Pedal Dual-Cam"
    )


class VernRetroHudApp(App[None]):
    """Textual 4:3 Phosphor-Green (#00FF66 on #000000) HUD & VS-20501 Hardware Simulator."""

    TITLE = f"V.E.R.N. (Model VS-20501) — {HUD_WIDTH}x{HUD_HEIGHT} ({HUD_ASPECT_RATIO}) Phosphor HUD"
    CSS = f"""
    Screen {{
        background: {PITCH_BLACK};
        color: {PHOSPHOR_GREEN};
        align: center middle;
    }}
    #hud-frame {{
        width: 92;
        height: 34;
        border: double {PHOSPHOR_GREEN};
        background: {PITCH_BLACK};
        color: {PHOSPHOR_GREEN};
        padding: 0 1;
    }}
    #mode-banner {{
        width: 100%;
        height: 3;
        content-align: center middle;
        text-style: bold;
        border-bottom: solid {PHOSPHOR_GREEN};
        color: {PHOSPHOR_GREEN};
        background: {PITCH_BLACK};
    }}
    #main-viewport {{
        width: 100%;
        height: 20;
        padding: 1 1;
        color: {PHOSPHOR_GREEN};
        background: {PITCH_BLACK};
    }}
    #bench-input {{
        width: 100%;
        border: solid {PHOSPHOR_GREEN};
        background: {PITCH_BLACK};
        color: {PHOSPHOR_GREEN};
    }}
    #hw-status-bar {{
        width: 100%;
        height: 4;
        border-top: solid {PHOSPHOR_GREEN};
        color: {PHOSPHOR_GREEN};
        background: {PITCH_BLACK};
        content-align: left middle;
    }}
    """

    BINDINGS = [
        Binding("left_square_bracket", "left_neck_dial", "Left Dial (Mode)"),
        Binding("right_square_bracket", "right_neck_dial", "Right Dial (Zoom/Rack)"),
        Binding("space", "toggle_screw_tray", "Screw Tray Toggle"),
        Binding("f14", "foot_pedal_capture", "Foot Pedal Dual-Cam"),
        Binding("f1", "demo_2sc458", "2SC458 Guardrail"),
        Binding("f2", "demo_dbt_short", "DBT Short Fault"),
        Binding("m", "toggle_mic", "Failover Mic"),
        Binding("q", "quit", "Exit Bench"),
    ]

    current_mode_index: reactive[int] = reactive(0)

    def __init__(self, db_path: str | Path | None = None) -> None:
        super().__init__()
        self.agent = VernAgent(db_path=db_path or WORKBENCH_DB_PATH)
        self.mic_router = DualMicRouter()
        self.vision_hub = VisionHub()
        self.active_unit_id = self._ensure_demo_unit()

    def _ensure_demo_unit(self) -> int:
        units = self.agent.db.list_units()
        if units:
            return int(units[0]["unit_id"])
        uid = self.agent.db.create_unit(
            brand="Kenwood",
            model="KA-6000",
            serial_number="610492",
            manual_local_path="G:/My Drive/Vintage_Audio_Manuals/Kenwood_KA-6000.pdf",
        )
        self.agent.db.update_screw_bin(
            "Bin A",
            unit_id=uid,
            screw_count=6,
            description="Faceplate & Walnut Side Panel M4 Screws",
        )
        return uid

    def compose(self) -> ComposeResult:
        with Container(id="hud-frame"):
            yield Static(id="mode-banner")
            yield Static(id="main-viewport")
            yield Input(
                placeholder="Ask V.E.R.N. (e.g. 'Check 2SC458 on KA-6000', 'DBT remains brightly lit', 'CEANL 80V cap')...",
                id="bench-input",
            )
            yield Static(id="hw-status-bar")

    def on_mount(self) -> None:
        self.refresh_hud_widgets()
        self.set_interval(0.25, self._tick_oscilloscope)

    def _tick_oscilloscope(self) -> None:
        if self.agent.hardware_state.hud_mode == "MODE_1_OSCILLOSCOPE":
            self.refresh_hud_widgets()

    def refresh_hud_widgets(self) -> None:
        mode = self.agent.hardware_state.hud_mode
        title = HUD_MODE_TITLES.get(mode, mode)
        self.query_one("#mode-banner", Static).update(
            f"V.E.R.N. VS-20501 ({HUD_WIDTH}x{HUD_HEIGHT} 4:3)  —  {title}"
        )

        if mode == "MODE_1_OSCILLOSCOPE":
            body = render_mode_1_oscilloscope(self.agent, self.mic_router)
        elif mode == "MODE_2_PINOUT":
            body = render_mode_2_pinout_flashcard(self.agent)
        elif mode == "MODE_3_VISION_RETICLE":
            body = render_mode_3_vision_reticle(self.agent, self.vision_hub)
        else:
            body = render_mode_4_screw_butler_toast(self.agent, self.active_unit_id)

        self.query_one("#main-viewport", Static).update(body)
        self.query_one("#hw-status-bar", Static).update(
            format_hardware_status_bar(self.agent, self.vision_hub)
        )

    def action_left_neck_dial(self) -> None:
        """Left rotary neck dial ('['): cycle through the 4 HUD modes."""
        curr = self.agent.hardware_state.hud_mode
        idx = HUD_MODES.index(curr) if curr in HUD_MODES else 0
        next_mode = HUD_MODES[(idx + 1) % len(HUD_MODES)]
        self.agent.control_vern_hardware(hud_mode=next_mode)
        self.refresh_hud_widgets()

    def action_right_neck_dial(self) -> None:
        """Right rotary neck dial (']'): zoom macro camera feed or rack screw tray."""
        new_zoom = self.vision_hub.adjust_macro_zoom(0.5)
        if new_zoom >= 5.0:
            self.vision_hub.zoom_level = 1.0
        self.agent.hardware_state.zoom_level = self.vision_hub.zoom_level
        self.agent.control_vern_hardware(arm_emote="inspect_focus")
        self.refresh_hud_widgets()

    def action_toggle_screw_tray(self) -> None:
        """Spacebar: extend or retract the Motorized Screw Butler magnetic tray."""
        new_state = (
            "EXTENDED" if self.agent.hardware_state.tray_state == "RETRACTED" else "RETRACTED"
        )
        emote = "present_tray" if new_state == "EXTENDED" else "idle"
        self.agent.control_vern_hardware(
            hud_mode="MODE_4_SCREW_BUTLER",
            tray_state=new_state,
            arm_emote=emote,
        )
        self.refresh_hud_widgets()

    def action_foot_pedal_capture(self) -> None:
        """F14 USB Foot Pedal: trigger synchronized Dual-Cam Snapshot."""
        snap = self.vision_hub.capture_synchronized_dual_frame(trigger_source="F14_FOOT_PEDAL")
        self.agent.hardware_state.last_spoken_reply = (
            f"Captured synchronized frames from the overhead vidicon tube and macro scanner at {snap.zoom_level:.1f}x! "
            "Ready to inspect solder joints and silkscreen orientation."
        )
        self.agent.control_vern_hardware(
            hud_mode="MODE_3_VISION_RETICLE",
            arm_emote="inspect_focus",
        )
        self.refresh_hud_widgets()

    def action_toggle_mic(self) -> None:
        """Simulate RØDE Wireless GO III TX1 to VS-20501 Shotgun Mic failover."""
        new_mic = self.mic_router.toggle_mic_source()
        self.agent.control_vern_hardware(active_mic=new_mic)
        self.refresh_hud_widgets()

    def action_demo_2sc458(self) -> None:
        self.agent.process_bench_command(
            "Check 2SC458D replacement on Kenwood KA-6000 phono preamp",
            unit_id=self.active_unit_id,
            prefer_cloud=False,
        )
        self.refresh_hud_widgets()

    def action_demo_dbt_short(self) -> None:
        self.agent.process_bench_command(
            "Dim bulb tester remains brightly lit on power up!",
            unit_id=self.active_unit_id,
            prefer_cloud=False,
        )
        self.refresh_hud_widgets()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
        event.input.value = ""
        self.agent.process_bench_command(
            query,
            unit_id=self.active_unit_id,
            prefer_cloud=bool(self.agent.api_key),
        )
        self.refresh_hud_widgets()


def run_tkinter_1024x768_window(db_path: str | Path | None = None) -> None:
    """Launch a pixel-exact 1024x768 (4:3) #00FF66-on-#000000 desktop window for the VS-20501 screen."""
    import tkinter as tk

    agent = VernAgent(db_path=db_path or WORKBENCH_DB_PATH)
    mic_router = DualMicRouter()
    vision_hub = VisionHub()
    units = agent.db.list_units()
    unit_id = (
        int(units[0]["unit_id"])
        if units
        else agent.db.create_unit("Kenwood", "KA-6000", "610492")
    )

    root = tk.Tk()
    root.title(f"V.E.R.N. (Model VS-20501) — {HUD_WIDTH}x{HUD_HEIGHT} (4:3) Phosphor HUD")
    root.geometry(f"{HUD_WIDTH}x{HUD_HEIGHT}")
    root.configure(bg=PITCH_BLACK)
    root.resizable(False, False)

    header_lbl = tk.Label(
        root,
        text="",
        fg=PHOSPHOR_GREEN,
        bg=PITCH_BLACK,
        font=("Consolas", 14, "bold"),
        pady=10,
    )
    header_lbl.pack(fill=tk.X)

    viewport_lbl = tk.Label(
        root,
        text="",
        fg=PHOSPHOR_GREEN,
        bg=PITCH_BLACK,
        font=("Consolas", 12),
        justify=tk.LEFT,
        anchor="nw",
        padx=24,
        pady=12,
    )
    viewport_lbl.pack(fill=tk.BOTH, expand=True)

    entry_frame = tk.Frame(root, bg=PITCH_BLACK, padx=24, pady=6)
    entry_frame.pack(fill=tk.X)
    tk.Label(
        entry_frame,
        text="BENCH CMD > ",
        fg=PHOSPHOR_GREEN,
        bg=PITCH_BLACK,
        font=("Consolas", 12, "bold"),
    ).pack(side=tk.LEFT)
    cmd_entry = tk.Entry(
        entry_frame,
        fg=PHOSPHOR_GREEN,
        bg="#05140A",
        insertbackground=PHOSPHOR_GREEN,
        font=("Consolas", 12),
    )
    cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    status_lbl = tk.Label(
        root,
        text="",
        fg=PHOSPHOR_GREEN,
        bg=PITCH_BLACK,
        font=("Consolas", 10, "bold"),
        pady=10,
    )
    status_lbl.pack(fill=tk.X, side=tk.BOTTOM)

    def refresh_view() -> None:
        mode = agent.hardware_state.hud_mode
        header_lbl.config(text=f"V.E.R.N. VS-20501 [{HUD_WIDTH}x{HUD_HEIGHT} 4:3] — {HUD_MODE_TITLES.get(mode, mode)}")
        if mode == "MODE_1_OSCILLOSCOPE":
            body = render_mode_1_oscilloscope(agent, mic_router)
        elif mode == "MODE_2_PINOUT":
            body = render_mode_2_pinout_flashcard(agent)
        elif mode == "MODE_3_VISION_RETICLE":
            body = render_mode_3_vision_reticle(agent, vision_hub)
        else:
            body = render_mode_4_screw_butler_toast(agent, unit_id)
        viewport_lbl.config(text=body)
        status_lbl.config(text=format_hardware_status_bar(agent, vision_hub))

    def on_left_dial(_event: Any = None) -> None:
        curr = agent.hardware_state.hud_mode
        idx = HUD_MODES.index(curr) if curr in HUD_MODES else 0
        agent.control_vern_hardware(hud_mode=HUD_MODES[(idx + 1) % len(HUD_MODES)])
        refresh_view()

    def on_right_dial(_event: Any = None) -> None:
        z = vision_hub.adjust_macro_zoom(0.5)
        if z >= 5.0:
            vision_hub.zoom_level = 1.0
        agent.hardware_state.zoom_level = vision_hub.zoom_level
        refresh_view()

    def on_space(_event: Any = None) -> None:
        if root.focus_get() == cmd_entry:
            return
        new_state = "EXTENDED" if agent.hardware_state.tray_state == "RETRACTED" else "RETRACTED"
        agent.control_vern_hardware(hud_mode="MODE_4_SCREW_BUTLER", tray_state=new_state, arm_emote="present_tray")
        refresh_view()

    def on_f14(_event: Any = None) -> None:
        vision_hub.capture_synchronized_dual_frame("F14_FOOT_PEDAL")
        agent.control_vern_hardware(hud_mode="MODE_3_VISION_RETICLE", arm_emote="inspect_focus")
        refresh_view()

    def on_submit(_event: Any = None) -> None:
        q = cmd_entry.get().strip()
        if q:
            cmd_entry.delete(0, tk.END)
            agent.process_bench_command(q, unit_id=unit_id, prefer_cloud=bool(agent.api_key))
            refresh_view()

    root.bind("[", on_left_dial)
    root.bind("]", on_right_dial)
    root.bind("<space>", on_space)
    root.bind("<F14>", on_f14)
    cmd_entry.bind("<Return>", on_submit)

    def tick() -> None:
        if agent.hardware_state.hud_mode == "MODE_1_OSCILLOSCOPE":
            refresh_view()
        root.after(250, tick)

    refresh_view()
    root.after(250, tick)
    root.mainloop()


def run_self_test_demo(db_path: str | Path | None = None) -> int:
    """Execute an end-to-end bench verification across all 4 HUD modes and guardrails."""
    agent = VernAgent(db_path=db_path or WORKBENCH_DB_PATH)
    mic = DualMicRouter()
    vision = VisionHub()
    unit_id = agent.db.create_unit("Kenwood", "KA-6000", "610492")

    print("=" * 78)
    print(f" V.E.R.N. (Model VS-20501) — {HUD_WIDTH}x{HUD_HEIGHT} (4:3) HUD & Bench Self-Test")
    print("=" * 78)

    print("\n--- [1] MODE 1: OSCILLOSCOPE FACE (Default) ---")
    print(render_mode_1_oscilloscope(agent, mic))

    print("\n--- [2] MODE 2: 2SC458 X-172 TOMBSTONE PINOUT FLASHCARD ---")
    agent.process_bench_command(
        "Check 2SC458D replacement on Kenwood KA-6000 phono preamp",
        unit_id=unit_id,
        prefer_cloud=False,
    )
    print(render_mode_2_pinout_flashcard(agent))

    print("\n--- [3] MODE 3: VISION TARGET RETICLE (F14 Dual-Cam Capture) ---")
    vision.adjust_macro_zoom(1.5)
    vision.capture_synchronized_dual_frame("F14_FOOT_PEDAL")
    agent.control_vern_hardware(hud_mode="MODE_3_VISION_RETICLE")
    print(render_mode_3_vision_reticle(agent, vision))

    print("\n--- [4] MODE 4: SCREW BUTLER & DBT TELEMETRY TOAST ---")
    agent.process_bench_command(
        "Extend Screw Butler Bin A and check Dim Bulb Tester bright flash then dims to faint glow",
        unit_id=unit_id,
        prefer_cloud=False,
    )
    agent.control_vern_hardware(
        hud_mode="MODE_4_SCREW_BUTLER",
        tray_state="EXTENDED",
        bin_label="Bin A",
        screw_count=6,
        screw_description="Kenwood KA-6000 Faceplate M4 Screws",
        unit_id=unit_id,
    )
    print(render_mode_4_screw_butler_toast(agent, unit_id))
    print("\n--- [BOTTOM HARDWARE SIMULATOR STATUS BAR] ---")
    print(format_hardware_status_bar(agent, vision))
    print("=" * 78)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="V.E.R.N. (Model VS-20501) 8.5-Inch 4:3 Phosphor-Green HUD & Hardware Simulator"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run non-interactive 4-mode HUD & guardrail bench demonstration and exit.",
    )
    parser.add_argument(
        "--window",
        action="store_true",
        help="Launch pixel-exact 1024x768 (4:3) Tkinter Phosphor-Green desktop window.",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test_demo()
    if args.window:
        run_tkinter_1024x768_window()
        return 0

    app = VernRetroHudApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
