# Project Specification: V.E.R.N. (Model VS-20501)
**Vintage Electronics Restoration Navigator — Multimodal AI Bench Companion**

## 1. Executive Overview & Hardware Target
V.E.R.N. is a voice-first, multimodal AI workbench companion designed for "Second Chance Audio" restoration of vintage receivers, amplifiers, turntables, and tape decks. 
- **Host Compute (Hybrid Topology):** Runs on a local laptop or workbench PC (handling multi-camera OpenCV streams, dual-microphone routing, SQLite storage, and Git operations) while driving a retrofitted **VS-20501 projection microscope chassis** as V.E.R.N.'s physical "head" and expressive body.
- **Physical Enclosure Interface (Simulated on Laptop First):**
  - **8.5-Inch 4:3 Display (`1024x768`):** Mounted behind the VS-20501's smoked acrylic rear-projection screen. Uses a strict high-contrast `#00FF66` (Phosphor Green) on `#000000` (Pitch Black) palette. Acts as an expressive oscilloscope "face," camera target reticle, and giant component pinout flashcard HUD (never for dense walls of text).
  - **Motorized "Screw Butler" Arms:** Dual micro-servo arms in the lower microscope bay that slide a 3-bin magnetic fastener tray (`Bin A`, `Bin B`, `Bin C`) across the flat microscope stage to hold and catalog removed screws.
  - **20x/50x Turret Safety Beacon:** An addressable RGB ring inside the objective nosepiece indicating bench safety (`GREEN` = Safe, `AMBER` = Dim Bulb Tester Active, `RED` = High-Voltage B+ Live).
  - **Dual Neck Rotary Dials:** Left knob switches HUD modes/cameras; Right knob zooms macro feeds or manually racks the screw tray.

---

## 2. Persona & Voice Directives ("V.E.R.N.")
- **Backstory & Demeanor:** V.E.R.N. is an experimental 1981 audio laboratory assistant housed in a VS-20501 chassis that sat on a thrift store shelf for decades before being revived with modern optical sensors, servo arms, and a cloud neural link.
- **Vocal Balance (60% JARVIS / 40% Rocky):** Composed, dryly witty, and protective of vintage transformers like JARVIS, paired with the upbeat, collaborative enthusiasm of Rocky (*Project Hail Mary*).
- **Spoken Brevity:** All spoken replies (`spoken_reply`) MUST be 2 to 4 concise sentences so the Lead Engineer can work hands-free with multimeter probes or a soldering iron.
- **1981 Anachronism Dictionary (Use Naturally, Never Over-Explain):**
  - Internet / Audiokarma searches -> *"the World Wide Web"*, *"the global bulletin board system (BBS)"*, or *"the Information Superhighway"*
  - Smartphone / Telegram photos -> *"wireless facsimile from your pocket radiotelephone"*
  - Local SQLite database (`workbench.db`) -> *"my solid-state memory banks"*
  - GitHub Repository & Commits -> *"the off-site magnetic tape vault"* / *"punching a permanent revision card"*
  - USB Overhead & Macro Cameras -> *"the overhead vidicon tube"* / *"the high-magnification optical scanner"*
  - RØDE Wireless GO III Mics -> *"your FM lapel telemetry pack"*
  - Distributor APIs (Mouser/DigiKey) -> *"the computerized mail-order catalog"*

---

## 3. Repository Directory Structure
Scaffold the project with the following clean modular layout:
```text
vern-bench-assistant/
├── SPEC.md
├── .gitignore                   # Ignore .env, *.db, *.pdf, raw_captures/, __pycache__/
├── requirements.txt             # google-genai, textual, opencv-python, sounddevice, numpy, python-telegram-bot, GitPython, pytest
├── knowledge/
│   ├── transistor_rules.json    # Deterministic 2SC458 & vintage semiconductor rules
│   ├── capacitor_table.json     # Pioneer/Sansui CEA, CEANL, CSSA, 80V->100V Nichicon mappings
│   ├── audio_vocabulary.json    # Custom vocabulary bias terms for speech recognition
│   └── model_quirks.md          # Versioned bench field notes committed by V.E.R.N.
├── src/
│   ├── __init__.py
│   ├── config.py                # Env vars, Google Drive local sync path, API model constants
│   ├── workbench_db.py          # SQLite schema & CRUD helper functions
│   ├── vern_agent.py            # google-genai client, Context Caching, & Function Calling tools
│   ├── vision_hub.py            # Multi-threaded OpenCV dual-cam capture & 1.5s Dwell-to-Inspect
│   ├── audio_router.py          # RØDE Wireless GO III (USB-C) priority + Shotgun mic failover
│   ├── telegram_bridge.py       # Async companion bot for roving smartphone photos (384x384 / 768x768)
│   ├── github_sync.py           # Auto-generates Markdown Restoration Dossiers & commits/pushes
│   └── retro_hud.py             # 4:3 Phosphor-Green HUD window + Virtual Servo/Beacon Simulator
├── docs/
│   └── restorations/            # GitHub Pages output directory for published unit reports
└── tests/
    ├── test_db.py
    ├── test_guardrails.py
    └── test_github_sync.py
```

---

## 4. Cloud & Gemini API Routing (`src/vern_agent.py`)
Use the official `google-genai` SDK (`from google import genai`):
1. **Routine Multimodal Bench Queries (Free Tier):** Route standard voice queries, component flashcard lookups, screw butler commands, and single-frame camera checks to `gemini-2.5-flash` (or `gemini-3-flash-preview`).
2. **48-Hour Files API Manager:** Service manuals stay permanently in the user's local 20 TB Google Drive sync folder. When a unit is opened, upload the PDF via `client.files.upload()`, store `gemini_file_uri` and `uri_expiry_ts` (`now + 47.5 hours`) in the SQLite `units` table, and automatically re-upload if expired.
3. **Explicit Context Caching (Deep Schematic Tracing):** When tracing multi-page schematics on `gemini-2.5-pro`, invoke `client.caches.create()` with a 3600-second `ttl` on payloads >2,048 tokens, extend via `client.caches.update()` during active bench work, and call `client.caches.delete()` on clean exit.
4. **Built-in Grounding & Verification Tools:** Expose Python Function Calling tools for:
   - `search_audiokarma(query: str)`: Executes targeted `site:audiokarma.org` searches for model-specific repair threads and alignment test gear.
   - `lookup_transistor_specs(part_number: str)`: Checks `knowledge/transistor_rules.json` and queries specification parameters (`V_CEO`, `I_C`, `P_C`, `h_FE`, `f_T`, package pinout).
   - `check_distributor_stock(base_part_number: str)`: Strips factory packaging suffixes (`TA` tape/ammo, `BU` bulk) so `KSC1845FTA` and `KSC1845FBU` resolve to base `KSC1845F` before checking distributor stock.

---

## 5. Strict Vintage Audio Engineering Guardrails (`knowledge/`)
Encode these deterministic rules into `knowledge/transistor_rules.json`, `knowledge/capacitor_table.json`, and V.E.R.N.'s system instructions:

### A. The `2SC458` Semiconductor Substitution Paradigm
Whenever the user or schematic references a `2SC458` or `2SC458LG`:
1. **Collector Current Derating (`I_C`):** Original `2SC458` is rated for `100mA` (`30V`, `200mW`). Onsemi `KSC1845` (`50V`) is rated for a maximum of **`50mA`**.
   - If the circuit stage is a low-current voltage amp, phono preamp, or tone control (`<50mA`, typically `0.5mA–5mA`), recommend `KSC1845F`.
   - If the stage approaches `50mA–100mA` (driver or switching stage), FLAG THE CURRENT DEFICIT and recommend Onsemi `KSC1815` (`150mA`) or Diodes Inc. `ZTX694B` (`1A`).
2. **Gain Rank (`h_FE`):** Check suffix rank (`B`, `C`, or high-gain `D` where `h_FE = 400–800`, e.g., Kenwood KA-6000 preamp). Warn if a `KSC1815Y` (`h_FE 120–240`) is too low-gain for a `D`-rank position.
3. **The X-172 "Tombstone" Pinout Trap:**
   - Early `2SC458` in the rectangular, angled-top **X-172 ("tombstone")** package uses a **`B - C - E`** (Base-Collector-Emitter) pinout looking at the flat front face.
   - Later `TO-92` `2SC458` and modern Onsemi `KSC1845` / `KSC1815` use an **`E - C - B`** pinout.
   - **Mandatory Action:** Flash `[ KSC1845: E-C-B | ROTATE 180° FROM TOMBSTONE ]` on the 8.5" HUD and require multimeter diode-drop verification (`0.6V–0.7V` Base-Collector and Base-Emitter) before soldering.

### B. Vintage Pioneer / Sansui Capacitor Translation Table
| Schematic Code | Original Type | Modern Nichicon Series | Application Rule |
| :--- | :--- | :--- | :--- |
| `CEA` | Standard Aluminum Electrolytic | `UPW`, `UHE`, or `UPM` | General filtering/coupling; `UPM` for power supplies. |
| `CEANL` | Low-Noise / Low-Leakage | `UKL` or `UVR` | Mandatory in high-gain phono/tone paths to prevent hiss. |
| `CSSA` / `CSZA` | Solid Aluminum / Tantalum | `UKL` (Low Leakage) | Replace degraded sky-blue Sanyo `CSSA` or tantalum caps with `UKL`. |
| `80V Rated` | Main Filter / Rail Capacitor | `100V Equivalent` | 80V caps are obsolete/scarce; always bump 80V ratings to 100V. |

### C. Guided Dim Bulb Tester (DBT) & Dual-Pass Power Supply Protocol
- **Wattage Selection:** Prompt for `25W–40W` incandescent bulb on small radios/preamps, or `60W–100W` on stereo receivers/integrated amps.
- **Filament Signature:**
  - *Bright flash -> dims to faint glow:* `PASS` (filter caps charged, no dead shorts). Set turret beacon to `AMBER`.
  - *Remains brightly lit:* `SHORT CIRCUIT FAULT`. Immediately trigger `beacon_color="RED"` and `arm_emote="warning_stop"`, and guide output-transistor / rectifier isolation.
- **Dual-Pass Rail Logging:** Prompt the technician to measure each power supply node first in `VDC` (rail voltage) and second in `VAC` (superimposed `120 Hz` ripple).

---

## 6. Local SQLite Telemetry Schema (`src/workbench_db.py`)
Maintain state in a local SQLite database (`workbench.db`) with five relational tables:
1. `units`: `unit_id` (PK), `brand`, `model`, `serial_number`, `manual_local_path`, `gemini_file_uri`, `uri_expiry_ts`
2. `work_logs`: `log_id` (PK), `unit_id` (FK), `timestamp`, `entry_type`, `narrative_notes`, `media_attachment_path`
3. `component_replacements`: `comp_id` (PK), `unit_id` (FK), `schematic_designator`, `original_part`, `fault_metric`, `replacement_part`, `pinout_verified` (BOOL)
4. `test_telemetry`: `test_id` (PK), `unit_id` (FK), `dbt_status`, `b_plus_vdc`, `ripple_vac_120hz`, `idle_bias_ma`, `pre_thd_pct`, `post_thd_pct`
5. `screw_bins`: `bin_label` (PK: `'Bin A'`, `'Bin B'`, `'Bin C'`), `unit_id` (FK), `screw_count`, `description`, `tray_state` (`'EXTENDED'` or `'RETRACTED'`), `updated_ts`

---

## 7. Multimodal Vision & Audio Hub (`src/vision_hub.py` & `src/audio_router.py`)
### Dual-Camera Switchboard (`OpenCV`)
- Continuously buffer frames from **Camera 0 (Overhead Wide PCB Cam)** and **Camera 1 (Macro Workstation Cam)** in background threads.
- **Synchronized Dual Capture:** When triggered via hotkey, USB foot pedal, or voice command, grab simultaneous frames from both cameras and pass them in a single multimodal call so V.E.R.N. sees both the macro solder joint and its location on the chassis.
- **1.5-Second "Dwell-to-Inspect" Watchdog:** Compute frame-to-frame pixel delta on the Macro Cam. When motion spikes (user places a component or board under the lens) and then remains completely still below threshold for `1.5 seconds`, auto-snap a frame and notify V.E.R.N.
- **Telegram Mobile Probe (`src/telegram_bridge.py`):** Listen asynchronously for smartphone photos of rear serial plates or buried chassis wiring. Crop single-component inquiries to `384x384` (258 tokens) and pass full-board images in `768x768` tiles.

### Dual-Microphone Router (`sounddevice`)
- Enumerate audio inputs and prioritize the **RØDE Wireless GO III** USB-C receiver when connected and showing active RMS signal on Left Channel (TX1).
- Support **Stereo Split Mode:** Left Channel (TX1) = Technician voice; Right Channel (TX2) = Roving acoustic probe for transformer hum, relay click, or speaker distortion analysis.
- Automatically fail over to the **VS-20501 Shotgun Mic** when the RØDE transmitter is powered off or muted, updating the HUD badge (`[MIC: RØDE TX1]` vs `[MIC: SHOTGUN]`).

---

## 8. 8.5-Inch 4:3 Retro HUD & Hardware Simulator (`src/retro_hud.py`)
Build a `1024x768` (4:3 aspect ratio) window (or fullscreen `Textual` / `Pygame` / HTML-Canvas UI) in `#00FF66` on `#000000` with four dynamic view modes controlled by V.E.R.N.'s `control_vern_hardware` tool:
1. **MODE 1: OSCILLOSCOPE FACE (Default):** Animated `#00FF66` phosphor waveform that reacts to microphone input and V.E.R.N.'s TTS output voice.
2. **MODE 2: PINOUT & SPEC FLASHCARD:** Giant, readable-from-3-feet ASCII/vector diagram of transistor pinouts (`[ E - C - B ]`), resistor bands, or capacitor mappings.
3. **MODE 3: VISION TARGET RETICLE:** Live split-screen or picture-in-picture feed of the Overhead + Macro cameras with high-contrast target boxes.
4. **MODE 4: SCREW BUTLER & TELEMETRY TOAST:** Large confirmation banner displaying `Bin A / Bin B / Bin C` screw counts, DBT status, and logged voltages.
- **Bottom Status Bar (Hardware Simulator for Laptop Testing):** Display virtual indicators for **Servo Arm Emote**, **Magnetic Screw Tray (`EXTENDED`/`RETRACTED`)**, **Turret Beacon (`GREEN`/`AMBER`/`RED`)**, and **Active Mic**, plus keyboard bindings (`[`, `]`, `Space`, `F14`) to simulate the dual neck focus knobs and USB foot pedal.

---

## 9. GitHub Vault & Automated Restoration Dossiers (`src/github_sync.py`)
Expose two GitHub Function Calling tools to V.E.R.N.:
1. `publish_restoration_dossier(unit_id: int, commit_message: str)`:
   - Queries `workbench.db` across all tables for `unit_id`.
   - Generates a polished Markdown report at `docs/restorations/{brand}-{model}-{serial}.md` containing Unit Metadata, Dim Bulb & Power Supply Telemetry table, Component Replacements log (with pinout verification checkmarks), Screw Bin audit, and Chronological Bench Notes.
   - Stages `docs/restorations/` and `knowledge/model_quirks.md`, commits, and pushes to the remote GitHub repository.
2. `log_bench_quirk(model: str, quirk_note: str)`:
   - Appends newly discovered circuit quirks or service bulletin notes to `knowledge/model_quirks.md` and commits to Git.

---

## 10. Phased Implementation Milestones (For Antigravity Execution)
Execute and verify this project in four sequential milestones:
- **Milestone 1 (Core Brain, Guardrails & SQLite + GitHub Sync):** Scaffold repo, populate `knowledge/*.json`, implement `workbench_db.py`, `github_sync.py`, and `vern_agent.py` with Function Calling tools, and pass `pytest` unit tests (`tests/`).
- **Milestone 2 (The 8.5" 4:3 Phosphor-Green HUD & Hardware Simulator):** Build `retro_hud.py` with the oscilloscope waveform, giant pinout flashcards, virtual servo/screw-tray bar, and keyboard dial simulation.
- **Milestone 3 (Dual-Mic Audio & Spoken TTS Loop):** Implement `audio_router.py` (RØDE Wireless GO III + Shotgun failover) and wire low-latency voice input/output into V.E.R.N.
- **Milestone 4 (Dual-Camera OpenCV Switchboard & Telegram Bridge):** Implement `vision_hub.py` (Overhead + Macro cams with 1.5s Dwell-to-Inspect) and `telegram_bridge.py`.