import osmnx as ox
import shapely
import numpy as np
from stl import mesh

def fetch_building_data(bbox):
    # Unpack the bounding box
    #north_lat, north_lng, south_lat, south_lng = bbox

    # Fetch building footprints within the bounding box
    #gdf = ox.features_from_bbox( bbox , tags = {'building': True})
    gdf = ox.features_from_bbox( bbox , tags = {'natural': ['water']})
    #{‘amenity’:True, ‘landuse’:[‘retail’,’commercial’]
    
    return gdf

def get_building_height(row, default_height=10):
    # Check for various height attributes
    height_attrs = ['height', 'building:height', 'building:levels']
    for attr in height_attrs:
        if attr in row:
            height = row[attr]
            if isinstance(height, (int, float)) and not np.isnan(height):
                if attr == 'building:levels':
                    return height * 3  # Assuming 3 meters per level
                return height
            elif isinstance(height, str):
                try:
                    height_value = float(height.replace('m', '').strip())
                    return height_value
                except ValueError:
                    continue
    return default_height

def create_solid_base(base_size, base_thickness=2):
    # Define vertices for the base (solid block)
    base_vertices = [
        (0, 0, 0),  # Bottom face
        (base_size, 0, 0),
        (base_size, base_size, 0),
        (0, base_size, 0),
        (0, 0, base_thickness),  # Top face (where buildings will sit)
        (base_size, 0, base_thickness),
        (base_size, base_size, base_thickness),
        (0, base_size, base_thickness)
    ]

    # Define faces for the base
    base_faces = [
        [0, 1, 5], [0, 5, 4],  # Sides
        [1, 2, 6], [1, 6, 5],
        [2, 3, 7], [2, 7, 6],
        [3, 0, 4], [3, 4, 7],
        [4, 5, 6], [4, 6, 7],  # Top face
        [0, 1, 2], [0, 2, 3]   # Bottom face
    ]

    return base_vertices, base_faces

def scale_coordinates(gdf, bbox, target_size=180, max_height_mm=40, default_height=10, base_thickness=2):
    # Unpack the bounding box
    #north_lat, north_lng, south_lat, south_lng = bbox
    south_lng, south_lat, north_lng, north_lat = bbox


    # Calculate the scale factors for x and y dimensions
    lat_range = north_lat - south_lat
    lng_range = north_lng - south_lng

    # Define the base size as 20% larger than the target area
    base_size = target_size * 1.2    

    # Calculate scaling factors based on the larger base
    scale_x = target_size / lng_range
    scale_y = target_size / lat_range

    # Calculate offsets to center the buildings on the enlarged base
    center_offset_x = (base_size - (scale_x * lng_range)) / 2
    center_offset_y = (base_size - (scale_y * lat_range)) / 2

    vertices = []
    faces = []

    # Generate and append solid base
    base_vertices, base_faces = create_solid_base(base_size, base_thickness)
    vertices.extend(base_vertices)
    faces.extend(base_faces)

    # Calculate the maximum building height
    max_building_height = gdf.apply(lambda row: get_building_height(row, default_height), axis=1).max()
    height_scale = max_height_mm / max_building_height

    for idx, row in gdf.iterrows():
        polygon = row['geometry']
        if isinstance(polygon, shapely.geometry.Polygon):
            exterior_coords = list(polygon.exterior.coords)
            base_index = len(vertices)

            # Create vertices for the building
            for coord in exterior_coords:
                x = ((coord[0] - south_lng) * scale_x) + center_offset_x
                if x > base_size:
                    x = base_size
                if x < 0:
                    x = 0
                y = ((coord[1] - south_lat) * scale_y) + center_offset_y
                if y > base_size:
                    y = base_size
                if y < 0:
                    y = 0
                if y < 0 or x < 0:
                    print(f"X: {x} Y: {y}")
                height = get_building_height(row, default_height) * height_scale
                #print(f"Building at index {idx} with coordinates {exterior_coords} has height {height}")

                v_bottom = (x, y, base_thickness)
                v_top = (x, y, height + base_thickness)
                vertices.extend([v_bottom, v_top])

            # Create side faces
            for i in range(len(exterior_coords) - 1):
                bottom1 = base_index + 2 * i
                bottom2 = base_index + 2 * (i + 1)
                top1 = base_index + 2 * i + 1
                top2 = base_index + 2 * (i + 1) + 1

                faces.append([bottom1, bottom2, top1])
                faces.append([top1, bottom2, top2])

            # Create top face
            top_face_indices = [base_index + 2 * i + 1 for i in range(len(exterior_coords) - 1)]
            for i in range(1, len(top_face_indices) - 1):
                faces.append([top_face_indices[0], top_face_indices[i], top_face_indices[i + 1]])

            # Create bottom face (this was omitted in the previous version)
            bottom_face_indices = [base_index + 2 * i for i in range(len(exterior_coords) - 1)]
            for i in range(1, len(bottom_face_indices) - 1):
                faces.append([bottom_face_indices[0], bottom_face_indices[i], bottom_face_indices[i + 1]])

    vertices = np.array(vertices)
    faces = np.array(faces)

    return vertices, faces

def save_to_stl(vertices, faces, filename):
    mesh_data = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
    for i, face in enumerate(faces):
        for j in range(3):
            mesh_data.vectors[i][j] = vertices[face[j], :]

    # Create a new plot
    #figure = pyplot.figure()
    #axes = figure.add_subplot(projection='3d')
    #axes.add_collection3d(mplot3d.art3d.Poly3DCollection(mesh_data.vectors))
    #scale = mesh_data.points.flatten()
    #axes.auto_scale_xyz(scale, scale, scale)
    #pyplot.show()

    mesh_data.save(filename)

def main():
    bbox = (4.87123, 52.35893, 4.93389, 52.38351)  #Amsterdam
    #bbox = (-122.4194, 37.7749, -122.3894, 37.8049) #Suddersdorf
    #bbox = min Longitude , min Latitude , max Longitude , max Latitude 
    gdf = fetch_building_data(bbox)
    vertices, faces = scale_coordinates(gdf, bbox, target_size=180, max_height_mm=1, default_height=40, base_thickness=2)
    save_to_stl(vertices, faces, 'buildings_with_base.stl')

if __name__ == "__main__":
    main()
