# entities.py

import math, random, time
from OpenGL.GL import *
from OpenGL.GLU import *
from config import PLAYER_EYE_HEIGHT, chunk_update_queue, chunk_coords_from_world, all_enemies
from render import draw_box
import bulletmarks
import pygame

enemy_pistol_sound = None
robodrone_sound = None
robodrone_explosion_sound = None  # For drone explosions

GRAVITY = 36.0

DOG_WIDTH = 0.25
DOG_LENGTH = 0.5
DOG_HEIGHT = 1.1

def get_robodog_boxes():
    body_hw = 0.25
    body_hh = 0.12
    body_hl = 0.5
    body_min = (-body_hw, 0.72 - body_hh, -body_hl)
    body_max = ( body_hw, 0.72 + body_hh, body_hl)

    head_hw = 0.12
    head_hh = 0.12
    head_hl = 0.12
    head_min = (-head_hw, 0.9 - head_hh, 0.62 - head_hl)
    head_max = ( head_hw, 0.9 + head_hh, 0.62 + head_hl)

    leg_hw = 0.05
    leg_hh = 0.3
    leg_hl = 0.05
    # front-left
    fl_min = (-0.2 - leg_hw, 0.3 - leg_hh, 0.45 - leg_hl)
    fl_max = (-0.2 + leg_hw, 0.3 + leg_hh, 0.45 + leg_hl)
    # front-right
    fr_min = (0.2 - leg_hw, 0.3 - leg_hh, 0.45 - leg_hl)
    fr_max = (0.2 + leg_hw, 0.3 + leg_hh, 0.45 + leg_hl)
    # back-left
    bl_min = (-0.2 - leg_hw, 0.3 - leg_hh, -0.45 - leg_hl)
    bl_max = (-0.2 + leg_hw, 0.3 + leg_hh, -0.45 + leg_hl)
    # back-right
    br_min = (0.2 - leg_hw, 0.3 - leg_hh, -0.45 - leg_hl)
    br_max = (0.2 + leg_hw, 0.3 + leg_hh, -0.45 + leg_hl)

    return [
        (body_min, body_max),
        (head_min, head_max),
        (fl_min, fl_max),
        (fr_min, fr_max),
        (bl_min, bl_max),
        (br_min, br_max)
    ]

def line_aabb_intersect(p1, p2, box_min, box_max):
    tmin = 0.0
    tmax = 1.0
    d = (p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2])
    for i, (bmin,bmax) in enumerate(zip(box_min, box_max)):
        start = p1[i]
        delta = d[i]
        if abs(delta)<1e-9:
            if start < bmin or start > bmax:
                return False
        else:
            t0 = (bmin - start)/delta
            t1 = (bmax - start)/delta
            if t0>t1:
                t0,t1=t1,t0
            if t1<tmin or t0>tmax:
                return False
            tmin = max(tmin,t0)
            tmax = min(tmax,t1)
            if tmin>tmax:
                return False
    return True

def bullet_or_rocket_hits_dog(old_pos, new_pos, dog_x, dog_y, dog_z, dog_yaw):
    rel_p1 = (old_pos[0]-dog_x, old_pos[1]-dog_y, old_pos[2]-dog_z)
    rel_p2 = (new_pos[0]-dog_x, new_pos[1]-dog_y, new_pos[2]-dog_z)

    rad = math.radians(dog_yaw)
    cosA = math.cos(rad)
    sinA = math.sin(rad)

    def rotate_y(p):
        x, y, z = p
        x2 = x*cosA + z*sinA
        z2 = -x*sinA + z*cosA
        return (x2,y,z2)

    local_p1 = rotate_y(rel_p1)
    local_p2 = rotate_y(rel_p2)

    boxes = get_robodog_boxes()
    for (bmin,bmax) in boxes:
        if line_aabb_intersect(local_p1, local_p2, bmin, bmax):
            return True
    return False

def dog_collides_with_world(x, y, z, world):
    min_x = int(math.floor(x - DOG_WIDTH))
    max_x = int(math.floor(x + DOG_WIDTH))
    min_y = int(math.floor(y))
    max_y = int(math.floor(y + DOG_HEIGHT))
    min_z = int(math.floor(z - DOG_LENGTH))
    max_z = int(math.floor(z + DOG_LENGTH))
    for bx in range(min_x, max_x+1):
        for by in range(min_y, max_y+1):
            for bz in range(min_z, max_z+1):
                if (bx,by,bz) in world:
                    return True
    return False

def get_block_below(x, y, z, world):
    below_y = int(math.floor(y - 0.1))
    bx = int(math.floor(x))
    bz = int(math.floor(z))
    return (bx, below_y, bz) in world

def line_block_intersect_3d(x1,y1,z1,x2,y2,z2,world):
    steps = int(max(abs(x2-x1), abs(y2-y1), abs(z2-z1))*2)
    if steps < 1:
        steps = 1
    dx = (x2-x1)/steps
    dy = (y2-y1)/steps
    dz = (z2-z1)/steps
    for i in range(steps+1):
        cx = x1+dx*i
        cy = y1+dy*i
        cz = z1+dz*i
        bx = int(math.floor(cx))
        by = int(math.floor(cy))
        bz = int(math.floor(cz))
        if (bx,by,bz) in world and not (i==steps):
            return True
    return None

class Bullet:
    def __init__(self, x, y, z, dx, dy, dz, radius=0.2, speed=30.0, max_dist=20.0, owner=None):
        self.x = x
        self.y = y
        self.z = z
        self.dx = dx
        self.dy = dy
        self.dz = dz
        self.speed = speed
        self.distance_traveled = 0
        self.max_distance = max_dist
        self.radius = radius
        self.owner = owner
        self.last_x = x
        self.last_y = y
        self.last_z = z

    def update(self, dt_s, world, enemies):
        old_pos = (self.x, self.y, self.z)
        self.x += self.dx * self.speed * dt_s
        self.y += self.dy * self.speed * dt_s
        self.z += self.dz * self.speed * dt_s
        self.distance_traveled += self.speed * dt_s
        if self.distance_traveled >= self.max_distance:
            return False

        bx = int(math.floor(self.x))
        by = int(math.floor(self.y))
        bz = int(math.floor(self.z))
        if (bx,by,bz) in world:
            return False

        for e in enemies:
            if e.health > 0 and e is not self.owner:
                if bullet_or_rocket_hits_dog(old_pos, (self.x, self.y, self.z), e.x, e.y, e.z, getattr(e, 'yaw', 0)):
                    e.take_damage(10)
                    return False

        self.last_x, self.last_y, self.last_z = self.x, self.y, self.z
        return True

    def draw(self, sphere_quad):
        glPushMatrix()
        glTranslatef(self.x, self.y, self.z)
        glColor3f(0.0,0.0,0.0)
        gluSphere(sphere_quad,self.radius,16,16)
        glPopMatrix()

class Rocket:
    def __init__(self, x, y, z, dx, dy, dz):
        self.x = x
        self.y = y
        self.z = z
        self.dx = dx
        self.dy = dy
        self.dz = dz
        self.speed = 18.0
        self.distance_traveled = 0
        self.max_distance = 50.0
        self.alive = True
        self.blast_radius = 3
        self.last_x = x
        self.last_y = y
        self.last_z = z

    def update(self, world, enemies, explosions, dt_s):
        if not self.alive:
            return False
        old_pos = (self.x, self.y, self.z)
        self.x += self.dx * self.speed * dt_s
        self.y += self.dy * self.speed * dt_s
        self.z += self.dz * self.speed * dt_s
        self.distance_traveled += self.speed * dt_s
        if self.distance_traveled > self.max_distance:
            self.alive = False
            return False

        for e in enemies:
            if e.health > 0:
                if bullet_or_rocket_hits_dog(old_pos, (self.x,self.y,self.z), e.x, e.y, e.z, getattr(e, 'yaw', 0)):
                    self.explode(world, explosions)
                    self.alive = False
                    return False

        bx = int(math.floor(self.x))
        by = int(math.floor(self.y))
        bz = int(math.floor(self.z))
        if (bx,by,bz) in world:
            self.explode(world, explosions)
            self.alive = False
            return False

        self.last_x,self.last_y,self.last_z = self.x,self.y,self.z
        return True

    def explode(self, world, explosions):
        from config import all_enemies, chunk_update_queue, chunk_coords_from_world
        ex, ey, ez = int(math.floor(self.x)), int(math.floor(self.y)), int(math.floor(self.z))
        radius = self.blast_radius
        to_remove = []
        for X in range(ex - radius, ex + radius + 1):
            for Y in range(ey - radius, ey + radius + 1):
                for Z in range(ez - radius, ez + radius + 1):
                    dist = math.sqrt((X - ex)**2+(Y - ey)**2+(Z - ez)**2)
                    if dist <= radius and (X,Y,Z) in world:
                        to_remove.append((X,Y,Z))

        for e in all_enemies:
            dist = math.sqrt((e.x - self.x)**2 + ((e.y+0.5)-self.y)**2 + (e.z - self.z)**2)
            if dist <= radius:
                e.take_damage(100)

        for coords in to_remove:
            bulletmarks.remove_bullet_marks_for_block(coords)
            del world[coords]

        updated_chunks = set()
        for (X,Y,Z) in to_remove:
            cx, cz = chunk_coords_from_world(X,Z)
            updated_chunks.add((cx,cz))
        for (cx,cz) in updated_chunks:
            chunk_update_queue.append(("load", cx, cz))

        explosions.append(Explosion(self.x,self.y,self.z))

    def draw(self, cylinder_quad):
        if not self.alive:
            return
        glPushMatrix()
        glTranslatef(self.x, self.y, self.z)
        dx, dy, dz = self.dx, self.dy, self.dz
        mag = math.sqrt(dx*dx + dy*dy + dz*dz)
        if mag > 0:
            dx /= mag
            dy /= mag
            dz /= mag
        dot = dz
        if dot > 1.0: dot = 1.0
        if dot < -1.0: dot = -1.0
        angle = math.degrees(math.acos(dot))
        cx = -dy
        cy = dx
        cz = 0.0
        axis_len = math.sqrt(cx*cx+cy*cy+cz*cz)
        if axis_len > 1e-9:
            cx /= axis_len
            cy /= axis_len

        length = 0.5
        radius = 0.05
        glColor3f(0.5,0.5,0.5)
        glRotatef(angle, cx, cy, cz)
        gluCylinder(cylinder_quad, radius, radius, length, 16, 16)

        glPushMatrix()
        glColor3f(1.0,0.0,0.0)
        glRotatef(180,1,0,0)
        gluCylinder(cylinder_quad, radius*0.6, 0.0, 0.2, 16,16)
        glPopMatrix()

        glPopMatrix()

class Explosion:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.particles = []
        for i in range(40):
            dx = random.uniform(-1,1)
            dy = random.uniform(-1,1)
            dz = random.uniform(-1,1)
            length = math.sqrt(dx*dx+dy*dy+dz*dz)
            if length>0:
                dx/=length
                dy/=length
                dz/=length
            speed = random.uniform(6,18)
            self.particles.append({"x":x,"y":y,"z":z,"dx":dx*speed,"dy":dy*speed,"dz":dz*speed,"life":1.0})
        self.alive = True
        self.fireball_life = 1.0
        self.life_decay_per_sec = 1.2

    def update(self, dt_s):
        if not self.alive:
            return False
        any_alive = False
        for p in self.particles:
            if p["life"]>0:
                p["x"]+=p["dx"]*dt_s
                p["y"]+=p["dy"]*dt_s
                p["z"]+=p["dz"]*dt_s
                p["life"]-=self.life_decay_per_sec*dt_s
                if p["life"]>0:
                    any_alive=True
        self.fireball_life -= self.life_decay_per_sec*dt_s
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

class AmmoPickup:
    ammo_info = {
        "pistol": {"amount":50, "color":(0.8,0.8,0.8)},
        "shotgun": {"amount":10, "color":(0.3,0.3,0.3)},
        "rocket": {"amount":5, "color":(0.8,0.4,0.0)}
    }
    def __init__(self, x, y, z, ammo_type, chunk_coords):
        self.x = x
        self.y = y
        self.z = z
        self.ammo_type = ammo_type
        self.chunk_coords = chunk_coords
        self.spawn_time = time.time()

    def get_amount(self):
        return self.ammo_info[self.ammo_type]["amount"]

    def update(self, dt_s):
        pass

    def draw(self):
        elapsed = time.time() - self.spawn_time
        bob = math.sin(elapsed*4.0)*0.25
        c = self.ammo_info[self.ammo_type]["color"]
        px, py, pz = self.x, self.y+bob, self.z
        hw = 0.2
        hh = 0.1
        hl = 0.2
        glColor3f(*c)
        glBegin(GL_QUADS)
        v = [
            (px - hw, py - hh, pz - hl),
            (px + hw, py - hh, pz - hl),
            (px + hw, py + hh, pz - hl),
            (px - hw, py + hh, pz - hl),
            (px - hw, py - hh, pz + hl),
            (px - hw, py + hh, pz + hl),
            (px + hw, py + hh, pz + hl),
            (px + hw, py - hh, pz + hl),
        ]
        faces = [(0,1,2,3),(4,5,6,7),(0,3,5,4),(1,7,6,2),(3,2,6,5),(0,4,7,1)]
        for f in faces:
            for idx in f:
                glVertex3f(*v[idx])
        glEnd()
        glColor3f(0,0,0)
        edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,7),(2,6),(3,5)]
        glBegin(GL_LINES)
        for (a,b) in edges:
            glVertex3f(*v[a])
            glVertex3f(*v[b])
        glEnd()

    def distance_to(self, px, py, pz):
        dx = self.x - px
        dy = self.y - py
        dz = self.z - pz
        return math.sqrt(dx*dx + dy*dy + dz*dz)

class RobotDog:
    def __init__(self, x, y, z, chunk_coords):
        self.x = x
        self.y = y
        self.z = z
        self.chunk_coords = chunk_coords
        self.health = 50
        self.max_health = 50
        self.speed = 6.0
        self.yaw = random.uniform(0,360)
        self.target_yaw = self.yaw
        self.turn_speed = 30.0
        self.walk_timer = 0.0
        self.walk_time = 0.0
        self.change_dir_interval = random.uniform(3,6)
        self.time_since_last_change = 0.0
        self.vy = 0.0
        self._pick_new_direction(force_move=True)

        self.last_shot_time = 0.0
        self.fire_delay = 5.0
        self.shoot_range = 30.0

        self.gun_yaw = 0.0
        self.gun_pitch = 0.0

    def _try_new_direction(self, world):
        for _ in range(10):
            attempt_yaw = random.uniform(0,360)
            rad = math.radians(attempt_yaw)
            f_x = -math.sin(rad)
            f_z = math.cos(rad)
            test_x = self.x + f_x * 0.5
            test_z = self.z + f_z * 0.5
            if not dog_collides_with_world(test_x, self.y, test_z, world):
                return attempt_yaw
        return random.uniform(0,360)

    def _pick_new_direction(self, force_move=False, world=None):
        if world is not None:
            self.target_yaw = self._try_new_direction(world)
        else:
            self.target_yaw = random.uniform(0,360)
        if force_move:
            self.walk_time = random.uniform(2,4)
        else:
            if random.random() < 0.2:
                self.walk_time = 0.0
            else:
                self.walk_time = random.uniform(2,4)
        self.walk_timer = 0.0
        self.time_since_last_change = 0.0
        self.change_dir_interval = random.uniform(3,6)

    def update(self, dt_s, player_pos, world, bullets, explosions):
        if self.health <= 0:
            return False

        # Gravity/falling:
        if not get_block_below(self.x, self.y, self.z, world):
            self.vy -= GRAVITY * dt_s
            new_y = self.y + self.vy*dt_s
            if dog_collides_with_world(self.x, new_y, self.z, world):
                self.vy = 0.0
            else:
                self.y = new_y
        else:
            if self.vy < 0:
                self.vy = 0.0

        # Turn towards target_yaw
        yaw_diff = (self.target_yaw - self.yaw) % 360
        if yaw_diff > 180:
            yaw_diff -= 360
        turn_amount = self.turn_speed * dt_s
        if abs(yaw_diff) < turn_amount:
            self.yaw = self.target_yaw
        else:
            if yaw_diff > 0:
                self.yaw += turn_amount
            else:
                self.yaw -= turn_amount
        self.yaw %= 360

        # Move if walk_time > 0
        if self.walk_time > 0:
            yaw_rad = math.radians(self.yaw)
            forward_x = -math.sin(yaw_rad)
            forward_z = math.cos(yaw_rad)
            proposed_x = self.x + forward_x * self.speed * dt_s
            proposed_z = self.z + forward_z * self.speed * dt_s
            if not dog_collides_with_world(proposed_x, self.y, proposed_z, world):
                self.x = proposed_x
                self.z = proposed_z
                self.walk_timer += dt_s
                if self.walk_timer >= self.walk_time:
                    self.walk_time = 0.0
            else:
                self._pick_new_direction(force_move=True, world=world)

        # Occasionally pick new direction
        self.time_since_last_change += dt_s
        if self.time_since_last_change >= self.change_dir_interval:
            self._pick_new_direction(world=world)

        # Aim at player:
        px, py, pz = player_pos
        dx = px - self.x
        dz = pz - self.z
        rad_yaw = math.radians(self.yaw)

        lx = -(dx*math.cos(-rad_yaw) - dz*math.sin(-rad_yaw))
        lz = dx*math.sin(-rad_yaw) + dz*math.cos(-rad_yaw)

        angle = math.degrees(math.atan2(lx, lz))
        self.gun_yaw = -angle
        self.gun_pitch = 0.0

        dy = (py+PLAYER_EYE_HEIGHT) - (self.y+1.05)
        dist = math.sqrt(dx*dx + dz*dz)
        if dist < self.shoot_range:
            res = line_block_intersect_3d(self.x, self.y+0.5, self.z, px, py+PLAYER_EYE_HEIGHT, pz, world)
            if res is None:
                current_time = time.time()
                if (current_time - self.last_shot_time) > self.fire_delay:
                    mag = math.sqrt(dx*dx+dy*dy+dz*dz)
                    if mag>1e-9:
                        dx/=mag
                        dy/=mag
                        dz/=mag
                    start_x = self.x + dx * 0.6
                    start_y = self.y + 0.8 + dy * 0.6
                    start_z = self.z + dz * 0.6
                    b = Bullet(start_x, start_y, start_z, dx, dy, dz, radius=0.05, owner=self)
                    bullets.append(b)
                    if enemy_pistol_sound is not None:
                        edist = math.sqrt((self.x - px)**2 + (self.y - py)**2 + (self.z - pz)**2)
                        vol = 0.0
                        if edist < 32.0:
                            vol = 1.0 - (edist/32.0)
                        enemy_pistol_sound.set_volume(vol)
                        if vol>0.0:
                            enemy_pistol_sound.play()
                    self.last_shot_time = current_time

        return True

    def take_damage(self, amount):
        self.health -= amount

    def draw(self):
        glPushMatrix()
        glTranslatef(self.x, self.y, self.z)
        glRotatef(-self.yaw, 0,1,0)

        # Body:
        body_hw = 0.25
        body_hh = 0.12
        body_hl = 0.5
        glColor3f(1.0,0.85,0.0)
        draw_box(0,0.72,0,body_hw,body_hh,body_hl)

        # Head:
        glColor3f(0.0,0.0,0.0)
        head_hw = 0.12
        head_hh = 0.12
        head_hl = 0.12
        draw_box(0,0.9,body_hl+head_hl, head_hw, head_hh, head_hl)

        # Legs:
        leg_hw = 0.05
        leg_hh = 0.3
        leg_hl = 0.05
        draw_box(-body_hw+leg_hw,0.3, body_hl-leg_hl, leg_hw, leg_hh, leg_hl)
        draw_box(body_hw-leg_hw,0.3, body_hl-leg_hl, leg_hw, leg_hh, leg_hl)
        draw_box(-body_hw+leg_hw,0.3,-body_hl+leg_hl, leg_hw, leg_hh, leg_hl)
        draw_box(body_hw-leg_hw,0.3,-body_hl+leg_hl, leg_hw, leg_hh, leg_hl)

        # Pistol:
        glPushMatrix()
        glTranslatef(0, 1.05, 0)
        glScalef(1.5,1.5,1.5)
        glRotatef(self.gun_yaw, 0,1,0)
        glRotatef(-self.gun_pitch, 1,0,0)

        def draw_pistol_for_dog():
            glColor3f(0.8,0.8,0.8)
            slide_half_w = 0.03
            slide_half_h = 0.03
            slide_half_l = 0.15
            slide_center_z = 0.075
            draw_box(0,0,slide_center_z, slide_half_w, slide_half_h, slide_half_l)

            handle_half_w = 0.02
            handle_half_h = 0.05
            handle_half_l = 0.05
            handle_center_z = 0.05
            handle_center_y = -0.03 - handle_half_h
            draw_box(0, handle_center_y, handle_center_z, handle_half_w, handle_half_h, handle_half_l)

            barrel_half_w = 0.01
            barrel_half_h = 0.01
            barrel_half_l = 0.05
            barrel_center_z = 0.175
            draw_box(0,0,barrel_center_z, barrel_half_w, barrel_half_h, barrel_half_l)
        draw_pistol_for_dog()
        glPopMatrix()

        glPopMatrix()

class RoboDrone:
    def __init__(self, x, y, z, chunk_coords):
        self.x = x
        self.y = y
        self.z = z
        self.chunk_coords = chunk_coords
        self.health = 5
        self.max_health = 5
        self.patrol_speed = 6.0
        self.attack_speed = 10.0
        self.current_speed = self.patrol_speed
        self.yaw = random.uniform(0,360)
        self.target_yaw = self.yaw
        self.turn_speed = 30.0
        self.time_since_last_change = 0.0
        self.change_dir_interval = random.uniform(3,6)

        # State: "patrol" or "attack"
        self.state = "patrol"

        # Vertical hover parameters
        self.hover_base_y = self.y
        self.hover_amplitude = 0.5
        self.hover_speed = 2.0
        self.hover_timer = 0.0

        self.blast_radius = 3

    def take_damage(self, amount):
        self.health -= amount

    def explode(self, world, explosions):
        # Play explosion sound for drone
        if robodrone_explosion_sound is not None:
            robodrone_explosion_sound.play()

        from config import all_enemies, chunk_update_queue, chunk_coords_from_world
        ex, ey, ez = int(math.floor(self.x)), int(math.floor(self.y)), int(math.floor(self.z))
        radius = self.blast_radius
        to_remove = []
        for X in range(ex - radius, ex + radius + 1):
            for Y in range(ey - radius, ey + radius + 1):
                for Z in range(ez - radius, ez + radius + 1):
                    dist = math.sqrt((X - ex)**2+(Y - ey)**2+(Z - ez)**2)
                    if dist <= radius and (X,Y,Z) in world:
                        to_remove.append((X,Y,Z))

        for e in all_enemies:
            dist = math.sqrt((e.x - self.x)**2 + ((e.y+0.5)-self.y)**2 + (e.z - self.z)**2)
            if dist <= radius:
                e.take_damage(100)

        for coords in to_remove:
            bulletmarks.remove_bullet_marks_for_block(coords)
            del world[coords]

        updated_chunks = set()
        for (X,Y,Z) in to_remove:
            cx, cz = chunk_coords_from_world(X,Z)
            updated_chunks.add((cx,cz))
        for (cx,cz) in updated_chunks:
            chunk_update_queue.append(("load", cx, cz))

        explosions.append(Explosion(self.x,self.y,self.z))

    def _pick_new_direction(self, world=None):
        self.target_yaw = random.uniform(0,360)
        self.time_since_last_change = 0.0
        self.change_dir_interval = random.uniform(3,6)

    def update(self, dt_s, player_pos, world, bullets, explosions):
        if self.health <= 0:
            # Dead: explode if not done
            self.explode(world, explosions)
            return False

        px, py, pz = player_pos
        dx = px - self.x
        dy = (py + PLAYER_EYE_HEIGHT) - self.y
        dz = pz - self.z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)

        if self.state == "patrol":
            if dist < 20.0:
                self.state = "attack"
                self.current_speed = self.attack_speed
            else:
                self.time_since_last_change += dt_s
                if self.time_since_last_change >= self.change_dir_interval:
                    self._pick_new_direction()

                # Turn towards target_yaw
                yaw_diff = (self.target_yaw - self.yaw) % 360
                if yaw_diff > 180:
                    yaw_diff -= 360
                turn_amount = self.turn_speed * dt_s
                if abs(yaw_diff) < turn_amount:
                    self.yaw = self.target_yaw
                else:
                    if yaw_diff > 0:
                        self.yaw += turn_amount
                    else:
                        self.yaw -= turn_amount
                self.yaw %= 360

                # Move forward at patrol speed
                yaw_rad = math.radians(self.yaw)
                forward_x = -math.sin(yaw_rad)
                forward_z = math.cos(yaw_rad)
                self.x += forward_x * self.patrol_speed * dt_s
                self.z += forward_z * self.patrol_speed * dt_s

        elif self.state == "attack":
            if dist < 1.5:
                self.explode(world, explosions)
                self.health = 0
                return False
            angle_to_player = math.degrees(math.atan2(-dx, dz)) % 360
            yaw_diff = (angle_to_player - self.yaw) % 360
            if yaw_diff > 180:
                yaw_diff -= 360
            turn_amount = self.turn_speed * dt_s
            if abs(yaw_diff) < turn_amount:
                self.yaw = angle_to_player
            else:
                if yaw_diff > 0:
                    self.yaw += turn_amount
                else:
                    self.yaw -= turn_amount
            self.yaw %= 360

            # Move towards player
            yaw_rad = math.radians(self.yaw)
            forward_x = -math.sin(yaw_rad)
            forward_z = math.cos(yaw_rad)
            self.y += dy * dt_s * 0.8
            self.x += forward_x * self.attack_speed * dt_s
            self.z += forward_z * self.attack_speed * dt_s

        # Hover effect
        self.hover_timer += dt_s * self.hover_speed
        hover_offset = math.sin(self.hover_timer) * self.hover_amplitude
        if self.state == "patrol":
            self.y = self.hover_base_y + hover_offset

        return True

    def draw(self):
        glPushMatrix()
        glTranslatef(self.x, self.y, self.z)
        glRotatef(-self.yaw, 0,1,0)

        body_hw = 0.15
        body_hh = 0.1
        body_hl = 0.4
        glColor3f(1.0, 0.85, 0.0)
        draw_box(0,0,0, body_hw, body_hh, body_hl)

        # Propellers with a bit of height:
        # 1/4 the height of the body = body height is 2*body_hh = 0.2, 1/4 = 0.05
        prop_radius = 0.3
        prop_height = 0.05
        glColor3f(0.2,0.2,0.2)
        prop_positions = [
            ( body_hw,  body_hh+0.05,  body_hl),
            (-body_hw,  body_hh+0.05,  body_hl),
            ( body_hw,  body_hh+0.05, -body_hl),
            (-body_hw,  body_hh+0.05, -body_hl),
        ]

        quadric = gluNewQuadric()
        for (px, py, pz) in prop_positions:
            glPushMatrix()
            glTranslatef(px, py, pz)
            # Rotate so disk normal is along y-axis (horizontal rotor)
            glRotatef(-90, 1,0,0)
            # Bottom disk
            gluDisk(quadric, 0, prop_radius, 32, 1)
            # Cylinder
            gluCylinder(quadric, prop_radius, prop_radius, prop_height, 32, 1)
            # Move up and top disk
            glTranslatef(0, prop_height, 0)
            gluDisk(quadric, 0, prop_radius, 32, 1)
            glPopMatrix()

        glPopMatrix()