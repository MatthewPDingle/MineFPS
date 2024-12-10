# bulletmarks.py
bullet_marks_by_block = {}  # (bx,by,bz): [ (ix, iy, iz, nx, ny, nz), ... ]

def add_bullet_mark(bx, by, bz, ix, iy, iz, nx, ny, nz):
    block_coords = (bx,by,bz)
    if block_coords not in bullet_marks_by_block:
        bullet_marks_by_block[block_coords] = []
    bullet_marks_by_block[block_coords].append((ix, iy, iz, nx, ny, nz))

def remove_bullet_marks_for_block(block_coords):
    if block_coords in bullet_marks_by_block:
        del bullet_marks_by_block[block_coords]

def get_all_bullet_marks():
    return bullet_marks_by_block

def clear_all_bullet_marks():
    bullet_marks_by_block.clear()
