# player.py
import math
import pygame
from config import PLAYER_COLLISION_RADIUS, PLAYER_HEIGHT, MOVE_SPEED, JUMP_SPEED, GRAVITY
from config import PLAYER_EYE_HEIGHT, MOUSE_SENSITIVITY
from pygame.locals import *

def check_collision(px, py, pz, world):
    min_x = int(math.floor(px - PLAYER_COLLISION_RADIUS))
    max_x = int(math.floor(px + PLAYER_COLLISION_RADIUS))
    min_z = int(math.floor(pz - PLAYER_COLLISION_RADIUS))
    max_z = int(math.floor(pz + PLAYER_COLLISION_RADIUS))
    for bx in range(min_x, max_x+1):
        for bz in range(min_z, max_z+1):
            min_block_y = int(math.floor(py))
            max_block_y = int(math.floor(py+PLAYER_HEIGHT))
            for by in range(min_block_y, max_block_y+1):
                if (bx,by,bz) in world:
                    return True
    return False

def slide_movement(px, py, pz, vx, vz, world):
    new_px = px + vx
    new_pz = pz + vz
    if check_collision(new_px, py, new_pz, world):
        test_px = px + vx
        if not check_collision(test_px, py, pz, world):
            px = test_px
        test_pz = pz + vz
        if not check_collision(px, py, test_pz, world):
            pz = test_pz
    else:
        px, pz = new_px, new_pz
    return px, pz

def move_player(forward, strafe, jump, px, py, pz, vy, on_ground, rx, ry, world):
    rad_y = math.radians(ry)
    fdx = math.sin(rad_y)
    fdz = -math.cos(rad_y)
    rdx = math.cos(rad_y)
    rdz = math.sin(rad_y)

    keys = pygame.key.get_pressed()
    speed_mult = 2.0 if (keys[K_LSHIFT] or keys[K_RSHIFT]) else 1.0
    speed = MOVE_SPEED * speed_mult

    vx = (forward * fdx + strafe * rdx)*speed
    vz = (forward * fdz + strafe * rdz)*speed

    px, pz = slide_movement(px, py, pz, vx, vz, world)

    if jump and on_ground:
        vy = JUMP_SPEED
        on_ground = False

    return px, py, pz, vy, on_ground

def apply_gravity(px, py, pz, vy, on_ground, world):
    vy -= GRAVITY
    new_py = py + vy

    if check_collision(px, new_py, pz, world):
        vy = 0
        on_ground = True
    else:
        py = new_py
        foot_block = (int(math.floor(px)), int(math.floor(py-0.01)), int(math.floor(pz)))
        on_ground = (foot_block in world)
    return px, py, pz, vy, on_ground

def player_pickup(px, py, pz, inventory):
    pass
