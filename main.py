import sys
from datetime import datetime, timedelta


def detect_stops(points):
    """
    Return indices where the car stopped, ignoring stationary points at start and end.
    """
    stop_speed = 1
    result = []
    prev_stopped = False

    # Find first moving point
    start_index = 0
    for i, pt in enumerate(points):
        if pt["speed"] is not None and pt["speed"] >= stop_speed:
            start_index = i
            break

    # Find last moving point
    end_index = len(points) - 1
    for i in reversed(range(len(points))):
        if points[i]["speed"] is not None and points[i]["speed"] >= stop_speed:
            end_index = i
            break

    # Only consider points between first and last moving points
    for index in range(start_index, end_index + 1):
        point = points[index]
        speed = point["speed"]

        if speed is not None and speed < stop_speed:
            cur_stop = True
        else:
            cur_stop = False

        if cur_stop and not prev_stopped:
            result.append(index)

        prev_stopped = cur_stop

    return result


def detect_left_turns(points):
    """
    Detect left turns by checking when a reasonable turn is made
    30 degrees was used since it seemed the most accurate
    """

    speed_min = 1
    angle_thresh = 30
    result = []

    for index in range(1, len(points)):

        point0 = points[index-1]
        point1 = points[index]

        if None in (point0["speed"], point1["speed"], point0["course"], point1["course"]):
            continue
        if point0["speed"] < speed_min or point1["speed"] < speed_min:
            continue

        delta = point1["course"] - point0["course"]

        while delta > 180:
            delta -= 360
        while delta < -180:
            delta += 360

        if delta > angle_thresh:
            result.append(index)
    return result


def format_change(coord_num, direction):
    """
    Fix for files coming in as Degrees*100 + Minutes
    Changes to +/- Degrees.fractional_degrees
    """

    if not coord_num:
        return None


    if direction in ("N", "S"):
        degree_length = 2
    else:
        degree_length = 3

    degrees = int(coord_num[:degree_length])
    minutes = float(coord_num[degree_length:])

    decimal = degrees + minutes / 60.0

    if direction in ("S", "W"):
        decimal = -decimal

    return decimal


def rmc_fields(line):
    parts = line.strip().split(',')
    if len(parts) < 9 or parts[0] != "$GPRMC" or parts[2] != "A":
        return None

    # Latitude/Longitude
    latitude = format_change(parts[3], parts[4])
    longitude = format_change(parts[5], parts[6])

    if latitude is None or longitude is None:
        return None

    # Speed (knots)
    try:
        speed = float(parts[7]) if parts[7] else None
    except ValueError:
        speed = None

    # Course (degrees)
    try:
        course = float(parts[8]) if parts[8] else None
    except ValueError:
        course = None

    # UTC Time
    try:
        raw_time = parts[1]  # e.g., "142136.000"
        hours = int(raw_time[0:2])
        minutes = int(raw_time[2:4])
        seconds = float(raw_time[4:])
        point_time = timedelta(hours=hours, minutes=minutes, seconds=seconds)
    except (ValueError, IndexError):
        point_time = None

    return {
        "latitude": latitude,
        "longitude": longitude,
        "speed": speed,
        "course": course,
        "time": point_time,  # store as timedelta for easy subtraction
    }


def read_gps_file(path):
    """
    Read a GPS log file and return a list of points.
    """

    points = []

    with open(path, 'r', encoding='ascii', errors='ignore') as file:
        for line in file:
            if line.startswith("$GPRMC"):
                point = rmc_fields(line)
                if point is not None:
                    points.append(point)
    return points


def write_kml(points, outfile_path):
    """
    Write one KML file with:
      - Red stop markers
      - Yellow left-turn markers
      - Yellow route line

    """

    altitude = 3.0
    stops = detect_stops(points)
    lefts = detect_left_turns(points)

    # Icons found from https://kml4earth.appspot.com/icons.html#kml-icons

    with open(outfile_path, "w", encoding="utf-8") as kml:
        kml.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        kml.write('<kml xmlns="http://www.opengis.net/kml/2.2">\n')
        kml.write('<Document>\n')

        # Stop marker style
        kml.write('<Style id="stopRed">\n')
        kml.write('  <IconStyle>\n')
        kml.write('    <color>ff0000ff</color>\n')
        kml.write('    <Icon><href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href></Icon>\n')
        kml.write('  </IconStyle>\n')
        kml.write('</Style>\n')

        # Left-turn marker style
        kml.write('<Style id="leftTurnYellow">\n')
        kml.write('  <IconStyle>\n')
        kml.write('    <color>ff00ffff</color>\n')
        kml.write('    <Icon><href>http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png</href></Icon>\n')
        kml.write('  </IconStyle>\n')
        kml.write('</Style>\n')

        # Route line style
        kml.write('<Style id="yellowPoly">\n')
        kml.write('  <LineStyle>\n')
        kml.write('    <color>ff00ffff</color>\n')
        kml.write('    <width>6</width>\n')
        kml.write('  </LineStyle>\n')
        kml.write('  <PolyStyle>\n')
        kml.write('    <color>ff00ff00</color>\n')
        kml.write('  </PolyStyle>\n')
        kml.write('</Style>\n')

        kml.write('<Placemark>\n')
        kml.write('  <styleUrl>#yellowPoly</styleUrl>\n')
        kml.write('  <LineString>\n')
        kml.write('    <Description>Speed in MPH, not altitude.</Description>\n')
        kml.write('    <extrude>1</extrude>\n')
        kml.write('    <tessellate>1</tessellate>\n')
        kml.write('    <altitudeMode>absolute</altitudeMode>\n')
        kml.write('    <coordinates>\n')

        # Line coordinates (longitude, latitude, altitude)
        for pts in points:
            kml.write(f'      {pts["longitude"]:},{pts["latitude"]:},{altitude}\n')
        kml.write('    </coordinates>\n')
        kml.write('  </LineString>\n')
        kml.write('</Placemark>\n')

        # Stop markers
        for index in stops:
            pts = points[index]
            kml.write('<Placemark>\n')
            kml.write('  <name>Stop</name>\n')
            kml.write('  <styleUrl>#stopRed</styleUrl>\n')
            kml.write('  <Point><coordinates>')
            kml.write(f'{pts["longitude"]:},{pts["latitude"]:},{altitude}')
            kml.write('</coordinates></Point>\n')
            kml.write('</Placemark>\n')

        # Left turn markers
        for index in lefts:
            pts = points[index]
            kml.write('<Placemark>\n')
            kml.write('  <name>Left Turn</name>\n')
            kml.write('  <styleUrl>#leftTurnYellow</styleUrl>\n')
            kml.write('  <Point><coordinates>')
            kml.write(f'{pts["longitude"]:},{pts["latitude"]:},{altitude}')
            kml.write('</coordinates></Point>\n')
            kml.write('</Placemark>\n')

        # End document
        kml.write('</Document>\n')
        kml.write('</kml>\n')


def travel_time(points, stop_speed=1):
    """
    Returns driving time in seconds, ignoring stationary points at start and end.
    """
    if not points:
        return 0

    # Find first and Last moving point (Same Logic as stops)
    start_index = 0
    for i, pt in enumerate(points):
        if pt["speed"] is not None and pt["speed"] >= stop_speed:
            start_index = i
            break
    end_index = len(points) - 1
    for i in reversed(range(len(points))):
        if points[i]["speed"] is not None and points[i]["speed"] >= stop_speed:
            end_index = i
            break

    # Compute duration
    start_time = points[start_index]["time"]
    end_time = points[end_index]["time"]

    if end_time < start_time:  # Handle crossing midnight
        end_time += 24*3600

    return end_time - start_time

def main():
    if len(sys.argv) != 3:
        print("Usage: main.py input.txt output.kml")
        sys.exit(1)

    read_from_path = sys.argv[1]
    write_to_path = sys.argv[2]

    points = read_gps_file(read_from_path)
    print(f"Read {len(points)} usable GPS points")

    time = travel_time(points)
    print(f"Travel time: {time}")
    write_kml(points, write_to_path)
    print(f"Written KML: {write_to_path}")


if __name__ == "__main__":
    main()
