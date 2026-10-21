import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from scipy.optimize import minimize
im=np.asarray(Image.open(r'C:\Users\u4419394\.claude\uploads\3a7894c0-d954-45e7-ad25-bf31005067da\5f65257c-image.jpg').convert('L')).astype(float)
print(im.shape)
x0,y0,x1,y1=230,560,1190,1480
sub=im[y0:y1,x0:x1]; bg=np.median(sub)
m=sub<bg-60; ys,xs=np.nonzero(m); print('px',m.sum(),'bg',bg)
P=np.c_[xs+x0,ys+y0].astype(float)[::3]; T=cKDTree(P); np.save('pts2.npy',P)
PITCH=50.0; CX,CY=25.0,15.0
def motor(te,n=2500):
    th=np.linspace(0,te,n); r=PITCH*th/(2*np.pi); return r*np.cos(th), r*np.sin(th)
def comp(c,C):  # what spiral.ino actually sends: extra C on every reversal after the first
    out=np.empty_like(c); off=0.0; last=0
    for i in range(len(c)):
        if i: 
            d=np.sign(c[i]-c[i-1])
            if d!=0 and d!=last:
                if last!=0: off+=C*d
                last=d
        out[i]=c[i]+off
    return out
def play(mm,B):
    s=np.empty_like(mm); cur=mm[0]; h=B/2
    for i,v in enumerate(mm):
        if v>cur+h: cur=v-h
        elif v<cur-h: cur=v+h
        s[i]=cur
    return s
cache={}
def sim(p):
    cx,cy,sx,sy,bx,by,te,rot=p
    mx,my=motor(te)
    X=play(comp(mx,CX),max(bx,0)); Y=play(comp(my,CY),max(by,0))
    X-=X[0]; Y-=Y[0]
    u=sx*X; v=-sy*Y; c,s=np.cos(rot),np.sin(rot)
    return np.c_[cx+c*u-s*v, cy+s*u+c*v]
def cost(p):
    S=sim(p); d1=T.query(S)[0]; d2=cKDTree(S).query(P)[0]
    return np.mean(np.minimum(d1,30))+np.mean(np.minimum(d2,30))
best=None
for sy in (1.25,-1.25):
  for te in (7.75*2*np.pi,8*2*np.pi):
    r=minimize(cost,[705,1015,1.25,sy,25,15,te,0],method='Nelder-Mead',options=dict(maxiter=1500))
    print(round(r.fun,2),np.round(r.x,3))
    if best is None or r.fun<best.fun: best=r
r=minimize(cost,best.x,method='Nelder-Mead',options=dict(maxiter=2500))
np.save('best2.npy',r.x); print('FINAL',round(r.fun,3),np.round(r.x,3),'turns',r.x[6]/2/np.pi)
print('true backlash X %.1f Y %.1f  -> applied 25/15 is over by X %.1f Y %.1f'%(r.x[4],r.x[5],25-r.x[4],15-r.x[5]))
