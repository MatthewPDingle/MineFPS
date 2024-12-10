# entities.py
import math, random
from OpenGL.GL import *
from OpenGL.GLU import *
from config import PLAYER_EYE_HEIGHT, chunk_update_queue
from world import chunk_coords_from_world
import bulletmarks

class Bullet:
    # Using real time steps, speed was originally 0.5/frame @60fps = 30 units/s
    def __init__(self, x, y, z, dx, dy, dz, radius=0.2):
        self.x = x
        self.y = y
        self.z = z
        self.dx = dx
        self.dy = dy
        self.dz = dz
        self.speed = 30.0
        self.distance_traveled = 0
        self.max_distance = 20.0
        self.radius = radius

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
    # Originally 0.3/frame @60fps=18 units/s
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
    # Originally particles life reduced by 0.02/frame → 1.2/s
    # Speeds 0.1-0.3/frame → 6-18 units/s
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
