# config.py
import math

WIN_WIDTH = 1280
WIN_HEIGHT = 720
FOV = 70.0

# Adjust these so that gameplay timing matches the original feel.
# Originally (per frame @60fps):
#   MOVE_SPEED = 0.1 units/frame → per second = 0.1 * 60 = 6 units/s
#   JUMP_SPEED = 0.2 units/frame → per second = 0.2 * 60 = 12 units/s
#   GRAVITY = 0.01 units/frame → per second = 0.01 * 60 = 0.6 units/s²
#
# However, with that gravity, a jump of 12 units/s upward would take too long to come down.
# In the original code, the apex was reached in about 20 frames (1/3 of a second).
# Starting vy: 0.2 per frame (12 units/s)
# After 20 frames, vy=0 (apex).
# In continuous time: to go from 12 units/s to 0 in 0.333s requires gravity=12/0.333=36 units/s².
#
# Thus, to preserve the original "feel":
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
