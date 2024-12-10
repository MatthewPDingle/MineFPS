# entities.py
import math, random, time
from OpenGL.GL import *
from OpenGL.GLU import *
from config import PLAYER_EYE_HEIGHT, chunk_update_queue, chunk_coords_from_world, all_enemies
from render import draw_box
import bulletmarks

enemy_pistol_sound = None

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
        self.owner = owner  # 'player' or enemy instance

    def update(self, dt_s):
        self.x += self.dx * self.speed * dt_s
        self.y += self.dy * self.speed * dt_s
        self.z += self.dz * self.speed * dt_s
        self.distance_traveled += self.speed * dt_s
        return self.distance_traveled < self.max_distance

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

    def update(self, world, chunk_lists, explosions, dt_s):
        if not self.alive:
            return False
        self.x += self.dx * self.speed * dt_s
        self.y += self.dy * self.speed * dt_s
        self.z += self.dz * self.speed * dt_s
        self.distance_traveled += self.speed * dt_s
        if self.distance_traveled > self.max_distance:
            self.alive = False
            return False

        for e in all_enemies:
            edx = e.x - self.x
            edy = (e.y+0.5) - self.y
            edz = e.z - self.z
            dist = math.sqrt(edx*edx+edy*edy+edz*edz)
            if dist < 0.5:
                self.explode(int(math.floor(self.x)), int(math.floor(self.y)), int(math.floor(self.z)), world, chunk_lists)
                explosions.append(Explosion(self.x,self.y,self.z))
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

        for e in all_enemies:
            edx = e.x - self.x
            edy = (e.y+0.5) - self.y
            edz = e.z - self.z
            dist = math.sqrt(edx*edx+edy*edy+edz*edz)
            if dist <= radius:
                e.take_damage(100)

        for coords in to_remove:
            bulletmarks.remove_bullet_marks_for_block(coords)
            del world[coords]

        updated_chunks = set()
        for (x,y,z) in to_remove:
            cx, cz = chunk_coords_from_world(x,z)
            updated_chunks.add((cx,cz))
        for (cx,cz) in updated_chunks:
            chunk_update_queue.append(("load", cx, cz))

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

        faces = [
            (0,1,2,3),
            (4,5,6,7),
            (0,3,5,4),
            (1,7,6,2),
            (3,2,6,5),
            (0,4,7,1),
        ]
        for f in faces:
            for idx in f:
                glVertex3f(*v[idx])
        glEnd()

        glColor3f(0,0,0)
        edges = [
            (0,1),(1,2),(2,3),(3,0),
            (4,5),(5,6),(6,7),(7,4),
            (0,4),(1,7),(2,6),(3,5)
        ]
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
        self.last_shot_time = 0.0
        self.fire_delay = 5.0
        self.ideal_distance = 10.0
        self.shoot_range = 30.0
        self.speed = 2.0
        self.yaw = 0.0  # For facing direction

    def update(self, dt_s, player_pos, world, bullets):
        if self.health <= 0:
            return False

        px, py, pz = player_pos
        dx = self.x - px
        dz = self.z - pz
        dist = math.sqrt(dx*dx + dz*dz)

        moved = False
        if dist < self.ideal_distance:
            angle = math.atan2(dz, dx)
            self.x += math.cos(angle)*self.speed*dt_s
            self.z += math.sin(angle)*self.speed*dt_s
            moved = True
        elif dist > self.ideal_distance+5:
            angle = math.atan2(-dz, -dx)
            self.x += math.cos(angle)*self.speed*dt_s
            self.z += math.sin(angle)*self.speed*dt_s
            moved = True

        if dist < self.ideal_distance:
            angle = math.atan2(dz, dx)
        elif dist > self.ideal_distance+5:
            angle = math.atan2(-dz, -dx)
        else:
            angle = None

        if angle is not None:
            self.yaw = math.degrees(angle)-90

        from world import line_block_intersect_3d
        res = line_block_intersect_3d(self.x, self.y+0.5, self.z, px, py+PLAYER_EYE_HEIGHT, pz, world)
        if res is None and dist < self.shoot_range:
            current_time = time.time()
            if (current_time - self.last_shot_time) > self.fire_delay:
                dirx = px - self.x
                diry = (py+PLAYER_EYE_HEIGHT) - (self.y+0.5)
                dirz = pz - self.z
                mag = math.sqrt(dirx*dirx+diry*diry+dirz*dirz)
                if mag > 1e-9:
                    dirx /= mag
                    diry /= mag
                    dirz /= mag
                start_x = self.x + dirx * 0.6
                start_y = self.y + 0.8 + diry * 0.6
                start_z = self.z + dirz * 0.6
                b = Bullet(start_x, start_y, start_z, dirx, diry, dirz, radius=0.05, owner=self)
                bullets.append(b)
                edist = math.sqrt((self.x - px)**2 + (self.y - py)**2 + (self.z - pz)**2)
                vol = 0.0
                if edist < 32.0:
                    vol = 1.0 - (edist/32.0)
                if enemy_pistol_sound is not None:
                    enemy_pistol_sound.set_volume(vol)
                    if vol > 0.0:
                        enemy_pistol_sound.play()
                self.last_shot_time = current_time

        return True

    def take_damage(self, amount):
        self.health -= amount

    def draw(self):
        glPushMatrix()
        glTranslatef(self.x, self.y, self.z)
        glRotatef(self.yaw, 0,1,0)

        glColor3f(1.0,0.85,0.0)
        body_hw = 0.5
        body_hh = 0.3
        body_hl = 0.5
        draw_box(0, body_hh, 0, body_hw, body_hh, body_hl)

        glColor3f(0.0,0.0,0.0)
        head_hw = 0.2
        head_hh = 0.2
        head_hl = 0.2
        draw_box(0, body_hh+0.2, -body_hl-head_hl, head_hw, head_hh, head_hl)

        glColor3f(0.0,0.0,0.0)
        leg_hw = 0.05
        leg_hh = 0.3
        leg_hl = 0.05
        draw_box(-body_hw+leg_hw, leg_hh, -body_hl+leg_hl, leg_hw, leg_hh, leg_hl)
        draw_box(body_hw-leg_hw, leg_hh, -body_hl+leg_hl, leg_hw, leg_hh, leg_hl)
        draw_box(-body_hw+leg_hw, leg_hh, body_hl-leg_hl, leg_hw, leg_hh, leg_hl)
        draw_box(body_hw-leg_hw, leg_hh, body_hl-leg_hl, leg_hw, leg_hh, leg_hl)

        glPushMatrix()
        glTranslatef(0, body_hh+0.35, 0)
        glScalef(0.5,0.5,0.5)
        def draw_pistol_for_dog():
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
        draw_pistol_for_dog()
        glPopMatrix()

        glPopMatrix()
