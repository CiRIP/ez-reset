# ez-reset

Reset waste ink counters on Epson printers via USB on Windows.

**Want to help with development, learn more about Epson printers, or simply need help?** 

## What it does

- Shows ink levels and waste ink counter status
- Resets waste ink counters
- Works with many Epson printer models over USB

## Requirements

- Windows
- Supported Epson printer connected via USB

## Installation (easy)

Grab a prebuilt binary from the *Releases* tab or [download directly from here](github.com/CiRIP/ez-reset/releases/latest/download/ez-reset.exe).

## Installation (advanced)

If you wish to experiment with the code, or otherwise distrust the prebuilt .exe, you can install the package on your
system:

```bash
pip install .
```

## Usage (advanced)

Run the GUI:

```bash
python -m ez_reset
```

1. The app will list detected USB printers
2. Double-click a printer to open its control panel
3. View ink levels and waste counter status
4. Click "Reset All" to reset waste counters
5. Restart your printer after resetting

## Warning

This tool modifies printer firmware counters. Use at your own risk. Always restart the printer after resetting waste counters.

## See also

- [Ircama/epson_print_conf](https://github.com/Ircama/epson_print_conf)
- [abrasive/epson-reversing](https://github.com/abrasive/epson-reversing)
