# fit_backlash.py: fit an 8-turn spiral with play (backlash) per axis to the
# line pixels of a photo of spiral.ino's drawing. pts.npy = Nx2 pixel coords of
# the dark line (threshold < 90 on the screen crop). Printed p = cx, cy, px/deg X,
# px/deg Y, backlash X deg, backlash Y deg, end angle, rotation. 21 Oct photo:
# X 25, Y 15, error 7.5 px vs 13 px with no backlash.
import numpy as np
from scipy.spatial import cKDTree
from scipy.optimize import minimize
P=np.load("pts.npy").astype(float)[::4]; T=cKDTree(P)
PITCH=50.0
def motor(th_end, n=1500):
    th=np.linspace(0,th_end,n); r=PITCH*th/(2*np.pi)
    return r*np.cos(th), r*np.sin(th)
def play(m,B):
    s=np.empty_like(m); cur=0.0; h=B/2
    for i,v in enumerate(m):
        if v>cur+h: cur=v-h
        elif v<cur-h: cur=v+h
        s[i]=cur
    return s
def sim(p):
    cx,cy,sx,sy,bx,by,te,rot=p
    mx,my=motor(te); X=play(mx,max(bx,0)); Y=play(my,max(by,0))
    u=sx*X; v=-sy*Y; c,s=np.cos(rot),np.sin(rot)
    return np.c_[cx+c*u-s*v, cy+s*u+c*v]
def cost(p):
    S=sim(p); d1=T.query(S)[0]; d2=cKDTree(S).query(P)[0]
    return np.mean(np.minimum(d1,30))+np.mean(np.minimum(d2,30))
best=None
for sy in (1.6,-1.6):
  for te in (4.25*2*np.pi,4.75*2*np.pi):
    for b in (15,):
      p0=[706,1165,1.6,sy,b,b,te,0.0]
      r=minimize(cost,p0,method='Nelder-Mead',options=dict(maxiter=1500,xatol=1e-3,fatol=1e-4))
      if best is None or r.fun<best.fun: best=r; print(round(r.fun,2),np.round(r.x,3))
r=minimize(cost,best.x,method='Nelder-Mead',options=dict(maxiter=2500,xatol=1e-4,fatol=1e-5))
np.save('best.npy',r.x); print('FINAL',round(r.fun,3),np.round(r.x,3),'turns',r.x[6]/2/np.pi)
# compare to zero backlash with everything else refit
def cost0(q): return cost(list(q[:4])+[0,0]+list(q[4:]))
r0=minimize(cost0,list(r.x[:4])+list(r.x[6:]),method='Nelder-Mead',options=dict(maxiter=2500))
print('NO-BACKLASH fit',round(r0.fun,3))
