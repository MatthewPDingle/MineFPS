# render.py
import pygame
from pygame.locals import *
import math
from OpenGL.GL import *
from OpenGL.GLU import *
from config import *

text_cache = {}

def create_text_texture(text_surface):
    text_data = pygame.image.tostring(text_surface, "RGBA", True)
    w, h = text_surface.get_size()
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, text_data)
    return tex_id, w, h

def draw_text_2d_cached(font, text, x, y):
    key = (text, font.get_height(), font.get_bold(), font.get_italic())
    if key not in text_cache:
        text_surface = font.render(text, True, (255,255,255,255))
        tex_id, w, h = create_text_texture(text_surface)
        text_cache[key] = (tex_id, w, h, text)
    else:
        tex_id, w, h, old_text = text_cache[key]
        if old_text != text:
            glDeleteTextures([tex_id])
            text_surface = font.render(text, True, (255,255,255,255))
            tex_id, w, h = create_text_texture(text_surface)
            text_cache[key] = (tex_id, w, h, text)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, text_cache[key][0])
    glBegin(GL_QUADS)
    glTexCoord2f(0,1); glVertex2f(x, y)
    glTexCoord2f(1,1); glVertex2f(x+w, y)
    glTexCoord2f(1,0); glVertex2f(x+w, y+h)
    glTexCoord2f(0,0); glVertex2f(x, y+h)
    glEnd()
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_BLEND)

def draw_box(cx, cy, cz, hw, hh, hl):
    v = [
        (cx - hw, cy - hh, cz - hl),
        (cx + hw, cy - hh, cz - hl),
        (cx + hw, cy + hh, cz - hl),
        (cx - hw, cy + hh, cz - hl),

        (cx - hw, cy - hh, cz + hl),
        (cx - hw, cy + hh, cz + hl),
        (cx + hw, cy + hh, cz + hl),
        (cx + hw, cy - hh, cz + hl),
    ]

    glBegin(GL_QUADS)
    glVertex3f(*v[0]); glVertex3f(*v[1]); glVertex3f(*v[2]); glVertex3f(*v[3])
    glVertex3f(*v[4]); glVertex3f(*v[5]); glVertex3f(*v[6]); glVertex3f(*v[7])
    glVertex3f(*v[0]); glVertex3f(*v[3]); glVertex3f(*v[5]); glVertex3f(*v[4])
    glVertex3f(*v[1]); glVertex3f(*v[7]); glVertex3f(*v[6]); glVertex3f(*v[2])
    glVertex3f(*v[3]); glVertex3f(*v[2]); glVertex3f(*v[6]); glVertex3f(*v[5])
    glVertex3f(*v[0]); glVertex3f(*v[4]); glVertex3f(*v[7]); glVertex3f(*v[1])
    glEnd()

    edges = [
        (0,1),(1,2),(2,3),(3,0),
        (4,5),(5,6),(6,7),(7,4),
        (0,4),(1,7),(2,6),(3,5)
    ]
    glBegin(GL_LINES)
    glColor3f(0,0,0)
    for (a,b) in edges:
        glVertex3f(*v[a])
        glVertex3f(*v[b])
    glEnd()

def set_display_mode(fullscreen):
    pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1)
    pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 4)

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

    glEnable(GL_MULTISAMPLE)
    glEnable(GL_LINE_SMOOTH)
    glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

    return screen

def build_chunk_vertex_data(chunk_data, cx, cz):
    def block_colors(val):
        if val == "leaf":
            return {
                "top":(0.0, 0.8, 0.0),
                "bottom":(0.0,0.5,0.0),
                "side":(0.0,0.6,0.0)
            }
        else:
            return {
                "top":(0.0, 1.0, 0.0),
                "bottom":(0.3, 0.2, 0.1),
                "side":(0.5, 0.3, 0.1)
            }

    def block_exists(bx,by,bz):
        return (bx,by,bz) in chunk_data

    face_data = []
    edge_data = []
    size = 1.0

    def add_face_edges(ex,ey,ez, direction):
        directions = {
            "top":[(ex,ey+size,ez),(ex+size,ey+size,ez),(ex+size,ey+size,ez+size),(ex,ey+size,ez+size)],
            "bottom":[(ex,ey,ez),(ex+size,ey,ez),(ex+size,ey,ez+size),(ex,ey,ez+size)],
            "north":[(ex,ey,ez),(ex+size,ey,ez),(ex+size,ey+size,ez),(ex,ey+size,ez)],
            "south":[(ex,ey,ez+size),(ex+size,ey,ez+size),(ex+size,ey+size,ez+size),(ex,ey+size,ez+size)],
            "west":[(ex,ey,ez),(ex,ey,ez+size),(ex,ey+size,ez+size),(ex,ey+size,ez)],
            "east":[(ex+size,ey,ez),(ex+size,ey,ez+size),(ex+size,ey+size,ez+size),(ex+size,ey+size,ez)]
        }
        quads = directions[direction]
        for i in range(len(quads)):
            x1,y1,z1 = quads[i]
            x2,y2,z2 = quads[(i+1)%len(quads)]
            edge_data.extend([x1,y1,z1,0,0,0,x2,y2,z2,0,0,0])

    for (bx,by,bz), val in chunk_data.items():
        c = block_colors(val)
        # top
        if not block_exists(bx, by+1, bz):
            tc = c["top"]
            face_data += [
                bx,by+size,bz,tc[0],tc[1],tc[2],
                bx+size,by+size,bz,tc[0],tc[1],tc[2],
                bx+size,by+size,bz+size,tc[0],tc[1],tc[2],

                bx,by+size,bz,tc[0],tc[1],tc[2],
                bx+size,by+size,bz+size,tc[0],tc[1],tc[2],
                bx,by+size,bz+size,tc[0],tc[1],tc[2],
            ]
            add_face_edges(bx,by,bz,"top")

        # bottom
        if not block_exists(bx, by-1, bz):
            bc = c["bottom"]
            face_data += [
                bx,by,bz,bc[0],bc[1],bc[2],
                bx+size,by,bz+size,bc[0],bc[1],bc[2],
                bx+size,by,bz,bc[0],bc[1],bc[2],

                bx,by,bz,bc[0],bc[1],bc[2],
                bx,by,bz+size,bc[0],bc[1],bc[2],
                bx+size,by,bz+size,bc[0],bc[1],bc[2],
            ]
            add_face_edges(bx,by,bz,"bottom")

        # north
        if not block_exists(bx, by, bz-1):
            sc = c["side"]
            face_data += [
                bx,by,bz,sc[0],sc[1],sc[2],
                bx+size,by,bz,sc[0],sc[1],sc[2],
                bx+size,by+size,bz,sc[0],sc[1],sc[2],

                bx,by,bz,sc[0],sc[1],sc[2],
                bx+size,by+size,bz,sc[0],sc[1],sc[2],
                bx,by+size,bz,sc[0],sc[1],sc[2],
            ]
            add_face_edges(bx,by,bz,"north")

        # south
        if not block_exists(bx, by, bz+1):
            sc = c["side"]
            face_data += [
                bx,by,bz+size,sc[0],sc[1],sc[2],
                bx+size,by,bz+size,sc[0],sc[1],sc[2],
                bx+size,by+size,bz+size,sc[0],sc[1],sc[2],

                bx,by,bz+size,sc[0],sc[1],sc[2],
                bx+size,by+size,bz+size,sc[0],sc[1],sc[2],
                bx,by+size,bz+size,sc[0],sc[1],sc[2],
            ]
            add_face_edges(bx,by,bz,"south")

        # west
        if not block_exists(bx-1, by, bz):
            sc = c["side"]
            face_data += [
                bx,by,bz,sc[0],sc[1],sc[2],
                bx,by,bz+size,sc[0],sc[1],sc[2],
                bx,by+size,bz+size,sc[0],sc[1],sc[2],

                bx,by,bz,sc[0],sc[1],sc[2],
                bx,by+size,bz+size,sc[0],sc[1],sc[2],
                bx,by+size,bz,sc[0],sc[1],sc[2],
            ]
            add_face_edges(bx,by,bz,"west")

        # east
        if not block_exists(bx+1, by, bz):
            sc = c["side"]
            face_data += [
                bx+size,by,bz,sc[0],sc[1],sc[2],
                bx+size,by,bz+size,sc[0],sc[1],sc[2],
                bx+size,by+size,bz+size,sc[0],sc[1],sc[2],

                bx+size,by,bz,sc[0],sc[1],sc[2],
                bx+size,by+size,bz+size,sc[0],sc[1],sc[2],
                bx+size,by+size,bz,sc[0],sc[1],sc[2],
            ]
            add_face_edges(bx,by,bz,"east")

    face_data_gl = (GLfloat * len(face_data))(*face_data)
    edge_data_gl = (GLfloat * len(edge_data))(*edge_data)

    return (face_data_gl, edge_data_gl)

def create_vbo_from_vertex_data(face_data, edge_data):
    all_data = list(face_data) + list(edge_data)
    vertex_data_gl = (GLfloat * len(all_data))(*all_data)

    vbo_id = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, vbo_id)
    glBufferData(GL_ARRAY_BUFFER, len(vertex_data_gl)*4, vertex_data_gl, GL_STATIC_DRAW)
    glBindBuffer(GL_ARRAY_BUFFER, 0)

    face_vertex_count = len(face_data)//6
    edge_vertex_count = len(edge_data)//6

    return vbo_id, face_vertex_count, edge_vertex_count

def render_chunk_vbo(vbo_id, face_vertex_count, edge_vertex_count):
    glBindBuffer(GL_ARRAY_BUFFER, vbo_id)
    glEnableClientState(GL_VERTEX_ARRAY)
    glEnableClientState(GL_COLOR_ARRAY)

    stride = 6 * 4
    glVertexPointer(3, GL_FLOAT, stride, None)
    glColorPointer(3, GL_FLOAT, stride, ctypes.c_void_p(3*4))

    glDrawArrays(GL_TRIANGLES, 0, face_vertex_count)
    edge_start = face_vertex_count
    glDrawArrays(GL_LINES, edge_start, edge_vertex_count)

    glDisableClientState(GL_COLOR_ARRAY)
    glDisableClientState(GL_VERTEX_ARRAY)
    glBindBuffer(GL_ARRAY_BUFFER, 0)
