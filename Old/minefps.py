import sys, math, time, random
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

WIN_WIDTH = 1280
WIN_HEIGHT = 720
FOV = 70.0
MOVE_SPEED = 0.1
MOUSE_SENSITIVITY = 0.2
JUMP_SPEED = 0.2
GRAVITY = 0.01
PLAYER_EYE_HEIGHT = 1.7

PLAYER_COLLISION_RADIUS = 0.3
PLAYER_HEIGHT = 1.7

CHUNK_SIZE = 16
RENDER_DISTANCE = 4
GROUND_LEVEL = 0

LOADS_PER_FRAME = 1  # limit chunk loads per frame

WEAPONS = [
    {"name":"Pistol", "color":(0.5,0.5,0.5), "id":"pistol"},
    {"name":"Shotgun", "color":(0.0,0.0,0.8), "id":"shotgun"},
    {"name":"Rocket Launcher", "color":(0.8,0.0,0.0), "id":"rocket"}
]

all_pickups = []
chunk_update_queue = []

def draw_cube_with_edges(x, y, z, val):
    if val == "leaf":
        top_color = (0.0, 0.8, 0.0)
        side_color = (0.0, 0.6, 0.0)
        bottom_color = (0.0, 0.5, 0.0)
    else:
        top_color = (0.0, 1.0, 0.0)
        bottom_color = (0.3, 0.2, 0.1)
        side_color = (0.5, 0.3, 0.1)

    size = 1.0
    bx, by, bz = x, y, z

    glColor3f(*top_color)
    glBegin(GL_QUADS)
    glVertex3f(bx    , by+size, bz)
    glVertex3f(bx+size, by+size, bz)
    glVertex3f(bx+size, by+size, bz+size)
    glVertex3f(bx    , by+size, bz+size)
    glEnd()

    glColor3f(*bottom_color)
    glBegin(GL_QUADS)
    glVertex3f(bx    , by, bz)
    glVertex3f(bx+size, by, bz)
    glVertex3f(bx+size, by, bz+size)
    glVertex3f(bx    , by, bz+size)
    glEnd()

    glColor3f(*side_color)
    # front
    glBegin(GL_QUADS)
    glVertex3f(bx    , by, bz+size)
    glVertex3f(bx+size, by, bz+size)
    glVertex3f(bx+size, by+size, bz+size)
    glVertex3f(bx    , by+size, bz+size)
    glEnd()

    # back
    glBegin(GL_QUADS)
    glVertex3f(bx    , by, bz)
    glVertex3f(bx+size, by, bz)
    glVertex3f(bx+size, by+size, bz)
    glVertex3f(bx    , by+size, bz)
    glEnd()

    # left
    glBegin(GL_QUADS)
    glVertex3f(bx    , by, bz)
    glVertex3f(bx    , by, bz+size)
    glVertex3f(bx    , by+size, bz+size)
    glVertex3f(bx    , by+size, bz)
    glEnd()

    # right
    glBegin(GL_QUADS)
    glVertex3f(bx+size, by, bz)
    glVertex3f(bx+size, by, bz+size)
    glVertex3f(bx+size, by+size, bz+size)
    glVertex3f(bx+size, by+size, bz)
    glEnd()

    glColor3f(0,0,0)
    glBegin(GL_LINES)
    # bottom
    glVertex3f(bx, by, bz); glVertex3f(bx+size, by, bz)
    glVertex3f(bx+size, by, bz); glVertex3f(bx+size, by, bz+size)
    glVertex3f(bx+size, by, bz+size); glVertex3f(bx, by, bz+size)
    glVertex3f(bx, by, bz+size); glVertex3f(bx, by, bz)

    # top
    glVertex3f(bx, by+size, bz); glVertex3f(bx+size, by+size, bz)
    glVertex3f(bx+size, by+size, bz); glVertex3f(bx+size, by+size, bz+size)
    glVertex3f(bx+size, by+size, bz+size); glVertex3f(bx, by+size, bz+size)
    glVertex3f(bx, by+size, bz+size); glVertex3f(bx, by+size, bz)

    # verticals
    glVertex3f(bx, by, bz); glVertex3f(bx, by+size, bz)
    glVertex3f(bx+size, by, bz); glVertex3f(bx+size, by+size, bz)
    glVertex3f(bx+size, by, bz+size); glVertex3f(bx+size, by+size, bz+size)
    glVertex3f(bx, by, bz+size); glVertex3f(bx, by+size, bz+size)
    glEnd()

class Bullet:
    def __init__(self, x, y, z, dx, dy, dz, radius=0.2):
        self.x = x
        self.y = y
        self.z = z
        self.dx = dx
        self.dy = dy
        self.dz = dz
        self.speed = 0.5
        self.distance_traveled = 0
        self.max_distance = 20.0
        self.radius = radius

    def update(self):
        self.x += self.dx * self.speed
        self.y += self.dy * self.speed
        self.z += self.dz * self.speed
        self.distance_traveled += self.speed
        return self.distance_traveled < self.max_distance

    def draw(self, sphere_quad):
        glPushMatrix()
        glTranslatef(self.x, self.y, self.z)
        glColor3f(1.0,0.0,0.0)
        gluSphere(sphere_quad,self.radius,16,16)
        glPopMatrix()

# Rocket and Explosion classes unchanged.
# ...
class Rocket:
    def __init__(self, x, y, z, dx, dy, dz):
        self.x = x
        self.y = y
        self.z = z
        self.dx = dx
        self.dy = dy
        self.dz = dz
        self.speed = 0.3
        self.distance_traveled = 0
        self.max_distance = 50.0
        self.alive = True
        self.blast_radius = 3

    def update(self, world, chunk_lists, explosions):
        if not self.alive:
            return False
        self.x += self.dx * self.speed
        self.y += self.dy * self.speed
        self.z += self.dz * self.speed
        self.distance_traveled += self.speed
        if self.distance_traveled > self.max_distance:
            self.alive = False
            return False

        bx = int(math.floor(self.x))
        by = int(math.floor(self.y))
        bz = int(math.floor(self.z))

        if (bx,by,bz) in world:
            self.explode(bx,by,bz, world, chunk_lists)
            explosions.append(Explosion(self.x,self.y,self.z))
            self.alive = False
            return False
        return True

    def explode(self, bx, by, bz, world, chunk_lists):
        radius = self.blast_radius
        to_remove = []
        for x in range(bx - radius, bx + radius + 1):
            for y in range(by - radius, by + radius + 1):
                for z in range(bz - radius, bz + radius + 1):
                    dx = x - bx
                    dy = y - by
                    dz = z - bz
                    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                    if dist <= radius:
                        if (x,y,z) in world:
                            to_remove.append((x,y,z))
        for coords in to_remove:
            del world[coords]

        updated_chunks = set()
        for (x,y,z) in to_remove:
            cx, cz = chunk_coords_from_world(x,z)
            updated_chunks.add((cx,cz))
        for (cx,cz) in updated_chunks:
            chunk_update_queue.append(("load", cx, cz))

    def draw(self, sphere_quad):
        if not self.alive:
            return
        glPushMatrix()
        glTranslatef(self.x, self.y, self.z)
        glColor3f(1.0,0.5,0.0)
        gluSphere(sphere_quad,0.15,16,16)
        glPopMatrix()

class Explosion:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.particles = []
        for i in range(20):
            dx = random.uniform(-1,1)
            dy = random.uniform(-1,1)
            dz = random.uniform(-1,1)
            length = math.sqrt(dx*dx+dy*dy+dz*dz)
            if length>0:
                dx/=length
                dy/=length
                dz/=length
            speed = random.uniform(0.1,0.3)
            self.particles.append({"x":x,"y":y,"z":z,"dx":dx*speed,"dy":dy*speed,"dz":dz*speed,"life":1.0})
        self.alive = True
        self.fireball_life = 1.0

    def update(self):
        if not self.alive:
            return False
        any_alive = False
        for p in self.particles:
            if p["life"]>0:
                p["x"]+=p["dx"]
                p["y"]+=p["dy"]
                p["z"]+=p["dz"]
                p["life"]-=0.02
                if p["life"]>0:
                    any_alive=True
        self.fireball_life -= 0.02
        if self.fireball_life < 0:
            self.fireball_life = 0

        if not any_alive and self.fireball_life<=0:
            self.alive=False
        return self.alive

    def draw(self, px, py, pz, sphere_quad):
        if not self.alive:
            return
        dx = self.x - px
        dy = self.y - py
        dz = self.z - pz
        dist = math.sqrt(dx*dx+dy*dy+dz*dz)
        point_size = max(1.0, 50.0/(dist+1.0))

        fireball_radius = 1.5 * self.fireball_life
        if fireball_radius > 0:
            glPushMatrix()
            glTranslatef(self.x, self.y, self.z)
            glColor4f(1.0,0.3,0.0,self.fireball_life)
            gluSphere(sphere_quad, fireball_radius,16,16)
            glPopMatrix()

        glPointSize(point_size)
        glBegin(GL_POINTS)
        for p in self.particles:
            if p["life"]>0:
                glColor4f(1.0,0.5,0.0,p["life"])
                glVertex3f(p["x"],p["y"],p["z"])
        glEnd()

def create_initial_world():
    return {}

def generate_chunk(cx, cz, world):
    seed_val = cx * 99999 + cz
    random.seed(seed_val)
    base_x = cx * CHUNK_SIZE
    base_z = cz * CHUNK_SIZE
    for x in range(CHUNK_SIZE):
        for z in range(CHUNK_SIZE):
            world[(base_x+x, GROUND_LEVEL, base_z+z)] = True

    obstacle_count = random.randint(0,3)
    for _ in range(obstacle_count):
        ox = base_x + random.randint(0, CHUNK_SIZE-1)
        oz = base_z + random.randint(0, CHUNK_SIZE-1)
        height = random.randint(2,5)
        for y in range(1, height+1):
            world[(ox, y, oz)] = True
        leaf_y = height+1
        leaf_positions = [(ox, leaf_y, oz),
                          (ox+1, leaf_y, oz),
                          (ox-1, leaf_y, oz),
                          (ox, leaf_y, oz+1),
                          (ox, leaf_y, oz-1)]
        for lx, ly, lz in leaf_positions:
            world[(lx, ly, lz)] = "leaf"

def chunk_coords_from_world(x, z):
    cx = math.floor(x / CHUNK_SIZE)
    cz = math.floor(z / CHUNK_SIZE)
    return cx, cz

def unload_chunk_now(cx, cz, world, chunk_lists):
    base_x = cx * CHUNK_SIZE
    base_z = cz * CHUNK_SIZE
    to_remove = []
    for (bx, by, bz) in list(world.keys()):
        if base_x <= bx < base_x + CHUNK_SIZE and base_z <= bz < base_z + CHUNK_SIZE:
            to_remove.append((bx,by,bz))
    for coords in to_remove:
        del world[coords]
    if (cx, cz) in chunk_lists:
        glDeleteLists(chunk_lists[(cx, cz)], 1)
        del chunk_lists[(cx, cz)]

def load_chunk_now(cx, cz, world, chunk_lists):
    generate_chunk(cx, cz, world)
    chunk_lists[(cx, cz)] = create_chunk_display_list(world,cx,cz)

def create_chunk_display_list(world, cx, cz):
    dlist = glGenLists(1)
    glNewList(dlist, GL_COMPILE)
    base_x = cx * CHUNK_SIZE
    base_z = cz * CHUNK_SIZE
    for (bx,by,bz), val in world.items():
        if base_x <= bx < base_x+CHUNK_SIZE and base_z <= bz < base_z+CHUNK_SIZE:
            draw_cube_with_edges(bx, by, bz, val)
    glEndList()
    return dlist

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

def set_display_mode(fullscreen):
    flags = DOUBLEBUF|OPENGL
    if fullscreen:
        modes = pygame.display.list_modes()
        if not modes or modes == -1:
            display_info = pygame.display.Info()
            native_width = display_info.current_w
            native_height = display_info.current_h
        else:
            native_width, native_height = modes[0]
        screen = pygame.display.set_mode((native_width, native_height), flags|FULLSCREEN)
    else:
        screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT), flags)
    width, height = screen.get_size()
    glViewport(0, 0, width, height)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(FOV, width/float(height), 0.1, 1000.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    return screen

def create_text_texture(text_surface):
    text_data = pygame.image.tostring(text_surface, "RGBA", True)
    w, h = text_surface.get_size()
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, text_data)
    return tex_id, w, h

def draw_text_2d(font, text, x, y):
    text_surface = font.render(text, True, (255,255,255,255))
    tex_id, w, h = create_text_texture(text_surface)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glBegin(GL_QUADS)
    glTexCoord2f(0,1); glVertex2f(x, y)
    glTexCoord2f(1,1); glVertex2f(x+w, y)
    glTexCoord2f(1,0); glVertex2f(x+w, y+h)
    glTexCoord2f(0,0); glVertex2f(x, y+h)
    glEnd()
    glDeleteTextures([tex_id])
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_BLEND)

def raycast_block_hit(px, py, pz, dx, dy, dz, world, max_dist=50.0):
    steps = int(max_dist*10)
    for i in range(steps):
        t = i*0.1
        X = px + dx*t
        Y = py + dy*t
        Z = pz + dz*t
        bx = int(math.floor(X))
        by = int(math.floor(Y))
        bz = int(math.floor(Z))
        if (bx,by,bz) in world:
            return (bx,by,bz)
    return None

def remove_block(bx, by, bz, world, chunk_lists):
    if (bx,by,bz) in world:
        del world[(bx,by,bz)]
        cx, cz = chunk_coords_from_world(bx, bz)
        chunk_update_queue.append(("load", cx, cz))

def load_chunk(cx, cz, world):
    generate_chunk(cx, cz, world)

def unload_chunk_now(cx, cz, world, chunk_lists):
    base_x = cx * CHUNK_SIZE
    base_z = cz * CHUNK_SIZE
    to_remove = []
    for (bx, by, bz) in list(world.keys()):
        if base_x <= bx < base_x + CHUNK_SIZE and base_z <= bz < base_z + CHUNK_SIZE:
            to_remove.append((bx,by,bz))
    for coords in to_remove:
        del world[coords]
    if (cx, cz) in chunk_lists:
        glDeleteLists(chunk_lists[(cx, cz)], 1)
        del chunk_lists[(cx, cz)]

def load_chunk_now(cx, cz, world, chunk_lists):
    generate_chunk(cx, cz, world)
    chunk_lists[(cx, cz)] = create_chunk_display_list(world,cx,cz)

def process_chunk_updates(world, chunk_lists):
    updates_count = 0
    while updates_count < LOADS_PER_FRAME and chunk_update_queue:
        action, cx, cz = chunk_update_queue.pop(0)
        if action == "loadgen":
            load_chunk(cx, cz, world)
            if (cx, cz) in chunk_lists:
                glDeleteLists(chunk_lists[(cx, cz)], 1)
                del chunk_lists[(cx, cz)]
            chunk_lists[(cx, cz)] = create_chunk_display_list(world,cx,cz)
        elif action == "load":
            if (cx, cz) in chunk_lists:
                glDeleteLists(chunk_lists[(cx, cz)], 1)
                del chunk_lists[(cx, cz)]
            chunk_lists[(cx, cz)] = create_chunk_display_list(world,cx,cz)
        elif action == "unload":
            unload_chunk_now(cx, cz, world, chunk_lists)
        updates_count += 1

def slide_movement(px, py, pz, vx, vz, world):
    new_px = px + vx
    new_pz = pz + vz
    if check_collision(new_px, py, new_pz, world):
        # Try sliding along X
        test_px = px + vx
        if not check_collision(test_px, py, pz, world):
            px = test_px
        # Try sliding along Z
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

def update_loaded_chunks(px, pz, world, loaded_chunks, chunk_lists):
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

def all_initial_chunks_loaded(loaded_chunks, chunk_lists):
    # Check if all needed initial chunks are loaded
    # If all currently in loaded_chunks have display lists, consider done.
    for cpos in loaded_chunks:
        if cpos not in chunk_lists:
            return False
    return True

def main():
    pygame.init()
    pygame.font.init()
    font = pygame.font.SysFont("Arial", 18)

    fullscreen = False
    screen = set_display_mode(fullscreen)

    pygame.mouse.set_visible(False)
    pygame.mouse.set_relative_mode(True)

    glClearColor(0.5, 0.7, 1.0, 1.0)
    glEnable(GL_DEPTH_TEST)

    global sphere_quad
    sphere_quad = gluNewQuadric()

    # Temporarily place player at None until chunks loaded
    start_px, start_py, start_pz = 8.0, 2.0, 2.0
    # We won't move player into the world until initial chunks are loaded.
    px = None
    py = None
    pz = None
    rx, ry = 0.0, 90.0
    vy = 0.0
    on_ground = False

    world = create_initial_world()
    loaded_chunks = set()
    chunk_lists = {}

    clock = pygame.time.Clock()

    # Queue initial chunk loads
    update_loaded_chunks(start_px, start_pz, world, loaded_chunks, chunk_lists)

    inventory = {
        "pistol": {"ammo":100, "owned":True},
        "shotgun": {"ammo":100, "owned":True},
        "rocket": {"ammo":100, "owned":True}
    }
    current_weapon_index = 0

    bullets = []
    rockets = []
    explosions = []

    def current_weapon_id():
        return WEAPONS[current_weapon_index]["id"]

    def current_weapon_name():
        return WEAPONS[current_weapon_index]["name"]

    def current_weapon_ammo():
        wid = current_weapon_id()
        return inventory[wid]["ammo"]

    def fire_weapon():
        if px is None:
            return
        wid = current_weapon_id()
        if inventory[wid]["owned"] and inventory[wid]["ammo"] > 0:
            inventory[wid]["ammo"] -= 1
            rad_x = math.radians(rx)
            rad_y = math.radians(ry)
            start_x = px
            start_y = py + PLAYER_EYE_HEIGHT
            start_z = pz
            dx = math.sin(rad_y)*math.cos(rad_x)
            dy = math.sin(rad_x)
            dz = -math.cos(rad_y)*math.cos(rad_x)
            if wid == "pistol":
                bullets.append(Bullet(start_x, start_y, start_z, dx,dy,dz, radius=0.2))
            elif wid == "shotgun":
                for i in range(8):
                    angle_h = random.uniform(-10,10)
                    angle_v = random.uniform(-2,2)
                    rad_y_off = math.radians(ry+angle_h)
                    rad_x_off = math.radians(rx+angle_v)
                    dx2 = math.sin(rad_y_off)*math.cos(rad_x_off)
                    dy2 = math.sin(rad_x_off)
                    dz2 = -math.cos(rad_y_off)*math.cos(rad_x_off)
                    bullets.append(Bullet(start_x, start_y, start_z, dx2,dy2,dz2, radius=0.05))
            elif wid == "rocket":
                rockets.append(Rocket(start_x,start_y,start_z, dx,dy,dz))

    weapon_count = len(WEAPONS)
    running = True
    initial_load_done = False

    while running:
        dt = clock.tick()
        fps = 1000.0/dt if dt>0 else 0.0

        process_chunk_updates(world, chunk_lists)

        # Check if initial chunks are loaded
        if px is None and all_initial_chunks_loaded(loaded_chunks, chunk_lists):
            # Now place the player in the world
            px, py, pz = start_px, start_py, start_pz
            # Ensure player doesn't fall if ground is loaded
            # find ground level at player pos if needed
            # In this simple world ground_level=0 always. So no problem.
            initial_load_done = True

        keys = pygame.key.get_pressed()

        if px is not None:
            forward = (keys[K_w] - keys[K_s])
            strafe = (keys[K_d] - keys[K_a])
            jump = keys[K_SPACE]

            for event in pygame.event.get():
                if event.type == QUIT:
                    running=False
                elif event.type == KEYDOWN:
                    if event.key == K_ESCAPE:
                        running=False
                    elif event.key == K_F11:
                        fullscreen = not fullscreen
                        screen = set_display_mode(fullscreen)
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
                    if event.button == 1:
                        fire_weapon()
                    elif event.button == 4:
                        for i in range(weapon_count):
                            current_weapon_index = (current_weapon_index-1) % weapon_count
                            wid = WEAPONS[current_weapon_index]["id"]
                            if inventory[wid]["owned"]:
                                break
                    elif event.button == 5:
                        for i in range(weapon_count):
                            current_weapon_index = (current_weapon_index+1) % weapon_count
                            wid = WEAPONS[current_weapon_index]["id"]
                            if inventory[wid]["owned"]:
                                break
            px, py, pz, vy, on_ground = move_player(forward, strafe, jump, px, py, pz, vy, on_ground, rx, ry, world)
            px, py, pz, vy, on_ground = apply_gravity(px, py, pz, vy, on_ground, world)
            player_pickup(px, py, pz, inventory)

            update_loaded_chunks(px, pz, world, loaded_chunks, chunk_lists)

            bullets = [b for b in bullets if b.update()]
            rockets = [r for r in rockets if r.update(world, chunk_lists, explosions)]
            explosions = [e for e in explosions if e.update()]
        else:
            # Player not placed yet, just handle events that might quit the game or full screen
            for event in pygame.event.get():
                if event.type == QUIT:
                    running=False
                elif event.type == KEYDOWN:
                    if event.key == K_ESCAPE:
                        running=False
                    elif event.key == K_F11:
                        fullscreen = not fullscreen
                        screen = set_display_mode(fullscreen)
                        pygame.mouse.set_visible(False)
                        pygame.mouse.set_relative_mode(True)

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

            for (cx,cz) in loaded_chunks:
                if (cx,cz) in chunk_lists:
                    glCallList(chunk_lists[(cx, cz)])

            for b in bullets:
                b.draw(sphere_quad)
            for r in rockets:
                r.draw(sphere_quad)
            for e in explosions:
                e.draw(px, py, pz, sphere_quad)

        glDisable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        vp = glGetIntegerv(GL_VIEWPORT)
        screen_w, screen_h = vp[2], vp[3]
        glOrtho(0, screen_w, screen_h, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glColor3f(1,1,1)
        cx = screen_w//2
        cy = screen_h//2
        glBegin(GL_LINES)
        glVertex2f(cx - 10, cy)
        glVertex2f(cx + 10, cy)
        glVertex2f(cx, cy - 10)
        glVertex2f(cx, cy + 10)
        glEnd()

        if px is not None:
            draw_text_2d(font, f"FPS: {fps:.1f}", 10, 10)
            wname = current_weapon_name()
            wammo = current_weapon_ammo()
            draw_text_2d(font, f"Weapon: {wname}  Ammo: {wammo}", 10, screen_h-30)

            icon_y = screen_h-70
            icon_x = 10
            size = 20
            for i,wdef in enumerate(WEAPONS):
                wid_ = wdef["id"]
                if inventory[wid_]["owned"]:
                    c = wdef["color"]
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

        else:
            # If not loaded yet, show loading text
            draw_text_2d(font, "Loading chunks...", screen_w//2 - 50, screen_h//2)

        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glEnable(GL_DEPTH_TEST)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    sphere_quad = None
    main()
