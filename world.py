# world.py
import math
from config import CHUNK_SIZE, GROUND_LEVEL, chunk_update_queue, LOADS_PER_FRAME
from OpenGL.GL import *
from chunk_worker import generated_chunks_queue
from render import create_vbo_from_vertex_data, build_chunk_vertex_data
import bulletmarks

def create_initial_world():
    return {}

def chunk_coords_from_world(x, z):
    cx = math.floor(x / CHUNK_SIZE)
    cz = math.floor(z / CHUNK_SIZE)
    return cx, cz

def unload_chunk_now(cx, cz, world, chunk_vbos):
    base_x = cx * CHUNK_SIZE
    base_z = cz * CHUNK_SIZE
    to_remove = []
    for (bx, by, bz) in list(world.keys()):
        if base_x <= bx < base_x + CHUNK_SIZE and base_z <= bz < base_z + CHUNK_SIZE:
            to_remove.append((bx,by,bz))
    for coords in to_remove:
        bulletmarks.remove_bullet_marks_for_block(coords)
        del world[coords]
    if (cx, cz) in chunk_vbos:
        vbo_id, face_count, edge_count = chunk_vbos[(cx, cz)]
        glDeleteBuffers(1, [vbo_id])
        del chunk_vbos[(cx, cz)]

def remove_block(bx, by, bz, world, chunk_vbos):
    if (bx,by,bz) in world:
        bulletmarks.remove_bullet_marks_for_block((bx,by,bz))
        del world[(bx,by,bz)]
        cx, cz = chunk_coords_from_world(bx, bz)
        chunk_update_queue.append(("load", cx, cz))

def process_chunk_updates(world, chunk_vbos, generated_chunks_queue):
    processed = 0
    while not generated_chunks_queue.empty() and processed < LOADS_PER_FRAME:
        cx, cz, chunk_data, (face_data, edge_data) = generated_chunks_queue.get_nowait()
        unload_chunk_now(cx, cz, world, chunk_vbos)
        world.update(chunk_data)
        vbo_id, face_count, edge_count = create_vbo_from_vertex_data(face_data, edge_data)
        chunk_vbos[(cx, cz)] = (vbo_id, face_count, edge_count)
        processed += 1

    updates_count = 0
    new_queue = []
    while updates_count < LOADS_PER_FRAME and chunk_update_queue:
        action, cx, cz = chunk_update_queue.pop(0)
        if action == "unload":
            unload_chunk_now(cx, cz, world, chunk_vbos)
            updates_count += 1
        elif action == "load":
            base_x = cx * CHUNK_SIZE
            base_z = cz * CHUNK_SIZE
            chunk_data = {}
            for (bx, by, bz), val in world.items():
                if base_x <= bx < base_x+CHUNK_SIZE and base_z <= bz < base_z+CHUNK_SIZE:
                    chunk_data[(bx,by,bz)] = val
            face_data, edge_data = build_chunk_vertex_data(chunk_data, cx, cz)
            if (cx, cz) in chunk_vbos:
                vbo_id_old, fc_old, ec_old = chunk_vbos[(cx, cz)]
                glDeleteBuffers(1, [vbo_id_old])
                del chunk_vbos[(cx, cz)]
            vbo_id, face_count, edge_count = create_vbo_from_vertex_data(face_data, edge_data)
            chunk_vbos[(cx, cz)] = (vbo_id, face_count, edge_count)
            updates_count += 1
        else:
            new_queue.append((action, cx, cz))

    if new_queue:
        chunk_update_queue[0:0] = new_queue

def update_loaded_chunks(px, pz, world, loaded_chunks, chunk_vbos):
    from config import RENDER_DISTANCE
    pcx, pcz = chunk_coords_from_world(px, pz)
    needed_chunks = set()
    for cx in range(pcx - RENDER_DISTANCE, pcx + RENDER_DISTANCE + 1):
        for cz in range(pcz - RENDER_DISTANCE, pcz + RENDER_DISTANCE + 1):
            needed_chunks.add((cx, cz))
    to_unload = loaded_chunks - needed_chunks
    for (ucx, ucz) in to_unload:
        chunk_update_queue.append(("unload", ucx, ucz))
    to_load = needed_chunks - loaded_chunks
    for (lcx, lcz) in to_load:
        chunk_update_queue.append(("loadgen", lcx, lcz))
    loaded_chunks.clear()
    loaded_chunks.update(needed_chunks)

def all_initial_chunks_loaded(loaded_chunks, chunk_vbos):
    for cpos in loaded_chunks:
        if cpos not in chunk_vbos:
            return False
    return True
