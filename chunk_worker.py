# chunk_worker.py
import threading, queue, math, random, time
from config import CHUNK_SIZE, GROUND_LEVEL, chunk_coords_from_world
from render import build_chunk_vertex_data
from entities import AmmoPickup

generation_queue = queue.Queue()
generated_chunks_queue = queue.Queue()

def generate_chunk_data(cx, cz):
    seed_val = cx * 99999 + cz
    random.seed(seed_val)
    base_x = cx * CHUNK_SIZE
    base_z = cz * CHUNK_SIZE
    chunk_data = {}
    for x in range(CHUNK_SIZE):
        for z in range(CHUNK_SIZE):
            chunk_data[(base_x+x, GROUND_LEVEL, base_z+z)] = True

    obstacle_count = random.randint(0,3)
    for _ in range(obstacle_count):
        ox = base_x + random.randint(0, CHUNK_SIZE-1)
        oz = base_z + random.randint(0, CHUNK_SIZE-1)
        height = random.randint(2,5)
        for y in range(1, height+1):
            chunk_data[(ox, y, oz)] = True
        leaf_y = height+1
        leaf_positions = [(ox, leaf_y, oz),
                          (ox+1, leaf_y, oz),
                          (ox-1, leaf_y, oz),
                          (ox, leaf_y, oz+1),
                          (ox, leaf_y, oz-1)]
        for lx, ly, lz in leaf_positions:
            chunk_data[(lx, ly, lz)] = "leaf"

    pickups = []
    pickup_types = ["pistol", "shotgun", "rocket"]
    num_pickups = random.randint(0,2)
    # Increase baseline Y to avoid clipping by placing them higher:
    # Previously: py = GROUND_LEVEL + 1.0
    # Now raise it more, say to GROUND_LEVEL + 1.5
    for _ in range(num_pickups):
        px = base_x + random.randint(0, CHUNK_SIZE-1) + 0.5
        pz = base_z + random.randint(0, CHUNK_SIZE-1) + 0.5
        py = GROUND_LEVEL + 1.5
        ammo_type = random.choice(pickup_types)
        p = AmmoPickup(px, py, pz, ammo_type, (cx, cz))
        pickups.append(p)

    return chunk_data, pickups

def chunk_generation_worker():
    while True:
        task = generation_queue.get()
        if task is None:
            break
        action, cx, cz = task
        if action == "loadgen":
            chunk_data, pickups = generate_chunk_data(cx, cz)
            vertex_data = build_chunk_vertex_data(chunk_data, cx, cz)
            generated_chunks_queue.put((cx, cz, chunk_data, vertex_data, pickups))

def start_chunk_worker():
    t = threading.Thread(target=chunk_generation_worker, daemon=True)
    t.start()
    return t
