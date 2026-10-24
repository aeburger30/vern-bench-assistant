# V.E.R.N. Bench Field Notes & Model Quirks (`VS-20501`)

Versioned solid-state memory archive of model-specific circuit quirks, service bulletins, and silkscreen traps discovered during bench restorations.

---

## Kenwood KA-6000
- **Phono & Tone Preamp (`2SC458D` X-172 Tombstone):** Uses high-gain `D`-rank (`h_FE = 400–800`) rectangular angled-top X-172 package transistors with a `B - C - E` pinout. Always substitute with `KSC1845F` (`E - C - B`) rotated 180° from the tombstone orientation; never use `KSC1815Y` due to insufficient beta.

## Pioneer SX-780
- **Regulator Trio (`Q19`, `Q20`, `Q25`):** TO-220 pass transistors on the main board run hot and fracture their solder joints over decades. Reflow with leaded 63/37 solder and add clip-on heatsinks during restoration.
- **Sky-Blue Sanyo `CSSA` Caps:** Replace all solid-aluminum sky-blue caps in the audio path with Nichicon `UKL` or WIMA `MKS2` film caps to eliminate DC leakage.

## Sansui AU-717
- **Corrosive Assembly Glue (F-2663 Power Supply Board):** Factory neoprene glue turns conductive and eats adjacent resistor and jumper leads. Scrape away completely and replace corroded 1/4W metal film resistors.
- **80V Rail Capacitors:** Original 80V electrolytics are obsolete; always bump to 100V Nichicon `UPM` or `LKG` equivalents.
