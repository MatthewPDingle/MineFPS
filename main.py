# main.py
import sys, math, time, random
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

from config import *
from config import chunk_coords_from_world
from render import set_display_mode, draw_text_2d_cached, render_chunk_vbo, text_cache, build_chunk_vertex_data, create_vbo_from_vertex_data, draw_box
from world import (create_initial_world, process_chunk_updates, all_initial_chunks_loaded,
                   update_loaded_chunks, chunk_update_queue, remove_block)
from player import move_player, apply_gravity, player_pickup
from entities import Bullet, Rocket, Explosion
from chunk_worker import generation_queue, generated_chunks_queue, start_chunk_worker
import bulletmarks
import entities

player_health = 100
PLAYER_MAX_HEALTH = 100

DAMAGE_BULLET = 10
DAMAGE_SHOTGUN_PELLET = 4
DAMAGE_ROCKET = 100
DAMAGE_ROCKET_PARTICLE = 4

current_weapon_index = 0
inventory = {
    "pistol": {"ammo":50, "owned":True},
    "shotgun": {"ammo":10, "owned":True},
    "rocket": {"ammo":5, "owned":True}
}

weapon_fire_cooldown = {
    "pistol": 0.0,
    "shotgun": 0.5,
    "rocket": 1.0
}
last_fire_time = {
    "pistol": 0.0,
    "shotgun": 0.0,
    "rocket": 0.0
}

def get_weapon_color(wid):
    CUSTOM_WEAPON_COLORS = {
        "pistol": (0.8,0.8,0.8),
        "shotgun": (0.3,0.3,0.3),
        "rocket": (0.8,0.4,0.0)
    }
    if wid in CUSTOM_WEAPON_COLORS:
        return CUSTOM_WEAPON_COLORS[wid]
    for wdef in WEAPONS:
        if wdef["id"] == wid:
            return wdef["color"]
    return (1,1,1)

def current_weapon_id():
    return WEAPONS[current_weapon_index]["id"]

def current_weapon_name():
    return WEAPONS[current_weapon_index]["name"]

def current_weapon_ammo():
    wid = current_weapon_id()
    return inventory[wid]["ammo"]

def draw_pistol():
    glColor3f(0.8,0.8,0.8)
    slide_half_w = 0.03
    slide_half_h = 0.03
    slide_half_l = 0.15
    slide_center_z = -0.075
    draw_box(0,0,slide_center_z, slide_half_w, slide_half_h, slide_half_l)
    handle_half_w = 0.02
    handle_half_h = 0.05
    handle_half_l = 0.05
    handle_center_z = -0.05
    handle_center_y = -0.03 - handle_half_h
    draw_box(0, handle_center_y, handle_center_z, handle_half_w, handle_half_h, handle_half_l)
    barrel_half_w = 0.01
    barrel_half_h = 0.01
    barrel_half_l = 0.05
    barrel_center_z = -0.175
    draw_box(0,0,barrel_center_z, barrel_half_w, barrel_half_h, barrel_half_l)

def draw_shotgun():
    glColor3f(0.3,0.3,0.3)
    slide_half_w = 0.03
    slide_half_h = 0.03
    slide_half_l = 0.20
    slide_center_z = -0.1
    draw_box(0,0,slide_center_z, slide_half_w, slide_half_h, slide_half_l)
    handle_half_w = 0.02
    handle_half_h = 0.05
    handle_half_l = 0.05
    handle_center_z = -0.05
    handle_center_y = -0.03 - handle_half_h
    draw_box(0, handle_center_y, handle_center_z, handle_half_w, handle_half_h, handle_half_l)
    barrel_half_w = 0.01
    barrel_half_h = 0.01
    barrel_half_l = 0.1
    barrel_center_z = -0.3
    draw_box(0,0,barrel_center_z, barrel_half_w, barrel_half_h, barrel_half_l)

def draw_rocket_launcher():
    glColor3f(0.8,0.4,0.0)
    length = 0.7
    radius = 0.05
    glPushMatrix()
    glRotatef(180,0,1,0)
    gluCylinder(cylinder_quad, radius, radius, length, 16,1)
    glPushMatrix()
    glTranslatef(0,0,length)
    gluDisk(disk_quad,0,radius,16,1)
    glPopMatrix()
    gluDisk(disk_quad,0,radius,16,1)
    glPopMatrix()

    handle_hw = 0.02
    handle_hh = 0.05
    handle_hl = 0.02
    handle_cz = -0.15
    handle_cy = -0.07
    draw_box(0, handle_cy, handle_cz, handle_hw, handle_hh, handle_hl)

    fin_hw = 0.01
    fin_hh = 0.02
    fin_hl = 0.02
    draw_box(0, 0.07, -fin_hl, fin_hw, fin_hh, fin_hl)
    draw_box(0, -0.07, -fin_hl, fin_hw, fin_hh, fin_hl)
    draw_box(-0.07,0,-fin_hl, fin_hh,fin_hw,fin_hl)
    draw_box(0.07,0,-fin_hl, fin_hh,fin_hw,fin_hl)

    sight_hw = 0.01
    sight_hh = 0.01
    sight_hl = 0.05
    sight_cz = -0.025
    sight_cy = 0.07
    draw_box(0,sight_cy,sight_cz,sight_hw,sight_hh,sight_hl)

def draw_simple_weapon(wid):
    if wid == "pistol":
        draw_pistol()
    elif wid == "shotgun":
        draw_shotgun()
    elif wid == "rocket":
        draw_rocket_launcher()
    else:
        glColor3f(*get_weapon_color(wid))
        draw_box(0,0,0,0.1,0.1,0.2)

def procedural_clouds(px, pz, radius=RENDER_DISTANCE):
    from config import chunk_coords_from_world
    pcx, pcz = chunk_coords_from_world(px, pz)
    clouds = []
    cloud_rand = random.Random() 
    for cx in range(pcx - radius, pcx + radius + 1):
        for cz in range(pcz - radius, pcz + radius + 1):
            seed_val = (cx * 374761393 + cz * 668265263) ^ 0x12345678
            cloud_rand.seed(seed_val)
            cloud_x = cloud_rand.uniform(cx*CHUNK_SIZE, cx*CHUNK_SIZE+CHUNK_SIZE)
            cloud_z = cloud_rand.uniform(cz*CHUNK_SIZE, cz*CHUNK_SIZE+CHUNK_SIZE)
            cloud_y = cloud_rand.uniform(15,20)
            size = cloud_rand.uniform(5,10)
            clouds.append((cloud_x, cloud_y, cloud_z, size))
    return clouds

def draw_clouds(px, py, pz, rx, ry):
    clouds = procedural_clouds(px, pz)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(1.0,1.0,1.0,0.8)
    for (cx,cy,cz,size) in clouds:
        dist = math.sqrt((cx - px)**2 + (cz - pz)**2)
        if dist < CHUNK_SIZE*(RENDER_DISTANCE+1):
            glBegin(GL_QUADS)
            glVertex3f(cx - size, cy, cz - size)
            glVertex3f(cx + size, cy, cz - size)
            glVertex3f(cx + size, cy, cz + size)
            glVertex3f(cx - size, cy, cz + size)
            glEnd()
    glDisable(GL_BLEND)

def draw_bullet_marks():
    from bulletmarks import get_all_bullet_marks
    marks_dict = get_all_bullet_marks()
    size = 0.02
    glEnable(GL_POLYGON_OFFSET_FILL)
    glPolygonOffset(-1.0,-1.0)
    glColor3f(0,0,0)
    glBegin(GL_QUADS)
    for (bx,by,bz), marks in marks_dict.items():
        for (hx, hy, hz, nx, ny, nz) in marks:
            offset = 0.001
            hx2 = hx + nx*offset
            hy2 = hy + ny*offset
            hz2 = hz + nz*offset
            up = (0,1,0)
            if abs(ny)>0.9:
                up = (1,0,0)
            ux,uy,uz = up
            nxn, nyn, nzn = nx, ny, nz
            t1x = uy*nzn - uz*nyn
            t1y = uz*nxn - ux*nzn
            t1z = ux*nyn - uy*nxn
            t1len = math.sqrt(t1x*t1x + t1y*t1y + t1z*t1z)
            if t1len > 1e-9:
                t1x/=t1len; t1y/=t1len; t1z/=t1len

            t2x = nyn*t1z - nzn*t1y
            t2y = nzn*t1x - nxn*t1z
            t2z = nxn*t1y - nyn*t1x
            t2len = math.sqrt(t2x*t2x + t2y*t2y + t2z*t2z)
            if t2len > 1e-9:
                t2x/=t2len; t2y/=t2len; t2z/=t2len

            ox1 = t1x*size + t2x*size
            oy1 = t1y*size + t2y*size
            oz1 = t1z*size + t2z*size

            ox2 = t1x*size - t2x*size
            oy2 = t1y*size - t2y*size
            oz2 = t1z*size - t2z*size

            ox3 = -t1x*size - t2x*size
            oy3 = -t1y*size - t2y*size
            oz3 = -t1z*size - t2z*size

            ox4 = -t1x*size + t2x*size
            oy4 = -t1y*size + t2y*size
            oz4 = -t1z*size + t2z*size

            glVertex3f(hx2+ox1, hy2+oy1, hz2+oz1)
            glVertex3f(hx2+ox2, hy2+oy2, hz2+oz2)
            glVertex3f(hx2+ox3, hy2+oy3, hz2+oz3)
            glVertex3f(hx2+ox4, hy2+oy4, hz2+oz4)
    glEnd()
    glDisable(GL_POLYGON_OFFSET_FILL)

def line_block_intersect(x1,y1,z1,x2,y2,z2,bx,by,bz):
    tmin = 0.0
    tmax = 1.0
    dx = x2 - x1
    dy = y2 - y1
    dz = z2 - z1

    for axis, bmin, bmax, dv in [('x',bx,bx+1,dx), ('y',by,by+1,dy), ('z',bz,bz+1,dz)]:
        if abs(dv)<1e-9:
            p0 = {'x':x1,'y':y1,'z':z1}[axis]
            if p0 < bmin or p0 > bmax:
                return None
        else:
            t0 = (bmin - {'x':x1,'y':y1,'z':z1}[axis])/dv
            t1 = (bmax - {'x':x1,'y':y1,'z':z1}[axis])/dv
            if t0>t1: t0,t1 = t1,t0
            if t1 < tmin or t0 > tmax:
                return None
            tmin = max(tmin,t0)
            tmax = min(tmax,t1)
            if tmin > tmax:
                return None

    ix = x1 + dx*tmin
    iy = y1 + dy*tmin
    iz = z1 + dz*tmin
    eps=1e-5
    normal = [0,0,0]
    if abs(ix - bx) < eps:
        normal = [-1,0,0]
    elif abs(ix - (bx+1)) < eps:
        normal = [1,0,0]
    elif abs(iy - by) < eps:
        normal = [0,-1,0]
    elif abs(iy - (by+1)) < eps:
        normal = [0,1,0]
    elif abs(iz - bz) < eps:
        normal = [0,0,-1]
    elif abs(iz - (bz+1)) < eps:
        normal = [0,0,1]

    return (ix,iy,iz, normal[0], normal[1], normal[2])

def main():
    pygame.init()
    pygame.font.init()
    pygame.mixer.init()

    snd_explosion = pygame.mixer.Sound("assets/explosion.flac")
    snd_hit = pygame.mixer.Sound("assets/hit.flac")
    snd_pickup = pygame.mixer.Sound("assets/pickup.flac")
    snd_pistol = pygame.mixer.Sound("assets/pistol.flac")
    snd_rocketlauncher = pygame.mixer.Sound("assets/rocketlauncher.flac")
    snd_shotgun = pygame.mixer.Sound("assets/shotgun.flac")
    snd_ammo = pygame.mixer.Sound("assets/ammo.flac")

    entities.enemy_pistol_sound = snd_pistol

    font = pygame.font.SysFont("Arial", 18)

    fullscreen = False
    screen = set_display_mode(fullscreen)

    pygame.mouse.set_visible(False)
    pygame.mouse.set_relative_mode(True)

    glClearColor(0.5, 0.7, 1.0, 1.0)
    glEnable(GL_DEPTH_TEST)

    global sphere_quad, cylinder_quad, disk_quad
    sphere_quad = gluNewQuadric()
    cylinder_quad = gluNewQuadric()
    disk_quad = gluNewQuadric()

    worker_thread = start_chunk_worker()

    start_px, start_py, start_pz = 8.0, 2.0, 2.0
    px = None
    py = None
    pz = None
    rx, ry = 0.0, 90.0
    vy = 0.0
    on_ground = False

    world = create_initial_world()
    loaded_chunks = set()
    chunk_vbos = {}

    clock = pygame.time.Clock()

    update_loaded_chunks(start_px, start_pz, world, loaded_chunks, chunk_vbos)

    global player_health
    global current_weapon_index
    global inventory

    bullets = []
    rockets = []
    explosions = []
    bullet_last_positions = []

    running = True
    random.seed()

    from config import all_enemies

    def play_sound_with_distance(sound, sx, sy, sz):
        if px is None:
            sound.set_volume(1.0)
            sound.play()
            return
        dist = math.sqrt((sx - px)**2 + (sy - py)**2 + (sz - pz)**2)
        if dist > 32.0:
            vol = 0.0
        else:
            vol = 1.0 - (dist/32.0)
        sound.set_volume(vol)
        if vol > 0.0:
            sound.play()

    while running:
        dt = clock.tick()
        dt_s = dt/1000.0

        fps = 1000.0/dt if dt>0 else 0.0

        generation_tasks = [(a,cx,cz) for (a,cx,cz) in chunk_update_queue if a == "loadgen"]
        chunk_update_queue[:] = [(a,cx,cz) for (a,cx,cz) in chunk_update_queue if a != "loadgen"]
        for t in generation_tasks:
            generation_queue.put(t)

        process_chunk_updates(world, chunk_vbos, generated_chunks_queue)

        if px is None and all_initial_chunks_loaded(loaded_chunks, chunk_vbos):
            px, py, pz = start_px, start_py, start_pz

        keys = pygame.key.get_pressed()
        current_time = time.time()

        for event in pygame.event.get():
            if event.type == QUIT:
                running=False
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    running=False
                elif event.key == K_F11:
                    fullscreen = not fullscreen
                    if fullscreen:
                        modes = pygame.display.list_modes()
                        if not modes or modes == -1:
                            display_info = pygame.display.Info()
                            width = display_info.current_w
                            height = display_info.current_h
                        else:
                            width, height = modes[0]
                        screen = pygame.display.set_mode((width, height), DOUBLEBUF|OPENGL|FULLSCREEN)
                    else:
                        width, height = WIN_WIDTH, WIN_HEIGHT
                        screen = pygame.display.set_mode((width, height), DOUBLEBUF|OPENGL)
                    glViewport(0, 0, width, height)
                    glMatrixMode(GL_PROJECTION)
                    glLoadIdentity()
                    gluPerspective(FOV, width/float(height), 0.1, 1000.0)
                    glMatrixMode(GL_MODELVIEW)
                    glLoadIdentity()
                    pygame.mouse.set_visible(False)
                    pygame.mouse.set_relative_mode(True)
                elif event.key == K_1:
                    current_weapon_index = 0
                elif event.key == K_2:
                    current_weapon_index = 1
                elif event.key == K_3:
                    current_weapon_index = 2
            elif event.type == MOUSEMOTION:
                mx, my = event.rel
                ry += mx * MOUSE_SENSITIVITY
                rx -= my * MOUSE_SENSITIVITY
                if rx > 89:
                    rx = 89
                if rx < -89:
                    rx = -89
            elif event.type == MOUSEBUTTONDOWN:
                if event.button == 1 and px is not None:
                    wid = current_weapon_id()
                    cooldown = weapon_fire_cooldown[wid]
                    if (current_time - last_fire_time[wid]) >= cooldown:
                        if inventory[wid]["owned"] and inventory[wid]["ammo"]>0:
                            inventory[wid]["ammo"] -= 1
                            start_x = px
                            start_y = py + PLAYER_EYE_HEIGHT
                            start_z = pz
                            rad_x = math.radians(rx)
                            rad_y = math.radians(ry)
                            dx = math.sin(rad_y)*math.cos(rad_x)
                            dy = math.sin(rad_x)
                            dz = -math.cos(rad_y)*math.cos(rad_x)

                            if wid=="pistol":
                                play_sound_with_distance(snd_pistol, px, py, pz)
                                b = Bullet(start_x, start_y, start_z, dx,dy,dz, radius=0.05)
                                bullets.append(b)
                                bullet_last_positions.append((id(b),start_x,start_y,start_z))
                            elif wid=="shotgun":
                                play_sound_with_distance(snd_shotgun, px, py, pz)
                                for i in range(8):
                                    angle_h = random.uniform(-10,10)
                                    angle_v = random.uniform(-2,2)
                                    rad_y_off = math.radians(ry+angle_h)
                                    rad_x_off = math.radians(rx+angle_v)
                                    dx2 = math.sin(rad_y_off)*math.cos(rad_x_off)
                                    dy2 = math.sin(rad_x_off)
                                    dz2 = -math.cos(rad_y_off)*math.cos(rad_x_off)
                                    b = Bullet(start_x, start_y, start_z, dx2,dy2,dz2, radius=0.05)
                                    bullets.append(b)
                                    bullet_last_positions.append((id(b),start_x,start_y,start_z))
                            elif wid=="rocket":
                                play_sound_with_distance(snd_rocketlauncher, px, py, pz)
                                r = Rocket(start_x,start_y,start_z, dx,dy,dz)
                                rockets.append(r)

                            last_fire_time[wid] = current_time
                elif event.button == 4:
                    for i in range(len(WEAPONS)):
                        current_weapon_index = (current_weapon_index-1) % len(WEAPONS)
                        wid = WEAPONS[current_weapon_index]["id"]
                        if inventory[wid]["owned"]:
                            break
                elif event.button == 5:
                    for i in range(len(WEAPONS)):
                        current_weapon_index = (current_weapon_index+1) % len(WEAPONS)
                        wid = WEAPONS[current_weapon_index]["id"]
                        if inventory[wid]["owned"]:
                            break

        if px is not None:
            forward = (keys[K_w] - keys[K_s])
            strafe = (keys[K_d] - keys[K_a])
            jump = keys[K_SPACE]
            px, py, pz, vy, on_ground = move_player(forward, strafe, jump, px, py, pz, vy, on_ground, rx, ry, world, dt_s)
            px, py, pz, vy, on_ground = apply_gravity(px, py, pz, vy, on_ground, world, dt_s)
            player_pickup(px, py, pz, inventory, snd_ammo)
            update_loaded_chunks(px, pz, world, loaded_chunks, chunk_vbos)

            new_bullets = []
            bullet_last_positions_new = []
            from config import all_enemies
            for b in bullets:
                prev_pos = None
                for (bid,ix,iy,iz) in bullet_last_positions:
                    if bid == id(b):
                        prev_pos = (ix,iy,iz)
                        break
                alive = b.update(dt_s, world, all_enemies)  # Pass world and all_enemies here
                if not alive:
                    # bullet died (hit block or enemy)
                    bx = int(math.floor(b.x))
                    by = int(math.floor(b.y))
                    bz = int(math.floor(b.z))
                    if (bx,by,bz) in world:
                        snd_hit.play()
                        if prev_pos is not None:
                            res = line_block_intersect(prev_pos[0],prev_pos[1],prev_pos[2],b.x,b.y,b.z,bx,by,bz)
                            if res:
                                ix,iy,iz, nx,ny,nz = res
                                bulletmarks.add_bullet_mark(bx, by, bz, ix, iy, iz, nx, ny, nz)
                    continue
                # Still alive
                new_bullets.append(b)
                bullet_last_positions_new.append((id(b),b.x,b.y,b.z))

            bullets = new_bullets
            bullet_last_positions = bullet_last_positions_new

            new_rockets = []
            for r in rockets:
                was_alive = r.alive
                still_alive = r.update(world, all_enemies, explosions, dt_s)
                if was_alive and not r.alive:
                    snd_explosion.play()
                if still_alive:
                    new_rockets.append(r)
            rockets = new_rockets

            explosions = [e for e in explosions if e.update(dt_s)]

            new_enemies = []
            player_pos = (px, py, pz)
            for e in all_enemies:
                alive = e.update(dt_s, player_pos, world, bullets)
                if e.health > 0 and alive:
                    new_enemies.append(e)
            all_enemies[:] = new_enemies

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        if px is not None:
            rad_x = math.radians(rx)
            rad_y = math.radians(ry)
            dx = math.sin(rad_y)*math.cos(rad_x)
            dy = math.sin(rad_x)
            dz = -math.cos(rad_y)*math.cos(rad_x)
            eye_y = py + PLAYER_EYE_HEIGHT

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            gluLookAt(px, eye_y, pz, px+dx, eye_y+dy, pz+dz, 0,1,0)

            projection = glGetDoublev(GL_PROJECTION_MATRIX)
            modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
            viewport = glGetIntegerv(GL_VIEWPORT)

            draw_clouds(px, py, pz, rx, ry)

            for (cx,cz) in loaded_chunks:
                if (cx,cz) in chunk_vbos:
                    vbo_id, face_count, edge_count = chunk_vbos[(cx, cz)]
                    render_chunk_vbo(vbo_id, face_count, edge_count)

            for b in bullets:
                b.draw(sphere_quad)
            for r in rockets:
                r.draw(cylinder_quad)
            for e in explosions:
                e.draw(px, py, pz, sphere_quad)

            draw_bullet_marks()

            for p in all_pickups:
                p.draw()

            for en in all_enemies:
                en.draw()

            # Check enemy HP bars
            enemy_positions_2d = []
            w, h = screen.get_size()

            # Compute forward vector of camera for visibility check
            cam_rad_x = math.radians(rx)
            cam_rad_y = math.radians(ry)
            fdx = math.sin(cam_rad_y)*math.cos(cam_rad_x)
            fdy = math.sin(cam_rad_x)
            fdz = -math.cos(cam_rad_y)*math.cos(cam_rad_x)

            for en in all_enemies:
                dist = math.sqrt((en.x - px)**2 + (en.y - py)**2 + (en.z - pz)**2)
                if dist <= 20.0 and en.health > 0:
                    exv = en.x - px
                    eyv = (en.y+1.2) - eye_y
                    ezv = en.z - pz
                    dot = exv*fdx + eyv*fdy + ezv*fdz
                    if dot < 0:
                        continue
                    wx, wy, wz = gluProject(en.x, en.y+1.2, en.z, modelview, projection, viewport)
                    if wz < 0.0 or wz > 1.0:
                        continue
                    if wx < 0 or wx > w or wy < 0 or wy > h:
                        continue
                    enemy_positions_2d.append((wx, h - wy, en.health, dist))

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        w, h = screen.get_size()
        gluPerspective(FOV, w/float(h), 0.1, 1000.0)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glDisable(GL_DEPTH_TEST)
        glTranslatef(0.0, -0.2, -0.5)
        if px is not None:
            draw_simple_weapon(current_weapon_id())

        glEnable(GL_DEPTH_TEST)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        glDisable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        w, h = screen.get_size()
        glOrtho(0, w, h, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glColor3f(1,1,1)
        cx = w//2
        cy = h//2
        # Crosshair
        glBegin(GL_LINES)
        glVertex2f(cx - 10, cy)
        glVertex2f(cx + 10, cy)
        glVertex2f(cx, cy - 10)
        glVertex2f(cx, cy + 10)
        glEnd()

        if px is not None:
            draw_text_2d_cached(font, f"FPS: {fps:.1f}", 10, 10)
            wname = current_weapon_name()
            wammo = current_weapon_ammo()
            draw_text_2d_cached(font, f"Weapon: {wname}  Ammo: {wammo}", 10, h-30)
            def draw_health_bar(w,h):
                bar_width = 200
                bar_height = 20
                x = 10
                y = 40
                health_ratio = player_health / float(PLAYER_MAX_HEALTH)
                glColor3f(0.2,0.2,0.2)
                glBegin(GL_QUADS)
                glVertex2f(x, y)
                glVertex2f(x+bar_width, y)
                glVertex2f(x+bar_width, y+bar_height)
                glVertex2f(x, y+bar_height)
                glEnd()
                glColor3f(1.0 - health_ratio,health_ratio,0.0)
                glBegin(GL_QUADS)
                glVertex2f(x, y)
                glVertex2f(x+bar_width*health_ratio, y)
                glVertex2f(x+bar_width*health_ratio, y+bar_height)
                glVertex2f(x, y+bar_height)
                glEnd()
            draw_health_bar(w,h)

            icon_y = h-70
            icon_x = 10
            size = 20
            for i,wdef in enumerate(WEAPONS):
                wid_ = wdef["id"]
                c = get_weapon_color(wid_)
                glColor3f(*c)
                glBegin(GL_QUADS)
                glVertex2f(icon_x, icon_y)
                glVertex2f(icon_x+size, icon_y)
                glVertex2f(icon_x+size, icon_y+size)
                glVertex2f(icon_x, icon_y+size)
                glEnd()
                if i == current_weapon_index:
                    glColor3f(1,1,1)
                    glBegin(GL_LINE_LOOP)
                    glVertex2f(icon_x, icon_y)
                    glVertex2f(icon_x+size, icon_y)
                    glVertex2f(icon_x+size, icon_y+size)
                    glVertex2f(icon_x, icon_y+size)
                    glEnd()
                icon_x += size+5

            for (ex, ey, ehp, dist) in enemy_positions_2d:
                bar_width = 30
                bar_height = 4
                hp_ratio = ehp/50.0
                bx = ex - bar_width/2
                by = ey - 2

                glColor3f(0,0,0)
                glBegin(GL_LINE_LOOP)
                glVertex2f(bx, by)
                glVertex2f(bx+bar_width, by)
                glVertex2f(bx+bar_width, by+bar_height)
                glVertex2f(bx, by+bar_height)
                glEnd()

                glColor3f(0.2,0.2,0.2)
                glBegin(GL_QUADS)
                glVertex2f(bx, by)
                glVertex2f(bx+bar_width, by)
                glVertex2f(bx+bar_width, by+bar_height)
                glVertex2f(bx, by+bar_height)
                glEnd()

                glColor3f(1.0 - hp_ratio, hp_ratio, 0.0)
                glBegin(GL_QUADS)
                glVertex2f(bx, by)
                glVertex2f(bx+bar_width*hp_ratio, by)
                glVertex2f(bx+bar_width*hp_ratio, by+bar_height)
                glVertex2f(bx, by+bar_height)
                glEnd()

        else:
            draw_text_2d_cached(font, "Loading chunks...", w//2 - 50, h//2)

        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glEnable(GL_DEPTH_TEST)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
