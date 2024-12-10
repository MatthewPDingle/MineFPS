# config.py
import math

WIN_WIDTH = 1280
WIN_HEIGHT = 720
FOV = 70.0

MOVE_SPEED = 6.0
MOUSE_SENSITIVITY = 0.2
JUMP_SPEED = 12.0
GRAVITY = 36.0
PLAYER_EYE_HEIGHT = 1.7
PLAYER_COLLISION_RADIUS = 0.3
PLAYER_HEIGHT = 1.7

CHUNK_SIZE = 16
RENDER_DISTANCE = 4
GROUND_LEVEL = 0
LOADS_PER_FRAME = 1

WEAPONS = [
    {"name":"Pistol", "color":(0.5,0.5,0.5), "id":"pistol"},
    {"name":"Shotgun", "color":(0.0,0.0,0.8), "id":"shotgun"},
    {"name":"Rocket Launcher", "color":(0.8,0.0,0.0), "id":"rocket"}
]

all_pickups = []
chunk_update_queue = []

def chunk_coords_from_world(x, z):
    cx = math.floor(x / CHUNK_SIZE)
    cz = math.floor(z / CHUNK_SIZE)
    return cx, cz
