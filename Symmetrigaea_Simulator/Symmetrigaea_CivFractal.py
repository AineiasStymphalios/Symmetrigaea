"""Python 2.4 port of the unwrapped BTS CvFractal height generator.

The algorithm follows CvFractal.cpp and CvRandom.cpp in the local BTS SDK.
It does not use the game's shared random stream or map wrapping flags.
"""


class CivRandom:
    def __init__(self, seed):
        self.seed = seed & 0xffffffff

    def get(self, upper):
        self.seed = (1103515245 * self.seed + 12345) & 0xffffffff
        return (((self.seed >> 16) & 65535) * upper) // 65536


class CivFractal:
    def __init__(self, width, height, grain, random_source, cancel=None):
        self.width = width
        self.height = height
        self.frac_width = 128
        self.frac_height = 64
        self.x_inc = (self.frac_width * 1000) // width
        self.y_inc = (self.frac_height * 1000) // height
        grid = [[0] * 65 for dummy in range(129)]
        smooth = max(0, min(6, 6 - grain))
        for level in range(smooth, -1, -1):
            if cancel is not None:
                cancel()
            screen = (1 << (level + 1)) - 1
            spread = 1 << (8 - smooth + level)
            center = 1 << (7 - smooth + level)
            for x in range((128 >> level) + 1):
                gx = x << level
                for y in range((64 >> level) + 1):
                    gy = y << level
                    if level == smooth:
                        grid[gx][gy] = random_source.get(256)
                    elif gx & screen:
                        if gy & screen:
                            value = (grid[(x-1) << level][(y-1) << level] +
                                     grid[(x+1) << level][(y-1) << level] +
                                     grid[(x-1) << level][(y+1) << level] +
                                     grid[(x+1) << level][(y+1) << level]) >> 2
                        else:
                            value = (grid[(x-1) << level][gy] +
                                     grid[(x+1) << level][gy]) >> 1
                        value += random_source.get(spread) - center
                        grid[gx][gy] = max(0, min(255, value))
                    elif gy & screen:
                        value = (grid[gx][(y-1) << level] +
                                 grid[gx][(y+1) << level]) >> 1
                        value += random_source.get(spread) - center
                        grid[gx][gy] = max(0, min(255, value))
        self.grid = grid
        histogram = [0] * 256
        for x in range(128):
            for y in range(64):
                histogram[grid[x][y]] += 1
        self.below = [0] * 257
        count = 0
        for value in range(256):
            self.below[value] = count
            count += histogram[value]
        self.below[256] = count

    def get_height(self, x, y):
        x_pos = self.x_inc * x
        y_pos = self.y_inc * y
        low_x = min(127, x_pos // 1000)
        low_y = min(63, y_pos // 1000)
        err_x = x_pos - low_x * 1000
        err_y = y_pos - low_y * 1000
        grid = self.grid
        total = ((1000 - err_x) * (1000 - err_y) * grid[low_x][low_y] +
                 err_x * (1000 - err_y) * grid[low_x + 1][low_y] +
                 (1000 - err_x) * err_y * grid[low_x][low_y + 1] +
                 err_x * err_y * grid[low_x + 1][low_y + 1])
        return max(0, min(255, total // 1000000))

    def get_height_from_percent(self, percent):
        percent = max(0, min(100, percent))
        low = 0
        high = 255
        estimate = (255 * percent) // 100
        while estimate != low:
            count = self.below[estimate]
            if (100 * count // 128 // 64) > percent:
                high = estimate
            else:
                low = estimate
            estimate = (high + low) // 2
        return estimate
