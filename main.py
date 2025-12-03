#/usr/bin/env python3

"""
Read in GPS data, clean it, and create a KML file with markers for stops, left turns, and the route.

authors: Jaidan Giglio, Garrett Mihalitsas
"""

import sys

def get_angle(coord1, coord2):
    """
    Calculates the smallest angle difference between two coordinates.
    Will add/subtract so that they are within a range of -180 to 180 degrees.

    Args:
        coord1: The first coordinate.
        coord2: The second coordinate.
    Returns:
        Absolute value of the difference between the given coordinates.
    """

    delta = coord2 - coord1

    while delta > 180:
        delta -= 360
    while delta < -180:
        delta += 360

    return abs(delta)

def get_indices(points):
    """
    Find the indices of the first and last moving points within a list of points.

    Args:
        points: list of points

    Returns:
        start_index: index of first moving point
        end_index: index of last moving point
    """
    stop_speed = 1

    # Find first moving point
    start_index = 0
    for index, point in enumerate(points):
        if point["speed"] is not None and point["speed"] >= stop_speed:
            start_index = index
            break

    # Find last moving point
    end_index = len(points) - 1
    for index in reversed(range(len(points))):
        if points[index]["speed"] is not None and points[index]["speed"] >= stop_speed:
            end_index = index
            break

    return start_index, end_index

def detect_stops(points):
    """
    Return indices where the car stopped, ignoring stationary points at start and end.

    Args:
        points: points list from GPS log file

    Returns:
        result: list of indices where the car stopped
    """
    stop_speed = 1
    result = []
    prev_stopped = False


    start_index, end_index = get_indices(points)

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

def detect_anomolies(points):
    """
    Removes parking stops and some points along a straight line

    Args:
        points: points list from GPS log file
    """
    stop_speed = 1
    remove_parked = []
    prev_stopped = False

    angle_thresh = 0.1
    stop_speed = 1
    angle = 180
    prev_course = 0

    start_index, end_index = get_indices(points)


    # Only consider points between first and last moving points
    for index in range(start_index, end_index + 1):
        point = points[index]
        speed = point["speed"]
        course = point["course"]

        if prev_course != 0:
            angle = get_angle(course, prev_course)


        if speed is not None and speed < stop_speed:
            cur_stop = True
        else:
            cur_stop = False

        if cur_stop and prev_stopped:
            remove_parked.append(index)

        if not cur_stop and not prev_stopped and angle < angle_thresh:
            remove_parked.append(index)

        prev_stopped = cur_stop
        prev_course = course

    for index in reversed(remove_parked):   # removes consecutive stops (parked)
        points.pop(index)

def detect_jumps(points):
    """
    Detects and removes large jumps based on latitude and longitude changes.

    Args:
        points: points list from GPS log file
    """
    jump_points = []

    prev_point = 0

    for index in range (1, len(points)):
        latitude_prev = points[prev_point].get("latitude")
        longitude_prev = points[prev_point].get("longitude")
        latitude_curr = points[index].get("latitude")
        longitude_curr = points[index].get("longitude")

        lat_change = abs(latitude_prev - latitude_curr)
        long_change = abs(longitude_prev - longitude_curr)

        if lat_change > 0.01 or long_change > 0.01:
            jump_points.append(index)
        else:
            prev_point = index

    for index in reversed(jump_points):
        points.pop(index)



def detect_left_turns(points):
    """
    Detect left turns by tracking heading change
    over a time window.

    Args:
        points: list of points from GPS log file

    Return:
        result: list of indices where left turn was detected
    """
    window_seconds = 3
    min_speed = 2.0
    turn_threshold = 50
    result = []
    window = []

    for index in range(len(points)):
        point = points[index]

        if point["course"] is None or point["speed"] is None:
            continue
        if point["speed"] < min_speed:
            continue

        # add point to window
        window.append(point)

        # remove old points (older than window_seconds)
        while (window[-1]["time"] - window[0]["time"]) % (24*3600) > window_seconds:
            window.pop(0)

        # compute net turn from first to last in window
        start_h = window[0]["course"]
        end_h   = window[-1]["course"]

        # normalize shortest angular difference
        delta = end_h - start_h
        while delta > 180: delta -= 360
        while delta < -180: delta += 360

        if delta > turn_threshold:
            result.append(index)
            # reset window so that one turn doesn't produce too many triggers
            window = [point]

    return result


def format_change(coord_num, direction):
    """
    Fix for files coming in as Degrees*100 + Minutes
    Changes to +/- Degrees.fractional_degrees

    Args:
        coord_num: original coordinate number
        direction: N, S, E, W

    Return:
        decimal: correctly formatted number
    """

    if not coord_num:
        return None


    if direction in ("N", "S"):
        degree_length = 2
    else:
        degree_length = 3

    try:
        degrees = int(coord_num[:degree_length])
        minutes = float(coord_num[degree_length:])
    except (ValueError, IndexError):
        return None

    decimal = degrees + minutes / 60.0

    if direction in ("S", "W"):
        decimal = -decimal

    return decimal


def rmc_fields(line):
    """
    Extracts and parses RMC fields from a given NMEA sentence.

    Args:
    line: str
        The input string containing the NMEA RMC sentence.

    Returns:
        List of parsed RMC fields for each point (line) from file
    """
    parts = line.strip().split(',')
    if len(parts) < 9 or parts[0] != "$GPRMC" or parts[2] != "A":
        return None

    # latitude/Longitude
    latitude = format_change(parts[3], parts[4])
    longitude = format_change(parts[5], parts[6])

    if latitude is None or longitude is None:
        return None

    # speed (in knots)
    try:
        speed = float(parts[7]) if parts[7] else None
    except ValueError:
        speed = None

    # course (in degrees)
    try:
        course = float(parts[8]) if parts[8] else None
    except ValueError:
        course = None

    # UTC time
    try:
        raw_time = parts[1]  # e.g., "142136.000"
        hours = int(raw_time[0:2])
        minutes = int(raw_time[2:4])
        seconds = float(raw_time[4:])
        point_time = hours * 3600 + minutes * 60 + seconds
    except (ValueError, IndexError):
        point_time = None

    return {
        "latitude": latitude,
        "longitude": longitude,
        "speed": speed,
        "course": course,
        "time": point_time,
    }


def read_gps_file(path):
    """
    Read a GPS log file and return a list of points.  Calls rmc_fields for each line to parse data.

    Args:
        path: path to the GPS log file.

    Returns:
        points: list of parsed RMC fields for each point (line) from file
    """
    points = []

    with open(path, 'r', encoding='ascii', errors='ignore') as file:
        for line in file:
            if line.startswith("$GPRMC"):
                if line.count("$GP") > 1:       # skips Arduino burps
                    continue
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

    Args:
        points: list of points from GPS log file
        outfile_path: path to write the KML file
    """
    altitude = 3.0
    stops = detect_stops(points)
    lefts = detect_left_turns(points)

    # icons found from https://kml4earth.appspot.com/icons.html#kml-icons

    with open(outfile_path, "w", encoding="utf-8") as kml:
        kml.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        kml.write('<kml xmlns="http://www.opengis.net/kml/2.2">\n')
        kml.write('<Document>\n')

        # stop marker style
        kml.write('<Style id="stopRed">\n')
        kml.write('  <IconStyle>\n')
        kml.write('    <color>ff0000ff</color>\n')
        kml.write('    <Icon><href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href></Icon>\n')
        kml.write('  </IconStyle>\n')
        kml.write('</Style>\n')

        # left turn marker style
        kml.write('<Style id="leftTurnYellow">\n')
        kml.write('  <IconStyle>\n')
        kml.write('    <color>ff00ffff</color>\n')
        kml.write('    <Icon><href>http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png</href></Icon>\n')
        kml.write('  </IconStyle>\n')
        kml.write('</Style>\n')

        # route line style
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

        # line coordinates (longitude, latitude, altitude)
        for pts in points:
            # skip if lat/lon missing
            if pts["longitude"] is None or pts["latitude"] is None:
                continue
            kml.write(f'      {pts["longitude"]},{pts["latitude"]},{altitude}\n')
        kml.write('    </coordinates>\n')
        kml.write('  </LineString>\n')
        kml.write('</Placemark>\n')

        # stop markers
        for index in stops:
            pts = points[index]
            if pts["longitude"] is None or pts["latitude"] is None:
                continue
            kml.write('<Placemark>\n')
            kml.write('  <name>Stop</name>\n')
            kml.write('  <styleUrl>#stopRed</styleUrl>\n')
            kml.write('  <Point><coordinates>')
            kml.write(f'{pts["longitude"]},{pts["latitude"]},{altitude}')
            kml.write('</coordinates></Point>\n')
            kml.write('</Placemark>\n')

        # left turn markers
        for index in lefts:
            pts = points[index]
            if pts["longitude"] is None or pts["latitude"] is None:
                continue
            kml.write('<Placemark>\n')
            kml.write('  <name>Left Turn</name>\n')
            kml.write('  <styleUrl>#leftTurnYellow</styleUrl>\n')
            kml.write('  <Point><coordinates>')
            kml.write(f'{pts["longitude"]},{pts["latitude"]},{altitude}')
            kml.write('</coordinates></Point>\n')
            kml.write('</Placemark>\n')

        # end document
        kml.write('</Document>\n')
        kml.write('</kml>\n')


def travel_time(points):
    """
    Returns driving time in seconds, ignoring stationary points at start and end.

    Args:
        points: list of points from GPS log file
    """
    if not points:
        return 0

    # find first and fast moving point (same logic as stops)
    start_index, end_index = get_indices(points)

    # compute duration
    start_time = points[start_index]["time"]
    end_time = points[end_index]["time"]

    if start_time is None or end_time is None:
        return 0

    if end_time < start_time:  # Handle crossing midnight
        end_time += 24*3600

    return end_time - start_time


def estimate_time(points):
    """
    Estimates start and end time changes based on a sequence of points.

    Args:
        points: list of points from GPS log file

    Returns:
        start_change: estimated time change at the start
        end_change: estimated time change at the end

    """

    if len(points) < 2:
        return 0, 0

    start_index, end_index = get_indices(points)

    start_change = 0
    start_motion = (start_index == 0)

    end_change = 0
    end_motion = (end_index == len(points)-1)

    if not start_motion and not end_motion:
        return 0, 0

    sum_change = 0.0
    count_change = 0
    time_temp = None

    for index in range(start_index, end_index+1):
        point = points[index]
        if point["time"] is None:
            continue
        if time_temp is not None:
            time_change = point["time"] - time_temp
            if time_change < 0:
                time_change += 24*3600
            sum_change += time_change
            count_change += 1
        time_temp = point["time"]

    if count_change == 0:
        return 0, 0

    average_change = sum_change / count_change

    if start_motion:
        start_change = average_change
    if end_motion:
        end_change = average_change

    return start_change, end_change


def main():
    """
    Main function to read a GPS file, clean the data from it, and create a KML file from it.
    """
    if len(sys.argv) != 3:
        print("Usage: main.py input.txt output.kml")
        sys.exit(1)
    read_from_path = sys.argv[1]
    write_to_path = sys.argv[2]

    points = read_gps_file(read_from_path)
    print(f"Read {len(points)} usable GPS points (raw)")
    detect_jumps(points)

    detect_anomolies(points)

    time = travel_time(points)
    start_change, end_change = estimate_time(points)
    if start_change != 0:
        print(f"Car started in motion, estimated {start_change} extra seconds")
        time += start_change
    if end_change != 0:
        print(f"Car ended in motion, estimated {end_change} extra seconds")
    time += end_change
    print(f"Travel time (seconds): {time}")

    write_kml(points, write_to_path)
    print(f"Written KML: {write_to_path}")
    print(f"{len(points)} usable GPS points (cleaned)")



if __name__ == "__main__":
    main()
