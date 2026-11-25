"""Projection, primitive faces and screen-to-floor picking (world Y points up)."""
from math import cos, sin, radians, pi


def rotate(point, angles):
    x, y, z = point
    a,b,c = map(radians, angles)
    y,z = y*cos(a)-z*sin(a), y*sin(a)+z*cos(a)
    x,z = x*cos(b)+z*sin(b), -x*sin(b)+z*cos(b)
    return x*cos(c)-y*sin(c), x*sin(c)+y*cos(c), z


def faces(obj):
    w,h,d = [v/2 for v in obj["size"]]
    if obj["shape"] == "Cylinder":
        rings = [[(w*cos(i*pi/10), k*h, d*sin(i*pi/10)) for i in range(20)] for k in (-1,1)]
    else:
        base = [(-w,-d),(w,-d),(w,d),(-w,d)]
        rings = [[(x,-h,z) for x,z in base],
                 [(x,-h if obj["shape"] == "Ramp" and z < 0 else h,z) for x,z in base]]
    lo,hi = rings
    polygons = [lo,hi] + [[lo[i-1],lo[i],hi[i],hi[i-1]] for i in range(len(lo))]
    return [[tuple(a+b for a,b in zip(rotate(p,obj["rotation"]),obj["pos"])) for p in poly] for poly in polygons]


class Camera:
    def __init__(self):
        self.yaw, self.pitch = .65, .55
        self.view = "Orbit"
        self.zoom = 1
        self.center = [0,0]

    def axes(self, point):
        x,y,z = point
        if self.view == "Top": return x,z,-y
        if self.view == "Front": return x,-y,z
        if self.view == "Side": return z,-y,-x
        a,b = self.yaw,self.pitch
        u = x*cos(a)-z*sin(a)
        v = x*sin(a)+z*cos(a)
        return u, -y*cos(b)+v*sin(b), -v*cos(b)-y*sin(b)

    def screen(self, point):
        u,v,depth = self.axes(point) if len(point)==3 else (*point,0)
        factor = 1200/max(100,1200+depth) if len(point)==3 and self.view=="Orbit" else 1
        return self.center[0]+u*self.zoom*factor, self.center[1]+v*self.zoom*factor

    def pick(self, sx,sy,dim):
        u,v = (sx-self.center[0])/self.zoom,(sy-self.center[1])/self.zoom
        if dim=="2D": return [u,v]
        if self.view=="Front": return [u,-v,0]
        if self.view=="Side": return [0,-v,u]
        if self.view=="Top": return [u,0,v]
        depth = v / max(.04, sin(self.pitch)+v*cos(self.pitch)/1200)
        horizontal = u*(1-depth*cos(self.pitch)/1200)
        return [horizontal*cos(self.yaw)+depth*sin(self.yaw),0,
                -horizontal*sin(self.yaw)+depth*cos(self.yaw)]

