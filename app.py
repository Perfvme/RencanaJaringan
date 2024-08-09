from flask import Flask, render_template, request, redirect, url_for, send_file
from geopy.distance import distance as geopy_distance
from geopy.geocoders import Nominatim
import folium
import gpxpy
import os
import math
import matplotlib.pyplot as plt

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['STATIC_FOLDER'] = 'static/'

geolocator = Nominatim(user_agent="gpx_map")

def haversine(lat1, lon1, lat2, lon2):
    return geopy_distance((lat1, lon1), (lat2, lon2)).meters

def calculate_angles(lat1, lon1, lat2, lon2, lat3, lon3):
    vector1 = (lat2 - lat1, lon2 - lon1)
    vector2 = (lat3 - lat2, lon3 - lon2)
    dot_product = sum(v1 * v2 for v1, v2 in zip(vector1, vector2))
    magnitude1 = math.sqrt(sum(v ** 2 for v in vector1))
    magnitude2 = math.sqrt(sum(v ** 2 for v in vector2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0, 0
    angle_rad = math.acos(dot_product / (magnitude1 * magnitude2))
    external_angle_deg = math.degrees(angle_rad)
    internal_angle_deg = 180 - external_angle_deg
    return internal_angle_deg, external_angle_deg

def get_location_name(lat, lon):
    location = geolocator.reverse((lat, lon), exactly_one=True)
    return location.address if location and location.address else "Unknown Location"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    if not file or not file.filename.endswith('.gpx'):
        return redirect(request.url)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)
    return redirect(url_for('show_map', filename=file.filename))

@app.route('/map/<filename>', methods=['GET', 'POST'])
def show_map(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        with open(filepath, 'r') as gpx_file:
            gpx = gpxpy.parse(gpx_file)
    except Exception as e:
        return f"Error parsing GPX file: {e}"

    waypoints = [{'lat': wp.latitude, 'lon': wp.longitude, 'ele': wp.elevation} for wp in gpx.waypoints]
    if not waypoints:
        return "No waypoints found in GPX file"

    options = request.form.getlist('option') if request.method == 'POST' else ['None'] * len(waypoints)
    angles = request.form.getlist('angle') if request.method == 'POST' else ['0'] * len(waypoints)
    line_types = request.form.getlist('line_type') if request.method == 'POST' else ['JTM'] * len(waypoints)
    construction_types = request.form.getlist('construction_type') if request.method == 'POST' else ['Besi'] * len(waypoints)
    symbols = request.form.getlist('symbol') if request.method == 'POST' else [''] * len(waypoints)
    multiplier = float(request.form.get('multiplier', 1.0))
    table_data = []

    for i in range(1, 15):
        boq_sebelum = float(request.form.get(f'boq_sebelum_{i}', 0))
        harga_material = float(request.form.get(f'harga_material_{i}', 0))
        harga_jasa = float(request.form.get(f'harga_jasa_{i}', 0))
        jumlah_material = boq_sebelum * harga_material
        jumlah_jasa = boq_sebelum * harga_jasa
        total = jumlah_material + jumlah_jasa
        row = {
            'boq_sebelum': boq_sebelum,
            'harga_material': harga_material,
            'harga_jasa': harga_jasa,
            'jumlah_material': jumlah_material,
            'jumlah_jasa': jumlah_jasa,
            'total': total
        }
        table_data.append(row)

    boq_sebelum_tiang_beton_count = sum(
        1 for i in range(1, len(waypoints))
        if construction_types[i] == 'Beton' and line_types[i] == 'JTR'
    )
    boq_sebelum_tiang_besi_count = sum(
        1 for i in range(1, len(waypoints))
        if construction_types[i] == 'Besi' and line_types[i] == 'JTR'
    )

    boq_jasa_pengecoran = boq_sebelum_tiang_beton_count + boq_sebelum_tiang_besi_count
    boq_penitikan_koordinat = boq_sebelum_tiang_beton_count + boq_sebelum_tiang_besi_count
    boq_pengecatan_tiang = boq_sebelum_tiang_besi_count

    total_jtr_length = 0
    m = folium.Map(location=[waypoints[0]['lat'], waypoints[0]['lon']], zoom_start=12)
    location_name = get_location_name(waypoints[0]['lat'], waypoints[0]['lon'])

    total_distance = 0
    elevations = []
    distances = [0]
    for i, waypoint in enumerate(waypoints):
        elevations.append(waypoint['ele'])
        if i > 0:
            previous_waypoint = waypoints[i - 1]
            distance = haversine(previous_waypoint['lat'], previous_waypoint['lon'], waypoint['lat'], waypoint['lon'])
            total_distance += distance
            distances.append(total_distance)
            if line_types[i - 1] == 'JTR':
                total_jtr_length += distance

            internal_angle, external_angle = None, None
            smallest_angle = None
            color = 'blue'
            radius = 5
            if i < len(waypoints) - 1:
                next_waypoint = waypoints[i + 1]
                internal_angle, external_angle = calculate_angles(previous_waypoint['lat'], previous_waypoint['lon'], waypoint['lat'], waypoint['lon'], next_waypoint['lat'], next_waypoint['lon'])
                smallest_angle = min(internal_angle, external_angle)
                if smallest_angle < 15:
                    color = 'red'
                    radius = 8
                elif 15 <= smallest_angle < 30:
                    color = 'orange'
                    radius = 7
                elif 30 <= smallest_angle < 60:
                    color = 'yellow'
                    radius = 6
                else:
                    color = 'green'
                    radius = 5

            folium.CircleMarker(
                location=[waypoint['lat'], waypoint['lon']],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.6,
                id=f'waypoint-{i}'
            ).add_to(m)

            mid_lat = (previous_waypoint['lat'] + waypoint['lat']) / 2
            mid_lon = (previous_waypoint['lon'] + waypoint['lon']) / 2
            folium.Marker(
                [mid_lat, mid_lon],
                icon=folium.DivIcon(
                    html=f"""
                    <div style="
                        position: absolute; 
                        transform: translate(-50%, -50%);
                        font-size: 10px;
                        font-weight: bold;
                        z-index: 1000;">
                        {distance:.2f} m
                    </div>"""
                )
            ).add_to(m)

            if smallest_angle is not None:
                folium.Marker(
                    [waypoint['lat'], waypoint['lon']],
                    icon=folium.DivIcon(
                        html=f"""
                        <div style="
                            position: absolute; 
                            transform: translate(-50%, -100%);
                            font-size: 10px;
                            font-weight: bold;
                            z-index: 1000;">
                            {smallest_angle:.2f}°
                        </div>"""
                    )
                ).add_to(m)

            line_color = 'blue' if line_types[i - 1] == 'JTR' else 'red'
            folium.PolyLine(locations=[[previous_waypoint['lat'], previous_waypoint['lon']], [waypoint['lat'], waypoint['lon']]], color=line_color).add_to(m)
        else:
            folium.CircleMarker(
                location=[waypoint['lat'], waypoint['lon']],
                radius=5,
                color='blue',
                fill=True,
                fill_color='blue',
                fill_opacity=0.6,
                id=f'waypoint-{i}'
            ).add_to(m)

        option = options[i] if i < len(options) else 'None'
        angle = float(angles[i]) if i < len(angles) else 0
        construction_type = construction_types[i] if i < len(construction_types) else 'Besi'
        symbol = symbols[i] if i < len(symbols) else ''

        if symbol:
            color = 'red' if symbol == 'Tiang Penumpu' else (
                'orange' if symbol == 'Tiang Sudut Kecil' else (
                    'yellow' if symbol == 'Tiang Sudut Sedang' else (
                        'green' if symbol == 'Tiang Sudut Besar' else (
                            'black' if symbol == 'Tiang Penopang' else 'blue'
                        )
                    )
                )
            )
            radius = 8

        if option == 'Guy Wire':
            folium.Marker(
                location=[waypoint['lat'], waypoint['lon']],
                icon=folium.DivIcon(
                    html=f"""
                    <div style="
                        position: absolute;
                        transform: translate(-50%, -50%) rotate({angle}deg);
                        transform-origin: 50% 100%;
                        width: 1px;
                        height: 20px;
                        background-color: black;
                        z-index: 1000;">
                        <div style="
                            position: absolute;
                            bottom: 100%;
                            left: 50%;
                            transform: translate(-50%, 0%);
                            width: 0;
                            height: 0;
                            border-left: 3px solid transparent;
                            border-right: 3px solid transparent;
                            border-bottom: 6px solid black;">
                        </div>
                    </div>"""
                )
            ).add_to(m)
        elif option == 'Support Pole':
            distance = 0.00005
            support_pole_lat = waypoint['lat'] + (distance * math.cos(math.radians(angle)))
            support_pole_lon = waypoint['lon'] + (distance * math.sin(math.radians(angle)))
            folium.CircleMarker(
                location=[support_pole_lat, support_pole_lon],
                radius=5,
                color='black',
                fill=True,
                fill_color='black',
                fill_opacity=0.6
            ).add_to(m)
            folium.PolyLine(locations=[[waypoint['lat'], waypoint['lon']], [support_pole_lat, support_pole_lon]], color='black').add_to(m)

        if symbol:
            folium.CircleMarker(
                location=[waypoint['lat'], waypoint['lon']],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.6,
                id=f'waypoint-{i}'
            ).add_to(m)
        elif construction_type == 'Beton':
            folium.CircleMarker(
                location=[waypoint['lat'], waypoint['lon']],
                radius=radius + 2,
                color='black',
                weight=2,
                fill=True,
                fill_color=color,
                fill_opacity=0.6,
                id=f'waypoint-{i}'
            ).add_to(m)

    if waypoints:
        folium.Marker(
            [waypoints[0]['lat'], waypoints[0]['lon']],
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    position: absolute; 
                    transform: translate(-50%, -100%);
                    font-size: 10px;
                    font-weight: bold;
                    z-index: 1000;">
                    {total_distance:.2f} m
                </div>"""
            )
        ).add_to(m)

    legend_html = """
        <div style="
    position: fixed; 
    bottom: 50px; 
    left: 50px; 
    width: 250px; 
    height: 290px; 
    background-color: white; 
    border:2px solid grey; 
    z-index:9999; 
    font-size:14px;">
    <h4 style="margin-top: 5px; text-align: center;">Keterangan Simbol</h4>
    <table style="width: 100%; margin: 5px;">
        <tr><td><svg height="10" width="10"><circle cx="5" cy="5" r="5" fill="red" /></svg></td><td>Tiang Penumpu</td></tr>
        <tr><td><svg height="10" width="10"><circle cx="5" cy="5" r="5" fill="orange" /></svg></td><td>Tiang Sudut Kecil</td></tr>
        <tr><td><svg height="10" width="10"><circle cx="5" cy="5" r="5" fill="yellow" /></svg></td><td>Tiang Sudut Sedang</td></tr>
        <tr><td><svg height="10" width="10"><circle cx="5" cy="5" r="5" fill="green" /></svg></td><td>Tiang Sudut Besar</td></tr>
        <tr><td><svg height="10" width="10"><circle cx="5" cy="5" r="5" fill="black" /></svg></td><td>Tiang Penopang</td></tr>
        <tr><td><svg height="10" width="100"><line x1="0" y1="5" x2="100" y2="5" stroke="blue" /></svg></td><td>JTR</td></tr>
        <tr><td><svg height="10" width="100"><line x1="0" y1="5" x2="100" y2="5" stroke="red" /></svg></td><td>JTM</td></tr>
        <tr><td><svg height="10" width="10"><circle cx="5" cy="5" r="5" fill="red" stroke="black" stroke-width="2" /></svg></td><td>Tiang Beton</td></tr>
    </table>
</div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    map_info_html = f"""
        <div style="
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 420px;
            height: 250px;
            background-color: white;
            border: 2px solid grey;
            z-index: 9999;
            font-size: 12px;
            padding: 10px;">
            <div style="text-align: center; font-weight: bold;">
                PT PLN (PERSERO) <br>
                UNIT PELAKSANA PROYEK KETENAGALISTRIKAN <br>
                PROVINSI SULAWESI UTARA
            </div>
            <div style="margin-top: 10px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="border: 1px solid black; text-align: center;"></td>
                        <td style="border: 1px solid black; text-align: center;">NAMA</td>
                        <td style="border: 1px solid black; text-align: center;">PARAF</td>
                        <td style="border: 1px solid black; text-align: center;">JABATAN</td>
                        <td style="border: 1px solid black; text-align: center;" rowspan="4">NO. GBR<br>01</td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid black; text-align: center;">DIRENCANA</td>
                        <td style="border: 1px solid black; text-align: center;"></td>
			<td style="border: 1px solid black; text-align: center;"></td>
			<td style="border: 1px solid black; text-align: center;"></td>
		    </tr>
		    <tr>
                        <td style="border: 1px solid black; text-align: center;">UP2K SULUT</td>
                        <td style="border: 1px solid black;"></td>
                        <td style="border: 1px solid black;"></td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid black; text-align: center;">DIGAMBAR</td>
                        <td style="border: 1px solid black;"></td>
                        <td style="border: 1px solid black;"></td>
                        <td style="border: 1px solid black;"></td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid black; text-align: center;">DIPERIKSA</td>
                        <td style="border: 1px solid black;"></td>
                        <td style="border: 1px solid black;"></td>
                        <td style="border: 1px solid black;"></td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid black; text-align: center;">DISETUJUI</td>
                        <td style="border: 1px solid black;"></td>
                        <td style="border: 1px solid black;"></td>
                        <td style="border: 1px solid black;"></td>
                        <td style="border: 1px solid black; text-align: center;">{location_name}</td>
                    </tr>
                </table>
            </div>
        </div>
    """
    m.get_root().html.add_child(folium.Element(map_info_html))

    elevation_profile_path = os.path.join(app.config['STATIC_FOLDER'], 'elevation_profile.png')
    plt.figure(figsize=(10, 5))
    plt.plot(distances, elevations, marker='o', linestyle='-', color='b')
    plt.fill_between(distances, elevations, color='skyblue', alpha=0.4)
    plt.xlabel('Distance (meters)')
    plt.ylabel('Elevation (meters)')
    plt.title('Elevation Profile')
    plt.grid(True)
    plt.savefig(elevation_profile_path)
    plt.close()

    map_html = m._repr_html_()
    return render_template(
        'map.html',
        map_html=map_html,
        waypoints=waypoints,
        options=options,
        angles=angles,
        elevation_profile='elevation_profile.png',
        line_types=line_types,
        construction_types=construction_types,
        symbols=symbols,
        table_data=table_data,
        boq_sebelum_tiang_beton_count=boq_sebelum_tiang_beton_count,
        boq_sebelum_tiang_besi_count=boq_sebelum_tiang_besi_count,
        boq_jasa_pengecoran=boq_jasa_pengecoran,
        boq_penitikan_koordinat=boq_penitikan_koordinat,
        boq_pengecatan_tiang=boq_pengecatan_tiang,
        total_jtr_length=total_jtr_length * multiplier
    )

@app.route('/static/<filename>')
def send_elevation_profile(filename):
    return send_file(os.path.join('static', filename))

if __name__ == '__main__':
    app.run(debug=True)
