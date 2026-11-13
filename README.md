# GPS Route Analyzer

**Final Project — CSCI 420: Principles of Data Mining | Rochester Institute of Technology**

A Python implementation developed as part of the final project for CSCI 420. The assignment involved processing GPS log data to identify stops and left turns, estimate travel time, and generate a KML file for visualizing the resulting route.

## Features

- **GPS parsing:** Reads valid `$GPRMC` sentences from NMEA GPS logs and extracts coordinates, speed, heading, and time.
- **Data cleaning:** Filters large coordinate jumps, repeated stationary readings, and redundant points with very small changes in heading.
- **Stop detection:** Identifies transitions from driving to a stop while excluding stationary periods at the beginning and end of a trip.
- **Left-turn detection:** Uses changes in heading over a short time window to identify likely left turns.
- **Travel-time estimation:** Calculates elapsed travel time between the first and last moving readings, with adjustments for trips that begin or end while the vehicle is moving.
- **KML export:** Generates a mapped route with color-coded markers for stops and left turns.

## Requirements

- Python 3
- A text file containing NMEA GPS data with `$GPRMC` records

The script uses only the Python standard library, so no additional packages are required.

## Usage

Clone the repository:

```bash
git clone https://github.com/jdg6005/PDM-proj.git
cd PDM-proj
```

Run the script with an input GPS log and the desired output KML path:

```bash
python main.py input.txt output.kml
```

Replace `input.txt` with the path to your GPS log. The script writes `output.kml` and prints the number of usable GPS points, the estimated travel time in seconds, and the output path.

Open the resulting KML file in a compatible geographic viewer, such as Google Earth, to inspect the route.

## KML Visualization

The exported KML includes:

| Element | Appearance |
| --- | --- |
| Recorded route | Yellow line |
| Detected stops | Red markers |
| Detected left turns | Yellow markers |

## How It Works

1. **Parse:** Read valid `$GPRMC` entries, converting latitude and longitude to decimal degrees.
2. **Clean:** Remove unusually large changes in position and certain redundant GPS samples.
3. **Analyze:** Detect stops and left turns from speed and heading changes.
4. **Estimate:** Compute trip duration from GPS timestamps, accounting for trips that cross midnight and estimating time at incomplete trip boundaries.
5. **Export:** Write the cleaned route and detected events to a KML file.

### Detection Parameters

The current implementation uses the following fixed thresholds:

| Detection | Threshold |
| --- | --- |
| Stop | Speed below 1 knot |
| Left turn | Heading increases by more than 50° within a 3-second window, at speeds of at least 2 knots |
| GPS jump | Latitude or longitude changes by more than 0.01° between retained points |
| Redundant heading | Heading changes by less than 0.1° between moving points |

These values are defined in `main.py` and can be adjusted for different GPS recordings.

## Contributors

- Jaidan Giglio
- Garrett Mihalitsas
