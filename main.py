from pyomo.environ import *
import pandas as pd
import numpy as np
import requests
import time

API_KEY_GOOGLE = ""


def obtener_distancias_google(coord_df, api_key):
    id_list = coord_df["ID"].tolist()
    coords_dict = {
        row["ID"]: f"{row['Latitude']},{row['Longitude']}"
        for _, row in coord_df.iterrows()
    }

    M = {}
    print(len(id_list))
    cou = 0
    for i in id_list:
        for j in id_list:
            if i == j:
                M[(i, j)] = 0.0
                continue

            origin = coords_dict[i]
            destination = coords_dict[j]
            url = (
                f"https://maps.googleapis.com/maps/api/distancematrix/json?"
                f"origins={origin}&destinations={destination}&"
                f"key={api_key}&units=metric"
            )

            try:
                response = requests.get(url)
                cou += 1
                data = response.json()

                if data["status"] != "OK":
                    print(f"Error API con {i}->{j}: {data['status']}")
                    M[(i, j)] = float("inf")
                    continue

                dist = data["rows"][0]["elements"][0]["distance"]["value"] / 1000
                M[(i, j)] = round(dist, 2)

                print(cou)

            except Exception as e:
                print(f"Error consultando {i}->{j}: {e}")
                M[(i, j)] = float("inf")

            time.sleep(0.1)

    dist_df = pd.DataFrame(
        [[M[(i, j)] for j in id_list] for i in id_list], index=id_list, columns=id_list
    )
    dist_df.to_csv("content/distances.csv")

    return M


def definirCasoPrueba(usarExistente):
    clients_df = pd.read_csv("content/clients.csv")
    depots_df = pd.read_csv("content/depots.csv")
    vehicles_df = pd.read_csv("content/vehicles.csv")

    CD = ["CD" + str(i + 1) for i in range(len(depots_df))]
    C = ["C" + str(i + 1) for i in range(len(clients_df))]
    P = C + CD
    V = ["V" + str(i + 1) for i in range(len(vehicles_df))]

    D = dict(zip(C, clients_df["Demand"]))
    Q = dict(zip(V, vehicles_df["Capacity"]))
    G = dict(zip(V, vehicles_df["Range"]))
    A = {cd: 50000 for cd in CD}

    clients_df["ID"] = C
    depots_df["ID"] = CD

    coord_df = pd.concat(
        [
            clients_df[["ID", "Latitude", "Longitude"]],
            depots_df[["ID", "Latitude", "Longitude"]],
        ]
    ).reset_index(drop=True)

    id_list = coord_df["ID"].tolist()

    if usarExistente:
        distances_df = pd.read_csv("content/distances.csv", index_col=0)
        M = {}
        for i in id_list:
            for j in id_list:
                M[(i, j)] = round(distances_df.loc[i, j], 2) if i != j else 0.0
    else:
        M = obtener_distancias_google(coord_df, API_KEY_GOOGLE)

    F1 = 1500
    F2 = 5000
    F3 = 700

    return CD, C, P, V, D, Q, G, A, M, F1, F2, F3, coord_df


def modelo(CD, C, P, V, D, Q, G, A, M, F1, F2, F3):
    model = ConcreteModel()

    model.x = Var(V, P, P, within=Binary)
    model.y = Var(V, within=Binary)
    model.z = Var(V, CD, within=Binary)

    model.objetivo = Objective(
        expr=(F1 + F2 + F3)
        * sum(M[m, n] * model.x[k, m, n] for k in V for m in P for n in P if m != n),
        sense=minimize,
    )

    model.inicio_CD = ConstraintList()
    for k in V:
        model.inicio_CD.add(
            sum(model.x[k, i, n] for i in CD for n in P if n != i) == model.y[k]
        )

    model.uso_vehiculo = ConstraintList()
    for k in V:
        model.uso_vehiculo.add(
            sum(model.x[k, i, n] for i in P for n in P if i != n) / len(P) <= model.y[k]
        )

    model.fin_CD = ConstraintList()
    for k in V:
        for i in CD:
            model.fin_CD.add(
                sum(model.x[k, n, i] for n in P if n != i)
                == sum(model.x[k, i, n] for n in P if n != i)
            )

    model.entrada_salida_cliente = ConstraintList()
    for k in V:
        for j in C:
            model.entrada_salida_cliente.add(
                sum(model.x[k, n, j] for n in P if n != j)
                == sum(model.x[k, j, n] for n in P if n != j)
            )

    model.autonomia = ConstraintList()
    for k in V:
        model.autonomia.add(
            sum(M[m, n] * model.x[k, m, n] for m in P for n in P if m != n) <= G[k]
        )

    model.capacidad_vehiculo = ConstraintList()
    for k in V:
        model.capacidad_vehiculo.add(
            sum(D[j] * sum(model.x[k, m, j] for m in P if m != j) for j in C) <= Q[k]
        )

    model.cobertura_clientes = ConstraintList()
    for j in C:
        model.cobertura_clientes.add(
            sum(model.x[k, m, j] for k in V for m in P if m != j) >= 1
        )

    model.inicia_en = ConstraintList()
    for i in CD:
        for k in V:
            model.inicia_en.add(
                expr=sum(model.x[k, i, n] for n in P) - 1e9 * model.z[k, i] <= 0
            )

    model.capacidad_cd = ConstraintList()
    for i in CD:
        model.capacidad_cd.add(
            sum(D[j] * sum(model.z[k, i] for k in V) for j in C) <= A[i]
        )

    return model


def imprimir_rutas(model, V, P):
    vehicle_paths = {k: [] for k in V}

    for k in V:
        for m in P:
            for n in P:
                if (
                    m != n
                    and model.x[k, m, n].value is not None
                    and model.x[k, m, n].value > 0.5
                ):
                    vehicle_paths[k].append((m, n))

    for k, path in vehicle_paths.items():
        print(f"Vehículo {k} sigue la ruta:")
        for m, n in path:
            print(f"  {m} -> {n}")
        print()

    return vehicle_paths


def mostrar_mapa_google_maps(coord_df, CD, V, P, vehicle_paths, api_key):
    coords_dict = dict(
        zip(coord_df["ID"], zip(coord_df["Latitude"], coord_df["Longitude"]))
    )

    center_lat = coord_df["Latitude"].mean()
    center_lng = coord_df["Longitude"].mean()

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Rutas Óptimas</title>
    <script src="https://maps.googleapis.com/maps/api/js?key={api_key}"></script>
    <style>#map {{ height: 100vh; width: 100%; }}</style>
</head>
<body>
    <div id="map"></div>
    <script>
        function initMap() {{
            var map = new google.maps.Map(document.getElementById('map'), {{
                zoom: 12,
                center: {{lat: {center_lat}, lng: {center_lng}}}
            }});

            var markers = {{}};
    """

    for id_, (lat, lng) in coords_dict.items():
        color = "http://maps.google.com/mapfiles/ms/icons/"
        color += "green-dot.png" if id_ in CD else "blue-dot.png"
        html += f"""
            var marker_{id_} = new google.maps.Marker({{
                position: {{lat: {lat}, lng: {lng}}}, 
                map: map,
                title: "{id_}",
                icon: "{color}"
            }});
            markers["{id_}"] = marker_{id_};
        """

    html += """
            var directionsService = new google.maps.DirectionsService();
    """

    color_list = [
        "#FF000",
        "#0000FF",
        "#00FF00",
        "#FFA500",
        "#800080",
        "#00CED1",
        "#FF69B4",
    ]

    for idx, (k, path) in enumerate(vehicle_paths.items()):
        color = color_list[idx % len(color_list)]
        for step_idx, (i, j) in enumerate(path):
            html += f"""
            var directionsRenderer_{i}_{j} = new google.maps.DirectionsRenderer({{
                map: map,
                suppressMarkers: true,
                preserveViewport: true,
                polylineOptions: {{
                    strokeColor: "{color}",
                    strokeWeight: 4
                }}
            }});
            directionsService.route({{
                origin: markers["{i}"].getPosition(),
                destination: markers["{j}"].getPosition(),
                travelMode: google.maps.TravelMode.DRIVING
            }}, function(response, status) {{
                if (status === google.maps.DirectionsStatus.OK) {{
                    directionsRenderer_{i}_{j}.setDirections(response);
                }} else {{
                    console.error('Directions request failed due to ' + status);
                }}
            }});
            """

    html += """
        }
        window.onload = initMap;
    </script>
</body>
</html>
"""

    with open("rutas_google_maps.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("✅ Mapa generado: rutas_google_maps.html (abre en navegador)")


# ============================
# MENÚ Y EJECUCIÓN
# ============================


def imprimirMenu():
    print("=" * 30 + " MENÚ " + "=" * 30)
    print("1. Usar archivo distances.csv existente")
    print("2. Consultar Google Maps API y guardar archivo")
    return int(input("Selecciona opción: "))


# MAIN
Model = None
op = imprimirMenu()

usar_csv = op == 1
CD, C, P, V, D, Q, G, A, M, F1, F2, F3, coord_df = definirCasoPrueba(usar_csv)

Model = modelo(CD, C, P, V, D, Q, G, A, M, F1, F2, F3)

SolverFactory("glpk").solve(Model)

vehicle_paths = imprimir_rutas(Model, V, P)

mostrar_mapa_google_maps(coord_df, CD, V, P, vehicle_paths, API_KEY_GOOGLE)
